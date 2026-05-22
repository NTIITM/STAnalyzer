#!/usr/bin/env python3
"""
Tangram 空间插补服务
基于 tutorial_tangram_with_squidpy 教程重构
"""
import os
import json
import logging
import tempfile
import uuid
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, Literal, Optional, Tuple

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

try:
    import anndata as ad
    import scanpy as sc
    import pandas as pd
    import numpy as np
    import tangram as tg
    import torch
    import matplotlib
    import seaborn as sns

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    BIO_AVAILABLE = True
    TANGRAM_AVAILABLE = True
    PLOT_AVAILABLE = True
except Exception as e:  # pragma: no cover - import guard
    logging.warning("核心依赖导入失败: %s", e)
    BIO_AVAILABLE = False
    TANGRAM_AVAILABLE = False
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
    title="Tangram 空间插补服务",
    description="使用 Tangram 将单细胞参考映射到空间转录组，输出插补 h5ad、映射得分与统计。",
    version="1.0.0",
)

OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def _read_adata(
    file_path: str,
    file_type: Literal["auto", "h5ad", "10x_h5", "csv", "tsv"] = "auto",
) -> "ad.AnnData":
    """读取 AnnData 文件"""
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


def _save_upload(upload: UploadFile) -> str:
    """保存上传文件到临时路径"""
    temp_path = os.path.join(
        tempfile.gettempdir(), f"input_{uuid.uuid4()}_{upload.filename}"
    )
    with open(temp_path, "wb") as f:
        content = upload.file.read()
        f.write(content)
    logger.info("上传文件已保存 %s (%d bytes)", temp_path, os.path.getsize(temp_path))
    return temp_path


def _clean_adata(adata: "ad.AnnData") -> "ad.AnnData":
    """清理 AnnData 中的无限值和 NaN 值"""
    try:
        if hasattr(adata.X, "toarray"):
            X_dense = adata.X.toarray()
            X_dense = np.nan_to_num(X_dense, nan=0.0, posinf=0.0, neginf=0.0)
            from scipy import sparse
            adata.X = sparse.csr_matrix(X_dense)
        else:
            X_dense = np.asarray(adata.X)
            X_dense = np.nan_to_num(X_dense, nan=0.0, posinf=0.0, neginf=0.0)
            adata.X = X_dense
        logger.info(f"Cleaned adata: shape={adata.shape}")
    except Exception as e:
        logger.warning(f"Error cleaning adata: {e}")
    return adata


