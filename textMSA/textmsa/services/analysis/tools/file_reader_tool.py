"""
文件读取工具：支持读取文件内容预览。

该工具基于 langgraph 框架实现，独立于旧工具。
"""

from __future__ import annotations

import csv
import json
import os
from typing import Any

from textmsa.logging_config import get_logger
from textmsa.services.file.file_service import get_file_service

logger = get_logger(__name__)


class FileReaderTool:
    """
    文件读取工具，支持读取文件内容预览
    
    支持的文件类型：
    - CSV/TSV: 返回前N行数据
    - JSON: 返回JSON结构预览
    - TXT/LOG/MD: 返回文本片段
    - H5AD: 返回AnnData文件的基本信息
    - 其他: 返回基本信息
    
    注意：不使用 try-catch，异常直接向上抛出。
    """

    def __init__(
        self,
        *,
        max_csv_rows: int = 10,
        max_text_bytes: int = 2000,
        max_json_depth: int = 3,
    ) -> None:
        """
        初始化文件读取工具
        
        Args:
            max_csv_rows: CSV文件最大预览行数
            max_text_bytes: 文本文件最大预览字节数
            max_json_depth: JSON文件最大预览深度
        """
        self._max_csv_rows = max_csv_rows
        self._max_text_bytes = max_text_bytes
        self._max_json_depth = max_json_depth
        self._file_service = get_file_service()

        logger.info(
            "FileReaderTool initialized",
            extra={
                "max_csv_rows": max_csv_rows,
                "max_text_bytes": max_text_bytes,
                "max_json_depth": max_json_depth,
            },
        )

    def read_file(
        self,
        *,
        file_id: str,
        user_id: str,
    ) -> str:
        """
        读取文件内容预览并返回字符串
        
        Args:
            file_id: 文件ID
            user_id: 用户ID
        
        Returns:
            文件内容字符串（JSON格式或文本格式）
            
        Raises:
            Exception: 如果读取失败，直接抛出异常（不捕获）
        """
        # 获取文件信息（如果失败，file_service 会抛出异常）
        file_info = self._file_service.get_file_info(file_id, user_id)
        filename = file_info.get("filename", "unknown")
        file_path = file_info.get("file_path")
        file_ext = os.path.splitext(filename)[1].lower()
        file_type_name = file_ext[1:] if file_ext else "unknown"
        
        # 根据文件类型读取预览
        preview = self._read_preview(file_path, file_type_name, filename)
        
        # 将预览转换为字符串
        return json.dumps(preview, ensure_ascii=False, indent=2)

    def _read_preview(
        self,
        file_path: str,
        file_type: str,
        filename: str,
    ) -> dict[str, Any]:
        """
        根据文件类型读取预览内容
        
        Args:
            file_path: 文件路径
            file_type: 文件类型名称
            filename: 文件名
        
        Returns:
            预览内容字典
        """
        file_ext = os.path.splitext(file_path)[1].lower()
        file_type_lower = file_type.lower()

        # CSV/TSV 文件
        if file_type_lower in ("csv", "tsv") or file_ext in (".csv", ".tsv"):
            return self._preview_csv(file_path)

        # JSON 文件
        if file_type_lower == "json" or file_ext == ".json":
            return self._preview_json(file_path)

        # 文本文件
        if file_type_lower in ("txt", "log", "text", "md") or file_ext in (
            ".txt",
            ".log",
            ".md",
        ):
            return self._preview_text(file_path)

        # H5AD 文件（AnnData格式）
        if file_type_lower == "h5ad" or file_ext == ".h5ad":
            return self._preview_h5ad(file_path)

        # 其他文件类型，返回基本信息
        file_size = os.path.getsize(file_path)
        return {
            "type": "unknown",
            "filename": filename,
            "size_bytes": file_size,
            "note": "该文件类型暂不支持内容预览",
        }

    def _preview_csv(self, file_path: str) -> dict[str, Any]:
        """预览CSV文件"""
        rows: list[list[str]] = []
        headers: list[str] = []
        with open(file_path, newline="", encoding="utf-8", errors="replace") as fh:
            # 尝试检测分隔符
            sample = fh.read(1024)
            fh.seek(0)
            delimiter = "," if sample.count(",") > sample.count("\t") else "\t"

            reader = csv.reader(fh, delimiter=delimiter)
            for i, row in enumerate(reader):
                if i == 0:
                    headers = row
                if i >= self._max_csv_rows:
                    break
                rows.append(row)

        return {
            "type": "csv",
            "headers": headers,
            "rows": rows,
            "row_count_preview": len(rows),
            "note": f"显示前 {len(rows)} 行（共 {len(headers)} 列）",
        }

    def _preview_json(self, file_path: str) -> dict[str, Any]:
        """预览JSON文件"""
        with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
            content = fh.read(self._max_text_bytes)
            data = json.loads(content)

        # 简化JSON结构（限制深度）
        simplified = self._simplify_json(data, max_depth=self._max_json_depth)

        return {
            "type": "json",
            "structure": simplified,
            "note": "JSON结构预览（已简化）",
        }

    def _preview_text(self, file_path: str) -> dict[str, Any]:
        """预览文本文件"""
        with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
            snippet = fh.read(self._max_text_bytes)
            is_truncated = len(snippet) == self._max_text_bytes

        return {
            "type": "text",
            "snippet": snippet,
            "is_truncated": is_truncated,
            "note": f"显示前 {len(snippet)} 个字符"
            + ("（已截断）" if is_truncated else ""),
        }

    def _preview_h5ad(self, file_path: str) -> dict[str, Any]:
        """预览H5AD文件（AnnData格式）"""
        try:
            import anndata as ad  # type: ignore
        except ImportError:
            return {
                "type": "h5ad",
                "error": "anndata库未安装，无法读取h5ad文件",
                "note": "请安装anndata库以支持h5ad文件预览",
            }

        # 使用backed='r'模式以节省内存，只读取元信息
        adata = ad.read_h5ad(file_path, backed="r")

        # 提取基本信息
        n_obs = int(adata.n_obs) if hasattr(adata, "n_obs") else None
        n_vars = int(adata.n_vars) if hasattr(adata, "n_vars") else None
        shape = [int(adata.shape[0]), int(adata.shape[1])] if hasattr(adata, "shape") else None

        # 获取文件大小
        try:
            file_size = os.path.getsize(file_path)
        except Exception:
            file_size = None

        result = {
            "type": "h5ad",
            "n_cells": n_obs,
            "n_genes": n_vars,
            "shape": shape,
            "size_bytes": file_size,
            "note": f"AnnData格式文件，包含 {n_obs} 个细胞/spot 和 {n_vars} 个基因",
        }

        # 关闭文件（backed模式下需要显式关闭）
        try:
            if hasattr(adata, "file") and adata.file is not None:
                adata.file.close()
        except Exception:
            pass

        return result

    def _simplify_json(
        self,
        data: Any,
        max_depth: int,
        current_depth: int = 0,
    ) -> Any:
        """简化JSON结构，限制深度"""
        if current_depth >= max_depth:
            if isinstance(data, dict):
                return f"{{...}} ({len(data)} keys)"
            if isinstance(data, list):
                return f"[...] ({len(data)} items)"
            return str(type(data).__name__)

        if isinstance(data, dict):
            return {
                k: self._simplify_json(v, max_depth, current_depth + 1)
                for k, v in list(data.items())[:10]  # 限制键数量
            }
        if isinstance(data, list):
            return [
                self._simplify_json(item, max_depth, current_depth + 1)
                for item in data[:10]  # 限制列表长度
            ]
        return data


__all__ = ["FileReaderTool"]

