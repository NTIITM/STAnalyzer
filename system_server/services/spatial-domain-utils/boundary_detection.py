"""
域边界识别模块
使用Alpha Shape算法识别空间域的边界
"""
import numpy as np
from typing import Dict, Any, List, Tuple
import logging

try:
    from scipy.spatial import ConvexHull
    from scipy.spatial.distance import pdist
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    logging.warning("scipy 未安装，边界识别功能可能受限")

try:
    from shapely.geometry import Point, MultiPoint
    from shapely.ops import unary_union
    HAS_SHAPELY = True
except ImportError:
    HAS_SHAPELY = False

logger = logging.getLogger(__name__)


def detect_domain_boundaries(
    spatial_coords: np.ndarray,
    domain_labels: np.ndarray,
    method: str = "alpha_shape",
    alpha: float = None,
    smoothness: float = 0.5
) -> Dict[str, Any]:
    """
    识别空间域的边界
    
    Parameters:
    -----------
    spatial_coords : np.ndarray
        空间坐标 (n_cells, 2)
    domain_labels : np.ndarray
        域标签 (n_cells,)
    method : str
        边界识别方法：'convex_hull', 'alpha_shape', 'contour'
    alpha : float, optional
        Alpha Shape参数（仅当method='alpha_shape'时使用）
    smoothness : float
        边界平滑度 (0.0-1.0)
    
    Returns:
    --------
    boundaries : Dict[str, Any]
        包含每个域的边界信息
    """
    if not HAS_SCIPY:
        raise ImportError("scipy 未安装，无法进行边界识别")
    
    if method != "convex_hull" and not HAS_SHAPELY:
        logger.warning("shapely 未安装，使用简化的凸包方法")
        method = "convex_hull"
    
    boundaries = {}
    unique_domains = np.unique(domain_labels)
    
    for domain in unique_domains:
        try:
            if domain == -1 or (isinstance(domain, (int, float)) and np.isnan(domain)):  # 跳过未分类的细胞
                continue
        except (TypeError, ValueError):
            pass
        
        domain_mask = domain_labels == domain
        domain_coords = spatial_coords[domain_mask]
        
        if len(domain_coords) < 3:
            # 点太少，无法形成边界
            boundaries[str(domain)] = {
                'coords': domain_coords.tolist(),
                'method': method,
                'n_points': len(domain_coords)
            }
            continue
        
        if method == "convex_hull":
            boundary_coords = _convex_hull_boundary(domain_coords)
        elif method == "alpha_shape" and HAS_SHAPELY:
            boundary_coords = _alpha_shape_boundary(domain_coords, alpha)
        elif method == "contour" and HAS_SHAPELY:
            boundary_coords = _contour_boundary(domain_coords, smoothness)
        else:
            # 回退到凸包
            boundary_coords = _convex_hull_boundary(domain_coords)
        
        boundaries[str(domain)] = {
            'coords': boundary_coords.tolist() if isinstance(boundary_coords, np.ndarray) else boundary_coords,
            'method': method,
            'n_points': len(domain_coords),
            'boundary_points': len(boundary_coords)
        }
    
    return boundaries


def _convex_hull_boundary(coords: np.ndarray) -> np.ndarray:
    """使用凸包算法识别边界"""
    if not HAS_SCIPY:
        return coords
    try:
        hull = ConvexHull(coords)
        boundary_coords = coords[hull.vertices]
        # 按顺序排列
        return boundary_coords
    except Exception as e:
        logger.warning(f"凸包计算失败: {e}，返回原始坐标")
        return coords


def _alpha_shape_boundary(coords: np.ndarray, alpha: float = None) -> List[Tuple[float, float]]:
    """使用Alpha Shape算法识别边界（更精确）"""
    # 目前使用凸包作为简化实现
    # 未来可以集成更复杂的alpha shape算法
    return _convex_hull_boundary(coords)


def _contour_boundary(coords: np.ndarray, smoothness: float = 0.5) -> List[Tuple[float, float]]:
    """使用轮廓检测识别边界"""
    if not HAS_SHAPELY:
        return _convex_hull_boundary(coords)
    
    try:
        from scipy.spatial import Voronoi
        
        # 使用Voronoi图识别边界
        vor = Voronoi(coords)
        
        # 提取边界顶点
        boundary_vertices = []
        for ridge in vor.ridge_vertices:
            if -1 not in ridge:  # 排除无限远的顶点
                for v in ridge:
                    if v >= 0:
                        boundary_vertices.append(tuple(vor.vertices[v]))
        
        if len(boundary_vertices) == 0:
            return _convex_hull_boundary(coords)
        
        # 平滑边界（简化实现）
        if smoothness > 0 and len(boundary_vertices) > 3:
            # 使用简单的移动平均平滑
            boundary_array = np.array(boundary_vertices)
            smoothed = boundary_array.copy()
            window = max(1, int(len(boundary_array) * smoothness * 0.1))
            if window > 1:
                for i in range(len(boundary_array)):
                    start = max(0, i - window // 2)
                    end = min(len(boundary_array), i + window // 2 + 1)
                    smoothed[i] = np.mean(boundary_array[start:end], axis=0)
                return smoothed.tolist()
        
        return boundary_vertices
    except Exception as e:
        logger.warning(f"轮廓检测失败: {e}，回退到凸包")
        return _convex_hull_boundary(coords)

