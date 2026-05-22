"""
SpatialDE 空间差异表达分析算法实现
基于 SpatialDE Python 包 (https://github.com/Teichlab/SpatialDE)
用于识别在空间上具有显著差异表达的基因
"""
import numpy as np
import pandas as pd
import logging
from typing import Dict, Any, Optional, Tuple

try:
    import anndata as ad
    import scanpy as sc
    HAS_ANNDATA = True
except ImportError:
    HAS_ANNDATA = False
    logging.warning("anndata/scanpy 未安装")

try:
    import SpatialDE
    import SpatialDE.base as spatialde_base
    try:
        import SpatialDE.util as spatialde_util
    except ImportError:
        spatialde_util = None
    HAS_SPATIALDE = True
except ImportError:
    HAS_SPATIALDE = False
    logging.warning("SpatialDE 未安装，请运行: pip install spatialde")
    spatialde_base = None
    spatialde_util = None

# 初始化 logger
logger = logging.getLogger(__name__)

# 在模块级别修复 scipy 兼容性问题（必须在导入 SpatialDE 之前）
import scipy
# 将缺失的 scipy 函数映射到 numpy
_scipy_functions = {
    'argsort': np.argsort,
    'zeros_like': np.zeros_like,
    'ones_like': np.ones_like,
    'array': np.array,
    'asarray': np.asarray,
    'dot': np.dot,
    'sum': np.sum,
    'mean': np.mean,
    'std': np.std,
    'sqrt': np.sqrt,
    'log': np.log,
    'exp': np.exp,
    'arange': np.arange,
}
for func_name, func_impl in _scipy_functions.items():
    if not hasattr(scipy, func_name):
        setattr(scipy, func_name, func_impl)
logger.info("Patched scipy module with numpy functions for SpatialDE compatibility (module level)")


def _apply_spatialde_patches():
    """
    修复 SpatialDE 与新版 pandas 和 scipy 的兼容性问题
    参考: https://www.jianshu.com/p/cfe0ace931a2
    """
    if not HAS_SPATIALDE or spatialde_base is None:
        return
    
    # scipy 兼容性 patch 已在模块级别应用，这里不需要重复
    
    # Patch 1: 修复 get_l_limits 函数
    if not hasattr(spatialde_base.get_l_limits, '_patched'):
        original_get_l_limits = spatialde_base.get_l_limits
        
        def patched_get_l_limits(X):
            """修复版本的 get_l_limits，确保所有数据都是 numpy 数组"""
            if isinstance(X, pd.DataFrame):
                X = X.to_numpy()
            elif isinstance(X, pd.Series):
                X = X.to_numpy()
            elif hasattr(X, 'values'):
                X = np.asarray(X.values)
            else:
                X = np.asarray(X)
            return original_get_l_limits(X)
        
        patched_get_l_limits._patched = True
        spatialde_base.get_l_limits = patched_get_l_limits
        logger.info("Patched SpatialDE get_l_limits function for pandas compatibility")
    
    # Patch 2: 修复 SE_kernel 函数
    if not hasattr(spatialde_base.SE_kernel, '_patched'):
        original_SE_kernel = spatialde_base.SE_kernel
        
        def patched_SE_kernel(X, lengthscale):
            """修复版本的 SE_kernel，确保所有数据都是 numpy 数组"""
            if isinstance(X, pd.DataFrame):
                X = X.to_numpy()
            elif isinstance(X, pd.Series):
                X = X.to_numpy()
            elif hasattr(X, 'values'):
                X = np.asarray(X.values)
            else:
                X = np.asarray(X)
            
            if isinstance(lengthscale, pd.Series):
                lengthscale = lengthscale.to_numpy()
            elif isinstance(lengthscale, pd.DataFrame):
                lengthscale = lengthscale.to_numpy()
            elif hasattr(lengthscale, 'values'):
                lengthscale = np.asarray(lengthscale.values)
            else:
                lengthscale = np.asarray(lengthscale)
            
            return original_SE_kernel(X, lengthscale)
        
        patched_SE_kernel._patched = True
        spatialde_base.SE_kernel = patched_SE_kernel
        logger.info("Patched SpatialDE SE_kernel function for pandas compatibility")
    
    # Patch 3: 修复 scipy.argsort 问题（SpatialDE.util.qvalue 使用 sp.argsort，但新版本 scipy 没有）
    if spatialde_util is not None and hasattr(spatialde_util, 'qvalue'):
        if not hasattr(spatialde_util.qvalue, '_patched'):
            original_qvalue = spatialde_util.qvalue
            
            def patched_qvalue(pv):
                """修复版本的 qvalue，直接使用 numpy 函数，不依赖 scipy"""
                import scipy as sp
                # 临时添加缺失的函数到 scipy
                if not hasattr(sp, 'arange'):
                    sp.arange = np.arange
                if not hasattr(sp, 'argsort'):
                    sp.argsort = np.argsort
                if not hasattr(sp, 'zeros_like'):
                    sp.zeros_like = np.zeros_like
                try:
                    return original_qvalue(pv)
                finally:
                    # 清理临时添加的函数（如果之前不存在）
                    pass  # 保留这些函数，因为可能在其他地方也需要
            
            patched_qvalue._patched = True
            spatialde_util.qvalue = patched_qvalue
            logger.info("Patched SpatialDE qvalue function for scipy compatibility (using numpy directly)")


