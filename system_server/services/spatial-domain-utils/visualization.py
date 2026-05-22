"""
空间域可视化模块
生成各种可视化图表
使用 scanpy 进行所有绘图
"""
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, List
import logging
import os
import warnings

try:
    import scanpy as sc
    from anndata import AnnData
    HAS_SCANPY = True
except ImportError:
    HAS_SCANPY = False
    raise ImportError("scanpy is required for visualization. Please install it: pip install scanpy")

logger = logging.getLogger(__name__)

# 设置 scanpy 绘图参数
sc.settings.set_figure_params(dpi=300, facecolor='white', figsize=(10, 10))


def plot_spatial_domains(
    adata,
    domain_key: str = 'cluster_label',
    spatial_key: str = 'spatial',
    output_path: str = None,
    figsize: tuple = (10, 10),
    dpi: int = 300,
    show_boundaries: bool = False,
    boundaries: Dict = None,
    use_background: bool = True,
    image_alpha: float = 0.5
) -> str:
    """
    绘制空间域分布图（使用 scanpy）
    
    Parameters:
    -----------
    adata : AnnData
        包含域标签的AnnData对象
    domain_key : str
        域标签列名
    spatial_key : str
        空间坐标键名
    output_path : str
        输出文件路径
    figsize : tuple
        图像大小
    dpi : int
        分辨率
    show_boundaries : bool
        是否显示边界（暂不支持，保留参数以便将来扩展）
    boundaries : Dict
        边界信息（暂不支持，保留参数以便将来扩展）
    use_background : bool
        是否使用切片背景（如果可用）
    image_alpha : float
        背景图像透明度（0-1之间）
    
    Returns:
    --------
    output_path : str
        输出文件路径
    """
    if not HAS_SCANPY:
        raise ImportError("scanpy is required for visualization")
    
    if spatial_key not in adata.obsm_keys():
        raise ValueError(f"空间坐标键 '{spatial_key}' 不存在")
    
    if domain_key not in adata.obs.columns:
        raise ValueError(f"域标签列 '{domain_key}' 不存在")
    
    # 设置输出路径
    if output_path is None:
        output_path = 'spatial_domains.png'
    
    # 设置 scanpy 绘图参数
    sc.settings.figdir = os.path.dirname(output_path) if os.path.dirname(output_path) else '.'
    sc.settings.figsize = figsize
    sc.settings.dpi = dpi
    
    # 使用 scanpy 绘制空间图
    # 确保空间坐标在 obsm 中
    if spatial_key not in adata.obsm:
        raise ValueError(f"空间坐标键 '{spatial_key}' 不在 adata.obsm 中")
    
    # 使用 scanpy 的 spatial 绘图函数
    # scanpy 的 save 参数会添加前缀，我们需要处理文件名
    save_name = os.path.basename(output_path).replace('.png', '')
    
    # 检查是否有library_id，如果没有则需要提供spot_size
    has_library_id = False
    if 'spatial' in adata.uns:
        spatial_dict = adata.uns['spatial']
        if isinstance(spatial_dict, dict):
            # 检查是否有任何library_id
            for lib_id in spatial_dict.keys():
                if isinstance(spatial_dict[lib_id], dict) and 'images' in spatial_dict[lib_id]:
                    has_library_id = True
                    break
    
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            # 准备绘图参数
            plot_kwargs = {
                'color': domain_key,
                'img_key': 'hires' if use_background else None,
                'alpha': image_alpha if use_background else 0.7,
                'size': 1.5,
                'show': False,
                'save': save_name
            }
            
            # 如果没有library_id，需要提供spot_size
            if not has_library_id:
                # 计算spot_size：基于空间坐标的范围
                spatial_coords = adata.obsm[spatial_key]
                coord_range = np.max(spatial_coords, axis=0) - np.min(spatial_coords, axis=0)
                # spot_size应该与坐标范围成比例，默认使用较小的范围
                spot_size = min(coord_range) * 0.01  # 约为最小范围的1%
                plot_kwargs['spot_size'] = spot_size
                plot_kwargs['library_id'] = None
            else:
                plot_kwargs['library_id'] = None  # 自动检测
            
            sc.pl.spatial(adata, **plot_kwargs)
            
            # scanpy 会自动保存图片，格式为: {figdir}/spatial_{save_name}.png
            scanpy_output = os.path.join(sc.settings.figdir, f"spatial_{save_name}.png")
            if os.path.exists(scanpy_output) and scanpy_output != output_path:
                import shutil
                shutil.move(scanpy_output, output_path)
        except Exception as e:
            logger.warning(f"使用 scanpy 绘图时出错: {e}，尝试使用备用方法")
            # 如果 scanpy 失败，可以回退到基础方法（但这里我们要求必须使用 scanpy）
            raise
    
    return output_path


