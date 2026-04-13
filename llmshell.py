#!/usr/bin/env python3
"""
主模块 - 包含 main 函数，程序的入口点
"""

import os
import sys
import logging

# 导入 LLMShell 类
from shell import LLMShell

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('LLM Shell')


async def main():
    """主函数"""
    import argparse
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='LLM Shell')
    parser.add_argument('--model-id', '-m', default=None,
                        help='Model ID (default: use default model from config)')
    parser.add_argument('--api-key', '-k', default=None,
                        help='API key (default: from environment or hardcoded)')
    args = parser.parse_args()
    
    # 获取模型 ID
    model_id = args.model_id
    
    # 设置 API key
    api_key = args.api_key
    
    # 打印模型信息
    if model_id:
        print(f"\nUsing specified model: {model_id}")
    else:
        # 从配置文件中读取默认模型信息
        try:
            import json
            with open('agent.json', 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            models_config = config.get('models', {})
            default_model_id = models_config.get('default_model')
            if default_model_id and default_model_id in models_config:
                model_config = models_config[default_model_id]
                provider = model_config.get('provider', 'Unknown')
                model_name = model_config.get('model', 'Unknown')
                print(f"\nUsing default model from config: {default_model_id} (Provider: {provider}, Model: {model_name})")
            else:
                print("\nUsing default model from config")
        except Exception as e:
            print("\nUsing default model from config")
    
    # 创建 LLM Shell 实例
    shell = LLMShell(
        model_id=model_id,
        api_key=api_key
    )
    # 初始化MCP服务器连接
    if shell.server_manager:
        await shell._initialize_mcp()
    # 运行shell
    await shell.run()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
