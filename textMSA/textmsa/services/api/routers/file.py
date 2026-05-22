"""
文件API路由
"""
import os
from typing import Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, status, Request, Query, Form, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from pathlib import Path
from textmsa.logging_config import get_logger
from textmsa.services.auth.auth_service import get_current_user_from_header
from textmsa.services.file.file_service import get_file_service
from textmsa.services.project.project_service import get_project_service
from textmsa.services.api.schemas import (
    FileUploadResponse,
    FileListResponse,
    FileDetailResponse,
    FileDeleteResponse,
    FileUpdateRequest,
    FileUpdateResponse,
    FileInfoItem
)

logger = get_logger(__name__)

# 创建路由
file_router = APIRouter(prefix="/api/file", tags=["文件管理"])


@file_router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    project_id: Optional[str] = Query(
        None,
        alias="projectId",
        description="项目ID（可选，如果提供，上传后自动添加到项目）",
    ),
    file_type_id: str = Form(
        ...,
        alias="fileTypeId",
        description="文件类型ID（必填）",
    ),
):
    """
    上传文件
    - **file**: 文件对象（multipart/form-data）
    - **project_id**: 项目ID（可选，如果提供，上传后自动添加到项目）
    - **file_type_id**: 文件类型ID（必填）
    
    注意：文件tags由后端自动维护，用户无法在上传时指定tags
    
    需要提供Authorization头或token头
    """
    try:
        # 获取当前用户
        user_info = await get_current_user_from_header(request=request)
        
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录"
            )
        
        user_id = user_info["user_id"]
        
        # 验证文件
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="文件名不能为空"
            )
        
        # 上传文件（如果提供了 project_id，会自动添加到项目）
        file_service = get_file_service()
        result = file_service.upload_file(
            file,
            user_id,
            project_id=project_id,
            file_type_id=file_type_id,
        )
        
        # 使用 Pydantic 模型确保字段名转换
        response_data = FileUploadResponse(**result)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "上传成功",
                "data": response_data.model_dump()  # 使用蛇形命名输出
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"文件上传失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"文件上传失败: {str(e)}"
        )


@file_router.get("/list", response_model=FileListResponse)
async def get_file_list(
    request: Request,
    project_id: Optional[str] = Query(
        None,
        alias="projectId",
        description="项目ID（可选，只返回该项目内的文件）",
    ),
):
    """
    获取文件列表
    
    需要提供Authorization头或token头
    """
    try:
        # 获取当前用户
        user_info = await get_current_user_from_header(request=request)
        
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录"
            )
        
        user_id = user_info["user_id"]
        
        # 开发模式：解析测试用户ID
        from textmsa.services.auth.auth_service import resolve_test_user_id
        user_id = resolve_test_user_id(user_id)
        
        logger.debug(f"获取文件列表，user_id: {user_id}, project_id: {project_id}")
        
        # 获取文件列表
        file_service = get_file_service()
        files = file_service.get_file_list(user_id)

        # 仅保留已上传或已完成的文件
        files = [f for f in files if f.get("status") in {"uploaded", "completed"}]

        # 如果提供了项目ID，则只返回属于该项目的文件
        if project_id:
            project_service = get_project_service()
            project_file_ids = set(
                project_service.get_project_files(project_id=project_id, user_id=user_id)
            )
            files = [f for f in files if f.get("file_id") in project_file_ids]
        
        logger.debug(f"获取到 {len(files)} 个文件")
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "success",
                "data": files
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取文件列表失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取文件列表失败"
        )


@file_router.get("/{file_id}", response_model=FileDetailResponse)
async def get_file_info(
    file_id: str,
    request: Request
):
    """
    获取文件详情
    
    - **file_id**: 文件ID
    
    需要提供Authorization头或token头
    """
    try:
        # 获取当前用户
        user_info = await get_current_user_from_header(request=request)
        
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录"
            )
        
        user_id = user_info["user_id"]
        
        # 获取文件信息
        file_service = get_file_service()
        file_info = file_service.get_file_info(file_id, user_id)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "success",
                "data": file_info
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取文件信息失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取文件信息失败"
        )