def plot_domain_boundaries(
    adata,
    boundaries: Dict,
    spatial_key: str = 'spatial',
    output_path: str = None,
    figsize: tuple = (10, 10),
    dpi: int = 300,
    use_background: bool = True,
    image_alpha: float = 0.5
) -> str:
    """
    绘制域边界轮廓图（使用 scanpy）
    注意：边界绘制功能有限，主要使用 scanpy 的空间绘图
    
    Parameters:
    -----------
    adata : AnnData
        AnnData对象
    boundaries : Dict
        边界信息（用于创建边界标签）
    spatial_key : str
        空间坐标键名
    output_path : str
        输出文件路径
    figsize : tuple
        图像大小
    dpi : int
        分辨率
    use_background : bool
        是否使用切片背景
    image_alpha : float
        背景图像透明度
    
    Returns:
    --------
    output_path : str
        输出文件路径
    """
    if not HAS_SCANPY:
        raise ImportError("scanpy is required for visualization")
    
    if spatial_key not in adata.obsm_keys():
        raise ValueError(f"空间坐标键 '{spatial_key}' 不存在")
    
    # 创建边界标签列
    boundary_label_key = '_boundary_domain'
    if boundary_label_key not in adata.obs.columns:
        # 为每个细胞分配边界域标签
        boundary_labels = pd.Series(['None'] * adata.n_obs, index=adata.obs.index)
        spatial_coords = adata.obsm[spatial_key]
        
        for domain, boundary_info in boundaries.items():
            boundary_coords = boundary_info.get('coords', [])
            if len(boundary_coords) > 0:
                # 简单方法：标记边界附近的点
                boundary_array = np.array(boundary_coords)
                # 这里简化处理，实际可以使用更复杂的边界检测
                # 暂时标记所有点，后续可以改进
                pass
        
        adata.obs[boundary_label_key] = boundary_labels
    
    # 设置输出路径
    if output_path is None:
        output_path = 'domain_boundaries.png'
    
    # 设置 scanpy 绘图参数
    sc.settings.figdir = os.path.dirname(output_path) if os.path.dirname(output_path) else '.'
    sc.settings.figsize = figsize
    sc.settings.dpi = dpi
    
    # 使用 scanpy 绘制空间图
    save_name = os.path.basename(output_path).replace('.png', '')
    
    # 检查是否有library_id，如果没有则需要提供spot_size
    has_library_id = False
    if 'spatial' in adata.uns:
        spatial_dict = adata.uns['spatial']
        if isinstance(spatial_dict, dict):
            # 检查是否有任何library_id
            for lib_id in spatial_dict.keys():
                if isinstance(spatial_dict[lib_id], dict) and 'images' in spatial_dict[lib_id]:
                    has_library_id = True
                    break
    
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            # 准备绘图参数
            plot_kwargs = {
                'color': boundary_label_key,
                'img_key': 'hires' if use_background else None,
                'alpha': image_alpha if use_background else 0.7,
                'size': 1.5,
                'show': False,
                'save': save_name
            }
            
            # 如果没有library_id，需要提供spot_size
            if not has_library_id:
                # 计算spot_size：基于空间坐标的范围
                spatial_coords = adata.obsm[spatial_key]
                coord_range = np.max(spatial_coords, axis=0) - np.min(spatial_coords, axis=0)
                # spot_size应该与坐标范围成比例，默认使用较小的范围
                spot_size = min(coord_range) * 0.01  # 约为最小范围的1%
                plot_kwargs['spot_size'] = spot_size
                plot_kwargs['library_id'] = None
            else:
                plot_kwargs['library_id'] = None  # 自动检测
            
            sc.pl.spatial(adata, **plot_kwargs)
            
            # 检查 scanpy 保存的文件路径
            scanpy_output = os.path.join(sc.settings.figdir, f"spatial_{save_name}.png")
            if os.path.exists(scanpy_output) and scanpy_output != output_path:
                import shutil
                shutil.move(scanpy_output, output_path)
        except Exception as e:
            logger.warning(f"使用 scanpy 绘图时出错: {e}")
            raise
    
    # 清理临时列
    if boundary_label_key in adata.obs.columns:
        adata.obs.drop(columns=[boundary_label_key], inplace=True)
    
    return output_path


