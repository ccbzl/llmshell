#!/usr/bin/env python3
"""
测试多个工具调用功能
"""

import os
import sys
import json
import re
from llmshell import LLMShell

# 设置 Moonshot API key
os.environ['MOONSHOT_API_KEY'] = 'sk-nA0TzOl3JSRBNw9b7WfBWcYvx6JzEdf7fdPJFdqXTlJDe9iG'

def test_multi_tool_calls():
    """测试多个工具调用"""
    print("=" * 60)
    print("测试多个工具调用功能")
    print("=" * 60)
    
    # 创建 LLM Shell 实例
    shell = LLMShell(
        model_provider="moonshot",
        model="moonshot-v1-8k",
        api_key=os.environ['MOONSHOT_API_KEY']
    )
    
    # 测试任务：列出当前目录，然后读取 README.md 文件
    test_prompt = "请执行以下任务：1. 列出当前目录下的文件和文件夹，2. 读取 README.md 文件的内容（如果存在）"
    
    print(f"\n测试提示：{test_prompt}")
    print("\n[Model Call Information]")
    print(f"[User Input] {test_prompt}")
    print("[System Prompt] Included")
    print("[Thinking...]")
    
    # 构建历史文本
    history_text = f"user: {test_prompt}\n"
    
    # 生成响应
    full_response = []
    for chunk in shell.model_interface.generate(history_text, shell.system_prompt, stream=True):
        if "error" in chunk:
            print(f"\n[Error] {chunk['error']}")
            return
        if "response" in chunk:
            full_response.append(chunk["response"])
    
    response = "".join(full_response)
    print(f"\n[Model Response]\n{response}")
    print("[Model Response End]")
    
    # 提取 JSON
    def extract_json(text):
        """从文本中提取 JSON"""
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
    
    json_data = extract_json(response)
    
    if json_data:
        if "toolcalls" in json_data:
            # 处理工具调用（一个或多个）
            tool_count = len(json_data["toolcalls"])
            print(f"\n[Tool Calls] {tool_count} tool(s) detected")
            
            # 打印工具调用详情
            for i, tool_call in enumerate(json_data["toolcalls"]):
                tool_name = tool_call.get("name")
                parameters = tool_call.get("parameters", {})
                print(f"\n[Tool Call {i+1}/{tool_count}]")
                print(f"[Tool Name] {tool_name}")
                print(f"[Tool Parameters] {json.dumps(parameters, ensure_ascii=False, indent=2)}")
                
                # 检查工具名称是否正确
                tool = shell.tool_registry.get_tool(tool_name)
                if tool:
                    print(f"[Tool Validation] ✓ Tool '{tool_name}' is registered")
                else:
                    print(f"[Tool Validation] ✗ Tool '{tool_name}' is NOT registered")
        else:
            print("\n[No tool calls detected]")
    else:
        print("\n[No valid JSON found]")

if __name__ == "__main__":
    test_multi_tool_calls()
