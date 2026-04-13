#!/usr/bin/env python3
"""
测试MCP功能
"""

import asyncio
from llmshell.shell import LLMShell

async def test_mcp():
    # 创建LLMShell实例
    shell = LLMShell(model_provider="kimi", model="kimi-k2.5", api_key="sk-nA0TzOl3JSRBNw9b7WfBWcYvx6JzEdf7fdPJFdqXTlJDe9iG")
    
    # 测试MCP服务器列表
    print("=== Testing MCP Server List ===")
    from llmshell.mcp_server_manager.manager import MCPServerManager
    server_manager = MCPServerManager()
    await shell._mcp_server_list(server_manager)
    
    # 测试MCP工具列表
    print("\n=== Testing MCP Tool List ===")
    await shell._mcp_tool_list(server_manager)
    
if __name__ == "__main__":
    asyncio.run(test_mcp())
