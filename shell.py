#!/usr/bin/env python3
"""
Shell 模块 - 包含 LLMShell 主类实现
"""

import json
import re
import sys
import logging
from typing import Dict, Any, List, Optional, Union

# 处理Windows系统上的readline模块
if sys.platform == 'win32':
    try:
        import pyreadline3 as readline
    except ImportError:
        try:
            import pyreadline as readline
        except ImportError:
            # 如果都没有安装，创建一个空的readline模块
            class DummyReadline:
                def parse_and_bind(self, *args):
                    pass
            readline = DummyReadline()
else:
    try:
        import readline
    except ImportError:
        # 在其他系统上如果没有readline，也创建一个空的
        class DummyReadline:
            def parse_and_bind(self, *args):
                pass
        readline = DummyReadline()

# 导入工具和模型
from tools import ToolRegistry, CommandTool, FileTool
from models import BaseModelInterface, OllamaInterface, MoonshotInterface
from model_manager import ModelManager

# 配置日志
logger = logging.getLogger('LLM Shell')


class LLMShell:
    """LLM Shell 主类"""
    
    def __init__(self, model_id: Optional[str] = None, api_key: Optional[str] = None):
        """
        初始化 LLM Shell
        
        Args:
            model_id: 模型 ID，None 表示使用默认模型
            api_key: API 密钥（仅需要 API 密钥的模型需要）
        """
        self.model_id = model_id
        self.api_key = api_key
        
        # 初始化模型管理器
        self.model_manager = ModelManager()
        
        self.model_interface = self._create_model_interface()
        self.tool_registry = ToolRegistry()
        self.history: List[Dict[str, str]] = []
        
        # 初始化MCP服务器管理器
        self.server_manager = None
        self.mcp_servers = []
        self.mcp_tools = []
        self._tool_name_map = {}
        
        try:
            from mcp_server_manager.manager import MCPServerManager
            self.server_manager = MCPServerManager()
            # 加载MCP server配置
            self.mcp_servers = self._load_mcp_servers()
            # 初始化MCP服务器连接将在main函数中异步执行
        except ImportError as e:
            print(f"警告: MCP 模块未安装，MCP 功能将被禁用。错误: {e}")
            print("请运行 'pip install mcp' 来安装 MCP 模块。")
        
        # 注册工具（在MCP服务器初始化后）
        self._register_tools()
        
        # 系统提示将在MCP服务器初始化后加载
    
    async def _initialize_mcp_async(self):
        """
        初始化MCP服务器连接（异步版本）
        """
        if self.server_manager is None:
            return
        # 连接所有MCP服务器
        await self.server_manager.connect_all()
        # 提取工具信息并构建工具名称映射
        tools_dict = self.server_manager.get_all_tools()
        self.mcp_tools = self._format_mcp_tools(tools_dict)
        self._build_tool_name_map()
    
    async def _initialize_mcp(self):
        """
        初始化MCP服务器连接
        """
        # 直接调用异步方法
        await self._initialize_mcp_async()
        # 加载系统提示词（在MCP服务器初始化后）
        self.system_prompt = self._load_system_prompt()
    
    def _load_mcp_servers(self):
        """
        加载MCP server配置
        
        Returns:
            已配置的MCP server列表
        """
        if self.server_manager is None:
            return []
        try:
            server_configs = self.server_manager.get_server_configs()
            servers = []
            for server_name, config in server_configs.items():
                servers.append({
                    'name': server_name,
                    'config': config
                })
            return servers
        except Exception as e:
            logger.error(f"Error loading MCP servers: {e}")
            return []
    
    def _format_mcp_tools(self, tools_dict):
        """
        格式化MCP工具信息
        """
        formatted_tools = []
        for server_name, tools in tools_dict.items():
            for tool in tools:
                formatted_tool = {
                    "name": f"{server_name}__{tool.name}",
                    "description": f"[MCP:{server_name}] {tool.description or ''}",
                    "parameters": tool.inputSchema if tool.inputSchema else {}
                }
                formatted_tools.append(formatted_tool)
        return formatted_tools
    
    def _build_tool_name_map(self):
        """
        构建工具名称映射
        """
        for tool in self.mcp_tools:
            tool_name = tool["name"]
            if "__" in tool_name:
                server_name, tool_name = tool_name.split("__", 1)
                self._tool_name_map[tool["name"]] = (server_name, tool_name)
    
    def _extract_mcp_tools(self):
        """
        提取MCP server工具信息
        
        Returns:
            MCP server工具信息列表
        """
        # 直接返回已缓存的MCP工具信息
        return self.mcp_tools
    
    def _create_model_interface(self) -> BaseModelInterface:
        """创建模型接口"""
        try:
            return self.model_manager.get_model_interface(
                model_id=self.model_id,
                api_key=self.api_key
            )
        except Exception as e:
            print(f"Error creating model interface: {e}")
            raise
    
    def _register_tools(self):
        """注册工具"""
        self.tool_registry.register(CommandTool())
        self.tool_registry.register(FileTool())
        # 注册MCP相关工具（如果MCP模块可用）
        if self.server_manager:
            from tools import MCPToolCallTool
            mcp_tool = MCPToolCallTool()
            mcp_tool.set_server_manager(self.server_manager)
            self.tool_registry.register(mcp_tool)
    
    def _load_system_prompt(self) -> str:
        """加载系统提示"""
        # 读取sys_prompt.cfg文件
        try:
            with open('sys_prompt.cfg', 'r', encoding='utf-8') as f:
                system_prompt = f.read()
        except FileNotFoundError:
            # 如果文件不存在，报错退出
            error_msg = "错误: 找不到系统提示词文件 'sys_prompt.cfg'。系统提示词文件是必需的。"
            print(error_msg)
            sys.exit(1)
        
        # 构建工具信息
        tools_info = self.tool_registry.get_tools_info()
        tools_str = "\n".join([
            f"- {tool['name']}: {tool['description']}"
            for tool in tools_info
        ])
        
        # 构建MCP服务器信息
        mcp_tools_info = ""
        if self.server_manager:
            tool_info_string = self.server_manager.get_tool_info_string()
            if tool_info_string and tool_info_string != "No MCP tools available":
                mcp_tools_info = "\n\nMCP Server Tools:\n"
                mcp_tools_info += tool_info_string
            else:
                mcp_tools_info = "\n\nNo MCP tools available"
        else:
            mcp_tools_info = "\n\nMCP functionality disabled (MCP module not installed)"
        
        # 替换占位符
        system_prompt = system_prompt.replace('{tools_info}', tools_str)
        system_prompt = system_prompt.replace('{mcp_tools_info}', mcp_tools_info)
        
        # 调试：打印系统提示词的长度和前500个字符
        # print(f"[Debug] System prompt length: {len(system_prompt)}")
        #print(f"[Debug] System prompt preview: {system_prompt}")
        
        return system_prompt
    
    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        """从文本中提取 JSON"""
        # 清理文本
        text = text.strip()
        
        # 尝试匹配 ```json ... ``` 格式
        json_match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
        if json_match:
            try:
                json_str = json_match.group(1).strip()
                result = json.loads(json_str, strict=False)  # 允许非标准JSON
                print(f"[JSON Extraction] Successfully extracted JSON from code block")
                return result
            except Exception as e:
                print(f"[JSON Extraction] Failed to parse JSON from code block: {e}")
        
        # 尝试匹配完整的 JSON 对象（处理嵌套大括号）
        if '{' in text:
            try:
                # 找到第一个 { 和匹配的 }
                start_idx = text.find('{')
                brace_count = 1
                end_idx = start_idx + 1
                while brace_count > 0 and end_idx < len(text):
                    if text[end_idx] == '{':
                        brace_count += 1
                    elif text[end_idx] == '}':
                        brace_count -= 1
                    end_idx += 1
                if brace_count == 0:
                    json_str = text[start_idx:end_idx]
                    result = json.loads(json_str, strict=False)
                    print(f"[JSON Extraction] Successfully extracted JSON from raw text")
                    return result
            except Exception as e:
                print(f"[JSON Extraction] Failed to parse JSON from raw text: {e}")
        
        # 尝试匹配工具调用格式
        toolcalls_match = re.search(r'"toolcalls"\s*:', text)
        if toolcalls_match:
            try:
                # 找到第一个 { 和匹配的 }
                start_idx = text.find('{')
                if start_idx != -1:
                    brace_count = 1
                    end_idx = start_idx + 1
                    while brace_count > 0 and end_idx < len(text):
                        if text[end_idx] == '{':
                            brace_count += 1
                        elif text[end_idx] == '}':
                            brace_count -= 1
                        end_idx += 1
                    if brace_count == 0:
                        json_str = text[start_idx:end_idx]
                        result = json.loads(json_str, strict=False)
                        if "toolcalls" in result:
                            print(f"[JSON Extraction] Successfully extracted toolcalls JSON")
                        return result
            except Exception as e:
                print(f"[JSON Extraction] Failed to parse toolcalls JSON: {e}")
        
        # 尝试匹配 JSON 数组
        if text.startswith('['):
            try:
                # 找到第一个 [ 和匹配的 ]
                start_idx = 0
                bracket_count = 1
                end_idx = 1
                while bracket_count > 0 and end_idx < len(text):
                    if text[end_idx] == '[':
                        bracket_count += 1
                    elif text[end_idx] == ']':
                        bracket_count -= 1
                    end_idx += 1
                if bracket_count == 0:
                    json_str = text[:end_idx]
                    result = json.loads(json_str, strict=False)
                    print(f"[JSON Extraction] Successfully extracted JSON array")
                    return result
            except Exception as e:
                print(f"[JSON Extraction] Failed to parse JSON array: {e}")
        
        print(f"[JSON Extraction] No valid JSON found in response")
        print(f"[Response Content] {text[:200]}...")
        return None
    
    async def _process_tool_call(self, data: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """处理工具调用"""
        results = []
        
        # 处理工具调用（支持一个或多个）
        if "toolcalls" in data:
            tool_calls = data["toolcalls"]
            #print(f"\n[Tool Calls] Processing {len(tool_calls)} tool(s)...")
            
            for i, tool_call in enumerate(tool_calls):
                tool_name = tool_call.get("name")
                parameters = tool_call.get("parameters", {})
                
                #print(f"\n[Tool Call {i+1}/{len(tool_calls)}]")
                #print(f"[Tool Name] {tool_name}")
                #print(f"[Tool Parameters] {json.dumps(parameters, ensure_ascii=False, indent=2)}")
                logger.info(f"[Tool Call {i+1}] {tool_name} with parameters: {json.dumps(parameters, ensure_ascii=False)}")
                
                tool = self.tool_registry.get_tool(tool_name)
                if not tool:
                    error_msg = f"Tool '{tool_name}' not found"
                    print(f"[Tool Error] {error_msg}")
                    logger.error(f"[Tool Error] {error_msg}")
                    result = {
                        "success": False,
                        "error": error_msg
                    }
                else:
                    print("[Tool Execution] Running...")
                    # 检查工具的run方法是否是异步的
                    import asyncio
                    if asyncio.iscoroutinefunction(tool.run):
                        # 使用await调用异步方法
                        result = await tool.run(**parameters)
                    else:
                        # 直接调用同步方法
                        result = tool.run(**parameters)
                    
                    # 显示工具结果
                    print("[Tool Result]")
                    if result.get("success"):
                        print("[Status] ✓ Success")
                        if "stdout" in result and result["stdout"]:
                            print("[Output]")
                            output = result['stdout']
                            if len(output) > 150:
                                print(output[:150] + "...")
                            else:
                                print(output)
                        if "content" in result and result["content"]:
                            print("[Content]")
                            content = result['content']
                            if len(content) > 150:
                                print(content[:150] + "...")
                            else:
                                print(content)
                        if "message" in result and result["message"]:
                            print(f"[Message] {result['message']}")
                    else:
                        error_msg = result.get('error', 'Unknown error')
                        print(f"[Status] ✗ Failed")
                        print(f"[Error] {error_msg}")
                
                logger.info(f"[Tool Result {i+1}] {json.dumps(result, ensure_ascii=False)}")
                results.append(result)
        
        return results if results else None
    
    def _get_final_response(self, tool_results: Union[Dict[str, Any], List[Dict[str, Any]]]) -> str:
        """获取最终响应"""
        # 构建包含工具结果的对话历史
        history_text = ""
        for msg in self.history[-5:]:  # 只使用最近的5条消息
            role = msg.get("role", "user")
            content = msg.get("content", "")
            history_text += f"{role}: {content}\n"
        
        # 添加工具结果
        if isinstance(tool_results, list):
            for i, result in enumerate(tool_results):
                history_text += f"\ntool_result_{i+1}: {json.dumps(result, ensure_ascii=False)}\n"
        else:
            history_text += f"\ntool_result: {json.dumps(tool_results, ensure_ascii=False)}\n"
        
        history_text += "\nBased on the tool results above, provide a clear and concise explanation to the user."
        
        # 调用模型获取最终回答
        full_response = []
        for chunk in self.model_interface.generate(history_text, self.system_prompt, stream=True):
            if "error" in chunk:
                return f"Error: {chunk['error']}"
            if "response" in chunk:
                full_response.append(chunk["response"])
        
        return "".join(full_response)
    
    async def run(self):
        """运行 shell"""
        # 检查模型连接
        # 从模型配置中获取提供商信息
        model_id = self.model_id or self.model_manager.models_config.get("default_model")
        model_config = self.model_manager.models_config.get(model_id) or {}
        model_provider = model_config.get("provider", "Unknown")
        model_name = model_config.get("model", "Unknown")
        
        logger.info(f"Checking {model_provider} connection...")
        print(f"Checking {model_provider} connection...")
        if not self.model_interface.check_model():
            error_msg = f"Model '{model_name}' not found or {model_provider} is not running."
            logger.error(error_msg)
            print(f"Error: {error_msg}")
            if model_provider == "ollama":
                print("Please make sure:")
                print("1. Ollama is installed and running")
                print(f"2. Model '{model_name}' is pulled: ollama pull {model_name}")
            else:
                print("Please make sure:")
                print("1. API endpoint is reachable")
                print("2. API key is valid")
                print(f"3. Model '{model_name}' is available")
            return
        
        logger.info(f"Starting LLM Shell with {model_provider}: {model_name}")
        print("=" * 50)
        print("Welcome to LLM Shell!")
        print(f"Model Provider: {model_provider}")
        print(f"Model: {model_name}")
        print("Type your request in natural language, or use system commands:")
        print("  /exit - Exit the shell")
        print("  /tools - List available tools")
        print("  /clear - Clear history")
        print("  /mcp - Manage MCP servers")
        print("  /model - Manage models")
        print("  /history - Show prompt history")
        print("=" * 50)
        
        try:
            while True:
                try:
                    # 使用 input() 函数读取输入，更好地支持中文输入和删除操作
                    user_input = input("\n>")
                    
                    if not user_input:
                        continue
                    
                    # 处理以 / 开头的系统命令
                    if user_input.startswith('/'):
                        command = user_input[1:].lower()
                        
                        if command == "exit":
                            logger.info("User requested exit")
                            print("Goodbye!")
                            break
                        
                        if command == "tools":
                            logger.info("User requested tool list")
                            print(self.tool_registry.list_tools())
                            continue
                        
                        if command == "clear":
                            logger.info("User requested history clear")
                            self.history.clear()
                            print("History cleared")
                            continue
                        
                        if command == "history":
                            logger.info("User requested history")
                            self._show_history()
                            continue
                        
                        if command.startswith("mcp"):
                            # 直接处理mcp命令
                            parts = user_input.split()
                            if len(parts) >= 3:
                                subcommand = parts[1]
                                if subcommand == "server" and parts[2] == "list":
                                    # 列出所有MCP服务器
                                    await self._mcp_server_list()
                                elif subcommand == "tool" and parts[2] == "list":
                                    # 列出MCP工具
                                    server_name = parts[3] if len(parts) >= 4 else None
                                    await self._mcp_tool_list(server_name)
                                else:
                                    print("Invalid MCP command. Try: /mcp server list or /mcp tool list [server]")
                            else:
                                print("Invalid MCP command. Try: /mcp server list or /mcp tool list [server]")
                            continue
                        
                        # 其他系统命令
                        # 处理 /model 命令
                        elif user_input.startswith("/model"):
                            parts = user_input.split()
                            if len(parts) < 2:
                                print("\n[Model Command Usage]")
                                print("/model list - List all configured models")
                                print("/model <id> - Switch to the specified model (id can be number or model name)")
                                # 跳过后续处理
                                continue
                            
                            subcommand = parts[1]
                            if subcommand == "list":
                                # 列出所有配置的模型
                                print("\n[Model List]")
                                print("=" * 60)
                                print(f"{'No.':<5} {'Model ID':<20} {'Provider':<15} {'Model Name':<20}")
                                print("=" * 60)
                                
                                # 获取所有模型配置
                                models = []
                                for model_id, model_config in self.model_manager.models_config.items():
                                    if model_id != "default_model":  # 排除 default_model 配置
                                        models.append((model_id, model_config))
                                
                                # 按编号列出模型
                                for i, (model_id, model_config) in enumerate(models, 1):
                                    provider = model_config.get("provider", "Unknown")
                                    model_name = model_config.get("model", "Unknown")
                                    print(f"{i:<5} {model_id:<20} {provider:<15} {model_name:<20}")
                                
                                print("=" * 60)
                                print("Use /model <id> to switch model (id can be number or model name)")
                                # 跳过后续处理
                                continue
                            else:
                                # 切换到指定的模型
                                model_identifier = subcommand
                                
                                # 获取所有模型配置
                                models = []
                                for model_id, model_config in self.model_manager.models_config.items():
                                    if model_id != "default_model":  # 排除 default_model 配置
                                        models.append((model_id, model_config))
                                
                                # 尝试将 identifier 解析为数字
                                try:
                                    index = int(model_identifier) - 1
                                    if 0 <= index < len(models):
                                        model_id = models[index][0]
                                    else:
                                        print(f"\n[Model Error] Invalid model number: {model_identifier}")
                                        # 跳过后续处理
                                        continue
                                except ValueError:
                                    # 不是数字，尝试作为模型 ID 或模型名称
                                    model_id = None
                                    for mid, model_config in models:
                                        if mid == model_identifier or model_config.get("model") == model_identifier:
                                            model_id = mid
                                            break
                                    if not model_id:
                                        print(f"\n[Model Error] Model not found: {model_identifier}")
                                        # 跳过后续处理
                                        continue
                                
                                # 切换模型
                                try:
                                    # 创建新的模型接口
                                    new_model_interface = self.model_manager.get_model_interface(model_id=model_id, api_key=self.api_key)
                                    
                                    # 检查模型是否可用
                                    if not new_model_interface.check_model():
                                        print(f"\n[Model Error] Model {model_id} is not available")
                                        # 跳过后续处理
                                        continue
                                    
                                    # 更新模型接口和模型 ID
                                    self.model_interface = new_model_interface
                                    self.model_id = model_id
                                    
                                    # 获取模型配置信息
                                    model_config = self.model_manager.models_config.get(model_id)
                                    provider = model_config.get("provider", "Unknown")
                                    model_name = model_config.get("model", "Unknown")
                                    
                                    print(f"\n[Model Switched]")
                                    print(f"Successfully switched to model: {model_id}")
                                    print(f"Provider: {provider}")
                                    print(f"Model Name: {model_name}")
                                    # 跳过后续处理
                                    continue
                                except Exception as e:
                                    print(f"\n[Model Error] Failed to switch model: {e}")
                                    # 跳过后续处理
                                    continue
                        else:
                            print(f"\n[Command Error] Unknown command: {user_input}")
                            # 跳过后续处理
                            continue
                    
                    # 添加到历史
                    self.history.append({"role": "user", "content": user_input})
                    logger.info(f"[User Input] {user_input}")
                    
                    # 记录大模型输入到llm_trace.log
                    import datetime
                    timestamp = datetime.datetime.now().isoformat()
                    # 从模型配置中获取模型信息
                    model_config = self.model_manager.models_config.get(self.model_id) or {}
                    model_name = model_config.get("model", "Unknown")
                    with open("llm_trace.log", "a", encoding="utf-8") as f:
                        f.write(f"[{timestamp}] MODEL: {model_name}\n")
                        f.write(f"[{timestamp}] SYSTEM: {self.system_prompt[:500]}...\n")
                        f.write(f"[{timestamp}] USER: {user_input}\n")
                    
                    # 构建初始 prompt
                    history_text = ""
                    for msg in self.history[-10:]:  # 只使用最近的10条消息
                        role = msg.get("role", "user")
                        content = msg.get("content", "")
                        history_text += f"{role}: {content}\n"
                    
                    # 显示简化的大模型调用信息
                    print("\n[Model Call Information]")
                    print(f"[User Input] {user_input}")
                    print("[System Prompt] Included (see logs for full content)")
                    print(f"[Prompt History Length] {len(history_text)} characters")
                    print("[Thinking...]")
                    
                    # 多轮工具调用循环
                    max_rounds = self.model_manager.get_max_rounds()  # 从配置文件获取最大轮数，防止无限循环
                    current_round = 0
                    
                    while current_round < max_rounds:
                        current_round += 1
                        logger.info(f"Generating response (round {current_round})...")
                        logger.info(f"[User Input Length] {len(user_input)} characters")
                        logger.info(f"[Prompt History Length] {len(history_text)} characters")
                        
                        full_response = []
                        for chunk in self.model_interface.generate(history_text, self.system_prompt, stream=True):
                            if "error" in chunk:
                                error_msg = chunk["error"]
                                logger.error(f"[Model Error] {error_msg}")
                                print(f"\n[Error] {error_msg}")
                                break
                            if "response" in chunk:
                                full_response.append(chunk["response"])
                        
                        response = "".join(full_response)
                        self.history.append({"role": "assistant", "content": response})
                        logger.info(f"[Full Model Response] {response}")
                        
                        # 记录大模型输出到llm_trace.log
                        import datetime
                        timestamp = datetime.datetime.now().isoformat()
                        with open("llm_trace.log", "a", encoding="utf-8") as f:
                            f.write(f"[{timestamp}] OUTPUT: {response}\n")
                        
                        # 提取并处理 JSON
                        json_data = self._extract_json(response)
                        logger.debug(f"[Extracted JSON] {json.dumps(json_data, ensure_ascii=False) if json_data else 'None'}")
                        
                        if json_data:
                            if "toolcalls" in json_data:
                                # 处理工具调用（一个或多个）
                                tool_count = len(json_data["toolcalls"])
                                logger.info(f"[Tool Calls] {tool_count} tool(s)")
                                
                                results = await self._process_tool_call(json_data)
                                if results:
                                    # 将工具结果添加到历史记录
                                    for i, result in enumerate(results):
                                        self.history.append({
                                            "role": "tool",
                                            "content": json.dumps(result, ensure_ascii=False)
                                        })
                                        logger.debug(f"[Tool Result {i+1}] {json.dumps(result, ensure_ascii=False)[:200]}...")
                                    
                                    # 构建新的历史文本，包含工具执行结果
                                    history_text = ""
                                    for msg in self.history[-10:]:  # 只使用最近的10条消息
                                        role = msg.get("role", "user")
                                        content = msg.get("content", "")
                                        history_text += f"{role}: {content}\n"
                                    
                                    # 继续循环，让模型判断是否需要进一步操作
                                    print("\n[Evaluating next steps...]")
                                    continue
                            elif "answer" in json_data:
                                # 直接回答，任务完成
                                answer = json_data["answer"]
                                logger.info(f"[Direct Answer] {answer[:100]}...")
                                print(f"\n[Answer]\n{answer}")
                                break
                            else:
                                # 没有提取到 JSON，直接显示响应
                                logger.info("No tool call detected in response")
                                print(f"\n[No tool call detected]")
                                break
                        else:
                            # 没有提取到 JSON，直接显示响应
                            logger.info("No tool call detected in response")
                            print(f"\n[No tool call detected]")
                            break
                    
                    if current_round >= max_rounds:
                        print("\n[Maximum rounds reached. Task may not be complete.]")
                
                except KeyboardInterrupt:
                    logger.info("User interrupted")
                    print("\nInterrupted. Type 'exit' to quit.")
                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"[Runtime Error] {error_msg}")
                    print(f"\n[Error] {error_msg}")
        finally:
            # 清理资源
            if self.server_manager:
                logger.info("Closing MCP server connections...")
                try:
                    # 捕获KeyboardInterrupt，确保在用户中断时能够优雅退出
                    await self.server_manager.close_all()
                    logger.info("MCP server connections closed")
                except KeyboardInterrupt:
                    logger.info("MCP connection close interrupted by user")
                except Exception as e:
                    logger.error(f"Error closing MCP server connections: {e}")
    

    
    async def _mcp_server_list(self):
        """列出所有MCP服务器"""
        if self.server_manager:
            self.server_manager.display_server_info()
        else:
            print("MCP functionality disabled (MCP module not installed)")
    
    async def _mcp_tool_list(self, server_name=None):
        """列出MCP工具"""
        if self.server_manager:
            self.server_manager.display_tool_info(server_name)
        else:
            print("MCP functionality disabled (MCP module not installed)")
    
    def _show_history(self):
        """显示历史记录"""
        if not self.history:
            print("No history available")
            return
        
        print("=" * 60)
        print("Prompt History")
        print("=" * 60)
        
        for i, msg in enumerate(self.history, 1):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            
            print(f"[{i}] {role.capitalize()}:")
            if len(content) > 100:
                print(f"  {content[:100]}...")
            else:
                print(f"  {content}")
            print()
        
        print("=" * 60)
