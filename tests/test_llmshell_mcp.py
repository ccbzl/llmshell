#!/usr/bin/env python3
"""
测试LLMShell的MCP功能
"""

from llmshell.shell import LLMShell

# 创建LLMShell实例
shell = LLMShell(model_provider="ollama", model="qwen3:4b")

print("=== 测试LLMShell的MCP功能 ===")

# 测试MCP服务器配置
print("\n1. 测试MCP服务器配置:")
print(f"MCP服务器数量: {len(shell.mcp_servers)}")
for server in shell.mcp_servers:
    print(f"  - {server['name']}")

# 测试MCP工具信息
print("\n2. 测试MCP工具信息:")
print(f"MCP工具数量: {len(shell.mcp_tools)}")
for tool in shell.mcp_tools:
    print(f"  - {tool['name']}: {tool['description']}")

# 测试工具名称映射
print("\n3. 测试工具名称映射:")
print(f"工具名称映射数量: {len(shell._tool_name_map)}")
for tool_name, mapping in shell._tool_name_map.items():
    print(f"  - {tool_name} → {mapping}")

print("\n=== 测试完成 ===")
