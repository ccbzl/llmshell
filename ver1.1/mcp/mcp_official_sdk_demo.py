#!/usr/bin/env python3
"""
官方 MCP Python SDK 使用示例
文件名: mcp_official_sdk_demo.py

基于官方 mcp 库 (pip install mcp)
文档: https://github.com/modelcontextprotocol/python-sdk
"""

import asyncio
import json
from contextlib import AsyncExitStack
from typing import Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import TextContent


class MCPOfficialClient:
    """使用官方 MCP SDK 的客户端"""
    
    def __init__(self):
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        
    async def connect_to_server(self, command: str, args: list[str] = None, env: dict = None):
        """
        连接到 MCP Server
        
        Args:
            command: 启动 server 的命令 (如 "npx", "python3")
            args: 命令参数 (如 ["-y", "@modelcontextprotocol/server-everything"])
            env: 环境变量字典
        """
        server_params = StdioServerParameters(
            command=command,
            args=args or [],
            env=env
        )
        
        # 建立 stdio 连接
        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        read, write = stdio_transport
        
        # 创建会话
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(read, write)
        )
        
        # 初始化（自动完成 initialize 握手和 notifications/initialized）
        await self.session.initialize()
        print(f"✅ 成功连接到 MCP Server: {command} {' '.join(args or [])}")
        
    async def list_tools(self) -> list:
        """列出 Server 提供的所有工具"""
        if not self.session:
            raise RuntimeError("未连接到 server")
            
        tools = await self.session.list_tools()
        print(f"\n📋 发现 {len(tools.tools)} 个工具:")
        for tool in tools.tools:
            print(f"  • {tool.name}: {tool.description}")
        return tools.tools
        
    async def call_tool(self, tool_name: str, arguments: dict) -> str:
        """
        调用指定工具
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数字典
            
        Returns:
            工具执行结果文本
        """
        if not self.session:
            raise RuntimeError("未连接到 server")
            
        print(f"\n🔧 调用工具: {tool_name}({json.dumps(arguments)})")
        
        result = await self.session.call_tool(tool_name, arguments)
        
        # 提取文本内容
        text_contents = [
            content.text for content in result.content 
            if isinstance(content, TextContent)
        ]
        
        output = "\n".join(text_contents)
        print(f"✅ 结果: {output[:200]}{'...' if len(output) > 200 else ''}")
        return output
        
    async def read_resource(self, uri: str) -> str:
        """读取资源（如果 server 支持 resources）"""
        if not self.session:
            raise RuntimeError("未连接到 server")
            
        result = await self.session.read_resource(uri)
        return result
        
    async def get_server_info(self) -> dict:
        """获取 Server 信息"""
        if not self.session:
            raise RuntimeError("未连接到 server")
            
        # 获取 server 能力信息
        info = {
            "tools": len((await self.session.list_tools()).tools),
        }
        
        # 尝试获取 prompts 和 resources（如果支持）
        try:
            prompts = await self.session.list_prompts()
            info["prompts"] = len(prompts.prompts)
        except:
            info["prompts"] = 0
            
        try:
            resources = await self.session.list_resources()
            info["resources"] = len(resources.resources)
        except:
            info["resources"] = 0
            
        return info
        
    async def close(self):
        """关闭连接"""
        await self.exit_stack.aclose()
        print("\n🔌 连接已关闭")


async def demo_calculator():
    """示例1: 连接自定义 Calculator Server"""
    print("=" * 60)
    print("示例 1: 使用自定义 Calculator Server")
    print("=" * 60)
    
    client = MCPOfficialClient()
    
    try:
        # 连接到 calculator server
        await client.connect_to_server(
            command="python3",
            args=["calculator_server.py"]
        )
        
        # 列出工具
        await client.list_tools()
        
        # 调用工具
        await client.call_tool("add", {"a": 100, "b": 200})
        await client.call_tool("multiply", {"a": 7, "b": 8})
        await client.call_tool("power", {"base": 2, "exponent": 10})
        
        # 获取 server 信息
        info = await client.get_server_info()
        print(f"\n📊 Server 信息: {info}")
        
    finally:
        await client.close()


async def demo_everything():
    """示例2: 连接官方 Everything Server"""
    print("\n" + "=" * 60)
    print("示例 2: 使用官方 Everything Server")
    print("=" * 60)
    
    client = MCPOfficialClient()
    
    try:
        # 连接到 everything server
        await client.connect_to_server(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-everything"]
        )
        
        # 列出工具
        tools = await client.list_tools()
        
        # 调用几个示例工具
        await client.call_tool("echo", {"message": "Hello from Official SDK!"})
        await client.call_tool("get-sum", {"a": 10, "b": 20})
        
        # 获取 server 信息
        info = await client.get_server_info()
        print(f"\n📊 Server 信息: {info}")
        
    finally:
        await client.close()


async def demo_simple_usage():
    """示例3: 最简化的使用方式"""
    print("\n" + "=" * 60)
    print("示例 3: 最简化的使用方式")
    print("=" * 60)
    
    server_params = StdioServerParameters(
        command="python3",
        args=["calculator_server.py"]
    )
    
    # 使用 async with 最简写法
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # 列出工具
            tools = await session.list_tools()
            print(f"发现 {len(tools.tools)} 个工具")
            
            # 调用 add 工具
            result = await session.call_tool("add", {"a": 50, "b": 25})
            text = result.content[0].text
            print(f"50 + 25 = {text}")
    
    print("✅ 最简示例完成")


async def main():
    """主函数：运行所有示例"""
    print("\n🚀 MCP 官方 Python SDK 使用示例")
    print("基于: pip install mcp\n")
    
    try:
        # 运行三个示例
        await demo_calculator()
        await demo_everything()
        await demo_simple_usage()
        
        print("\n" + "=" * 60)
        print("✅ 所有示例运行完成！")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
