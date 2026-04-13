#!/usr/bin/env python3
"""
MCP Server配置管理模块

负责MCP Server的配置管理和信息存储
"""

import os
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger('LLM Shell')


class MCPServerInstaller:
    """MCP Server配置管理器"""
    
    def __init__(self):
        """
        初始化配置管理器
        """
        # 使用当前目录作为配置目录
        self.config_file = os.path.join(os.getcwd(), "servers.json")
        
    def save_server_config(self, server_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        保存MCP Server配置
        
        Args:
            server_name: 服务器名称
            config: 服务器配置
            
        Returns:
            保存结果
        """
        try:
            # 读取现有配置
            servers = self._load_servers_config()
            
            # 更新或添加服务器配置
            servers[server_name] = config
            
            # 保存配置
            with open(self.config_file, 'w') as f:
                json.dump(servers, f, indent=2)
            
            logger.info(f"Saved MCP Server config for {server_name}")
            return {
                "success": True,
                "message": f"MCP Server config saved successfully for {server_name}"
            }
            
        except Exception as e:
            logger.error(f"Error saving MCP Server config: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_server_config(self, server_name: str) -> Dict[str, Any]:
        """
        获取MCP Server配置
        
        Args:
            server_name: 服务器名称
            
        Returns:
            服务器配置
        """
        try:
            servers = self._load_servers_config()
            
            if server_name in servers:
                return {
                    "success": True,
                    "config": servers[server_name]
                }
            else:
                return {
                    "success": False,
                    "error": f"MCP Server {server_name} not found"
                }
                
        except Exception as e:
            logger.error(f"Error getting MCP Server config: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def list_servers(self) -> Dict[str, Any]:
        """
        列出已配置的MCP Server
        
        Returns:
            服务器列表
        """
        try:
            servers = self._load_servers_config()
            
            server_list = [
                {
                    "name": name,
                    "config": config
                }
                for name, config in servers.items()
            ]
            
            return {
                "success": True,
                "servers": server_list
            }
            
        except Exception as e:
            logger.error(f"Error listing MCP Servers: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def delete_server_config(self, server_name: str) -> Dict[str, Any]:
        """
        删除MCP Server配置
        
        Args:
            server_name: 服务器名称
            
        Returns:
            删除结果
        """
        try:
            servers = self._load_servers_config()
            
            if server_name in servers:
                del servers[server_name]
                
                # 保存配置
                with open(self.config_file, 'w') as f:
                    json.dump(servers, f, indent=2)
                
                logger.info(f"Deleted MCP Server config for {server_name}")
                return {
                    "success": True,
                    "message": f"MCP Server config deleted successfully for {server_name}"
                }
            else:
                return {
                    "success": False,
                    "error": f"MCP Server {server_name} not found"
                }
                
        except Exception as e:
            logger.error(f"Error deleting MCP Server config: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _load_servers_config(self) -> Dict[str, Any]:
        """
        加载服务器配置
        
        Returns:
            服务器配置字典
        """
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                # 处理mcpServers格式
                if 'mcpServers' in data:
                    return data['mcpServers']
                else:
                    return data
            else:
                return {}
        except Exception as e:
            logger.error(f"Error loading servers config: {e}")
            return {}
