"""
可视化API路由
提供数据可视化功能，支持空间转录组学等多种可视化类型
使用分层路径结构，便于扩展
"""
import os
from typing import Optional, List
from fastapi import APIRouter, HTTPException, status, Request, Query, Path, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field
from textmsa.logging_config import get_logger
from textmsa.services.auth.auth_service import get_current_user_from_header
from textmsa.services.visualization.visualization_service import get_visualization_service

logger = get_logger(__name__)

# 创建路由
visualization_router = APIRouter(prefix="/api/visualization", tags=["数据可视化"])


class RawQcRequest(BaseModel):
  """原始QC预览请求体"""
  file_id: str = Field(..., description="文件ID")
  genes: List[str] = Field(..., description="基因列表")
  max_cells: int | None = Field(2000, description="最大细胞数")
  return_qc: bool | None = Field(True, description="是否返回QC指标")
  return_coords: bool | None = Field(True, description="是否返回降维坐标")
  embed_method: str | None = Field("umap", description="降维方式: umap/pca/tsne")


@visualization_router.get("/{file_id}/types")
async def get_visualization_types(
    file_id: str = Path(..., description="文件ID", min_length=1),
    request: Request = None
):
    """
    获取文件支持的可视化类型
    
    - **file_id**: 文件ID（必填）
    
    需要提供Authorization头或token头
    """
    try:
        # 验证file_id参数
        if not file_id or not file_id.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="文件ID不能为空"
            )
        
        file_id = file_id.strip()
        
        # 获取当前用户
        user_info = await get_current_user_from_header(request=request)
        
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录"
            )
        
        user_id = user_info["user_id"]
        
        # 获取可视化类型
        visualization_service = get_visualization_service()
        types = visualization_service.get_visualization_types(file_id, user_id)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "success",
                "data": types
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取可视化类型失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取可视化类型失败"
        )


@visualization_router.get("/{file_id}/spatial/slice-image")
async def get_spatial_slice_image(
    file_id: str = Path(..., description="文件ID", min_length=1),
    request: Request = None
):
    """
    获取空间转录组学切片图像
    
    - **file_id**: 文件ID（必填）
    
    需要提供Authorization头或token头
    """
    try:
        # 验证file_id参数
        if not file_id or not file_id.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="文件ID不能为空"
            )
        
        file_id = file_id.strip()
        
        # 获取当前用户
        user_info = await get_current_user_from_header(request=request)
        
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录"
            )
        
        user_id = user_info["user_id"]
        
        # 获取切片图像
        visualization_service = get_visualization_service()
        image_info = visualization_service.get_spatial_slice_image(file_id, user_id)
        
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


@visualization_router.get("/{file_id}/spatial/spots")
async def get_spatial_spots(
    file_id: str = Path(..., description="文件ID", min_length=1),
    request: Request = None
):
    """
    获取空间转录组学spots位置数据
    
    - **file_id**: 文件ID（必填）
    
    需要提供Authorization头或token头
    """
    try:
        # 验证file_id参数
        if not file_id or not file_id.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="文件ID不能为空"
            )
        
        file_id = file_id.strip()
        
        # 获取当前用户
        user_info = await get_current_user_from_header(request=request)
        
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录"
            )
        
        user_id = user_info["user_id"]
        
        # 获取spots数据
        visualization_service = get_visualization_service()
        spots_data = visualization_service.get_spatial_spots(file_id, user_id)
        
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
        logger.error(f"获取spots数据失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取spots数据失败"
        )


@visualization_router.get("/{file_id}/spatial/gene/{gene_name}/expression")
async def get_spatial_gene_expression(
    file_id: str = Path(..., description="文件ID", min_length=1),
    gene_name: str = Path(..., description="基因名称", min_length=1),
    request: Request = None
):
    """
    获取空间转录组学基因表达数据
    
    - **file_id**: 文件ID（必填）
    - **gene_name**: 基因名称（必填）
    
    需要提供Authorization头或token头
    """
    try:
        # 验证file_id参数
        if not file_id or not file_id.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="文件ID不能为空"
            )
        
        file_id = file_id.strip()
        
        # 验证gene_name参数
        if not gene_name or not gene_name.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="基因名称不能为空"
            )
        
        gene_name = gene_name.strip()
        
        # 获取当前用户
        user_info = await get_current_user_from_header(request=request)
        
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录"
            )
        
        user_id = user_info["user_id"]
        
        # 获取基因表达数据
        visualization_service = get_visualization_service()
        expression_data = visualization_service.get_spatial_gene_expression(
            file_id, gene_name, user_id
        )
        
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


