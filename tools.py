#!/usr/bin/env python3
"""
工具模块 - 包含工具基类和具体工具实现
"""

import subprocess
import shlex
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional


class Tool(ABC):
    """工具基类"""
    
    @abstractmethod
    def name(self) -> str:
        """工具名称"""
        pass
    
    @abstractmethod
    def description(self) -> str:
        """工具描述"""
        pass
    
    @abstractmethod
    def parameters(self) -> Dict[str, Any]:
        """工具参数定义"""
        pass
    
    @abstractmethod
    def run(self, **kwargs) -> Dict[str, Any]:
        """执行工具"""
        pass


class CommandTool(Tool):
    """命令执行工具"""
    # 绝对禁止的命令列表
    PROHIBITED_COMMANDS = {
        'rmdir', 'format', 'mkfs', 'dd', 'shutdown', 'reboot'
    }
    
    # 需要用户授权的命令列表
    AUTHORIZATION_REQUIRED_COMMANDS = {
        'mv', 'cp', 'chmod', 'chown'
    }
    
    # 危险参数
    DANGEROUS_ARGS = ['-rf', '--delete', '--force', '-f']
    
    # 递归删除参数
    RECURSIVE_ARGS = ['-r', '-R', '--recursive']
    
    def name(self) -> str:
        return "execute_command"
    
    def description(self) -> str:
        return "Execute a system command and return the output. Use this to run shell commands like ls, pwd, cat, etc."
    
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute (e.g., 'ls -la', 'pwd', 'cat file.txt')"
                }
            },
            "required": ["command"]
        }
    
    def run(self, **kwargs) -> Dict[str, Any]:
        # 获取命令参数
        command = kwargs.get('command', '')
        
        # 检测危险命令
        command_lower = command.lower()
        
        # 检查绝对禁止的命令
        for prohibited_cmd in self.PROHIBITED_COMMANDS:
            if f' {prohibited_cmd} ' in f' {command_lower} ' or command_lower.startswith(prohibited_cmd + ' '):
                return {
                    "success": False,
                    "error": f"Command '{prohibited_cmd}' is absolutely prohibited for security reasons"
                }
        
        # 检查 rm 命令的特殊处理
        # 使用更健壮的方式检测 rm 命令
        try:
            # 解析命令，获取命令名
            parsed_cmd = shlex.split(command_lower)[0]
            if parsed_cmd == 'rm':
                # 所有 rm 命令都需要授权
                print(f"\n[Security Warning] This command requires authorization: {command}")
                print("Do you want to proceed? (y/N): ", end="")
                confirmation = input().strip().lower()
                if confirmation != 'y':
                    return {
                        "success": False,
                        "error": "Command cancelled by user"
                    }
        except IndexError:
            # 空命令，不处理
            pass
        
        # 检查危险参数
        for dangerous_arg in self.DANGEROUS_ARGS:
            if f' {dangerous_arg} ' in f' {command_lower} ' or command_lower.endswith(f' {dangerous_arg}'):
                return {
                    "success": False,
                    "error": f"Argument '{dangerous_arg}' is not allowed for security reasons"
                }
        
        # 检查需要用户授权的命令
        for auth_cmd in self.AUTHORIZATION_REQUIRED_COMMANDS:
            if f' {auth_cmd} ' in f' {command_lower} ' or command_lower.startswith(auth_cmd + ' '):
                print(f"\n[Security Warning] This command requires authorization: {command}")
                print("Do you want to proceed? (y/N): ", end="")
                confirmation = input().strip().lower()
                if confirmation != 'y':
                    return {
                        "success": False,
                        "error": "Command cancelled by user"
                    }
                break
        
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=30,
                shell=True
            )
            return {
                "success": True,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Command execution timed out after 30 seconds"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


class FileTool(Tool):
    """文件操作工具"""
    
    def name(self) -> str:
        return "file_operation"
    
    def description(self) -> str:
        return "Read or write files. Use this to read file contents or write to files."
    
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["read", "write"],
                    "description": "Action to perform: 'read' to read file, 'write' to write file"
                },
                "path": {
                    "type": "string",
                    "description": "File path (absolute or relative)"
                },
                "content": {
                    "type": "string",
                    "description": "Content to write (required for write action)"
                }
            },
            "required": ["action", "path"]
        }
    
    def run(self, **kwargs) -> Dict[str, Any]:
        try:
            action = kwargs.get('action', '')
            path = kwargs.get('path', '')
            content = kwargs.get('content', None)
            
            if action == "read":
                with open(path, 'r', encoding='utf-8') as f:
                    file_content = f.read()
                return {
                    "success": True,
                    "content": file_content,
                    "path": path
                }
            elif action == "write":
                if content is None:
                    return {
                        "success": False,
                        "error": "Content is required for write action"
                    }
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(content)
                return {
                    "success": True,
                    "message": f"File written successfully: {path}",
                    "path": path
                }
            else:
                return {
                    "success": False,
                    "error": f"Invalid action: {action}. Must be 'read' or 'write'"
                }
        except FileNotFoundError:
            return {
                "success": False,
                "error": f"File not found: {path}"
            }
        except PermissionError:
            return {
                "success": False,
                "error": f"Permission denied: {path}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


class MCPToolCallTool(Tool):
    """MCP Server工具调用工具"""
    
    def __init__(self):
        self.server_manager = None
    
    def set_server_manager(self, server_manager):
        """设置MCPServerManager实例"""
        self.server_manager = server_manager
    
    def name(self) -> str:
        return "mcp_tool_call"
    
    def description(self) -> str:
        return "Call tool through MCP Server using server__tool format"
    
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "tool_name": {
                    "type": "string",
                    "description": "Tool name in server__tool format (e.g., mysql__execute_sql)"
                },
                "args": {
                    "type": "object",
                    "description": "Tool arguments"
                }
            },
            "required": ["tool_name", "args"]
        }
    
    async def run(self, **kwargs) -> Dict[str, Any]:
        """
        调用 MCP 服务器工具（异步接口）

        直接使用 await 调用异步方法
        """
        try:
            # 支持多种参数名称格式，提高兼容性
            tool_name = kwargs.get('tool_name', kwargs.get('tool', ''))
            arguments = kwargs.get('args', kwargs.get('arguments', {}))

            # 解析工具名称，提取服务器名称和工具名称
            parts = tool_name.split("__", 1)
            if len(parts) != 2:
                return {
                    "success": False,
                    "error": f"Invalid tool name format. Use server__tool format."
                }

            server_name, tool_name = parts

            # 检查server_manager是否初始化
            if not self.server_manager:
                return {
                    "success": False,
                    "error": "MCP server manager not initialized"
                }

            # 直接调用异步方法
            result = await self.server_manager.call_tool(server_name, tool_name, arguments)

            # 格式化结果
            return {
                "success": True,
                "content": self._format_tool_result(result)
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    def _format_tool_result(content: Any) -> str:
        """将工具返回内容序列化为字符串"""
        import json
        from mcp.types import TextContent
        
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, TextContent):
                    parts.append(item.text)
                else:
                    try:
                        parts.append(json.dumps(item, ensure_ascii=False, default=str))
                    except Exception:
                        parts.append(str(item))
            return "\n".join(parts)
        try:
            return json.dumps(content, ensure_ascii=False, default=str)
        except Exception:
            return str(content)


class ToolRegistry:
    """工具注册器"""
    
    def __init__(self):
        self.tools: Dict[str, Tool] = {}
    
    def register(self, tool: Tool):
        """注册工具"""
        self.tools[tool.name()] = tool
    
    def get_tool(self, name: str) -> Optional[Tool]:
        """获取工具"""
        return self.tools.get(name)
    
    def get_tools_info(self) -> List[Dict[str, Any]]:
        """获取所有工具信息"""
        return [
            {
                "name": tool.name(),
                "description": tool.description(),
                "parameters": tool.parameters()
            }
            for tool in self.tools.values()
        ]
    
    def list_tools(self) -> str:
        """列出所有工具"""
        lines = ["Available Tools:", "-" * 40]
        for tool in self.tools.values():
            lines.append(f"  {tool.name()}: {tool.description()}")
        return "\n".join(lines)
