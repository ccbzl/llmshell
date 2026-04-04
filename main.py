#!/usr/bin/env python3
"""
主模块 - 包含 main 函数，程序的入口点
"""

import os
import sys
import logging

# 导入 LLMShell 类
from .shell import LLMShell

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('LLM Shell')


def main():
    """主函数"""
    print("=" * 60)
    print("LLM Shell - 模型选择")
    print("=" * 60)
    print("请选择模型提供商:")
    print("1. Ollama")
    print("2. Kimi")
    print("3. Moonshot")
    print("=" * 60)
    
    while True:
        try:
            choice = input("请输入选择 (1/2/3): ").strip()
            if choice == "1":
                model_provider = "ollama"
                model = "qwen3:4b"
                api_key = None
                break
            elif choice == "2":
                model_provider = "kimi"
                model = "kimi-k2.5"
                # 从环境变量读取 API key
                api_key = os.environ.get("KIMI_API_KEY") or os.environ.get("MOONSHOT_API_KEY")
                if not api_key:
                    print("错误: Kimi API key 未设置。请设置 KIMI_API_KEY 或 MOONSHOT_API_KEY 环境变量。")
                    print("例如: export KIMI_API_KEY=your_api_key")
                    continue
                break
            elif choice == "3":
                model_provider = "moonshot"
                model = "moonshot-v1-8k"
                # 从环境变量读取 API key
                api_key = os.environ.get("MOONSHOT_API_KEY") or os.environ.get("KIMI_API_KEY")
                if not api_key:
                    print("错误: Moonshot API key 未设置。请设置 MOONSHOT_API_KEY 或 KIMI_API_KEY 环境变量。")
                    print("例如: export MOONSHOT_API_KEY=your_api_key")
                    continue
                break
            else:
                print("无效选择，请输入 1、2 或 3")
        except KeyboardInterrupt:
            print("\n取消选择，退出程序")
            return
        except Exception as e:
            print(f"错误: {e}")
            return
    
    print(f"\n您选择了: {model_provider} - {model}")
    
    shell = LLMShell(
        model_provider=model_provider,
        model=model,
        api_key=api_key
    )
    shell.run()


if __name__ == "__main__":
    main()