def plot_domain_genes_heatmap(
    domain_genes: Dict,
    adata: Optional[AnnData] = None,
    output_path: str = None,
    figsize: tuple = (12, 8),
    dpi: int = 300,
    n_top_genes: int = 10
) -> str:
    """
    绘制域特异性基因热图（使用 scanpy）
    
    Parameters:
    -----------
    domain_genes : Dict
        域特异性基因信息，格式：{domain: {'genes': [...], 'scores': [...]}}
    adata : AnnData, optional
        如果提供，将使用实际的基因表达数据；否则创建临时数据
    output_path : str
        输出文件路径
    figsize : tuple
        图像大小
    dpi : int
        分辨率
    n_top_genes : int
        每个域显示的Top N基因
    
    Returns:
    --------
    output_path : str
        输出文件路径
    """
    if not HAS_SCANPY:
        raise ImportError("scanpy is required for visualization")
    
    # 收集所有基因
    all_genes = []
    domain_list = []
    for domain, genes_info in domain_genes.items():
        genes = genes_info.get('genes', [])[:n_top_genes]
        all_genes.extend(genes)
        domain_list.extend([f'Domain_{domain}'] * len(genes))
    
    if len(all_genes) == 0:
        logger.warning("没有域特异性基因数据，跳过热图绘制")
        if output_path is None:
            output_path = 'domain_genes_heatmap.png'
        # 使用 scanpy 创建空图
        temp_adata = AnnData(X=np.zeros((1, 1)))
        temp_adata.var_names = ['dummy']
        temp_adata.obs_names = ['dummy']
        sc.settings.figdir = os.path.dirname(output_path) if os.path.dirname(output_path) else '.'
        sc.settings.figsize = figsize
        sc.settings.dpi = dpi
        # scanpy 没有直接的空图功能，使用简单的热图
        return output_path
    
    # 去重但保持顺序
    unique_genes = []
    seen = set()
    for gene in all_genes:
        if gene not in seen:
            unique_genes.append(gene)
            seen.add(gene)
    
    # 创建临时 AnnData 对象用于热图
    if adata is None:
        # 创建基于分数的临时数据
        n_genes = len(unique_genes)
        n_domains = len(domain_genes)
        heatmap_matrix = np.zeros((n_genes, n_domains))
        
        gene_to_idx = {gene: i for i, gene in enumerate(unique_genes)}
        domain_to_idx = {domain: i for i, domain in enumerate(domain_genes.keys())}
        
        for domain, genes_info in domain_genes.items():
            genes = genes_info.get('genes', [])[:n_top_genes]
            scores = genes_info.get('scores', [])[:n_top_genes]
            domain_idx = domain_to_idx[domain]
            
            for gene, score in zip(genes, scores):
                if gene in gene_to_idx:
                    gene_idx = gene_to_idx[gene]
                    heatmap_matrix[gene_idx, domain_idx] = score
        
        # 创建临时 AnnData
        temp_adata = AnnData(X=heatmap_matrix.T)
        temp_adata.var_names = unique_genes
        temp_adata.obs_names = [f'Domain_{d}' for d in domain_genes.keys()]
        groupby_key = '_domain_group'
        temp_adata.obs[groupby_key] = temp_adata.obs_names
    else:
        # 使用实际数据
        temp_adata = adata.copy()
        # 确保基因存在
        available_genes = [g for g in unique_genes if g in temp_adata.var_names]
        if len(available_genes) == 0:
            logger.warning("提供的 adata 中没有找到域特异性基因")
            return output_path
        unique_genes = available_genes
        groupby_key = None
        # 尝试找到域标签列
        for key in temp_adata.obs.columns:
            if 'domain' in key.lower() or 'cluster' in key.lower():
                groupby_key = key
                break
    
    # 设置输出路径
    if output_path is None:
        output_path = 'domain_genes_heatmap.png'
    
    # 设置 scanpy 绘图参数
    sc.settings.figdir = os.path.dirname(output_path) if os.path.dirname(output_path) else '.'
    sc.settings.figsize = figsize
    sc.settings.dpi = dpi
    
    # 使用 scanpy 绘制热图
    save_name = os.path.basename(output_path).replace('.png', '')
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            if groupby_key is not None:
                sc.pl.heatmap(
                    temp_adata,
                    var_names=unique_genes[:50],  # 限制基因数量
                    groupby=groupby_key,
                    show=False,
                    save=save_name
                )
                scanpy_output = os.path.join(sc.settings.figdir, f"heatmap_{save_name}.png")
            else:
                # 如果没有分组，使用矩阵图
                sc.pl.matrixplot(
                    temp_adata,
                    var_names=unique_genes[:50],
                    show=False,
                    save=save_name
                )
                scanpy_output = os.path.join(sc.settings.figdir, f"matrixplot_{save_name}.png")
            
            # 检查 scanpy 保存的文件路径并移动
            if os.path.exists(scanpy_output) and scanpy_output != output_path:
                import shutil
                shutil.move(scanpy_output, output_path)
        except Exception as e:
            logger.warning(f"使用 scanpy 绘图时出错: {e}")
            raise
    
    return output_path


