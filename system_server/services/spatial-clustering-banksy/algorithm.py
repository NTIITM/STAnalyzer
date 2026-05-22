"""
BANKSY空间域识别算法实现
基于官方 BANKSY 库 (https://github.com/prabhakarlab/Banksy_py)
BANKSY (BANKSY: Spatial Clustering with Neighbor-Aware Gene Expression)
结合空间邻域信息和基因表达进行空间域识别
"""
import numpy as np
import pandas as pd
import logging
import sys
import os
from typing import Dict, Any, Optional

try:
    import anndata as ad
    import scanpy as sc
    HAS_ANNDATA = True
except ImportError:
    HAS_ANNDATA = False
    logging.warning("anndata/scanpy 未安装")

# 初始化 logger
logger = logging.getLogger(__name__)

# 尝试导入 BANKSY 库
HAS_BANKSY = False

# 首先尝试从环境变量或常见路径导入
banksy_paths = [
    os.path.join(os.path.dirname(__file__), 'banksy', 'src'),  # 当前目录下的 banksy/src
    os.path.join(os.path.dirname(__file__), 'banksy'),  # 当前目录下的 banksy
    '/app/Banksy_py',  # Docker 环境中的路径
    os.path.join(os.path.dirname(__file__), 'Banksy_py'),  # 当前目录下的 Banksy_py
    os.path.join(os.path.dirname(__file__), '..', '..', '..', 'Banksy_py'),
    os.path.join(os.path.dirname(__file__), '..', '..', 'Banksy_py'),
    os.path.expanduser('~/Banksy_py'),
]

# 检查是否有 banksy_path.txt 文件（Docker 环境）
banksy_path_file = '/app/banksy_path.txt'
if os.path.exists(banksy_path_file):
    with open(banksy_path_file, 'r') as f:
        custom_path = f.read().strip()
        if custom_path:
            banksy_paths.insert(0, custom_path)

# 尝试从各个路径导入
for banksy_path in banksy_paths:
    if os.path.exists(banksy_path):
        if banksy_path not in sys.path:
            sys.path.insert(0, banksy_path)
        try:
            from banksy.main import median_dist_to_nearest_neighbour
            from banksy_utils.filter_utils import normalize_total, filter_hvg
            from banksy.initialize_banksy import initialize_banksy
            from banksy.embed_banksy import generate_banksy_matrix
            from banksy.run_banksy import run_banksy_multiparam
            HAS_BANKSY = True
            logger.info(f"成功从 {banksy_path} 导入 BANKSY 库")
            break
        except ImportError as e:
            logger.debug(f"无法从 {banksy_path} 导入 BANKSY: {e}")
            continue

# 如果还没有导入成功，尝试直接从系统路径导入（可能已安装到 site-packages）
if not HAS_BANKSY:
    try:
        from banksy.main import median_dist_to_nearest_neighbour
        from banksy_utils.filter_utils import normalize_total, filter_hvg
        from banksy.initialize_banksy import initialize_banksy
        from banksy.embed_banksy import generate_banksy_matrix
        from banksy.run_banksy import run_banksy_multiparam
        HAS_BANKSY = True
        logger.info("从系统路径导入 BANKSY 库")
    except ImportError:
        HAS_BANKSY = False
        logger.warning("BANKSY 库未安装，请确保已克隆 https://github.com/prabhakarlab/Banksy_py 并添加到 Python 路径")


