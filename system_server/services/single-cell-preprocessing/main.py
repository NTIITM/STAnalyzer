#!/usr/bin/env python3
"""
单细胞数据预处理服务 - FastAPI
提供单细胞RNA-seq数据的质量控制、标准化和高可变基因识别
"""
import os
import logging
from logging.handlers import RotatingFileHandler
import traceback
import tempfile
import uuid
from typing import Dict, Any, Optional, Literal

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.exceptions import RequestValidationError

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
except Exception as e:
    logging.warning(f"生物信息学包导入失败: {e}")
    BIO_AVAILABLE = False
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

app = FastAPI(
    title="单细胞数据预处理服务",
    description="提供单细胞RNA-seq数据的预处理、质量控制和标准化功能",
    version="1.0.0",
)

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
    return {
        "error": True,
        "step": step,
        "error_type": type(error).__name__,
        "error_message": str(error),
        "traceback": traceback.format_exc(),
    }

def _read_adata(
    file_path: str,
    file_type: Literal["auto", "h5ad", "10x_h5", "csv", "tsv"] = "auto",
) -> "ad.AnnData":
    if file_type == "auto":
        if file_path.endswith(".h5ad"):
            return ad.read_h5ad(file_path)
        if file_path.endswith(".h5"):
            return sc.read_10x_h5(file_path)
        if file_path.endswith(".csv"):
            df = pd.read_csv(file_path, index_col=0)
            return ad.AnnData(X=df.values, var=pd.DataFrame(index=df.columns))
        if file_path.endswith(".tsv"):
            df = pd.read_csv(file_path, sep="\t", index_col=0)
            return ad.AnnData(X=df.values, var=pd.DataFrame(index=df.columns))
        return sc.read(file_path)
    if file_type == "h5ad":
        return ad.read_h5ad(file_path)
    if file_type == "10x_h5":
        return sc.read_10x_h5(file_path)
    if file_type == "csv":
        df = pd.read_csv(file_path, index_col=0)
        return ad.AnnData(X=df.values, var=pd.DataFrame(index=df.columns))
    if file_type == "tsv":
        df = pd.read_csv(file_path, sep="\t", index_col=0)
        return ad.AnnData(X=df.values, var=pd.DataFrame(index=df.columns))
    raise ValueError(f"Unsupported file_type: {file_type}")

def generate_qc_plots(adata: ad.AnnData, file_id: str, output_dir: str) -> Dict[str, str]:
    """生成QC可视化图"""
    plot_files = {}
    if not PLOT_AVAILABLE:
        return plot_files
    
    try:
        # QC指标violin plot
        fig, axes = plt.subplots(1, 3, figsize=(15, 5))
        fig.suptitle('Quality Control Metrics', fontsize=16, fontweight='bold')
        
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
        
        plt.tight_layout()
        qc_plot_path = os.path.join(output_dir, f"qc_metrics_{file_id}.png")
        plt.savefig(qc_plot_path, dpi=300, bbox_inches='tight')
        plt.close()
        plot_files['qc_metrics'] = qc_plot_path
        logger.info(f"QC metrics plot saved: {qc_plot_path}")
    except Exception as e:
        logger.warning(f"Failed to generate QC plots: {e}")
    
    return plot_files