def plot_domain_statistics(
    stats: Dict,
    output_path: str = None,
    figsize: tuple = (10, 6),
    dpi: int = 300
) -> str:
    """
    绘制域统计图（使用 scanpy）
    使用 violin plot 或 dotplot 来显示域大小分布
    
    Parameters:
    -----------
    stats : Dict
        域统计信息，应包含 'domain_details' 键
    output_path : str
        输出文件路径
    figsize : tuple
        图像大小
    dpi : int
        分辨率
    
    Returns:
    --------
    output_path : str
        输出文件路径
    """
    if not HAS_SCANPY:
        raise ImportError("scanpy is required for visualization")
    
    # 处理 domain_details（可能是字典或列表）
    domain_details = stats.get('domain_details', {})
    if isinstance(domain_details, dict):
        domain_details = list(domain_details.values())
    
    if len(domain_details) == 0:
        logger.warning("没有域统计信息，跳过统计图绘制")
        if output_path is None:
            output_path = 'domain_statistics.png'
        return output_path
    
    # 提取域和大小信息
    domains = [d.get('domain', d.get('Domain', 'Unknown')) for d in domain_details]
    sizes = [d.get('n_cells', d.get('n_cells', 0)) for d in domain_details]
    
    # 创建临时 AnnData 对象用于可视化
    # 使用一个虚拟基因，值为域大小
    n_domains = len(domains)
    # 创建数据：每个域作为一个"细胞"，域大小作为"表达值"
    X = np.array(sizes).reshape(-1, 1)
    
    temp_adata = AnnData(X=X)
    temp_adata.obs_names = [f'Domain_{d}' for d in domains]
    temp_adata.var_names = ['cell_count']
    temp_adata.obs['domain'] = domains
    temp_adata.obs['domain_label'] = [f'Domain {d}' for d in domains]
    
    # 设置输出路径
    if output_path is None:
        output_path = 'domain_statistics.png'
    
    # 设置 scanpy 绘图参数
    sc.settings.figdir = os.path.dirname(output_path) if os.path.dirname(output_path) else '.'
    sc.settings.figsize = figsize
    sc.settings.dpi = dpi
    
    # 使用 scanpy 的 dotplot 或 violin plot 来显示统计信息
    save_name = os.path.basename(output_path).replace('.png', '')
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            # 使用 dotplot 显示域大小
            sc.pl.dotplot(
                temp_adata,
                var_names=['cell_count'],
                groupby='domain_label',
                show=False,
                save=save_name
            )
            
            # 检查 scanpy 保存的文件路径
            scanpy_output = os.path.join(sc.settings.figdir, f"dotplot_{save_name}.png")
            if os.path.exists(scanpy_output) and scanpy_output != output_path:
                import shutil
                shutil.move(scanpy_output, output_path)
        except Exception as e:
            logger.warning(f"使用 scanpy 绘图时出错: {e}")
            raise
    
    return output_path

