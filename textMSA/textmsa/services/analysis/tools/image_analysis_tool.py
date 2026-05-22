"""
图片分析工具：使用多模态 LLM 解读图片文件。

该工具基于 langgraph 框架实现，独立于旧工具。
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from textmsa.logging_config import get_logger
from textmsa.services.agent.llm_client import LLMClient, LLMRequest
from textmsa.services.file.file_service import get_file_service
from textmsa.services.analysis.tools.file_reader_tool import FileReaderTool
from textmsa.settings import get_multimodal_llm_config

logger = get_logger(__name__)


class ImageAnalysisTool:
    """
    图片分析工具，使用多模态 LLM 解读图片文件
    
    注意：不使用 try-catch，异常直接向上抛出。
    """

    IMAGE_TYPES = {"png", "jpg", "jpeg", "bmp", "gif", "tiff", "webp"}

    def __init__(
        self,
        *,
        llm_client: LLMClient | None = None,
        system_prompt: str | None = None,
        temperature: float = 0.2,
    ) -> None:
        """
        初始化图片分析工具
        
        Args:
            llm_client: LLM 客户端，如果为 None 则使用多模态 LLM 配置创建
            system_prompt: 系统提示词，如果为 None 则使用默认提示词
            temperature: LLM 温度参数
        """
        # 如果没有提供 llm_client，使用多模态 LLM 配置创建
        if llm_client is None:
            multimodal_config = get_multimodal_llm_config()
            self._llm_client = LLMClient(config=multimodal_config)
        else:
            self._llm_client = llm_client
        
        self._file_service = get_file_service()
        self._file_reader = FileReaderTool()
        self._system_prompt = system_prompt or (
            "你是多模态文件阅读助手，可以根据图片、结构化数据和文本片段，"
            "用中文给出简要的文件内容解读和关键发现。请忠实于给定的内容。"
        )
        self._temperature = temperature

        logger.info(
            "ImageAnalysisTool initialized",
            extra={
                "temperature": temperature,
            },
        )

    def analyze(
        self,
        *,
        file_id: str,
        user_id: str,
        question: str = "",
    ) -> str:
        """
        分析图片文件并返回解读结果
        
        Args:
            file_id: 文件ID
            user_id: 用户ID
            question: 用户问题或分析要求（可选）
        
        Returns:
            分析结果字符串
            
        Raises:
            Exception: 如果分析失败，直接抛出异常（不捕获）
        """
        # 获取文件信息（如果失败，file_service 会抛出异常）
        file_info = self._file_service.get_file_info(file_id, user_id)
        filename = file_info.get("filename", "unknown")
        file_path = file_info.get("file_path")
        
        # 构建消息
        messages = self._build_messages(
            file_path=file_path,
            filename=filename,
            question=question,
        )
        
        # 调用多模态 LLM（如果失败会抛出异常）
        request = LLMRequest(
            messages=messages,
            temperature=self._temperature,
        )
        response = self._llm_client.chat(request)
        
        # 返回分析结果
        return response.content.strip()

    def _build_messages(
        self,
        *,
        file_path: str,
        filename: str,
        question: str,
    ) -> list[dict[str, Any]]:
        """
        构建多模态消息
        
        Args:
            file_path: 文件路径
            filename: 文件名
            question: 用户问题
        
        Returns:
            消息列表
        """
        metadata_payload = {
            "filename": filename,
            "question": question or "",
        }
        
        user_instruction = (
            question.strip()
            or "请基于提供的图片给出简明的分析总结。"
        )
        
        content_blocks: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": "请结合以下文件信息，回答用户的问题：\n"
                f"{user_instruction}",
            },
            {
                "type": "text",
                "text": "文件元信息：\n"
                + json.dumps(metadata_payload, ensure_ascii=False, indent=2),
            },
        ]
        
        # 添加图片内容块
        image_block = self._build_base64_image_block(file_path)
        if image_block:
            content_blocks.append(image_block)
        
        return [
            {"role": "system", "content": self._system_prompt},
            {"role": "user", "content": content_blocks},
        ]

    def _build_base64_image_block(
        self,
        file_path: str,
    ) -> dict[str, Any] | None:
        """
        构建 base64 编码的图片内容块
        
        Args:
            file_path: 文件路径
        
        Returns:
            图片内容块字典，如果文件不存在则返回 None
        """
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
        """从文件名推断扩展名"""
        parts = (filename or "").lower().rsplit(".", 1)
        return parts[1] if len(parts) == 2 else ""

    def _guess_mime(self, ext: str) -> str:
        """根据扩展名推断 MIME 类型"""
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


__all__ = ["ImageAnalysisTool"]

