#!/usr/bin/env python3
"""
检查系统提示长度
"""

import json
import os

# 模拟工具信息
tools_info = [
    {
        'name': 'command',
        'description': 'Execute a shell command',
        'parameters': {
            'command': 'The shell command to execute',
            'target_terminal': 'The terminal to use (new or existing terminal ID)'
        }
    },
    {
        'name': 'file',
        'description': 'File operations',
        'parameters': {
            'action': 'Action to perform (read, write, append)',
            'file_path': 'Path to the file',
            'content': 'Content to write (required for write/append)',
            'encoding': 'File encoding (default: utf-8)'
        }
    }
]

tools_json = json.dumps(tools_info, indent=2, ensure_ascii=False)

# 构建系统提示
system_prompt = """You are LLM Shell, a command-line assistant. Your job is to help users by executing commands and tools.

## Available Tools
%s

## Response Format
Use toolcalls for any task requiring tools:
{"toolcalls": [{"name": "tool_name", "parameters": {"param1": "value1"}}]}

Use answer for direct responses:
{"answer": "Your response"}

## Instructions
1. Analyze user requests carefully
2. For multi-step tasks, break into sequential tool calls
3. Always use toolcalls format for tool execution
4. Respond with valid JSON only
5. No text outside JSON
6. Only safe commands: ls, pwd, cat, echo, date, whoami, uname, df, du, ps, top, which
7. Never: rm, rmdir, mv, cp, chmod, chown, format, mkfs, dd, shutdown, reboot
"""

# 使用字符串替换
system_prompt = system_prompt % tools_json

print(f"System prompt length: {len(system_prompt)} characters")
print(f"System prompt length: {len(system_prompt) / 1024:.2f} KB")

# 打印系统提示内容
print("\nSystem prompt:")
print(system_prompt)