@file_router.put("/{file_id}", response_model=FileUpdateResponse)
async def update_file_info(
    file_id: str,
    request: Request,
    update_data: FileUpdateRequest
):
    """
    更新文件信息
    
    - **file_id**: 文件ID
    - **update_data**: 更新数据（name和/或description）
    
    需要提供Authorization头或token头
    """
    try:
        # 获取当前用户
        user_info = await get_current_user_from_header(request=request)
        
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录"
            )
        
        user_id = user_info["user_id"]
        
        # 更新文件信息（注意：tags只能由后端维护，用户不能修改）
        file_service = get_file_service()
        result = file_service.update_file_info(
            file_id=file_id,
            user_id=user_id,
            filename=update_data.name,
            description=update_data.description
        )
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "success",
                "data": result
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新文件信息失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新文件信息失败"
        )


@file_router.delete("/{file_id}", response_model=FileDeleteResponse)
async def delete_file(
    file_id: str,
    request: Request,
    project_id: Optional[str] = Query(
        None,
        alias="projectId",
        description="限定删除范围的项目ID（可选）",
    ),
):
    """
    删除文件
    
    - **file_id**: 文件ID
    - **project_id**: 限定删除的项目ID（可选）
    
    需要提供Authorization头或token头
    """
    try:
        # 获取当前用户
        user_info = await get_current_user_from_header(request=request)
        
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录"
            )
        
        user_id = user_info["user_id"]
        
        # 删除文件
        file_service = get_file_service()
        deletion_result = file_service.delete_file(file_id, user_id, project_id=project_id)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "success",
                "data": deletion_result
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除文件失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除文件失败"
        )


@file_router.delete("/{file_id}/children", response_model=FileDeleteResponse)
async def delete_file_children(
    file_id: str,
    request: Request,
    project_id: Optional[str] = Query(
        None,
        alias="projectId",
        description="限定删除范围的项目ID（可选）",
    ),
):
    """
    递归删除指定文件的所有子文件（不删除自身）
    
    - **file_id**: 文件ID
    - **project_id**: 限定删除的项目ID（可选）
    
    需要提供Authorization头或token头
    """
    try:
        user_info = await get_current_user_from_header(request=request)
        
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录"
            )
        
        user_id = user_info["user_id"]
        
        file_service = get_file_service()
        deletion_result = file_service.delete_file_children(
            file_id=file_id,
            user_id=user_id,
            project_id=project_id,
        )
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "success",
                "data": deletion_result
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除子文件失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除子文件失败"
        )

@file_router.get("/download/{file_id}")
async def download_file(
    file_id: str,
    request: Request
):
    """
    下载文件（返回二进制流）
    
    - **file_id**: 文件ID
    
    需要提供Authorization头或token头
    """
    try:
        user_info = await get_current_user_from_header(request=request)
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录"
            )

        user_id = user_info["user_id"]

        file_service = get_file_service()
        file_info = file_service.get_file_info(file_id, user_id)
        file_path = file_info.get("file_path")

        if not file_path or not os.path.exists(file_path):
            logger.error(f"文件路径不存在: file_id={file_id}, path={file_path}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文件不存在或已被删除"
            )

        filename = file_info.get("filename") or f"{file_id}"

        # 根据文件扩展名设置正确的 media_type
        if file_path:
            file_ext = os.path.splitext(file_path)[1].lower()
            if file_ext == ".png":
                media_type = "image/png"
            elif file_ext in [".jpg", ".jpeg"]:
                media_type = "image/jpeg"
            elif file_ext == ".gif":
                media_type = "image/gif"
            elif file_ext == ".webp":
                media_type = "image/webp"
            elif file_ext == ".svg":
                media_type = "image/svg+xml"
            elif file_ext == ".csv":
                media_type = "text/csv"
            elif file_ext == ".tsv":
                media_type = "text/tab-separated-values"
            elif file_ext == ".h5ad":
                media_type = "application/octet-stream"  # h5ad 文件保持二进制流
            elif file_ext in [".pdf"]:
                media_type = "application/pdf"
            elif file_ext in [".json"]:
                media_type = "application/json"
            elif file_ext in [".txt", ".log"]:
                media_type = "text/plain"
            else:
                media_type = "application/octet-stream"
        else:
            media_type = "application/octet-stream"

        return FileResponse(
            path=file_path,
            filename=filename,
            media_type=media_type
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"下载文件失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"下载文件失败: {str(e)}"
        )


