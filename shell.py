#!/usr/bin/env python3
"""
Shell 模块 - 包含 LLMShell 主类实现
"""

import json
import re
import sys
import logging
from typing import Dict, Any, List, Optional, Union

# 导入工具和模型
from .tools import ToolRegistry, CommandTool, FileTool
from .models import BaseModelInterface, OllamaInterface, KimiInterface, MoonshotInterface

# 配置日志
logger = logging.getLogger('LLM Shell')


class LLMShell:
    """LLM Shell 主类"""
    
    def __init__(self, model_provider: str = "ollama", model: str = "qwen3:4b", api_key: str = None):
        """
        初始化 LLM Shell
        
        Args:
            model_provider: 模型提供商，可选值: "ollama", "kimi", "moonshot"
            model: 模型名称
            api_key: API 密钥（仅 Kimi/Moonshot 需要）
        """
        self.model_provider = model_provider
        self.model = model
        self.api_key = api_key
        self.model_interface = self._create_model_interface()
        self.tool_registry = ToolRegistry()
        self.history: List[Dict[str, str]] = []
        self._register_tools()
        self.system_prompt = self._load_system_prompt()
    
    def _create_model_interface(self) -> BaseModelInterface:
        """创建模型接口"""
        if self.model_provider == "kimi":
            # 优先使用传入的 API key，否则会在 KimiInterface 中从环境变量读取
            return KimiInterface(model=self.model, api_key=self.api_key)
        elif self.model_provider == "moonshot":
            # 优先使用传入的 API key，否则会在 MoonshotInterface 中从环境变量读取
            return MoonshotInterface(model=self.model, api_key=self.api_key)
        else:  # 默认使用 Ollama
            return OllamaInterface(model=self.model)
    
    def _register_tools(self):
        """注册工具"""
        self.tool_registry.register(CommandTool())
        self.tool_registry.register(FileTool())
    
    def _load_system_prompt(self) -> str:
        """加载系统提示"""
        tools_info = self.tool_registry.get_tools_info()
        
        # 构建简洁的工具信息
        tools_str = "\n".join([
            f"- {tool['name']}: {tool['description']}"
            for tool in tools_info
        ])
        
        system_prompt = """You are LLM Shell, a command-line assistant. Execute commands and tools for users.

Available Tools:
%s

Response Format:
- For tools: {"toolcalls": [{"name": "tool1", "parameters": {...}}, {"name": "tool2", "parameters": {...}}]}
- For direct answers: {"answer": "text"}

Instructions:
1. For complex tasks, use sequential tool calls in a single toolcalls array
2. After executing tools, analyze the results and determine if further actions are needed
3. If further actions are needed, generate additional tool calls
4. If the task is complete, provide a summary of what was done
5. Use exact tool names: execute_command, file_operation
6. Use exact parameters: command, action, path, content
7. Respond with valid JSON only
8. No text outside JSON
9. Absolutely prohibited commands: rmdir, format, mkfs, dd, shutdown, reboot
10. Commands requiring user authorization: mv, cp, chmod, chown, rm (all rm commands)
"""
        
        return system_prompt % tools_str
    
    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        """从文本中提取 JSON"""
        # 清理文本
        text = text.strip()
        
        # 尝试匹配 ```json ... ``` 格式
        json_match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
        if json_match:
            try:
                json_str = json_match.group(1).strip()
                result = json.loads(json_str)
                print(f"[JSON Extraction] Successfully extracted JSON from code block")
                return result
            except Exception as e:
                print(f"[JSON Extraction] Failed to parse JSON from code block: {e}")
        
        # 尝试匹配完整的 JSON 对象（从第一个 { 到最后一个 }）
        if text.startswith('{'):
            try:
                # 找到最后一个 } 的位置
                last_brace = text.rfind('}')
                if last_brace != -1:
                    json_str = text[:last_brace + 1]
                    result = json.loads(json_str)
                    print(f"[JSON Extraction] Successfully extracted JSON from raw text")
                    return result
            except Exception as e:
                print(f"[JSON Extraction] Failed to parse JSON from raw text: {e}")
        
        # 尝试匹配工具调用格式
        toolcalls_match = re.search(r'\{\s*"toolcalls"\s*:', text)
        if toolcalls_match:
            try:
                # 从工具调用开始到最后一个 } 的位置
                start_idx = text.find('{')
                last_brace = text.rfind('}')
                if start_idx != -1 and last_brace != -1:
                    json_str = text[start_idx:last_brace + 1]
                    result = json.loads(json_str)
                    if "toolcalls" in result:
                        print(f"[JSON Extraction] Successfully extracted toolcalls JSON")
                    return result
            except Exception as e:
                print(f"[JSON Extraction] Failed to parse toolcalls JSON: {e}")
        
        print(f"[JSON Extraction] No valid JSON found in response")
        print(f"[Response Content] {text[:200]}...")
        return None
    
    def _process_tool_call(self, data: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
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
    
    def run(self):
        """运行 shell"""
        # 检查模型连接
        logger.info(f"Checking {self.model_provider} connection...")
        print(f"Checking {self.model_provider} connection...")
        if not self.model_interface.check_model():
            error_msg = f"Model '{self.model}' not found or {self.model_provider} is not running."
            logger.error(error_msg)
            print(f"Error: {error_msg}")
            if self.model_provider == "ollama":
                print("Please make sure:")
                print("1. Ollama is installed and running")
                print(f"2. Model '{self.model}' is pulled: ollama pull {self.model}")
            else:
                print("Please make sure:")
                print("1. API endpoint is reachable")
                print("2. API key is valid")
                print(f"3. Model '{self.model}' is available")
            return
        
        logger.info(f"Starting LLM Shell with {self.model_provider}: {self.model}")
        print("=" * 50)
        print("Welcome to LLM Shell!")
        print(f"Model Provider: {self.model_provider}")
        print(f"Model: {self.model}")
        print("Type your request in natural language, or 'exit' to quit.")
        print("Type 'tools' to see available tools.")
        print("=" * 50)
        
        while True:
            try:
                # 使用 sys.stdin 读取输入
                print("\n> ", end="", flush=True)
                user_input = sys.stdin.readline().strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() == "exit":
                    logger.info("User requested exit")
                    print("Goodbye!")
                    break
                
                if user_input.lower() == "tools":
                    logger.info("User requested tool list")
                    print(self.tool_registry.list_tools())
                    continue
                
                if user_input.lower() == "clear":
                    logger.info("User requested history clear")
                    self.history.clear()
                    print("History cleared")
                    continue
                
                # 添加到历史
                self.history.append({"role": "user", "content": user_input})
                logger.info(f"[User Input] {user_input}")
                
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
                max_rounds = 5  # 最大轮数，防止无限循环
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
                    
                    # 提取并处理 JSON
                    json_data = self._extract_json(response)
                    logger.debug(f"[Extracted JSON] {json.dumps(json_data, ensure_ascii=False) if json_data else 'None'}")
                    
                    if json_data:
                        if "toolcalls" in json_data:
                            # 处理工具调用（一个或多个）
                            tool_count = len(json_data["toolcalls"])
                            logger.info(f"[Tool Calls] {tool_count} tool(s)")
                            
                            results = self._process_tool_call(json_data)
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
                
                if current_round >= max_rounds:
                    print("\n[Maximum rounds reached. Task may not be complete.]")
                
            except KeyboardInterrupt:
                logger.info("User interrupted")
                print("\nInterrupted. Type 'exit' to quit.")
            except Exception as e:
                error_msg = str(e)
                logger.error(f"[Runtime Error] {error_msg}")
                print(f"\n[Error] {error_msg}")
