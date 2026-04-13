#!/usr/bin/env python3
"""
测试MCP功能重构
"""

from llmshell.shell import LLMShell

def test_mcp():
    print("=== 测试MCP功能重构 ===")
    
    # 测试列出MCP服务器
    print("\n1. 测试列出MCP服务器:")
    # 直接使用服务器管理器，避免事件循环冲突
    from llmshell.mcp_server_manager.manager import MCPServerManager
    server_manager = MCPServerManager()
    server_configs = server_manager.get_server_configs()
    
    if not server_configs:
        print("No MCP servers configured")
    else:
        for server_name, config in server_configs.items():
            print(f"\nServer: {server_name}")
            print(f"  Type: {config.get('type', 'stdio')}")
            print(f"  Command: {config.get('command', 'N/A')}")
            print(f"  Args: {' '.join(config.get('args', []))}")
            if config.get('env'):
                env_str = ", ".join([f"{k}={v}" for k, v in config['env'].items()])
                print(f"  Env: {env_str}")
            if config.get('url'):
                print(f"  URL: {config.get('url')}")
    
    # 测试MCP工具调用
    print("\n2. 测试MCP工具调用:")
    # 假设calculator服务器有一个add工具
    from llmshell.tools import MCPToolCallTool
    mcp_tool = MCPToolCallTool()
    
    try:
        # 调用calculator服务器的add工具
        result = mcp_tool.run(
            tool_name="calculator__add",
            args={"a": 1, "b": 2}
        )
        print(f"Tool call result: {result}")
    except Exception as e:
        print(f"Error: {e}")
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    # 直接运行测试函数，避免事件循环冲突
    test_mcp()