def _prepare_adata_for_hvg(adata: "ad.AnnData") -> "ad.AnnData":
    """
    为 HVG 选择准备数据：创建副本并彻底清理无穷大值和 NaN 值
    
    参考教程和 spage-service 的实现，确保在 HVG 选择前数据完全干净
    """
    # 创建数据副本，避免修改原始数据
    adata_clean = adata.copy()
    
    # 转换为密集矩阵进行清理
    X_dense = _sparse_to_ndarray(adata_clean.X)
    
    # 检查并清理无穷大值和 NaN 值
    if np.any(~np.isfinite(X_dense)):
        logger.info("检测到数据中的无穷大或 NaN 值，进行清理")
        # 将无穷大和 NaN 替换为 0
        X_dense = np.where(np.isfinite(X_dense), X_dense, 0.0)
        
        # 确保没有负值（某些操作可能产生负值）
        X_dense = np.maximum(X_dense, 0.0)
        
        # 转换回稀疏矩阵（如果原始是稀疏的）
        if hasattr(adata.X, "toarray"):
            from scipy import sparse
            adata_clean.X = sparse.csr_matrix(X_dense)
        else:
            adata_clean.X = X_dense
    
    # 再次验证数据中没有无穷大值
    X_check = _sparse_to_ndarray(adata_clean.X)
    if np.any(~np.isfinite(X_check)):
        logger.warning("清理后仍存在无穷大值，进行二次清理")
        X_check = np.where(np.isfinite(X_check), X_check, 0.0)
        X_check = np.maximum(X_check, 0.0)
        if hasattr(adata_clean.X, "toarray"):
            from scipy import sparse
            adata_clean.X = sparse.csr_matrix(X_check)
        else:
            adata_clean.X = X_check
    
    # 清理 var 和 obs 中的统计量，避免在计算 HVG 时产生无穷大
    # 清理 var 中的统计量
    if hasattr(adata_clean, "var") and adata_clean.var.shape[1] > 0:
        for col in adata_clean.var.columns:
            if adata_clean.var[col].dtype in [np.float64, np.float32]:
                if np.any(~np.isfinite(adata_clean.var[col].values)):
                    logger.info(f"清理 var['{col}'] 中的无穷大值")
                    adata_clean.var[col] = adata_clean.var[col].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    
    # 清理 obs 中的统计量
    if hasattr(adata_clean, "obs") and adata_clean.obs.shape[1] > 0:
        for col in adata_clean.obs.columns:
            if adata_clean.obs[col].dtype in [np.float64, np.float32]:
                if np.any(~np.isfinite(adata_clean.obs[col].values)):
                    logger.info(f"清理 obs['{col}'] 中的无穷大值")
                    adata_clean.obs[col] = adata_clean.obs[col].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    
    # 最终验证和清理
    X_final = _sparse_to_ndarray(adata_clean.X)
    is_finite = np.all(np.isfinite(X_final))
    
    # 清理非有限值
    if not is_finite:
        logger.warning("数据清理后仍存在非有限值，强制清理")
        X_final = np.where(np.isfinite(X_final), X_final, 0.0)
        X_final = np.maximum(X_final, 0.0)
    
    # 裁剪极端值，避免在 HVG 计算时产生无穷大
    # 使用 99.9% 分位数作为上限，避免极端值影响统计计算
    if X_final.size > 0:
        upper_bound = np.percentile(X_final[X_final > 0], 99.9) if np.any(X_final > 0) else np.max(X_final)
        if np.isfinite(upper_bound) and upper_bound > 0:
            # 只裁剪明显异常的值（超过 99.9% 分位数的 10 倍）
            extreme_threshold = upper_bound * 10
            if np.any(X_final > extreme_threshold):
                logger.info(f"裁剪极端值 (阈值: {extreme_threshold:.2f})")
                X_final = np.clip(X_final, 0, extreme_threshold)
    
    # 确保数据是有限的
    X_final = np.where(np.isfinite(X_final), X_final, 0.0)
    X_final = np.maximum(X_final, 0.0)
    
    # 更新数据矩阵
    if hasattr(adata_clean.X, "toarray"):
        from scipy import sparse
        adata_clean.X = sparse.csr_matrix(X_final)
    else:
        adata_clean.X = X_final
    
    # 删除可能包含无穷大值的预计算统计量，让 scanpy 重新计算
    # 这些统计量可能在 HVG 计算时导致问题
    stats_to_remove = ['mean', 'std', 'var', 'dispersions', 'dispersions_norm', 
                       'highly_variable', 'highly_variable_nbatches', 'means', 
                       'variances', 'variances_norm']
    for stat in stats_to_remove:
        if stat in adata_clean.var.columns:
            logger.info(f"删除可能包含问题的预计算统计量: var['{stat}']")
            adata_clean.var = adata_clean.var.drop(columns=[stat], errors='ignore')
    
    logger.info(f"数据准备完成: shape={adata_clean.shape}, finite values: {np.all(np.isfinite(X_final))}")
    
    return adata_clean


