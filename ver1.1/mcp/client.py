#!/usr/bin/env python3
"""
MCP Client模块

负责与本地MCP Server通信，发送工具调用请求，处理响应
使用官方MCP SDK
"""

import os
import json
import asyncio
import logging
from typing import Dict, Any, Optional, List
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import TextContent

logger = logging.getLogger('LLM Shell')


class MCPClient:
    """MCP Client"""
    
    def __init__(self):
        """
        初始化MCP Client
        """
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.server_params: Optional[StdioServerParameters] = None
    
    async def connect_to_server(self, command: str, args: list = None, env: dict = None) -> Dict[str, Any]:
        """
        连接到MCP Server
        
        Args:
            command: 启动server的命令 (如 "npx", "python3")
            args: 命令参数
            env: 环境变量字典
            
        Returns:
            连接结果
        """
        try:
            logger.info(f"Attempting to connect to MCP Server: {command} {' '.join(args or [])}")
            
            # 直接使用子进程启动服务器，不使用官方SDK的stdio_client
            import asyncio
            process_env = env.copy() if env else None
            self.server_process = await asyncio.create_subprocess_exec(
                command, *args, 
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=process_env
            )
            
            self.reader = self.server_process.stdout
            self.writer = self.server_process.stdin
            self.server_config = {
                "command": command,
                "args": args or [],
                "env": env or {}
            }
            
            # 等待服务器启动
            await asyncio.sleep(1)
            
            # 检查服务器是否启动成功
            if self.server_process.returncode is not None:
                stderr = await self.server_process.stderr.read()
                error_message = stderr.decode('utf-8') if stderr else "Unknown error"
                return {
                    "success": False,
                    "error": f"MCP Server failed to start: {error_message}"
                }
            
            # 手动发送初始化请求
            import json
            init_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {}
            }
            
            self.writer.write(json.dumps(init_request).encode('utf-8') + b'\n')
            await self.writer.drain()
            
            # 读取初始化响应
            init_response = await self.reader.readline()
            if not init_response:
                return {
                    "success": False,
                    "error": "No response from MCP Server"
                }
            
            try:
                init_result = json.loads(init_response.decode('utf-8'))
                if "error" in init_result:
                    return {
                        "success": False,
                        "error": f"Initialization error: {init_result['error'].get('message', 'Unknown error')}"
                    }
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing initialization response: {e}")
            
            logger.info(f"Connected to MCP Server: {command} {' '.join(args or [])}")
            return {
                "success": True,
                "message": f"Connected to MCP Server: {command} {' '.join(args or [])}"
            }
            
        except Exception as e:
            error_msg = f"Error connecting to MCP Server: {e}"
            logger.error(error_msg)
            logger.exception(e)
            return {
                "success": False,
                "error": error_msg
            }
    
    async def call_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        调用MCP Server上的工具
        
        Args:
            tool_name: 工具名称
            parameters: 工具参数
            
        Returns:
            工具执行结果
        """
        try:
            if not self.reader or not self.writer:
                return {
                    "success": False,
                    "error": "Not connected to MCP Server"
                }
            
            logger.info(f"Calling tool '{tool_name}' with parameters: {parameters}")
            
            # 手动构建工具调用请求
            import json
            request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "callTool",
                "params": {
                    "toolName": tool_name,
                    "arguments": parameters
                }
            }
            
            # 发送请求
            self.writer.write(json.dumps(request).encode('utf-8') + b'\n')
            await self.writer.drain()
            
            # 读取响应
            response_json = await self.reader.readline()
            if not response_json:
                return {
                    "success": False,
                    "error": "No response from MCP Server"
                }
            
            response = json.loads(response_json.decode('utf-8'))
            
            if "result" in response:
                result = response["result"]
                if "content" in result:
                    # 提取文本内容
                    text_contents = []
                    for item in result["content"]:
                        if item.get("type") == "text":
                            text_contents.append(item.get("text", ""))
                    output = "\n".join(text_contents)
                else:
                    output = str(result)
                
                logger.info(f"Tool call result: {output[:200]}{'...' if len(output) > 200 else ''}")
                return {
                    "success": True,
                    "content": output
                }
            else:
                error_message = response.get("error", {}).get("message", "Unknown error")
                return {
                    "success": False,
                    "error": f"Tool call error: {error_message}"
                }
                
        except Exception as e:
            error_msg = f"Error calling tool: {e}"
            logger.error(error_msg)
            logger.exception(e)
            return {
                "success": False,
                "error": error_msg
            }
    
    async def get_available_tools(self) -> Dict[str, Any]:
        """
        获取MCP Server上可用的工具
        
        Returns:
            可用工具列表
        """
        try:
            if not self.reader or not self.writer:
                return {
                    "success": False,
                    "error": "Not connected to MCP Server"
                }
            
            logger.info("Getting available tools from MCP Server")
            
            # 手动构建请求
            import json
            request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "listTools",
                "params": {}
            }
            
            # 发送请求
            self.writer.write(json.dumps(request).encode('utf-8') + b'\n')
            await self.writer.drain()
            
            # 读取响应
            response_json = await self.reader.readline()
            if not response_json:
                return {
                    "success": False,
                    "error": "No response from MCP Server"
                }
            
            response = json.loads(response_json.decode('utf-8'))
            
            if "result" in response:
                tools = response["result"]
                if isinstance(tools, list):
                    logger.info(f"Available tools: {len(tools)} tools")
                    return {
                        "success": True,
                        "tools": tools
                    }
                elif isinstance(tools, dict) and "tools" in tools:
                    logger.info(f"Available tools: {len(tools['tools'])} tools")
                    return {
                        "success": True,
                        "tools": tools["tools"]
                    }
                else:
                    return {
                        "success": False,
                        "error": "Invalid tools response format"
                    }
            else:
                error_message = response.get("error", {}).get("message", "Unknown error")
                return {
                    "success": False,
                    "error": f"Error getting tools: {error_message}"
                }
                
        except Exception as e:
            error_msg = f"Error getting available tools: {e}"
            logger.error(error_msg)
            logger.exception(e)
            return {
                "success": False,
                "error": error_msg
            }
    
    async def get_server_info(self) -> Dict[str, Any]:
        """
        获取MCP Server信息
        
        Returns:
            服务器信息
        """
        try:
            if not self.session:
                return {
                    "success": False,
                    "error": "Not connected to MCP Server"
                }
            
            logger.info("Getting MCP Server info")
            
            # 获取工具数量
            tools_response = await self.session.list_tools()
            tool_count = len(tools_response.tools)
            
            # 尝试获取prompts和resources
            prompt_count = 0
            resource_count = 0
            
            try:
                prompts = await self.session.list_prompts()
                prompt_count = len(prompts.prompts)
            except:
                pass
            
            try:
                resources = await self.session.list_resources()
                resource_count = len(resources.resources)
            except:
                pass
            
            info = {
                "tools": tool_count,
                "prompts": prompt_count,
                "resources": resource_count
            }
            
            logger.info(f"MCP Server info: {info}")
            
            return {
                "success": True,
                "info": info
            }
            
        except Exception as e:
            error_msg = f"Error getting server info: {e}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }
    
    async def close(self):
        """
        关闭连接
        """
        try:
            await self.exit_stack.aclose()
            self.session = None
            self.server_params = None
            logger.info("MCP Server connection closed")
        except Exception as e:
            logger.error(f"Error closing MCP Server connection: {e}")

    def is_connected(self) -> bool:
        """
        检查是否已连接到MCP Server
        
        Returns:
            是否已连接
        """
        return self.session is not None
