#!/usr/bin/env python3
"""
MCP Agent - 模拟 Claude Code 的 MCP 架构
通过自然语言与大模型交互，自动调用 MCP 服务

MCP 通信使用官方 mcp 库（pip install mcp）：
  - stdio  : mcp.client.stdio.stdio_client
  - sse    : mcp.client.sse.sse_client
  - http   : mcp.client.streamable_http.streamable_http_client

支持的 LLM 提供商:
  - moonshot  : Moonshot Kimi（默认，OpenAI 兼容接口）
  - openai    : OpenAI GPT
  - anthropic : Anthropic Claude
"""

import asyncio
import json
import logging
import os
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

# 官方 MCP 库
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import TextContent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# MCP Server Manager
# ============================================================================

# 导入 MCP Server Manager 包
from mcp_server_manager import MCPServerManager, MCPServerConfig, ConnectedServer


# ============================================================================
# LLM Integration
# ============================================================================

# 导入 models.py 中的模型接口
from models import KimiInterface



# ============================================================================
# MCP Agent
# ============================================================================

class MCPAgent:
    """MCP Agent - 核心协调器"""

    def __init__(
        self,
        llm_provider: str = "moonshot",
        llm_model: str = None,
        llm_api_key: str = None,
        llm_base_url: str = None,
        mcp_config_path: str = None,
    ):
        self.server_manager = MCPServerManager(mcp_config_path)
        
        # LLM 相关属性
        self.api_key = llm_api_key or "sk-nA0TzOl3JSRBNw9b7WfBWcYvx6JzEdf7fdPJFdqXTlJDe9iG"
        # 确保 model 不为 None，使用默认值 "kimi-k2.5"
        self.model = llm_model or "kimi-k2.5"
        self.llm_interface = KimiInterface(model=self.model, api_key=self.api_key)
        logger.info(f"LLM Client: provider=kimi, model={self.model}")

        self.messages: List[Dict[str, Any]] = []
        self._tools_cache: Optional[List[Dict[str, Any]]] = None
        # safe_name -> (server_name, tool_name)
        self._tool_name_map: Dict[str, Tuple[str, str]] = {}
        # 存储服务器配置（用于系统提示词）
        self._server_configs: Dict[str, Dict[str, Any]] = {}

    def build_system_prompt(self, tools: List[Dict[str, Any]], server_configs: Dict[str, Dict[str, Any]]) -> str:
        """
        动态构建系统提示词（仿照 Claude Code）

        Args:
            tools: 格式化后的工具列表
            server_configs: MCP 服务器配置信息（用于添加 command/args/env）

        Returns:
            系统提示词
        """
        # 基础提示词
        system_prompt = """你是 MCP Agent，通过自然语言调用 MCP (Model Context Protocol) 服务完成任务。

# 你的能力
- 可以访问多个 MCP 服务器提供的工具
- 根据用户需求选择合适的工具
- 将工具结果整合成清晰的答案

# 工具调用格式
当你决定调用工具时，必须返回符合以下格式的 JSON：

```json
{
  "toolcalls": [
    {
      "name": "mcp_tool_call",
      "parameters": {
        "tool_name": "server_name__tool_name",
        "args": {
          "parameter_name": "value",
          ...
        }
      }
    }
  ]
}
```

注意事项：
1. `tool_name` 格式为 `server_name__tool_name`（双下划线分隔）
2. `parameters` 必须符合工具定义的 JSON Schema
3. 一次只能调用一个工具
4. 如果不需要工具，直接返回文本回答即可

# 工具使用指南
"""

        # 添加工具列表到系统提示词
        if tools:
            system_prompt += "\n## 可用工具\n\n"
            # 按服务器分组
            tools_by_server = {}
            for tool in tools:
                func = tool["function"]
                server_name = tool.get("_server", "Unknown")
                if server_name not in tools_by_server:
                    tools_by_server[server_name] = []
                tools_by_server[server_name].append(func)

            # 输出每个服务器的工具
            for server_name, server_tools in tools_by_server.items():
                system_prompt += f"### {server_name}\n\n"
                for tool in server_tools:
                    name = tool["name"]
                    desc = tool["description"]
                    params = tool.get("parameters", {})
                    required = params.get("required", [])
                    properties = params.get("properties", {})

                    system_prompt += f"**{name}**\n"
                    system_prompt += f"- 描述: {desc}\n"

                    if properties:
                        system_prompt += "- 参数:\n"
                        for param_name, param_schema in properties.items():
                            param_type = param_schema.get("type", "unknown")
                            param_desc = param_schema.get("description", "")
                            is_required = param_name in required

                            system_prompt += f"  - `{param_name}`"
                            if is_required:
                                system_prompt += " (必需)"
                            system_prompt += f" [{param_type}]"
                            if param_desc:
                                system_prompt += f": {param_desc}"
                            system_prompt += "\n"

                    system_prompt += "\n"

        # 添加 MCP 服务器信息（包含 command/args/env）
        if server_configs:
            system_prompt += "\n## MCP 服务器配置\n\n"
            system_prompt += "以下为已连接的 MCP 服务器及其启动配置（仅供参考，无需在工具调用中包含这些信息）：\n\n"

            for server_name, config in server_configs.items():
                system_prompt += f"### {server_name}\n"
                system_prompt += f"- 命令: `{config.get('command', 'N/A')}`\n"
                system_prompt += f"- 参数: `{' '.join(config.get('args', []))}`\n"
                if config.get('env'):
                    env_str = ", ".join([f"{k}={v}" for k, v in config['env'].items()])
                    system_prompt += f"- 环境变量: `{env_str}`\n"
                system_prompt += "\n"

        # 添加响应格式说明
        system_prompt += """
# 响应格式

## 需要调用工具时
```json
{
  "toolcalls": [
    {
      "name": "mcp_tool_call",
      "parameters": {
        "tool_name": "filesystem__read_file",
        "args": {
          "path": "/path/to/file.txt"
        }
      }
    }
  ]
}
```

## 不需要工具时
直接返回文本回答，例如：
```
我可以直接回答你的问题...
```

# 重要提示
- 仔细检查参数是否符合工具的 Schema 定义
- 必需参数不能省略
- 参数类型必须匹配（string, number, array, object）
- 如果工具执行失败，根据错误信息重试或提供替代方案
"""

        return system_prompt

    def format_tools_for_llm(self, tools_dict: Dict[str, List[Any]]) -> List[Dict[str, Any]]:
        """
        将 MCP 工具列表转换为 OpenAI function calling 格式。
        工具名使用 server__tool（双下划线），兼容 OpenAI 函数名规范。
        """
        formatted: List[Dict[str, Any]] = []
        for server_name, tools in tools_dict.items():
            for tool in tools:
                safe_name = f"{server_name}__{tool.name}"
                # inputSchema 是 dict（JSON Schema）
                params = tool.inputSchema if tool.inputSchema else {"type": "object", "properties": {}}
                formatted.append({
                    "type": "function",
                    "function": {
                        "name": safe_name,
                        "description": f"[{server_name}] {tool.description or ''}",
                        "parameters": params,
                    },
                    # 内部用，传给 API 前会过滤掉
                    "_server": server_name,
                    "_tool": tool.name,
                })
        return formatted

    def build_tool_name_map(self, tools: List[Dict[str, Any]]) -> Dict[str, Tuple[str, str]]:
        """
        构建 safe_name -> (server_name, tool_name) 的映射，
        供 _execute_tool 定位服务器和工具名使用。
        """
        return {t["function"]["name"]: (t["_server"], t["_tool"]) for t in (tools or [])}

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]] = None,
        server_configs: Dict[str, Dict[str, Any]] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> Any:
        """
        使用 KimiInterface 进行聊天

        Args:
            messages: 消息历史
            tools: 格式化的工具列表
            server_configs: MCP 服务器配置（用于构建系统提示词）
            max_tokens: 最大 token 数
            temperature: 温度参数

        Returns:
            LLM 响应，包含 content 和可能的 tool_calls
        """
        # 动态构建系统提示词
        system_prompt = self.build_system_prompt(tools, server_configs or {})

        # 处理对话历史，防止 full_prompt 无限变大
        # 只保留最近的 10 轮对话（用户消息 + 助手回复 + 工具结果）
        # 这是一个简单的截断策略，类似于 Claude Code 的处理方式
        recent_messages = messages[-30:]  # 保留最近的 30 条消息（约 10 轮对话）

        # 构建对话历史（从最近的消息开始）
        conversation = []
        for msg in recent_messages:
            if msg["role"] == "user":
                conversation.append(f"用户: {msg['content']}")
            elif msg["role"] == "assistant":
                conversation.append(f"助手: {msg.get('content', '')}")
            elif msg["role"] == "tool":
                # 对工具结果进行简化，只保留关键信息
                tool_content = msg.get('content', '')
                if len(tool_content) > 500:
                    tool_content = tool_content[:500] + "..."  # 截断过长的工具结果
                conversation.append(f"工具结果: {tool_content}")

        # 当前用户消息
        user_message = messages[-1]["content"] if messages and messages[-1]["role"] == "user" else ""

        # 构建完整的提示词（包含对话历史）
        if conversation:
            conversation_str = "\n".join(conversation)
            full_prompt = conversation_str
        else:
            full_prompt = user_message

        # 再次检查 full_prompt 的长度，如果仍然过长，则进一步截断
        max_prompt_length = 8000  # 设定一个最大长度
        if len(full_prompt) > max_prompt_length:
            # 保留最后一部分，确保包含最新的用户消息
            full_prompt = "..." + full_prompt[-max_prompt_length:]  # 截断并添加省略号

        # 确保 full_prompt 不为空
        if not full_prompt:
            full_prompt = "请基于工具调用结果生成最终答案"

        # 记录发送给大模型的请求信息
        logger.info(f"[LLM Request] 发送给 {self.model} 的请求")
        logger.info(f"[LLM Request] System Prompt 长度: {len(system_prompt)} 字符")
        #log print system_prompt
        
        #log print full_prompt
        logger.info(f"[LLM Request] Full Prompt: {full_prompt}")
        #logger.info(f"[LLM Request] System Prompt: {system_prompt}")
        logger.info(f"[LLM Request] User Message: {user_message[:200]}...")

        # 使用 asyncio.to_thread 运行同步的 generate 方法，避免阻塞事件循环
        import asyncio
        response = ""

        def generate_response():
            nonlocal response
            for chunk in self.llm_interface.generate(full_prompt, system_prompt):
                if "response" in chunk:
                    response += chunk["response"]
                elif "error" in chunk:
                    logger.error(f"LLM 错误: {chunk['error']}")
                    return {"error": chunk["error"]}
            return None

        try:
            error_result = await asyncio.to_thread(generate_response)
            if error_result:
                return error_result
        except asyncio.CancelledError:
            logger.info("LLM 调用被取消")
            return {"error": "LLM 调用被取消"}

        # 记录大模型的响应信息
        logger.info(f"[LLM Response] 收到来自 {self.model} 的响应")
        logger.info(f"[LLM Response] 响应内容: {response[:200]}...")

        # 解析响应：可能是文本或 JSON 工具调用
        tool_call = self._parse_tool_call(response)

        if tool_call:
            # 返回工具调用
            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": response,
                            "tool_calls": [tool_call]
                        }
                    }
                ]
            }
        else:
            # 返回纯文本
            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": response
                        }
                    }
                ]
            }

    def _parse_tool_call(self, response: Optional[str]) -> Optional[Dict[str, Any]]:
        """
        解析 LLM 响应中的工具调用

        Args:
            response: LLM 返回的文本

        Returns:
            工具调用字典（如果存在），否则 None
        """
        if not response:
            return None

        import re

        # 尝试匹配 JSON 代码块
        json_pattern = r'```json\s*\n(.*?)\n```'
        matches = re.findall(json_pattern, response, re.DOTALL)

        for match in matches:
            try:
                data = json.loads(match.strip())
                
                # 检查是否包含 toolcalls 数组
                if "toolcalls" in data and isinstance(data["toolcalls"], list):
                    for toolcall in data["toolcalls"]:
                        if "name" in toolcall and toolcall["name"] == "mcp_tool_call":
                            if "parameters" in toolcall:
                                parameters = toolcall["parameters"]
                                if "tool_name" in parameters and "args" in parameters:
                                    tool_name = parameters["tool_name"]
                                    arguments = parameters["args"]

                                    # 生成工具调用 ID
                                    tool_id = f"call_{hash(tool_name) & 0xffffffff:08x}"

                                    # 返回标准格式的工具调用
                                    return {
                                        "id": tool_id,
                                        "type": "function",
                                        "function": {
                                            "name": tool_name,
                                            "arguments": json.dumps(arguments, ensure_ascii=False)
                                        }
                                    }
                
                # 兼容旧格式
                elif "tool_name" in data and "parameters" in data:
                    tool_name = data["tool_name"]
                    parameters = data["parameters"]

                    # 生成工具调用 ID
                    tool_id = f"call_{hash(tool_name) & 0xffffffff:08x}"

                    # 返回标准格式的工具调用
                    return {
                        "id": tool_id,
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "arguments": json.dumps(parameters, ensure_ascii=False)
                        }
                    }
            except (json.JSONDecodeError, KeyError):
                continue

        return None

    def _system_prompt(self) -> str:
        return """你是一个 AI 助手，使用 MCP (Model Context Protocol) 服务器来完成任务。

# 可用工具
每个工具名称格式为 "server_name__tool_name"（双下划线）。

# 工具调用规则
1. 理解用户意图，判断是否需要调用工具
2. 选择合适的工具，提供必需的参数
3. 多个工具调用按逻辑顺序执行
4. 将工具结果整合成清晰的答案

# 提示
- 工具结果可能包含错误，需要妥善处理
- 不是所有问题都需要工具，有时直接回答即可"""

    async def initialize(self, connect_all: bool = True) -> None:
        """初始化：连接 MCP 服务器并发现工具"""
        logger.info("Initializing MCP Agent...")

        if connect_all:
            await self.server_manager.connect_all()

        # 获取服务器配置（用于系统提示词）
        self._server_configs = self.server_manager.get_server_configs()

        tools_dict = self.server_manager.get_all_tools()
        self._tools_cache = self.format_tools_for_llm(tools_dict)
        self._tool_name_map = self.build_tool_name_map(self._tools_cache)

        total = len(self._tools_cache)
        logger.info(f"Agent ready: {total} tool(s) available")

    async def run(self, user_message: str) -> str:
        """
        执行一轮对话（含多步工具调用循环）

        Args:
            user_message: 用户输入

        Returns:
            最终文本回答
        """
        self.messages.append({"role": "user", "content": user_message})

        max_iterations = 10
        for iteration in range(1, max_iterations + 1):
            logger.info(f"Iteration {iteration}")

            response = await self.chat(
                messages=self.messages,
                tools=self._tools_cache if self._tools_cache else None,
                server_configs=self._server_configs,
            )

            content, tool_calls = self._parse_llm_response(response)

            if not tool_calls:
                # 无工具调用 → 最终答案
                self.messages.append({"role": "assistant", "content": content})
                return content

            # --- 执行工具调用 ---
            assistant_msg: Dict[str, Any] = {
                "role": "assistant",
                "content": content or None,
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["safe_name"],
                            "arguments": json.dumps(tc["arguments"], ensure_ascii=False),
                        },
                    }
                    for tc in tool_calls
                ],
            }
            self.messages.append(assistant_msg)

            for tc in tool_calls:
                tool_result = await self._execute_tool(tc)
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": self._format_tool_result(tool_result),
                })

        return "对话超时：已达到最大迭代次数"

    def _parse_llm_response(self, response: Any) -> Tuple[str, List[Dict[str, Any]]]:
        """
        解析 LLM 响应，返回 (文本内容, 工具调用列表)

        tool_call 字典:
            id        : 工具调用 ID
            safe_name : LLM 可见的名称（server__tool）
            arguments : dict
        """
        content = ""
        tool_calls: List[Dict[str, Any]] = []

        # 检查 response 是否为 None 或格式不正确
        if not response or not isinstance(response, dict) or "choices" not in response:
            return content, tool_calls

        # 只处理 OpenAI 兼容接口（moonshot）的响应格式
        try:
            choice = response["choices"][0]
            message = choice["message"]
            content = message.get("content") or ""
            for tc in message.get("tool_calls") or []:
                try:
                    arguments = json.loads(tc["function"]["arguments"])
                except (json.JSONDecodeError, TypeError):
                    arguments = {}
                tool_calls.append({
                    "id": tc["id"],
                    "safe_name": tc["function"]["name"],
                    "arguments": arguments,
                })
        except (KeyError, IndexError):
            # 响应格式不正确，返回空内容和空工具调用列表
            pass

        return content, tool_calls

    async def _execute_tool(self, tool_call: Dict[str, Any]) -> Any:
        """通过 MCPServerManager 执行工具调用（使用官方 mcp 库）"""
        safe_name = tool_call["safe_name"]
        arguments = tool_call["arguments"]
        #打印要调用的mcp服务的信息
        logger.info(f"[Tool Call] 要调用的工具: {safe_name} (参数: {arguments})")
        mapping = self._tool_name_map.get(safe_name)
        if not mapping:
            # 降级：尝试从 safe_name 拆解
            parts = safe_name.split("__", 1)
            if len(parts) == 2:
                mapping = (parts[0], parts[1])
            else:
                raise ValueError(f"无法解析工具名称: {safe_name}")

        server_name, tool_name = mapping

        try:
            result = await self.server_manager.call_tool(server_name, tool_name, arguments)
            return result
        except Exception as e:
            logger.error(f"Tool {safe_name} failed: {e}")
            return [TextContent(type="text", text=f"工具调用失败: {e}")]

    @staticmethod
    def _format_tool_result(content: Any) -> str:
        """将工具返回内容序列化为字符串"""
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, TextContent):
                    parts.append(item.text)
                else:
                    try:
                        parts.append(json.dumps(item, ensure_ascii=False, default=str))
                    except Exception:
                        parts.append(str(item))
            return "\n".join(parts)
        try:
            return json.dumps(content, ensure_ascii=False, default=str)
        except Exception:
            return str(content)

    def show_tools(self) -> None:
        """打印所有可用工具"""
        if not self._tools_cache:
            print("没有可用的工具")
            return

        # 按服务器分组工具
        tools_by_server = {}
        for tool in self._tools_cache:
            server_name = tool.get("_server", "Unknown")
            if server_name not in tools_by_server:
                tools_by_server[server_name] = []
            tools_by_server[server_name].append(tool)

        print("\n" + "=" * 80)
        print("可用的 MCP 工具")
        print("=" * 80)
        
        # 按服务器显示工具
        for server_name, tools in tools_by_server.items():
            print(f"\n🔧 {server_name} (共 {len(tools)} 个工具)")
            print("-" * 60)
            for tool in tools:
                fn = tool["function"]
                print(f"\n📦 {fn['name']}")
                print(f"   {fn['description']}")
                params = fn.get("parameters", {}).get("properties", {})
                if params:
                    print(f"   参数: {', '.join(params.keys())}")
        print("=" * 80 + "\n")

    async def cleanup(self) -> None:
        """释放所有 MCP 连接"""
        await self.server_manager.close_all()


