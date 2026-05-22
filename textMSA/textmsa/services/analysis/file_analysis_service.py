"""
文件智能分析服务

该服务根据文件类型自动路由到相应的分析工具。
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from pathlib import Path
from typing import Any, Callable, Optional

from textmsa.logging_config import get_logger
from textmsa.services.file.file_service import get_file_service
from textmsa.services.analysis.tools.file_reader_tool import FileReaderTool
from textmsa.services.analysis.tools.text_analysis_tool import TextAnalysisTool
from textmsa.services.analysis.tools.data_analysis_tool import DataAnalysisTool
from textmsa.services.analysis.tools.image_analysis_tool import ImageAnalysisTool
# from textmsa.services.agent.h5ad_agent import run_h5ad_agent
from textmsa.services.agent.file_analysis_agent import (
    astream_file_analysis_agent,
    run_file_analysis_agent,
)

logger = get_logger(__name__)


class FileAnalysisService:
    """
    文件智能分析服务
    
    根据文件类型自动路由到相应的分析工具：
    - 文本文件（txt, log, md, json）：使用 TextAnalysisTool
    - H5AD 文件（h5ad）：使用 H5AD Agent 进行智能分析
    - 数据文件（csv, excel）：使用 DataAnalysisTool
    - 图片文件（png, jpg, jpeg等）：使用 ImageAnalysisTool
    - 其他文件：使用 FileReaderTool 默认预览
    
    注意：不使用 try-catch，异常直接向上抛出。
    """
    
    # 文件类型路由映射
    TEXT_TYPES = {"txt", "log", "md", "json"}
    H5AD_TYPE = "h5ad"  # H5AD 文件单独处理
    DATA_TYPES = {"csv", "excel", "xlsx"}  # 移除 h5ad，单独处理
    IMAGE_TYPES = {"png", "jpg", "jpeg", "bmp", "gif", "tiff", "webp"}

    def __init__(self) -> None:
        """初始化文件分析服务"""
        self._file_service = get_file_service()
        
        # 初始化工具实例
        self._file_reader_tool = FileReaderTool()
        self._text_analysis_tool = TextAnalysisTool()
        self._data_analysis_tool = DataAnalysisTool()
        self._image_analysis_tool = ImageAnalysisTool()
        
        logger.info("FileAnalysisService initialized")

    # def analyze_file(
    #     self,
    #     *,
    #     file_id: str,
    #     user_id: str,
    #     query: str = "",
    # ) -> str:
    #     """
    #     分析文件并返回结果
        
    #     Args:
    #         file_id: 文件ID
    #         user_id: 用户ID
    #         query: 用户查询/问题（可选，用于指导分析）
    #         **kwargs: 其他可选参数
        
    #     Returns:
    #         分析结果内容字符串
            
    #     Raises:
    #         Exception: 如果分析失败，直接抛出异常（不捕获，由 API 层处理）
    #     """
    #     # 获取文件信息（如果失败，file_service 会抛出异常）
    #     file_info = self._file_service.get_file_info(file_id, user_id)
    #     filename = file_info.get("filename", "unknown")
        
    #     # 检测文件类型
    #     file_type = self._detect_file_type(filename)
        
    #     logger.info(
    #         "Analyzing file",
    #         extra={
    #             "file_id": file_id,
    #             "file_name": filename,
    #             "file_type": file_type,
    #         },
    #     )
        
    #     # 根据文件类型路由到相应工具
    #     if file_type in self.TEXT_TYPES:
    #         # 文本文件：使用 LLM 解读
    #         result = self._text_analysis_tool.analyze(
    #             file_id=file_id,
    #             user_id=user_id,
    #             question=query,
    #         )
    #     elif file_type == self.H5AD_TYPE:
    #         # H5AD 文件：使用 H5AD Agent 进行智能分析

    #         file_path = file_info.get("file_path")
    #         agent_result = run_h5ad_agent(
    #             user_query=query,
    #             h5ad_file_path=file_path,
    #         )            
    #         # 提取最终答案
    #         result = agent_result.get("final_answer")
    #         if not result:
    #             result = agent_result.get("error_message")
    #         if not result:
    #             raise ValueError("H5AD Agent 分析失败")

    #     elif file_type in self.DATA_TYPES:
    #         # 数据文件：通过 PythonREPL 工具分析
    #         result = self._data_analysis_tool.analyze(
    #             question=query or "请分析这个数据文件的基本信息和内容。",
    #             file_id=file_id,
    #             user_id=user_id,
    #         )
    #     elif file_type in self.IMAGE_TYPES:
    #         # 图片文件：通过多模态模型解读
    #         result = self._image_analysis_tool.analyze(
    #             file_id=file_id,
    #             user_id=user_id,
    #             question=query,
    #         )
    #     else:
    #         # 其他文件类型：使用 FileReaderTool 默认预览
    #         result = self._file_reader_tool.read_file(
    #             file_id=file_id,
    #             user_id=user_id,
    #         )
        
    #     return result

    def analyze_file(
        self,
        *,
        file_id: str,
        user_id: str,
        query: str = "",
    ) -> str:
        """
        分析文件并返回结果（JSON序列化）
        
        使用 File Read Agent 进行文件分析。
        
        Args:
            file_id: 文件ID
            user_id: 用户ID
            query: 用户查询/问题（可选，用于指导分析）
        
        Returns:
            JSON序列化的分析结果字符串
        
        Raises:
            Exception: 如果分析失败，直接抛出异常（不捕获，由 API 层处理）
        """
        # 获取文件信息（如果失败，file_service 会抛出异常）
        file_info = self._file_service.get_file_info(file_id, user_id)
        filename = file_info.get("filename", "unknown")
        file_path = file_info.get("file_path")
        
        logger.info(
            "Analyzing file with File Read Agent",
            extra={
                "file_id": file_id,
                "file_name": filename,
                "user_query": query,
            },
        )
        
        # 读取文件预览
        file_ext = os.path.splitext(filename)[1].lower()
        file_type_name = file_ext[1:] if file_ext else "unknown"
        preview = self._file_reader_tool._read_preview(file_path, file_type_name, filename)
        
        # 构建 read_results 字典
        read_results = {
            "file_id": file_id,
            "file_name": filename,
            "file_path": file_path,
            "file_type": file_type_name,
            "preview": preview,
        }
        
        # 创建临时工作目录（主目录下 tmp+uuid）
        base_dir = Path(os.getcwd())  # 主目录（当前工作目录）
        work_dir_name = f"tmp{uuid.uuid4().hex}"
        work_dir_path = str(base_dir / work_dir_name)
        
        logger.info(
            "Created work directory for File Read Agent",
            extra={
                "work_dir_path": work_dir_path,
            },
        )
        
        # 调用 File Read Agent
        agent_result = run_file_analysis_agent(
            user_query=query or "请分析这个文件的基本信息和内容。",
            read_results=read_results,
            work_dir_path=work_dir_path,
        )
        
        logger.info(
            "File Read Agent completed",
            extra={
                "has_final_answer": bool(agent_result.get("final_answer")),
                "generated_files_count": len(agent_result.get("generated_files_info", [])),
            },
        )
        
        # 返回 JSON 序列化的结果
        return json.dumps(agent_result, ensure_ascii=False, indent=2)

    async def analyze_file_async(
        self,
        *,
        file_id: str,
        user_id: str,
        query: str = "",
        progress_cb: Optional[Callable[[dict], None]] = None,
    ) -> None:
        """
        异步分析文件并返回结果，支持进度回调
        """

        def emit(progress: dict) -> None:
            if not progress_cb:
                return
            try:
                progress_cb(progress)
            except Exception:
                logger.exception("progress_cb failed")

        emit({"message": "file preview"})

        file_info = await asyncio.to_thread(self._file_service.get_file_info, file_id, user_id)
        filename = file_info.get("filename", "unknown")
        file_path = file_info.get("file_path")

        file_ext = os.path.splitext(filename)[1].lower()
        file_type_name = file_ext[1:] if file_ext else "unknown"

        preview = await asyncio.to_thread(
            self._file_reader_tool._read_preview,  # type: ignore[attr-defined]
            file_path,
            file_type_name,
            filename,
        )
        emit({"message": "file preview finished"})

        base_dir = Path(os.getcwd())
        work_dir_name = f"tmp{uuid.uuid4().hex}"
        work_dir_path = str(base_dir / work_dir_name)

        emit({"message": "file analysis agent started"})

        await astream_file_analysis_agent(
            query or "请分析这个文件的基本信息和内容。",
            {
                "file_id": file_id,
                "file_name": filename,
                "file_path": file_path,
                "file_type": file_type_name,
                "preview": preview,
            },
            work_dir_path,
            on_event=emit,
        )
        emit({"message": "file analysis agent finished"})

    def _detect_file_type(self, filename: str) -> str:
        """
        从文件名提取文件类型
        
        Args:
            filename: 文件名
        
        Returns:
            文件类型（扩展名，小写）
        """
        parts = filename.lower().split(".")
        return parts[-1] if len(parts) > 1 else "unknown"

    async def analyze_file_async(
        self,
        *,
        file_id: str,
        user_id: str,
        query: str = "",
        progress_cb: Optional[Callable[[dict], None]] = None,
    ) -> None:
        """
        异步分析文件并返回结果，支持进度回调
        """

        def emit(progress: dict) -> None:
            if not progress_cb:
                return
            try:
                progress_cb(progress)
            except Exception:
                logger.exception("progress_cb failed")

        emit({"message": "file preview"})

        file_info = await asyncio.to_thread(self._file_service.get_file_info, file_id, user_id)
        filename = file_info.get("filename", "unknown")
        file_path = file_info.get("file_path")

        file_ext = os.path.splitext(filename)[1].lower()
        file_type_name = file_ext[1:] if file_ext else "unknown"

        preview = await asyncio.to_thread(
            self._file_reader_tool._read_preview,  # type: ignore[attr-defined]
            file_path,
            file_type_name,
            filename,
        )
        emit({"message": "file preview finished"})

        base_dir = Path(os.getcwd())
        work_dir_name = f"tmp{uuid.uuid4().hex}"
        work_dir_path = str(base_dir / work_dir_name)

        emit({"message": "file analysis agent started"})

        await astream_file_analysis_agent(
            query or "请分析这个文件的基本信息和内容。",
            {
                "file_id": file_id,
                "file_name": filename,
                "file_path": file_path,
                "file_type": file_type_name,
                "preview": preview,
            },
            work_dir_path,
            on_event=emit,
        )
        emit({"message": "file analysis agent finished"})

    def _detect_file_type(self, filename: str) -> str:
        """
        从文件名提取文件类型
        
        Args:
            filename: 文件名
        
        Returns:
            文件类型（扩展名，小写）
        """
        parts = filename.lower().split(".")
        return parts[-1] if len(parts) > 1 else "unknown"



# 全局服务实例
_file_analysis_service: FileAnalysisService | None = None


def get_file_analysis_service() -> FileAnalysisService:
    """获取全局文件分析服务实例"""
    global _file_analysis_service
    if _file_analysis_service is None:
        _file_analysis_service = FileAnalysisService()
    return _file_analysis_service


__all__ = ["FileAnalysisService", "get_file_analysis_service"]

