#!/usr/bin/env python3
"""
空间转录组细胞类型标注服务（基于SCSA方法）- FastAPI

核心思路：
- 输入：已经预处理/聚类完成的空间转录组 AnnData
- 使用 SCSA (Single Cell Signature Annotation) 方法进行自动注释
- 基于 omicverse 的 pySCSA，支持 CellMarker 和 PanglaoDB 数据库
- 对每个 cluster 计算差异表达基因，与数据库中的 marker 基因比对
- 输出带有 cell_type 的 AnnData 及统计和可视化

参考：https://www.cnblogs.com/starlitnightly/p/18258594
"""
import os
import json
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
    # 验证 pandas 版本（omicverse 2023 数据库要求 pandas<2.0）
    if not pd.__version__.startswith('1.'):
        raise RuntimeError(f"pandas 版本错误: {pd.__version__}，omicverse 2023 数据库需要 pandas<2.0，请降级 pandas 版本")
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import seaborn as sns
    import requests
    
    # 尝试导入 omicverse
    try:
        import omicverse as ov
        # 检查是否有 pySCSA 功能
        if hasattr(ov, 'single') and hasattr(ov.single, 'pySCSA'):
            OMV_AVAILABLE = True
        else:
            OMV_AVAILABLE = False
            logging.warning("omicverse imported but pySCSA not available")
    except (ImportError, ModuleNotFoundError, Exception) as e:
        OMV_AVAILABLE = False
        logging.warning(f"omicverse not available, SCSA annotation will not work: {e}")

    plt.rcParams["font.sans-serif"] = ["Arial", "DejaVu Sans", "Liberation Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    BIO_AVAILABLE = True
    PLOT_AVAILABLE = True
except Exception as e:
    logging.warning(f"生物信息学/绘图包导入失败: {e}")
    BIO_AVAILABLE = False
    PLOT_AVAILABLE = False
    OMV_AVAILABLE = False


def _setup_logging() -> None:
    """控制台 + 滚动文件日志配置"""
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
    title="空间转录组细胞类型标注服务（SCSA）",
    description=(
        "基于 SCSA (Single Cell Signature Annotation) 方法，对空间转录组数据进行细胞类型标注。\n"
        "使用 omicverse 的 pySCSA，支持 CellMarker 和 PanglaoDB 数据库。"
    ),
    version="1.0.0",
)

OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)


# 请求日志中间件
try:
    import time
    from starlette.middleware.base import BaseHTTPMiddleware

    class RequestLogMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            start = time.time()
            response = None
            try:
                response = await call_next(request)
                return response
            finally:
                duration = (time.time() - start) * 1000.0
                status = getattr(response, "status_code", -1) if response else -1
                logger.info(
                    "request %s %s -> %s (%.1f ms)",
                    request.method,
                    request.url.path,
                    status,
                    duration,
                )

    app.add_middleware(RequestLogMiddleware)