def generate_hvg_plot(adata: ad.AnnData, file_id: str, output_dir: str) -> Optional[str]:
    """生成高变基因选择图"""
    if not PLOT_AVAILABLE or 'means' not in adata.var.columns or 'dispersions' not in adata.var.columns:
        return None
    
    try:
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # 检查是否有highly_variable列
        if 'highly_variable' in adata.var.columns:
            hvg = adata.var['highly_variable']
            ax.scatter(adata.var.loc[~hvg, 'means'], 
                     adata.var.loc[~hvg, 'dispersions'],
                     s=1, alpha=0.5, label='Other genes', color='gray')
            ax.scatter(adata.var.loc[hvg, 'means'],
                     adata.var.loc[hvg, 'dispersions'],
                     s=1, alpha=0.7, label='Highly variable genes', color='red')
        else:
            ax.scatter(adata.var['means'], adata.var['dispersions'],
                     s=1, alpha=0.5, color='gray')
        
        ax.set_xlabel('Mean Expression', fontsize=12)
        ax.set_ylabel('Dispersion', fontsize=12)
        ax.set_title('Highly Variable Genes Selection', fontsize=14, fontweight='bold')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        hvg_plot_path = os.path.join(output_dir, f"hvg_selection_{file_id}.png")
        plt.savefig(hvg_plot_path, dpi=300, bbox_inches='tight')
        plt.close()
        logger.info(f"HVG plot saved: {hvg_plot_path}")
        return hvg_plot_path
    except Exception as e:
        logger.warning(f"Failed to generate HVG plot: {e}")
        return None

def perform_quality_control(
    adata: ad.AnnData,
    min_genes: int = 200,
    min_cells: int = 3,
    max_mito_percent: float = 20.0,
    mito_prefix: str = "MT-"
) -> Dict[str, Any]:
    """执行质量控制"""
    initial_cells = adata.n_obs
    initial_genes = adata.n_vars
    
    # 计算QC指标
    logger.info("计算质量控制指标")
    mt_key = "mt"
    adata.var[mt_key] = adata.var_names.str.startswith(mito_prefix)
    sc.pp.calculate_qc_metrics(adata, qc_vars=[mt_key], percent_top=None, log1p=False, inplace=True)
    
    # 保存过滤前的QC指标用于统计
    qc_metrics_before = {}
    if 'total_counts' in adata.obs.columns:
        qc_metrics_before['total_counts_mean'] = float(adata.obs['total_counts'].mean())
        qc_metrics_before['total_counts_median'] = float(adata.obs['total_counts'].median())
    if 'n_genes_by_counts' in adata.obs.columns:
        qc_metrics_before['n_genes_mean'] = float(adata.obs['n_genes_by_counts'].mean())
        qc_metrics_before['n_genes_median'] = float(adata.obs['n_genes_by_counts'].median())
    if 'pct_counts_mt' in adata.obs.columns:
        qc_metrics_before['pct_counts_mt_mean'] = float(adata.obs['pct_counts_mt'].mean())
        qc_metrics_before['pct_counts_mt_median'] = float(adata.obs['pct_counts_mt'].median())
    
    # 过滤低质量细胞和基因
    logger.info(f"过滤细胞 (min_genes={min_genes})")
    sc.pp.filter_cells(adata, min_genes=min_genes)
    
    logger.info(f"过滤基因 (min_cells={min_cells})")
    sc.pp.filter_genes(adata, min_cells=min_cells)
    
    # 线粒体基因过滤
    pct_col = "pct_counts_mt"
    mito_removed = 0
    if max_mito_percent > 0 and pct_col in adata.obs.columns:
        logger.info(f"过滤线粒体基因 (max_mito_percent={max_mito_percent})")
        before_mito = int(adata.n_obs)
        adata = adata[adata.obs[pct_col] < max_mito_percent, :].copy()
        mito_removed = before_mito - int(adata.n_obs)
        logger.info(f"基于线粒体基因过滤移除 {mito_removed} 个细胞")
    else:
        logger.info("跳过线粒体基因过滤")
    
    # 保存过滤后的QC指标
    qc_metrics_after = {}
    if 'total_counts' in adata.obs.columns:
        qc_metrics_after['total_counts_mean'] = float(adata.obs['total_counts'].mean())
        qc_metrics_after['total_counts_median'] = float(adata.obs['total_counts'].median())
    if 'n_genes_by_counts' in adata.obs.columns:
        qc_metrics_after['n_genes_mean'] = float(adata.obs['n_genes_by_counts'].mean())
        qc_metrics_after['n_genes_median'] = float(adata.obs['n_genes_by_counts'].median())
    if 'pct_counts_mt' in adata.obs.columns:
        qc_metrics_after['pct_counts_mt_mean'] = float(adata.obs['pct_counts_mt'].mean())
        qc_metrics_after['pct_counts_mt_median'] = float(adata.obs['pct_counts_mt'].median())
    
    return {
        "adata": adata,
        "initial_cells": initial_cells,
        "final_cells": adata.n_obs,
        "cells_removed": initial_cells - adata.n_obs,
        "initial_genes": initial_genes,
        "final_genes": adata.n_vars,
        "genes_removed": initial_genes - adata.n_vars,
        "mito_cells_removed": mito_removed,
        "qc_metrics_before": qc_metrics_before,
        "qc_metrics_after": qc_metrics_after
    }

