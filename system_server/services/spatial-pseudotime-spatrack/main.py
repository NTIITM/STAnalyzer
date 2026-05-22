#!/usr/bin/env python3
"""
Spatial pseudotime (SpaTrack) service

设计目标：
- 输入：与 GraphST 空间聚类服务类似的 AnnData（通常为 GraphST 输出的 h5ad），含表达矩阵和空间坐标；
- 使用 SpaTrack 包，基于最优传输理论推断空间转录组数据中的细胞轨迹；
- 输出：带有伪时序信息的 h5ad、空间伪时序图、流线图、伪时序密度图以及文本报告；
- 错误返回：参考其他空间服务，返回带诊断信息的 JSON（success=False, message, error 字段）。
"""
import os
import logging
import logging.handlers
import traceback
import tempfile
import uuid
from typing import Dict, Any, Optional, Literal

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse

import anndata as ad
import scanpy as sc
import pandas as pd
import numpy as np
from scipy.stats import entropy
from scipy.sparse.csgraph import dijkstra
from scipy.sparse import csr_matrix
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as ticker  # noqa: E402
import seaborn as sns  # noqa: E402

plt.rcParams["font.sans-serif"] = ["Arial", "DejaVu Sans", "Liberation Sans"]
plt.rcParams["axes.unicode_minus"] = False

# 尝试导入 spaTrack
try:
    import spaTrack as spt
    SPATRACK_AVAILABLE = True
except ImportError:
    SPATRACK_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("spaTrack package not available. Please install it: pip install spaTrack")


def _setup_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    default_dir = os.path.dirname(os.path.abspath(__file__))
    log_dir = os.getenv("LOG_DIR", default_dir)
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "service.log")
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = []
    fmt = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    sh.setLevel(level)
    fh = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=3
    )
    fh.setFormatter(fmt)
    fh.setLevel(level)
    root.addHandler(sh)
    root.addHandler(fh)


_setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Spatial Pseudotime (SpaTrack) Service",
    description="Use SpaTrack (Optimal Transport) to infer pseudotime trajectories on spatial transcriptomics data (AnnData input).",
    version="1.0.0",
)

OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

sc.settings.verbosity = 0
plt.rcParams["figure.dpi"] = 200  # 分辨率


def _read_adata(
    file_path: str,
    file_type: Literal["auto", "h5ad", "10x_h5", "csv", "tsv"] = "auto",
) -> "ad.AnnData":
    """统一读取 AnnData（与其他空间服务风格保持一致）"""
    def _read_h5ad_with_fallback(file_path: str) -> "ad.AnnData":
        """尝试读取h5ad文件，如果遇到兼容性问题，尝试使用h5py修复"""
        try:
            return sc.read(file_path)
        except Exception as e:
            error_msg = str(e)
            # 如果遇到IOSpec编码问题，尝试修复文件
            if "IOSpec" in error_msg or "encoding_type" in error_msg or "log1p" in error_msg:
                try:
                    import h5py
                    # 使用h5py打开文件，删除有问题的字段
                    with h5py.File(file_path, "r+") as f:
                        if "uns" in f and "log1p" in f["uns"]:
                            if "base" in f["uns/log1p"]:
                                del f["uns/log1p"]
                    logger.info("Fixed h5ad file, retrying read...")
                    return sc.read(file_path)
                except Exception as e2:
                    logger.error("Failed to fix h5ad file: %s", e2)
                    raise
            raise

    if file_type == "auto":
        if file_path.endswith(".h5ad"):
            file_type = "h5ad"
        elif file_path.endswith(".h5") or file_path.endswith(".hdf5"):
            file_type = "10x_h5"
        elif file_path.endswith(".csv"):
            file_type = "csv"
        elif file_path.endswith(".tsv"):
            file_type = "tsv"

    try:
        if file_type == "h5ad":
            return _read_h5ad_with_fallback(file_path)
        elif file_type == "10x_h5":
            return sc.read_10x_h5(file_path)
        elif file_type == "csv":
            return sc.read_csv(file_path).T
        elif file_type == "tsv":
            return sc.read_text(file_path, delimiter="\t").T
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
    except Exception as e:
        logger.error("Failed to read file %s: %s", file_path, e, exc_info=True)
        raise HTTPException(
            status_code=400,
            detail=f"Failed to read input file: {str(e)}. Please check file format and content.",
        )


def _format_error_response(
    error: Exception, step: str = "unknown", include_traceback: bool = True
) -> Dict[str, Any]:
    """格式化错误响应，参考其他服务的错误处理风格"""
    error_info = {
        "success": False,
        "message": f"Error in {step}: {str(error)}",
        "error": str(error),
        "step": step,
        "diagnosis": "",
        "suggestions": [],
    }

    lower_msg = str(error).lower()
    if "spatrack" in lower_msg or "spaTrack" in lower_msg or "import" in lower_msg:
        error_info["diagnosis"] = "SpaTrack 包未安装或导入失败"
        error_info["suggestions"].append(
            {
                "issue": "spaTrack 包可能未正确安装",
                "recommendations": [
                    "确认镜像中成功安装了 spaTrack 包（参见 Dockerfile）。",
                    "尝试手动安装: pip install spaTrack 或从 GitHub 安装。",
                ],
            }
        )
    elif "spatial" in lower_msg and ("coordinate" in lower_msg or "missing" in lower_msg):
        error_info["diagnosis"] = "缺少空间坐标信息"
        error_info["suggestions"].append(
            {
                "issue": "输入数据缺少空间坐标（spatial 或 X_spatial）。",
                "recommendations": [
                    "确认输入数据包含空间坐标信息（adata.obsm['spatial'] 或 adata.obsm['X_spatial']）。",
                    "SpaTrack 需要空间坐标来推断轨迹。",
                ],
            }
        )
    elif "memory" in lower_msg or "out of memory" in lower_msg:
        error_info["diagnosis"] = "内存不足（数据量过大）"
        error_info["suggestions"].append(
            {
                "issue": "数据量较大导致内存不足。",
                "recommendations": [
                    "减少基因数量（例如先在 Python 端筛选高变基因）。",
                    "考虑对数据进行预处理，减少细胞或基因数量。",
                ],
            }
        )
    if not error_info["suggestions"]:
        error_info["suggestions"].append(
            {
                "issue": "Unknown error",
                "recommendations": [
                    "检查输入数据格式和内容。",
                    "确认参数设置是否合理。",
                    "查看 traceback 以获取更多细节。",
                ],
            }
        )

    logger.error("Step %s failed: %s", step, error)
    if include_traceback:
        logger.error(traceback.format_exc())
    return error_info


