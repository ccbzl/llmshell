# LLM Shell 版本标记

## 版本：v1.0.0

### 日期：2026-04-12

### 主要修改内容：

1. **模型管理架构优化**：
   - 实现了通过模型 ID 选择模型的功能
   - 将模型配置集中到 agent.json 文件中
   - 支持通过配置文件动态加载模型
   - 移除了交互式模型选择，直接使用配置文件或命令行指定的模型 ID

2. **代码优化**：
   - 修复了重复与 LLM 交互的问题
   - 优化了条件判断逻辑，确保当模型返回直接回答时，系统会立即显示回答并跳出循环
   - 修复了模型提供商和模型名称显示为 "Unknown" 的问题

3. **配置文件更新**：
   - 按模型 ID 配置模型，包含 provider、type、model、api_endpoint、parameters 等
   - 设置 default_model，实现通过模型 ID 选择模型的功能

### 运行方式：

- 使用默认模型：`python llmshell.py`
- 使用指定模型：`python llmshell.py --model-id <model_id>`
- 使用指定模型和 API 密钥：`python llmshell.py --model-id <model_id> --api-key <api_key>`

### 支持的模型：

- moonshot-kimi: Moonshot 提供商的 kimi-k2.5 模型
- moonshot-moonshot: Moonshot 提供商的 moonshot-v1-8k 模型
- ollama-deepseek: Ollama 提供商的 deepseek-r1:14b 模型
- ollama-qwen: Ollama 提供商的 qwen3:4b 模型

### 注意事项：

- 运行前请确保已安装所需的依赖包
- 对于需要 API 密钥的模型，请确保已设置相应的环境变量或通过命令行参数提供
- 对于 Ollama 模型，请确保 Ollama 服务已启动且模型已下载