# ============================================================================
# Interactive CLI
# ============================================================================

async def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="MCP Agent - 通过自然语言使用 MCP 服务",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--provider",
        choices=["moonshot"],
        default="moonshot",
        help=(
            "LLM 提供商 (默认: moonshot)\n"
            "  moonshot  - Moonshot Kimi (MOONSHOT_API_KEY)"
        ),
    )
    parser.add_argument("--model", help="LLM 模型名称（不填则使用提供商默认值）")
    parser.add_argument("--api-key", help="LLM API 密钥（也可通过环境变量设置）")
    parser.add_argument("--base-url", help="自定义 API 端点 URL（可选）")
    parser.add_argument("--mcp-config", help="MCP 配置文件路径（默认: mcpagent-config.json）")
    parser.add_argument("--no-connect", action="store_true", help="启动时不自动连接 MCP 服务器")
    parser.add_argument("--show-tools", action="store_true", help="显示可用工具后退出")

    args = parser.parse_args()

    agent = MCPAgent(
        llm_provider=args.provider,
        llm_model=args.model,
        llm_api_key=args.api_key,
        llm_base_url=args.base_url,
        mcp_config_path=args.mcp_config,
    )

    try:
        await agent.initialize(connect_all=not args.no_connect)

        if args.show_tools:
            agent.show_tools()
            return

        provider_label = {
            "moonshot": f"Moonshot Kimi ({agent.model})",
        }.get(args.provider, args.provider)

        print("\n" + "=" * 80)
        print(f"🤖 MCP Agent 已启动  [ {provider_label} ]")
        print("=" * 80)
        print("  /tools  - 显示可用 MCP 工具")
        print("  /clear  - 清除对话历史")
        print("  /quit   - 退出")
        print("=" * 80 + "\n")

        while True:
            try:
                user_input = input("你: ").strip()
                if not user_input:
                    continue
                if user_input.lower() in ("/quit", "/exit", "quit", "exit"):
                    print("\n再见！👋")
                    break
                if user_input.lower() == "/tools":
                    agent.show_tools()
                    continue
                if user_input.lower() == "/clear":
                    agent.messages.clear()
                    print("✅ 对话历史已清除\n")
                    continue

                print("\nAgent: ", end="", flush=True)
                response = await agent.run(user_input)
                print(f"{response}\n")

            except KeyboardInterrupt:
                print("\n\n中断输入")
            except Exception as e:
                logger.error(f"Error: {e}", exc_info=True)
                print(f"❌ 错误: {e}\n")

    finally:
        await agent.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n程序已退出")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        print(f"❌ 致命错误: {e}")