def _select_training_genes(
    adata_sc: "ad.AnnData", top_genes: int
) -> Tuple[Optional[list], str]:
    """
    选择训练基因，按照教程顺序：
    1. 尝试使用标记基因（如果有细胞类型注释）
    2. 使用高变基因（HVG）
    3. 使用所有重叠基因（fallback）
    
    返回: (genes_list, source_description)
    """
    # 方法1: 尝试使用标记基因（教程 Cell 11-12）
    cell_type_cols = ["cell_subclass", "cell_type", "cluster", "annotation", "celltype"]
    cell_type_col = None
    
    if hasattr(adata_sc, "obs") and adata_sc.obs.shape[1] > 0:
        for col in cell_type_cols:
            if col in adata_sc.obs.columns:
                cell_type_col = col
                break
    
    if cell_type_col is not None:
        try:
            logger.info(f"使用 {cell_type_col} 选择标记基因（教程方法）")
            # 教程 Cell 12: 使用 rank_genes_groups 找标记基因
            sc.tl.rank_genes_groups(
                adata_sc, groupby=cell_type_col, use_raw=False, method="t-test"
            )
            
            # 提取前100个标记基因（教程 Cell 12）
            markers_df = pd.DataFrame(adata_sc.uns["rank_genes_groups"]["names"]).iloc[
                0:100, :
            ]
            markers = list(np.unique(markers_df.melt().value.values))
            
            if len(markers) > 0:
                # 如果标记基因数量超过 top_genes，优先选择在多个组中出现的基因
                if len(markers) > top_genes:
                    marker_counts = markers_df.melt().value_counts()
                    markers = marker_counts.head(top_genes).index.tolist()
                
                logger.info(f"选择了 {len(markers)} 个标记基因")
                return markers, f"marker_genes_{cell_type_col}"
        except Exception as e:
            logger.warning(f"标记基因选择失败: {e}，尝试其他方法")
    
    # 方法2: 使用高变基因（HVG）
    # 在 HVG 选择前，准备干净的数据副本
    logger.info("准备数据用于 HVG 选择")
    adata_sc_clean = _prepare_adata_for_hvg(adata_sc)
    
    try:
        logger.info("使用高变基因（HVG）作为训练基因")
        # 优先尝试 seurat_v3 方法（不依赖 binning，更稳定）
        try:
            hvgs = sc.pp.highly_variable_genes(
                adata_sc_clean, n_top_genes=top_genes, inplace=False, flavor="seurat_v3"
            )
            training_genes = hvgs.index[hvgs["highly_variable"]].tolist()
            logger.info(f"选择了 {len(training_genes)} 个 HVG (seurat_v3)")
            return training_genes, "hvg_seurat_v3"
        except Exception as e:
            logger.warning(f"HVG with seurat_v3 flavor failed: {e}, trying seurat flavor...")
            # 尝试 seurat 方法
            try:
                hvgs = sc.pp.highly_variable_genes(
                    adata_sc_clean, n_top_genes=top_genes, inplace=False, flavor="seurat"
                )
                training_genes = hvgs.index[hvgs["highly_variable"]].tolist()
                logger.info(f"选择了 {len(training_genes)} 个 HVG (seurat)")
                return training_genes, "hvg_seurat"
            except Exception as e2:
                logger.warning(f"HVG with seurat flavor failed: {e2}, trying manual variance-based selection...")
                # 手动计算方差并选择高变基因（fallback 方法）
                try:
                    X = _sparse_to_ndarray(adata_sc_clean.X)
                    # 确保数据是有限的
                    X = np.where(np.isfinite(X), X, 0.0)
                    X = np.maximum(X, 0.0)
                    
                    # 计算每个基因的均值和方差
                    gene_means = np.mean(X, axis=0)
                    gene_vars = np.var(X, axis=0)
                    
                    # 清理统计量中的无穷大值
                    gene_means = np.where(np.isfinite(gene_means), gene_means, 0.0)
                    gene_vars = np.where(np.isfinite(gene_vars), gene_vars, 0.0)
                    
                    # 计算变异系数（CV = std/mean），避免除零
                    gene_means_safe = np.where(gene_means > 0, gene_means, 1e-10)
                    gene_stds = np.sqrt(gene_vars)
                    gene_cvs = gene_stds / gene_means_safe
                    gene_cvs = np.where(np.isfinite(gene_cvs), gene_cvs, 0.0)
                    
                    # 选择变异系数最高的基因
                    top_indices = np.argsort(gene_cvs)[::-1][:top_genes]
                    training_genes = adata_sc_clean.var.index[top_indices].tolist()
                    logger.info(f"选择了 {len(training_genes)} 个 HVG (手动方差方法)")
                    return training_genes, "hvg_manual_variance"
                except Exception as e3:
                    logger.warning(f"手动方差方法也失败: {e3}")
                    raise e3
    except Exception as e:
        logger.warning(f"HVG 选择失败: {e}")
    
    # 方法3: 返回 None，让 pp_adatas 使用所有重叠基因
    logger.info("将使用所有重叠基因作为训练基因")
    return None, "all_overlapping"


def _sparse_to_ndarray(matrix) -> np.ndarray:
    """将稀疏矩阵转换为 numpy 数组"""
    if matrix is None:
        return np.array([])
    if hasattr(matrix, "toarray"):
        return matrix.toarray()
    return np.asarray(matrix)


