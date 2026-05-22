#!/usr/bin/env python3
"""
空间转录组数据预处理工具 - FastAPI 版本
提供数据预处理、空间聚类和 SpatialDE 分析功能
"""

import os
import logging
from logging.handlers import RotatingFileHandler
import traceback
import tempfile
import uuid
from typing import Dict, List, Optional, Any, Literal
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel

# 尝试导入生物信息学相关包
try:
    import anndata as ad
    import scanpy as sc
    import pandas as pd
    import numpy as np
    from scipy import sparse
    import matplotlib
    matplotlib.use('Agg')  # 非交互式后端
    import matplotlib.pyplot as plt
    import seaborn as sns
    plt.rcParams['font.sans-serif'] = ['Arial', 'DejaVu Sans', 'Liberation Sans']
    plt.rcParams['axes.unicode_minus'] = False
    BIO_AVAILABLE = True
    PLOT_AVAILABLE = True
except ImportError as e:
    logging.warning(f"生物信息学包导入失败: {e}")
    BIO_AVAILABLE = False
    PLOT_AVAILABLE = False

# 配置日志
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

# 创建 FastAPI 应用
app = FastAPI(
    title="空间转录组数据预处理服务",
    description="提供空间转录组数据的预处理、空间聚类和 SpatialDE 分析功能",
    version="1.0.0"
)

# 输出目录配置
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)
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

# 文件类型映射（用于下载接口）
FILE_TYPE_MAP = {
    "preprocessed": "preprocessed_{file_id}.h5ad",
    "spatial": "spatial_{file_id}.h5ad",
    "spatialde": "spatialde_{file_id}.h5ad"
}


def format_error_info_to_message(error_info: Dict[str, Any]) -> str:
    """将 error_info 字典格式化为可读的字符串消息"""
    parts = []
    
    # 基本信息
    parts.append(f"Error Type: {error_info.get('error_type', 'Unknown')}")
    parts.append(f"Error Message: {error_info.get('error_message', 'Unknown error')}")
    
    # 诊断信息
    if "diagnosis" in error_info:
        parts.append(f"\nDiagnosis: {error_info['diagnosis']}")
    
    # 过滤统计信息
    if "filtering_stats" in error_info:
        stats = error_info["filtering_stats"]
        parts.append("\nFiltering Statistics:")
        parts.append(f"  Initial cells: {stats.get('initial_cells', 0):,}")
        parts.append(f"  Final cells: {stats.get('final_cells', 0):,}")
        parts.append(f"  Cells removed: {stats.get('cells_removed', 0):,}")
        parts.append(f"  Removal rate: {stats.get('removal_rate', '0%')}")
    
    # 建议信息
    if "suggestions" in error_info and error_info["suggestions"]:
        parts.append("\nSuggestions:")
        for idx, suggestion in enumerate(error_info["suggestions"], 1):
            if isinstance(suggestion, dict):
                issue = suggestion.get("issue", "Unknown issue")
                recommendations = suggestion.get("recommendations", [])
                parts.append(f"\n  {idx}. {issue}:")
                for rec in recommendations:
                    parts.append(f"     - {rec}")
    
    # 堆栈跟踪（可选）
    if "traceback" in error_info:
        parts.append(f"\nTraceback:\n{error_info['traceback']}")
    
    return "\n".join(parts)