@visualization_router.get("/{file_id}/spatial/genes")
async def get_spatial_genes(
    file_id: str = Path(..., description="文件ID", min_length=1),
    query: Optional[str] = Query(None, description="搜索关键词（可选）"),
    request: Request = None
):
    """
    获取空间转录组学基因列表
    
    - **file_id**: 文件ID（必填）
    - **query**: 搜索关键词（可选）
    
    需要提供Authorization头或token头
    """
    try:
        # 验证file_id参数
        if not file_id or not file_id.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="文件ID不能为空"
            )
        
        file_id = file_id.strip()
        
        # 获取当前用户
        user_info = await get_current_user_from_header(request=request)
        
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录"
            )
        
        user_id = user_info["user_id"]
        
        # 获取基因列表
        visualization_service = get_visualization_service()
        genes = visualization_service.get_spatial_genes(file_id, user_id, query=query)
        
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


@visualization_router.get("/{file_id}/{visualization_type}/data")
async def get_visualization_data(
    file_id: str = Path(..., description="文件ID", min_length=1),
    visualization_type: str = Path(..., description="可视化类型", min_length=1),
    data_type: Optional[str] = Query(None, description="数据类型（可选，如：slice-image, spots, gene-expression, genes）"),
    gene_name: Optional[str] = Query(None, description="基因名称（当data_type为gene-expression时必填）"),
    query: Optional[str] = Query(None, description="搜索关键词（当data_type为genes时可选）"),
    request: Request = None
):
    """
    获取可视化数据（通用接口，支持未来扩展）
    
    - **file_id**: 文件ID（必填）
    - **visualization_type**: 可视化类型（必填，如：spatial）
    - **data_type**: 数据类型（可选，如：slice-image, spots, gene-expression, genes）
    - **gene_name**: 基因名称（当data_type为gene-expression时必填）
    - **query**: 搜索关键词（当data_type为genes时可选）
    
    需要提供Authorization头或token头
    """
    try:
        # 验证file_id参数
        if not file_id or not file_id.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="文件ID不能为空"
            )
        
        file_id = file_id.strip()
        
        # 验证visualization_type参数
        if not visualization_type or not visualization_type.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="可视化类型不能为空"
            )
        
        visualization_type = visualization_type.strip()
        
        # 验证gene_name参数（当data_type为gene-expression时必填）
        if data_type == "gene-expression":
            if not gene_name or not gene_name.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="获取基因表达数据需要提供gene_name参数"
                )
            gene_name = gene_name.strip()
        
        # 获取当前用户
        user_info = await get_current_user_from_header(request=request)
        
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录"
            )
        
        user_id = user_info["user_id"]
        
        # 构建kwargs参数
        kwargs = {}
        if gene_name:
            kwargs["gene_name"] = gene_name
        if query:
            kwargs["query"] = query
        
        # 获取可视化数据
        visualization_service = get_visualization_service()
        data = visualization_service.get_visualization_data(
            file_id=file_id,
            visualization_type=visualization_type,
            user_id=user_id,
            data_type=data_type,
            **kwargs
        )
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "code": 200,
                "message": "success",
                "data": data
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取可视化数据失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取可视化数据失败"
        )


@visualization_router.post("/query_h5ad_genes")
async def query_h5ad_genes(payload: RawQcRequest, request: Request = None):
    """
    原始QC预览，返回 counts / n_genes / pct_mt / expression / coords 等信息。
    """
    try:
        # 鉴权
        user_info = await get_current_user_from_header(request=request)
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录"
            )
        user_id = user_info["user_id"]

        svc = get_visualization_service()
        data = svc.query_raw_qc(
            file_id=payload.file_id.strip(),
            user_id=user_id,
            genes=payload.genes,
            max_cells=payload.max_cells or 2000,
            return_qc=payload.return_qc if payload.return_qc is not None else True,
            return_coords=payload.return_coords if payload.return_coords is not None else True,
            embed_method=payload.embed_method or "umap",
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"code": 200, "message": "success", "data": data}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"query_h5ad_genes 失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取原始QC数据失败"
        )


@visualization_router.get("/download_h5ad")
async def download_h5ad(
    file_id: str = Query(..., description="文件ID"),
    genes: Optional[str] = Query(None, description="基因列表，逗号分隔"),
    cell_id: Optional[str] = Query(None, description="单细胞ID"),
    request: Request = None,
    background_tasks: BackgroundTasks = None
):
    """
    下载子集 h5ad 文件。支持按基因/单细胞子集。
    """
    try:
        user_info = await get_current_user_from_header(request=request)
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未授权，请先登录"
            )
        user_id = user_info["user_id"]

        genes_list = genes.split(",") if genes else None
        svc = get_visualization_service()
        tmp_path = svc.download_raw_h5ad(
            file_id=file_id.strip(),
            user_id=user_id,
            genes=genes_list,
            cell_id=cell_id
        )

        filename = os.path.basename(tmp_path) or "raw_subset.h5ad"

        # 下载完成后删除临时文件
        def _cleanup(path: str):
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception as e:
                logger.warning(f"删除临时文件失败: {e}")

        if background_tasks is not None:
            background_tasks.add_task(_cleanup, tmp_path)

        return FileResponse(
            path=tmp_path,
            filename=filename,
            media_type="application/octet-stream"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"download_h5ad 失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="下载失败"
        )