def _plot_score_distribution(scores: np.ndarray, output_dir: str) -> Optional[str]:
    """绘制映射得分分布图"""
    if not PLOT_AVAILABLE or scores.size == 0:
        return None
    try:
        finite_scores = scores[np.isfinite(scores)]
        if finite_scores.size == 0:
            logger.warning("No finite scores to plot")
            return None

        n_bins = min(40, max(10, int(np.sqrt(finite_scores.size))))
        if n_bins < 1:
            n_bins = 10

        fig, ax = plt.subplots(figsize=(8, 5))
        ax.hist(
            finite_scores,
            bins=n_bins,
            color="steelblue",
            alpha=0.8,
            edgecolor="black",
        )
        ax.set_xlabel("mapping score (sum of weights per spot)")
        ax.set_ylabel("count")
        ax.set_title("Tangram mapping score distribution")
        plt.tight_layout()
        file_id = f"{uuid.uuid4()}.png"
        file_path = os.path.join(output_dir, file_id)
        plt.savefig(file_path, dpi=200, bbox_inches="tight")
        plt.close(fig)
        return file_id
    except Exception as e:
        logger.warning("绘制得分分布失败: %s", e)
        return None


def _plot_training_scores(ad_map: "ad.AnnData", output_dir: str) -> Optional[str]:
    """
    绘制训练基因得分图（教程 Cell 25）
    包含4个面板：
    1. 训练基因相似度分数的直方图
    2. 训练分数 vs scRNA-seq 数据稀疏度
    3. 训练分数 vs 空间数据稀疏度
    4. 训练分数 vs 稀疏度差异
    """
    if not PLOT_AVAILABLE or not TANGRAM_AVAILABLE:
        return None
    try:
        if "train_genes_df" not in ad_map.uns:
            logger.warning("ad_map.uns['train_genes_df'] 不存在，无法绘制训练得分图")
            return None
        
        tg.plot_training_scores(ad_map, bins=20, alpha=0.5)
        file_id = f"{uuid.uuid4()}.png"
        file_path = os.path.join(output_dir, file_id)
        plt.savefig(file_path, dpi=200, bbox_inches="tight")
        plt.close()
        logger.info("训练基因得分图已保存")
        return file_id
    except Exception as e:
        logger.warning("绘制训练基因得分图失败: %s", e)
        return None


def _plot_auc_validation(
    ad_ge: "ad.AnnData",
    adata_st: "ad.AnnData",
    adata_sc: "ad.AnnData",
    output_dir: str,
) -> Optional[str]:
    """
    绘制 AUC 验证图（教程 Cell 43）
    这是最重要的验证图，显示所有基因的得分 vs 空间数据稀疏度
    用于评估映射质量
    """
    if not PLOT_AVAILABLE or not TANGRAM_AVAILABLE:
        return None
    try:
        # 比较空间基因表达（教程 Cell 41）
        df_all_genes = tg.compare_spatial_geneexp(ad_ge, adata_st, adata_sc)
        
        # 手动绘制 AUC 图（教程 Cell 43）
        # 修复：tg.plot_auc() 内部使用的 seaborn.scatterplot() 在新版本中 API 不兼容
        # 因此手动绘制，参考教程中的实现
        plt.figure(figsize=(10, 6))
        sns.scatterplot(
            data=df_all_genes,
            x='score',
            y='sparsity_sp',
            hue='is_training',
            alpha=0.5
        )
        plt.xlabel('Gene Score', fontsize=12)
        plt.ylabel('Spatial Data Sparsity', fontsize=12)
        plt.title('AUC Validation: Gene Score vs Spatial Sparsity', fontsize=14)
        plt.legend(title='Is Training Gene', loc='best')
        plt.tight_layout()
        
        file_id = f"{uuid.uuid4()}.png"
        file_path = os.path.join(output_dir, file_id)
        plt.savefig(file_path, dpi=200, bbox_inches="tight")
        plt.close()
        logger.info("AUC 验证图已保存")
        return file_id
    except Exception as e:
        logger.warning("绘制 AUC 验证图失败: %s", e)
        return None


def _cleanup(paths: Tuple[str, ...]) -> None:
    """清理临时文件"""
    for p in paths:
        if p and os.path.exists(p):
            try:
                os.remove(p)
            except Exception as e:
                logger.debug("清理临时文件失败 %s: %s", p, e)


