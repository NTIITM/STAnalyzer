"""
可视化服务
提供数据可视化功能，支持空间转录组学等多种可视化类型
设计为可扩展架构，便于未来添加新的可视化类型
"""
import os
from typing import Dict, Any, List, Optional, Protocol
from fastapi import HTTPException, status

from textmsa.logging_config import get_logger
from textmsa.services.file.file_service import get_file_service
from textmsa.services.spatial.spatial_service import get_spatial_service

logger = get_logger(__name__)


class VisualizationHandler(Protocol):
    """可视化处理器协议，定义可视化类型的接口"""
    
    def get_slice_image(self, file_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """获取切片图像"""
        ...
    
    def get_spots(self, file_id: str, user_id: str) -> Dict[str, Any]:
        """获取spots位置数据"""
        ...
    
    def get_gene_expression(self, file_id: str, gene_name: str, user_id: str) -> List[Dict[str, Any]]:
        """获取基因表达数据"""
        ...
    
    def get_genes(self, file_id: str, user_id: str, query: Optional[str] = None) -> List[str]:
        """获取基因列表"""
        ...


class SpatialVisualizationHandler:
    """空间转录组学可视化处理器"""
    
    def __init__(self):
        """初始化空间可视化处理器"""
        self.spatial_service = get_spatial_service()
    
    def get_slice_image(self, file_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """
        获取空间转录组学切片图像
        
        Args:
            file_id: 文件ID
            user_id: 用户ID
        
        Returns:
            包含imageUrl、width、height的字典，如果没有图像则返回 None
        """
        return self.spatial_service.get_slice_image(file_id, user_id)
    
    def get_spots(self, file_id: str, user_id: str) -> Dict[str, Any]:
        """
        获取空间转录组学spots位置数据
        
        Args:
            file_id: 文件ID
            user_id: 用户ID
        
        Returns:
            包含spots列表和totalCount的字典
        """
        return self.spatial_service.get_spots(file_id, user_id)
    
    def get_gene_expression(self, file_id: str, gene_name: str, user_id: str) -> List[Dict[str, Any]]:
        """
        获取空间转录组学基因表达数据
        
        Args:
            file_id: 文件ID
            gene_name: 基因名称
            user_id: 用户ID
        
        Returns:
            包含spotId和value的字典列表
        """
        return self.spatial_service.get_gene_expression(file_id, gene_name, user_id)
    
    def get_genes(self, file_id: str, user_id: str, query: Optional[str] = None) -> List[str]:
        """
        获取空间转录组学基因列表
        
        Args:
            file_id: 文件ID
            user_id: 用户ID
            query: 搜索关键词（可选）
        
        Returns:
            基因名称列表
        """
        return self.spatial_service.get_gene_list(file_id, user_id, query)

    def query_raw_qc(
        self,
        file_id: str,
        user_id: str,
        genes: List[str],
        max_cells: int = 2000,
        return_qc: bool = True,
        return_coords: bool = True,
        embed_method: str = "umap"
    ) -> Dict[str, Any]:
        return self.spatial_service.query_raw_qc(
            file_id=file_id,
            user_id=user_id,
            genes=genes,
            max_cells=max_cells,
            return_qc=return_qc,
            return_coords=return_coords,
            embed_method=embed_method,
        )

    def download_raw_h5ad(
        self,
        file_id: str,
        user_id: str,
        genes: Optional[List[str]] = None,
        cell_id: Optional[str] = None
    ) -> str:
        return self.spatial_service.download_raw_h5ad(file_id, user_id, genes=genes, cell_id=cell_id)


class VisualizationService:
    """
    可视化服务类
    提供统一的可视化接口，支持多种可视化类型
    设计为可扩展架构，便于未来添加新的可视化类型
    """
    
    # 支持的可视化类型
    VISUALIZATION_TYPES = {
        "spatial": {
            "name": "空间转录组学",
            "description": "空间转录组学数据可视化",
            "handler": None  # 延迟初始化
        }
        # 未来可以添加其他类型，例如：
        # "single_cell": {...},
        # "bulk_rnaseq": {...},
        # "proteomics": {...}
    }
    
    def __init__(self):
        """初始化可视化服务"""
        self.file_service = get_file_service()
        # 延迟初始化处理器，避免循环依赖
        self._handlers: Dict[str, VisualizationHandler] = {}
    
    def _get_handler(self, visualization_type: str) -> VisualizationHandler:
        """
        获取指定类型的可视化处理器
        
        Args:
            visualization_type: 可视化类型（如 "spatial"）
        
        Returns:
            可视化处理器实例
        
        Raises:
            HTTPException: 如果可视化类型不支持
        """
        if visualization_type not in self.VISUALIZATION_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不支持的可视化类型: {visualization_type}"
            )
        
        # 延迟初始化处理器
        if visualization_type not in self._handlers:
            if visualization_type == "spatial":
                self._handlers[visualization_type] = SpatialVisualizationHandler()
            else:
                raise HTTPException(
                    status_code=status.HTTP_501_NOT_IMPLEMENTED,
                    detail=f"可视化类型 {visualization_type} 尚未实现"
                )
        
        return self._handlers[visualization_type]
    
    def _validate_file_access(self, file_id: str, user_id: str) -> Dict[str, Any]:
        """
        验证文件访问权限
        
        Args:
            file_id: 文件ID
            user_id: 用户ID
        
        Returns:
            文件信息字典
        
        Raises:
            HTTPException: 如果文件不存在或用户无权限访问
        """
        try:
            file_info = self.file_service.get_file_info(file_id, user_id)
            return file_info
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"验证文件访问权限失败: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="验证文件访问权限失败"
            )
    
    def get_visualization_types(self, file_id: str, user_id: str) -> List[Dict[str, Any]]:
        """
        获取文件支持的可视化类型
        
        Args:
            file_id: 文件ID
            user_id: 用户ID
        
        Returns:
            支持的可视化类型列表
        """
        # 验证文件访问权限
        file_info = self._validate_file_access(file_id, user_id)
        
        # 根据文件类型和元数据判断支持的可视化类型
        supported_types = []
        
        # 检查文件路径和元数据，判断是否支持空间转录组学
        file_path = file_info.get("file_path", "")
        metadata = file_info.get("metadata", {})
        
        # 如果文件是h5ad格式，可能支持空间转录组学
        if file_path.lower().endswith('.h5ad'):
            # 检查元数据中是否有空间信息
            has_spatial = (
                metadata.get("has_spatial", False) or
                "spatial" in str(metadata).lower() or
                os.path.exists(file_path)  # 文件存在，可以进一步检查
            )
            
            if has_spatial:
                supported_types.append({
                    "type": "spatial",
                    "name": self.VISUALIZATION_TYPES["spatial"]["name"],
                    "description": self.VISUALIZATION_TYPES["spatial"]["description"]
                })
        
        return supported_types

    def query_raw_qc(
        self,
        file_id: str,
        user_id: str,
        genes: List[str],
        max_cells: int = 2000,
        return_qc: bool = True,
        return_coords: bool = True,
        embed_method: str = "umap"
    ) -> Dict[str, Any]:
        handler = self._get_handler("spatial")
        return handler.query_raw_qc(
            file_id=file_id,
            user_id=user_id,
            genes=genes,
            max_cells=max_cells,
            return_qc=return_qc,
            return_coords=return_coords,
            embed_method=embed_method,
        )

    def download_raw_h5ad(
        self,
        file_id: str,
        user_id: str,
        genes: Optional[List[str]] = None,
        cell_id: Optional[str] = None
    ) -> str:
        handler = self._get_handler("spatial")
        return handler.download_raw_h5ad(file_id, user_id, genes=genes, cell_id=cell_id)
    
    def get_spatial_slice_image(self, file_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """
        获取空间转录组学切片图像
        
        Args:
            file_id: 文件ID
            user_id: 用户ID
        
        Returns:
            包含imageUrl、width、height的字典，如果没有图像则返回 None
        """
        # 验证文件访问权限
        self._validate_file_access(file_id, user_id)
        
        # 获取空间可视化处理器
        handler = self._get_handler("spatial")
        
        # 调用处理器获取切片图像
        return handler.get_slice_image(file_id, user_id)
    
    def get_spatial_spots(self, file_id: str, user_id: str) -> Dict[str, Any]:
        """
        获取空间转录组学spots位置数据
        
        Args:
            file_id: 文件ID
            user_id: 用户ID
        
        Returns:
            包含spots列表和totalCount的字典
        """
        # 验证文件访问权限
        self._validate_file_access(file_id, user_id)
        
        # 获取空间可视化处理器
        handler = self._get_handler("spatial")
        
        # 调用处理器获取spots数据
        return handler.get_spots(file_id, user_id)
    
    def get_spatial_gene_expression(self, file_id: str, gene_name: str, user_id: str) -> List[Dict[str, Any]]:
        """
        获取空间转录组学基因表达数据
        
        Args:
            file_id: 文件ID
            gene_name: 基因名称
            user_id: 用户ID
        
        Returns:
            包含spotId和value的字典列表
        """
        # 验证文件访问权限
        self._validate_file_access(file_id, user_id)
        
        # 获取空间可视化处理器
        handler = self._get_handler("spatial")
        
        # 调用处理器获取基因表达数据
        return handler.get_gene_expression(file_id, gene_name, user_id)
    
    def get_spatial_genes(self, file_id: str, user_id: str, query: Optional[str] = None) -> List[str]:
        """
        获取空间转录组学基因列表
        
        Args:
            file_id: 文件ID
            user_id: 用户ID
            query: 搜索关键词（可选）
        
        Returns:
            基因名称列表
        """
        # 验证文件访问权限
        self._validate_file_access(file_id, user_id)
        
        # 获取空间可视化处理器
        handler = self._get_handler("spatial")
        
        # 调用处理器获取基因列表
        return handler.get_genes(file_id, user_id, query)
    
    def get_visualization_data(
        self,
        file_id: str,
        visualization_type: str,
        user_id: str,
        data_type: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        获取可视化数据（通用接口，支持未来扩展）
        
        Args:
            file_id: 文件ID
            visualization_type: 可视化类型（如 "spatial"）
            user_id: 用户ID
            data_type: 数据类型（如 "slice-image", "spots", "gene-expression"）
            **kwargs: 其他参数（如 gene_name）
        
        Returns:
            可视化数据字典
        
        Raises:
            HTTPException: 如果可视化类型不支持或参数无效
        """
        # 验证文件访问权限
        self._validate_file_access(file_id, user_id)
        
        # 获取指定类型的可视化处理器
        handler = self._get_handler(visualization_type)
        
        # 根据数据类型调用相应的方法
        if visualization_type == "spatial":
            if data_type == "slice-image":
                result = handler.get_slice_image(file_id, user_id)
                # 如果没有图像，返回空字典而不是 None
                return result if result is not None else {}
            elif data_type == "spots":
                return handler.get_spots(file_id, user_id)
            elif data_type == "gene-expression":
                gene_name = kwargs.get("gene_name")
                if not gene_name:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="获取基因表达数据需要提供gene_name参数"
                    )
                return {"expression": handler.get_gene_expression(file_id, gene_name, user_id)}
            elif data_type == "genes":
                query = kwargs.get("query")
                return {"genes": handler.get_genes(file_id, user_id, query)}
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"不支持的数据类型: {data_type}。支持的类型: slice-image, spots, gene-expression, genes"
                )
        else:
            # 未来可以添加其他可视化类型的处理逻辑
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail=f"可视化类型 {visualization_type} 尚未实现"
            )


# 全局服务实例
_visualization_service: Optional[VisualizationService] = None


def get_visualization_service() -> VisualizationService:
    """获取全局可视化服务实例"""
    global _visualization_service
    if _visualization_service is None:
        _visualization_service = VisualizationService()
    return _visualization_service

