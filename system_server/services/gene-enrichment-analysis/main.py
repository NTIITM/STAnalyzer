#!/usr/bin/env python3
"""
按簇进行基因富集分析服务 - FastAPI
基于 gseapy.enrichr，对聚类后的空间转录组数据按簇执行富集分析。
从每个簇中提取特征基因（高表达或标记基因），然后对每个簇分别进行富集分析。
"""
import os
import logging
from logging.handlers import RotatingFileHandler
import traceback
import tempfile
import uuid
from typing import Dict, Any, Optional, List, Tuple

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.exceptions import RequestValidationError

import pandas as pd
import numpy as np
from scipy.stats import hypergeom

try:
    import anndata as ad
    HAS_ANNDATA = True
except ImportError:
    HAS_ANNDATA = False
    logging.warning("anndata 未安装，无法读取 h5ad 文件")

try:
    from statsmodels.stats.multitest import multipletests
    HAS_STATSMODELS = True
except ImportError:
    HAS_STATSMODELS = False

try:
    import gseapy as gp
    HAS_GSEAPY = True
except Exception as e:
    logging.warning(f"gseapy 导入失败: {e}")
    HAS_GSEAPY = False

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import seaborn as sns
    plt.rcParams['font.sans-serif'] = ['Arial', 'DejaVu Sans', 'Liberation Sans']
    plt.rcParams['axes.unicode_minus'] = False
    PLOT_AVAILABLE = True
except Exception as e:
    logging.warning(f"可视化包导入失败: {e}")
    PLOT_AVAILABLE = False

def _setup_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    default_dir = os.path.dirname(os.path.abspath(__file__))
    log_dir = os.getenv("LOG_DIR", default_dir)
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "log")
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = []
    fmt = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    sh.setLevel(level)
    fh = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=3)
    fh.setFormatter(fmt)
    fh.setLevel(level)
    root.addHandler(sh)
    root.addHandler(fh)

_setup_logging()
logger = logging.getLogger(__name__)

# 记录 statsmodels 状态
if not HAS_STATSMODELS:
    logger.warning("statsmodels 未安装，将使用简单的 Bonferroni 校正进行多重检验")

app = FastAPI(
    title="按簇进行基因富集分析服务",
    description="使用 gseapy 对聚类后的空间转录组数据按簇进行富集分析（Enrichr），每个簇分别分析并标注簇信息",
    version="2.0.0",
)

OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# GMT 文件目录（本地基因集库）
GMT_DIR = os.getenv("GMT_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "gmt"))
os.makedirs(GMT_DIR, exist_ok=True)

# 是否优先使用本地文件（环境变量控制）
USE_LOCAL_FIRST = os.getenv("USE_LOCAL_GMT", "true").lower() == "true"

try:
    import time
    from starlette.middleware.base import BaseHTTPMiddleware
    class RequestLogMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            start = time.time()
            response = None
            try:
                response = await call_next(request)
                return response
            finally:
                duration = (time.time() - start) * 1000.0
                status = getattr(response, "status_code", -1)
                logger.info("request %s %s -> %s (%.1f ms)",
                            request.method, request.url.path, status, duration)
    app.add_middleware(RequestLogMiddleware)
except Exception as _e:
    logger.debug("中间件初始化失败: %s", _e)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    error_details = exc.errors()
    error_body = exc.body if hasattr(exc, 'body') else None
    logger.error(
        "请求验证失败: %s %s\n错误详情: %s\n请求体: %s",
        request.method,
        request.url.path,
        error_details,
        error_body[:500] if error_body else None,
        exc_info=True
    )
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "message": "请求参数验证失败",
            "error": {
                "error_type": "RequestValidationError",
                "error_message": str(exc),
                "details": error_details,
            },
        },
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(
        "未处理的异常: %s %s\n异常类型: %s\n异常信息: %s",
        request.method,
        request.url.path,
        type(exc).__name__,
        str(exc),
        exc_info=True
    )
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "服务器内部错误",
            "error": {
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            },
        },
    )

def _handle_error(step: str, error: Exception) -> Dict[str, Any]:
    """
    Legacy simple error handler (kept for backward compatibility if imported).
    For new code paths in this service, prefer `_handle_detailed_error` +
    `format_error_info_to_message`, which provide richer diagnostics.
    """
    return _handle_detailed_error(step, error)


def format_error_info_to_message(error_info: Dict[str, Any]) -> str:
    """Format a rich error_info dict into a human‑readable multi‑line message.

    This is aligned with the spatial transcriptomics preprocessing service so that
    callers receive detailed diagnostics, filtering stats (when available),
    and concrete suggestions for parameter adjustments.
    """
    parts = []

    # Basic info
    parts.append(f"Error Type: {error_info.get('error_type', 'Unknown')}")
    parts.append(f"Error Message: {error_info.get('error_message', 'Unknown error')}")

    # Diagnosis
    if "diagnosis" in error_info:
        parts.append(f"\nDiagnosis: {error_info['diagnosis']}")

    # Enrichment statistics context (if any)
    if "enrichment_stats" in error_info:
        stats = error_info["enrichment_stats"]
        parts.append("\nEnrichment Statistics:")
        if "num_input_genes" in stats:
            parts.append(f"  Input genes: {stats.get('num_input_genes', 0):,}")
        if "num_unique_genes" in stats:
            parts.append(f"  Unique genes after deduplication: {stats.get('num_unique_genes', 0):,}")
        if "total_terms" in stats:
            parts.append(f"  Total enriched terms: {stats.get('total_terms', 0):,}")
        if "significant_terms" in stats:
            parts.append(
                f"  Significant terms (p < {stats.get('pval_threshold', 0.05)}): "
                f"{stats.get('significant_terms', 0):,} "
                f"({stats.get('significant_percentage', 0.0):.2f}%)"
            )

    # Suggestions
    if "suggestions" in error_info and error_info["suggestions"]:
        parts.append("\nSuggestions:")
        for idx, suggestion in enumerate(error_info["suggestions"], 1):
            if isinstance(suggestion, dict):
                issue = suggestion.get("issue", "Potential issue")
                recommendations = suggestion.get("recommendations", [])
                parts.append(f"\n  {idx}. {issue}:")
                for rec in recommendations:
                    parts.append(f"     - {rec}")

    # Traceback (optional)
    if "traceback" in error_info and error_info.get("traceback"):
        parts.append(f"\nTraceback:\n{error_info['traceback']}")

    return "\n".join(parts)