def detect_spatial_domains_banksy(
    adata: ad.AnnData,
    n_neighbors: int = 15,
    lambda_adj: float = 0.2,
    resolution: float = 1.0,
    algorithm: str = "leiden",
    random_state: int = 0,
    spatial_key: str = "spatial",
    n_pcs: int = 30,
    use_highly_variable: bool = True
) -> ad.AnnData:
    """
    使用BANKSY方法进行空间域识别（基于官方BANKSY库）
    
    Parameters:
    -----------
    adata : AnnData
        输入数据，必须包含空间坐标
    n_neighbors : int
        空间近邻数 (对应 BANKSY 的 k_geom)
    lambda_adj : float
        邻域权重参数 (0-1)，控制邻域信息的影响
    resolution : float
        聚类分辨率
    algorithm : str
        聚类算法：'leiden' 或 'louvain'
    random_state : int
        随机种子
    spatial_key : str
        空间坐标键名
    n_pcs : int
        PCA主成分数
    use_highly_variable : bool
        是否只使用高变基因
    
    Returns:
    --------
    adata : AnnData
        添加了空间域标签的数据
    """
    if not HAS_ANNDATA:
        raise ImportError("anndata/scanpy 未安装，无法进行空间域识别")
    
    if not HAS_BANKSY:
        raise ImportError("BANKSY 库未安装，请确保已克隆 https://github.com/prabhakarlab/Banksy_py 并添加到 Python 路径")
    
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
    
    logger.info(f"开始BANKSY空间域识别，n_neighbors={n_neighbors}, lambda_adj={lambda_adj}")
    
    # 保存原始表达矩阵（如果存在）
    if 'counts' not in adata.layers:
        if hasattr(adata.X, 'toarray'):
            adata.layers['counts'] = adata.X.toarray().copy()
        else:
            adata.layers['counts'] = adata.X.copy()
    
    # 使用 counts 层作为原始计数数据
    adata.X = adata.layers['counts'].copy()
    
    # 准备坐标键（BANKSY 需要 x, y 在 obs 中）
    coord_keys = ['x', 'y', spatial_key]
    adata.obs['x'] = adata.obsm[spatial_key][:, 0]
    adata.obs['y'] = adata.obsm[spatial_key][:, 1]
    
    # 检测数据是否已经预处理
    # 判断标准：
    # 1. 如果 X.max() < 20，通常表示已经标准化
    # 2. 如果存在 'log1p' layer，表示已经 log 变换
    # 3. 如果 var 中有 'highly_variable' 标记，表示已经筛选过高变基因
    is_preprocessed = False
    
    # 检查 X 矩阵的最大值（标准化后的数据通常最大值较小）
    try:
        if hasattr(adata.X, 'max'):
            x_max = float(adata.X.max())
        elif hasattr(adata.X, 'toarray'):
            x_max = float(adata.X.toarray().max())
        else:
            x_max = float(np.max(adata.X))
    except Exception as e:
        logger.warning(f"无法计算 X.max()，假设数据未预处理: {e}")
        x_max = 100  # 设置一个较大的值，表示可能未预处理
    
    # 检查是否有 log1p layer
    has_log1p_layer = 'log1p' in adata.layers
    
    # 检查是否已经筛选过高变基因
    has_hvg_marker = 'highly_variable' in adata.var.columns
    
    # 如果数据已经标准化（最大值较小）或者有 log1p layer，认为已经预处理
    if x_max < 20 or has_log1p_layer:
        is_preprocessed = True
        logger.info(f"检测到数据可能已经预处理：X.max()={x_max:.2f}, has_log1p_layer={has_log1p_layer}")
    
    # 预处理：标准化和筛选高变基因（仅在未预处理时执行）
    if not is_preprocessed:
        logger.info("数据未预处理，开始预处理：标准化和筛选高变基因")
        adata = normalize_total(adata)
        
        if use_highly_variable:
            # 如果已经有高变基因标记，检查是否需要重新筛选
            if has_hvg_marker and adata.var['highly_variable'].sum() > 0:
                logger.info(f"数据已包含高变基因标记，使用现有标记筛选")
                adata_allgenes = adata.copy()
                adata = adata[:, adata.var['highly_variable']]
                logger.info(f"使用现有高变基因标记筛选出 {adata.n_vars} 个高变基因")
            else:
                adata, adata_allgenes = filter_hvg(adata, n_top_genes=2000, flavor="seurat")
                logger.info(f"筛选出 {adata.n_vars} 个高变基因")
        else:
            adata_allgenes = None
    else:
        logger.info("数据已预处理，跳过标准化步骤")
        # 即使已预处理，如果 use_highly_variable=True，仍需要筛选高变基因
        if use_highly_variable:
            if has_hvg_marker and adata.var['highly_variable'].sum() > 0:
                logger.info(f"使用现有高变基因标记筛选")
                adata_allgenes = adata.copy()
                adata = adata[:, adata.var['highly_variable']]
                logger.info(f"使用现有高变基因标记筛选出 {adata.n_vars} 个高变基因")
            else:
                logger.info("数据已预处理但缺少高变基因标记，进行高变基因筛选")
                adata, adata_allgenes = filter_hvg(adata, n_top_genes=2000, flavor="seurat")
                logger.info(f"筛选出 {adata.n_vars} 个高变基因")
        else:
            adata_allgenes = None
    
    # BANKSY 参数设置
    k_geom = n_neighbors  # 空间近邻数
    max_m = 1  # azimuthal transform 的最大阶数
    nbr_weight_decay = "scaled_gaussian"  # 邻居权重衰减方式
    
    # 计算中位距离到最近邻居（用于确定 sigma）
    logger.info("计算空间邻域距离")
    nbrs = median_dist_to_nearest_neighbour(adata, key=spatial_key)
    
    # 初始化 BANKSY
    logger.info("初始化 BANKSY")
    banksy_dict = initialize_banksy(
        adata,
        coord_keys,
        k_geom,
        nbr_weight_decay=nbr_weight_decay,
        max_m=max_m,
        plt_edge_hist=False,
        plt_nbr_weights=False,
        plt_agf_angles=False
    )
    
    # 生成 BANKSY 矩阵
    logger.info(f"生成 BANKSY 矩阵，lambda={lambda_adj}")
    lambda_list = [lambda_adj]
    banksy_dict, banksy_matrix = generate_banksy_matrix(
        adata,
        banksy_dict,
        lambda_list,
        max_m
    )
    
    # 运行 BANKSY 聚类
    logger.info(f"执行 BANKSY 聚类，resolution={resolution}, algorithm={algorithm}")
    resolutions = [resolution]
    pca_dims = [n_pcs]
    
    # 生成随机颜色列表（用于可视化）
    import random
    number_of_colors = 50
    colors = ["#" + ''.join([random.choice('0123456789ABCDEF') for j in range(6)])
              for i in range(number_of_colors)]
    
    # 运行多参数 BANKSY
    results_df = run_banksy_multiparam(
        adata,
        banksy_dict,
        lambda_list,
        resolutions,
        color_list=colors,
        max_m=max_m,
        filepath='/tmp',  # 临时路径，不保存图片
        key=coord_keys,
        pca_dims=pca_dims,
        annotation_key=None,
        max_labels=None,
        cluster_algorithm=algorithm,
        match_labels=False,
        savefig=False,
        add_nonspatial=True,
        variance_balance=False
    )
    
    # 从结果中提取聚类标签
    # results_df 是一个 DataFrame，索引是参数名称（如 'scaled_gaussian_pc30_nc0.20_r0.50'）
    # 每行包含 'labels', 'adata', 'lambda_param' 等信息
    cluster_key = "banksy"
    
    # 构建 BANKSY 结果的参数名称
    lambda_str = f"{lambda_adj:0.2f}"
    resolution_str = f"{resolution:0.2f}"
    pca_str = str(n_pcs)
    
    # 查找 BANKSY 结果行（排除 nonspatial）
    banksy_param_name = f"scaled_gaussian_pc{pca_str}_nc{lambda_str}_r{resolution_str}"
    
    if banksy_param_name not in results_df.index:
        # 尝试查找包含 scaled_gaussian 的行
        matching_rows = [idx for idx in results_df.index if 'scaled_gaussian' in str(idx) and f"_pc{pca_str}_" in str(idx)]
        if matching_rows:
            banksy_param_name = matching_rows[0]
        else:
            # 如果找不到，使用第一个非 nonspatial 的行
            non_nonspatial = [idx for idx in results_df.index if 'nonspatial' not in str(idx)]
            if non_nonspatial:
                banksy_param_name = non_nonspatial[0]
            else:
                # 最后使用第一个结果
                banksy_param_name = results_df.index[0]
    
    logger.info(f"使用参数行: {banksy_param_name}")
    
    # 获取对应的 adata 和 labels
    banksy_adata = results_df.loc[banksy_param_name, 'adata']
    banksy_labels = results_df.loc[banksy_param_name, 'labels']
    
    # 如果 labels 是 Label 对象，提取 dense 数组
    from banksy.labels import Label
    if isinstance(banksy_labels, Label):
        labels_array = banksy_labels.dense
    else:
        labels_array = banksy_labels
    
    # 将聚类结果添加到 adata
    adata.obs[cluster_key] = labels_array
    
    # 复制 BANKSY 嵌入（如果存在）
    if 'reduced_pc_' + str(n_pcs) in banksy_adata.obsm_keys():
        pca_key = 'reduced_pc_' + str(n_pcs)
        adata.obsm['X_banksy'] = banksy_adata.obsm[pca_key].copy()
        # 也保存为 X_pca 以便后续可视化
        adata.obsm['X_pca'] = banksy_adata.obsm[pca_key].copy()
    
    # 复制 UMAP（如果存在）
    if 'X_umap_banksy' in banksy_adata.obsm_keys():
        adata.obsm['X_umap'] = banksy_adata.obsm['X_umap_banksy'].copy()
    elif 'X_umap' in banksy_adata.obsm_keys():
        adata.obsm['X_umap'] = banksy_adata.obsm['X_umap'].copy()
    
    # 恢复原始表达矩阵
    if hasattr(adata.X, 'toarray'):
        adata.X = adata.layers['counts'].toarray() if hasattr(adata.layers['counts'], 'toarray') else adata.layers['counts']
    else:
        adata.X = adata.layers['counts']
    
    # 确保标签是字符串类型
    adata.obs[cluster_key] = adata.obs[cluster_key].astype(str)
    
    n_domains = len(adata.obs[cluster_key].unique())
    logger.info(f"识别到 {n_domains} 个空间域")
    
    return adata
