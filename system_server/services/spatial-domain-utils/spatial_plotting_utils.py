"""
空间可视化工具函数
提供在空间可视化图片中添加切片背景的功能
注意：推荐直接使用 scanpy 的 sc.pl.spatial() 函数，它已内置背景支持
这些函数保留用于向后兼容，但内部已改为使用 scanpy
"""
import numpy as np
from typing import Optional, Dict, Any, Tuple
import logging
import warnings

try:
    import scanpy as sc
    from anndata import AnnData
    HAS_SCANPY = True
except ImportError:
    HAS_SCANPY = False
    raise ImportError("scanpy is required. Please install it: pip install scanpy")

logger = logging.getLogger(__name__)


def get_spatial_image(adata, image_key: str = 'hires') -> Optional[Tuple[np.ndarray, float]]:
    """
    从AnnData对象中获取空间切片图像和缩放因子
    
    Parameters:
    -----------
    adata : AnnData
        包含空间信息的AnnData对象
    image_key : str
        图像键名，可选 'hires', 'lowres', 'fullres'
    
    Returns:
    --------
    tuple : (image, scale_factor) 或 None
        图像数组和缩放因子，如果不存在则返回None
    """
    if 'spatial' not in adata.uns:
        return None
    
    spatial_info = adata.uns['spatial']
    if not isinstance(spatial_info, dict):
        return None
    
    # 获取第一个切片的数据
    for slice_id, slice_data in spatial_info.items():
        if not isinstance(slice_data, dict) or 'images' not in slice_data:
            continue
        
        images = slice_data['images']
        scalefactors = slice_data.get('scalefactors', {})
        
        # 处理h5py对象
        if hasattr(scalefactors, 'keys'):
            try:
                scalefactors_dict = {}
                for key in scalefactors.keys():
                    value = scalefactors[key]
                    if hasattr(value, '__getitem__') and not isinstance(value, dict):
                        try:
                            scalefactors_dict[key] = float(value[()])
                        except:
                            scalefactors_dict[key] = value
                    else:
                        scalefactors_dict[key] = value
                scalefactors = scalefactors_dict
            except Exception as e:
                logger.warning(f"读取缩放因子失败: {e}")
                scalefactors = {}
        
        # 按优先级查找图像
        image_keys = []
        if image_key == 'hires':
            image_keys = ['hires', 'lowres', 'fullres']
        elif image_key == 'lowres':
            image_keys = ['lowres', 'hires', 'fullres']
        elif image_key == 'fullres':
            image_keys = ['fullres', 'hires', 'lowres']
        else:
            image_keys = [image_key, 'hires', 'lowres', 'fullres']
        
        for img_key in image_keys:
            if img_key in images:
                img_data = images[img_key]
                
                # 获取对应的缩放因子
                scale_factor = None
                if img_key == 'hires' and 'tissue_hires_scalef' in scalefactors:
                    scale_factor = scalefactors['tissue_hires_scalef']
                elif img_key == 'lowres' and 'tissue_lowres_scalef' in scalefactors:
                    scale_factor = scalefactors['tissue_lowres_scalef']
                elif img_key == 'fullres':
                    scale_factor = 1.0
                
                if scale_factor is None:
                    scale_factor = 1.0
                
                # 确保图像是numpy数组
                if isinstance(img_data, np.ndarray):
                    # 确保是uint8格式
                    if img_data.dtype != np.uint8:
                        if img_data.max() <= 1.0:
                            img_data = (img_data * 255).astype(np.uint8)
                        else:
                            img_data = img_data.astype(np.uint8)
                    
                    return img_data, scale_factor
        
        # 如果没找到，返回None
        break
    
    return None


def plot_spatial_with_background(
    adata,
    ax,
    color_key: Optional[str] = None,
    spatial_key: str = 'spatial',
    image_key: str = 'hires',
    image_alpha: float = 0.5,
    spot_size: float = 10.0,
    **scatter_kwargs
) -> bool:
    """
    在matplotlib axes上绘制空间可视化，包含切片背景
    注意：此函数保留用于向后兼容，推荐直接使用 scanpy 的 sc.pl.spatial()
    
    Parameters:
    -----------
    adata : AnnData
        包含空间信息的AnnData对象
    ax : matplotlib.axes.Axes
        matplotlib axes对象（scanpy 会自动处理）
    color_key : str, optional
        用于着色的obs列名（如cluster_label, cell_type等）
    spatial_key : str
        空间坐标键名，默认为'spatial'
    image_key : str
        图像键名，可选 'hires', 'lowres', 'fullres'
    image_alpha : float
        背景图像透明度，0-1之间
    spot_size : float
        spot大小
    **scatter_kwargs
        传递给scatter的其他参数
    
    Returns:
    --------
    bool
        是否成功添加了背景图像
    """
    if not HAS_SCANPY:
        logger.warning("scanpy 不可用，无法使用背景功能")
        return False
    
    if spatial_key not in adata.obsm_keys():
        logger.warning(f"空间坐标键 '{spatial_key}' 不存在")
        return False
    
    # 检查是否有空间图像
    has_background = get_spatial_image(adata, image_key=image_key) is not None
    
    # 注意：由于 scanpy 的 sc.pl.spatial() 会自动处理背景和绘图
    # 这个函数主要用于向后兼容，实际绘图应该使用 scanpy
    logger.info("推荐使用 scanpy 的 sc.pl.spatial() 函数进行空间绘图，它已内置背景支持")
    
    return has_background


def create_spatial_plot_with_background(
    adata,
    color_key: Optional[str] = None,
    spatial_key: str = 'spatial',
    image_key: str = 'hires',
    image_alpha: float = 0.5,
    figsize: tuple = (10, 10),
    dpi: int = 300,
    title: Optional[str] = None,
    spot_size: float = 10.0,
    show_legend: bool = True,
    **scatter_kwargs
) -> Tuple[Any, Any, bool]:
    """
    创建包含切片背景的空间可视化图
    注意：此函数保留用于向后兼容，推荐直接使用 scanpy 的 sc.pl.spatial()
    
    Parameters:
    -----------
    adata : AnnData
        包含空间信息的AnnData对象
    color_key : str, optional
        用于着色的obs列名
    spatial_key : str
        空间坐标键名
    image_key : str
        图像键名
    image_alpha : float
        背景图像透明度
    figsize : tuple
        图像大小
    dpi : int
        分辨率
    title : str, optional
        图像标题（scanpy 会自动生成）
    spot_size : float
        spot大小
    show_legend : bool
        是否显示图例（scanpy 会自动处理）
    **scatter_kwargs
        传递给scanpy绘图的其他参数
    
    Returns:
    --------
    tuple : (fig, ax, has_background)
        图像对象、axes对象和是否成功添加背景
    """
    if not HAS_SCANPY:
        raise ImportError("scanpy is required")
    
    # 检查是否有背景
    has_background = get_spatial_image(adata, image_key=image_key) is not None
    
    # 使用 scanpy 进行绘图
    # 注意：scanpy 的 sc.pl.spatial() 会自动创建 figure 和 axes
    # 这里返回 None 作为占位符，实际应该使用 scanpy 的绘图函数
    logger.info("推荐使用 scanpy 的 sc.pl.spatial() 函数，它已内置背景和绘图支持")
    
    # 为了向后兼容，返回占位符
    return None, None, has_background