def preprocess_data(adata: ad.AnnData) -> ad.AnnData:
    """
    数据预处理：基因过滤、归一化、对数转换
    参考教程中的预处理步骤
    """
    logger.info("Preprocessing data: %d cells, %d genes", adata.n_obs, adata.n_vars)
    
    # 保存原始计数
    if "counts" not in adata.layers:
        adata.layers["counts"] = adata.X.copy()
    
    # 基因过滤
    sc.pp.filter_genes(adata, min_cells=10)
    logger.info("After gene filtering: %d genes", adata.n_vars)
    
    # 归一化
    sc.pp.normalize_total(adata, target_sum=1e4)
    
    # 对数转换
    sc.pp.log1p(adata)
    
    # 计算质量控制指标
    sc.pp.calculate_qc_metrics(adata, percent_top=None, log1p=False, inplace=True)
    
    return adata


def check_spatial_coordinates(adata: ad.AnnData) -> np.ndarray:
    """检查并获取空间坐标"""
    if "spatial" in adata.obsm_keys():
        coords = adata.obsm["spatial"]
    elif "X_spatial" in adata.obsm_keys():
        coords = adata.obsm["X_spatial"]
    else:
        raise ValueError(
            "Spatial coordinates not found. Please provide spatial coordinates in "
            "adata.obsm['spatial'] or adata.obsm['X_spatial']"
        )
    
    if coords.shape[1] < 2:
        raise ValueError("Spatial coordinates must have at least 2 dimensions (x, y)")
    
    # 确保坐标是2D的
    if coords.shape[1] > 2:
        logger.warning("Spatial coordinates have %d dimensions, using first 2", coords.shape[1])
        coords = coords[:, :2]
    
    return coords


