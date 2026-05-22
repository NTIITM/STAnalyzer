"""
空间转录组数据服务
负责读取h5ad文件并提供空间可视化数据
"""
import os
import base64
import tempfile
from typing import Optional, Dict, Any, List, Iterable
from pathlib import Path
from fastapi import HTTPException, status

from textmsa.logging_config import get_logger
from textmsa.services.file.file_service import get_file_service
from textmsa.services.data.user_data_manager_mongodb import get_user_data_manager
from textmsa.settings import get_server_config

logger = get_logger(__name__)

# 读取配置（避免导入auth_service导致jose依赖）
_server_config = get_server_config()
_DEV_MODE = bool(_server_config.get("dev_mode", True))
_DEV_TEST_USER_ID = str(_server_config.get("dev_test_user_id", "test_user_id"))

# 尝试导入anndata和其他依赖
try:
    import anndata as ad
    import numpy as np
    import pandas as pd
    from scipy import sparse
    import scanpy as sc
    BIO_AVAILABLE = True
except ImportError:
    BIO_AVAILABLE = False
    logger.warning("anndata库未安装，空间数据服务功能受限")

# 尝试导入PIL
try:
    import PIL.Image as Image
    import io
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logger.warning("PIL库未安装，图像处理功能受限")


class SpatialService:
    """空间转录组数据服务类"""
    
    def __init__(self):
        """初始化空间服务"""
        self.file_service = get_file_service()
        self.user_data_manager = get_user_data_manager()
        self._adata_cache: Dict[str, Any] = {}  # 文件ID -> AnnData对象缓存
    
    def _get_file_path(self, file_id: str, user_id: str) -> str:
        """获取文件路径"""
        # 开发模式：如果user_id是DEV_TEST_USER_ID，尝试映射到实际的user_id
        if _DEV_MODE and user_id == _DEV_TEST_USER_ID:
            try:
                from textmsa.services.user.user_service import get_user_service
                user_service = get_user_service()
                test_user = user_service.get_user_by_username("test_user")
                if test_user:
                    user_id = test_user["userId"]
                    logger.debug(f"开发模式：映射DEV_TEST_USER_ID到实际user_id: {user_id}")
            except Exception as e:
                logger.warning(f"开发模式：无法获取test_user的实际ID: {e}")
        
        file_info = self.user_data_manager.get_file_info(user_id, file_id)
        if not file_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文件不存在"
            )
        file_path = file_info.get("file_path")
        if not file_path or not os.path.exists(file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文件路径不存在"
            )
        return file_path
    
    def _load_adata(self, file_id: str, file_path: str) -> Any:
        """
        加载AnnData对象（带缓存）
        
        处理常见的警告：
        - 将索引转换为字符串类型（避免隐式转换警告）
        - 确保var_names和obs_names唯一性
        """
        if not BIO_AVAILABLE:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="生物信息学库未安装"
            )
        
        # 检查缓存
        if file_id in self._adata_cache:
            adata = self._adata_cache[file_id]
            # 检查文件是否被修改
            try:
                if hasattr(adata, 'file') and adata.file is not None:
                    # backed模式，文件可能已关闭或修改
                    # 重新打开
                    adata.file.close()
                    del self._adata_cache[file_id]
            except:
                pass
        
        if file_id not in self._adata_cache:
            adata = None
            last_error = None
            
            # 方式1: 尝试使用backed='r'模式（标准h5ad格式，节省内存）
            try:
                adata = ad.read_h5ad(file_path, backed='r')
                logger.debug(f"使用backed模式成功加载文件: {file_path}")
            except Exception as e1:
                last_error = e1
                logger.debug(f"backed模式加载失败，尝试内存模式: {e1}")
                
                # 方式2: 尝试不使用backed模式（完全加载到内存）
                # 适用于文件结构不完整或非标准格式的情况
                try:
                    adata = ad.read_h5ad(file_path, backed=False)
                    logger.debug(f"使用内存模式成功加载文件: {file_path}")
                except Exception as e2:
                    last_error = e2
                    logger.error(f"内存模式加载也失败: {e2}")
            
            if adata is None:
                logger.error(f"加载h5ad文件失败，已尝试所有方式: {last_error}", exc_info=True)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"加载文件失败: {str(last_error)}"
                )
            
            self._adata_cache[file_id] = adata
        
        return self._adata_cache[file_id]
    
    def _normalize_adata_names(self, adata: Any) -> Any:
        """
        规范化AnnData对象的名称，避免警告
        
        处理：
        1. 隐式转换为字符串索引的警告
        2. 变量名不唯一的警告
        
        在backed模式下，创建一个内存视图来处理名称问题
        """
        # 检查是否需要处理
        needs_normalization = False
        
        # 检查索引类型和唯一性
        try:
            # 检查var_names是否需要处理
            var_names = adata.var_names
            # 检查是否有重复（主要问题）
            if hasattr(var_names, 'is_unique'):
                if not var_names.is_unique:
                    needs_normalization = True
                    logger.debug(f"检测到var_names不唯一: {len(var_names)} 个基因中有重复")
            # 检查索引类型（可能导致隐式转换警告）
            var_names_dtype = str(var_names.dtype)
            if 'int' in var_names_dtype or 'float' in var_names_dtype:
                # 如果索引是数值类型，访问时可能会触发隐式转换警告
                needs_normalization = True
                logger.debug(f"检测到var_names为数值类型: {var_names_dtype}，需要转换为字符串")
            
            # 检查obs_names
            obs_names = adata.obs_names
            if hasattr(obs_names, 'is_unique') and not obs_names.is_unique:
                needs_normalization = True
                logger.debug(f"检测到obs_names不唯一")
        except Exception as e:
            logger.debug(f"检查名称时出错: {e}，尝试规范化")
            needs_normalization = True
        
        # 如果不需要规范化，直接返回
        if not needs_normalization:
            return adata
        
        # 如果需要规范化，创建内存视图
        try:
            # 在backed模式下，我们需要先加载到内存
            if hasattr(adata, 'filename') and adata.filename is not None:
                logger.debug("规范化AnnData名称（backed模式，加载到内存）")
                adata_memory = adata.to_memory()
                # 确保名称唯一
                if hasattr(adata_memory.var_names, 'is_unique') and not adata_memory.var_names.is_unique:
                    adata_memory.var_names_make_unique()
                if hasattr(adata_memory.obs_names, 'is_unique') and not adata_memory.obs_names.is_unique:
                    adata_memory.obs_names_make_unique()
                logger.debug("名称规范化完成")
                return adata_memory
            else:
                # 非backed模式，直接修改
                if hasattr(adata.var_names, 'is_unique') and not adata.var_names.is_unique:
                    adata.var_names_make_unique()
                if hasattr(adata.obs_names, 'is_unique') and not adata.obs_names.is_unique:
                    adata.obs_names_make_unique()
                logger.debug("名称规范化完成")
                return adata
        except Exception as e:
            logger.warning(f"规范化AnnData名称失败: {e}，返回原始对象")
            return adata
    
    def get_slices(self, file_id: str, user_id: str) -> List[Dict[str, Any]]:
        """获取文件的切片列表"""
        file_path = self._get_file_path(file_id, user_id)
        adata = self._load_adata(file_id, file_path)
        
        slices = []
        
        # 检查uns['spatial']中是否有切片信息
        if 'spatial' in adata.uns:
            spatial_info = adata.uns['spatial']
            
            # 如果spatial_info是字典，遍历所有切片
            if isinstance(spatial_info, dict):
                for slice_id, slice_data in spatial_info.items():
                    slice_info = {
                        "id": str(slice_id),
                        "name": f"切片 {slice_id}",
                        "description": f"切片 {slice_id} 的空间数据"
                    }
                    
                    # 尝试获取图像尺寸
                    if isinstance(slice_data, dict):
                        if 'images' in slice_data:
                            images = slice_data['images']
                            if isinstance(images, dict):
                                # 获取第一个图像的尺寸
                                for img_key, img_data in images.items():
                                    if hasattr(img_data, 'shape'):
                                        slice_info["height"] = int(img_data.shape[0])
                                        slice_info["width"] = int(img_data.shape[1])
                                        break
                        elif 'scalefactors' in slice_data:
                            scalefactors = slice_data['scalefactors']
                            if isinstance(scalefactors, dict) and 'tissue_hires_scalef' in scalefactors:
                                # 如果有缩放因子，可以估算尺寸
                                pass
                    
                    slices.append(slice_info)
            
            # 如果spatial_info不是字典，可能是单个切片
            if not slices:
                slices.append({
                    "id": "default",
                    "name": "默认切片",
                    "description": "默认空间切片"
                })
        else:
            # 如果没有spatial信息，创建一个默认切片
            slices.append({
                "id": "default",
                "name": "默认切片",
                "description": "默认空间切片"
            })
        
        return slices
    
    def get_slice_image(self, file_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """
        获取切片的图像URL或base64编码（单切片模式）
        
        根据缩放因子缩放图像的width和height，确保与spot坐标对齐。
        
        如果没有找到图像，返回 None 而不是抛出异常。
        """
        file_path = self._get_file_path(file_id, user_id)
        adata = self._load_adata(file_id, file_path)
        
        # 尝试从uns['spatial']获取图像
        if 'spatial' in adata.uns:
            spatial_info = adata.uns['spatial']
            
            if isinstance(spatial_info, dict):
                # 获取第一个切片的数据
                for slice_id, slice_data in spatial_info.items():
                    if isinstance(slice_data, dict) and 'images' in slice_data:
                        images = slice_data['images']
                        scalefactors = slice_data.get('scalefactors', {})
                        
                        # 处理h5py对象：如果是h5py Group或Dataset，转换为字典
                        if hasattr(scalefactors, 'keys'):
                            try:
                                scalefactors_dict = {}
                                for key in scalefactors.keys():
                                    value = scalefactors[key]
                                    # 如果是h5py Dataset，读取值
                                    if hasattr(value, '__getitem__') and not isinstance(value, dict):
                                        try:
                                            scalefactors_dict[key] = float(value[()])
                                        except:
                                            scalefactors_dict[key] = value
                                    else:
                                        scalefactors_dict[key] = value
                                scalefactors = scalefactors_dict
                            except Exception as e:
                                logger.warning(f"读取缩放因子失败: {e}，使用空字典")
                                scalefactors = {}
                        
                        # 优先使用hires图像
                        for img_key in ['hires', 'lowres', 'fullres']:
                            if img_key in images:
                                img_data = images[img_key]
                                
                                # 获取对应的缩放因子
                                scale_factor = None
                                if img_key == 'hires' and 'tissue_hires_scalef' in scalefactors:
                                    scale_factor = scalefactors['tissue_hires_scalef']
                                elif img_key == 'lowres' and 'tissue_lowres_scalef' in scalefactors:
                                    scale_factor = scalefactors['tissue_lowres_scalef']
                                elif img_key == 'fullres':
                                    # fullres通常缩放因子为1.0
                                    scale_factor = 1.0
                                
                                # 转换为base64编码
                                try:
                                    if not PIL_AVAILABLE:
                                        raise ImportError("PIL库未安装")
                                    
                                    if isinstance(img_data, np.ndarray):
                                        # 确保是uint8格式
                                        if img_data.dtype != np.uint8:
                                            img_data = (img_data * 255).astype(np.uint8)
                                        
                                        # 转换为PIL Image
                                        if len(img_data.shape) == 2:
                                            img = Image.fromarray(img_data, mode='L')
                                        elif len(img_data.shape) == 3:
                                            img = Image.fromarray(img_data, mode='RGB')
                                        else:
                                            raise ValueError(f"不支持的图像格式: {img_data.shape}")
                                        
                                        # 转换为base64
                                        buffer = io.BytesIO()
                                        img.save(buffer, format='PNG')
                                        img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
                                        
                                        # 获取图像的原始像素尺寸
                                        original_width = int(img_data.shape[1])
                                        original_height = int(img_data.shape[0])
                                        
                                        # 根据缩放因子计算显示尺寸（用于spot对齐）
                                        if scale_factor and scale_factor > 0:
                                            display_width = int(original_width / scale_factor)
                                            display_height = int(original_height / scale_factor)
                                            logger.debug(f"图像缩放: {img_key}, 原始尺寸: {original_width}x{original_height}, "
                                                        f"缩放因子: {scale_factor}, 显示尺寸: {display_width}x{display_height}")
                                        else:
                                            # 如果没有缩放因子，使用原始尺寸
                                            display_width = original_width
                                            display_height = original_height
                                            logger.warning(f"未找到{img_key}图像的缩放因子，使用原始尺寸")
                                        
                                        return {
                                            "imageUrl": f"data:image/png;base64,{img_base64}",
                                            "width": display_width,
                                            "height": display_height
                                        }
                                except Exception as e:
                                    logger.warning(f"转换图像失败: {e}")
                                    continue
        
        # 如果没有找到图像，返回 None（而不是抛出 404 错误）
        return None
    
    def get_spots(
        self,
        file_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        获取文件的Spots位置数据（单切片模式）
        
        返回Spot的位置信息（id, x, y）和分组属性（group）。group包含obs中所有列的值（排除坐标列x和y）。
        
        Args:
            file_id: 文件ID
            user_id: 用户ID
            
        Returns:
            包含spots列表和totalCount的字典。每个spot包含id、x、y和group（包含所有obs列属性）。
        """
        file_path = self._get_file_path(file_id, user_id)
        adata = self._load_adata(file_id, file_path)
        
        # 获取空间坐标
        if 'spatial' in adata.obsm:
            coords = adata.obsm['spatial']
            if isinstance(coords, np.ndarray):
                x_coords = coords[:, 0]
                y_coords = coords[:, 1]
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="空间坐标格式错误"
                )
        elif 'x' in adata.obs.columns and 'y' in adata.obs.columns:
            x_coords = adata.obs['x'].values
            y_coords = adata.obs['y'].values
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="未找到空间坐标信息"
            )
        
        # 获取所有obs列，排除坐标列x和y
        obs_columns = [col for col in adata.obs.columns if col not in ['x', 'y']]
        
        # 构建spots数据（包含位置信息和所有obs属性）
        spots = []
        for idx in range(len(x_coords)):
            spot_id = str(adata.obs_names[idx])
            spot_data = {
                "id": spot_id,
                "x": float(x_coords[idx]),
                "y": float(y_coords[idx])
            }
            
            # 构建group对象，包含所有obs列的值
            group = {}
            for col in obs_columns:
                value = adata.obs[col].iloc[idx]
                # 处理值的类型转换，确保可以序列化为JSON
                if pd.isna(value):
                    group[col] = None
                elif isinstance(value, (int, np.integer)):
                    group[col] = int(value)
                elif isinstance(value, (float, np.floating)):
                    group[col] = float(value)
                elif isinstance(value, (bool, np.bool_)):
                    group[col] = bool(value)
                else:
                    # 字符串或其他类型，转换为字符串
                    group[col] = str(value)
            
            spot_data["group"] = group
            spots.append(spot_data)
        
        return {
            "spots": spots,
            "totalCount": len(spots)
        }
    
    def get_spot_details(self, file_id: str, spot_id: str, user_id: str) -> Dict[str, Any]:
        """获取Spot的详细信息（单切片模式）"""
        file_path = self._get_file_path(file_id, user_id)
        adata = self._load_adata(file_id, file_path)
        
        # 查找spot
        if spot_id not in adata.obs_names:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Spot {spot_id} 不存在"
            )
        
        spot_idx = adata.obs_names.get_loc(spot_id)
        
        # 获取坐标
        if 'spatial' in adata.obsm:
            coords = adata.obsm['spatial'][spot_idx]
            x, y = float(coords[0]), float(coords[1])
        elif 'x' in adata.obs.columns and 'y' in adata.obs.columns:
            x = float(adata.obs['x'].iloc[spot_idx])
            y = float(adata.obs['y'].iloc[spot_idx])
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="未找到空间坐标信息"
            )
        
        spot_data = {
            "id": spot_id,
            "x": x,
            "y": y
        }
        
        # 添加cluster信息
        cluster_cols = [col for col in adata.obs.columns if 'cluster' in col.lower() or 'leiden' in col.lower() or 'louvain' in col.lower()]
        if cluster_cols:
            cluster_col = cluster_cols[0]
            spot_data["cluster"] = str(adata.obs[cluster_col].iloc[spot_idx])
        
        # 获取高表达基因
        try:
            if sparse.issparse(adata.X):
                expr_values = np.array(adata.X[spot_idx, :].todense()).flatten()
            else:
                expr_values = np.array(adata.X[spot_idx, :]).flatten()
            
            top_indices = np.argsort(expr_values)[::-1][:10]
            top_genes = []
            for gene_idx in top_indices:
                if expr_values[gene_idx] > 0:
                    top_genes.append({
                        "name": str(adata.var_names[gene_idx]),
                        "value": float(expr_values[gene_idx])
                    })
            spot_data["topGenes"] = top_genes
        except Exception as e:
            logger.warning(f"获取高表达基因失败: {e}")
        
        # 添加元数据
        metadata = {}
        if 'total_counts' in adata.obs.columns:
            metadata["totalCounts"] = float(adata.obs['total_counts'].iloc[spot_idx])
        if 'n_genes' in adata.obs.columns:
            metadata["nFeatures"] = int(adata.obs['n_genes'].iloc[spot_idx])
        if metadata:
            spot_data["metadata"] = metadata
        
        return spot_data
    
    def get_spot_top_genes(
        self,
        file_id: str,
        spot_id: str,
        user_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """获取Spot的高表达基因列表（单切片模式）"""
        file_path = self._get_file_path(file_id, user_id)
        adata = self._load_adata(file_id, file_path)
        
        if spot_id not in adata.obs_names:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Spot {spot_id} 不存在"
            )
        
        spot_idx = adata.obs_names.get_loc(spot_id)
        
        # 获取表达值
        try:
            if sparse.issparse(adata.X):
                expr_values = np.array(adata.X[spot_idx, :].todense()).flatten()
            else:
                expr_values = np.array(adata.X[spot_idx, :]).flatten()
            
            top_indices = np.argsort(expr_values)[::-1][:limit]
            top_genes = []
            for gene_idx in top_indices:
                if expr_values[gene_idx] > 0:
                    top_genes.append({
                        "name": str(adata.var_names[gene_idx]),
                        "value": float(expr_values[gene_idx])
                    })
            return top_genes
        except Exception as e:
            logger.error(f"获取基因表达值失败: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"获取基因表达值失败: {str(e)}"
            )

    # -------- Raw QC / expression preview for h5ad (front-end SpatialVisualization) -------- #
    def _get_obs_values(self, adata, column: str, fallback: Optional[Iterable[float]] = None) -> List[float]:
        if column in adata.obs.columns:
            return [float(x) for x in adata.obs[column].tolist()]
        if fallback is not None:
            return [float(x) for x in fallback]
        return []

    def _compute_counts(self, adata, cell_indices: List[int]) -> List[float]:
        try:
            if sparse.issparse(adata.X):
                sub = adata.X[cell_indices, :]
                return [float(x) for x in sub.sum(axis=1).A.flatten()]
            sub = adata.X[cell_indices, :]
            return [float(v) for v in sub.sum(axis=1)]
        except Exception as e:
            logger.warning(f"计算counts失败: {e}")
            return [0.0 for _ in cell_indices]

    def _compute_n_genes(self, adata, cell_indices: List[int]) -> List[float]:
        try:
            if sparse.issparse(adata.X):
                sub = adata.X[cell_indices, :]
                return [int((row > 0).sum()) for row in sub]
            sub = adata.X[cell_indices, :]
            return [int((row > 0).sum()) for row in sub]
        except Exception as e:
            logger.warning(f"计算n_genes失败: {e}")
            return [0 for _ in cell_indices]

    def _compute_pct_mt(self, adata, cell_indices: List[int]) -> List[float]:
        try:
            mt_mask = [str(g).upper().startswith("MT-") for g in adata.var_names]
            if not any(mt_mask):
                return []
            if sparse.issparse(adata.X):
                sub = adata.X[cell_indices, :]
                total = sub.sum(axis=1).A.flatten()
                mt_vals = sub[:, mt_mask].sum(axis=1).A.flatten()
            else:
                sub = adata.X[cell_indices, :]
                total = sub.sum(axis=1)
                mt_vals = sub[:, mt_mask].sum(axis=1)
            pct = []
            for t, m in zip(total, mt_vals):
                pct.append(float(m / t * 100) if t > 0 else 0.0)
            return pct
        except Exception as e:
            logger.warning(f"计算pct_mt失败: {e}")
            return []

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
        """
        提供原始表达和QC预览，返回与前端 SpatialVisualization 约定的数据结构。
        """
        if not genes:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="genes 不能为空")

        file_path = self._get_file_path(file_id, user_id)
        adata = self._load_adata(file_id, file_path)
        adata = self._normalize_adata_names(adata)

        # 统一转内存以便切片
        if hasattr(adata, "filename") and adata.filename is not None:
            adata = adata.to_memory()

        # 匹配基因
        genes_found = []
        gene_indices = []
        for g in genes:
            if g in adata.var_names:
                genes_found.append(g)
                gene_indices.append(adata.var_names.get_loc(g))
        if not gene_indices:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="未找到任一输入基因")

        # 细胞采样
        total_cells = adata.n_obs
        cell_indices = list(range(total_cells))
        if max_cells and total_cells > max_cells:
            cell_indices = cell_indices[:max_cells]

        # 切片基因与细胞
        adata_subset = adata[cell_indices, gene_indices]

        # 表达矩阵 (dense list)
        if sparse.issparse(adata_subset.X):
            expr = adata_subset.X.toarray().tolist()
        else:
            expr = adata_subset.X.tolist()

        # qc
        qc = {}
        if return_qc:
            qc["counts"] = self._get_obs_values(
                adata, "total_counts", fallback=self._compute_counts(adata, cell_indices)
            )[: len(cell_indices)]
            qc["n_genes"] = self._get_obs_values(
                adata, "n_genes", fallback=self._compute_n_genes(adata, cell_indices)
            )[: len(cell_indices)]
            pct_mt = self._get_obs_values(adata, "pct_counts_mt", fallback=self._compute_pct_mt(adata, cell_indices))
            if pct_mt:
                qc["pct_mt"] = pct_mt[: len(cell_indices)]

        # coords
        coords = None
        if return_coords:
            key = None
            embed_method = (embed_method or "umap").lower()
            if embed_method == "umap" and "X_umap" in adata.obsm:
                key = "X_umap"
            elif embed_method == "pca" and "X_pca" in adata.obsm:
                key = "X_pca"
            elif embed_method == "tsne" and "X_tsne" in adata.obsm:
                key = "X_tsne"
            elif "X_umap" in adata.obsm:
                key = "X_umap"
            elif "X_pca" in adata.obsm:
                key = "X_pca"
            if key:
                arr = adata.obsm[key]
                coords = [[float(arr[i, 0]), float(arr[i, 1])] for i in cell_indices[: arr.shape[0]]]

        return {
            "meta": {
                "total_cells": total_cells,
                "total_genes": adata.n_vars,
                "genes_found": genes_found,
                "has_mt": bool(qc.get("pct_mt")) if return_qc else False
            },
            "qc": qc if return_qc else {},
            "cells": [str(adata.obs_names[i]) for i in cell_indices],
            "genes": genes_found,
            "expression": expr,
            "coords": coords,
        }

    def download_raw_h5ad(
        self,
        file_id: str,
        user_id: str,
        genes: Optional[List[str]] = None,
        cell_id: Optional[str] = None
    ) -> str:
        """
        生成子集 h5ad 文件并返回临时路径。
        """
        file_path = self._get_file_path(file_id, user_id)
        adata = self._load_adata(file_id, file_path)
        if hasattr(adata, "filename") and adata.filename is not None:
            adata = adata.to_memory()

        # 细胞子集
        if cell_id:
            if cell_id not in adata.obs_names:
                raise HTTPException(status.HTTP_404_NOT_FOUND, detail="cell_id 不存在")
            adata = adata[[cell_id], :]

        # 基因子集
        if genes:
            keep = [g for g in genes if g in adata.var_names]
            if not keep:
                raise HTTPException(status.HTTP_404_NOT_FOUND, detail="所选基因不存在")
            adata = adata[:, keep]

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".h5ad")
        tmp_path = tmp.name
        tmp.close()
        adata.write_h5ad(tmp_path)
        return tmp_path
    
    def get_gene_list(
        self,
        file_id: str,
        user_id: str,
        query: Optional[str] = None
    ) -> List[str]:
        """
        获取文件的可用基因列表（单切片模式）
        
        1. 去除重名基因（如果有重名，保留第一个）
        2. 筛选高可变基因并返回
        
        Args:
            file_id: 文件ID
            user_id: 用户ID
            query: 搜索关键词（可选）
            
        Returns:
            高可变基因列表（已去重）
        """
        file_path = self._get_file_path(file_id, user_id)
        adata = self._load_adata(file_id, file_path)
        
        # 规范化名称（处理重复和类型问题）
        adata = self._normalize_adata_names(adata)
        
        # 1. 去除重名基因（如果有重名，保留第一个出现的）
        gene_names = list(adata.var_names)
        seen_genes = {}
        unique_genes = []
        duplicate_indices = []
        
        for idx, gene_name in enumerate(gene_names):
            gene_str = str(gene_name)
            if gene_str not in seen_genes:
                seen_genes[gene_str] = idx
                unique_genes.append(gene_name)
            else:
                duplicate_indices.append(idx)
                logger.debug(f"发现重名基因: {gene_str} (索引 {idx} 和 {seen_genes[gene_str]})")
        
        if duplicate_indices:
            logger.info(f"发现 {len(duplicate_indices)} 个重名基因，已去除")
        
        # # 2. 筛选高可变基因
        # # 检查是否已经计算过高可变基因
        # # 注意：在backed='r'模式下，需要先检查是否已有highly_variable列
        # has_hvg_column = 'highly_variable' in adata.var.columns

        # if not has_hvg_column:
        #     logger.info("未找到高可变基因标记，开始计算...")
        #     try:
        #         # 为了不修改backed模式的原始数据，我们需要创建一个视图或复制
        #         # 但为了性能，我们先尝试直接计算（scanpy会处理backed模式）
        #         n_top_genes = min(2000, adata.n_vars)

        #         # 如果adata是backed模式，需要先加载到内存
        #         if hasattr(adata, 'filename') and adata.filename is not None:
        #             logger.debug("检测到backed模式，加载到内存用于计算高可变基因")
        #             # 使用to_memory()加载到内存
        #             adata_memory = adata.to_memory()
        #             sc.pp.highly_variable_genes(
        #                 adata_memory,
        #                 n_top_genes=n_top_genes,
        #                 flavor='seurat_v3',
        #                 inplace=True
        #             )
        #             # 使用计算结果
        #             hvg_mask = adata_memory.var['highly_variable'].values
        #         else:
        #             sc.pp.highly_variable_genes(
        #                 adata,
        #                 n_top_genes=n_top_genes,
        #                 flavor='seurat_v3',
        #                 inplace=True
        #             )
        #             hvg_mask = adata.var['highly_variable'].values

        #         logger.info(f"计算完成，找到 {hvg_mask.sum()} 个高可变基因")
        #     except Exception as e:
        #         logger.warning(f"计算高可变基因失败: {e}，返回所有基因")
        #         # 如果计算失败，标记所有基因为高可变
        #         hvg_mask = np.ones(len(gene_names), dtype=bool)
        # else:
        #     # 直接使用已有的highly_variable列
        #     hvg_mask = adata.var['highly_variable'].values
        
        # 直接返回所有基因，不进行高可变基因筛选
        all_genes_mask = np.ones(len(gene_names), dtype=bool)
        
        # 筛选出既是唯一基因又是高可变基因的基因
        result_genes = []
        for idx, gene_name in enumerate(gene_names):
            # 只保留唯一基因（不在duplicate_indices中）且是高可变基因的
            if idx not in duplicate_indices and all_genes_mask[idx]:
                result_genes.append(gene_name)
        
        logger.info(f"获取到 {len(result_genes)} 个唯一基因（已去重）")
        
        # 3. 应用查询过滤（如果有）
        if query:
            query_lower = query.lower()
            result_genes = [g for g in result_genes if query_lower in str(g).lower()]
            logger.debug(f"查询过滤后剩余 {len(result_genes)} 个基因")
        
        # 转换为字符串列表并排序
        result = sorted([str(g) for g in result_genes])
        
        return result
    
    def get_gene_expression(
        self,
        file_id: str,
        gene_name: str,
        user_id: str
    ) -> List[Dict[str, Any]]:
        """获取指定基因在所有Spots中的表达值"""
        file_path = self._get_file_path(file_id, user_id)
        adata = self._load_adata(file_id, file_path)
        
        # 检查基因是否存在
        if gene_name not in adata.var_names:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"基因 {gene_name} 不存在"
            )
        
        gene_idx = adata.var_names.get_loc(gene_name)
        
        # 获取所有spots的表达值
        expression_data = []
        
        try:
            # 获取表达值向量
            gene_vector = adata.X[:, gene_idx]
            
            # 统一转换为密集数组
            if sparse.issparse(gene_vector):
                expr_values = gene_vector.toarray().flatten()
            else:
                expr_values = gene_vector.flatten()
            
            # 批量构建结果，更高效
            spot_ids = [str(x) for x in adata.obs_names]
            values = expr_values.astype(float)
            
            expression_data = [
                {"spotId": spot_id, "value": value}
                for spot_id, value in zip(spot_ids, values)
            ]
            
            return expression_data
            
        except Exception as e:
            logger.error(f"获取基因表达值失败: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"获取基因表达值失败: {str(e)}"
            )

# 全局服务实例
_spatial_service: Optional[SpatialService] = None


def get_spatial_service() -> SpatialService:
    """获取全局空间服务实例"""
    global _spatial_service
    if _spatial_service is None:
        _spatial_service = SpatialService()
    return _spatial_service