def handle_error(
    step: str, 
    error: Exception, 
    include_traceback: bool = True,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """统一错误处理函数，提供详细的错误信息和参数建议"""
    error_info = {
        "error": True,
        "step": step,
        "error_type": type(error).__name__,
        "error_message": str(error),
        "suggestions": []
    }
    
    if include_traceback:
        error_info["traceback"] = traceback.format_exc()
    
    # 根据错误类型和上下文提供参数建议
    error_msg_lower = str(error).lower()
    
    # 检查是否是数据为空的问题
    if "0 sample" in error_msg_lower or "shape=(0" in error_msg_lower or "empty" in error_msg_lower:
        error_info["diagnosis"] = "Data became empty after filtering (all cells or genes were filtered out)"
        error_info["suggestions"].extend([
            {
                "issue": "Data over-filtered",
                "recommendations": [
                    "Reduce min_genes parameter (current value may be too high, causing all cells to be filtered)",
                    "Reduce min_cells parameter (current value may be too high, causing all genes to be filtered)",
                    "Increase max_mito_percent parameter (current value may be too low, causing too many cells to be filtered)",
                    "Check input data quality to ensure the data itself is valid"
                ]
            }
        ])
        if context:
            if "min_genes" in context:
                error_info["suggestions"][0]["recommendations"].append(
                    f"Consider reducing min_genes from {context['min_genes']} to {max(50, context['min_genes'] // 2)} or lower"
                )
            if "min_cells" in context:
                error_info["suggestions"][0]["recommendations"].append(
                    f"Consider reducing min_cells from {context['min_cells']} to {max(1, context['min_cells'] // 2)} or lower"
                )
            if "max_mito_percent" in context:
                error_info["suggestions"][0]["recommendations"].append(
                    f"Consider increasing max_mito_percent from {context['max_mito_percent']} to {context['max_mito_percent'] * 2} or higher"
                )
            if "initial_cells" in context and "final_cells" in context:
                error_info["filtering_stats"] = {
                    "initial_cells": context.get("initial_cells", 0),
                    "final_cells": context.get("final_cells", 0),
                    "cells_removed": context.get("initial_cells", 0) - context.get("final_cells", 0),
                    "removal_rate": f"{(1 - context.get('final_cells', 0) / max(1, context.get('initial_cells', 1))) * 100:.1f}%"
                }
    
    # 检查是否是文件读取问题
    elif "file" in error_msg_lower or "read" in error_msg_lower or "format" in error_msg_lower:
        error_info["diagnosis"] = "File reading or format issue"
        error_info["suggestions"].extend([
            {
                "issue": "File format mismatch or file corrupted",
                "recommendations": [
                    "Check if file format is correct (supported formats: h5ad, 10x_h5, csv, tsv)",
                    "Try explicitly specifying the file_type parameter",
                    "Ensure the file is not corrupted and uploaded completely",
                    "Check file encoding (CSV/TSV files should be UTF-8)"
                ]
            }
        ])
    
    # 检查是否是内存问题
    elif "memory" in error_msg_lower or "out of memory" in error_msg_lower:
        error_info["diagnosis"] = "Insufficient memory"
        error_info["suggestions"].extend([
            {
                "issue": "Data volume too large causing memory shortage",
                "recommendations": [
                    "Increase available system memory",
                    "Reduce data volume (sample the data first)",
                    "Reduce n_top_genes parameter to decrease memory usage"
                ]
            }
        ])
    
    # 检查是否是参数值问题
    elif "invalid" in error_msg_lower or "value" in error_msg_lower:
        error_info["diagnosis"] = "Invalid parameter value"
        error_info["suggestions"].extend([
            {
                "issue": "Parameter value out of valid range",
                "recommendations": [
                    "Check if all parameters are within valid ranges",
                    "min_genes and min_cells should be positive integers",
                    "max_mito_percent should be a float between 0-100",
                    "target_sum should be a positive number"
                ]
            }
        ])
    
    # 如果没有匹配到特定错误类型，提供通用建议
    if not error_info["suggestions"]:
        error_info["suggestions"].append({
            "issue": "Unknown error",
            "recommendations": [
                "Check input data format and content",
                "Verify all parameter values are reasonable",
                "Review detailed error stack trace for more clues"
            ]
        })
    
    logger.error(f"Step {step} failed: {error}")
    if include_traceback:
        logger.error(traceback.format_exc())
    
    return error_info


def _read_adata(
    file_path: str,
    file_type: Literal["auto", "h5ad", "10x_h5", "csv", "tsv"] = "auto",
) -> "ad.AnnData":
    """Centralized AnnData reader.
    Supports a few common spatial/single-cell formats and keeps logic in one place.
    """
    adata = None
    
    if file_type == "auto":
        if file_path.endswith(".h5ad"):
            adata = ad.read_h5ad(file_path)
        elif file_path.endswith(".h5"):
            adata = sc.read_10x_h5(file_path)
        elif file_path.endswith(".csv"):
            df = pd.read_csv(file_path, index_col=0)
            # 确保索引和列名都是字符串类型
            df.index = df.index.astype(str)
            df.columns = df.columns.astype(str)
            adata = ad.AnnData(X=df.values, var=pd.DataFrame(index=df.columns), obs=pd.DataFrame(index=df.index))
        elif file_path.endswith(".tsv"):
            df = pd.read_csv(file_path, sep="\t", index_col=0)
            # 确保索引和列名都是字符串类型
            df.index = df.index.astype(str)
            df.columns = df.columns.astype(str)
            adata = ad.AnnData(X=df.values, var=pd.DataFrame(index=df.columns), obs=pd.DataFrame(index=df.index))
        else:
            # Fallback to scanpy's autodetect
            adata = sc.read(file_path)
    elif file_type == "h5ad":
        adata = ad.read_h5ad(file_path)
    elif file_type == "10x_h5":
        adata = sc.read_10x_h5(file_path)
    elif file_type == "csv":
        df = pd.read_csv(file_path, index_col=0)
        # 确保索引和列名都是字符串类型
        df.index = df.index.astype(str)
        df.columns = df.columns.astype(str)
        adata = ad.AnnData(X=df.values, var=pd.DataFrame(index=df.columns), obs=pd.DataFrame(index=df.index))
    elif file_type == "tsv":
        df = pd.read_csv(file_path, sep="\t", index_col=0)
        # 确保索引和列名都是字符串类型
        df.index = df.index.astype(str)
        df.columns = df.columns.astype(str)
        adata = ad.AnnData(X=df.values, var=pd.DataFrame(index=df.columns), obs=pd.DataFrame(index=df.index))
    else:
        # If we get here the file_type is not supported
        raise ValueError(f"Unsupported file_type: {file_type}")
    
    # 确保变量名唯一，解决重复基因名问题（必须在读取后立即处理）
    if adata is not None:
        # 先确保索引为字符串类型，避免类型转换警告
        if adata.var_names.dtype != 'object' or not isinstance(adata.var_names[0] if len(adata.var_names) > 0 else '', str):
            adata.var_names = adata.var_names.astype(str)
        if adata.obs_names.dtype != 'object' or not isinstance(adata.obs_names[0] if len(adata.obs_names) > 0 else '', str):
            adata.obs_names = adata.obs_names.astype(str)
        # 去除重名基因（必须在索引类型转换之后）
        adata.var_names_make_unique()
    
    return adata


def calculate_qc_metrics(adata: ad.AnnData, qc_result: Dict[str, Any]) -> Dict[str, Any]:
    """计算QC质量指标"""
    metrics = {}
    
    # 检查是否有细胞数据，如果没有则跳过统计计算
    if adata.n_obs == 0:
        logger.warning("数据为空（所有细胞都被过滤），跳过QC统计计算")
        # 仍然返回过滤信息
        metrics['filtering'] = {
            'cells_before': int(qc_result['initial_cells']),
            'cells_after': int(qc_result['final_cells']),
            'cells_removed': int(qc_result['cells_removed']),
            'genes_before': int(qc_result['initial_genes']),
            'genes_after': int(qc_result['final_genes']),
            'genes_removed': int(qc_result['genes_removed']),
            'mito_cells_removed': int(qc_result['mito_cells_removed'])
        }
        return metrics
    
    # 计算基因数分布统计
    if 'n_genes_by_counts' in adata.obs.columns:
        n_genes = adata.obs['n_genes_by_counts'].values
        if len(n_genes) > 0:
            metrics['n_genes'] = {
                'min': float(n_genes.min()),
                'max': float(n_genes.max()),
                'mean': float(n_genes.mean()),
                'median': float(np.median(n_genes)),
                'std': float(n_genes.std())
            }
    
    # 计算UMI数分布统计
    if 'total_counts' in adata.obs.columns:
        total_counts = adata.obs['total_counts'].values
        if len(total_counts) > 0:
            metrics['total_counts'] = {
                'min': float(total_counts.min()),
                'max': float(total_counts.max()),
                'mean': float(total_counts.mean()),
                'median': float(np.median(total_counts)),
                'std': float(total_counts.std())
            }
    
    # 计算线粒体基因百分比分布统计
    if 'pct_counts_mt' in adata.obs.columns:
        pct_mt = adata.obs['pct_counts_mt'].values
        if len(pct_mt) > 0:
            metrics['pct_counts_mt'] = {
                'min': float(pct_mt.min()),
                'max': float(pct_mt.max()),
                'mean': float(pct_mt.mean()),
                'median': float(np.median(pct_mt)),
                'std': float(pct_mt.std())
            }
    
    # 过滤前后对比
    metrics['filtering'] = {
        'cells_before': int(qc_result['initial_cells']),
        'cells_after': int(qc_result['final_cells']),
        'cells_removed': int(qc_result['cells_removed']),
        'genes_before': int(qc_result['initial_genes']),
        'genes_after': int(qc_result['final_genes']),
        'genes_removed': int(qc_result['genes_removed']),
        'mito_cells_removed': int(qc_result['mito_cells_removed'])
    }
    
    return metrics


def _create_placeholder_plot(file_path: str, title: str, message: str = "Plot generation failed") -> None:
    """创建占位图片（当图片生成失败时使用）"""
    try:
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.text(0.5, 0.5, message, ha='center', va='center', fontsize=14, 
                color='gray', transform=ax.transAxes)
        ax.set_title(title, fontsize=16, fontweight='bold', color='gray')
        ax.axis('off')
        plt.tight_layout()
        plt.savefig(file_path, dpi=300, bbox_inches='tight')
        plt.close()
        logger.info(f"Placeholder plot created: {file_path}")
    except Exception as e:
        logger.error(f"Failed to create placeholder plot: {e}")


def generate_qc_plots(adata: ad.AnnData, output_dir: str, qc_result: Dict[str, Any]) -> Dict[str, str]:
    """生成QC可视化图 - 确保所有图片都生成（失败时创建占位图片）
    返回: Dict[str, str] - key为图片类型，value为文件ID（UUID+扩展名）
    """
    plot_files = {}
    
    # 为每个图片生成独立的UUID（包含扩展名）
    violin_id = f"{str(uuid.uuid4())}.png"
    scatter_id = f"{str(uuid.uuid4())}.png"
    filtering_id = f"{str(uuid.uuid4())}.png"
    
    qc_violin_path = os.path.join(output_dir, violin_id)
    qc_scatter_path = os.path.join(output_dir, scatter_id)
    qc_filtering_path = os.path.join(output_dir, filtering_id)
    
    # 1. 生成QC指标小提琴图
    if not PLOT_AVAILABLE:
        _create_placeholder_plot(qc_violin_path, "QC Violin Plot", "Plotting library not available")
        plot_files['qc_violin'] = violin_id
    else:
        try:
            fig, axes = plt.subplots(1, 3, figsize=(15, 5))
            fig.suptitle('Quality Control Metrics Distribution', fontsize=16, fontweight='bold')
            
            metrics = ['total_counts', 'n_genes_by_counts', 'pct_counts_mt']
            titles = ['Total UMI Counts', 'Number of Genes', 'Mitochondrial %']
            
            for idx, (metric, title) in enumerate(zip(metrics, titles)):
                if metric in adata.obs.columns:
                    ax = axes[idx]
                    values = adata.obs[metric].values
                    ax.violinplot([values], positions=[0], showmeans=True, showmedians=True)
                    ax.set_title(title, fontsize=12, fontweight='bold')
                    ax.set_ylabel('Value', fontsize=10)
                    ax.grid(True, alpha=0.3)
                    # 添加统计信息
                    mean_val = values.mean()
                    median_val = np.median(values)
                    ax.text(0.5, 0.95, f'Mean: {mean_val:.2f}\nMedian: {median_val:.2f}', 
                           transform=ax.transAxes, ha='center', va='top',
                           bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
                else:
                    ax = axes[idx]
                    ax.text(0.5, 0.5, f'{metric} not found', ha='center', va='center', 
                           transform=ax.transAxes, color='gray')
                    ax.set_title(title, fontsize=12, fontweight='bold')
                    ax.axis('off')
            
            plt.tight_layout()
            plt.savefig(qc_violin_path, dpi=300, bbox_inches='tight')
            plt.close()
            plot_files['qc_violin'] = violin_id
            logger.info(f"QC violin plot saved: {qc_violin_path}")
        except Exception as e:
            logger.warning(f"Failed to generate QC violin plot: {e}, creating placeholder")
            _create_placeholder_plot(qc_violin_path, "QC Violin Plot", f"Generation failed: {str(e)}")
            plot_files['qc_violin'] = violin_id
    
    # 2. 生成基因数 vs UMI数散点图
    if not PLOT_AVAILABLE:
        _create_placeholder_plot(qc_scatter_path, "QC Scatter Plot", "Plotting library not available")
        plot_files['qc_scatter'] = scatter_id
    else:
        try:
            if 'n_genes_by_counts' in adata.obs.columns and 'total_counts' in adata.obs.columns:
                fig, ax = plt.subplots(figsize=(10, 8))
                
                n_genes = adata.obs['n_genes_by_counts'].values
                total_counts = adata.obs['total_counts'].values
                
                if 'pct_counts_mt' in adata.obs.columns:
                    pct_mt = adata.obs['pct_counts_mt'].values
                    scatter = ax.scatter(n_genes, total_counts, c=pct_mt, cmap='viridis', 
                                       s=10, alpha=0.6, edgecolors='none')
                    plt.colorbar(scatter, ax=ax, label='Mitochondrial %')
                else:
                    ax.scatter(n_genes, total_counts, s=10, alpha=0.6, color='blue')
                
                ax.set_xlabel('Number of Genes', fontsize=12)
                ax.set_ylabel('Total UMI Counts', fontsize=12)
                ax.set_title('Genes vs UMI Counts', fontsize=14, fontweight='bold')
                ax.grid(True, alpha=0.3)
                
                plt.tight_layout()
                plt.savefig(qc_scatter_path, dpi=300, bbox_inches='tight')
                plt.close()
                plot_files['qc_scatter'] = scatter_id
                logger.info(f"QC scatter plot saved: {qc_scatter_path}")
            else:
                _create_placeholder_plot(qc_scatter_path, "QC Scatter Plot", "Required columns not found")
                plot_files['qc_scatter'] = scatter_id
        except Exception as e:
            logger.warning(f"Failed to generate QC scatter plot: {e}, creating placeholder")
            _create_placeholder_plot(qc_scatter_path, "QC Scatter Plot", f"Generation failed: {str(e)}")
            plot_files['qc_scatter'] = scatter_id
    
    # 3. 生成过滤前后对比柱状图
    if not PLOT_AVAILABLE:
        _create_placeholder_plot(qc_filtering_path, "QC Filtering Plot", "Plotting library not available")
        plot_files['qc_filtering'] = filtering_id
    else:
        try:
            fig, axes = plt.subplots(1, 2, figsize=(12, 5))
            fig.suptitle('Filtering Statistics', fontsize=16, fontweight='bold')
            
            # 细胞数对比
            ax1 = axes[0]
            categories = ['Before', 'After']
            cell_counts = [qc_result['initial_cells'], qc_result['final_cells']]
            bars1 = ax1.bar(categories, cell_counts, color=['lightcoral', 'lightblue'])
            ax1.set_ylabel('Number of Cells', fontsize=12)
            ax1.set_title('Cell Filtering', fontsize=12, fontweight='bold')
            ax1.grid(True, alpha=0.3, axis='y')
            # 添加数值标签
            for bar in bars1:
                height = bar.get_height()
                ax1.text(bar.get_x() + bar.get_width()/2., height,
                        f'{int(height):,}', ha='center', va='bottom')
            
            # 基因数对比
            ax2 = axes[1]
            gene_counts = [qc_result['initial_genes'], qc_result['final_genes']]
            bars2 = ax2.bar(categories, gene_counts, color=['lightcoral', 'lightblue'])
            ax2.set_ylabel('Number of Genes', fontsize=12)
            ax2.set_title('Gene Filtering', fontsize=12, fontweight='bold')
            ax2.grid(True, alpha=0.3, axis='y')
            # 添加数值标签
            for bar in bars2:
                height = bar.get_height()
                ax2.text(bar.get_x() + bar.get_width()/2., height,
                        f'{int(height):,}', ha='center', va='bottom')
            
            plt.tight_layout()
            plt.savefig(qc_filtering_path, dpi=300, bbox_inches='tight')
            plt.close()
            plot_files['qc_filtering'] = filtering_id
            logger.info(f"QC filtering plot saved: {qc_filtering_path}")
        except Exception as e:
            logger.warning(f"Failed to generate QC filtering plot: {e}, creating placeholder")
            _create_placeholder_plot(qc_filtering_path, "QC Filtering Plot", f"Generation failed: {str(e)}")
            plot_files['qc_filtering'] = filtering_id
    
    return plot_files


def check_if_preprocessed(adata: ad.AnnData) -> Dict[str, Any]:
    """
    检查数据是否已经预处理过（基于单细胞表达数据的结果）
    
    返回:
        Dict包含:
        - is_preprocessed: bool, 是否已预处理
        - reasons: List[str], 判断原因列表
        - skip_qc: bool, 是否跳过质量控制
        - skip_normalization: bool, 是否跳过标准化
    """
    reasons = []
    skip_qc = False
    skip_normalization = False
    
    # 检查1: 是否已经选择过高变基因（这是预处理的重要标志）
    if 'highly_variable' in adata.var.columns:
        if adata.var['highly_variable'].any():
            reasons.append("数据已选择过高变基因（highly_variable列存在且有True值）")
            skip_normalization = True  # 如果已选择高变基因，说明已经标准化过
    
    # 检查2: 是否已经计算过QC指标
    qc_columns = ['n_genes_by_counts', 'total_counts', 'pct_counts_mt']
    has_qc_metrics = all(col in adata.obs.columns for col in qc_columns)
    if has_qc_metrics:
        reasons.append("数据已计算过QC指标（n_genes_by_counts, total_counts, pct_counts_mt列存在）")
        # 注意：有QC指标不一定意味着已经过滤过，所以不跳过QC
    
    # 检查3: 数据是否已经标准化（通过检查数据值范围）
    # 如果数据已经log1p转换，值通常较小（<20），且分布特征不同
    if not sparse.issparse(adata.X):
        data_sample = adata.X.flatten()
    else:
        data_sample = adata.X.data
    
    # 采样检查（避免大数据集计算过慢）
    sample_size = min(10000, len(data_sample))
    if len(data_sample) > 0:
        sample_data = np.random.choice(data_sample, size=sample_size, replace=False)
        max_val = np.max(np.abs(sample_data))
        mean_val = np.mean(np.abs(sample_data))
        
        # 如果最大值较小且均值较小，可能是已经log1p转换过的数据
        # 但这不是绝对判断，因为原始数据也可能很小
        if max_val < 20 and mean_val < 5:
            # 进一步检查：如果数据中大部分值都是非整数，可能是标准化后的
            non_integer_ratio = np.sum(sample_data != np.round(sample_data)) / len(sample_data)
            if non_integer_ratio > 0.5:
                reasons.append(f"数据值范围特征显示可能已标准化（最大值: {max_val:.2f}, 均值: {mean_val:.2f}, 非整数比例: {non_integer_ratio:.2%}）")
    
    # 检查4: 检查uns中是否有预处理标记
    if 'preprocessed' in adata.uns:
        reasons.append("数据包含预处理标记（uns['preprocessed']存在）")
        skip_normalization = True
    
    # 检查5: 如果数据维度已经很小（可能是已经选择过高变基因的结果）
    # 通常原始数据有数万个基因，如果只有几千个，可能是已经选择过高变基因
    if adata.n_vars < 5000 and 'highly_variable' in adata.var.columns:
        if adata.var['highly_variable'].sum() == adata.n_vars:
            reasons.append(f"数据基因数较少（{adata.n_vars}）且全部标记为高变基因，可能已预处理")
            skip_normalization = True
    
    # 综合判断：如果有多个预处理特征，则认为已预处理
    is_preprocessed = len(reasons) >= 2 or skip_normalization
    
    return {
        "is_preprocessed": is_preprocessed,
        "reasons": reasons,
        "skip_qc": skip_qc,
        "skip_normalization": skip_normalization
    }


def perform_quality_control(
    adata: ad.AnnData,
    min_genes: int = 1,
    min_cells: int = 1,
    max_mito_percent: float = 100.0,
    mito_prefix: str = "MT-"
) -> Dict[str, Any]:
    """执行质量控制的内部函数"""
    initial_cells = adata.n_obs
    initial_genes = adata.n_vars
    
    # 计算质量控制指标
    logger.info("计算质量控制指标")
    # mark mitochondrial genes by prefix then compute QC metrics
    mt_key = "mt"
    adata.var[mt_key] = adata.var_names.str.startswith(mito_prefix)
    sc.pp.calculate_qc_metrics(adata, qc_vars=[mt_key], percent_top=None, log1p=False, inplace=True)
    
    # 过滤低质量细胞和基因
    logger.info(f"过滤细胞 (min_genes={min_genes})")
    sc.pp.filter_cells(adata, min_genes=min_genes)
    
    logger.info(f"过滤基因 (min_cells={min_cells})")
    sc.pp.filter_genes(adata, min_cells=min_cells)
    
    # 线粒体基因过滤
    pct_col = "pct_counts_mt"
    if max_mito_percent > 0 and pct_col in adata.obs.columns:
        logger.info(f"过滤线粒体基因 (max_mito_percent={max_mito_percent})")
        before_mito = int(adata.n_obs)
        adata = adata[adata.obs[pct_col] < max_mito_percent, :].copy()
        mito_removed = before_mito - int(adata.n_obs)
        logger.info(f"基于线粒体基因过滤移除 {mito_removed} 个细胞")
    else:
        mito_removed = 0
        logger.info("跳过线粒体基因过滤")
    
    return {
        "adata": adata,
        "initial_cells": initial_cells,
        "final_cells": adata.n_obs,
        "cells_removed": initial_cells - adata.n_obs,
        "initial_genes": initial_genes,
        "final_genes": adata.n_vars,
        "genes_removed": initial_genes - adata.n_vars,
        "mito_cells_removed": mito_removed
    }


def perform_normalization(
    adata: ad.AnnData,
    method: Literal["log1p", "sqrt", "none"] = "log1p",
    target_sum: float = 1e4,
    highly_variable_genes: bool = True,
    n_top_genes: int = 3000,
    hvg_flavor: Literal["seurat", "seurat_v3", "cell_ranger"] = "seurat_v3",
    scale: bool = True,
    scale_zero_center: bool = False,
    scale_max_value: float = 10.0,
) -> Dict[str, Any]:
    """执行数据标准化的内部函数"""
    # 检查数据是否为空
    if adata.n_obs == 0 or adata.n_vars == 0:
        raise ValueError(
            f"Data is empty, cannot perform normalization. Current data shape: {adata.shape}. "
            f"This usually occurs when quality control steps filtered out all cells or genes. "
            f"Please reduce filtering parameters (min_genes, min_cells, max_mito_percent) and try again."
        )
    
    # 在标准化之前保存原始数据到 layers['counts']（保留所有基因的原始数据）
    logger.info("保存原始数据到 layers['counts']")
    if sparse.issparse(adata.X):
        adata.layers['counts'] = adata.X.copy()
    else:
        adata.layers['counts'] = adata.X.copy()
    
    # 高变基因选择（在标准化之前，与GraphST一致）
    n_hvg = 0
    if highly_variable_genes:
        logger.info(f"选择高变基因 (n_top_genes={n_top_genes}, flavor={hvg_flavor})")
        # 确保数据已经处理过（没有重名基因，索引是字符串）
        if adata.var_names.duplicated().any():
            logger.warning("检测到重名基因，正在处理...")
            adata.var_names_make_unique()
        try:
            sc.pp.highly_variable_genes(adata, flavor=hvg_flavor, n_top_genes=n_top_genes)
            n_hvg = adata.var.highly_variable.sum()
            logger.info(f"选择了 {n_hvg} 个高变基因")
        except Exception as e:
            logger.warning(f"高变基因选择失败 ({hvg_flavor}): {e}")
            # 尝试使用替代方法
            fallback_flavors = ["seurat", "cell_ranger"] if hvg_flavor != "seurat" else ["cell_ranger"]
            success = False
            for fallback_flavor in fallback_flavors:
                try:
                    logger.info(f"尝试使用替代方法: {fallback_flavor}")
                    sc.pp.highly_variable_genes(adata, flavor=fallback_flavor, n_top_genes=n_top_genes)
                    n_hvg = adata.var.highly_variable.sum()
                    logger.info(f"使用 {fallback_flavor} 方法选择了 {n_hvg} 个高变基因")
                    success = True
                    break
                except Exception as e2:
                    logger.warning(f"替代方法 {fallback_flavor} 也失败: {e2}")
                    continue
            if not success:
                logger.warning("所有高变基因选择方法都失败，跳过高变基因选择步骤")
                n_hvg = 0
    
    # 标准化
    logger.info(f"标准化数据 (target_sum={target_sum})")
    sc.pp.normalize_total(adata, target_sum=target_sum)
    
    logger.info(f"应用转换方法: {method}")
    if method == "log1p":
        sc.pp.log1p(adata)
    elif method == "sqrt":
        # handle sparse matrices
        if sparse.issparse(adata.X):
            adata.X = np.sqrt(adata.X.A)
        else:
            adata.X = np.sqrt(adata.X)
    elif method == "none":
        logger.info("跳过数据转换")
    
    # 如果选择了高变基因，在标准化后过滤
    # 注意：过滤时 layers['counts'] 也会被自动过滤，只保留高变基因的原始数据
    if highly_variable_genes and n_hvg > 0:
        # 保存高变基因的原始数据（在过滤前）
        hvg_mask = adata.var.highly_variable.values
        if sparse.issparse(adata.layers['counts']):
            hvg_counts = adata.layers['counts'][:, hvg_mask].copy()
        else:
            hvg_counts = adata.layers['counts'][:, hvg_mask].copy()
        
        # 过滤 adata 为只保留高变基因
        adata = adata[:, adata.var.highly_variable].copy()
        
        # 更新 layers['counts'] 为高变基因的原始数据
        adata.layers['counts'] = hvg_counts
        logger.info(f"已过滤为 {n_hvg} 个高变基因，并保留高变基因的原始数据到 layers['counts']")
    else:
        logger.info("未选择高变基因，保留所有基因的原始数据到 layers['counts']")
    
    # Scale步骤（与GraphST一致）
    if scale:
        logger.info(f"Scale数据 (zero_center={scale_zero_center}, max_value={scale_max_value})")
        sc.pp.scale(adata, zero_center=scale_zero_center, max_value=scale_max_value)
    
    return {
        "adata": adata,
        "method": method,
        "target_sum": target_sum,
        "n_hvg": n_hvg,
        "hvg_flavor": hvg_flavor,
        "scale": scale,
        "final_shape": list(adata.shape)
    }


@app.post("/api/preprocess")
async def integrated_preprocessing(
    file: UploadFile = File(..., description="空间转录组数据文件"),
    # 文件类型
    file_type: Literal["auto", "h5ad", "10x_h5", "csv", "tsv"] = Form("auto", description="文件类型"),
    # 质量控制参数
    min_genes: int = Form(1, description="每个细胞最少表达的基因数"),
    min_cells: int = Form(1, description="每个基因最少在多少个细胞中表达"),
    max_mito_percent: float = Form(100.0, description="线粒体基因最大百分比"),
    mito_prefix: str = Form("MT-", description="线粒体基因前缀"),
    # 标准化参数
    normalization_method: Literal["log1p", "sqrt", "none"] = Form("log1p", description="标准化方法"),
    target_sum: float = Form(1e4, description="标准化目标总和"),
    highly_variable_genes: bool = Form(True, description="是否选择高变基因"),
    n_top_genes: int = Form(3000, description="高变基因数量"),
    hvg_flavor: Literal["seurat", "seurat_v3", "cell_ranger"] = Form("seurat_v3", description="高变基因选择方法"),
    scale: bool = Form(True, description="是否进行scale标准化"),
    scale_zero_center: bool = Form(False, description="scale时是否零中心化"),
    scale_max_value: float = Form(10.0, description="scale时的最大值截断"),
):
    """
    整合的数据预处理流程：加载 → 质控 → 归一化
    
    接收上传的文件，执行质量控制和数据标准化，返回文件ID用于下载。
    
    **参数说明**:
    - `file`: 上传的空间转录组数据文件（支持 h5ad, 10x_h5, csv, tsv 格式）
    - `file_type`: 文件类型，可选: auto, h5ad, 10x_h5, csv, tsv（默认: "auto"）
    - `min_genes`: 每个细胞最少表达的基因数（默认: 1，不质控）
    - `min_cells`: 每个基因最少在多少个细胞中表达（默认: 1，不质控）
    - `max_mito_percent`: 线粒体基因最大百分比（默认: 100.0，不质控）
    - `mito_prefix`: 线粒体基因前缀（默认: "MT-"）
    - `normalization_method`: 标准化方法，可选: log1p, sqrt, none（默认: "log1p"）
    - `target_sum`: 标准化目标总和（默认: 1e4）
    - `highly_variable_genes`: 是否选择高变基因（默认: True）
    - `n_top_genes`: 高变基因数量（默认: 3000，与GraphST一致）
    - `hvg_flavor`: 高变基因选择方法，可选: seurat, seurat_v3, cell_ranger（默认: "seurat_v3"，与GraphST一致）
    - `scale`: 是否进行scale标准化（默认: True，与GraphST一致）
    - `scale_zero_center`: scale时是否零中心化（默认: False，与GraphST一致）
    - `scale_max_value`: scale时的最大值截断（默认: 10.0，与GraphST一致）
    
    **返回** (JSON格式):
    - `data`: 包含文件ID和统计信息的字典
        - `preprocessed_data.h5ad`: 文件ID（用于下载接口）
        - `Processing Statistics`: Text format statistics
    """
    if not BIO_AVAILABLE:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": "Bioinformatics packages not installed. Please install anndata, scanpy, pandas, numpy, scipy"
            }
        )
    
    temp_input_path = None
    
    try:
        # 生成唯一的文件ID
        file_id = str(uuid.uuid4())
        
        # 保存上传的文件到临时目录
        temp_input_path = os.path.join(tempfile.gettempdir(), f"input_{file_id}_{file.filename}")
        with open(temp_input_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        logger.info(f"文件已保存: {temp_input_path}, 大小: {len(content)} bytes")
        
        # 步骤1: 加载数据
        logger.info("步骤1: 加载数据")
        adata = _read_adata(temp_input_path, file_type)
        initial_shape = adata.shape
        
        # 检查数据是否已经预处理过
        logger.info("检查数据是否已经预处理过")
        preprocess_check = check_if_preprocessed(adata)
        
        if preprocess_check["is_preprocessed"]:
            logger.info(f"检测到数据可能已经预处理过，原因: {', '.join(preprocess_check['reasons'])}")
            logger.info("将跳过已完成的预处理步骤")
        
        # 步骤2: 质量控制
        if preprocess_check["skip_qc"]:
            logger.info("步骤2: 跳过质量控制（数据已预处理）")
            # 如果跳过QC，创建模拟的QC结果
            qc_result = {
                "adata": adata,
                "initial_cells": adata.n_obs,
                "final_cells": adata.n_obs,
                "cells_removed": 0,
                "initial_genes": adata.n_vars,
                "final_genes": adata.n_vars,
                "genes_removed": 0,
                "mito_cells_removed": 0
            }
            # 如果缺少QC指标，尝试计算（但不进行过滤）
            qc_columns = ['n_genes_by_counts', 'total_counts', 'pct_counts_mt']
            if not all(col in adata.obs.columns for col in qc_columns):
                logger.info("补充计算QC指标（不进行过滤）")
                mt_key = "mt"
                adata.var[mt_key] = adata.var_names.str.startswith(mito_prefix)
                sc.pp.calculate_qc_metrics(adata, qc_vars=[mt_key], percent_top=None, log1p=False, inplace=True)
        else:
            logger.info("步骤2: 质量控制")
            qc_result = perform_quality_control(
                adata, min_genes, min_cells, max_mito_percent, mito_prefix
            )
            adata = qc_result["adata"]
        
        # 检查过滤后数据是否为空
        if adata.n_obs == 0 or adata.n_vars == 0:
            error_context = {
                "min_genes": min_genes,
                "min_cells": min_cells,
                "max_mito_percent": max_mito_percent,
                "initial_cells": qc_result["initial_cells"],
                "final_cells": qc_result["final_cells"],
                "initial_genes": qc_result["initial_genes"],
                "final_genes": qc_result["final_genes"],
                "cells_removed": qc_result["cells_removed"],
                "genes_removed": qc_result["genes_removed"],
                "mito_cells_removed": qc_result["mito_cells_removed"]
            }
            error_msg = (
                f"Data is empty after quality control: initial {qc_result['initial_cells']} cells, "
                f"{qc_result['initial_genes']} genes; after filtering {qc_result['final_cells']} cells, "
                f"{qc_result['final_genes']} genes. All data has been filtered out."
            )
            raise ValueError(error_msg)
        
        # 计算精细化QC统计
        qc_metrics = calculate_qc_metrics(adata, qc_result)
        
        # 步骤3: 数据标准化
        if preprocess_check["skip_normalization"]:
            logger.info("步骤3: 跳过数据标准化（数据已预处理）")
            # 如果跳过标准化，创建模拟的标准化结果
            norm_result = {
                "adata": adata,
                "method": "skipped (already preprocessed)",
                "target_sum": "N/A",
                "n_hvg": adata.var['highly_variable'].sum() if 'highly_variable' in adata.var.columns else 0,
                "hvg_flavor": "N/A",
                "scale": False,
                "final_shape": list(adata.shape)
            }
            logger.info(f"数据已预处理，保持原样。当前维度: {adata.shape[0]:,} 细胞 × {adata.shape[1]:,} 基因")
            if 'highly_variable' in adata.var.columns:
                logger.info(f"高变基因数量: {norm_result['n_hvg']:,}")
        else:
            logger.info("步骤3: 数据标准化")
            norm_result = perform_normalization(
                adata, normalization_method, target_sum, 
                highly_variable_genes, n_top_genes, hvg_flavor,
                scale, scale_zero_center, scale_max_value
            )
            adata = norm_result["adata"]
        
        # 为h5ad文件生成独立的UUID（包含扩展名）
        h5ad_id = f"{str(uuid.uuid4())}.h5ad"
        output_file_path = os.path.join(OUTPUT_DIR, h5ad_id)
        adata.write_h5ad(output_file_path)
        logger.info(f"预处理后的数据已保存: {output_file_path}")
        
        # 生成可视化图（每个图片都有独立的ID）
        plot_files = generate_qc_plots(adata, OUTPUT_DIR, qc_result)
        
        # Format processing statistics as text
        stats_text_parts = []
        stats_text_parts.append("=== I. Initial Data Dimensions ===")
        stats_text_parts.append(f"  Cells: {initial_shape[0]:,}")
        stats_text_parts.append(f"  Genes: {initial_shape[1]:,}")
        
        # Add preprocessing check information
        if preprocess_check["is_preprocessed"]:
            stats_text_parts.append(f"\n=== Preprocessing Check Results ===")
            stats_text_parts.append(f"  Detection: Data is preprocessed, corresponding steps skipped")
            stats_text_parts.append(f"  Reasons:")
            for reason in preprocess_check["reasons"]:
                stats_text_parts.append(f"    - {reason}")
            if preprocess_check["skip_qc"]:
                stats_text_parts.append(f"  Skipped: Quality Control")
            if preprocess_check["skip_normalization"]:
                stats_text_parts.append(f"  Skipped: Data Normalization")
        
        stats_text_parts.append(f"\n=== II. Quality Control Statistics ===")
        stats_text_parts.append(f"  Initial cells: {qc_result['initial_cells']:,}")
        stats_text_parts.append(f"  Final cells: {qc_result['final_cells']:,}")
        stats_text_parts.append(f"  Cells removed: {qc_result['cells_removed']:,}")
        stats_text_parts.append(f"  Initial genes: {qc_result['initial_genes']:,}")
        stats_text_parts.append(f"  Final genes: {qc_result['final_genes']:,}")
        stats_text_parts.append(f"  Genes removed: {qc_result['genes_removed']:,}")
        stats_text_parts.append(f"  Mitochondrial-filtered cells removed: {qc_result['mito_cells_removed']:,}")
        
        # Add detailed statistics
        if 'n_genes' in qc_metrics:
            ng = qc_metrics['n_genes']
            stats_text_parts.append(f"\n  Number of genes per cell distribution:")
            stats_text_parts.append(f"    Min: {ng['min']:.0f}")
            stats_text_parts.append(f"    Max: {ng['max']:.0f}")
            stats_text_parts.append(f"    Mean: {ng['mean']:.2f}")
            stats_text_parts.append(f"    Median: {ng['median']:.2f}")
            stats_text_parts.append(f"    Std: {ng['std']:.2f}")
        
        if 'total_counts' in qc_metrics:
            tc = qc_metrics['total_counts']
            stats_text_parts.append(f"\n  UMI count distribution:")
            stats_text_parts.append(f"    Min: {tc['min']:,.0f}")
            stats_text_parts.append(f"    Max: {tc['max']:,.0f}")
            stats_text_parts.append(f"    Mean: {tc['mean']:,.2f}")
            stats_text_parts.append(f"    Median: {tc['median']:,.2f}")
            stats_text_parts.append(f"    Std: {tc['std']:,.2f}")
        
        if 'pct_counts_mt' in qc_metrics:
            pm = qc_metrics['pct_counts_mt']
            stats_text_parts.append(f"\n  Mitochondrial percentage distribution:")
            stats_text_parts.append(f"    Min: {pm['min']:.2f}%")
            stats_text_parts.append(f"    Max: {pm['max']:.2f}%")
            stats_text_parts.append(f"    Mean: {pm['mean']:.2f}%")
            stats_text_parts.append(f"    Median: {pm['median']:.2f}%")
            stats_text_parts.append(f"    Std: {pm['std']:.2f}%")
        
        stats_text_parts.append(f"\n=== III. Data Normalization Statistics ===")
        stats_text_parts.append(f"  Normalization method: {norm_result['method']}")
        target_sum_str = norm_result['target_sum']
        if isinstance(target_sum_str, (int, float)):
            stats_text_parts.append(f"  Target sum: {target_sum_str:,.0f}")
        else:
            stats_text_parts.append(f"  Target sum: {target_sum_str}")
        stats_text_parts.append(f"  HVG method: {norm_result.get('hvg_flavor', 'N/A')}")
        stats_text_parts.append(f"  Number of HVGs: {norm_result['n_hvg']:,}")
        if norm_result.get('scale', False):
            stats_text_parts.append(f"  Scale normalization: Applied (zero_center={scale_zero_center}, max_value={scale_max_value})")
        else:
            stats_text_parts.append(f"  Scale normalization: Not applied")
        stats_text_parts.append(f"  Final data dimensions: {norm_result['final_shape'][0]:,} cells × {norm_result['final_shape'][1]:,} genes")
        
        stats_text = "\n".join(stats_text_parts)
        
        # 保存统计报告
        statistics_id = f"{str(uuid.uuid4())}.txt"
        statistics_path = os.path.join(OUTPUT_DIR, statistics_id)
        with open(statistics_path, "w", encoding="utf-8") as f:
            f.write(stats_text)
        logger.info(f"Statistics report saved: {statistics_path}")
        
        # 构建返回数据字典 - 每个文件使用独立的ID（包含扩展名）
        data_dict = {
            "preprocessed_data.h5ad": h5ad_id,
            "statistics.txt": statistics_id,  # 统计报告
            "qc_violin.png": plot_files.get('qc_violin', f"{str(uuid.uuid4())}.png"),      # 每个图片都有独立的ID
            "qc_scatter.png": plot_files.get('qc_scatter', f"{str(uuid.uuid4())}.png"),      # 每个图片都有独立的ID
            "qc_filtering.png": plot_files.get('qc_filtering', f"{str(uuid.uuid4())}.png")     # 每个图片都有独立的ID
        }
        
        # 返回 JSON 响应，数据放在 data 下
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Data preprocessing completed",
                "data": data_dict
            }
        )
    
    except Exception as e:
        logger.error(f"数据预处理失败: {str(e)}", exc_info=True)
        
        # 构建错误上下文，用于提供参数建议
        error_context = {
            "min_genes": min_genes,
            "min_cells": min_cells,
            "max_mito_percent": max_mito_percent
        }
        
        # 尝试获取QC结果（如果已经执行过QC步骤）
        try:
            if 'qc_result' in locals() and qc_result is not None:
                error_context.update({
                    "initial_cells": qc_result.get("initial_cells", 0),
                    "final_cells": qc_result.get("final_cells", 0),
                    "initial_genes": qc_result.get("initial_genes", 0),
                    "final_genes": qc_result.get("final_genes", 0),
                    "cells_removed": qc_result.get("cells_removed", 0),
                    "genes_removed": qc_result.get("genes_removed", 0),
                    "mito_cells_removed": qc_result.get("mito_cells_removed", 0)
                })
        except (NameError, AttributeError):
            pass  # qc_result 可能还未定义
        
        error_info = handle_error("integrated_preprocessing", e, context=error_context)
        error_message = format_error_info_to_message(error_info)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": error_message
            }
        )
    
    finally:
        # 清理临时输入文件
        if temp_input_path and os.path.exists(temp_input_path):
            try:
                os.remove(temp_input_path)
            except Exception as e:
                logger.warning(f"清理临时文件失败: {e}")


