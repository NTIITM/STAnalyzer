from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from pymongo.errors import DuplicateKeyError
from pydantic import ValidationError

from textmsa.logging_config import get_logger
from textmsa.services.data.user_data_manager_mongodb import (
    UserDataManagerMongoDB,
    get_user_data_manager,
)

logger = get_logger(__name__)


class FileTypeService:
    """集中处理文件类型 CRUD、解析与推断逻辑。"""

    def __init__(self, user_data_manager: Optional[UserDataManagerMongoDB] = None) -> None:
        self.user_data_manager = user_data_manager or get_user_data_manager()

    # ---------- CRUD ----------
    def list_types(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.user_data_manager.list_file_types(category=category)

    def create_type(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            created = self.user_data_manager.create_file_type(payload)
        except (ValueError, ValidationError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"INVALID_FILE_TYPE_PAYLOAD: {exc}",
            ) from exc
        except DuplicateKeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="FILE_TYPE_CONFLICT",
            ) from exc
        return created

    def update_type(self, file_type_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        if not file_type_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="FILE_TYPE_ID_REQUIRED")
        try:
            updated = self.user_data_manager.update_file_type(file_type_id, updates)
        except (ValueError, ValidationError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"INVALID_FILE_TYPE_PAYLOAD: {exc}",
            ) from exc
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FILE_TYPE_NOT_FOUND")
        return updated

    def delete_type(self, file_type_id: str) -> bool:
        if not file_type_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="FILE_TYPE_ID_REQUIRED")
        return self.user_data_manager.delete_file_type(file_type_id)

    def count_type_usage(self, file_type_id: str) -> int:
        if not file_type_id:
            return 0
        return self.user_data_manager.count_files_by_file_type(file_type_id)

    # ---------- 解析 ----------
    def resolve_type(
        self,
        *,
        file_type_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """解析最终 file_type 对象，若无法解析抛 400。"""
        if file_type_id:
            match = self.user_data_manager.get_file_type_by_id(file_type_id)
            if match:
                return self._normalize_file_type_payload(match)
            logger.warning(
                f"file_type id not found: {file_type_id}",
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="FILE_TYPE_NOT_FOUND",
            )

        # TODO: file_type_infer_failure_total metric
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="FILE_TYPE_REQUIRED",
        )

    # ---------- 工具方法 ----------
    @staticmethod
    def build_metadata_block(resolved: Dict[str, Any]) -> Dict[str, Any]:
        """构建可嵌入文件 metadata 的 file_type 对象。"""
        return {
            "id": resolved["file_type_id"],
            "name": resolved["name"],
            "display_name": resolved["display_name"],
            "description": resolved.get("description"),
            "category": resolved.get("category"),
            "extensions": resolved.get("extensions", []),
        }

    def _normalize_file_type_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        file_type_id = payload.get("file_type_id") or payload.get("id")
        if not file_type_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="FILE_TYPE_PAYLOAD_INVALID",
            )
        normalized = {
            "file_type_id": file_type_id,
            "name": payload.get("name"),
            "display_name": payload.get("display_name") or payload.get("name"),
            "description": payload.get("description"),
            "category": payload.get("category"),
            "extensions": payload.get("extensions", []),
        }
        if not normalized["name"] or not normalized["display_name"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="FILE_TYPE_PAYLOAD_INVALID",
            )
        normalized["extensions"] = normalized.get("extensions") or []
        return normalized


_file_type_service: Optional[FileTypeService] = None


def get_file_type_service() -> FileTypeService:
    global _file_type_service
    if _file_type_service is None:
        _file_type_service = FileTypeService()
    return _file_type_service

