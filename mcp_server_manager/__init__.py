#!/usr/bin/env python3
"""
MCP Server Manager 包

这个包提供了一个用于管理 MCP 服务器连接的管理器类，
支持连接、断开、列出工具等操作。
"""

from .manager import MCPServerManager, MCPServerConfig, ConnectedServer

__all__ = ["MCPServerManager", "MCPServerConfig", "ConnectedServer"]
__version__ = "1.0.0"
