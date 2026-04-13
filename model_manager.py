#!/usr/bin/env python3
"""
模型管理器

用于管理所有模型的配置和实例化，支持通过配置参数创建不同的模型实例。
"""

import json
import os
from typing import Dict, Any, Optional

from models import BaseModelInterface, OllamaInterface, MoonshotInterface


class ModelManager:
    """模型管理器"""

    def __init__(self, config_path: str = "agent.json"):
        """
        初始化模型管理器
        
        Args:
            config_path: 配置文件路径，默认 agent.json
        """
        self.config_path = config_path
        self.config: Dict[str, Any] = {}
        self.models_config: Dict[str, Any] = {}
        self._load_config()

    def _load_config(self) -> None:
        """加载模型配置"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            self.config = config
            models_config = config.get("models", {})
            
            # 计算实际模型数量（排除default_model）
            model_count = len(models_config) - 1 if "default_model" in models_config else len(models_config)
            print(f"Loaded {model_count} models from {self.config_path}")
            
            self.models_config = models_config
        except FileNotFoundError:
            print(f"Config not found: {self.config_path}")
        except Exception as e:
            print(f"Failed to load config: {e}")

    def get_model_interface(self, model_id: Optional[str] = None, api_key: Optional[str] = None) -> BaseModelInterface:
        """
        获取模型接口实例
        
        Args:
            model_id: 模型 ID，None 表示使用默认模型
            api_key: API 密钥，None 表示从环境变量获取
        
        Returns:
            模型接口实例
        """
        # 使用指定的模型 ID 或默认模型 ID
        model_id = model_id or self.models_config.get("default_model")
        if not model_id:
            raise ValueError("No model ID specified and no default model configured")
        
        # 获取模型配置
        if model_id not in self.models_config:
            raise ValueError(f"Unknown model ID: {model_id}")
        
        model_config = self.models_config[model_id]
        provider = model_config.get("provider")
        model_name = model_config.get("model")
        
        if not provider or not model_name:
            raise ValueError(f"Invalid model configuration for {model_id}")
        
        # 获取 API 密钥
        if api_key is None and "api_key_env" in model_config:
            api_key = os.environ.get(model_config["api_key_env"])
        
        # 根据模型类型创建实例
        model_type = model_config.get("type")
        if model_type == "OllamaInterface":
            return OllamaInterface(model=model_name)
        elif model_type == "MoonshotInterface":
            if not api_key:
                raise ValueError("API key is required for Moonshot model")
            return MoonshotInterface(model=model_name, api_key=api_key)
        else:
            raise ValueError(f"Unsupported model type: {model_type}")

    def list_providers(self) -> list:
        """
        列出所有可用的模型提供商
        
        Returns:
            模型提供商列表
        """
        return list(self.models_config.keys())

    def get_max_rounds(self) -> int:
        """
        获取最大轮数配置
        
        Returns:
            最大轮数，如果配置中没有则返回默认值 5
        """
        return self.config.get("MAX_ROUNDS", 5)

    def list_models(self, provider: str) -> list:
        """
        列出指定提供商的所有可用模型
        
        Args:
            provider: 模型提供商
        
        Returns:
            模型列表
        """
        if provider not in self.models_config:
            raise ValueError(f"Unknown model provider: {provider}")
        
        return self.models_config[provider].get("models", [])

    def get_default_model(self, provider: str) -> str:
        """
        获取指定提供商的默认模型
        
        Args:
            provider: 模型提供商
        
        Returns:
            默认模型名称
        """
        if provider not in self.models_config:
            raise ValueError(f"Unknown model provider: {provider}")
        
        default_model = self.models_config[provider].get("default_model")
        if not default_model:
            raise ValueError(f"No default model configured for {provider}")
        
        return default_model