def run_spatrack_pseudotime(
    adata: ad.AnnData,
    cluster_key: Optional[str] = None,
    n_neigh_pos: int = 50,
    entropy_method: str = "auto",
    start_cluster: Optional[str] = None,
) -> Dict[str, Any]:
    """
    运行 SpaTrack 伪时序分析
    
    步骤：
    1. 数据预处理
    2. 识别轨迹起点（基于信息熵）
    3. 计算细胞转移概率（最优传输）
    4. 推断伪时间
    5. 计算速度矢量场
    """
    if not SPATRACK_AVAILABLE:
        raise ImportError(
            "spaTrack package is not available. Please install it: pip install spaTrack"
        )
    
    logger.info("Starting SpaTrack pseudotime analysis")
    
    # 1. 数据预处理
    adata = preprocess_data(adata.copy())
    
    # 2. 检查并设置空间坐标
    coords = check_spatial_coordinates(adata)
    adata.obsm["X_spatial"] = coords
    
    # 3. 识别轨迹起点
    if cluster_key and cluster_key in adata.obs.columns:
        logger.info("Identifying trajectory start using entropy method")
        try:
            # 使用 assess_start_cluster 识别起始集群
            if hasattr(spt, 'assess_start_cluster'):
                entropy_result = spt.assess_start_cluster(
                    adata, 
                    cluster_key=cluster_key,
                    method=entropy_method if entropy_method != "auto" else None
                )
                
                # 获取熵值最高的集群作为起始点
                if start_cluster is None:
                    if hasattr(entropy_result, 'idxmax'):
                        start_cluster = entropy_result.idxmax()
                    elif isinstance(entropy_result, dict):
                        start_cluster = max(entropy_result.items(), key=lambda x: x[1])[0]
                    elif isinstance(entropy_result, pd.Series):
                        start_cluster = entropy_result.idxmax()
                    else:
                        # 如果无法自动识别，使用第一个集群
                        start_cluster = adata.obs[cluster_key].cat.categories[0] if hasattr(adata.obs[cluster_key], 'cat') else adata.obs[cluster_key].unique()[0]
                        logger.warning("Could not automatically identify start cluster, using: %s", start_cluster)
            else:
                # 如果没有assess_start_cluster函数，手动计算熵
                logger.info("assess_start_cluster not found, computing entropy manually")
                
                cluster_entropies = {}
                for cluster in adata.obs[cluster_key].unique():
                    # 处理 NaN 值
                    if pd.isna(cluster):
                        cluster_mask = adata.obs[cluster_key].isna()
                    else:
                        cluster_mask = adata.obs[cluster_key] == cluster
                    
                    if cluster_mask.sum() == 0:
                        continue  # 跳过没有细胞的集群
                    
                    cluster_expr = adata.X[cluster_mask]
                    # 计算每个基因的表达分布熵
                    if hasattr(cluster_expr, 'toarray'):
                        cluster_expr = cluster_expr.toarray()
                    # 对每个基因计算熵
                    gene_entropies = [entropy(cluster_expr[:, i] + 1e-10) for i in range(cluster_expr.shape[1])]
                    cluster_entropies[cluster] = np.mean(gene_entropies)
                
                if start_cluster is None:
                    start_cluster = max(cluster_entropies.items(), key=lambda x: x[1])[0]
            
            logger.info("Selected start cluster: %s", start_cluster)
            
            # 选择起始细胞（该集群中空间位置最边缘的细胞）
            if pd.isna(start_cluster):
                start_mask = adata.obs[cluster_key].isna()
            else:
                start_mask = adata.obs[cluster_key] == start_cluster
            start_coords = coords[start_mask]
            if len(start_coords) > 0:
                # 选择距离中心最远的细胞作为起始点
                center = start_coords.mean(axis=0)
                distances = np.linalg.norm(start_coords - center, axis=1)
                start_idx = np.where(start_mask)[0][distances.argmax()]
            else:
                start_idx = 0
                logger.warning("Start cluster has no cells, using first cell as start")
        except Exception as e:
            logger.warning("Failed to use entropy method for start identification: %s. Using first cell.", e, exc_info=True)
            start_idx = 0
            start_cluster = None
    else:
        logger.info("No cluster key provided, using first cell as trajectory start")
        start_idx = 0
        start_cluster = None
    
    # 4. 计算细胞转移概率（最优传输矩阵）
    logger.info("Computing optimal transport matrix")
    try:
        ot_matrix = spt.get_ot_matrix(adata, data_type="spatial")
        # 将OT矩阵存储到adata.obsp["trans"]，供get_ptime使用
        adata.obsp["trans"] = ot_matrix
        logger.info("Optimal transport matrix computed: shape %s", ot_matrix.shape)
    except Exception as e:
        logger.error("Failed to compute OT matrix: %s", e)
        raise
    
    # 5. 推断伪时间
    logger.info("Inferring pseudotime")
    try:
        # 根据实际API，get_ptime需要start_cells参数（列表）
        if hasattr(spt, 'get_ptime'):
            ptime = spt.get_ptime(adata, start_cells=[start_idx])
        elif hasattr(spt, 'get_pseudotime'):
            ptime = spt.get_pseudotime(adata, start_cells=[start_idx])
        else:
            # 如果函数不存在，手动计算伪时间
            logger.warning("get_ptime/get_pseudotime not found, attempting manual calculation")
            # 基于OT矩阵和起始点计算伪时间（最短路径）
            
            # 将OT矩阵转换为距离矩阵（取负对数或使用1-概率）
            dist_matrix = -np.log(ot_matrix + 1e-10)
            # 使用Dijkstra算法计算从起始点到所有点的最短距离
            dist_matrix_sparse = csr_matrix(dist_matrix)
            distances = dijkstra(dist_matrix_sparse, indices=start_idx, directed=False)
            # 归一化到[0, 1]
            finite_dist = distances[np.isfinite(distances)]
            if len(finite_dist) > 0 and finite_dist.max() > finite_dist.min():
                ptime = (distances - finite_dist.min()) / (finite_dist.max() - finite_dist.min())
            else:
                ptime = np.zeros(len(adata))
                logger.warning("Could not compute meaningful pseudotime, using zeros")
        
        # 确保ptime是numpy数组
        if isinstance(ptime, (list, pd.Series)):
            ptime = np.array(ptime)
        
        # 存储伪时间（使用两个名称以兼容不同的API）
        adata.obs["spatrack_pseudotime"] = ptime
        adata.obs["ptime"] = ptime  # get_velocity 可能需要 'ptime' 列
        logger.info("Pseudotime computed: range [%.4f, %.4f], mean=%.4f", 
                   ptime.min(), ptime.max(), ptime.mean())
    except Exception as e:
        logger.error("Failed to compute pseudotime: %s", e)
        raise
    
    # 6. 计算速度矢量场
    logger.info("Computing velocity vector field")
    E_grid = None
    V_grid = None
    try:
        # 尝试不同的参数组合，因为 get_velocity 的 API 可能不同
        try:
            E_grid, V_grid = spt.get_velocity(
                adata, 
                basis="spatial", 
                n_neigh_pos=n_neigh_pos
            )
            adata.uns["E_grid"] = E_grid
            adata.uns["V_grid"] = V_grid
            logger.info("Velocity vector field computed successfully")
        except (KeyError, AttributeError, TypeError) as e1:
            # 如果失败，尝试传递 ptime 参数
            logger.debug("First get_velocity attempt failed: %s, trying with ptime parameter", e1)
            try:
                E_grid, V_grid = spt.get_velocity(
                    adata, 
                    basis="spatial", 
                    n_neigh_pos=n_neigh_pos,
                    ptime_key="ptime"
                )
                adata.uns["E_grid"] = E_grid
                adata.uns["V_grid"] = V_grid
                logger.info("Velocity vector field computed successfully (with ptime_key)")
            except (TypeError, AttributeError, KeyError) as e2:
                # 如果还是失败，尝试其他可能的参数名
                logger.debug("Second get_velocity attempt failed: %s, trying alternative", e2)
                try:
                    E_grid, V_grid = spt.get_velocity(
                        adata, 
                        basis="spatial", 
                        n_neigh_pos=n_neigh_pos,
                        pseudotime_key="ptime"
                    )
                    adata.uns["E_grid"] = E_grid
                    adata.uns["V_grid"] = V_grid
                    logger.info("Velocity vector field computed successfully (with pseudotime_key)")
                except Exception as e3:
                    # 所有尝试都失败
                    logger.warning("All get_velocity attempts failed. Last error: %s", e3)
                    raise e3
    except Exception as e:
        logger.warning("Failed to compute velocity field: %s. Continuing without velocity.", e)
        E_grid = None
        V_grid = None
    
    return {
        "adata": adata,
        "ot_matrix": ot_matrix,
        "start_idx": start_idx,
        "start_cluster": start_cluster if cluster_key else None,
        "E_grid": E_grid,
        "V_grid": V_grid,
    }