@app.get("/api/download/{file_id}")
async def download_file(file_id: str):
    """
    根据文件ID下载处理后的文件
    
    **参数说明**:
    - `file_id`: 文件ID（由预处理/分析接口返回，每个文件都有独立的UUID+扩展名）
    
    **返回**:
    - 文件内容（二进制流）
    - 如果文件不存在，返回 404 错误
    
    **说明**:
    - file_id就是完整的文件名（UUID+扩展名），直接使用file_id查找文件
    - 不再使用前缀模式，每个文件都有独立的ID
    """
    # file_id就是文件名（UUID+扩展名），直接查找
    file_path = os.path.join(OUTPUT_DIR, file_id)
    
    # 检查文件是否存在
    if not os.path.exists(file_path):
        logger.warning(f"文件不存在: file_id={file_id}")
        raise HTTPException(
            status_code=404,
            detail=f"File not found or expired: file_id={file_id}"
        )
    
    # 根据文件扩展名确定媒体类型
    if file_path.endswith(".csv"):
        media_type = "text/csv"
    elif file_path.endswith(".png"):
        media_type = "image/png"
    elif file_path.endswith(".h5ad"):
        media_type = "application/octet-stream"
    else:
        media_type = "application/octet-stream"
    
    # 返回文件
    filename = os.path.basename(file_path)
    logger.info(f"下载文件: {file_path}, file_id: {file_id}")
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type=media_type
    )


@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {
        "status": "healthy",
        "bio_available": BIO_AVAILABLE,
        "output_dir": OUTPUT_DIR,
        "services": [
            "preprocess",
            "spatial-analysis",
            "spatialde"
        ]
    }


if __name__ == "__main__":
    import uvicorn, os as _os
    _port = int(_os.getenv("PORT", 8086))
    uvicorn.run(app, host="0.0.0.0", port=_port)
