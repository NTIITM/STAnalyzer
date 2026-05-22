"""
文件读取工具：支持读取文件内容预览，特别是CSV等数据文件。

该工具允许 agent 主动读取文件内容，帮助 agent 了解生成的文件内容，
从而做出更好的决策。
"""

from __future__ import annotations

import csv
import json
import os
import base64
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from textmsa.logging_config import get_logger
from textmsa.services.file.file_service import get_file_service

logger = get_logger(__name__)


@dataclass
class FileReadResult:
    """文件读取结果"""

    success: bool
    file_id: str
    filename: str
    file_type: str
    file_path: str
    preview: dict[str, Any] | None = None
    error: str | None = None


class FileReaderTool:
    """
    文件读取工具，支持读取文件内容预览

    支持的文件类型：
    - CSV/TSV: 返回前N行数据
    - JSON: 返回JSON结构预览
    - TXT/LOG: 返回文本片段
    - H5AD: 返回AnnData文件的基本信息（细胞数、基因数、空间信息等）
    - 其他: 返回基本信息
    """

    def __init__(
        self,
        *,
        max_csv_rows: int = 10,
        max_text_bytes: int = 2000,
        max_image_bytes: int = 2_000_000,
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
        self._max_image_bytes = max_image_bytes
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
    ) -> FileReadResult:
        """
        读取文件内容预览

        Args:
            file_id: 文件ID
            user_id: 用户ID

        Returns:
            FileReadResult: 文件读取结果
        """
        # 获取文件信息
        file_info = self._file_service.get_file_info(file_id, user_id)
        filename = file_info.get("filename", "unknown")
        file_path = file_info.get("file_path")
        file_ext = os.path.splitext(filename)[1].lower()
        file_type_name = file_ext[1:] if file_ext else "unknown"
        # 根据文件类型读取预览
        preview = self._read_preview(file_path, file_type_name, filename)
        return FileReadResult(
            success=True,
            file_id=file_id,
            filename=filename,
            file_type=file_type_name,
            file_path=file_path,
            preview=preview,
        )


    def read_full_file(
        self,
        *,
        file_id: str,
        user_id: str,
    ) -> FileReadResult:
        """
        读取完整文件内容（用于 full_read_file）

        Args:
            file_id: 文件ID
            user_id: 用户ID

        Returns:
            FileReadResult: 文件读取结果，包含完整文件内容
        """
        try:
            # 获取文件信息
            file_info = self._file_service.get_file_info(file_id, user_id)
            if not file_info:
                return FileReadResult(
                    success=False,
                    file_id=file_id,
                    filename="unknown",
                    file_type="unknown",
                    error="文件不存在",
                )

            filename = file_info.get("filename", "unknown")
            file_path = file_info.get("file_path")
            # 从文件名后缀获取文件类型
            file_ext = os.path.splitext(filename)[1].lower()
            file_type_name = file_ext[1:] if file_ext else "unknown"
            # 根据文件类型读取完整内容
            full_content = self._read_full_content(file_path, file_type_name, filename)

            return FileReadResult(
                success=True,
                file_id=file_id,
                filename=filename,
                file_type=file_type_name,
                preview=full_content,
            )
        except Exception as e:  # noqa: BLE001
            logger.error(
                f"读取完整文件失败: {e}",
                extra={"file_id": file_id, "user_id": user_id},
                exc_info=True,
            )
            return FileReadResult(
                success=False,
                file_id=file_id,
                filename="unknown",
                file_type="unknown",
                error=str(e),
            )

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
        if file_type_lower in ("txt", "log", "text") or file_ext in (
            ".txt",
            ".log",
            ".md",
        ):
            return self._preview_text(file_path)

        # 图片文件（支持 PNG/JPG/JPEG/BMP/GIF/TIFF/WEBP）
        if file_type_lower in (
            "png",
            "jpg",
            "jpeg",
            "bmp",
            "gif",
            "tiff",
            "webp",
        ) or file_ext in (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff", ".webp"):
            return self._preview_image(file_path, filename)

        # H5AD 文件（AnnData格式）
        if file_type_lower == "h5ad" or file_ext == ".h5ad":
            return self._preview_h5ad(file_path)

        # 其他文件类型，返回基本信息
        try:
            file_size = os.path.getsize(file_path)
            return {
                "type": "unknown",
                "filename": filename,
                "size_bytes": file_size,
                "note": "该文件类型暂不支持内容预览",
            }
        except Exception:  # noqa: BLE001
            return {
                "type": "unknown",
                "filename": filename,
                "note": "无法读取文件信息",
            }

    def _preview_csv(self, file_path: str) -> dict[str, Any]:
        """预览CSV文件"""
        rows: list[list[str]] = []
        headers: list[str] = []
        try:
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
        except Exception as e:  # noqa: BLE001
            # 如果CSV解析失败，退回到文本预览
            logger.warning(f"CSV解析失败，使用文本预览: {e}")
            return {
                "type": "csv",
                "error": str(e),
                "text_preview": self._preview_text(file_path).get("snippet", ""),
            }

    def _preview_json(self, file_path: str) -> dict[str, Any]:
        """预览JSON文件"""
        try:
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
        except json.JSONDecodeError as e:
            return {
                "type": "json",
                "error": f"JSON解析失败: {str(e)}",
                "text_preview": self._preview_text(file_path).get("snippet", ""),
            }
        except Exception as e:  # noqa: BLE001
            return {
                "type": "json",
                "error": str(e),
            }

    def _preview_text(self, file_path: str) -> dict[str, Any]:
        """预览文本文件"""
        try:
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
        except Exception as e:  # noqa: BLE001
            return {
                "type": "text",
                "error": str(e),
            }

    def _preview_image(self, file_path: str, filename: str) -> dict[str, Any]:
        """预览图片文件，返回 base64 data URI（截断）"""
        try:
            file_size = os.path.getsize(file_path)
            data = Path(file_path).read_bytes()
            truncated = False
            if len(data) > self._max_image_bytes:
                data = data[: self._max_image_bytes]
                truncated = True
            encoded = base64.b64encode(data).decode("utf-8")
            ext = os.path.splitext(filename)[1].lower().lstrip(".") or "png"
            mime = {
                "png": "image/png",
                "jpg": "image/jpeg",
                "jpeg": "image/jpeg",
                "bmp": "image/bmp",
                "gif": "image/gif",
                "tiff": "image/tiff",
                "webp": "image/webp",
            }.get(ext, "application/octet-stream")
            note = "图片预览（base64 data URI"
            if truncated:
                note += f"，已截断到 {self._max_image_bytes} 字节"
            note += "）"
            return {
                "type": "image",
                "filename": filename,
                "mime": mime,
                "size_bytes": file_size,
                "base64": encoded,
                "note": note,
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "type": "image",
                "filename": filename,
                "error": str(exc),
            }

    def _preview_h5ad(self, file_path: str) -> dict[str, Any]:
        """预览H5AD文件（AnnData格式）"""
        # 使用 extract_h5ad_metadata 获取完整元信息
        metadata = self.extract_h5ad_metadata(file_path)
        
        # 如果提取失败，返回错误信息
        if metadata.get("error"):
            return {
                "type": "h5ad",
                "error": metadata.get("error"),
                "note": metadata.get("note", "无法读取h5ad文件内容"),
            }
        
        # 转换为预览格式
        n_obs = metadata.get("n_spots")
        n_vars = metadata.get("n_genes")
        shape = None
        if n_obs is not None and n_vars is not None:
            shape = [n_obs, n_vars]
        
        # 限制显示数量（用于预览）
        obsm_keys_preview = metadata.get("obsm_keys", [])[:10]
        obs_cols_preview = metadata.get("obs_columns", [])[:10]
        var_cols_preview = metadata.get("var_columns", [])[:10]
        
        result = {
            "type": "h5ad",
            "n_cells": n_obs,
            "n_genes": n_vars,
            "shape": shape,
            "has_spatial": metadata.get("has_spatial", False),
            "obsm_keys": obsm_keys_preview,
            "obs_columns": obs_cols_preview,
            "var_columns": var_cols_preview,
            "size_bytes": metadata.get("size"),
            "note": f"AnnData格式文件，包含 {n_obs} 个细胞/spot 和 {n_vars} 个基因"
            + ("（包含空间信息）" if metadata.get("has_spatial") else ""),
        }
        
        return result

    def extract_h5ad_metadata(self, file_path: str) -> dict[str, Any]:
        """
        提取h5ad文件的元信息（完整信息，不限制数量）
        
        Args:
            file_path: h5ad文件路径
        
        Returns:
            包含元信息的字典，包括：
            - n_spots: 细胞/spot数量
            - n_genes: 基因数量
            - has_spatial: 是否包含空间信息
            - size: 文件大小（字节）
            - obs_columns: obs（细胞/spot）的属性列名列表（完整列表）
            - var_columns: var（基因）的属性列名列表（完整列表）
            - obsm_keys: obsm（多维数组）的键列表（完整列表）
            - uns_keys: uns（非结构化注释）的键列表（完整列表）
            - error: 错误信息（如果有）
            - note: 说明信息（如果有）
        """
        metadata = {
            "n_spots": None,
            "n_genes": None,
            "has_spatial": None,
            "size": None,
            "obs_columns": [],
            "var_columns": [],
            "obsm_keys": [],
            "uns_keys": [],
        }
        
        try:
            import anndata as ad  # type: ignore
        except ImportError:
            logger.warning("anndata库未安装，无法读取h5ad元信息")
            return {
                **metadata,
                "error": "anndata库未安装，无法读取h5ad元信息",
                "note": "请安装anndata库以支持h5ad文件预览",
            }
        
        try:
            # 读取文件大小
            file_size = os.path.getsize(file_path)
            metadata["size"] = file_size
            
            # 读取h5ad文件（只读取元信息，不读取完整数据）
            adata = ad.read_h5ad(file_path, backed="r")  # backed='r' 表示只读模式，节省内存
            
            # 提取基本信息
            metadata["n_spots"] = int(adata.n_obs) if hasattr(adata, "n_obs") else None
            metadata["n_genes"] = int(adata.n_vars) if hasattr(adata, "n_vars") else None
            
            # 提取 obs（细胞/spot）的属性列
            if hasattr(adata, "obs") and adata.obs is not None:
                try:
                    obs_cols = list(adata.obs.columns) if hasattr(adata.obs, "columns") else []
                    metadata["obs_columns"] = obs_cols
                except Exception as e:  # noqa: BLE001
                    logger.warning(f"提取obs列名失败: {e}")
            
            # 提取 var（基因）的属性列
            if hasattr(adata, "var") and adata.var is not None:
                try:
                    var_cols = list(adata.var.columns) if hasattr(adata.var, "columns") else []
                    metadata["var_columns"] = var_cols
                except Exception as e:  # noqa: BLE001
                    logger.warning(f"提取var列名失败: {e}")
            
            # 提取 obsm（多维数组）的键
            if hasattr(adata, "obsm") and adata.obsm is not None:
                try:
                    obsm_keys = list(adata.obsm.keys()) if hasattr(adata.obsm, "keys") else []
                    metadata["obsm_keys"] = obsm_keys
                except Exception as e:  # noqa: BLE001
                    logger.warning(f"提取obsm键失败: {e}")
            
            # 提取 uns（非结构化注释）的键
            if hasattr(adata, "uns") and adata.uns is not None:
                try:
                    uns_keys = list(adata.uns.keys()) if hasattr(adata.uns, "keys") else []
                    metadata["uns_keys"] = uns_keys
                except Exception as e:  # noqa: BLE001
                    logger.warning(f"提取uns键失败: {e}")
            
            # 检查是否有空间信息
            has_spatial = False
            if metadata["obsm_keys"]:
                has_spatial = any("spatial" in str(key).lower() for key in metadata["obsm_keys"])
            
            if not has_spatial and metadata["uns_keys"]:
                has_spatial = any("spatial" in str(key).lower() for key in metadata["uns_keys"])
            
            if not has_spatial and metadata["obs_columns"]:
                spatial_cols = ["x", "y", "x_coord", "y_coord", "spatial_x", "spatial_y"]
                has_spatial = any(col.lower() in spatial_cols for col in metadata["obs_columns"])
            
            metadata["has_spatial"] = has_spatial
            
            logger.info(
                f"成功提取h5ad元信息: n_spots={metadata['n_spots']}, n_genes={metadata['n_genes']}, "
                f"has_spatial={has_spatial}, obs_cols={len(metadata['obs_columns'])}, "
                f"var_cols={len(metadata['var_columns'])}, obsm_keys={len(metadata['obsm_keys'])}, "
                f"uns_keys={len(metadata['uns_keys'])}"
            )
            
            # 关闭文件（backed模式下需要显式关闭）
            try:
                if hasattr(adata, "file") and adata.file is not None:
                    adata.file.close()
            except Exception:  # noqa: BLE001
                pass
            
        except Exception as e:  # noqa: BLE001
            logger.warning(f"读取h5ad元信息失败: {e}", exc_info=True)
            # 如果读取失败，至少保存文件大小
            if metadata["size"] is None:
                try:
                    metadata["size"] = os.path.getsize(file_path)
                except Exception:  # noqa: BLE001
                    pass
            return {
                **metadata,
                "error": str(e),
                "note": "无法读取h5ad文件内容",
            }
        
        return metadata

    def _read_full_content(
        self,
        file_path: str,
        file_type: str,
        filename: str,
    ) -> dict[str, Any]:
        """
        读取完整文件内容（用于 full_read_file）

        Args:
            file_path: 文件路径
            file_type: 文件类型名称
            filename: 文件名

        Returns:
            完整文件内容字典
        """
        file_ext = os.path.splitext(file_path)[1].lower()
        file_type_lower = file_type.lower()

        try:
            # CSV/TSV 文件：读取所有行
            if file_type_lower in ("csv", "tsv") or file_ext in (".csv", ".tsv"):
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
                        rows.append(row)

                return {
                    "type": "csv",
                    "headers": headers,
                    "rows": rows,
                    "total_rows": len(rows),
                    "note": f"完整文件内容（共 {len(rows)} 行，{len(headers)} 列）",
                }

            # JSON 文件：读取完整 JSON
            if file_type_lower == "json" or file_ext == ".json":
                with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
                    content = fh.read()
                    data = json.loads(content)

                return {
                    "type": "json",
                    "content": data,
                    "note": "完整 JSON 文件内容",
                }

            # 文本文件：读取完整文本
            if file_type_lower in ("txt", "log", "text") or file_ext in (
                ".txt",
                ".log",
                ".md",
            ):
                with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
                    content = fh.read()

                return {
                    "type": "text",
                    "content": content,
                    "note": f"完整文本文件内容（共 {len(content)} 个字符）",
                }

            # 图片文件：返回 base64 data URI
            if file_type_lower in (
                "png",
                "jpg",
                "jpeg",
                "bmp",
                "gif",
                "tiff",
                "webp",
            ) or file_ext in (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff", ".webp"):
                return self._preview_image(file_path, filename)

            # H5AD 文件：返回完整信息（与预览相同，因为预览已经包含所有信息）
            if file_type_lower == "h5ad" or file_ext == ".h5ad":
                return self._preview_h5ad(file_path)

            # 其他文件类型：尝试读取为文本
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
                    content = fh.read()
                return {
                    "type": "text",
                    "content": content,
                    "note": f"完整文件内容（共 {len(content)} 个字符）",
                }
            except Exception:
                # 如果无法以文本方式读取，返回文件大小信息
                try:
                    file_size = os.path.getsize(file_path)
                    return {
                        "type": "binary",
                        "size_bytes": file_size,
                        "note": f"二进制文件，无法直接读取内容（大小: {file_size} 字节）",
                    }
                except Exception:
                    return {
                        "type": "unknown",
                        "note": "无法读取文件内容",
                    }
        except Exception as e:  # noqa: BLE001
            logger.error(
                f"读取完整文件内容失败: {e}",
                extra={"file_path": file_path, "file_type": file_type},
                exc_info=True,
            )
            return {
                "type": "error",
                "error": str(e),
                "note": f"读取完整文件内容失败: {str(e)}",
            }

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

    @staticmethod
    def get_file_type_from_path(file_path: str) -> str:
        """
        从文件路径推断文件类型

        Args:
            file_path: 文件路径

        Returns:
            文件类型名称（如 "csv", "json", "txt" 等）
        """
        file_ext = os.path.splitext(file_path)[1].lower()
        if not file_ext:
            return "unknown"

        ext = file_ext[1:]  # 移除点号

        # 映射常见扩展名
        type_map = {
            "csv": "csv",
            "tsv": "tsv",
            "xlsx": "excel",
            "xls": "excel",
            "json": "json",
            "txt": "text",
            "log": "text",
            "md": "text",
            "h5ad": "h5ad",
            "png": "png",
            "jpg": "jpg",
            "jpeg": "jpeg",
            "bmp": "bmp",
            "gif": "gif",
            "tiff": "tiff",
            "webp": "webp",
        }

        return type_map.get(ext, "unknown")

    def read_preview_by_path(
        self,
        file_path: str,
        file_type: str | None = None,
        filename: str | None = None,
    ) -> dict[str, Any]:
        """
        通过文件路径读取文件预览（不依赖 file_id）

        Args:
            file_path: 文件路径
            file_type: 文件类型（如果为 None，则从路径推断）
            filename: 文件名（如果为 None，则从路径提取）

        Returns:
            文件预览字典
        """
        if not file_path or not os.path.exists(file_path):
            return {
                "type": "error",
                "error": "文件路径不存在",
            }

        # 推断文件类型
        if file_type is None:
            file_type = self.get_file_type_from_path(file_path)

        # 提取文件名
        if filename is None:
            filename = os.path.basename(file_path)

        # 读取预览
        return self._read_preview(file_path, file_type, filename)

    def read_full_by_path(
        self,
        file_path: str,
        file_type: str | None = None,
        filename: str | None = None,
    ) -> dict[str, Any]:
        """
        通过文件路径读取完整内容（不依赖 file_id）

        Args:
            file_path: 文件路径
            file_type: 文件类型（如果为 None，则从路径推断）
            filename: 文件名（如果为 None，则从路径提取）

        Returns:
            完整内容字典
        """
        if not file_path or not os.path.exists(file_path):
            return {
                "type": "error",
                "error": "文件路径不存在",
            }

        if file_type is None:
            file_type = self.get_file_type_from_path(file_path)

        if filename is None:
            filename = os.path.basename(file_path)

        return self._read_full_content(file_path, file_type, filename)

    def format_preview(
        self,
        preview: Mapping[str, Any],
        style: str = "default",
    ) -> str:
        """
        格式化文件预览内容，返回易读的字符串。

        Args:
            preview: 文件预览字典
            style: 格式化风格
                - "default": 简单格式（缩进4空格）
                - "detailed": 详细格式（缩进2空格，更详细的信息）
                - "compact": 紧凑格式（单行或少量行）

        Returns:
            格式化的预览字符串
        """
        if not preview:
            return ""

        # 根据 style 选择缩进
        if style == "detailed":
            indent = "  "
            sub_indent = "    "
        elif style == "compact":
            indent = ""
            sub_indent = "  "
        else:  # default
            indent = "     "
            sub_indent = "     "

        lines: list[str] = []
        preview_type = preview.get("type", "unknown")

        # 处理 CSV/TSV 预览
        if preview_type in ("csv", "tsv") and "headers" in preview:
            headers = preview.get("headers", [])
            rows = preview.get("rows", [])
            if headers:
                if style == "detailed":
                    lines.append(f"{indent}列名（共 {len(headers)} 列）：{', '.join(str(h) for h in headers[:10])}")
                    if len(headers) > 10:
                        lines.append(f"{indent}... 还有 {len(headers) - 10} 列")
                else:
                    lines.append(f"{indent}列名: {', '.join(str(h) for h in headers[:10])}")
                    if len(headers) > 10:
                        lines.append(f"{indent}... (还有 {len(headers) - 10} 列)")

            if rows:
                if style == "detailed":
                    lines.append(f"{indent}前 {len(rows)} 行数据预览：")
                    for i, row in enumerate(rows[:5], 1):  # 最多显示5行
                        if isinstance(row, (list, tuple)):
                            # 限制每行显示的长度
                            row_str = ", ".join(str(cell)[:50] for cell in row[:10])
                            if len(row) > 10:
                                row_str += f" ... (还有 {len(row) - 10} 列)"
                            lines.append(f"{sub_indent}第 {i} 行: {row_str}")
                        elif isinstance(row, dict):
                            row_str = str(row)[:200]
                            lines.append(f"{sub_indent}第 {i} 行: {row_str}")
                else:
                    lines.append(f"{indent}前几行数据:")
                    for row in rows[:3]:  # 最多显示3行
                        if isinstance(row, (list, tuple)):
                            lines.append(f"{sub_indent}{row}")
                        elif isinstance(row, dict):
                            lines.append(f"{sub_indent}{row}")

            if "note" in preview:
                lines.append(f"{indent}说明: {preview.get('note')}")

        # 处理 JSON 预览
        elif preview_type == "json" and "structure" in preview:
            structure = preview.get("structure")
            if structure:
                if style == "detailed":
                    try:
                        structure_str = json.dumps(structure, ensure_ascii=False, indent=2)
                        # 限制长度
                        if len(structure_str) > 500:
                            structure_str = structure_str[:500] + "... (已截断)"
                        lines.append(f"{indent}JSON 结构预览：")
                        lines.append(f"{indent}{structure_str}")
                    except Exception:  # noqa: BLE001
                        lines.append(f"{indent}JSON 结构: {str(structure)[:300]}")
                else:
                    lines.append(f"{indent}结构: {structure}")

            if "note" in preview:
                lines.append(f"{indent}说明: {preview.get('note')}")

        # 处理文本预览
        elif preview_type == "text":
            text_content = preview.get("text") or preview.get("snippet", "")
            if text_content:
                if style == "detailed":
                    text_preview = text_content[:500]  # 限制文本长度
                    lines.append(f"{indent}文本内容预览（前 {len(text_preview)} 个字符）：")
                    lines.append(f"{indent}{text_preview}")
                    if preview.get("is_truncated"):
                        lines.append(f"{indent}... (已截断)")
                else:
                    text_preview = text_content[:300]  # 限制文本长度
                    lines.append(f"{indent}文本片段: {text_preview}")

            if "note" in preview:
                lines.append(f"{indent}说明: {preview.get('note')}")

        # 处理 H5AD 文件预览
        elif preview_type == "h5ad":
            # 检查是否有错误
            if "error" in preview:
                lines.append(f"{indent}错误: {preview.get('error')}")
                if "note" in preview:
                    lines.append(f"{indent}说明: {preview.get('note')}")
            else:
                # 基本信息
                if "n_cells" in preview and preview["n_cells"] is not None:
                    lines.append(f"{indent}细胞/Spot数: {preview.get('n_cells')}")
                if "n_genes" in preview and preview["n_genes"] is not None:
                    lines.append(f"{indent}基因数: {preview.get('n_genes')}")
                if "shape" in preview and preview["shape"]:
                    shape = preview.get("shape")
                    if isinstance(shape, (list, tuple)) and len(shape) >= 2:
                        lines.append(f"{indent}数据维度: {shape[0]} × {shape[1]}")

                # 空间信息
                if "has_spatial" in preview:
                    has_spatial = preview.get("has_spatial", False)
                    lines.append(f"{indent}包含空间信息: {'是' if has_spatial else '否'}")

                # obsm键（降维结果、空间坐标等）
                if "obsm_keys" in preview and preview["obsm_keys"]:
                    obsm_keys = preview.get("obsm_keys", [])
                    if obsm_keys:
                        if style == "detailed":
                            keys_str = ", ".join(str(k) for k in obsm_keys[:10])
                            if len(obsm_keys) > 10:
                                keys_str += f" ... (共 {len(obsm_keys)} 个)"
                            lines.append(f"{indent}obsm 键: {keys_str}")
                        else:
                            keys_str = ", ".join(str(k) for k in obsm_keys[:5])  # 最多显示5个
                            if len(obsm_keys) > 5:
                                keys_str += f" ... (共{len(obsm_keys)}个)"
                            lines.append(f"{indent}obsm键: {keys_str}")

                # obs列名
                if "obs_columns" in preview and preview["obs_columns"]:
                    obs_cols = preview.get("obs_columns", [])
                    if obs_cols:
                        if style == "detailed":
                            cols_str = ", ".join(str(c) for c in obs_cols[:10])
                            if len(obs_cols) > 10:
                                cols_str += f" ... (共 {len(obs_cols)} 列)"
                            lines.append(f"{indent}obs 列: {cols_str}")
                        else:
                            cols_str = ", ".join(str(c) for c in obs_cols[:5])  # 最多显示5个
                            if len(obs_cols) > 5:
                                cols_str += f" ... (共{len(obs_cols)}个)"
                            lines.append(f"{indent}obs列: {cols_str}")

                # var列名
                if "var_columns" in preview and preview["var_columns"]:
                    var_cols = preview.get("var_columns", [])
                    if var_cols:
                        if style == "detailed":
                            cols_str = ", ".join(str(c) for c in var_cols[:10])
                            if len(var_cols) > 10:
                                cols_str += f" ... (共 {len(var_cols)} 列)"
                            lines.append(f"{indent}var 列: {cols_str}")
                        else:
                            cols_str = ", ".join(str(c) for c in var_cols[:5])  # 最多显示5个
                            if len(var_cols) > 5:
                                cols_str += f" ... (共{len(var_cols)}个)"
                            lines.append(f"{indent}var列: {cols_str}")

                # 文件大小
                if "size_bytes" in preview and preview["size_bytes"] is not None:
                    size_bytes = preview.get("size_bytes")
                    if size_bytes:
                        # 格式化文件大小
                        if size_bytes < 1024:
                            size_str = f"{size_bytes} B"
                        elif size_bytes < 1024 * 1024:
                            size_str = f"{size_bytes / 1024:.2f} KB"
                        else:
                            size_str = f"{size_bytes / (1024 * 1024):.2f} MB"
                        lines.append(f"{indent}文件大小: {size_str}")

                # 说明文字
                if "note" in preview and preview["note"]:
                    lines.append(f"{indent}说明: {preview.get('note')}")

        # 处理其他格式
        else:
            if "error" in preview:
                lines.append(f"{indent}错误: {preview.get('error')}")
            elif "preview" in preview:
                preview_content = preview.get("preview")
                if preview_content:
                    if isinstance(preview_content, str):
                        lines.append(f"{indent}预览: {preview_content[:300]}")
                    else:
                        lines.append(f"{indent}预览: {str(preview_content)[:300]}")
            elif "note" in preview:
                lines.append(f"{indent}说明: {preview.get('note')}")
            else:
                lines.append(f"{indent}文件类型: {preview_type}")

        return "\n".join(lines) if lines else ""


__all__ = ["FileReadResult", "FileReaderTool"]

