#!/usr/bin/env python3
"""
测试MCP功能
"""

import asyncio
from llmshell.mcp_server_manager.manager import MCPServerManager

async def test_mcp():
    # 创建服务器管理器
    server_manager = MCPServerManager()
    
    # 测试获取服务器配置
    print("=== Testing MCP Server Configs ===")
    server_configs = server_manager.get_server_configs()
    print(f"Found {len(server_configs)} servers:")
    for server_name, config in server_configs.items():
        print(f"  Server: {server_name}")
        print(f"    Command: {config.get('command', 'N/A')}")
        print(f"    Args: {' '.join(config.get('args', []))}")
    
    # 测试连接服务器
    print("\n=== Testing MCP Server Connection ===")
    for server_name in server_configs:
        try:
            print(f"Connecting to {server_name}...")
            await server_manager.connect_server(server_name)
            print(f"Connected to {server_name}")
        except Exception as e:
            print(f"Error connecting to {server_name}: {e}")
    
    # 测试获取工具
    print("\n=== Testing MCP Tools ===")
    all_tools = server_manager.get_all_tools()
    for server_name, tools in all_tools.items():
        print(f"\nServer: {server_name} ({len(tools)} tools)")
        for tool in tools:
            print(f"  Tool: {server_name}__{tool.name}")
            print(f"  Description: {tool.description or 'No description'}")
    
    # 关闭连接
    await server_manager.close_all()
    print("\nAll connections closed")

if __name__ == "__main__":
    asyncio.run(test_mcp())