@app.post("/api/impute")
async def tangram_impute(
    spatial_file: UploadFile = File(..., description="空间转录组 h5ad"),
    single_cell_file: UploadFile = File(..., description="单细胞参考 h5ad"),
    spatial_file_type: Literal["auto", "h5ad", "10x_h5", "csv", "tsv"] = Form("auto"),
    single_cell_file_type: Literal["auto", "h5ad", "10x_h5", "csv", "tsv"] = Form(
        "auto"
    ),
    mode: Literal["cells", "clusters"] = Form("cells"),
    n_epochs: int = Form(250),
    learning_rate: float = Form(0.005),
    lambda_dreg: float = Form(5.0),
    top_genes: int = Form(3000),
    seed: int = Form(1234),
) -> JSONResponse:
    """
    使用 Tangram 将单细胞参考映射到空间数据，返回插补后的空间表达与映射得分。
    完全按照 tutorial_tangram_with_squidpy 教程实现。
    """
    if not BIO_AVAILABLE or not TANGRAM_AVAILABLE:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": "核心生信依赖未安装（anndata/scanpy/tangram/torch）",
            },
        )

    spatial_path = None
    sc_path = None
    try:
        # 保存上传文件
        spatial_path = _save_upload(spatial_file)
        sc_path = _save_upload(single_cell_file)

        # 读取数据（教程 Cell 5）
        logger.info("读取数据文件")
        adata_sp = _read_adata(spatial_path, spatial_file_type)
        adata_sc = _read_adata(sc_path, single_cell_file_type)

        # 清理数据
        adata_sp = _clean_adata(adata_sp)
        adata_sc = _clean_adata(adata_sc)

        logger.info(f"空间数据: {adata_sp.shape}, 单细胞数据: {adata_sc.shape}")

        # 设置随机种子
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
        np.random.seed(seed)

        # 选择训练基因（教程 Cell 11-12）
        logger.info("选择训练基因")
        training_genes, training_genes_source = _select_training_genes(
            adata_sc, top_genes
        )

        # 预处理数据（教程 Cell 14）
        # tg.pp_adatas 会：
        # - 确保基因顺序一致
        # - 过滤掉在任一数据集中全为0的基因
        # - 过滤掉不在两个数据集中的基因
        # - 将训练基因保存到 uns['training_genes']
        # - 计算密度先验
        logger.info(
            f"预处理数据 (tg.pp_adatas)，训练基因: {len(training_genes) if training_genes else '所有重叠基因'}"
        )
        tg.pp_adatas(adata_sc, adata_sp, genes=training_genes)

        # 检查训练基因（教程 Cell 14-15）
        if "training_genes" not in adata_sc.uns:
            error_msg = "tg.pp_adatas 未保存训练基因到 uns['training_genes']，数据可能有问题"
            logger.error(error_msg)
            raise ValueError(error_msg)

        actual_training_genes = adata_sc.uns["training_genes"]
        n_training_genes = len(actual_training_genes)
        logger.info(f"实际使用的训练基因数: {n_training_genes}")

        if n_training_genes == 0:
            error_msg = "训练基因数为0，无法进行映射。请检查数据质量和基因重叠情况。"
            logger.error(error_msg)
            raise ValueError(error_msg)

        # 获取重叠基因数
        n_overlap_genes = (
            len(adata_sc.uns["overlap_genes"])
            if "overlap_genes" in adata_sc.uns
            else 0
        )

        # 映射细胞到空间（教程 Cell 18）
        logger.info(f"开始映射 (mode={mode}, epochs={n_epochs})")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        ad_map = tg.map_cells_to_space(
            adata_sc=adata_sc,
            adata_sp=adata_sp,
            mode=mode,
            num_epochs=n_epochs,
            learning_rate=learning_rate,
            lambda_d=lambda_dreg,
            density_prior="rna_count_based",  # 教程默认值
            device=device,
        )

        logger.info("映射完成，开始投影基因")

        # 投影基因创建插补空间数据（教程 Cell 31）
        ad_ge = tg.project_genes(adata_map=ad_map, adata_sc=adata_sc)
        logger.info(f"插补数据形状: {ad_ge.shape}")

        # 提取映射得分
        map_matrix = _sparse_to_ndarray(getattr(ad_map, "X", None))
        spot_ids = ad_map.var_names.tolist() if hasattr(ad_map, "var_names") else []

        if map_matrix.size == 0 or map_matrix.shape[1] == 0:
            scores = np.array([])
            n_mapped_cells = np.array([])
            mapping_entropy = np.array([])
        else:
            # 映射得分：每个spot的权重总和（列和）
            scores = map_matrix.sum(axis=0).ravel()

            # 每个spot映射的细胞数
            if mode == "cells":
                n_mapped_cells = (map_matrix > 0).sum(axis=0).ravel()
            else:
                n_mapped_cells = np.array([])

            # 映射熵
            from scipy.stats import entropy

            mapping_entropy = np.array(
                [
                    entropy(map_matrix[:, j]) if map_matrix[:, j].sum() > 0 else 0.0
                    for j in range(map_matrix.shape[1])
                ]
            )

        # 构建统计信息
        stats = {
            "mode": mode,
            "n_epochs": int(n_epochs),
            "learning_rate": float(learning_rate),
            "lambda_dreg": float(lambda_dreg),
            "top_genes": int(top_genes),
            "seed": int(seed),
            "device": device,
            "density_prior": "rna_count_based",
            "spatial_shape": list(adata_sp.shape),
            "single_cell_shape": list(adata_sc.shape),
            "genes_used": n_training_genes,
            "training_genes_count": n_training_genes,
            "training_genes_source": training_genes_source,
            "overlap_genes_count": n_overlap_genes,
            "imputed_shape": list(ad_ge.shape),
        }

        # 映射得分统计
        if scores.size > 0:
            stats["mapping_score_summary"] = {
                "min": float(np.min(scores)),
                "max": float(np.max(scores)),
                "mean": float(np.mean(scores)),
                "median": float(np.median(scores)),
            }
        else:
            stats["mapping_score_summary"] = {
                "min": None,
                "max": None,
                "mean": None,
                "median": None,
            }

        # 创建映射得分 DataFrame
        n_spots = len(spot_ids)
        mapping_df_data = {
            "spot_id": spot_ids,
            "mapping_score": (
                scores.tolist() if scores.size > 0 and len(scores) == n_spots else [None] * n_spots
            ),
        }

        if n_mapped_cells.size > 0 and len(n_mapped_cells) == n_spots:
            mapping_df_data["n_mapped_cells"] = n_mapped_cells.tolist()
        else:
            mapping_df_data["n_mapped_cells"] = [None] * n_spots

        if mapping_entropy.size > 0 and len(mapping_entropy) == n_spots:
            mapping_df_data["mapping_entropy"] = mapping_entropy.tolist()
        else:
            mapping_df_data["mapping_entropy"] = [None] * n_spots

        mapping_df = pd.DataFrame(mapping_df_data)

        # 保存文件
        h5ad_id = f"{uuid.uuid4()}.h5ad"
        mapping_id = f"{uuid.uuid4()}.csv"
        statistics_id = f"{uuid.uuid4()}.txt"

        imputed_path = os.path.join(OUTPUT_DIR, h5ad_id)
        mapping_path = os.path.join(OUTPUT_DIR, mapping_id)
        statistics_path = os.path.join(OUTPUT_DIR, statistics_id)

        ad_ge.write_h5ad(imputed_path)
        mapping_df.to_csv(mapping_path, index=False)

        # Generate statistics report text (contains all statistical information)
        stats_text_parts = []
        stats_text_parts.append("=" * 60)
        stats_text_parts.append("Tangram Spatial Imputation Statistics Report")
        stats_text_parts.append("=" * 60)
        stats_text_parts.append("\n1. Analysis Parameters")
        stats_text_parts.append(f"  mode: {mode}")
        stats_text_parts.append(f"  n_epochs: {n_epochs}")
        stats_text_parts.append(f"  learning_rate: {learning_rate}")
        stats_text_parts.append(f"  lambda_dreg: {lambda_dreg}")
        stats_text_parts.append(f"  top_genes: {top_genes}")
        stats_text_parts.append(f"  seed: {seed}")
        stats_text_parts.append(f"  device: {device}")
        stats_text_parts.append("\n2. Data Statistics")
        stats_text_parts.append(f"  Spatial data cells: {stats['spatial_shape'][0]:,}")
        stats_text_parts.append(f"  Spatial data genes: {stats['spatial_shape'][1]:,}")
        stats_text_parts.append(f"  Single-cell reference data cells: {stats['single_cell_shape'][0]:,}")
        stats_text_parts.append(f"  Single-cell reference data genes: {stats['single_cell_shape'][1]:,}")
        stats_text_parts.append(f"  Number of training genes used: {n_training_genes:,}")
        
        source_map = {
            "marker_genes_cell_subclass": "Marker genes (cell_subclass)",
            "marker_genes_cell_type": "Marker genes (cell_type)",
            "marker_genes_cluster": "Marker genes (cluster)",
            "hvg_seurat_v3": "Highly variable genes (seurat_v3)",
            "hvg_seurat": "Highly variable genes (seurat)",
            "hvg_default": "Highly variable genes (default)",
            "hvg_manual_variance": "Highly variable genes (manual variance)",
            "all_overlapping": "All overlapping genes",
        }
        source_name = source_map.get(training_genes_source, training_genes_source)
        stats_text_parts.append(f"  Training genes source: {source_name}")
        
        if n_overlap_genes > 0:
            stats_text_parts.append(f"  Total overlapping genes: {n_overlap_genes:,}")

        stats_text_parts.append("\n3. Mapping Statistics")
        if scores.size > 0:
            stats_text_parts.append(f"  Mean mapping score: {float(np.mean(scores)):.4f}")
            stats_text_parts.append(f"  Min mapping score: {float(np.min(scores)):.4f}")
            stats_text_parts.append(f"  Max mapping score: {float(np.max(scores)):.4f}")
            stats_text_parts.append(f"  Median mapping score: {float(np.median(scores)):.4f}")
        else:
            stats_text_parts.append("  Mapping score statistics: Not available")

        stats_text = "\n".join(stats_text_parts)
        with open(statistics_path, "w", encoding="utf-8") as f:
            f.write(stats_text)

        # 绘制可视化图表（cell mode 下）
        qc_png_id = _plot_score_distribution(scores, OUTPUT_DIR)
        training_scores_png_id = None
        auc_png_id = None
        
        if mode == "cells":
            # 绘制训练基因得分图（教程 Cell 25）
            training_scores_png_id = _plot_training_scores(ad_map, OUTPUT_DIR)
            
            # 绘制 AUC 验证图（教程 Cell 43）- 最重要的验证图
            try:
                auc_png_id = _plot_auc_validation(ad_ge, adata_sp, adata_sc, OUTPUT_DIR)
            except Exception as e:
                logger.warning("AUC 验证图生成失败: %s", e)

        data_dict: Dict[str, Any] = {
            "imputed_spatial_data.h5ad": h5ad_id,
            "mapping_scores.csv": mapping_id,
            "statistics.txt": statistics_id,
        }
        
        # 添加可视化文件
        if qc_png_id:
            data_dict["mapping_score_distribution.png"] = qc_png_id
        if training_scores_png_id:
            data_dict["training_scores.png"] = training_scores_png_id
        if auc_png_id:
            data_dict["auc_validation.png"] = auc_png_id
        
        # 为了向后兼容，保留 imputation_qc.png 的别名
        if qc_png_id:
            data_dict["imputation_qc.png"] = qc_png_id

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Tangram 插补完成",
                "data": data_dict,
            },
        )
    except Exception as e:
        logger.error("Tangram 插补失败: %s", e, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": "Tangram 插补失败",
                "error": {
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                },
            },
        )
    finally:
        _cleanup((spatial_path, sc_path))


@app.get("/api/download/{file_id}")
async def download_file(file_id: str) -> FileResponse:
    """下载输出文件"""
    file_path = os.path.join(OUTPUT_DIR, file_id)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"文件不存在: {file_id}")

    if file_path.endswith(".png"):
        media_type = "image/png"
    elif file_path.endswith(".h5ad"):
        media_type = "application/octet-stream"
    elif file_path.endswith(".csv"):
        media_type = "text/csv"
    elif file_path.endswith(".json"):
        media_type = "application/json"
    elif file_path.endswith(".txt"):
        media_type = "text/plain"
    else:
        media_type = "application/octet-stream"

    filename = os.path.basename(file_path)
    logger.info("下载文件 %s", file_path)
    return FileResponse(path=file_path, filename=filename, media_type=media_type)


@app.get("/health")
async def health():
    """健康检查"""
    return {
        "status": "healthy",
        "bio_available": BIO_AVAILABLE,
        "tangram_available": TANGRAM_AVAILABLE,
        "output_dir": OUTPUT_DIR,
    }


if __name__ == "__main__":
    import uvicorn

    _port = int(os.getenv("PORT", 60890))
    uvicorn.run(app, host="0.0.0.0", port=_port)
