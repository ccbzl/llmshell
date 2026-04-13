#!/usr/bin/env python3
"""
Simple Calculator MCP Server for Testing
Implements basic arithmetic operations via MCP protocol
"""

import asyncio
import json
import sys
from typing import Any, Dict, List, Optional

class CalculatorMCPServer:
    """A simple MCP server providing calculator functionality"""
    
    def __init__(self):
        self.initialized = False
        self.tools = [
            {
                "name": "add",
                "description": "Add two numbers together V2.0",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "a": {"type": "number", "description": "First number"},
                        "b": {"type": "number", "description": "Second number"}
                    },
                    "required": ["a", "b"]
                }
            },
            {
                "name": "subtract",
                "description": "Subtract second number from first V2.0",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "a": {"type": "number", "description": "First number"},
                        "b": {"type": "number", "description": "Second number"}
                    },
                    "required": ["a", "b"]
                }
            },
            {
                "name": "multiply",
                "description": "Multiply two numbers V2.0",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "a": {"type": "number", "description": "First number"},
                        "b": {"type": "number", "description": "Second number"}
                    },
                    "required": ["a", "b"]
                }
            },
            {
                "name": "divide",
                "description": "Divide first number by second",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "a": {"type": "number", "description": "Dividend"},
                        "b": {"type": "number", "description": "Divisor"}
                    },
                    "required": ["a", "b"]
                }
            },
            {
                "name": "power",
                "description": "Raise a number to a power V2.0",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "base": {"type": "number", "description": "Base number"},
                        "exponent": {"type": "number", "description": "Exponent"}
                    },
                    "required": ["base", "exponent"]
                }
            }
        ]
    
    def send_message(self, message: Dict[str, Any]):
        """Send a JSON-RPC message"""
        print(json.dumps(message), flush=True)
    
    def handle_initialize(self, request_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle initialize request"""
        self.initialized = True
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2025-06-18",
                "capabilities": {
                    "tools": {"listChanged": False}
                },
                "serverInfo": {
                    "name": "calculator-server",
                    "version": "1.0.0"
                }
            }
        }
    
    def handle_tools_list(self, request_id: str) -> Dict[str, Any]:
        """Handle tools/list request"""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": self.tools
            }
        }
    
    def handle_tool_call(self, request_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools/call request"""
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        
        try:
            if tool_name == "add":
                result = arguments["a"] + arguments["b"]
            elif tool_name == "subtract":
                result = arguments["a"] - arguments["b"]
            elif tool_name == "multiply":
                result = arguments["a"] * arguments["b"]
            elif tool_name == "divide":
                if arguments["b"] == 0:
                    return self.make_error(request_id, -32600, "Division by zero")
                result = arguments["a"] / arguments["b"]
            elif tool_name == "power":
                result = arguments["base"] ** arguments["exponent"]
            else:
                return self.make_error(request_id, -32601, f"Unknown tool: {tool_name}")
            
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": str(result)
                        }
                    ]
                }
            }
        except KeyError as e:
            return self.make_error(request_id, -32602, f"Missing required parameter: {e}")
        except Exception as e:
            return self.make_error(request_id, -32603, str(e))
    
    def make_error(self, request_id: str, code: int, message: str) -> Dict[str, Any]:
        """Create an error response"""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": code,
                "message": message
            }
        }
    
    def handle_request(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Handle an incoming request"""
        method = request.get("method", "")
        request_id = request.get("id")
        params = request.get("params", {})
        
        if method == "initialize":
            return self.handle_initialize(request_id, params)
        elif method == "tools/list":
            return self.handle_tools_list(request_id)
        elif method == "tools/call":
            return self.handle_tool_call(request_id, params)
        elif method == "notifications/initialized":
            # Notification, no response needed
            return None
        else:
            return self.make_error(request_id, -32601, f"Method not found: {method}")
    
    def run(self):
        """Main server loop"""
        while True:
            try:
                line = sys.stdin.readline()
                if not line:
                    break
                
                request = json.loads(line.strip())
                response = self.handle_request(request)
                
                if response:
                    self.send_message(response)
                    
            except json.JSONDecodeError as e:
                self.send_message(self.make_error(None, -32700, f"Parse error: {e}"))
            except Exception as e:
                self.send_message(self.make_error(None, -32603, f"Internal error: {e}"))


if __name__ == "__main__":
    server = CalculatorMCPServer()
    server.run()