def generate_spatrack_plots(
    adata: ad.AnnData,
    output_dir: str,
    cluster_key: Optional[str] = None,
) -> Dict[str, str]:
    """生成 SpaTrack 可视化图（优化版）"""
    os.makedirs(output_dir, exist_ok=True)
    file_ids = {}
    
    try:
        # 1. 空间伪时间图（优化版）
        logger.info("Generating spatial pseudotime plot")
        fig, ax = plt.subplots(figsize=(10, 8))
        
        # 使用更好的颜色映射（viridis或plasma，更适合科学可视化）
        # 但保留Reds作为备选，因为用户可能习惯红色表示高值
        ptime = adata.obs["spatrack_pseudotime"].values
        
        # 使用hexbin进行更平滑的可视化
        coords = adata.obsm.get("spatial", adata.obsm.get("X_spatial", None))
        if coords is not None and len(coords) > 0:
            try:
                # 使用hexbin创建更平滑的伪时间分布
                hb = ax.hexbin(
                    coords[:, 0],
                    coords[:, 1],
                    C=ptime,
                    gridsize=50,
                    cmap="plasma",  # 使用plasma颜色映射，从深紫到亮黄，更适合表示时间进程
                    mincnt=1,
                    linewidths=0.1,
                )
                # 添加颜色条
                cbar = plt.colorbar(hb, ax=ax, label="Pseudotime", shrink=0.8)
                cbar.ax.tick_params(labelsize=10)
            except Exception as e:
                logger.warning("Hexbin failed, using scatter instead: %s", e)
                # 如果hexbin失败，回退到scatter
                scatter = ax.scatter(
                    coords[:, 0],
                    coords[:, 1],
                    c=ptime,
                    cmap="plasma",
                    s=50,
                    alpha=0.7,
                    edgecolors="none",
                )
                cbar = plt.colorbar(scatter, ax=ax, label="Pseudotime", shrink=0.8)
                cbar.ax.tick_params(labelsize=10)
        else:
            # 如果没有坐标，使用简单的散点图
            logger.warning("No spatial coordinates found, using fallback visualization")
            scatter = ax.scatter(
                range(len(adata)),
                ptime,
                c=ptime,
                cmap="plasma",
                s=50,
                alpha=0.7,
                edgecolors="none",
            )
            ax.set_xlabel("Cell/Spot Index", fontsize=12, fontweight="bold")
            ax.set_ylabel("Pseudotime", fontsize=12, fontweight="bold")
            cbar = plt.colorbar(scatter, ax=ax, label="Pseudotime", shrink=0.8)
            cbar.ax.tick_params(labelsize=10)
        
        # 改进标签和标题
        ax.set_xlabel("Spatial Coordinate 1", fontsize=12, fontweight="bold")
        ax.set_ylabel("Spatial Coordinate 2", fontsize=12, fontweight="bold")
        ax.set_title("SpaTrack Pseudotime Spatial Distribution", fontsize=14, fontweight="bold", pad=15)
        
        # 改进坐标轴刻度
        ax.xaxis.set_major_locator(ticker.MultipleLocator(1000))
        ax.yaxis.set_major_locator(ticker.MultipleLocator(1000))
        ax.tick_params(labelsize=10)
        ax.grid(True, alpha=0.2, linestyle="--")
        
        # 添加统计信息文本（包含更多统计量）
        stats_text = (
            f"Range: [{ptime.min():.3f}, {ptime.max():.3f}]\n"
            f"Mean: {ptime.mean():.3f} | Median: {np.median(ptime):.3f}\n"
            f"Std: {ptime.std():.3f} | CV: {ptime.std()/(ptime.mean()+1e-10):.3f}"
        )
        ax.text(0.02, 0.98, stats_text, transform=ax.transAxes,
                fontsize=9, verticalalignment="top",
                bbox=dict(boxstyle="round", facecolor="white", alpha=0.8))
        
        plot_id = f"{uuid.uuid4()}.png"
        plot_path = os.path.join(output_dir, plot_id)
        plt.savefig(plot_path, dpi=300, bbox_inches="tight", facecolor="white")
        plt.close()
        file_ids["spatial_pseudotime"] = plot_id
        logger.info("Spatial pseudotime plot saved: %s", plot_path)
    except Exception as e:
        logger.warning("Failed to generate spatial pseudotime plot: %s", e, exc_info=True)
        # 如果hexbin失败，回退到原始方法
        try:
            fig, ax = plt.subplots(figsize=(10, 8))
            sc.pl.embedding(
                adata,
                basis="spatial",
                color="spatrack_pseudotime",
                show=False,
                ax=ax,
                color_map="plasma",  # 改用plasma
                title="SpaTrack Pseudotime",
                size=100,
            )
            ax.set_xlabel("Spatial Coordinate 1", fontsize=12, fontweight="bold")
            ax.set_ylabel("Spatial Coordinate 2", fontsize=12, fontweight="bold")
            ax.xaxis.set_major_locator(ticker.MultipleLocator(1000))
            ax.yaxis.set_major_locator(ticker.MultipleLocator(1000))
            
            # 在 fallback 方法中也添加统计信息
            ptime = adata.obs["spatrack_pseudotime"].values
            stats_text = (
                f"Range: [{ptime.min():.3f}, {ptime.max():.3f}]\n"
                f"Mean: {ptime.mean():.3f} | Median: {np.median(ptime):.3f}\n"
                f"Std: {ptime.std():.3f} | CV: {ptime.std()/(ptime.mean()+1e-10):.3f}"
            )
            ax.text(0.02, 0.98, stats_text, transform=ax.transAxes,
                    fontsize=9, verticalalignment="top",
                    bbox=dict(boxstyle="round", facecolor="white", alpha=0.8))
            
            plot_id = f"{uuid.uuid4()}.png"
            plot_path = os.path.join(output_dir, plot_id)
            plt.savefig(plot_path, dpi=300, bbox_inches="tight", facecolor="white")
            plt.close()
            file_ids["spatial_pseudotime"] = plot_id
        except Exception as e2:
            logger.error("Fallback visualization also failed: %s", e2, exc_info=True)
    
    try:
        # 2. 流线图（如果速度场可用）
        if "E_grid" in adata.uns and "V_grid" in adata.uns:
            logger.info("Generating streamplot")
            fig, ax = plt.subplots(figsize=(6, 6))
            
            # 绘制细胞类型或聚类
            color_key = cluster_key if cluster_key and cluster_key in adata.obs.columns else None
            if color_key:
                sc.pl.embedding(
                    adata,
                    basis="spatial",
                    show=False,
                    title=" ",
                    color=color_key,
                    ax=ax,
                    frameon=False,
                    palette="tab20b",
                    legend_fontweight="normal",
                    alpha=0.8,
                    size=150,
                )
            else:
                sc.pl.embedding(
                    adata,
                    basis="spatial",
                    show=False,
                    title=" ",
                    ax=ax,
                    frameon=False,
                    alpha=0.8,
                    size=150,
                )
            
            # 叠加流线图
            E_grid = adata.uns["E_grid"]
            V_grid = adata.uns["V_grid"]
            ax.streamplot(
                E_grid[0],
                E_grid[1],
                V_grid[0],
                V_grid[1],
                density=1.8,
                color="black",
                linewidth=2.5,
                arrowsize=1.5,
            )
            
            plot_id = f"{uuid.uuid4()}.png"
            plot_path = os.path.join(output_dir, plot_id)
            plt.savefig(plot_path, dpi=300, bbox_inches="tight")
            plt.close()
            file_ids["streamplot"] = plot_id
            logger.info("Streamplot saved: %s", plot_path)
        else:
            logger.info("Velocity field not available, skipping streamplot")
    except Exception as e:
        logger.warning("Failed to generate streamplot: %s", e, exc_info=True)
    
    try:
        # 3. 伪时间分布图（优化版）
        logger.info("Generating pseudotime distribution plot")
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))
        
        ptime = adata.obs["spatrack_pseudotime"].values
        
        # 改进的直方图
        n, bins, patches = axes[0].hist(
            ptime, 
            bins=50, 
            edgecolor="white", 
            alpha=0.75,
            color="steelblue",
            linewidth=1.2
        )
        # 根据值着色（从蓝到红）
        cm = plt.cm.get_cmap("plasma")
        bin_centers = 0.5 * (bins[:-1] + bins[1:])
        col = bin_centers - bin_centers.min()
        col /= col.max()
        for c, p in zip(col, patches):
            plt.setp(p, "facecolor", cm(c))
        
        # 添加统计线
        mean_pt = ptime.mean()
        median_pt = np.median(ptime)
        axes[0].axvline(mean_pt, color="red", linestyle="--", linewidth=2, label=f"Mean: {mean_pt:.3f}")
        axes[0].axvline(median_pt, color="green", linestyle="--", linewidth=2, label=f"Median: {median_pt:.3f}")
        
        axes[0].set_xlabel("Pseudotime", fontsize=11, fontweight="bold")
        axes[0].set_ylabel("Number of cells/spots", fontsize=11, fontweight="bold")
        axes[0].set_title("Pseudotime Distribution", fontsize=12, fontweight="bold")
        axes[0].grid(True, alpha=0.3, linestyle="--")
        axes[0].legend(fontsize=9, framealpha=0.9)
        axes[0].tick_params(labelsize=9)
        
        # 改进的按聚类/细胞类型分组的箱线图
        if cluster_key and cluster_key in adata.obs.columns:
            df_plot = pd.DataFrame({
                "pseudotime": ptime,
                "cluster": adata.obs[cluster_key].astype(str).values
            })
            
            # 按伪时间中位数排序聚类
            cluster_medians = df_plot.groupby("cluster")["pseudotime"].median().sort_values()
            df_plot["cluster"] = pd.Categorical(df_plot["cluster"], categories=cluster_medians.index)
            
            # 使用violin plot + boxplot组合，提供更多信息
            parts = axes[1].violinplot(
                [df_plot[df_plot["cluster"] == c]["pseudotime"].values 
                 for c in cluster_medians.index],
                positions=range(len(cluster_medians)),
                showmeans=True,
                showmedians=True,
                widths=0.7
            )
            
            # 设置颜色
            colors = plt.cm.tab20(np.linspace(0, 1, len(cluster_medians)))
            for pc, color in zip(parts["bodies"], colors):
                pc.set_facecolor(color)
                pc.set_alpha(0.7)
            
            axes[1].set_xticks(range(len(cluster_medians)))
            axes[1].set_xticklabels(cluster_medians.index, rotation=45, ha="right", fontsize=9)
            axes[1].set_ylabel("Pseudotime", fontsize=11, fontweight="bold")
            axes[1].set_title("Pseudotime Distribution by Cluster", fontsize=12, fontweight="bold")
            axes[1].grid(True, alpha=0.3, linestyle="--", axis="y")
            axes[1].tick_params(labelsize=9)
        else:
            axes[1].text(0.5, 0.5, "No cluster information available", 
                        ha="center", va="center", transform=axes[1].transAxes,
                        fontsize=11, style="italic")
            axes[1].set_title("Pseudotime by Cluster (N/A)", fontsize=12, fontweight="bold")
            axes[1].axis("off")
        
        plt.tight_layout()
        plot_id = f"{uuid.uuid4()}.png"
        plot_path = os.path.join(output_dir, plot_id)
        plt.savefig(plot_path, dpi=300, bbox_inches="tight", facecolor="white")
        plt.close()
        file_ids["pseudotime_distribution"] = plot_id
        logger.info("Pseudotime distribution plot saved: %s", plot_path)
    except Exception as e:
        logger.warning("Failed to generate pseudotime distribution plot: %s", e, exc_info=True)
    
    # 只返回实际生成的文件ID
    result_file_ids = {}
    for key, file_id in file_ids.items():
        file_path = os.path.join(output_dir, file_id)
        if os.path.exists(file_path):
            result_file_ids[key] = file_id
            logger.debug("Plot file generated: %s -> %s", key, file_id)
        else:
            logger.warning("Plot file %s (%s) was not generated, removing from results", key, file_id)
    
    logger.info("Generated %d/%d plot files: %s", len(result_file_ids), len(file_ids), list(result_file_ids.keys()))
    return result_file_ids


