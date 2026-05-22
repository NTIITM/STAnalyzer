"""
文件类型管理 API
"""
from typing import Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Request, Query, status
from fastapi.responses import JSONResponse

from textmsa.logging_config import get_logger
from textmsa.services.auth.auth_service import get_current_user_from_header
from textmsa.services.file.file_type_service import get_file_type_service
from textmsa.services.api.schemas import (
    FileTypeListResponse,
    FileTypeResponse,
    FileTypeCreateRequest,
    FileTypeUpdateRequest,
)

logger = get_logger(__name__)

file_type_router = APIRouter(prefix="/api/file-types", tags=["文件类型"])


async def _require_user(request: Request) -> str:
    """解析并确保用户已登录"""
    user_info = await get_current_user_from_header(request=request)
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未授权，请先登录",
        )
    return user_info["user_id"]


def _to_response_model(payload: Dict[str, Any]) -> FileTypeResponse:
    """将底层字典转换为响应模型"""
    normalized = payload.copy()
    file_type_id = normalized.get("file_type_id") or normalized.get("id")
    normalized.setdefault("file_type_id", file_type_id)
    normalized.setdefault("id", file_type_id)
    return FileTypeResponse(**normalized)


@file_type_router.get("", response_model=FileTypeListResponse)
async def list_file_types(
    request: Request,
    category: Optional[str] = Query(None, description="根据分类过滤文件类型"),
):
    """列出文件类型"""
    await _require_user(request)
    file_type_service = get_file_type_service()
    items = file_type_service.list_types(category=category)
    response_data = FileTypeListResponse(
        items=[_to_response_model(item) for item in items],
        total=len(items),
    )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "code": 200,
            "message": "success",
            "data": response_data.model_dump(),
        },
    )


@file_type_router.post("", response_model=FileTypeResponse)
async def create_file_type(request: Request, payload: FileTypeCreateRequest):
    """创建新的文件类型"""
    user_id = await _require_user(request)
    # TODO: 仅允许管理员创建全局文件类型
    file_type_service = get_file_type_service()
    created = file_type_service.create_type(payload.model_dump(exclude_none=True))
    logger.info(
        "file_type created via API",
        extra={"file_type_id": created.get("file_type_id"), "user_id": user_id},
    )
    response_data = _to_response_model(created)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "code": 200,
            "message": "success",
            "data": response_data.model_dump(),
        },
    )


@file_type_router.put("/{file_type_id}", response_model=FileTypeResponse)
async def update_file_type(
    file_type_id: str,
    request: Request,
    payload: FileTypeUpdateRequest,
):
    """更新文件类型"""
    user_id = await _require_user(request)
    # TODO: 仅允许管理员更新全局文件类型
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="EMPTY_UPDATE_PAYLOAD",
        )
    file_type_service = get_file_type_service()
    updated = file_type_service.update_type(file_type_id, updates)
    logger.info(
        "file_type updated via API",
        extra={"file_type_id": file_type_id, "user_id": user_id},
    )
    response_data = _to_response_model(updated)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "code": 200,
            "message": "success",
            "data": response_data.model_dump(),
        },
    )


@file_type_router.delete("/{file_type_id}")
async def delete_file_type(file_type_id: str, request: Request):
    """删除文件类型（需确保未被引用）"""
    user_id = await _require_user(request)
    # TODO: 仅允许管理员删除文件类型
    file_type_service = get_file_type_service()
    usage = file_type_service.count_type_usage(file_type_id)
    if usage > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="FILE_TYPE_IN_USE",
        )
    deleted = file_type_service.delete_type(file_type_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="FILE_TYPE_NOT_FOUND",
        )
    logger.info(
        "file_type deleted via API",
        extra={"file_type_id": file_type_id, "user_id": user_id},
    )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "code": 200,
            "message": "success",
            "data": {
                "file_type_id": file_type_id,
                "deleted": True,
            },
        },
    )