def _handle_detailed_error(
    step: str,
    error: Exception,
    include_traceback: bool = True,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Richer error handler providing diagnosis and parameter suggestions.

    This mirrors the spatial‑transcriptomics‑preprocessing service so that
    the frontend receives more helpful error messages and can surface them
    directly to users.
    """
    error_info: Dict[str, Any] = {
        "error": True,
        "step": step,
        "error_type": type(error).__name__,
        "error_message": str(error),
        "suggestions": [],
    }

    if include_traceback:
        error_info["traceback"] = traceback.format_exc()

    if context:
        # Attach raw context for debugging
        error_info["context"] = context

    msg_lower = str(error).lower()

    # 1. Empty / invalid input gene list
    if "no gene" in msg_lower or "empty" in msg_lower or "0 gene" in msg_lower:
        error_info["diagnosis"] = "Input gene list is empty or invalid."
        error_info["suggestions"].append(
            {
                "issue": "Empty or malformed gene list",
                "recommendations": [
                    "Ensure the uploaded file contains a 'gene' column.",
                    "Verify that the file delimiter matches the 'sep' parameter (',' for CSV or '\\t' for TSV).",
                    "Check that at least one non‑empty gene symbol is present after filtering.",
                ],
            }
        )

    # 2. File reading / format problems
    elif "file" in msg_lower or "read" in msg_lower or "parse" in msg_lower or "format" in msg_lower:
        error_info["diagnosis"] = "File reading or format issue."
        error_info["suggestions"].append(
            {
                "issue": "File format mismatch or parsing error",
                "recommendations": [
                    "Confirm the file is a valid CSV/TSV text file and not an Excel or binary format.",
                    "For TSV files, set sep='\\t'; for CSV files, set sep=','.",
                    "Ensure the first row contains column headers, including a 'gene' column.",
                    "Check file encoding (UTF‑8 is recommended).",
                ],
    }
        )

    # 3. Library / organism / engine issues
    elif "library" in msg_lower or "gene_sets" in msg_lower or "organism" in msg_lower:
        error_info["diagnosis"] = "Enrichr library or organism configuration issue."
        recommendations = [
            "Make sure the 'library' parameter is a valid Enrichr gene set name (e.g., 'GO_Biological_Process_2021').",
            "For KEGG analysis, either choose a KEGG_* library explicitly or use engine='kegg' so the service can auto‑select.",
            "Verify that the 'organism' parameter matches what gseapy expects, such as 'Human' or 'Mouse'.",
        ]
        error_info["suggestions"].append(
            {
                "issue": "Invalid library/organism settings",
                "recommendations": recommendations,
            }
        )

    # 4. Network / Enrichr server issues
    elif "connection" in msg_lower or "timeout" in msg_lower or "enrichr" in msg_lower:
        error_info["diagnosis"] = "Network or remote Enrichr service problem."
        error_info["suggestions"].append(
            {
                "issue": "Network connectivity or remote API failure",
                "recommendations": [
                    "Check internet connectivity from the service container to the Enrichr API endpoints.",
                    "Retry later in case the remote service is temporarily unavailable.",
                    "If running in an offline environment, consider using local gene set libraries.",
                ],
            }
        )

    # 5. Memory / resource issues
    elif "memory" in msg_lower or "out of memory" in msg_lower:
        error_info["diagnosis"] = "Insufficient memory to complete enrichment."
        error_info["suggestions"].append(
            {
                "issue": "Input too large or resource limits too strict",
                "recommendations": [
                    "Reduce the number of input genes by pre‑filtering low‑confidence genes.",
                    "Try a smaller or more specific gene set library.",
                    "Increase memory resources available to the service container.",
                ],
            }
        )

    # 6. Generic invalid parameter value issues
    elif "invalid" in msg_lower or "value" in msg_lower:
        error_info["diagnosis"] = "Invalid parameter value."
        error_info["suggestions"].append(
            {
                "issue": "Parameter value out of valid range",
                "recommendations": [
                    "Check that 'sep' is either ',' or '\\t'.",
                    "Ensure 'engine' is one of ['enrichr', 'kegg'].",
                    "Verify that 'organism' is supported by gseapy/enrichr.",
                ],
            }
        )

    # 7. Fallback generic advice
    if not error_info["suggestions"]:
        error_info["suggestions"].append(
            {
                "issue": "Unknown error",
                "recommendations": [
                    "Check the input file format and content carefully.",
                    "Verify all parameters (sep, library, organism, engine) are valid.",
                    "Review the full traceback for more technical details.",
                ],
            }
        )

    logger.error(f"Step {step} failed: {error}", exc_info=include_traceback)
    return error_info

def _read_adata(path: str) -> "ad.AnnData":
    """读取 AnnData/h5ad 文件"""
    if not HAS_ANNDATA:
        raise RuntimeError("anndata 未安装，无法读取 h5ad 文件")
    if not path.endswith(".h5ad"):
        raise ValueError(f"文件必须是 .h5ad 格式，当前文件: {path}")
    return ad.read_h5ad(path)


def _get_clusters(adata: "ad.AnnData", cluster_key: str) -> Tuple[pd.Series, str]:
    """从 AnnData 的 obs 中获取簇标签"""
    if cluster_key in adata.obs:
        clusters = adata.obs[cluster_key].astype(str)
        return clusters, cluster_key
    # 尝试常见的簇列名
    common_keys = ["leiden", "louvain", "cluster", "clusters"]
    for key in common_keys:
        if key in adata.obs:
            logger.info(f"未找到指定的 cluster_key '{cluster_key}'，使用 '{key}' 作为簇标签")
            return adata.obs[key].astype(str), key
    raise ValueError(
        f"未找到簇标签列。指定的 cluster_key='{cluster_key}' 不存在，"
        f"且未找到常见的簇列名（{', '.join(common_keys)}）。"
        f"可用的 obs 列: {', '.join(adata.obs.columns[:10].tolist())}"
    )


def _extract_top_expressed_genes(
    adata: "ad.AnnData", 
    cluster: str, 
    clusters: pd.Series, 
    top_n: int
) -> List[str]:
    """提取指定簇中高表达的 top N 基因"""
    cluster_mask = clusters == cluster
    if cluster_mask.sum() == 0:
        return []
    
    # 计算该簇的平均表达
    cluster_expr = adata[cluster_mask].X
    if hasattr(cluster_expr, "toarray"):
        cluster_expr = cluster_expr.toarray()
    mean_expr = np.mean(cluster_expr, axis=0)
    
    # 获取 top N 基因
    top_indices = np.argsort(mean_expr)[::-1][:top_n]
    top_genes = adata.var_names[top_indices].tolist()
    return top_genes


def _extract_marker_genes(
    adata: "ad.AnnData",
    cluster: str,
    clusters: pd.Series,
    top_n: int,
    min_fold_change: float = 1.5
) -> List[str]:
    """提取指定簇的标记基因（fold change > threshold）"""
    cluster_mask = clusters == cluster
    other_mask = clusters != cluster
    
    if cluster_mask.sum() == 0 or other_mask.sum() == 0:
        return []
    
    # 计算簇内和簇外的平均表达
    cluster_expr = adata[cluster_mask].X
    other_expr = adata[other_mask].X
    
    if hasattr(cluster_expr, "toarray"):
        cluster_expr = cluster_expr.toarray()
    if hasattr(other_expr, "toarray"):
        other_expr = other_expr.toarray()
    
    mean_cluster = np.mean(cluster_expr, axis=0)
    mean_other = np.mean(other_expr, axis=0)
    
    # 避免除零
    mean_other = np.maximum(mean_other, 1e-6)
    
    # 计算 fold change
    fold_change = mean_cluster / mean_other
    
    # 选择 fold change > threshold 的基因
    marker_mask = fold_change >= min_fold_change
    marker_genes = adata.var_names[marker_mask].tolist()
    
    # 按 fold change 排序，取 top N
    if len(marker_genes) > top_n:
        marker_fc = fold_change[marker_mask]
        top_indices = np.argsort(marker_fc)[::-1][:top_n]
        marker_genes = [marker_genes[i] for i in top_indices]
    
    return marker_genes


def find_local_gmt_file(library_name: str) -> Optional[str]:
    """
    查找本地 GMT 文件
    
    Args:
        library_name: 基因集库名称
    
    Returns:
        GMT 文件路径，如果不存在则返回 None
    """
    gmt_file = os.path.join(GMT_DIR, f"{library_name}.gmt")
    if os.path.exists(gmt_file):
        return gmt_file
    return None

def enrich_with_local_files(
    gene_list: list,
    library_list: list,
    organism: str
) -> pd.DataFrame:
    """
    使用本地 GMT 文件进行富集分析（超几何检验）
    
    Args:
        gene_list: 基因列表
        library_list: 基因集库名称列表
        organism: 物种
    
    Returns:
        富集分析结果 DataFrame，格式与 enrichr 输出兼容
    """
    all_results = []
    gene_set = set(gene.upper() for gene in gene_list)  # 转换为大写以便比较
    n_genes = len(gene_set)
    
    # 估计背景基因总数（通常为 20000-25000）
    # 这里使用一个合理的估计值，或者可以从 GMT 文件中统计
    background_size = 20000
    
    for library_name in library_list:
        gmt_file = find_local_gmt_file(library_name)
        if not gmt_file:
            logger.warning(f"本地未找到库文件: {library_name}.gmt，跳过")
            continue
        
        try:
            logger.info(f"使用本地文件进行富集分析: {library_name}")
            
            # 读取 GMT 文件并收集所有基因以估计背景大小
            gene_sets = {}
            all_background_genes = set()
            
            with open(gmt_file, 'r', encoding='utf-8') as f:
                for line in f:
                    parts = line.strip().split('\t')
                    if len(parts) < 3:
                        continue
                    term = parts[0]
                    genes_in_set = [g.upper() for g in parts[2:]]
                    gene_sets[term] = genes_in_set
                    all_background_genes.update(genes_in_set)
            
            # 更新背景大小
            if len(all_background_genes) > background_size:
                background_size = len(all_background_genes)
            
            # 对每个基因集进行超几何检验
            enrichment_results = []
            
            for term, genes_in_pathway in gene_sets.items():
                pathway_genes = set(genes_in_pathway)
                overlap = gene_set & pathway_genes
                n_overlap = len(overlap)
                
                if n_overlap == 0:
                    continue  # 跳过没有重叠的基因集
                
                n_pathway = len(pathway_genes)
                
                # 超几何检验
                # P(X >= n_overlap) = 1 - P(X < n_overlap)
                # 其中 X ~ Hypergeometric(N, K, n)
                # N = 背景基因总数
                # K = 通路中的基因数
                # n = 输入基因数
                # 我们计算 P(X >= n_overlap)
                
                try:
                    # 使用超几何分布的累积分布函数
                    # hypergeom.cdf(k, N, K, n) 返回 P(X <= k)
                    # 所以 P(X >= n_overlap) = 1 - hypergeom.cdf(n_overlap - 1, N, K, n)
                    pvalue = 1 - hypergeom.cdf(n_overlap - 1, background_size, n_pathway, n_genes)
                    
                    # 计算 odds ratio
                    # OR = (n_overlap / (n_genes - n_overlap)) / ((n_pathway - n_overlap) / (background_size - n_pathway - n_genes + n_overlap))
                    if n_overlap < n_genes and (n_pathway - n_overlap) > 0:
                        odds_ratio = (n_overlap / (n_genes - n_overlap)) / \
                                    ((n_pathway - n_overlap) / (background_size - n_pathway - n_genes + n_overlap))
                    else:
                        odds_ratio = float('inf') if n_overlap == n_genes else 0.0
                    
                    # 计算 combined score (类似 Enrichr)
                    # Combined Score = log(pvalue) * z_score
                    # 简化版本：使用 -log10(pvalue) * odds_ratio
                    combined_score = -np.log10(max(pvalue, 1e-300)) * min(odds_ratio, 1000)
                    
                    enrichment_results.append({
                        'Term': term,
                        'Overlap': f"{n_overlap}/{n_pathway}",  # 格式：重叠数/通路总基因数，与Enrichr API保持一致
                        'P-value': pvalue,
                        'Adjusted P-value': pvalue,  # 简化版本，不进行多重检验校正
                        'Odds Ratio': odds_ratio,
                        'Combined Score': combined_score,
                        'Genes': ';'.join(sorted(overlap)),
                        'library': library_name
                    })
                except Exception as e:
                    logger.debug(f"计算 {term} 的统计量时出错: {e}")
                    continue
            
            if enrichment_results:
                df = pd.DataFrame(enrichment_results)
                # 按 P-value 排序
                df = df.sort_values('P-value')
                # 进行 Benjamini-Hochberg 校正
                if HAS_STATSMODELS:
                    _, pvals_corrected, _, _ = multipletests(df['P-value'], method='fdr_bh')
                    df['Adjusted P-value'] = pvals_corrected
                else:
                    # 如果没有 statsmodels，使用简单的 Bonferroni 校正
                    df['Adjusted P-value'] = df['P-value'] * len(df)
                    df['Adjusted P-value'] = df['Adjusted P-value'].clip(upper=1.0)
                all_results.append(df)
            else:
                logger.warning(f"库 {library_name} 未找到富集结果")
                
        except Exception as e:
            logger.error(f"使用本地文件分析库 {library_name} 时出错: {e}", exc_info=True)
            continue
    
    if not all_results:
        return pd.DataFrame()
    
    # 合并所有结果
    combined = pd.concat(all_results, ignore_index=True)
    # 再次按调整后的 P-value 排序
    combined = combined.sort_values('Adjusted P-value')
    return combined

def enrich_with_enrichr_api(
    gene_list: list,
    library_list: list,
    organism: str
) -> pd.DataFrame:
    """
    使用 Enrichr API 进行富集分析（需要网络连接）
    
    Args:
        gene_list: 基因列表
        library_list: 基因集库名称列表
        organism: 物种
    
    Returns:
        富集分析结果 DataFrame
    """
    logger.info("使用 Enrichr API 进行富集分析（需要网络连接）")
    enr = gp.enrichr(gene_list=gene_list, gene_sets=library_list, organism=organism)
    res = enr.results if hasattr(enr, "results") else pd.DataFrame()
    if res is None:
        res = pd.DataFrame()
    return res

def calculate_enrichment_metrics(res: pd.DataFrame, pval_threshold: float = 0.05) -> Dict[str, Any]:
    """计算富集分析质量指标（整合两个服务的统计功能）"""
    metrics = {}
    try:
        if res.empty:
            return metrics
        
        metrics['total_terms'] = len(res)
        
        # 显著性统计
        if 'Adjusted P-value' in res.columns or 'P-value' in res.columns:
            pval_col = 'Adjusted P-value' if 'Adjusted P-value' in res.columns else 'P-value'
            significant = res[res[pval_col] < pval_threshold]
            metrics['significant_terms'] = len(significant)
            metrics['significant_percentage'] = float(len(significant) / len(res) * 100) if len(res) > 0 else 0.0
            metrics['pval_threshold'] = pval_threshold
        
        # P值统计
        if 'P-value' in res.columns:
            pvals = res['P-value'].astype(float).dropna()
            if len(pvals) > 0:
                metrics['pval_stats'] = {
                    'min': float(pvals.min()),
                    'max': float(pvals.max()),
                    'mean': float(pvals.mean()),
                    'median': float(pvals.median()),
                }
        
        # 调整后P值统计
        if 'Adjusted P-value' in res.columns:
            adj_pvals = res['Adjusted P-value'].astype(float).dropna()
            if len(adj_pvals) > 0:
                metrics['adj_pval_stats'] = {
                    'min': float(adj_pvals.min()),
                    'max': float(adj_pvals.max()),
                    'mean': float(adj_pvals.mean()),
                    'median': float(adj_pvals.median()),
                }
        
        # 富集分数统计
        if 'Combined Score' in res.columns:
            metrics['combined_score'] = {
                'min': float(res['Combined Score'].min()),
                'max': float(res['Combined Score'].max()),
                'mean': float(res['Combined Score'].mean()),
                'median': float(res['Combined Score'].median())
            }
        
        # 基因数统计
        if 'Overlap' in res.columns:
            overlap_counts = res['Overlap'].str.split('/').str[0].astype(int)
            metrics['overlap_genes'] = {
                'min': int(overlap_counts.min()),
                'max': int(overlap_counts.max()),
                'mean': float(overlap_counts.mean()),
                'median': float(overlap_counts.median())
            }
        
        # 每个通路的基因数统计（如果存在Genes列）
        if 'Genes' in res.columns:
            genes_col = res['Genes'].astype(str)
            gene_counts = genes_col.str.split(';').str.len()
            metrics['genes_per_pathway_stats'] = {
                'min': int(gene_counts.min()) if len(gene_counts) > 0 else 0,
                'max': int(gene_counts.max()) if len(gene_counts) > 0 else 0,
                'mean': float(gene_counts.mean()) if len(gene_counts) > 0 else 0.0,
                'median': float(gene_counts.median()) if len(gene_counts) > 0 else 0.0,
            }
        
        # Odds Ratio统计
        if 'Odds Ratio' in res.columns:
            odds_ratios = res['Odds Ratio'].astype(float).dropna()
            if len(odds_ratios) > 0:
                metrics['odds_ratio_stats'] = {
                    'min': float(odds_ratios.min()),
                    'max': float(odds_ratios.max()),
                    'mean': float(odds_ratios.mean()),
                    'median': float(odds_ratios.median()),
                }
        
    except Exception as e:
        logger.warning(f"Failed to calculate enrichment metrics: {e}")
    
    return metrics

def generate_enrichment_plots(res: pd.DataFrame, file_id: str, output_dir: str,
                              library: str, pval_threshold: float = 0.05,
                              top_n: int = 20, clusters: Optional[List[str]] = None) -> Dict[str, str]:
    """生成富集分析可视化图（整合两个服务的所有可视化功能）"""
    plot_files = {}
    if not PLOT_AVAILABLE or res.empty:
        return plot_files
    
    try:
        # 准备数据
        res_plot = res.copy()
        pval_col = 'Adjusted P-value' if 'Adjusted P-value' in res_plot.columns else 'P-value'
        if pval_col not in res_plot.columns:
            return plot_files
        
        has_cluster = 'cluster' in res_plot.columns
        
        # 1. Bar plot - Top富集项（按簇展示）
        if has_cluster and clusters:
            # 按簇分别展示
            n_clusters = len(clusters)
            ncols = min(3, n_clusters)
            nrows = int(np.ceil(n_clusters / ncols))
            fig, axes = plt.subplots(nrows, ncols, figsize=(5 * ncols, 4 * nrows))
            axes = np.atleast_1d(axes).flatten()
            
            for idx, cluster_id in enumerate(clusters):
                ax = axes[idx]
                cluster_data = res_plot[res_plot['cluster'] == str(cluster_id)].sort_values(pval_col).head(top_n)
                if cluster_data.empty:
                    ax.axis('off')
                    ax.text(0.5, 0.5, f'Cluster {cluster_id}\nNo enriched terms', 
                           ha='center', va='center', transform=ax.transAxes)
                    continue
                
                cluster_data['-log10_pval'] = -np.log10(cluster_data[pval_col] + 1e-300)
                colors = plt.cm.viridis(np.linspace(0, 1, len(cluster_data)))
                bars = ax.barh(range(len(cluster_data)), cluster_data['-log10_pval'], color=colors, alpha=0.7)
                ax.set_yticks(range(len(cluster_data)))
                term_labels = cluster_data['Term'].tolist()
                ax.set_yticklabels([term[:50] + '...' if len(str(term)) > 50 else str(term) for term in term_labels], fontsize=8)
                ax.set_xlabel('-Log10 P-value', fontsize=10)
                ax.set_title(f'Cluster {cluster_id} - Top {len(cluster_data)} Terms', fontsize=11, fontweight='bold')
                ax.grid(True, alpha=0.3, axis='x')
            
            # 隐藏多余的子图
            for idx in range(n_clusters, len(axes)):
                axes[idx].axis('off')
            
            plt.suptitle(f'Top Enriched Terms by Cluster - {library}', fontsize=14, fontweight='bold', y=0.995)
            plt.tight_layout()
        else:
            # 单图展示（如果没有簇信息）
            res_plot = res_plot.sort_values(pval_col).head(top_n)
            res_plot['-log10_pval'] = -np.log10(res_plot[pval_col] + 1e-300)
            fig, ax = plt.subplots(figsize=(12, max(6, top_n * 0.3)))
            colors = plt.cm.viridis(np.linspace(0, 1, len(res_plot)))
            bars = ax.barh(range(len(res_plot)), res_plot['-log10_pval'], color=colors, alpha=0.7)
            ax.set_yticks(range(len(res_plot)))
            term_labels = res_plot['Term'] if 'Term' in res_plot.columns else res_plot.index
            ax.set_yticklabels([term[:60] + '...' if len(str(term)) > 60 else str(term) for term in term_labels], fontsize=9)
            ax.set_xlabel('-Log10 P-value', fontsize=12)
            ax.set_title(f'Top {top_n} Enriched Terms - {library}', fontsize=14, fontweight='bold')
            ax.grid(True, alpha=0.3, axis='x')
            plt.tight_layout()
        
        bar_id = "enrichment_bar.png"
        bar_path = os.path.join(output_dir, bar_id)
        plt.savefig(bar_path, dpi=300, bbox_inches='tight')
        plt.close()
        plot_files['enrichment_bar'] = bar_id
        logger.info(f"Enrichment bar plot saved: {bar_path}")
        
        # 2. Volcano图（按簇分子图）
        if 'Adjusted P-value' in res.columns and 'Odds Ratio' in res.columns:
            if has_cluster and clusters:
                # 按簇分别展示
                n_clusters = len(clusters)
                ncols = min(3, n_clusters)
                nrows = int(np.ceil(n_clusters / ncols))
                fig, axes = plt.subplots(nrows, ncols, figsize=(5 * ncols, 4 * nrows))
                axes = np.atleast_1d(axes).flatten()
                
                for idx, cluster_id in enumerate(clusters):
                    ax = axes[idx]
                    cluster_data = res[res['cluster'] == str(cluster_id)]
                    if cluster_data.empty:
                        ax.axis('off')
                        ax.text(0.5, 0.5, f'Cluster {cluster_id}\nNo enriched terms', 
                               ha='center', va='center', transform=ax.transAxes)
                        continue
                    
                    adj_pvals = cluster_data['Adjusted P-value'].astype(float)
                    odds_ratios = cluster_data['Odds Ratio'].astype(float)
                    
                    scatter = ax.scatter(odds_ratios, -np.log10(adj_pvals + 1e-300), 
                                       s=50, alpha=0.6, c=adj_pvals, cmap='viridis_r')
                    ax.set_xlabel('Odds Ratio', fontsize=10)
                    ax.set_ylabel('-Log10(Adjusted P-value)', fontsize=10)
                    ax.set_title(f'Cluster {cluster_id}', fontsize=11, fontweight='bold')
                    ax.axhline(y=-np.log10(0.05), color='red', linestyle='--', label='Adj P-value = 0.05')
                    ax.axvline(x=1.0, color='gray', linestyle='--', alpha=0.5)
                    ax.legend(fontsize=8)
                    ax.grid(True, alpha=0.3)
                
                # 隐藏多余的子图
                for idx in range(n_clusters, len(axes)):
                    axes[idx].axis('off')
                
                plt.suptitle(f'Enrichment Volcano Plot by Cluster - {library}', fontsize=14, fontweight='bold', y=0.995)
                plt.tight_layout()
            else:
                adj_pvals = res['Adjusted P-value'].astype(float)
                odds_ratios = res['Odds Ratio'].astype(float)
                
                fig, ax = plt.subplots(figsize=(10, 8))
                scatter = ax.scatter(odds_ratios, -np.log10(adj_pvals + 1e-300), 
                                   s=50, alpha=0.6, c=adj_pvals, cmap='viridis_r')
                ax.set_xlabel('Odds Ratio', fontsize=12)
                ax.set_ylabel('-Log10(Adjusted P-value)', fontsize=12)
                ax.set_title('Enrichment Volcano Plot', fontsize=14, fontweight='bold')
                ax.axhline(y=-np.log10(0.05), color='red', linestyle='--', label='Adjusted P-value = 0.05')
                ax.axvline(x=1.0, color='gray', linestyle='--', alpha=0.5)
                ax.legend()
                ax.grid(True, alpha=0.3)
                plt.colorbar(scatter, ax=ax, label='Adjusted P-value')
                plt.tight_layout()
            
            volcano_id = "enrichment_volcano.png"
            volcano_path = os.path.join(output_dir, volcano_id)
            plt.savefig(volcano_path, dpi=300, bbox_inches='tight')
            plt.close()
            plot_files['enrichment_volcano'] = volcano_id
            logger.info(f"Enrichment volcano plot saved: {volcano_path}")
        
    except Exception as e:
        logger.warning(f"Failed to generate enrichment plots: {e}")
    
    return plot_files

@app.post("/api/enrich")
async def enrichment_analysis(
    file: UploadFile = File(..., description="聚类后的空间转录组数据文件（h5ad 格式），必须包含簇标签"),
    cluster_key: str = Form("cluster", description="簇标签所在的 obs 列名（如 'cluster', 'leiden', 'louvain'）"),
    gene_selection_method: str = Form("top_expressed", description="基因选择方法：'top_expressed'（高表达基因）或 'marker_genes'（标记基因）"),
    top_n_genes: int = Form(200, description="每个簇选择的基因数量（用于 top_expressed 方法）"),
    library: str = Form("GO_Biological_Process_2021", description="富集库名称"),
    organism: str = Form("Human", description="物种（Human/Mouse 等）"),
    engine: str = Form("enrichr", description="富集引擎：enrichr 或 kegg（基于 Enrichr 的 KEGG 库）"),
) -> JSONResponse:
    if not HAS_GSEAPY:
        return JSONResponse(status_code=500, content={"success": False, "message": "gseapy 未安装，无法进行富集分析"})
    if not HAS_ANNDATA:
        return JSONResponse(status_code=500, content={"success": False, "message": "anndata 未安装，无法读取 h5ad 文件"})
    
    if gene_selection_method not in ["top_expressed", "marker_genes"]:
        raise HTTPException(status_code=400, detail="gene_selection_method 必须是 'top_expressed' 或 'marker_genes'")
    
    temp_input_path = None
    try:
        file_id = str(uuid.uuid4())
        temp_input_path = os.path.join(tempfile.gettempdir(), f"input_{file_id}_{file.filename}")
        with open(temp_input_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # 读取 h5ad 文件
        logger.info(f"读取 h5ad 文件: {temp_input_path}")
        adata = _read_adata(temp_input_path)
        logger.info(f"数据维度: {adata.shape[0]} spots, {adata.shape[1]} genes")
        
        # 获取簇标签
        clusters, actual_cluster_key = _get_clusters(adata, cluster_key)
        unique_clusters = sorted(clusters.unique())
        logger.info(f"找到 {len(unique_clusters)} 个簇: {unique_clusters}")
        
        # 对每个簇提取基因并进行富集分析
        all_results = []
        cluster_gene_counts = {}
        
        for cluster_id in unique_clusters:
            logger.info(f"处理簇 {cluster_id}...")
            
            # 提取该簇的基因
            if gene_selection_method == "top_expressed":
                cluster_genes = _extract_top_expressed_genes(adata, cluster_id, clusters, top_n_genes)
            else:  # marker_genes
                cluster_genes = _extract_marker_genes(adata, cluster_id, clusters, top_n_genes)
            
            if not cluster_genes:
                logger.warning(f"簇 {cluster_id} 未提取到任何基因，跳过")
                continue
            
            cluster_gene_counts[cluster_id] = len(cluster_genes)
            logger.info(f"簇 {cluster_id} 提取了 {len(cluster_genes)} 个基因")
            # Support multiple libraries separated by comma
            library_list = [x.strip() for x in str(library).split(",") if x.strip()]
            if not library_list:
                raise HTTPException(
                    status_code=400,
                    detail="Parameter 'library' is empty after parsing. Provide at least one valid gene set name.",
                )

            # Handle KEGG mode
            if engine.lower() == "kegg":
                has_kegg = any("KEGG_" in lib.upper() for lib in library_list)
                if not has_kegg:
                    default_kegg = "KEGG_2021_Human" if organism.lower().startswith("human") else "KEGG_2021_Mouse"
                    library_list = [default_kegg]

            # 对该簇进行富集分析
            res = pd.DataFrame()
            use_local = USE_LOCAL_FIRST
            
            if use_local:
                local_files_available = any(find_local_gmt_file(lib) for lib in library_list)
                if local_files_available:
                    try:
                        logger.info(f"簇 {cluster_id}: 尝试使用本地 GMT 文件进行富集分析")
                        res = enrich_with_local_files(cluster_genes, library_list, organism)
                        if not res.empty:
                            logger.info(f"簇 {cluster_id}: 成功使用本地文件完成富集分析")
                        else:
                            logger.warning(f"簇 {cluster_id}: 本地文件分析结果为空，尝试使用网络 API")
                            use_local = False
                    except Exception as e:
                        logger.warning(f"簇 {cluster_id}: 使用本地文件失败，回退到网络 API: {e}")
                        use_local = False
            
            if not use_local or res.empty:
                try:
                    res = enrich_with_enrichr_api(cluster_genes, library_list, organism)
                except Exception as e:
                    if use_local:
                        raise
                    logger.warning(f"簇 {cluster_id}: 网络请求失败，尝试使用本地文件: {e}")
                    local_files_available = any(find_local_gmt_file(lib) for lib in library_list)
                    if local_files_available:
                        res = enrich_with_local_files(cluster_genes, library_list, organism)
                    else:
                        raise
            
            # 在结果中添加簇信息
            if not res.empty:
                res.insert(0, 'cluster', cluster_id)
                all_results.append(res)
        
        # 合并所有簇的结果
        if not all_results:
            raise HTTPException(status_code=400, detail="所有簇都未能提取到基因或富集分析失败")
        
        res = pd.concat(all_results, ignore_index=True)
        
        # 保存CSV文件（使用固定文件名）
        csv_filename = "enrichment_results.csv"
        out_csv = os.path.join(OUTPUT_DIR, csv_filename)
        res.to_csv(out_csv, index=False)
        
        # 计算精细化统计
        pval_threshold = 0.05
        enrichment_metrics = calculate_enrichment_metrics(res, pval_threshold)
        
        # 生成可视化图片（按簇）
        plot_files = {}
        if PLOT_AVAILABLE and not res.empty:
            plot_files = generate_enrichment_plots(res, file_id, OUTPUT_DIR, library, pval_threshold, top_n=20, clusters=unique_clusters)
        
        # 格式化精细化统计信息（改为英文描述，便于跨语言前端展示）
        stats_text_parts = []
        stats_text_parts.append("=" * 60)
        stats_text_parts.append("Gene Enrichment Analysis Statistics Report")
        stats_text_parts.append("=" * 60)
        
        stats_text_parts.append("\n[1] Analysis Parameters")
        stats_text_parts.append(f"  Input file: {file.filename}")
        stats_text_parts.append(f"  Cluster key: {actual_cluster_key}")
        stats_text_parts.append(f"  Number of clusters: {len(unique_clusters)}")
        stats_text_parts.append(f"  Clusters: {', '.join(map(str, unique_clusters))}")
        stats_text_parts.append(f"  Gene selection method: {gene_selection_method}")
        if gene_selection_method == "top_expressed":
            stats_text_parts.append(f"  Top N genes per cluster: {top_n_genes}")
        stats_text_parts.append(f"  Genes per cluster: {', '.join([f'{c}: {cluster_gene_counts.get(c, 0)}' for c in unique_clusters])}")
        stats_text_parts.append(f"  Enrichment library: {library}")
        stats_text_parts.append(f"  Organism: {organism}")
        stats_text_parts.append(f"  Engine: {engine}")
        
        stats_text_parts.append("\n[2] Basic Statistics")
        stats_text_parts.append(
            f"  Total enriched terms: "
            f"{enrichment_metrics.get('total_terms', len(res) if res is not None else 0):,}"
        )
        if 'significant_terms' in enrichment_metrics:
            stats_text_parts.append(
                f"  Significant terms (p < {pval_threshold}): "
                f"{enrichment_metrics.get('significant_terms', 0):,} "
                f"({enrichment_metrics.get('significant_percentage', 0):.2f}%)"
            )
        
        if enrichment_metrics.get('pval_stats'):
            stats_text_parts.append("\n[3] P‑value Distribution")
            ps = enrichment_metrics['pval_stats']
            stats_text_parts.append(f"  Minimum: {ps.get('min', 0):.4f}")
            stats_text_parts.append(f"  Maximum: {ps.get('max', 0):.4f}")
            stats_text_parts.append(f"  Mean: {ps.get('mean', 0):.4f}")
            stats_text_parts.append(f"  Median: {ps.get('median', 0):.4f}")
        
        if enrichment_metrics.get('adj_pval_stats'):
            stats_text_parts.append("\n[4] Adjusted P‑value Distribution")
            aps = enrichment_metrics['adj_pval_stats']
            stats_text_parts.append(f"  Minimum: {aps.get('min', 0):.4f}")
            stats_text_parts.append(f"  Maximum: {aps.get('max', 0):.4f}")
            stats_text_parts.append(f"  Mean: {aps.get('mean', 0):.4f}")
            stats_text_parts.append(f"  Median: {aps.get('median', 0):.4f}")
        
        if enrichment_metrics.get('combined_score'):
            stats_text_parts.append("\n[5] Combined Score Distribution")
            cs_stats = enrichment_metrics['combined_score']
            stats_text_parts.append(f"  Minimum: {cs_stats.get('min', 0):.2f}")
            stats_text_parts.append(f"  Maximum: {cs_stats.get('max', 0):.2f}")
            stats_text_parts.append(f"  Mean: {cs_stats.get('mean', 0):.2f}")
            stats_text_parts.append(f"  Median: {cs_stats.get('median', 0):.2f}")
        
        if enrichment_metrics.get('overlap_genes'):
            stats_text_parts.append("\n[6] Overlap Gene Count Statistics")
            overlap_stats = enrichment_metrics['overlap_genes']
            stats_text_parts.append(f"  Minimum: {overlap_stats.get('min', 0):,}")
            stats_text_parts.append(f"  Maximum: {overlap_stats.get('max', 0):,}")
            stats_text_parts.append(f"  Mean: {overlap_stats.get('mean', 0):.1f}")
            stats_text_parts.append(f"  Median: {overlap_stats.get('median', 0):.1f}")
        
        if enrichment_metrics.get('genes_per_pathway_stats'):
            stats_text_parts.append("\n[7] Gene Count per Pathway Distribution")
            gps = enrichment_metrics['genes_per_pathway_stats']
            stats_text_parts.append(f"  Minimum: {gps.get('min', 0)}")
            stats_text_parts.append(f"  Maximum: {gps.get('max', 0)}")
            stats_text_parts.append(f"  Mean: {gps.get('mean', 0):.2f}")
            stats_text_parts.append(f"  Median: {gps.get('median', 0):.2f}")
        
        if enrichment_metrics.get('odds_ratio_stats'):
            stats_text_parts.append("\n[8] Odds Ratio Distribution")
            ors = enrichment_metrics['odds_ratio_stats']
            stats_text_parts.append(f"  Minimum: {ors.get('min', 0):.4f}")
            stats_text_parts.append(f"  Maximum: {ors.get('max', 0):.4f}")
            stats_text_parts.append(f"  Mean: {ors.get('mean', 0):.4f}")
            stats_text_parts.append(f"  Median: {ors.get('median', 0):.4f}")
        
        # Add per-cluster statistics
        has_cluster_col = 'cluster' in res.columns
        pval_col_for_summary = 'Adjusted P-value' if 'Adjusted P-value' in res.columns else 'P-value'
        if has_cluster_col and unique_clusters and pval_col_for_summary in res.columns:
            stats_text_parts.append("\n[9] Per-Cluster Statistics")
            for cluster_id in unique_clusters:
                cluster_data = res[res['cluster'] == str(cluster_id)]
                cluster_total = len(cluster_data)
                cluster_sig = len(cluster_data[cluster_data[pval_col_for_summary] < pval_threshold])
                stats_text_parts.append(f"\n  Cluster {cluster_id}:")
                stats_text_parts.append(f"    Total enriched terms: {cluster_total:,}")
                stats_text_parts.append(f"    Significant terms (p < {pval_threshold}): {cluster_sig:,}")
                
                # Top 3 enriched terms per cluster
                top_terms = cluster_data.nsmallest(3, pval_col_for_summary)
                if not top_terms.empty:
                    stats_text_parts.append(f"    Top 3 enriched terms:")
                    for idx, row in top_terms.iterrows():
                        term = row.get('Term', 'N/A')
                        adj_pval = row.get('Adjusted P-value', row.get('P-value', 'N/A'))
                        if isinstance(adj_pval, (int, float)):
                            stats_text_parts.append(f"      - {term}")
                            stats_text_parts.append(f"        Adjusted P-value: {adj_pval:.2e}")
        
        # Save summary text to file (使用固定文件名)
        stats_text = "\n".join(stats_text_parts)
        summary_filename = "enrichment_summary.txt"
        summary_path = os.path.join(OUTPUT_DIR, summary_filename)
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(stats_text)
        logger.info(f"Enrichment summary saved: {summary_path}")
        
        # 构建返回数据字典 - 只包含需要的文件
        data_dict = {
            "enrichment_results.csv": csv_filename,
            "enrichment_summary.txt": summary_filename
        }
        
        # 添加可视化图片文件（只包含bar和volcano图）
        if 'enrichment_bar' in plot_files:
            data_dict["enrichment_bar.png"] = plot_files['enrichment_bar']
        if 'enrichment_volcano' in plot_files:
            data_dict["enrichment_volcano.png"] = plot_files['enrichment_volcano']
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "富集分析完成",
                "data": data_dict,
            },
        )
    except Exception as e:
        logger.error("Enrichment analysis failed: %s", e, exc_info=True)

        # 收集可用的上下文信息以改进诊断
        error_context: Dict[str, Any] = {
            "cluster_key": cluster_key,
            "gene_selection_method": gene_selection_method,
            "top_n_genes": top_n_genes,
            "library": library,
            "organism": organism,
            "engine": engine,
        }
        try:
            if 'unique_clusters' in locals():
                error_context["num_clusters"] = len(unique_clusters)
            if 'cluster_gene_counts' in locals():
                error_context["cluster_gene_counts"] = cluster_gene_counts
        except Exception:
            pass

        error_info = _handle_detailed_error("enrichment_analysis", e, context=error_context)
        error_message = format_error_info_to_message(error_info)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": error_message,
                "error": error_info,
            },
        )
    finally:
        if temp_input_path and os.path.exists(temp_input_path):
            try:
                os.remove(temp_input_path)
            except Exception as e:
                logger.warning("清理临时文件失败: %s", e)

@app.get("/api/download/{file_id}")
async def download_file(file_id: str) -> FileResponse:
    """
    下载富集分析结果文件
    
    **参数说明**:
    - `file_id`: 文件名（由富集分析接口返回，固定文件名）
    
    **返回**:
    - 文件内容（二进制流）
    - 如果文件不存在，返回 404 错误
    
    **说明**:
    - file_id就是完整的文件名，直接使用file_id查找文件
    """
    # file_id就是文件名，直接查找
    file_path = os.path.join(OUTPUT_DIR, file_id)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"文件不存在或已过期: file_id={file_id}")
    
    # 根据文件扩展名确定媒体类型
    if file_path.endswith(".png"):
        media_type = "image/png"
    elif file_path.endswith(".csv"):
        media_type = "text/csv"
    elif file_path.endswith(".txt"):
        media_type = "text/plain"
    else:
        media_type = "application/octet-stream"
    
    filename = os.path.basename(file_path)
    logger.info(f"下载文件: {file_path}, file_id: {file_id}")
    return FileResponse(path=file_path, filename=filename, media_type=media_type)

@app.get("/health")
async def health():
    return {
        "status": "healthy", 
        "has_gseapy": HAS_GSEAPY,
        "has_anndata": HAS_ANNDATA,
        "output_dir": OUTPUT_DIR
    }

if __name__ == "__main__":
    import uvicorn, os as _os
    _port = int(_os.getenv("PORT", 8086))
    uvicorn.run(app, host="0.0.0.0", port=_port)

