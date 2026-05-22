"""
Multi-modal file reader tool.

This tool builds multi-modal chat messages (text + images) and delegates the
actual interpretation of the file content to the configured LLM.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from textmsa.logging_config import get_logger
from textmsa.services.agent.llm_client import LLMClient, LLMRequest
from textmsa.services.agent.tools.file_reader_tool import (
    FileReadResult,
    FileReaderTool,
)
from textmsa.services.file.file_service import get_file_service
from textmsa.settings import get_multimodal_llm_config

logger = get_logger(__name__)


class MultiModalReaderTool:
    """Encapsulates building and sending multi-modal reading requests."""

    IMAGE_TYPES = {"png", "jpg", "jpeg", "bmp", "gif", "tiff", "webp"}


    def __init__(
        self,
        *,
        llm_client: LLMClient | None = None,
        system_prompt: str | None = None,
        max_preview_chars: int = 4000,
        temperature: float = 0.2,
    ) -> None:
        # 如果没有提供 llm_client，使用多模态 LLM 配置创建
        if llm_client is None:
            multimodal_config = get_multimodal_llm_config()
            self._llm_client = LLMClient(config=multimodal_config)
        else:
            self._llm_client = llm_client
        self._file_reader = FileReaderTool()
        self._file_service = get_file_service()
        self._system_prompt = system_prompt or (
            "你是多模态文件阅读助手，可以根据图片、结构化数据和文本片段，"
            "用中文给出简要的文件内容解读和关键发现。请忠实于给定的内容。"
        )
        self._max_preview_chars = max_preview_chars
        self._temperature = temperature

    def read_with_llm(
        self,
        *,
        file_id: str,
        user_id: str,
        question: str = "",
    ) -> str:
        """Read a file via multi-modal LLM prompt."""
        read_result = self._file_reader.read_file(file_id=file_id, user_id=user_id)
        
        messages = self._build_messages(
            read_result=read_result,
            question=question,
        )
        request = LLMRequest(
            messages=messages,
            temperature=self._temperature,
        )
        response = self._llm_client.chat(request)
        llm_output = response.content.strip()
        return llm_output

    def _build_messages(
        self,
        *,
        read_result: FileReadResult,
        question: str,
    ) -> list[dict[str, Any]]:
        """Assemble the system + user messages for the multi-modal call."""
        metadata_payload = {
            "file_id": read_result.file_id,
            "filename": read_result.filename,
            "file_type": read_result.file_type,
            "question": question or "",
        }

        user_instruction = (
            question.strip()
            or "请基于提供的内容给出简明的分析总结。"
        )

        content_blocks: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": "请结合以下文件片段与元信息，回答用户的问题：\n"
                f"{user_instruction}",
            },
            {
                "type": "text",
                "text": "文件元信息：\n"
                + json.dumps(metadata_payload, ensure_ascii=False, indent=2),
            },
        ]

        image_block = self._build_base64_image_block(read_result.file_path)
        if image_block:
            content_blocks.append(image_block)

        return [
            {"role": "system", "content": self._system_prompt},
            {"role": "user", "content": content_blocks},
        ]

    def _render_preview(self, preview: Any) -> str:
        """Render FileReadResult.preview into text."""
        if preview is None:
            return ""
        if isinstance(preview, str):
            return preview
        if isinstance(preview, Mapping):
            try:
                return json.dumps(preview, ensure_ascii=False, indent=2)
            except Exception:  # noqa: BLE001
                return str(preview)
        if isinstance(preview, Sequence) and not isinstance(preview, (str, bytes, bytearray)):
            try:
                return json.dumps(preview, ensure_ascii=False, indent=2)
            except Exception:  # noqa: BLE001
                return "\n".join(str(item) for item in preview[:5])
        return str(preview)

    def _build_base64_image_block(
        self,
        file_path: str,
    ) -> dict[str, Any] | None:
        """Construct an image content block when applicable."""
        image_path = Path(str(file_path))
        if not image_path.exists():
            return None
        data = image_path.read_bytes()
        encoded = base64.b64encode(data).decode("utf-8")
        
        # 获取文件扩展名以确定 MIME 类型
        ext = self._guess_ext(image_path.name)
        mime_type = self._guess_mime(ext)
        
        # 使用 OpenAI 兼容的格式：image_url
        return {
            "type": "image_url",
            "image_url": {
                "url": f"data:{mime_type};base64,{encoded}"
            }
        }

    def _guess_ext(self, filename: str) -> str:
        parts = (filename or "").lower().rsplit(".", 1)
        return parts[1] if len(parts) == 2 else ""

    def _guess_mime(self, ext: str) -> str:
        mapping = {
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "bmp": "image/bmp",
            "gif": "image/gif",
            "tiff": "image/tiff",
            "webp": "image/webp",
        }
        return mapping.get(ext, "application/octet-stream")