def cleanup_temp_file(file_path: str):
    """清理临时文件的后台任务"""
    try:
        if os.path.exists(file_path):
            os.unlink(file_path)
            logger.debug(f"已删除临时文件: {file_path}")
    except Exception as e:
        logger.error(f"删除临时文件失败: {file_path}, 错误: {e}")


@file_router.get("/preview/{file_id}")
async def preview_file(
    file_id: str,
    request: Request,
    background_tasks: BackgroundTasks
):
    """
    预览文件（返回二进制流）
    
    对于 CSV/TSV 等表格文件，仅返回前 300 行
    对于其他文件类型，与下载接口行为相同
    
    - **file_id**: 文件ID
    
    需要提供Authorization头或token头
    """
    try:
        user_info = await get_current_user_from_header(request=request)
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录"
            )
        user_id = user_info["user_id"]

        file_service = get_file_service()
        file_info = file_service.get_file_info(file_id, user_id)
        file_path = file_info.get("file_path")

        if not file_path or not os.path.exists(file_path):
            logger.error(f"文件路径不存在: file_id={file_id}, path={file_path}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文件不存在或已被删除"
            )

        filename = file_info.get("filename") or f"{file_id}"
        file_ext = os.path.splitext(file_path)[1].lower()

        # 根据文件扩展名设置正确的 media_type
        if file_ext == ".png":
            media_type = "image/png"
        elif file_ext in [".jpg", ".jpeg"]:
            media_type = "image/jpeg"
        elif file_ext == ".gif":
            media_type = "image/gif"
        elif file_ext == ".webp":
            media_type = "image/webp"
        elif file_ext == ".svg":
            media_type = "image/svg+xml"
        elif file_ext == ".csv":
            media_type = "text/csv"
        elif file_ext == ".tsv":
            media_type = "text/tab-separated-values"
        elif file_ext == ".h5ad":
            media_type = "application/octet-stream"
        elif file_ext in [".pdf"]:
            media_type = "application/pdf"
        elif file_ext in [".json"]:
            media_type = "application/json"
        elif file_ext in [".txt", ".log"]:
            media_type = "text/plain"
        else:
            media_type = "application/octet-stream"

        # 对于 CSV/TSV 文件，只返回前 300 行
        if file_ext in [".csv", ".tsv"]:
            import tempfile
            import csv
            
            # 检测分隔符
            delimiter = ',' if file_ext == ".csv" else '\t'
            
            # 创建临时文件存储预览内容
            temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=file_ext, encoding='utf-8')
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f, delimiter=delimiter)
                    writer = csv.writer(temp_file, delimiter=delimiter)
                    
                    # 只读取前 300 行
                    for i, row in enumerate(reader):
                        if i >= 300:
                            break
                        writer.writerow(row)
                
                temp_file.close()
                
                # 添加后台任务来删除临时文件
                background_tasks.add_task(cleanup_temp_file, temp_file.name)
                
                # 返回临时文件
                return FileResponse(
                    path=temp_file.name,
                    filename=filename,
                    media_type=media_type
                )
            except Exception as e:
                # 如果出错，确保删除临时文件
                if os.path.exists(temp_file.name):
                    os.unlink(temp_file.name)
                raise e
        else:
            # 其他文件类型直接返回完整文件
            return FileResponse(
                path=file_path,
                filename=filename,
                media_type=media_type
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"预览文件失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"预览文件失败: {str(e)}"
        )
