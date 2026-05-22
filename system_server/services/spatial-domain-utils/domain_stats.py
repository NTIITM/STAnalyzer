"""
域统计信息计算模块
计算空间域的统计信息
"""
import numpy as np
import pandas as pd
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


def calculate_domain_statistics(
    adata,
    domain_key: str = 'cluster_label',
    spatial_key: str = 'spatial'
) -> Dict[str, Any]:
    """
    计算空间域的统计信息
    
    Parameters:
    -----------
    adata : AnnData
        包含表达数据和域标签的AnnData对象
    domain_key : str
        存储域标签的obs列名
    spatial_key : str
        存储空间坐标的obsm键名
    
    Returns:
    --------
    stats : Dict[str, Any]
        域统计信息
    """
    if domain_key not in adata.obs.columns:
        raise ValueError(f"域标签列 '{domain_key}' 不存在")
    
    domain_labels = adata.obs[domain_key].values
    unique_domains = np.unique(domain_labels)
    unique_domains = unique_domains[unique_domains != -1]  # 排除未分类
    
    n_cells = len(domain_labels)
    n_domains = len(unique_domains)
    
    # 基本统计
    domain_sizes = []
    domain_details = []
    
    # 获取空间坐标（如果存在）
    has_spatial = False
    spatial_coords = None
    if spatial_key in adata.obsm_keys():
        spatial_coords = adata.obsm[spatial_key]
        has_spatial = True
    
    for domain in unique_domains:
        domain_mask = domain_labels == domain
        domain_size = np.sum(domain_mask)
        domain_percentage = (domain_size / n_cells) * 100
        domain_sizes.append(domain_size)
        
        # 确保所有值都是Python原生类型，避免h5ad保存时的类型转换错误
        domain_info = {
            'domain': str(domain),
            'n_cells': int(domain_size.item() if hasattr(domain_size, 'item') else domain_size),
            'percentage': float(domain_percentage.item() if hasattr(domain_percentage, 'item') else domain_percentage)
        }
        
        # 空间范围（如果存在空间坐标）
        # 注意：h5ad格式不支持嵌套字典，需要展平为顶层键
        # 同时确保所有numpy类型都转换为Python原生类型
        if has_spatial:
            domain_coords = spatial_coords[domain_mask]
            if len(domain_coords) > 0:
                x_min_val = np.min(domain_coords[:, 0])
                x_max_val = np.max(domain_coords[:, 0])
                y_min_val = np.min(domain_coords[:, 1])
                y_max_val = np.max(domain_coords[:, 1])
                # 确保转换为Python原生float类型
                domain_info['spatial_x_min'] = float(x_min_val.item() if hasattr(x_min_val, 'item') else x_min_val)
                domain_info['spatial_x_max'] = float(x_max_val.item() if hasattr(x_max_val, 'item') else x_max_val)
                domain_info['spatial_y_min'] = float(y_min_val.item() if hasattr(y_min_val, 'item') else y_min_val)
                domain_info['spatial_y_max'] = float(y_max_val.item() if hasattr(y_max_val, 'item') else y_max_val)
                domain_info['spatial_width'] = float(domain_info['spatial_x_max'] - domain_info['spatial_x_min'])
                domain_info['spatial_height'] = float(domain_info['spatial_y_max'] - domain_info['spatial_y_min'])
        
        domain_details.append(domain_info)
    
    domain_sizes = np.array(domain_sizes)
    
    # 域大小分布统计
    # 确保所有值都是Python原生类型
    size_stats = {
        'min': int(np.min(domain_sizes).item() if hasattr(np.min(domain_sizes), 'item') else np.min(domain_sizes)),
        'max': int(np.max(domain_sizes).item() if hasattr(np.max(domain_sizes), 'item') else np.max(domain_sizes)),
        'mean': float(np.mean(domain_sizes).item() if hasattr(np.mean(domain_sizes), 'item') else np.mean(domain_sizes)),
        'median': float(np.median(domain_sizes).item() if hasattr(np.median(domain_sizes), 'item') else np.median(domain_sizes)),
        'std': float(np.std(domain_sizes).item() if hasattr(np.std(domain_sizes), 'item') else np.std(domain_sizes))
    }
    
    # 域间相似性（基于平均表达）
    domain_similarity = None
    if adata.X is not None:
        try:
            # 计算每个域的平均表达
            domain_means = []
            for domain in unique_domains:
                domain_mask = domain_labels == domain
                if hasattr(adata.X, 'toarray'):
                    domain_mean = np.mean(adata.X[domain_mask].toarray(), axis=0)
                else:
                    domain_mean = np.mean(adata.X[domain_mask], axis=0)
                domain_means.append(domain_mean)
            
            domain_means = np.array(domain_means)
            
            # 计算域间相关性
            from scipy.stats import pearsonr
            n_domains = len(unique_domains)
            similarity_matrix = np.zeros((n_domains, n_domains))
            for i in range(n_domains):
                for j in range(n_domains):
                    if i == j:
                        similarity_matrix[i, j] = 1.0
                    else:
                        corr, _ = pearsonr(domain_means[i], domain_means[j])
                        similarity_matrix[i, j] = corr
            
            mean_sim_val = np.mean(similarity_matrix[np.triu_indices(n_domains, k=1)])
            domain_similarity = {
                'matrix': similarity_matrix.tolist(),
                'domains': [str(d) for d in unique_domains],
                'mean_similarity': float(mean_sim_val.item() if hasattr(mean_sim_val, 'item') else mean_sim_val)
            }
        except Exception as e:
            logger.warning(f"计算域间相似性失败: {e}")
    
    stats = {
        'n_domains': n_domains,
        'n_cells': n_cells,
        'domain_size_distribution': size_stats,
        'domain_details': domain_details,
        'domain_similarity': domain_similarity,
        'has_spatial': has_spatial
    }
    
    return stats