def perform_spatial_de_analysis(
    adata: ad.AnnData,
    spatial_key: str = "spatial",
    min_counts: int = 1,
    min_cells: int = 10,
) -> Tuple[pd.DataFrame, ad.AnnData]:
    """
    使用 SpatialDE 进行空间差异表达分析
    
    Parameters:
    -----------
    adata : AnnData
        输入数据，必须包含空间坐标和基因表达矩阵（已预处理）
    spatial_key : str
        空间坐标键名，默认为 "spatial"
    min_counts : int
        基因的最小总计数阈值
    min_cells : int
        基因必须在至少多少个细胞中表达
    
    Returns:
    --------
    results_df : pd.DataFrame
        SpatialDE 分析结果，包含以下列：
        - g: 基因名
        - l: 最优长度尺度参数
        - LLR: 对数似然比
        - pval: p 值
        - qval: 校正后的 p 值（FDR）
        - FSV: 空间方差分数
        - BIC: 贝叶斯信息准则
    adata : AnnData
        处理后的数据
    """
    if not HAS_ANNDATA:
        raise ImportError("anndata/scanpy 未安装，无法进行空间差异分析")
    
    if not HAS_SPATIALDE:
        raise ImportError("SpatialDE 未安装，请运行: pip install spatialde")
    
    # 检查空间坐标
    if spatial_key not in adata.obsm_keys():
        for key in ['X_spatial', 'spatial_coords']:
            if key in adata.obsm_keys():
                spatial_key = key
                break
        else:
            raise ValueError(f"未找到空间坐标，请确保数据包含 obsm['{spatial_key}'] 或 obsm['X_spatial']")
    
    # 复制数据避免修改原始数据
    adata = adata.copy()
    
    logger.info(f"开始 SpatialDE 空间差异表达分析")
    logger.info(f"输入数据: {adata.n_obs} 个细胞/spot, {adata.n_vars} 个基因")
    logger.info("假设输入数据已经预处理完成，跳过标准化和高变基因筛选步骤")
    
    # 准备表达矩阵和坐标
    if hasattr(adata.X, 'toarray'):
        expr_matrix = adata.X.toarray()
    else:
        expr_matrix = adata.X.copy()
    
    coords = adata.obsm[spatial_key]
    
    # 检查数据维度
    if expr_matrix.shape[0] != coords.shape[0]:
        raise ValueError(f"表达矩阵行数 ({expr_matrix.shape[0]}) 与坐标行数 ({coords.shape[0]}) 不匹配")
    
    # 基因筛选：最小计数和最小细胞数
    gene_counts = expr_matrix.sum(axis=0)
    cell_counts = (expr_matrix > 0).sum(axis=0)
    
    min_counts_mask = gene_counts >= min_counts
    min_cells_mask = cell_counts >= min_cells
    
    # 合并筛选条件
    final_mask = min_counts_mask & min_cells_mask
    logger.info(f"经过筛选后，保留 {final_mask.sum()} 个基因（总基因数: {adata.n_vars}）")
    logger.info(f"基因计数统计: min={gene_counts.min()}, max={gene_counts.max()}, mean={gene_counts.mean():.2f}")
    logger.info(f"细胞表达统计: min={cell_counts.min()}, max={cell_counts.max()}, mean={cell_counts.mean():.2f}")
    
    # 使用筛选后的数据（假设已经预处理）
    expr_matrix_filtered = expr_matrix[:, final_mask]
    
    # 获取筛选后的基因名
    gene_names = adata.var_names[final_mask].tolist()
    
    logger.info(f"最终用于分析的基因数: {len(gene_names)}")
    if len(gene_names) > 0:
        logger.info(f"前10个基因名: {gene_names[:10]}")
        logger.info(f"后10个基因名: {gene_names[-10:]}")
    else:
        logger.warning("警告：没有基因通过筛选条件！")
    
    # 应用 pandas 兼容性 patch（在准备数据之前）
    _apply_spatialde_patches()
    
    # 准备 SpatialDE 输入格式
    # SpatialDE 需要：
    # - sample_info: DataFrame with columns ['x', 'y'] 和 index 为样本名
    # - expression_data: DataFrame with genes as columns and samples as rows
    # 注意：确保坐标是 numpy 数组，避免 pandas 多维索引问题
    coords_array = np.asarray(coords)
    # 确保 x 和 y 是 numpy 数组，不是 pandas Series
    x_coords = np.asarray(coords_array[:, 0], dtype=np.float64)
    y_coords = np.asarray(coords_array[:, 1], dtype=np.float64) if coords_array.shape[1] > 1 else np.zeros(coords_array.shape[0], dtype=np.float64)
    
    sample_info = pd.DataFrame(
        {
            'x': x_coords,
            'y': y_coords
        },
        index=adata.obs_names
    )
    
    # 确保表达矩阵是 numpy 数组
    expr_matrix_array = np.asarray(expr_matrix_filtered, dtype=np.float64)
    expression_data = pd.DataFrame(
        expr_matrix_array,
        index=adata.obs_names,
        columns=gene_names
    )
    
    logger.info(f"准备运行 SpatialDE 分析")
    logger.info(f"Expression data shape: {expression_data.shape}")
    logger.info(f"Expression data columns (first 20): {list(expression_data.columns[:20])}")
    logger.info(f"Sample info shape: {sample_info.shape}")
    logger.info(f"Sample info columns: {list(sample_info.columns)}")
    
    # 运行 SpatialDE
    # 注意：SpatialDE.run() 的参数顺序是 (sample_info, expression_data)，不是 (expression_data, sample_info)！
    try:
        results = SpatialDE.run(sample_info, expression_data)
        logger.info(f"SpatialDE 分析完成，检测到 {len(results)} 个基因的结果")
        logger.info(f"Results columns: {list(results.columns)}")
        if len(results) > 0:
            logger.info(f"Results gene names (first 10): {list(results['g'].head(10)) if 'g' in results.columns else 'N/A'}")
    except Exception as e:
        logger.error(f"SpatialDE 分析失败: {e}")
        raise RuntimeError(f"SpatialDE 分析失败: {str(e)}")
    
    # 确保结果包含必要的列
    required_columns = ['g', 'LLR', 'pval', 'qval']
    missing_columns = [col for col in required_columns if col not in results.columns]
    if missing_columns:
        logger.warning(f"结果缺少列: {missing_columns}")
    
    # 更新 adata 的 var，标记哪些基因被分析
    adata.var['spatialde_analyzed'] = False
    adata.var.loc[final_mask, 'spatialde_analyzed'] = True
    
    # 将结果添加到 adata.uns
    adata.uns['spatialde_results'] = results.to_dict('list')
    
    logger.info("SpatialDE 分析完成")
    
    return results, adata

