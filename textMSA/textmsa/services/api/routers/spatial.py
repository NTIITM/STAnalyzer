"""
空间转录组数据API路由（单切片模式）
"""
from fastapi import APIRouter, HTTPException, status, Request, Query
from fastapi.responses import JSONResponse
from typing import Optional, List

from textmsa.logging_config import get_logger
from textmsa.services.auth.auth_service import get_current_user_from_header
from textmsa.services.spatial.spatial_service import get_spatial_service
from textmsa.services.api.schemas import (
    GetSliceImageResponse,
    GetSpotsResponse
)

logger = get_logger(__name__)

# 创建路由
spatial_router = APIRouter(prefix="/api/spatial", tags=["空间转录组数据"])


@spatial_router.get("/{fileId}/image", response_model=GetSliceImageResponse)
async def get_slice_image(
    fileId: str,
    request: Request
):
    """
    获取文件的切片图像URL（单切片模式）
    
    - **fileId**: 文件ID
    
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
        
        # 获取切片图像
        spatial_service = get_spatial_service()
        image_info = spatial_service.get_slice_image(fileId, user_id)
        
        # 如果没有图像，返回空数据而不是 404
        if image_info is None:
            image_info = {}
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "success",
                "data": image_info
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取切片图像失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取切片图像失败"
        )


@spatial_router.get("/{fileId}/spots", response_model=GetSpotsResponse)
async def get_spots(
    fileId: str,
    request: Request
):
    """
    获取文件的Spots位置数据（单切片模式）
    
    - **fileId**: 文件ID
    
    只返回Spot的位置信息（id, x, y），用于在图像上绘制spots。
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
        
        # 获取Spots数据（只返回位置信息）
        spatial_service = get_spatial_service()
        spots_data = spatial_service.get_spots(fileId, user_id)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "success",
                "data": spots_data
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取Spots数据失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取Spots数据失败"
        )


@spatial_router.get("/{fileId}/gene/{geneName}")
async def get_gene_expression(
    fileId: str,
    geneName: str,
    request: Request
):
    """
    获取指定基因在所有Spots中的表达值（单切片模式）
    
    - **fileId**: 文件ID
    - **geneName**: 基因名称
    
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
        
        # 获取基因表达数据
        spatial_service = get_spatial_service()
        expression_data = spatial_service.get_gene_expression(fileId, geneName, user_id)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "success",
                "data": expression_data
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取基因表达数据失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取基因表达数据失败"
        )


@spatial_router.get("/{fileId}/genes")
async def get_gene_list(
    fileId: str,
    request: Request,
    query: Optional[str] = Query(None, description="搜索关键词（可选）")
):
    """
    获取文件的可用基因列表（单切片模式）
    
    - **fileId**: 文件ID
    - **query**: 搜索关键词（可选）
    
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
        
        # 获取基因列表
        spatial_service = get_spatial_service()
        genes = spatial_service.get_gene_list(fileId, user_id, query=query)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "success",
                "data": genes
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取基因列表失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取基因列表失败"
        )
