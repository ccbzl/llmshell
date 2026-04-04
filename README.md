# LLM Shell

LLM Shell 是一个基于大语言模型的命令行工具，允许用户通过自然语言指令执行系统命令和文件操作。

## 功能特性

- **多模型支持**：支持 Ollama、Kimi 和 Moonshot 等多种大语言模型
- **工具调用**：通过自然语言指令执行系统命令和文件操作
- **多工具执行**：支持一次执行多个工具调用
- **命令安全**：对危险命令进行分类和授权管理
- **多轮对话**：支持复杂任务的多轮工具调用
- **模块化设计**：代码结构清晰，易于维护和扩展

## 目录结构

```
llmshell/
├── __init__.py     # 包初始化文件
├── main.py         # 主入口文件
├── models.py       # 模型接口实现
├── shell.py        # 核心功能实现
├── tools.py        # 工具类实现
├── README.md       # 项目文档
└── .gitignore      # Git 忽略文件配置
```

## 安装方法

1. **克隆仓库**：
   ```bash
   git clone https://github.com/yourusername/llmshell.git
   cd llmshell
   ```

2. **安装依赖**：
   ```bash
   pip install requests
   ```

3. **设置环境变量**：
   - 对于 Kimi 模型：设置 `KIMI_API_KEY` 环境变量
   - 对于 Moonshot 模型：设置 `MOONSHOT_API_KEY` 环境变量

   示例（Linux/macOS）：
   ```bash
   export KIMI_API_KEY=your_api_key
   ```

   示例（Windows）：
   ```cmd
   set KIMI_API_KEY=your_api_key
   ```

## 使用方法

1. **运行 LLM Shell**：
   ```bash
   python -m llmshell.main
   ```

2. **选择模型**：
   - 1: Ollama (本地模型，默认使用 qwen3:4b)
   - 2: Kimi (需要 API key)
   - 3: Moonshot (需要 API key)

3. **输入指令**：
   例如：
   ```
   [User Input] 列出当前目录下的文件
   ```

4. **工具调用**：
   模型会生成工具调用，执行相应的操作并返回结果。

5. **退出**：
   输入 `exit` 或 `quit` 退出 LLM Shell。

## 安全说明

- **危险命令**：某些危险命令（如 `rm`、`sudo` 等）需要用户授权才能执行
- **文件操作**：文件写入操作可能会覆盖现有文件，请谨慎使用
- **命令超时**：命令执行超时时间为 30 秒，超时会自动终止

## 开发指南

### 新增工具

1. 在 `tools.py` 中创建新的工具类，继承自 `BaseTool`
2. 实现 `get_schema`、`validate_parameters` 和 `execute` 方法
3. 在 `LLMShell.__init__` 方法中注册新工具

### 新增模型

1. 在 `models.py` 中创建新的模型接口类，继承自 `BaseModelInterface`
2. 实现 `generate` 和 `check_model` 方法
3. 在 `LLMShell.__init__` 方法中添加模型选择逻辑

## 示例

### 示例 1：列出目录文件

```
[User Input] 列出当前目录下的所有文件和子目录

[Model Response]
```json
{
  "toolcalls": [
    {
      "name": "execute_command",
      "parameters": {
        "command": "ls -la"
      }
    }
  ]
}
```

[Tool Execution] Running...
[Tool Result]
[Status] ✓ Success
[Output]
total 40
drwxr-xr-x  9 user  group  288 Apr  4 11:00 .
drwxr-xr-x  3 user  group   96 Apr  4 10:00 ..
-rw-r--r--  1 user  group  100 Apr  4 10:30 README.md
...
```

### 示例 2：读取文件内容

```
[User Input] 读取 README.md 文件的内容

[Model Response]
```json
{
  "toolcalls": [
    {
      "name": "file_operation",
      "parameters": {
        "action": "read",
        "path": "./README.md"
      }
    }
  ]
}
```

[Tool Execution] Running...
[Tool Result]
[Status] ✓ Success
[Output]
# LLM Shell

LLM Shell 是一个基于大语言模型的命令行工具，允许用户通过自然语言指令执行系统命令和文件操作。
...
```

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request 来改进这个项目！
