#!/usr/bin/env python3
"""
MCP Server Manager

封装所有异步逻辑，提供同步接口。
外部调用者无需了解 asyncio。
"""

from __future__ import annotations

import json
import os
import asyncio
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from threading import Lock
from typing import Any

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    ClientSession = Any  # type: ignore
    StdioServerParameters = Any  # type: ignore
    stdio_client = Any  # type: ignore


@dataclass
class MCPServerConfig:
    """MCP 服务器配置"""
    name: str
    type: str = "stdio"  # stdio | sse | http | streamable_http
    command: str | None = None
    args: list[str] | None = None
    env: dict[str, str] | None = None
    url: str | None = None
    headers: dict[str, str] | None = None


@dataclass
class ConnectedServer:
    """已连接的服务器信息"""
    config: Any
    session: Any
    tools: list[Any] = field(default_factory=list)
    connected: bool = False


class MCPServerManager:
    """
    MCP 服务器管理器

    设计原则：
    1. 封装所有异步逻辑 - 外部调用者无需了解 asyncio
    2. 懒加载连接 - 首次使用时才建立连接
    3. 长连接复用 - 连接建立后保持活跃，支持多轮调用
    """

    _instance: MCPServerManager | None = None
    _lock: Lock = Lock()

    def __new__(cls, *args: Any, **kwargs: Any) -> MCPServerManager:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, config_path: str | None = None) -> None:
        if getattr(self, '_initialized', False):
            return

        if not MCP_AVAILABLE:
            print("警告: MCP 模块未安装，MCP 功能将被禁用。")

        if config_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(base_dir, "mcpconfig.json")

        self.config_path: str = config_path
        self.server_configs: dict[str, MCPServerConfig] = {}
        self.connected: dict[str, ConnectedServer] = {}
        self._exit_stacks: dict[str, AsyncExitStack] = {}
        self._connecting: set[str] = set()
        self._initialized: bool = True

        self._load_config()

    def _load_config(self) -> None:
        """加载 MCP 配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            mcp_servers = config.get("mcpServers", {})

            for name, sc in mcp_servers.items():
                self.server_configs[name] = MCPServerConfig(
                    name=name,
                    type=sc.get("type", "stdio"),
                    command=sc.get("command"),
                    args=sc.get("args"),
                    env=sc.get("env"),
                    url=sc.get("url"),
                    headers=sc.get("headers"),
                )
            print(f"Loaded {len(self.server_configs)} MCP servers from {self.config_path}")
        except FileNotFoundError:
            print(f"MCP config not found: {self.config_path}")
        except Exception as e:
            print(f"Failed to load MCP config: {e}")

    # ==================== 公共同步接口 ====================

    def call_tool(self, server_name: str, tool_name: str, arguments: dict[str, Any]) -> Any:
        """调用 MCP 服务器工具（同步接口）"""
        if not MCP_AVAILABLE:
            raise RuntimeError("MCP 模块未安装")
        try:
            return asyncio.run(self._call_tool_async(server_name, tool_name, arguments))
        except Exception as e:
            raise RuntimeError(f"调用工具失败: {e}")

    def list_tools(self, server_name: str | None = None) -> dict[str, list[Any]]:
        """获取工具列表（同步接口）"""
        if not MCP_AVAILABLE:
            return {}
        try:
            return asyncio.run(self._list_tools_async(server_name))
        except Exception as e:
            print(f"获取工具列表失败: {e}")
            return {}

    def get_server_configs(self) -> dict[str, Any]:
        """获取所有服务器配置"""
        return self.server_configs

    def display_tool_info(self, server_name: str | None = None) -> None:
        """显示工具信息"""
        tools = self.list_tools(server_name)
        if not tools:
            print("No tools available")
            return
        for name, tool_list in tools.items():
            print(f"\n{name}:")
            if tool_list:
                for tool in tool_list:
                    tool_name = getattr(tool, 'name', 'unknown')
                    tool_desc = getattr(tool, 'description', 'No description')[:50]
                    print(f"  - {tool_name}: {tool_desc}...")

    def connect(self, server_name: str | None = None) -> bool:
        """连接到 MCP 服务器（同步接口）"""
        if not MCP_AVAILABLE:
            return False
        try:
            if server_name:
                try:
                    asyncio.run(self._connect_server_async(server_name))
                    return True
                except Exception as e:
                    print(f"连接到 {server_name} 失败: {e}")
                    return False
            else:
                success = True
                for name in self.server_configs:
                    try:
                        asyncio.run(self._connect_server_async(name))
                    except Exception as e:
                        print(f"连接到 {name} 失败: {e}")
                        success = False
                return success
        except Exception as e:
            print(f"连接错误: {e}")
            return False

    def disconnect(self, server_name: str | None = None) -> None:
        """断开 MCP 服务器连接"""
        def close_server(name: str) -> None:
            if name in self.connected:
                self.connected[name].connected = False
                self.connected[name].session = None  # type: ignore
                self.connected[name].tools = []

            # 移除退出栈，但不尝试关闭它，因为这可能会导致任务上下文错误
            # 退出栈会在程序结束时自动清理
            if name in self._exit_stacks:
                self._exit_stacks.pop(name, None)

        if server_name:
            close_server(server_name)
        else:
            for name in list(self.server_configs.keys()):
                close_server(name)

    def is_connected(self, server_name: str) -> bool:
        """检查服务器是否已连接"""
        conn = self.connected.get(server_name)
        return conn is not None and conn.connected

    def get_all_tools(self) -> dict[str, list[Any]]:
        """返回所有已连接服务器的 {server_name: [Tool, ...]}"""
        return {name: conn.tools for name, conn in self.connected.items() if conn.connected}

    def get_tool_info_string(self) -> str:
        """获取 MCP 工具信息字符串"""
        tools_data = self._get_tools_data()
        if not tools_data:
            return "No MCP tools available"

        info_lines: list[str] = []
        for server_name, tools in tools_data.items():
            info_lines.append(f"\n### {server_name}")
            for tool_info in tools:
                info_lines.append(f"**{tool_info['tool_name']}**")
                info_lines.append(f"- description: [{tool_info['server_name']}] {tool_info['description']}")
                if tool_info['parameters']:
                    info_lines.append("- parameters:")
                    for param in tool_info['parameters']:
                        req = " (required)" if param['required'] else ""
                        info_lines.append(f"  - `{param['name']}`{req} [{param['type']}]: {param['description']}")
        return "\n".join(info_lines)

    def display_server_info(self) -> None:
        """显示 MCP 服务器信息"""
        print("\n" + "-" * 50)
        print("MCP Servers")
        print("-" * 50)

        if not self.server_configs:
            print("No MCP servers configured")
        else:
            for name in self.server_configs:
                status = "✓ Connected" if self.is_connected(name) else "✗ Disconnected"
                print(f"  {name}: {status}")

        print("-" * 50)

    def close(self) -> None:
        """关闭所有连接并清理资源"""
        self.disconnect()
        MCPServerManager._instance = None
        self._initialized = False

    # ==================== 内部异步方法 ====================

    async def _connect_server_async(self, name: str) -> ConnectedServer:
        """连接到指定的 MCP 服务器"""
        if name not in self.server_configs:
            raise ValueError(f"Unknown server: {name}")

        if name in self._connecting:
            for _ in range(100):
                await asyncio.sleep(0.1)
                if name not in self._connecting:
                    break

        conn = self.connected.get(name)
        if conn and conn.connected:
            return conn

        cfg = self.server_configs[name]
        print(f"Connecting to MCP server: {name} (type={cfg.type})")

        self._connecting.add(name)
        exit_stack = AsyncExitStack()

        try:
            if cfg.type == "stdio":
                env = {**os.environ, **(cfg.env or {})} if cfg.env else None
                server_params = StdioServerParameters(  # type: ignore[attr-defined]
                    command=cfg.command,
                    args=cfg.args or [],
                    env=env,
                )
                read, write = await exit_stack.enter_async_context(
                    stdio_client(server_params)  # type: ignore[attr-defined]
                )

            elif cfg.type in ("sse",):
                from mcp.client.sse import sse_client  # type: ignore[attr-defined,import]
                read, write = await exit_stack.enter_async_context(
                    sse_client(url=cfg.url, headers=cfg.headers or {})
                )

            elif cfg.type in ("http", "streamable_http"):
                from mcp.client.streamable_http import streamable_http_client  # type: ignore[attr-defined,import]
                read, write, _ = await exit_stack.enter_async_context(
                    streamable_http_client(url=cfg.url, headers=cfg.headers or {})
                )
            else:
                raise ValueError(f"Unsupported transport type: {cfg.type}")

            session = await exit_stack.enter_async_context(ClientSession(read, write))  # type: ignore[attr-defined]
            await session.initialize()

            tools_result = await session.list_tools()
            tools = tools_result.tools
            print(f"Connected to {name}: {len(tools)} tool(s)")

            self._exit_stacks[name] = exit_stack
            self.connected[name] = ConnectedServer(
                config=cfg,
                session=session,
                tools=tools,
                connected=True
            )

            return self.connected[name]

        except Exception as e:
            print(f"Failed to connect to {name}: {e}")
            try:
                await exit_stack.aclose()
            except Exception:
                pass
            raise
        finally:
            self._connecting.discard(name)

    async def _call_tool_async(self, server_name: str, tool_name: str, arguments: dict[str, Any]) -> Any:
        """调用工具（自动按需连接）"""
        conn = self.connected.get(server_name)

        if not conn or not conn.connected:
            conn = await self._connect_server_async(server_name)

        if not conn or not conn.session:
            raise ValueError(f"Server not connected: {server_name}")

        try:
            result = await conn.session.call_tool(tool_name, arguments)
            return result
        except Exception as e:
            if "not connected" in str(e).lower() or "session" in str(e).lower():
                conn = await self._connect_server_async(server_name)
                result = await conn.session.call_tool(tool_name, arguments)
                return result
            raise

    async def _list_tools_async(self, server_name: str | None = None) -> dict[str, list[Any]]:
        """获取工具列表"""
        if server_name:
            if not self.is_connected(server_name):
                await self._connect_server_async(server_name)
        else:
            for name in self.server_configs:
                if not self.is_connected(name):
                    try:
                        await self._connect_server_async(name)
                    except Exception:
                        pass

        return self.get_all_tools()

    def _get_tools_data(self, server_name: str | None = None) -> dict[str, list[dict[str, Any]]]:
        """获取工具数据"""
        all_tools = self.get_all_tools()
        if not all_tools:
            return {}

        if server_name:
            if server_name not in all_tools:
                return {}
            tools_to_process = {server_name: all_tools[server_name]}
        else:
            tools_to_process = all_tools

        tools_data: dict[str, list[dict[str, Any]]] = {}
        for srv_name, tools in tools_to_process.items():
            tools_info: list[dict[str, Any]] = []
            for tool in tools:
                tool_name = f"{srv_name}__{tool.name}"
                description = tool.description or f"{srv_name} tool: {tool.name}"

                parameters: list[dict[str, Any]] = []
                if tool.inputSchema:
                    properties = tool.inputSchema.get('properties', {})
                    required = tool.inputSchema.get('required', [])
                    for param_name, param_schema in properties.items():
                        parameters.append({
                            'name': param_name,
                            'required': param_name in required,
                            'type': param_schema.get('type', 'string'),
                            'description': param_schema.get('description', '')
                        })

                tools_info.append({
                    'tool_name': tool_name,
                    'description': description,
                    'parameters': parameters,
                    'server_name': srv_name
                })
            tools_data[srv_name] = tools_info

        return tools_data


def create_manager(config_path: str | None = None) -> MCPServerManager:
    """创建 MCP 服务器管理器实例"""
    MCPServerManager._instance = None
    return MCPServerManager(config_path)
