#!/usr/bin/env python3
"""
MCP Server Manager

用于管理 MCP 服务器连接的管理器类，支持连接、断开、列出工具等操作。
"""

import json
import os
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@dataclass
class MCPServerConfig:
    """MCP 服务器配置"""
    name: str
    type: str = "stdio"           # stdio | sse | http | streamable_http
    command: Optional[str] = None
    args: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None
    url: Optional[str] = None
    headers: Optional[Dict[str, str]] = None


@dataclass
class ConnectedServer:
    """已连接的服务器信息"""
    config: MCPServerConfig
    session: ClientSession
    tools: List[Any] = field(default_factory=list)


class MCPServerManager:
    """
    MCP 服务器管理器

    使用官方 mcp 库建立连接，所有连接生命周期由内部 AsyncExitStack 管理。
    调用 initialize() 后连接保持活跃；调用 close_all() 时统一释放。
    """

    def __init__(self, config_path: str = None):
        """
        Args:
            config_path: MCP 配置文件路径，默认 agent.json
        """
        if config_path is None:
            config_path = "agent.json"

        self.config_path = config_path
        self.server_configs: Dict[str, MCPServerConfig] = {}
        self.connected: Dict[str, ConnectedServer] = {}
        self._exit_stack = AsyncExitStack()

        self._load_config()

    def _load_config(self) -> None:
        """加载 MCP 配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            mcp_servers = config.get("mcpServers", {})

            for name, sc in mcp_servers.items():
                try:
                    self.server_configs[name] = MCPServerConfig(
                        name=name,
                        type=sc.get("type", "stdio"),
                        command=sc.get("command"),
                        args=sc.get("args"),
                        env=sc.get("env"),
                        url=sc.get("url"),
                        headers=sc.get("headers"),
                    )
                except Exception as e:
                    print(f"Failed to load server {name}: {e}")
            print(f"Loaded {len(self.server_configs)} MCP servers from {self.config_path}")
        except FileNotFoundError:
            print(f"MCP config not found: {self.config_path}")
        except Exception as e:
            print(f"Failed to load MCP config: {e}")

    async def connect_server(self, name: str) -> ConnectedServer:
        """连接到指定的 MCP 服务器（使用官方 mcp 库）"""
        if name in self.connected:
            return self.connected[name]

        if name not in self.server_configs:
            raise ValueError(f"Unknown server: {name}")

        cfg = self.server_configs[name]
        print(f"Connecting to MCP server: {name} (type={cfg.type})")

        # 根据传输类型选择官方客户端
        if cfg.type == "stdio":
            # 合并环境变量
            env = {**os.environ, **(cfg.env or {})} if cfg.env else None
            server_params = StdioServerParameters(
                command=cfg.command,
                args=cfg.args or [],
                env=env,
            )
            read, write = await self._exit_stack.enter_async_context(
                stdio_client(server_params)
            )

        elif cfg.type in ("sse",):
            from mcp.client.sse import sse_client
            read, write = await self._exit_stack.enter_async_context(
                sse_client(url=cfg.url, headers=cfg.headers or {})
            )

        elif cfg.type in ("http", "streamable_http"):
            from mcp.client.streamable_http import streamable_http_client
            read, write, _ = await self._exit_stack.enter_async_context(
                streamable_http_client(url=cfg.url, headers=cfg.headers or {})
            )

        else:
            raise ValueError(f"Unsupported transport type: {cfg.type}")

        # 创建 ClientSession 并初始化
        session = await self._exit_stack.enter_async_context(
            ClientSession(read, write)
        )
        await session.initialize()

        # 获取工具列表
        tools_result = await session.list_tools()
        tools = tools_result.tools
        print(f"Connected to {name}: {len(tools)} tool(s) available")

        conn = ConnectedServer(config=cfg, session=session, tools=tools)
        self.connected[name] = conn
        return conn

    async def connect_all(self) -> None:
        """连接所有配置的 MCP 服务器"""
        for name in self.server_configs:
            try:
                await self.connect_server(name)
            except Exception as e:
                print(f"Failed to connect to {name}: {e}")

    def get_all_tools(self) -> Dict[str, List[Any]]:
        """返回 {server_name: [Tool, ...]} 字典"""
        return {name: conn.tools for name, conn in self.connected.items()}

    def _get_servers_data(self) -> Dict[str, Dict[str, Any]]:
        """
        获取服务器数据
        
        Returns:
            服务器数据字典 {server_name: {type, command, args, env, url, headers}}
        """
        servers_data = {}
        for name, cfg in self.server_configs.items():
            servers_data[name] = {
                "type": cfg.type,
                "command": cfg.command,
                "args": cfg.args or [],
                "env": cfg.env or {},
                "url": cfg.url,
                "headers": cfg.headers,
            }
        return servers_data

    def get_server_configs(self) -> Dict[str, Dict[str, Any]]:
        """
        返回所有服务器配置（用于系统提示词）

        Returns:
            {server_name: {command, args, env, ...}}
        """
        return self._get_servers_data()

    def get_session(self, server_name: str) -> Optional[ClientSession]:
        """获取指定服务器的 ClientSession"""
        conn = self.connected.get(server_name)
        return conn.session if conn else None

    async def call_tool(self, server_name: str, tool_name: str, arguments: dict) -> Any:
        """
        调用指定服务器上的工具

        Args:
            server_name: 服务器名称
            tool_name: 工具名称
            arguments: 工具参数

        Returns:
            工具执行结果
        """
        # 检查服务器是否已连接，如果没有连接则自动连接
        session = self.get_session(server_name)
        if not session:
            try:
                # 自动连接服务器
                await self.connect_server(server_name)
                session = self.get_session(server_name)
                if not session:
                    raise ValueError(f"Failed to connect to server: {server_name}")
            except Exception as e:
                raise ValueError(f"Error connecting to server {server_name}: {e}")

        result = await session.call_tool(tool_name, arguments)
        return result

    async def close_all(self) -> None:
        """关闭所有 MCP 连接"""
        import asyncio
        try:
            # 添加超时处理，避免关闭操作卡死
            await asyncio.wait_for(self._exit_stack.aclose(), timeout=10.0)
        except asyncio.TimeoutError:
            print("Warning: MCP connection close timeout, force exiting")
        except Exception as e:
            print(f"Error closing MCP connections: {e}")
    
    def get_server_info_string(self) -> str:
        """
        获取MCP服务器信息字符串，用于系统提示词注入
        
        Returns:
            MCP服务器信息字符串
        """
        servers_data = self._get_servers_data()
        if not servers_data:
            return "No MCP servers configured"
        
        info = []
        for server_name, config in servers_data.items():
            info.append(f"- {server_name}: {config.get('type', 'stdio')} server")
        
        return "\n".join(info)
    
    def _get_tools_data(self, server_name=None) -> Dict[str, List[Dict[str, Any]]]:
        """
        获取工具数据
        
        Args:
            server_name: 服务器名称，None表示获取所有服务器的工具
            
        Returns:
            工具数据字典 {server_name: [tool_info, ...]}
        """
        all_tools = self.get_all_tools()
        
        if not all_tools:
            return {}
        
        # 过滤服务器
        if server_name:
            if server_name not in all_tools:
                return {}
            tools_to_process = {server_name: all_tools[server_name]}
        else:
            tools_to_process = all_tools
        
        # 处理工具数据
        tools_data = {}
        for srv_name, tools in tools_to_process.items():
            tools_info = []
            for tool in tools:
                tool_name = f"{srv_name}__{tool.name}"
                description = tool.description or f"{srv_name} server tool: {tool.name}"
                
                # 提取参数信息
                parameters = []
                if tool.inputSchema:
                    properties = tool.inputSchema.get('properties', {})
                    required = tool.inputSchema.get('required', [])
                    for param_name, param_schema in properties.items():
                        param_info = {
                            'name': param_name,
                            'required': param_name in required,
                            'type': param_schema.get('type', 'string'),
                            'description': param_schema.get('description', '')
                        }
                        parameters.append(param_info)
                
                tools_info.append({
                    'tool_name': tool_name,
                    'description': description,
                    'parameters': parameters,
                    'server_name': srv_name
                })
            tools_data[srv_name] = tools_info
        
        return tools_data
    
    def get_tool_info_string(self) -> str:
        """
        获取MCP工具信息字符串，用于系统提示词注入
        
        Returns:
            MCP工具信息字符串
        """
        tools_data = self._get_tools_data()
        if not tools_data:
            return "No MCP tools available"
        
        info = []
        for server_name, tools in tools_data.items():
            info.append(f"\n### {server_name}")
            info.append("")
            for tool_info in tools:
                tool_name = tool_info['tool_name']
                description = tool_info['description']
                parameters = tool_info['parameters']
                
                # 添加工具名称
                info.append(f"**{tool_name}**")
                
                # 添加描述信息，确保多行描述正确缩进
                description_lines = description.split('\n')
                for i, line in enumerate(description_lines):
                    if i == 0:
                        info.append(f"- description: [{tool_info['server_name']}] {line}")
                    else:
                        info.append(f"  {line}")
                
                # 添加参数信息
                if parameters:
                    info.append("- parameters:")
                    for param in parameters:
                        required_mark = " (required)" if param['required'] else ""
                        param_desc = param['description'] if param['description'] else ""
                        info.append(f"  - `{param['name']}`{required_mark} [{param['type']}]: {param_desc}")
                
                info.append("")
        
        return "\n".join(info)
    
    def display_server_info(self) -> None:
        """
        显示MCP服务器信息
        """
        servers_data = self._get_servers_data()
        
        print("\n" + "-" * 60)
        print("MCP Servers List")
        print("-" * 60)
        
        if not servers_data:
            print("No MCP servers configured")
            print("-" * 60)
            return
        
        for server_name, config in servers_data.items():
            print(f"\nServer: {server_name}")
            print(f"  Type: {config.get('type', 'stdio')}")
            print(f"  Command: {config.get('command', 'N/A')}")
            print(f"  Args: {' '.join(config.get('args', []))}")
            if config.get('env'):
                env_str = ", ".join([f"{k}={v}" for k, v in config['env'].items()])
                print(f"  Env: {env_str}")
            if config.get('url'):
                print(f"  URL: {config.get('url')}")
        
        print("-" * 60)
    
    def display_tool_info(self, server_name=None) -> None:
        """
        显示MCP工具信息
        
        Args:
            server_name: 服务器名称，None表示显示所有服务器的工具
        """
        tools_data = self._get_tools_data(server_name)
        
        print("\n" + "-" * 60)
        print("MCP Tools List")
        print("-" * 60)
        
        if not tools_data:
            if server_name:
                print(f"Server {server_name} not found or not connected")
            else:
                print("No MCP tools available")
            print("-" * 60)
            return
        
        # 显示工具信息
        for srv_name, tools in tools_data.items():
            print(f"\nServer: {srv_name} ({len(tools)} tools)")
            print("  " + "-" * 50)
            for tool_info in tools:
                print(f"  Tool: {tool_info['tool_name']}")
                print(f"  Description: {tool_info['description']}")
                if tool_info['parameters']:
                    print("  Parameters:")
                    for param in tool_info['parameters']:
                        required_mark = " (required)" if param['required'] else ""
                        print(f"    {param['name']}{required_mark} [{param['type']}]")
                print()
        
        print("-" * 60)
