"""
文本分析工具：使用 LLM 解读文本文件。

该工具基于 langgraph 框架实现，独立于旧工具。
"""

from __future__ import annotations

import json
from typing import Any

from textmsa.logging_config import get_logger
from textmsa.services.agent.llm_client import LLMClient, LLMRequest
from textmsa.services.file.file_service import get_file_service
from textmsa.settings import get_llm_config

logger = get_logger(__name__)


class TextAnalysisTool:
    """
    文本分析工具，使用 LLM 解读文本文件
    
    注意：不使用 try-catch，异常直接向上抛出。
    """

    def __init__(
        self,
        *,
        llm_client: LLMClient | None = None,
        system_prompt: str | None = None,
        temperature: float = 0.2,
    ) -> None:
        """
        初始化文本分析工具
        
        Args:
            llm_client: LLM 客户端，如果为 None 则使用默认配置创建
            system_prompt: 系统提示词，如果为 None 则使用默认提示词
            temperature: LLM 温度参数
        """
        if llm_client is None:
            llm_config = get_llm_config()
            self._llm_client = LLMClient(config=llm_config)
        else:
            self._llm_client = llm_client
        
        self._file_service = get_file_service()
        self._system_prompt = system_prompt or (
            "你是一个专业的文本分析助手。请仔细阅读用户提供的文本内容，"
            "并根据用户的问题或要求进行分析和解读。"
            "请用中文给出清晰、准确的分析结果。"
        )
        self._temperature = temperature

        logger.info(
            "TextAnalysisTool initialized",
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
        language: str = "zh",
    ) -> str:
        """
        分析文本文件并返回解读结果
        
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
        
        # 读取文件内容（如果失败会抛出异常）
        file_content = self._read_file_content(file_path)
        
        # 构建 prompt
        user_prompt = self._build_prompt(
            filename=filename,
            file_content=file_content,
            question=question,
            language=language,
        )
        
        # 调用 LLM 进行分析（如果失败会抛出异常）
        request = LLMRequest(
            messages=[
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=self._temperature,
        )
        response = self._llm_client.chat(request)
        
        # 返回分析结果
        return response.content.strip()

    def _read_file_content(self, file_path: str) -> str:
        """
        读取文件内容
        
        Args:
            file_path: 文件路径
        
        Returns:
            文件内容字符串
        """
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

    def _build_prompt(
        self,
        *,
        filename: str,
        file_content: str,
        question: str,
        language: str = "zh",
    ) -> str:
        """
        构建分析 prompt
        
        Args:
            filename: 文件名
            file_content: 文件内容
            question: 用户问题
            language: 语言代码，默认为中文（"zh"）
        
        Returns:
            prompt 字符串
        """
        prompt_parts = [
            f"文件名：{filename}",
            "",
            "文件内容：",
            "```",
            file_content,
            "```",
            "",
        ]
        
        if question:
            prompt_parts.extend([
                "用户问题或要求：",
                question,
                "",
            ])
        else:
            prompt_parts.extend([
                "请对上述文件内容进行分析和总结。",
                "",
            ])
        
        prompt_parts.append(
            "请仔细阅读文件内容，并根据用户的问题或要求进行分析和解读。"
        )
        
        return "\n".join(prompt_parts)


__all__ = ["TextAnalysisTool"]

