"""
域特异性基因分析模块
识别每个空间域的特异性基因
"""
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional
import logging
from scipy import stats

try:
    import scanpy as sc
    HAS_SCANPY = True
except ImportError:
    HAS_SCANPY = False
    logging.warning("scanpy 未安装，将使用基础统计方法")

logger = logging.getLogger(__name__)


def find_domain_specific_genes(
    adata,
    domain_key: str = 'cluster_label',
    n_top_genes: int = 20,
    min_fold_change: float = 1.5,
    method: str = 'wilcoxon',
    use_raw: bool = True
) -> Dict[str, Any]:
    """
    识别每个空间域的特异性基因
    
    Parameters:
    -----------
    adata : AnnData
        包含表达数据和域标签的AnnData对象
    domain_key : str
        存储域标签的obs列名
    n_top_genes : int
        每个域返回的Top N基因数
    min_fold_change : float
        最小fold change阈值
    method : str
        差异分析方法：'wilcoxon', 't-test', 'logreg'
    use_raw : bool
        是否使用raw数据
    
    Returns:
    --------
    domain_genes : Dict[str, Any]
        每个域的特异性基因信息
    """
    if domain_key not in adata.obs.columns:
        raise ValueError(f"域标签列 '{domain_key}' 不存在")
    
    domain_labels = adata.obs[domain_key].values
    unique_domains = np.unique(domain_labels)
    unique_domains = unique_domains[unique_domains != -1]  # 排除未分类
    
    domain_genes = {}
    
    # 获取表达矩阵
    # Access raw counts from layers['counts'] (preprocessing service stores raw data here)
    if use_raw:
        if 'counts' in adata.layers:
            X = adata.layers['counts']
            gene_names = adata.var_names
        elif adata.raw is not None:
            # Fallback: use raw if counts layer is not available
        X = adata.raw.X
        gene_names = adata.raw.var_names
        else:
            X = adata.X
            gene_names = adata.var_names
    else:
        X = adata.X
        gene_names = adata.var_names
    
    # 转换为密集矩阵（如果必要）
    if hasattr(X, 'toarray'):
        X = X.toarray()
    
    for domain in unique_domains:
        domain_mask = domain_labels == domain
        other_mask = ~domain_mask
        
        if np.sum(domain_mask) < 3 or np.sum(other_mask) < 3:
            logger.warning(f"域 {domain} 的细胞数太少，跳过")
            continue
        
        # 计算差异表达
        if method == 'wilcoxon' and HAS_SCANPY:
            try:
                # 使用scanpy的差异分析
                sc.tl.rank_genes_groups(
                    adata,
                    groupby=domain_key,
                    groups=[str(domain)],
                    method='wilcoxon',
                    use_raw=use_raw,
                    n_genes=n_top_genes * 2  # 多取一些以便过滤
                )
                
                # 提取结果
                result = adata.uns['rank_genes_groups']
                genes = result['names'][str(domain)][:n_top_genes]
                scores = result['scores'][str(domain)][:n_top_genes]
                pvals = result['pvals'][str(domain)][:n_top_genes]
                pvals_adj = result['pvals_adj'][str(domain)][:n_top_genes]
                logfoldchanges = result['logfoldchanges'][str(domain)][:n_top_genes]
                
                # 计算fold change
                fold_changes = np.power(2, logfoldchanges)
                
                # 过滤
                valid_mask = fold_changes >= min_fold_change
                genes = genes[valid_mask]
                scores = scores[valid_mask]
                pvals = pvals[valid_mask]
                pvals_adj = pvals_adj[valid_mask]
                fold_changes = fold_changes[valid_mask]
                
            except Exception as e:
                logger.warning(f"Scanpy差异分析失败: {e}，使用基础方法")
                genes, scores, pvals, pvals_adj, fold_changes = _basic_differential_analysis(
                    X, gene_names, domain_mask, other_mask, n_top_genes, min_fold_change
                )
        else:
            # 使用基础统计方法
            genes, scores, pvals, pvals_adj, fold_changes = _basic_differential_analysis(
                X, gene_names, domain_mask, other_mask, n_top_genes, min_fold_change
            )
        
        domain_genes[str(domain)] = {
            'genes': genes.tolist() if isinstance(genes, np.ndarray) else list(genes),
            'scores': scores.tolist() if isinstance(scores, np.ndarray) else list(scores),
            'pvals': pvals.tolist() if isinstance(pvals, np.ndarray) else list(pvals),
            'pvals_adj': pvals_adj.tolist() if isinstance(pvals_adj, np.ndarray) else list(pvals_adj),
            'fold_changes': fold_changes.tolist() if isinstance(fold_changes, np.ndarray) else list(fold_changes),
            'n_genes': len(genes)
        }
    
    return domain_genes


def _basic_differential_analysis(
    X: np.ndarray,
    gene_names: pd.Index,
    domain_mask: np.ndarray,
    other_mask: np.ndarray,
    n_top_genes: int,
    min_fold_change: float
) -> tuple:
    """基础差异表达分析（Wilcoxon秩和检验）"""
    n_genes = X.shape[1]
    scores = np.zeros(n_genes)
    pvals = np.ones(n_genes)
    fold_changes = np.ones(n_genes)
    
    domain_expr = X[domain_mask, :]
    other_expr = X[other_mask, :]
    
    # 计算平均表达
    domain_mean = np.mean(domain_expr, axis=0)
    other_mean = np.mean(other_expr, axis=0)
    
    # 避免除零
    other_mean = np.maximum(other_mean, 1e-10)
    fold_changes = domain_mean / other_mean
    
    # Wilcoxon秩和检验
    for i in range(n_genes):
        try:
            stat, pval = stats.ranksums(domain_expr[:, i], other_expr[:, i])
            scores[i] = stat
            pvals[i] = pval
        except Exception:
            scores[i] = 0
            pvals[i] = 1.0
    
    # 多重检验校正（Benjamini-Hochberg）
    try:
        from statsmodels.stats.multitest import multipletests
        _, pvals_adj, _, _ = multipletests(pvals, method='fdr_bh')
    except ImportError:
        # 如果没有statsmodels，使用简单的Bonferroni校正
        pvals_adj = np.minimum(pvals * len(pvals), 1.0)
    
    # 排序和过滤
    valid_mask = fold_changes >= min_fold_change
    valid_indices = np.where(valid_mask)[0]
    
    if len(valid_indices) == 0:
        # 如果没有满足fold change的，返回top genes
        top_indices = np.argsort(scores)[::-1][:n_top_genes]
    else:
        # 按score排序
        valid_scores = scores[valid_indices]
        sorted_valid = np.argsort(valid_scores)[::-1]
        top_indices = valid_indices[sorted_valid[:n_top_genes]]
    
    genes = gene_names[top_indices].values
    scores = scores[top_indices]
    pvals = pvals[top_indices]
    pvals_adj = pvals_adj[top_indices]
    fold_changes = fold_changes[top_indices]
    
    return genes, scores, pvals, pvals_adj, fold_changes

