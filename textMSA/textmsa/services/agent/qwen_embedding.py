"""
Qwen Embedding 服务：提供文本向量化功能。

使用 Qwen embedding API 将文本转换为向量，用于文档相似度计算和精排。
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

import httpx
import numpy as np

from textmsa.logging_config import get_logger
from textmsa.settings import get_llm_config

logger = get_logger(__name__)


class QwenEmbedding:
    """Qwen Embedding 服务，用于文本向量化。"""

    def __init__(
        self,
        *,
        model_name: str = "text-embedding-v2",
        config: Optional[Dict[str, Any]] = None,
    ):
        """初始化 Qwen embedding 服务。

        Args:
            model_name: embedding 模型名称，默认 "text-embedding-v2"
            config: 可选的配置字典，如果不提供则从 settings 读取
        """
        cfg = dict(config or get_llm_config())
        self.model_name = model_name
        self.base_url = cfg.get("base_url", "https://api.apiyi.com/v1").rstrip("/")
        self.api_key = cfg.get("api_key", "")
        self.timeout = httpx.Timeout(
            timeout=30.0,
            connect=10.0,
            read=30.0,
            write=10.0,
        )
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )

    def embed_text(self, text: str) -> np.ndarray:
        """生成单个文本的向量。

        Args:
            text: 输入文本

        Returns:
            文本向量（numpy 数组）
        """
        result = self.embed_batch([text])
        return result[0]

    def embed_batch(self, texts: List[str]) -> List[np.ndarray]:
        """批量生成文本向量。

        Args:
            texts: 文本列表

        Returns:
            向量列表，每个元素是一个 numpy 数组
        """
        if not texts:
            return []

        payload = {
            "model": self.model_name,
            "input": texts,
        }

        logger.info(
            "Qwen Embedding 请求 | 模型: %s | 文本数量: %d",
            self.model_name,
            len(texts),
        )

        response = self._client.post("/v1/embeddings", json=payload)
        response.raise_for_status()
        data = response.json()

        embeddings = []
        for item in data.get("data", []):
            embedding = item.get("embedding", [])
            embeddings.append(np.array(embedding, dtype=np.float32))

        logger.info(
            "Qwen Embedding 响应成功 | 模型: %s | 向量数量: %d | 向量维度: %d",
            self.model_name,
            len(embeddings),
            len(embeddings[0]) if embeddings else 0,
        )

        return embeddings

    def close(self) -> None:
        """关闭 HTTP 客户端。"""
        self._client.close()


# 单例实例
_qwen_embedding_instance: Optional[QwenEmbedding] = None


def get_qwen_embedding(
    model_name: str = "text-embedding-v2",
    config: Optional[Dict[str, Any]] = None,
) -> QwenEmbedding:
    """获取 Qwen embedding 服务单例。

    Args:
        model_name: embedding 模型名称
        config: 可选的配置字典

    Returns:
        QwenEmbedding 实例
    """
    global _qwen_embedding_instance
    if _qwen_embedding_instance is None:
        _qwen_embedding_instance = QwenEmbedding(model_name=model_name, config=config)
    return _qwen_embedding_instance


































