#!/usr/bin/env python3
"""
MCP Server管理模块

负责MCP Server的生命周期管理和状态监控
"""

import os
import subprocess
import json
import time
import logging
import threading
from typing import Dict, Any, Optional

logger = logging.getLogger('LLM Shell')


class MCPServerManager:
    """MCP Server管理器"""
    
    def __init__(self):
        """
        初始化服务器管理器
        """
        self.server_process = None
        self.server_thread = None
        self.running = False
        self.status_lock = threading.Lock()
        self.server_config = None
    
    def start_server(self, command: str, args: list = None, env: dict = None) -> Dict[str, Any]:
        """
        启动MCP Server
        
        Args:
            command: 启动server的命令 (如 "npx", "python3")
            args: 命令参数
            env: 环境变量字典
            
        Returns:
            启动结果
        """
        with self.status_lock:
            if self.running:
                return {
                    "success": False,
                    "error": "MCP Server is already running"
                }
        
        try:
            # 保存服务器配置
            self.server_config = {
                "command": command,
                "args": args or [],
                "env": env
            }
            
            logger.info(f"Starting MCP Server: {command} {' '.join(args or [])}")
            
            # 启动服务器进程
            self.server_process = subprocess.Popen(
                [command] + (args or []),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env
            )
            
            # 启动监控线程
            self.server_thread = threading.Thread(target=self._monitor_server)
            self.server_thread.daemon = True
            self.server_thread.start()
            
            # 等待服务器启动
            time.sleep(2)
            
            # 检查进程是否还在运行
            if self.server_process and self.server_process.poll() is None:
                with self.status_lock:
                    self.running = True
                return {
                    "success": True,
                    "message": f"MCP Server started successfully: {command} {' '.join(args or [])}"
                }
            else:
                # 清理进程
                if self.server_process:
                    self.server_process.terminate()
                    self.server_process = None
                with self.status_lock:
                    self.running = False
                return {
                    "success": False,
                    "error": "Failed to start MCP Server"
                }
                
        except Exception as e:
            logger.error(f"Error starting MCP Server: {e}")
            # 清理进程
            if self.server_process:
                self.server_process.terminate()
                self.server_process = None
            with self.status_lock:
                self.running = False
            return {
                "success": False,
                "error": str(e)
            }
    
    def stop_server(self) -> Dict[str, Any]:
        """
        停止MCP Server
        
        Returns:
            停止结果
        """
        with self.status_lock:
            if not self.running:
                return {
                    "success": False,
                    "error": "MCP Server is not running"
                }
        
        try:
            logger.info("Stopping MCP Server")
            
            # 停止服务器进程
            if self.server_process:
                self.server_process.terminate()
                self.server_process.wait(timeout=10)
                self.server_process = None
            
            # 等待服务器停止
            time.sleep(2)
            
            with self.status_lock:
                self.running = False
            
            return {
                "success": True,
                "message": "MCP Server stopped successfully"
            }
            
        except Exception as e:
            logger.error(f"Error stopping MCP Server: {e}")
            with self.status_lock:
                self.running = False
            return {
                "success": False,
                "error": str(e)
            }
    
    def restart_server(self, command: str, args: list = None, env: dict = None) -> Dict[str, Any]:
        """
        重启MCP Server
        
        Args:
            command: 启动server的命令 (如 "npx", "python3")
            args: 命令参数
            env: 环境变量字典
            
        Returns:
            重启结果
        """
        try:
            # 先停止服务器
            stop_result = self.stop_server()
            if not stop_result.get("success"):
                return stop_result
            
            # 再启动服务器
            start_result = self.start_server(command, args, env)
            return start_result
            
        except Exception as e:
            logger.error(f"Error restarting MCP Server: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_status(self) -> Dict[str, Any]:
        """
        获取MCP Server状态
        
        Returns:
            服务器状态
        """
        try:
            with self.status_lock:
                is_running = self.running
            
            if is_running:
                return {
                    "success": True,
                    "status": "running",
                    "config": self.server_config
                }
            else:
                return {
                    "success": True,
                    "status": "stopped",
                    "config": self.server_config
                }
                
        except Exception as e:
            logger.error(f"Error getting MCP Server status: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _monitor_server(self):
        """
        监控MCP Server运行状态
        """
        while True:
            time.sleep(10)  # 每10秒检查一次
            
            with self.status_lock:
                if not self.running:
                    break
            
            try:
                # 检查进程是否还在运行
                if self.server_process:
                    returncode = self.server_process.poll()
                    if returncode is not None:
                        logger.warning(f"MCP Server process exited with code: {returncode}")
                        with self.status_lock:
                            self.running = False
                        break
                    
            except Exception as e:
                logger.error(f"Error monitoring MCP Server: {e}")
