#!/usr/bin/env python3
"""
模型接口模块 - 包含模型接口基类和具体模型实现
"""

import requests
import json
import os
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Generator

# 导入日志
import logging
logger = logging.getLogger('LLM Shell')


class BaseModelInterface(ABC):
    """模型接口基类"""
    
    @abstractmethod
    def generate(self, prompt: str, system_prompt: Optional[str] = None, stream: bool = True) -> Generator[Dict[str, Any], None, None]:
        """生成响应"""
        pass
    
    @abstractmethod
    def check_model(self) -> bool:
        """检查模型是否可用"""
        pass


class OllamaInterface(BaseModelInterface):
    """Ollama 模型接口"""
    
    def __init__(self, model: str = "qwen3:4b"):
        self.model = model
        self.base_url = "http://localhost:11434/api"
    
    def generate(self, prompt: str, system_prompt: Optional[str] = None, stream: bool = True) -> Generator[Dict[str, Any], None, None]:
        """生成响应"""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": stream,
            "options": {
                "temperature": 0.7,
                "num_predict": 2048
            }
        }
        if system_prompt:
            payload["system"] = system_prompt
        
        logger.info(f"[Model Request] Sending to {self.model} (Ollama)")
        logger.debug(f"[Prompt] {prompt[:100]}...")
        if system_prompt:
            logger.debug(f"[System Prompt] {system_prompt[:100]}...")
        
        try:
            response = requests.post(
                f"{self.base_url}/generate",
                json=payload,
                stream=stream,
                timeout=120
            )
            response.raise_for_status()
            logger.info(f"[Model Response] Received from {self.model} (Ollama)")
            
            if stream:
                full_response = ""
                for line in response.iter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            if "response" in data:
                                full_response += data["response"]
                            yield data
                        except json.JSONDecodeError:
                            continue
                logger.debug(f"[Full Response] {full_response[:200]}...")
            else:
                data = response.json()
                if "response" in data:
                    logger.debug(f"[Full Response] {data['response'][:200]}...")
                yield data
        except requests.exceptions.ConnectionError:
            error_msg = "Cannot connect to Ollama. Please make sure Ollama is running."
            logger.error(f"[Model Error] {error_msg}")
            yield {"error": error_msg}
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[Model Error] {error_msg}")
            yield {"error": error_msg}
    
    def check_model(self) -> bool:
        """检查模型是否可用"""
        try:
            response = requests.get(f"{self.base_url}/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get("models", [])
                return any(self.model in m.get("name", "") for m in models)
            return False
        except:
            return False





class MoonshotInterface(BaseModelInterface):
    """Moonshot 模型接口（支持 Kimi 和 Moonshot 模型）"""
    
    def __init__(self, model: str = "kimi-k2.5", api_key: Optional[str] = None):
        self.model = model
        # 优先从环境变量读取 API key
        self.api_key = api_key or os.environ.get("KIMI_API_KEY") or os.environ.get("MOONSHOT_API_KEY")
        if not self.api_key:
            raise ValueError("API key not provided. Please set KIMI_API_KEY or MOONSHOT_API_KEY environment variable.")
        self.base_url = "https://api.moonshot.cn/v1"
    
    def generate(self, prompt: str, system_prompt: Optional[str] = None, stream: bool = True) -> Generator[Dict[str, Any], None, None]:
        """生成响应"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        messages = []
        # 启用 system prompt
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        # 根据模型设置不同的参数
        if self.model.startswith("kimi-k2"):
            # 对于 kimi-k2.5 模型，使用文档推荐的参数
            payload = {
                "model": self.model,
                "messages": messages,
                "stream": stream,
                "temperature": 1.0,  # kimi-k2.5 固定使用 1.0
                "max_tokens": 16000  # 至少 16000 以支持完整的思考内容
            }
        else:
            # 其他模型使用默认参数
            payload = {
                "model": self.model,
                "messages": messages,
                "stream": stream,
                "temperature": 0.7,
                "max_tokens": 2048
            }
        
        logger.info(f"[Model Request] Sending to {self.model} (Moonshot)")
        logger.debug(f"[Prompt] {prompt[:100]}...")
        if system_prompt:
            logger.debug(f"[System Prompt] {system_prompt[:100]}...")
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
                stream=stream,
                timeout=120
            )
            response.raise_for_status()
            logger.info(f"[Model Response] Received from {self.model} (Moonshot)")
            
            if stream:
                full_response = ""
                for line in response.iter_lines():
                    if line:
                        line = line.decode('utf-8')
                        if line.startswith('data: '):
                            line = line[6:]
                            if line == '[DONE]':
                                break
                            try:
                                data = json.loads(line)
                                if "choices" in data and data["choices"]:
                                    delta = data["choices"][0].get("delta", {})
                                    # 处理 reasoning_content 字段（模型思考内容）
                                    if "reasoning_content" in delta:
                                        reasoning = delta["reasoning_content"]
                                        logger.debug(f"[Model Reasoning] {reasoning[:100]}...")
                                        # 暂时不返回思考内容，只返回最终内容
                                    # 处理 content 字段（最终响应）
                                    if "content" in delta:
                                        content = delta["content"]
                                        full_response += content
                                        yield {"response": content}
                            except json.JSONDecodeError:
                                continue
                logger.debug(f"[Full Response] {full_response[:200]}...")
            else:
                data = response.json()
                if "choices" in data and data["choices"]:
                    message = data["choices"][0].get("message", {})
                    # 处理 reasoning_content 字段（模型思考内容）
                    if "reasoning_content" in message:
                        reasoning = message["reasoning_content"]
                        logger.debug(f"[Model Reasoning] {reasoning[:100]}...")
                    # 处理 content 字段（最终响应）
                    content = message.get("content", "")
                    logger.debug(f"[Full Response] {content[:200]}...")
                    yield {"response": content}
                yield {"response": ""}
        except requests.exceptions.ConnectionError:
            error_msg = "Cannot connect to Moonshot. Please make sure the API endpoint is reachable."
            logger.error(f"[Model Error] {error_msg}")
            yield {"error": error_msg}
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[Model Error] {error_msg}")
            yield {"error": error_msg}
    
    def check_model(self) -> bool:
        """检查模型是否可用"""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}"
            }
            response = requests.get(f"{self.base_url}/models", headers=headers, timeout=5)
            if response.status_code == 200:
                return True
            return False
        except:
            return False
