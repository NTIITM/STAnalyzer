"""
多模态 LLM 客户端（OpenAI 风格）。

与 `LLMClient` 完全兼容的 chat/completions 风格，只是默认读取
`get_multimodal_llm_config()`，适合专门用于图片 + 文本等多模态调用。

当前项目中的 `MultiModalReaderTool` 已经构造了 OpenAI 兼容的 messages：
- system: 纯文本指令
- user: 包含 `{"type": "text"}` 与 `{"type": "image_url"}` 的内容块

因此这里直接复用 `LLMClient` 的能力，只是提供一个语义更清晰的封装。
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from textmsa.services.agent.llm_client import LLMClient, LLMRequest, LLMTelemetryHook
from textmsa.settings import get_multimodal_llm_config


class MultimodalClient(LLMClient):
    """多模态专用的 LLMClient 封装。

    - 默认从 `multimodal_llm` 段读取配置
    - 保持与 `LLMClient` 完全一致的 `chat()` 接口
    """

    def __init__(
        self,
        *,
        config: Optional[Dict[str, Any]] = None,
        telemetry_hook: Optional[LLMTelemetryHook] = None,
    ) -> None:
        cfg = dict(config or get_multimodal_llm_config())
        super().__init__(config=cfg, telemetry_hook=telemetry_hook)


_MULTIMODAL_CLIENT: Optional[MultimodalClient] = None


def get_multimodal_client() -> MultimodalClient:
    """懒加载单例多模态客户端。"""
    global _MULTIMODAL_CLIENT
    if _MULTIMODAL_CLIENT is None:
        _MULTIMODAL_CLIENT = MultimodalClient()
    return _MULTIMODAL_CLIENT


__all__ = [
    "MultimodalClient",
    "get_multimodal_client",
    "LLMRequest",
]


