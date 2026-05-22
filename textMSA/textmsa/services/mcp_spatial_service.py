"""
MCP-based Spatial Service
使用 MCP 协议调用空间分析工具，而不是直接导入 Python 模块
"""
import json
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

from textmsa.mcp_client.fastmcp_client import FastMCPClients, create_fastmcp_clients
from textmsa.logging_config import get_logger

logger = get_logger(__name__)


class MCPSpatialService:
    """
    基于 MCP 协议的空间分析服务
    通过 FastMCPClients 调用远程 MCP 服务器上的工具
    """
    
    def __init__(self, mcp_clients: Optional[FastMCPClients] = None):
        """
        初始化 MCP 空间分析服务
        
        Args:
            mcp_clients: FastMCPClients 实例，如果为 None 则自动创建
        """
        self.mcp_clients = mcp_clients
        self._initialized = False
    
    async def ensure_initialized(self):
        """确保服务已初始化"""
        if not self._initialized:
            if self.mcp_clients is None:
                logger.info("创建 MCP 客户端...")
                self.mcp_clients = await create_fastmcp_clients()
            self._initialized = True
            logger.info("MCP Spatial Service 初始化完成")
            logger.info(f"已连接的服务器: {self.mcp_clients.get_connected_servers()}")
    
    async def list_available_clustering_methods(self) -> Dict[str, Any]:
        """
        列出可用的聚类方法
        
        Returns:
            包含聚类方法列表的字典
        """
        await self.ensure_initialized()
        
        # 返回基于 MCP 服务器提供的方法
        methods = []
        
        # Leiden 聚类 (通过 spatial_analysis MCP)
        if "spatial_analysis" in self.mcp_clients.get_connected_servers():
            methods.append({
                "id": "leiden",
                "name": "Leiden聚类",
                "description": "基于邻居图的Leiden聚类算法",
                "server": "spatial_analysis",
                "tool": "sa_preprocessing_and_clustering",
                "default_params": {
                    "n_neighbors": 10,
                    "n_pcs": 30,
                }
            })
            methods.append({
                "id": "custom_spatial_analysis",
                "name": "自定义空间分析",
                "description": "可选的PCA/Neighbors/UMAP/Leiden组合",
                "server": "spatial_analysis",
                "tool": "sa_spatial_analysis",
                "default_params": {
                    "methods": ["pca", "neighbors", "umap", "leiden"],
                    "n_neighbors": 10,
                    "n_pcs": 30,
                }
            })
        
        # 空间分割聚类 (通过 spatial_segmentation MCP)
        if "spatial_segmentation" in self.mcp_clients.get_connected_servers():
            methods.append({
                "id": "spatial_segmentation",
                "name": "空间分割聚类",
                "description": "基于PCA和空间坐标的K-Means聚类",
                "server": "spatial_segmentation",
                "tool": "seg_segment",
                "default_params": {
                    "n_domains": 8,
                    "n_pcs": 30,
                }
            })
        
        return {"methods": methods}
    
    async def preprocessing_and_clustering(
        self,
        file_path: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        执行预处理和聚类流程
        通过 MCP 调用 spatial_analysis 服务的 sa_preprocessing_and_clustering 工具
        
        Args:
            file_path: 输入数据路径
            **kwargs: 其他参数传递给工具
            
        Returns:
            执行结果字典
        """
        await self.ensure_initialized()
        
        try:
            # 查找工具
            tool = self.mcp_clients.tool_map.get("sa_preprocessing_and_clustering")
            if not tool:
                return {
                    "success": False,
                    "error": True,
                    "message": "未找到 sa_preprocessing_and_clustering 工具，请确保 spatial_analysis MCP 服务器已启动"
                }
            
            # 准备参数
            params = {"file_path": file_path, **kwargs}
            
            logger.info(f"调用 MCP 工具 sa_preprocessing_and_clustering，参数: {params}")
            
            # 执行工具
            result = await tool.execute(**params)
            
            if result.success:
                return result.data
            else:
                return {
                    "success": False,
                    "error": True,
                    "message": result.error or "工具执行失败"
                }
        
        except Exception as e:
            logger.error(f"preprocessing_and_clustering 执行失败: {e}", exc_info=True)
            return {
                "success": False,
                "error": True,
                "message": f"执行失败: {str(e)}"
            }
    
    async def spatial_analysis(
        self,
        file_path: str,
        methods: Optional[List[str]] = None,
        n_neighbors: int = 10,
        n_pcs: int = 30,
    ) -> Dict[str, Any]:
        """
        执行空间分析
        通过 MCP 调用 spatial_analysis 服务的 sa_spatial_analysis 工具
        
        Args:
            file_path: 输入数据路径
            methods: 要执行的方法列表
            n_neighbors: 邻居数
            n_pcs: PCA主成分数
            
        Returns:
            执行结果字典
        """
        await self.ensure_initialized()
        
        try:
            tool = self.mcp_clients.tool_map.get("sa_spatial_analysis")
            if not tool:
                return {
                    "success": False,
                    "error": True,
                    "message": "未找到 sa_spatial_analysis 工具"
                }
            
            params = {
                "file_path": file_path,
                "methods": methods or ["pca", "neighbors", "umap", "leiden"],
                "n_neighbors": n_neighbors,
                "n_pcs": n_pcs,
            }
            
            logger.info(f"调用 MCP 工具 sa_spatial_analysis，参数: {params}")
            
            result = await tool.execute(**params)
            
            if result.success:
                return result.data
            else:
                return {
                    "success": False,
                    "error": True,
                    "message": result.error or "工具执行失败"
                }
        
        except Exception as e:
            logger.error(f"spatial_analysis 执行失败: {e}", exc_info=True)
            return {
                "success": False,
                "error": True,
                "message": f"执行失败: {str(e)}"
            }
    
    async def spatial_segmentation(
        self,
        file_path: str,
        n_domains: int = 8,
        n_pcs: int = 30,
        coord_key: str = "spatial",
        **kwargs
    ) -> Dict[str, Any]:
        """
        执行空间分割聚类
        通过 MCP 调用 spatial_segmentation 服务的 seg_segment 工具
        
        Args:
            file_path: 输入数据路径
            n_domains: 分割域数量
            n_pcs: PCA主成分数
            coord_key: 坐标键名
            **kwargs: 其他参数
            
        Returns:
            执行结果字典
        """
        await self.ensure_initialized()
        
        try:
            tool = self.mcp_clients.tool_map.get("seg_segment")
            if not tool:
                return {
                    "success": False,
                    "error": True,
                    "message": "未找到 seg_segment 工具，请确保 spatial_segmentation MCP 服务器已启动"
                }
            
            params = {
                "file_path": file_path,
                "n_domains": n_domains,
                "n_pcs": n_pcs,
                "coord_key": coord_key,
                **kwargs
            }
            
            logger.info(f"调用 MCP 工具 seg_segment，参数: {params}")
            
            result = await tool.execute(**params)
            
            if result.success:
                return result.data
            else:
                return {
                    "success": False,
                    "error": True,
                    "message": result.error or "工具执行失败"
                }
        
        except Exception as e:
            logger.error(f"spatial_segmentation 执行失败: {e}", exc_info=True)
            return {
                "success": False,
                "error": True,
                "message": f"执行失败: {str(e)}"
            }
    
    async def call_tool_by_method(
        self,
        method: str,
        file_path: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        根据方法名调用相应的工具
        
        Args:
            method: 聚类方法ID
            file_path: 数据文件路径
            parameters: 参数字典
            
        Returns:
            执行结果
        """
        if method == "leiden":
            return await self.preprocessing_and_clustering(
                file_path=file_path,
                **parameters
            )
        elif method == "spatial_segmentation":
            return await self.spatial_segmentation(
                file_path=file_path,
                **parameters
            )
        elif method == "custom_spatial_analysis":
            return await self.spatial_analysis(
                file_path=file_path,
                **parameters
            )
        else:
            return {
                "success": False,
                "error": True,
                "message": f"未知的聚类方法: {method}"
            }


# 全局服务实例
_mcp_spatial_service: Optional[MCPSpatialService] = None


async def get_mcp_spatial_service() -> MCPSpatialService:
    """
    获取全局 MCP 空间分析服务实例
    
    Returns:
        MCPSpatialService 实例
    """
    global _mcp_spatial_service
    if _mcp_spatial_service is None:
        _mcp_spatial_service = MCPSpatialService()
        await _mcp_spatial_service.ensure_initialized()
    return _mcp_spatial_service

