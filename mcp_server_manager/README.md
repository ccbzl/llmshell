# MCP Server Manager

MCP Server Manager 是一个用于管理 MCP (Model Context Protocol) 服务器连接的 Python 包，支持连接、断开、列出工具等操作。

## 功能特性

- **多服务器管理**：支持管理多个 MCP 服务器
- **多种传输协议**：支持 stdio、sse、http、streamable_http 等传输协议
- **统一的连接管理**：使用 AsyncExitStack 管理所有连接的生命周期
- **工具列表获取**：自动获取并缓存服务器提供的工具列表
- **工具调用**：支持调用服务器上的工具并返回结果

## 安装

### 从源代码安装

```bash
cd mcp_server_manager
pip install -e .
```

### 依赖项

- Python 3.7+
- mcp

## 使用示例

### 基本用法

```python
import asyncio
from mcp_server_manager import MCPServerManager

async def main():
    # 创建服务器管理器
    manager = MCPServerManager(config_path="mcpagent-config.json")
    
    # 连接所有服务器
    await manager.connect_all()
    
    # 获取所有工具
    tools = manager.get_all_tools()
    print("可用工具:")
    for server_name, server_tools in tools.items():
        print(f"\n{server_name}:")
        for tool in server_tools:
            print(f"  - {tool.name}: {tool.description}")
    
    # 调用工具
    result = await manager.call_tool("calculator", "add", {"a": 1, "b": 2})
    print(f"\n调用结果: {result}")
    
    # 关闭所有连接
    await manager.close_all()

if __name__ == "__main__":
    asyncio.run(main())
```

### 配置文件格式

```json
{
  "mcpServers": {
    "filesystem": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/directory"]
    },
    "brave-search": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-brave-search"],
      "env": {
        "BRAVE_API_KEY": "your-brave-api-key"
      }
    },
    "calculator": {
      "type": "stdio",
      "command": "python3",
      "args": ["calculator_server.py"]
    }
  }
}
```

## API 文档

### MCPServerManager

#### `__init__(config_path: str = None)`

创建 MCP 服务器管理器实例。

- `config_path`: MCP 配置文件路径，默认 `mcpagent-config.json`

#### `async connect_server(name: str) -> ConnectedServer`

连接到指定的 MCP 服务器。

- `name`: 服务器名称
- 返回: `ConnectedServer` 对象

#### `async connect_all() -> None`

连接所有配置的 MCP 服务器。

#### `get_all_tools() -> Dict[str, List[Any]]`

返回所有连接服务器的工具列表。

- 返回: 字典，键为服务器名称，值为工具列表

#### `get_session(server_name: str) -> Optional[ClientSession]`

获取指定服务器的 ClientSession。

- `server_name`: 服务器名称
- 返回: ClientSession 对象或 None

#### `async call_tool(server_name: str, tool_name: str, arguments: dict) -> Any`

调用指定服务器上的工具。

- `server_name`: 服务器名称
- `tool_name`: 工具名称
- `arguments`: 工具参数
- 返回: 工具执行结果

#### `async close_all() -> None`

关闭所有 MCP 连接。

## 许可证

MIT