except Exception as _e:
    logger.debug("中间件初始化失败: %s", _e)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    error_details = exc.errors()
    error_body = exc.body if hasattr(exc, "body") else None
    logger.error(
        "请求验证失败: %s %s\n错误详情: %s\n请求体: %s",
        request.method,
        request.url.path,
        error_details,
        error_body[:500] if error_body else None,
        exc_info=True,
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
        exc_info=True,
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
    """统一 AnnData 读取"""
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


def _find_cluster_key(adata: "ad.AnnData", cluster_key: Optional[str] = None) -> str:
    """查找 cluster 列名"""
    if cluster_key and cluster_key in adata.obs.columns:
        return cluster_key
    
    # 尝试常见的 cluster 列名
    common_keys = ["cluster", "leiden", "louvain", "leiden_res1", "layer"]
    for key in common_keys:
        if key in adata.obs.columns:
            logger.info(f"使用找到的 cluster 列: {key}")
            return key
    
    raise ValueError(
        f"未找到 cluster 列。提供的 cluster_key='{cluster_key}'，"
        f"可用的列: {list(adata.obs.columns)}"
    )


def _ensure_log1p_base(adata: "ad.AnnData") -> None:
    """确保 log1p base 设置正确"""
    if "log1p" not in adata.uns:
        adata.uns["log1p"] = {}
    if "base" not in adata.uns["log1p"]:
        adata.uns["log1p"]["base"] = None  # SCSA 会自动处理


def _run_scsa_annotation(
    adata: "ad.AnnData",
    cluster_key: str,
    foldchange: float = 1.5,
    pvalue: float = 0.01,
    celltype: str = "normal",
    target: str = "cellmarker",
    tissue: str = "All",
    rank_rep: bool = True,
    model_path: Optional[str] = None,
) -> tuple["ad.AnnData", pd.DataFrame]:
    """
    运行 SCSA 注释
    
    返回:
        (annotated_adata, annotation_results_df)
    """
    if not OMV_AVAILABLE:
        raise ImportError("omicverse 未安装，无法使用 SCSA 方法")
    
    # 创建一个临时的 cluster 列，使用数字格式（避免 omicverse 解析错误）
    # omicverse 的 cell_auto_anno 期望 cluster 名称是数字格式
    temp_cluster_key = f"{cluster_key}_scsa_temp"
    cluster_mapping = {}
    reverse_mapping = {}
    
    unique_clusters = adata.obs[cluster_key].unique()
    for i, cluster in enumerate(unique_clusters):
        # 使用数字作为临时 cluster 名称（omicverse 需要）
        new_name = str(i)
        cluster_mapping[cluster] = new_name
        reverse_mapping[new_name] = cluster
    
    # 创建临时 cluster 列
    adata.obs[temp_cluster_key] = adata.obs[cluster_key].map(cluster_mapping)
    logger.info(f"临时 cluster 映射: {dict(list(cluster_mapping.items())[:5])}... (共 {len(cluster_mapping)} 个)")
    
    logger.info("初始化 SCSA 对象...")
    logger.info(f"参数: foldchange={foldchange}, pvalue={pvalue}, celltype={celltype}, target={target}, tissue={tissue}")
    
    # 初始化 SCSA
    scsa = ov.single.pySCSA(
        adata=adata,
        foldchange=foldchange,
        pvalue=pvalue,
        celltype=celltype,
        target=target,
        tissue=tissue,
        model_path=model_path if model_path else '',  # 空字符串表示自动下载
    )
    
    logger.info("开始 SCSA 注释...")
    # 执行注释（使用临时 cluster 列）
    res = scsa.cell_anno(
        clustertype=temp_cluster_key,
        cluster='all',
        rank_rep=rank_rep
    )
    
    logger.info(f"SCSA 注释完成，res 类型: {type(res)}, 长度: {len(res) if hasattr(res, '__len__') else 'N/A'}")
    
    # 打印注释结果（用于调试）
    try:
        scsa.cell_anno_print()
    except Exception as e:
        logger.warning(f"无法打印注释结果: {e}")
    
    # 将注释结果添加到 adata（使用临时 cluster 列）
    annotation_key = f"scsa_celltype_{target}"
    try:
        scsa.cell_auto_anno(adata, clustertype=temp_cluster_key, key=annotation_key)
        logger.info(f"注释结果已添加到 adata.obs['{annotation_key}']")
    except Exception as e:
        logger.error(f"添加注释结果到 adata 失败: {e}")
        raise
    
    # 删除临时 cluster 列
    if temp_cluster_key in adata.obs.columns:
        adata.obs.drop(columns=[temp_cluster_key], inplace=True)
    
    # 提取 Z-score 信息（从注释结果中）
    # res 是 DataFrame，包含 Cluster, Cell_type, Z-score 等列
    # 我们需要从 res 中提取每个 cluster 的信息
    annotation_results = []
    
    # 获取所有已注释的 cluster
    annotated_clusters = set()
    if isinstance(res, pd.DataFrame) and len(res) > 0:
        # 检查 res 的列名（可能是 'Cluster', 'Cell_type', 'Z-score' 等）
        cluster_col = None
        celltype_col = None
        zscore_col = None
        
        for col in res.columns:
            col_lower = col.lower()
            if 'cluster' in col_lower:
                cluster_col = col
            elif 'cell' in col_lower and 'type' in col_lower:
                celltype_col = col
            elif 'z' in col_lower and 'score' in col_lower:
                zscore_col = col
        
        if cluster_col and celltype_col:
            for cluster_id in adata.obs[cluster_key].unique():
                cluster_str = str(cluster_id)
                # 重要：res 中的 cluster 是数字格式（临时 cluster），需要转换
                temp_cluster_id = cluster_mapping.get(cluster_id, str(cluster_id))
                cluster_res = res[res[cluster_col].astype(str) == str(temp_cluster_id)]
                
                if len(cluster_res) > 0:
                    # 获取主要细胞类型（第一个）
                    main_cell_type = cluster_res.iloc[0][celltype_col]
                    main_z_score = cluster_res.iloc[0][zscore_col] if zscore_col and zscore_col in cluster_res.columns else np.nan
                    
                    # 获取备选类型（如果有多个）
                    alt_types = []
                    if len(cluster_res) > 1:
                        alt_types = cluster_res.iloc[1:][celltype_col].tolist()
                    
                    annotated_clusters.add(cluster_id)
                else:
                    main_cell_type = "Unknown"
                    main_z_score = np.nan
                    alt_types = []
                    logger.warning(f"未找到 cluster {cluster_id} (临时ID: {temp_cluster_id}) 的注释结果")
                
                # 从 adata.obs 中获取实际标注的细胞类型（可能已经被 cell_auto_anno 处理过）
                cluster_mask = adata.obs[cluster_key] == cluster_id
                actual_cell_type = adata.obs.loc[cluster_mask, annotation_key].iloc[0] if cluster_mask.any() else main_cell_type
                
                annotation_results.append({
                    'cluster': cluster_str,
                    'assigned_cell_type': actual_cell_type,
                    'z_score': main_z_score,
                    'alternative_types': '|'.join(alt_types) if alt_types else ''
                })
        else:
            # 如果 res 格式不符合预期，从 adata.obs 中提取
            logger.warning("无法从 res DataFrame 中提取 Z-score，仅使用 adata.obs 中的标注")
            for cluster_id in adata.obs[cluster_key].unique():
                cluster_mask = adata.obs[cluster_key] == cluster_id
                cell_type = adata.obs.loc[cluster_mask, annotation_key].iloc[0] if cluster_mask.any() else "Unknown"
                annotation_results.append({
                    'cluster': str(cluster_id),
                    'assigned_cell_type': cell_type,
                    'z_score': np.nan,
                    'alternative_types': ''
                })
    else:
        # 如果 res 为空或不是 DataFrame，从 adata.obs 中提取
        logger.warning("SCSA 注释结果为空，仅使用 adata.obs 中的标注")
        for cluster_id in adata.obs[cluster_key].unique():
            cluster_mask = adata.obs[cluster_key] == cluster_id
            cell_type = adata.obs.loc[cluster_mask, annotation_key].iloc[0] if cluster_mask.any() else "Unknown"
            annotation_results.append({
                'cluster': str(cluster_id),
                'assigned_cell_type': cell_type,
                'z_score': np.nan,
                'alternative_types': ''
            })
    
    results_df = pd.DataFrame(annotation_results)
    
    # 将 Z-score 添加到 adata.obs
    z_score_map = dict(zip(results_df['cluster'], results_df['z_score']))
    adata.obs['scsa_z_score'] = adata.obs[cluster_key].map(z_score_map).astype(float)
    
    # 将注释结果重命名为 cell_type（统一命名）
    adata.obs['cell_type'] = adata.obs[annotation_key]
    
    return adata, results_df


def _create_visualizations(
    adata: "ad.AnnData",
    output_dir: str,
    cluster_key: str,
) -> Dict[str, str]:
    """创建可视化图表"""
    output_files = {}
    
    try:
        # 1. UMAP 图
        if 'X_umap' in adata.obsm:
            try:
                fig, ax = plt.subplots(figsize=(10, 8))
                sc.pl.umap(adata, color='cell_type', ax=ax, show=False, frameon=False)
                umap_path = os.path.join(output_dir, "annotation_umap.png")
                plt.savefig(umap_path, dpi=300, bbox_inches='tight')
                plt.close()
                output_files['umap'] = umap_path
                logger.info("UMAP 图已保存")
            except Exception as e:
                logger.warning(f"创建 UMAP 图失败: {e}")
        
        # 2. 空间分布图
        spatial_key = None
        if 'spatial' in adata.obsm:
            spatial_key = 'spatial'
        elif 'X_spatial' in adata.obsm:
            spatial_key = 'X_spatial'
        
        if spatial_key:
            fig, ax = plt.subplots(figsize=(12, 10))
            spatial_coords = adata.obsm[spatial_key]
            if spatial_coords.shape[1] >= 2:
                sc.pl.embedding(
                    adata,
                    basis=spatial_key,
                    color='cell_type',
                    ax=ax,
                    show=False,
                    frameon=False
                )
                spatial_path = os.path.join(output_dir, "annotation_spatial.png")
                plt.savefig(spatial_path, dpi=300, bbox_inches='tight')
                plt.close()
                output_files['spatial'] = spatial_path
                logger.info("空间分布图已保存")
        
        # 3. 细胞类型组成条形图
        cell_type_counts = adata.obs['cell_type'].value_counts()
        fig, ax = plt.subplots(figsize=(12, 6))
        cell_type_counts.plot(kind='bar', ax=ax)
        ax.set_xlabel('Cell Type', fontsize=12)
        ax.set_ylabel('Number of Spots', fontsize=12)
        ax.set_title('Cell Type Composition', fontsize=14)
        ax.tick_params(axis='x', rotation=45, labelsize=10)
        plt.tight_layout()
        composition_path = os.path.join(output_dir, "cell_type_composition.png")
        plt.savefig(composition_path, dpi=300, bbox_inches='tight')
        plt.close()
        output_files['composition'] = composition_path
        logger.info("细胞类型组成图已保存")
        
    except Exception as e:
        logger.warning(f"创建可视化时出错: {e}", exc_info=True)
    
    return output_files


def _generate_statistics_report(
    adata: "ad.AnnData",
    annotation_results: pd.DataFrame,
    params: Dict[str, Any],
    output_path: str,
) -> None:
    """生成统计报告"""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("=" * 60 + "\n")
        f.write("SCSA 细胞类型标注统计报告\n")
        f.write("=" * 60 + "\n\n")
        
        f.write("1. 数据基本信息\n")
        f.write("-" * 60 + "\n")
        f.write(f"总 spot 数: {adata.n_obs}\n")
        f.write(f"总基因数: {adata.n_vars}\n")
        f.write(f"Cluster 列: {params.get('cluster_key', 'N/A')}\n")
        f.write(f"Cluster 数量: {len(adata.obs[params.get('cluster_key', 'cluster')].unique())}\n\n")
        
        f.write("2. SCSA 参数\n")
        f.write("-" * 60 + "\n")
        f.write(f"数据库: {params.get('target', 'N/A')}\n")
        f.write(f"Fold change: {params.get('foldchange', 'N/A')}\n")
        f.write(f"P-value: {params.get('pvalue', 'N/A')}\n")
        f.write(f"Cell type: {params.get('celltype', 'N/A')}\n")
        f.write(f"Tissue: {params.get('tissue', 'N/A')}\n\n")
        
        f.write("3. 标注结果统计\n")
        f.write("-" * 60 + "\n")
        cell_type_counts = adata.obs['cell_type'].value_counts()
        total_spots = len(adata.obs)
        for cell_type, count in cell_type_counts.items():
            percentage = (count / total_spots) * 100
            # 获取该细胞类型的平均 Z-score
            mask = adata.obs['cell_type'] == cell_type
            z_scores = adata.obs.loc[mask, 'scsa_z_score']
            # 确保是数值类型
            if z_scores.dtype.name == 'category':
                z_scores = z_scores.astype(str).astype(float)
            avg_z_score = z_scores.mean()
            f.write(f"{cell_type}:\n")
            f.write(f"  Spot 数: {count} ({percentage:.2f}%)\n")
            f.write(f"  平均 Z-score: {avg_z_score:.3f}\n\n")
        
        f.write("4. Cluster 级别标注详情\n")
        f.write("-" * 60 + "\n")
        for _, row in annotation_results.iterrows():
            f.write(f"Cluster {row['cluster']}: {row['assigned_cell_type']}\n")
            f.write(f"  Z-score: {row['z_score']:.3f}\n")
            if row['alternative_types']:
                f.write(f"  备选类型: {row['alternative_types']}\n")
            f.write("\n")


@app.get("/health")
async def health_check():
    """健康检查端点"""
    status = {
        "status": "healthy",
        "service": "spatial-scsa-annotation",
        "version": "1.0.0",
        "bio_available": BIO_AVAILABLE,
        "plot_available": PLOT_AVAILABLE,
        "omicverse_available": OMV_AVAILABLE,
    }
    return JSONResponse(content=status)


@app.post("/api/annotate")
async def annotate(
    request: Request,
    file: UploadFile = File(...),
    cluster_key: str = Form("cluster"),
    foldchange: float = Form(1.5),
    pvalue: float = Form(0.01),
    celltype: str = Form("normal"),
    target: str = Form("cellmarker"),
    tissue: str = Form("All"),
    rank_rep: bool = Form(True),
):
    """
    执行 SCSA 细胞类型标注
    """
    if not BIO_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="生物信息学包未安装，服务不可用"
        )
    
    if not OMV_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="omicverse 未安装，SCSA 方法不可用。请安装: pip install omicverse"
        )
    
    job_id = str(uuid.uuid4())
    output_dir = os.path.join(OUTPUT_DIR, job_id)
    os.makedirs(output_dir, exist_ok=True)
    
    logger.info(f"开始处理任务 {job_id}")
    logger.info(f"参数: cluster_key={cluster_key}, foldchange={foldchange}, pvalue={pvalue}, target={target}")
    
    try:
        # 1. 保存上传的文件
        input_file = os.path.join(output_dir, "input.h5ad")
        with open(input_file, "wb") as f:
            content = await file.read()
            f.write(content)
        logger.info(f"文件已保存: {input_file} ({len(content)} bytes)")
        
        # 2. 读取 AnnData
        logger.info("读取 AnnData 数据...")
        adata = _read_adata(input_file)
        logger.info(f"数据维度: {adata.n_obs} spots × {adata.n_vars} genes")
        
        # 3. 查找 cluster 列
        actual_cluster_key = _find_cluster_key(adata, cluster_key)
        logger.info(f"使用 cluster 列: {actual_cluster_key}")
        
        # 4. 确保 log1p base 设置
        _ensure_log1p_base(adata)
        
        # 5. 运行 SCSA 注释
        logger.info("开始 SCSA 注释...")
        adata, annotation_results = _run_scsa_annotation(
            adata=adata,
            cluster_key=actual_cluster_key,
            foldchange=foldchange,
            pvalue=pvalue,
            celltype=celltype,
            target=target,
            tissue=tissue,
            rank_rep=rank_rep,
        )
        
        # 6. 保存标注后的数据
        output_h5ad = os.path.join(output_dir, "annotated_data.h5ad")
        adata.write(output_h5ad)
        logger.info(f"标注后的数据已保存: {output_h5ad}")
        
        # 7. 保存统计信息
        stats_csv = os.path.join(output_dir, "scsa_annotation_statistics.csv")
        annotation_results.to_csv(stats_csv, index=False, encoding='utf-8')
        logger.info(f"统计信息已保存: {stats_csv}")
        
        # 8. 创建可视化
        logger.info("创建可视化图表...")
        viz_files = _create_visualizations(adata, output_dir, actual_cluster_key)
        
        # 9. 生成统计报告
        stats_txt = os.path.join(output_dir, "statistics.txt")
        _generate_statistics_report(
            adata=adata,
            annotation_results=annotation_results,
            params={
                'cluster_key': actual_cluster_key,
                'foldchange': foldchange,
                'pvalue': pvalue,
                'celltype': celltype,
                'target': target,
                'tissue': tissue,
            },
            output_path=stats_txt,
        )
        
        # 10. 保存配置信息到 adata.uns
        adata.uns['scsa_annotation'] = {
            'job_id': job_id,
            'cluster_key': actual_cluster_key,
            'foldchange': foldchange,
            'pvalue': pvalue,
            'celltype': celltype,
            'target': target,
            'tissue': tissue,
            'rank_rep': rank_rep,
        }
        adata.write(output_h5ad)  # 重新保存以包含配置信息

        # 11. 构造基于 id 的返回结果，形式参考 spatial-tf-activity-service
        # 这里的 id 即为相对 OUTPUT_DIR 的路径，可直接用于 /api/download/{file_id}
        outputs = {
            "annotated_data.h5ad": f"{job_id}/annotated_data.h5ad",
            "scsa_annotation_statistics.csv": f"{job_id}/scsa_annotation_statistics.csv",
            "statistics.txt": f"{job_id}/statistics.txt",
        }
        for k, v in viz_files.items():
            filename = os.path.basename(v)
            outputs[filename] = f"{job_id}/{filename}"
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "job_id": job_id,
                "message": "SCSA 标注完成",
                "data": outputs,
            },
        )
        
    except Exception as e:
        logger.error(f"处理失败: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "job_id": job_id,
                "message": f"处理失败: {str(e)}",
                "error": _handle_error("annotation", e),
            },
        )


@app.get("/api/download/{file_id:path}")
async def download(file_id: str):
    """
    下载结果文件
    
    与 spatial-tf-activity-service 一致，使用单一 file_id（相对 OUTPUT_DIR 的路径），
    例如: {job_id}/annotated_data.h5ad
    """
    file_path = os.path.join(OUTPUT_DIR, file_id)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"文件不存在: {file_id}")
    filename = os.path.basename(file_path)
    return FileResponse(
        file_path,
        media_type="application/octet-stream",
        filename=filename,
    )


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "50008"))
    uvicorn.run(app, host="0.0.0.0", port=port)