def perform_normalization(
    adata: ad.AnnData,
    method: Literal["log1p", "sqrt", "none"] = "log1p",
    target_sum: float = 1e4,
    highly_variable_genes: bool = True,
    n_top_genes: int = 2000,
    flavor: Literal["seurat_v3", "seurat", "cell_ranger"] = "seurat_v3"
) -> Dict[str, Any]:
    """执行数据标准化"""
    # 保存标准化前的表达量统计
    if sparse.issparse(adata.X):
        expr_before = np.array(adata.X.sum(axis=1)).flatten()
    else:
        expr_before = adata.X.sum(axis=1)
    expr_stats_before = {
        'mean': float(expr_before.mean()),
        'median': float(np.median(expr_before)),
        'std': float(expr_before.std())
    }
    
    # 标准化
    logger.info(f"标准化数据 (target_sum={target_sum})")
    sc.pp.normalize_total(adata, target_sum=target_sum)
    
    logger.info(f"应用转换方法: {method}")
    if method == "log1p":
        sc.pp.log1p(adata)
    elif method == "sqrt":
        if sparse.issparse(adata.X):
            adata.X = np.sqrt(adata.X.A)
        else:
            adata.X = np.sqrt(adata.X)
    elif method == "none":
        logger.info("跳过数据转换")
    
    # 保存标准化后的表达量统计
    if sparse.issparse(adata.X):
        expr_after = np.array(adata.X.sum(axis=1)).flatten()
    else:
        expr_after = adata.X.sum(axis=1)
    expr_stats_after = {
        'mean': float(expr_after.mean()),
        'median': float(np.median(expr_after)),
        'std': float(expr_after.std())
    }
    
    # 高变基因选择
    n_hvg = 0
    hvg_stats = {}
    if highly_variable_genes:
        logger.info(f"选择高变基因 (n_top_genes={n_top_genes}, flavor={flavor})")
        try:
            sc.pp.highly_variable_genes(adata, n_top_genes=n_top_genes, flavor=flavor, inplace=True)
            n_hvg = adata.var.highly_variable.sum()
            if 'means' in adata.var.columns and 'dispersions' in adata.var.columns:
                hvg_stats['mean_expression_mean'] = float(adata.var['means'].mean())
                hvg_stats['dispersion_mean'] = float(adata.var['dispersions'].mean())
                hvg_stats['hvg_dispersion_mean'] = float(adata.var.loc[adata.var.highly_variable, 'dispersions'].mean()) if n_hvg > 0 else 0.0
            adata = adata[:, adata.var.highly_variable].copy()
            logger.info(f"选择了 {n_hvg} 个高变基因")
        except Exception as e:
            logger.warning(f"高变基因选择失败: {e}")
            n_hvg = 0
    
    return {
        "adata": adata,
        "method": method,
        "target_sum": target_sum,
        "n_hvg": n_hvg,
        "final_shape": list(adata.shape),
        "expr_stats_before": expr_stats_before,
        "expr_stats_after": expr_stats_after,
        "hvg_stats": hvg_stats
    }