def evaluate_biological_logic(
    adata: ad.AnnData,
    cluster_key: Optional[str] = None,
    start_cluster: Optional[str] = None,
) -> Dict[str, Any]:
    """
    从生物学专家角度评估伪时间结果是否符合生物学逻辑
    
    评估标准：
    1. 伪时间分布的合理性（不应过于集中或分散）
    2. 空间连续性（相邻细胞应有相似的伪时间值）
    3. 聚类一致性（同一聚类内的伪时间应相对一致）
    4. 轨迹方向性（应有明确的起始和终点区域）
    """
    evaluation = {
        "overall_quality": "good",
        "issues": [],
        "warnings": [],
        "strengths": [],
        "recommendations": [],
        "metrics": {}
    }
    
    if "spatrack_pseudotime" not in adata.obs.columns:
        evaluation["overall_quality"] = "poor"
        evaluation["issues"].append("Pseudotime values not found in data")
        return evaluation
    
    ptime = adata.obs["spatrack_pseudotime"].values
    
    # 1. 评估伪时间分布
    ptime_range = ptime.max() - ptime.min()
    ptime_std = ptime.std()
    ptime_cv = ptime_std / (ptime.mean() + 1e-10)  # 变异系数
    
    evaluation["metrics"]["pseudotime_range"] = float(ptime_range)
    evaluation["metrics"]["pseudotime_std"] = float(ptime_std)
    evaluation["metrics"]["pseudotime_cv"] = float(ptime_cv)
    
    if ptime_range < 0.1:
        evaluation["overall_quality"] = "poor"
        evaluation["issues"].append(
            f"Pseudotime range is too small ({ptime_range:.4f}), suggesting limited trajectory variation. "
            "This may indicate: (1) insufficient data variation, (2) incorrect start point selection, "
            "or (3) parameter tuning needed."
        )
    elif ptime_range < 0.3:
        evaluation["warnings"].append(
            f"Pseudotime range is relatively small ({ptime_range:.4f}), "
            "which may limit the ability to distinguish different trajectory stages."
        )
    else:
        evaluation["strengths"].append(
            f"Good pseudotime range ({ptime_range:.4f}), indicating clear trajectory progression."
        )
    
    # 2. 评估空间连续性
    coords = adata.obsm.get("spatial", adata.obsm.get("X_spatial", None))
    if coords is not None and len(coords) > 10:
        from scipy.spatial.distance import pdist, squareform
        from scipy.stats import pearsonr
        
        # 计算空间距离和伪时间差异的相关性
        spatial_dist = squareform(pdist(coords))
        ptime_diff = squareform(pdist(ptime.reshape(-1, 1)))
        
        # 只考虑最近的邻居（避免远距离噪声）
        k_nearest = min(10, len(adata) // 10)
        spatial_continuity_scores = []
        
        for i in range(min(100, len(adata))):  # 采样评估
            nearest_indices = np.argsort(spatial_dist[i])[1:k_nearest+1]
            if len(nearest_indices) > 2:
                spatial_dists = spatial_dist[i, nearest_indices]
                ptime_diffs = np.abs(ptime[i] - ptime[nearest_indices])
                if np.std(spatial_dists) > 0 and np.std(ptime_diffs) > 0:
                    corr, _ = pearsonr(spatial_dists, ptime_diffs)
                    if not np.isnan(corr):
                        spatial_continuity_scores.append(corr)
        
        if spatial_continuity_scores:
            mean_continuity = np.mean(spatial_continuity_scores)
            evaluation["metrics"]["spatial_continuity"] = float(mean_continuity)
            
            if mean_continuity < 0.1:
                evaluation["strengths"].append(
                    f"Good spatial continuity (correlation: {mean_continuity:.3f}). "
                    "Adjacent cells have similar pseudotime values, which is biologically expected."
                )
            elif mean_continuity > 0.5:
                evaluation["warnings"].append(
                    f"Spatial continuity is low (correlation: {mean_continuity:.3f}). "
                    "Adjacent cells have very different pseudotime values, which may indicate: "
                    "(1) noisy data, (2) incorrect trajectory inference, or (3) complex spatial patterns."
                )
    
    # 3. 评估聚类一致性（如果提供了聚类信息）
    if cluster_key and cluster_key in adata.obs.columns:
        cluster_consistency = {}
        for cluster in adata.obs[cluster_key].unique():
            if pd.isna(cluster):
                cluster_mask = adata.obs[cluster_key].isna()
            else:
                cluster_mask = adata.obs[cluster_key] == cluster
            
            cluster_ptime = ptime[cluster_mask]
            if len(cluster_ptime) > 1:
                cluster_std = cluster_ptime.std()
                cluster_range = cluster_ptime.max() - cluster_ptime.min()
                cluster_consistency[str(cluster)] = {
                    "std": float(cluster_std),
                    "range": float(cluster_range),
                    "mean": float(cluster_ptime.mean()),
                    "n_cells": int(len(cluster_ptime))
                }
        
        evaluation["metrics"]["cluster_consistency"] = cluster_consistency
        
        # 检查是否有聚类内伪时间差异过大
        high_variance_clusters = []
        for cluster, stats in cluster_consistency.items():
            if stats["std"] > 0.3:  # 阈值可调整
                high_variance_clusters.append(f"{cluster} (std={stats['std']:.3f})")
        
        if high_variance_clusters:
            evaluation["warnings"].append(
                f"Some clusters show high pseudotime variance: {', '.join(high_variance_clusters)}. "
                "This may indicate: (1) clusters contain multiple trajectory stages, "
                "(2) clustering resolution too low, or (3) trajectory inference needs refinement."
            )
        else:
            evaluation["strengths"].append(
                "Clusters show consistent pseudotime values, suggesting good alignment "
                "between clustering and trajectory inference."
            )
    
    # 4. 评估轨迹方向性
    if coords is not None:
        # 检查是否有明确的起始和终点区域
        low_ptime_cells = ptime < np.percentile(ptime, 10)
        high_ptime_cells = ptime > np.percentile(ptime, 90)
        
        if np.sum(low_ptime_cells) > 0 and np.sum(high_ptime_cells) > 0:
            low_ptime_coords = coords[low_ptime_cells]
            high_ptime_coords = coords[high_ptime_cells]
            
            low_center = low_ptime_coords.mean(axis=0)
            high_center = high_ptime_coords.mean(axis=0)
            
            trajectory_distance = np.linalg.norm(high_center - low_center)
            spatial_span = np.max(coords, axis=0) - np.min(coords, axis=0)
            max_span = np.max(spatial_span)
            
            relative_distance = trajectory_distance / (max_span + 1e-10)
            evaluation["metrics"]["trajectory_directionality"] = float(relative_distance)
            
            if relative_distance > 0.3:
                evaluation["strengths"].append(
                    f"Clear trajectory directionality detected (relative distance: {relative_distance:.3f}). "
                    "Start and end regions are spatially separated, which is biologically meaningful."
                )
            elif relative_distance < 0.1:
                evaluation["warnings"].append(
                    f"Trajectory directionality is weak (relative distance: {relative_distance:.3f}). "
                    "Start and end regions are spatially overlapping, which may indicate: "
                    "(1) incorrect start point selection, (2) circular trajectory, or (3) complex spatial patterns."
                )
    
    # 5. 综合评估和建议
    if len(evaluation["issues"]) > 0:
        evaluation["overall_quality"] = "poor"
    elif len(evaluation["warnings"]) >= 3:
        evaluation["overall_quality"] = "fair"
    elif len(evaluation["warnings"]) > 0:
        evaluation["overall_quality"] = "good"
    else:
        evaluation["overall_quality"] = "excellent"
    
    # 生成建议
    if evaluation["overall_quality"] in ["poor", "fair"]:
        evaluation["recommendations"].extend([
            "Consider adjusting n_neigh_pos parameter to improve spatial smoothness",
            "Verify that the start cluster selection is biologically meaningful",
            "Check if input data quality is sufficient for trajectory inference",
            "Consider using different entropy methods or manually specifying start_cluster"
        ])
    
    if evaluation["metrics"].get("pseudotime_range", 1.0) < 0.3:
        evaluation["recommendations"].append(
            "Low pseudotime range detected. Consider: (1) checking data preprocessing, "
            "(2) verifying optimal transport matrix computation, (3) trying different parameters"
        )
    
    return evaluation


def generate_pseudotime_report(
    output_dir: str,
    adata: ad.AnnData,
    start_cluster: Optional[str],
    cluster_key: Optional[str],
    n_neigh_pos: int,
) -> str:
    """生成文本报告"""
    os.makedirs(output_dir, exist_ok=True)
    report_id = f"{uuid.uuid4()}.txt"
    report_path = os.path.join(output_dir, report_id)
    
    parts = []
    parts.append("=" * 70)
    parts.append("SpaTrack-based Spatial Pseudotime Analysis Report")
    parts.append("=" * 70)
    
    parts.append("\n[I. Input Data]")
    parts.append(f"  Cells/Spots: {adata.n_obs:,}")
    parts.append(f"  Genes: {adata.n_vars:,}")
    parts.append(f"  Has spatial coordinates: {('spatial' in adata.obsm_keys()) or ('X_spatial' in adata.obsm_keys())}")
    if cluster_key and cluster_key in adata.obs.columns:
        n_clusters = adata.obs[cluster_key].nunique()
        parts.append(f"  Cluster key: {cluster_key} (n={n_clusters} groups)")
    else:
        parts.append("  Cluster key: None or not found.")
    
    parts.append("\n[II. SpaTrack Parameters]")
    parts.append(f"  Start cluster identification: {'Entropy-based' if start_cluster else 'First cell'}")
    if start_cluster:
        parts.append(f"  Selected start cluster: {start_cluster}")
    parts.append(f"  Spatial neighbor count (n_neigh_pos): {n_neigh_pos}")
    
    parts.append("\n[III. Pseudotime Summary]")
    if "spatrack_pseudotime" in adata.obs.columns:
        pt = adata.obs["spatrack_pseudotime"].astype(float)
        parts.append(
            f"  Pseudotime range: [{pt.min():.4f}, {pt.max():.4f}], mean={pt.mean():.4f}, median={pt.median():.4f}"
        )
        parts.append(f"  Standard deviation: {pt.std():.4f}")
    else:
        parts.append("  Pseudotime column 'spatrack_pseudotime' not found in obs.")
    
    if cluster_key and cluster_key in adata.obs.columns and "spatrack_pseudotime" in adata.obs.columns:
        parts.append("\n  Pseudotime by cluster:")
        # 处理NaN值，只对非NaN的cluster进行排序
        unique_clusters = adata.obs[cluster_key].unique()
        # 过滤掉NaN值并转换为字符串以便排序
        clusters_to_sort = [c for c in unique_clusters if pd.notna(c)]
        clusters_to_sort = sorted(clusters_to_sort, key=lambda x: str(x))
        # 如果有NaN值，添加到末尾
        if any(pd.isna(c) for c in unique_clusters):
            clusters_to_sort.append(None)
        
        for cluster in clusters_to_sort:
            if pd.isna(cluster):
                cluster_mask = adata.obs[cluster_key].isna()
                cluster_name = "NaN"
            else:
                cluster_mask = adata.obs[cluster_key] == cluster
                cluster_name = str(cluster)
            cluster_pt = adata.obs[cluster_mask]["spatrack_pseudotime"]
            if len(cluster_pt) > 0:
                parts.append(f"    {cluster_name}: mean={cluster_pt.mean():.4f}, range=[{cluster_pt.min():.4f}, {cluster_pt.max():.4f}]")
    
    # 添加生物学逻辑评估
    parts.append("\n[IV. Biological Logic Evaluation]")
    evaluation = evaluate_biological_logic(adata, cluster_key, start_cluster)
    
    parts.append(f"  Overall Quality: {evaluation['overall_quality'].upper()}")
    
    if evaluation["strengths"]:
        parts.append("\n  Strengths:")
        for strength in evaluation["strengths"]:
            parts.append(f"    + {strength}")
    
    if evaluation["warnings"]:
        parts.append("\n  Warnings:")
        for warning in evaluation["warnings"]:
            parts.append(f"    ⚠ {warning}")
    
    if evaluation["issues"]:
        parts.append("\n  Issues:")
        for issue in evaluation["issues"]:
            parts.append(f"    ✗ {issue}")
    
    if evaluation["recommendations"]:
        parts.append("\n  Recommendations:")
        for rec in evaluation["recommendations"]:
            parts.append(f"    → {rec}")
    
    parts.append("\n[V. Notes]")
    parts.append(
        "  - SpaTrack uses Optimal Transport theory to infer trajectories by combining "
        "gene expression and spatial information."
    )
    parts.append(
        "  - The trajectory start is identified using entropy-based method (if cluster_key is provided), "
        "selecting the cluster with highest entropy as the starting point."
    )
    parts.append(
        "  - Pseudotime values represent the progression along the inferred trajectory, "
        "with higher values indicating later stages."
    )
    if "E_grid" in adata.uns and "V_grid" in adata.uns:
        parts.append("  - Velocity vector field was successfully computed and can be visualized in the streamplot.")
    else:
        parts.append("  - Velocity vector field was not computed or is unavailable.")
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))
    logger.info("SpaTrack pseudotime report generated: %s", report_path)
    return report_id