@app.post("/api/preprocess")
async def preprocess(
    file: UploadFile = File(..., description="单细胞数据文件"),
    file_type: Literal["auto", "h5ad", "10x_h5", "csv", "tsv"] = Form("auto"),
    # 质量控制参数
    min_genes: int = Form(200, description="每个细胞最少表达的基因数"),
    min_cells: int = Form(3, description="每个基因最少在多少个细胞中表达"),
    max_mito_percent: float = Form(20.0, description="线粒体基因最大百分比"),
    mito_prefix: str = Form("MT-", description="线粒体基因前缀"),
    # 标准化参数
    normalization_method: Literal["log1p", "sqrt", "none"] = Form("log1p", description="标准化方法"),
    target_sum: float = Form(1e4, description="标准化目标总和"),
    highly_variable_genes: bool = Form(True, description="是否选择高变基因"),
    n_top_genes: int = Form(2000, description="高变基因数量"),
    hvg_flavor: Literal["seurat_v3", "seurat", "cell_ranger"] = Form("seurat_v3", description="高变基因选择方法"),
) -> JSONResponse:
    if not BIO_AVAILABLE:
        return JSONResponse(status_code=500, content={"success": False, "message": "生物信息学包未安装"})
    temp_input_path = None
    try:
        file_id = str(uuid.uuid4())
        temp_input_path = os.path.join(tempfile.gettempdir(), f"input_{file_id}_{file.filename}")
        with open(temp_input_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        logger.info(f"文件已保存: {temp_input_path}, 大小: {len(content)} bytes")
        
        # 加载数据
        logger.info("步骤1: 加载数据")
        adata = _read_adata(temp_input_path, file_type)
        initial_shape = adata.shape
        
        # 质量控制
        logger.info("步骤2: 质量控制")
        qc_result = perform_quality_control(adata, min_genes, min_cells, max_mito_percent, mito_prefix)
        adata = qc_result["adata"]
        
        # 数据标准化
        logger.info("步骤3: 数据标准化")
        norm_result = perform_normalization(
            adata, normalization_method, target_sum, 
            highly_variable_genes, n_top_genes, hvg_flavor
        )
        adata = norm_result["adata"]
        
        # 保存处理后的数据
        output_filename = f"preprocessed_{file_id}.h5ad"
        output_file_path = os.path.join(OUTPUT_DIR, output_filename)
        adata.write_h5ad(output_file_path)
        logger.info(f"预处理后的数据已保存: {output_file_path}")
        
        # 生成可视化图片
        plot_files = {}
        if PLOT_AVAILABLE:
            # 需要重新加载数据用于绘图（因为可能已经过滤了高变基因）
            adata_for_plot = _read_adata(temp_input_path, file_type)
            # 重新计算QC指标
            mt_key = "mt"
            adata_for_plot.var[mt_key] = adata_for_plot.var_names.str.startswith(mito_prefix)
            sc.pp.calculate_qc_metrics(adata_for_plot, qc_vars=[mt_key], percent_top=None, log1p=False, inplace=True)
            sc.pp.filter_cells(adata_for_plot, min_genes=min_genes)
            sc.pp.filter_genes(adata_for_plot, min_cells=min_cells)
            if max_mito_percent > 0 and "pct_counts_mt" in adata_for_plot.obs.columns:
                adata_for_plot = adata_for_plot[adata_for_plot.obs["pct_counts_mt"] < max_mito_percent, :].copy()
            
            # 生成QC图
            qc_plots = generate_qc_plots(adata_for_plot, file_id, OUTPUT_DIR)
            plot_files.update(qc_plots)
            
            # 标准化并生成HVG图
            sc.pp.normalize_total(adata_for_plot, target_sum=target_sum)
            if normalization_method == "log1p":
                sc.pp.log1p(adata_for_plot)
            if highly_variable_genes:
                try:
                    sc.pp.highly_variable_genes(adata_for_plot, n_top_genes=n_top_genes, flavor=hvg_flavor, inplace=True)
                    hvg_path = generate_hvg_plot(adata_for_plot, file_id, OUTPUT_DIR)
                    if hvg_path:
                        plot_files['hvg_selection'] = hvg_path
                except Exception as e:
                    logger.warning(f"Failed to generate HVG plot: {e}")
        
        # 格式化精细化统计信息
        stats_text_parts = []
        stats_text_parts.append("=" * 60)
        stats_text_parts.append("单细胞数据预处理统计报告")
        stats_text_parts.append("=" * 60)
        
        stats_text_parts.append("\n【一、初始数据维度】")
        stats_text_parts.append(f"  细胞数: {initial_shape[0]:,}")
        stats_text_parts.append(f"  基因数: {initial_shape[1]:,}")
        
        stats_text_parts.append("\n【二、质量控制统计】")
        stats_text_parts.append(f"  初始细胞数: {qc_result['initial_cells']:,}")
        stats_text_parts.append(f"  最终细胞数: {qc_result['final_cells']:,}")
        cells_removed_pct = (qc_result['cells_removed'] / qc_result['initial_cells'] * 100) if qc_result['initial_cells'] > 0 else 0
        stats_text_parts.append(f"  移除细胞数: {qc_result['cells_removed']:,} ({cells_removed_pct:.2f}%)")
        stats_text_parts.append(f"  初始基因数: {qc_result['initial_genes']:,}")
        stats_text_parts.append(f"  最终基因数: {qc_result['final_genes']:,}")
        genes_removed_pct = (qc_result['genes_removed'] / qc_result['initial_genes'] * 100) if qc_result['initial_genes'] > 0 else 0
        stats_text_parts.append(f"  移除基因数: {qc_result['genes_removed']:,} ({genes_removed_pct:.2f}%)")
        stats_text_parts.append(f"  线粒体过滤移除细胞数: {qc_result['mito_cells_removed']:,}")
        
        # QC指标统计
        if qc_result.get('qc_metrics_before') and qc_result.get('qc_metrics_after'):
            stats_text_parts.append("\n  【QC指标变化】")
            qc_before = qc_result['qc_metrics_before']
            qc_after = qc_result['qc_metrics_after']
            if 'total_counts_mean' in qc_before:
                stats_text_parts.append(f"    平均UMI数: {qc_before.get('total_counts_mean', 0):.2f} → {qc_after.get('total_counts_mean', 0):.2f}")
            if 'n_genes_mean' in qc_before:
                stats_text_parts.append(f"    平均基因数: {qc_before.get('n_genes_mean', 0):.2f} → {qc_after.get('n_genes_mean', 0):.2f}")
            if 'pct_counts_mt_mean' in qc_before:
                stats_text_parts.append(f"    平均线粒体%: {qc_before.get('pct_counts_mt_mean', 0):.2f}% → {qc_after.get('pct_counts_mt_mean', 0):.2f}%")
        
        stats_text_parts.append("\n【三、数据标准化统计】")
        stats_text_parts.append(f"  标准化方法: {norm_result['method']}")
        stats_text_parts.append(f"  目标总和: {norm_result['target_sum']:.0f}")
        
        # 表达量统计
        if norm_result.get('expr_stats_before') and norm_result.get('expr_stats_after'):
            stats_text_parts.append("\n  【表达量分布变化】")
            expr_before = norm_result['expr_stats_before']
            expr_after = norm_result['expr_stats_after']
            stats_text_parts.append(f"    平均表达量: {expr_before.get('mean', 0):.2f} → {expr_after.get('mean', 0):.2f}")
            stats_text_parts.append(f"    中位表达量: {expr_before.get('median', 0):.2f} → {expr_after.get('median', 0):.2f}")
            stats_text_parts.append(f"    标准差: {expr_before.get('std', 0):.2f} → {expr_after.get('std', 0):.2f}")
        
        stats_text_parts.append(f"\n  高变基因选择: {'是' if highly_variable_genes else '否'}")
        if highly_variable_genes:
            stats_text_parts.append(f"  高变基因数量: {norm_result['n_hvg']:,}")
            stats_text_parts.append(f"  高变基因比例: {(norm_result['n_hvg'] / norm_result['final_shape'][1] * 100):.2f}%")
            if norm_result.get('hvg_stats'):
                hvg_stats = norm_result['hvg_stats']
                if 'hvg_dispersion_mean' in hvg_stats:
                    stats_text_parts.append(f"  高变基因平均离散度: {hvg_stats['hvg_dispersion_mean']:.4f}")
        
        stats_text_parts.append(f"\n  最终数据维度: {norm_result['final_shape'][0]:,} 细胞 × {norm_result['final_shape'][1]:,} 基因")
        
        stats_text_parts.append("\n【四、数据质量评估】")
        if qc_result['cells_removed'] / qc_result['initial_cells'] < 0.1:
            stats_text_parts.append("  ✓ 细胞过滤率较低，数据质量良好")
        elif qc_result['cells_removed'] / qc_result['initial_cells'] < 0.3:
            stats_text_parts.append("  ⚠ 细胞过滤率中等，建议检查原始数据质量")
        else:
            stats_text_parts.append("  ✗ 细胞过滤率较高，可能存在数据质量问题")
        
        if norm_result['n_hvg'] >= 1000:
            stats_text_parts.append("  ✓ 高变基因数量充足，适合后续分析")
        elif norm_result['n_hvg'] >= 500:
            stats_text_parts.append("  ⚠ 高变基因数量中等，可能影响降维效果")
        else:
            stats_text_parts.append("  ✗ 高变基因数量较少，建议调整参数或检查数据")
        
        # 构建返回数据
        data_dict = {
            "preprocessed_data.h5ad": file_id
        }
        
        # 添加图片文件ID
        for plot_name, plot_path in plot_files.items():
            if plot_path and os.path.exists(plot_path):
                plot_filename = os.path.basename(plot_path)
                plot_file_id = plot_filename.replace(f"_{file_id}.png", "").replace(f"{file_id}.png", "")
                # 提取file_id
                if f"_{file_id}.png" in plot_filename:
                    plot_file_id = file_id
                data_dict[f"{plot_name}.png"] = file_id
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "单细胞数据预处理完成",
                "data": data_dict
            }
        )
    except Exception as e:
        logger.error("单细胞数据预处理失败: %s", e, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": "单细胞数据预处理失败",
                "error": _handle_error("preprocess", e)
            }
        )
    finally:
        if temp_input_path and os.path.exists(temp_input_path):
            try:
                os.remove(temp_input_path)
            except Exception as e:
                logger.warning("清理临时文件失败: %s", e)

@app.get("/api/download/{file_id}")
async def download_file(file_id: str, file_type: str = "h5ad") -> FileResponse:
    """下载文件，支持h5ad和png格式"""
    if file_type == "png":
        # 尝试查找PNG文件
        possible_names = [
            f"qc_metrics_{file_id}.png",
            f"hvg_selection_{file_id}.png"
        ]
        for filename in possible_names:
            file_path = os.path.join(OUTPUT_DIR, filename)
            if os.path.exists(file_path):
                return FileResponse(path=file_path, filename=filename, media_type="image/png")
        raise HTTPException(status_code=404, detail="PNG文件不存在或已过期")
    else:
        filename = f"preprocessed_{file_id}.h5ad"
        file_path = os.path.join(OUTPUT_DIR, filename)
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="文件不存在或已过期")
        return FileResponse(path=file_path, filename=filename, media_type="application/octet-stream")

@app.get("/health")
async def health():
    return {"status": "healthy", "bio_available": BIO_AVAILABLE, "output_dir": OUTPUT_DIR}

if __name__ == "__main__":
    import uvicorn
    import os as _os
    _port = int(_os.getenv("PORT", 53000))
    uvicorn.run(app, host="0.0.0.0", port=_port)