@app.get("/health")
async def health():
    """健康检查端点"""
    return {
        "status": "healthy",
        "spatrack_available": SPATRACK_AVAILABLE,
    }


@app.post("/api/spatrack-pseudotime")
async def spatrack_pseudotime(
    file: UploadFile = File(..., description="Spatial transcriptomics data with spatial coordinates (AnnData file)"),
    file_type: Literal["auto", "h5ad", "10x_h5", "csv", "tsv"] = Form("auto"),
    cluster_key: Optional[str] = Form("leiden"),
    n_neigh_pos: int = Form(50),
    entropy_method: str = Form("auto"),
    start_cluster: Optional[str] = Form(None),
) -> JSONResponse:
    """
    使用 SpaTrack（最优传输理论）对空间转录组数据进行伪时序分析。
    
    推荐输入：
    - GraphST 空间聚类服务的输出 h5ad（含空间坐标和聚类标签）；
    - 或其他包含空间坐标的 AnnData 对象。
    
    参数：
    - cluster_key: 用于识别轨迹起点的聚类列名（如 'leiden', 'louvain'）
    - n_neigh_pos: 计算速度场时的空间邻居数量
    - entropy_method: 熵计算方法（'auto', 'shannon', 'renyi'）
    - start_cluster: 手动指定起始集群（如果为None，则自动基于熵选择）
    """
    if not SPATRACK_AVAILABLE:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "SpaTrack pseudotime analysis failed: spaTrack package is not available"},
        )
    
    temp_input_path = None
    try:
        # 保存上传文件
        file_id = str(uuid.uuid4())
        temp_input_path = os.path.join(
            tempfile.gettempdir(), f"input_{file_id}_{file.filename}"
        )
        with open(temp_input_path, "wb") as f:
            content = await file.read()
            f.write(content)
        logger.info("Uploaded file saved: %s", temp_input_path)
        
        # 读取 AnnData
        adata = _read_adata(temp_input_path, file_type)
        
        # 运行 SpaTrack 伪时序
        result = run_spatrack_pseudotime(
            adata=adata,
            cluster_key=cluster_key,
            n_neigh_pos=n_neigh_pos,
            entropy_method=entropy_method,
            start_cluster=start_cluster,
        )
        
        adata_out: ad.AnnData = result["adata"]
        start_cluster_used = result["start_cluster"]
        
        # 保存 h5ad
        h5ad_id = f"{uuid.uuid4()}.h5ad"
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        output_path = os.path.join(OUTPUT_DIR, h5ad_id)
        adata_out.write_h5ad(output_path)
        logger.info("SpaTrack pseudotime results saved: %s", output_path)
        
        # 生成可视化图
        plot_ids = generate_spatrack_plots(
            adata_out,
            output_dir=OUTPUT_DIR,
            cluster_key=cluster_key,
        )
        
        # 生成报告
        report_id = generate_pseudotime_report(
            OUTPUT_DIR,
            adata=adata_out,
            start_cluster=start_cluster_used,
            cluster_key=cluster_key,
            n_neigh_pos=n_neigh_pos,
        )
        
        # 生物学逻辑评估
        biological_evaluation = evaluate_biological_logic(
            adata_out, 
            cluster_key=cluster_key, 
            start_cluster=start_cluster_used
        )
        
        # 构建响应（参照 GraphST 服务的返回格式）
        data_dict = {
            "spatial_pseudotime_spatrack.h5ad": h5ad_id,
            "pseudotime_report.txt": report_id,
        }
        
        # 添加图片文件（只添加成功生成的）
        expected_plots = {
            "spatial_pseudotime.png": "spatial_pseudotime",
            "streamplot.png": "streamplot",
            "pseudotime_distribution.png": "pseudotime_distribution",
        }
        for filename, plot_key in expected_plots.items():
            if plot_key in plot_ids:
                data_dict[filename] = plot_ids[plot_key]
        
        response_data = {
            "success": True,
            "message": "SpaTrack pseudotime analysis completed successfully",
            "data": data_dict,
        }
        
        logger.info("SpaTrack analysis completed successfully: %s", h5ad_id)
        return JSONResponse(
            status_code=200,
            content=response_data,
        )
        
    except Exception as e:
        logger.error("SpaTrack analysis failed: %s", str(e), exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"SpaTrack pseudotime analysis failed: {str(e)}"},
        )
    
    finally:
        # 清理临时文件
        if temp_input_path and os.path.exists(temp_input_path):
            try:
                os.remove(temp_input_path)
                logger.debug("Temporary input file removed: %s", temp_input_path)
            except Exception as e:
                logger.warning("Failed to remove temporary file %s: %s", temp_input_path, e)


@app.get("/api/download/{file_id}")
async def download_file(file_id: str):
    """下载输出文件"""
    file_path = os.path.join(OUTPUT_DIR, file_id)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        file_path,
        media_type="application/octet-stream",
        filename=file_id,
    )


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)

