#!/usr/bin/env python3
"""
SpaGE 空间插补服务（KNN/SVD 实现，若可用则调用 SpaGE）
"""
import json
import os
import logging
import tempfile
import uuid
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, Iterable, Literal, Optional, Sequence, Tuple

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

# 导入核心依赖
try:
    import anndata as ad
    import scanpy as sc
    import pandas as pd
    import numpy as np
    from sklearn.decomposition import TruncatedSVD
    from sklearn.neighbors import NearestNeighbors
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    BIO_AVAILABLE = True
    PLOT_AVAILABLE = True
except Exception as e:  # pragma: no cover - import guard
    logging.warning("核心依赖导入失败: %s", e)
    BIO_AVAILABLE = False
    PLOT_AVAILABLE = False

# 尝试导入 SpaGE（可选）
SPAGE_AVAILABLE = False
if BIO_AVAILABLE:
    try:
        import SpaGE
        SPAGE_AVAILABLE = True
    except Exception as e:  # pragma: no cover - import guard
        logging.info("SpaGE 包未安装，将使用 KNN 实现: %s", e)
        SPAGE_AVAILABLE = False


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
    title="SpaGE 空间插补服务",
    description="使用 SpaGE（可用时）或 KNN/SVD 近邻插补将单细胞表达投射到空间数据。",
    version="1.0.0",
)

OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)


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


def _save_upload(upload: UploadFile) -> str:
    temp_path = os.path.join(
        tempfile.gettempdir(), f"input_{uuid.uuid4()}_{upload.filename}"
    )
    with open(temp_path, "wb") as f:
        content = upload.file.read()
        f.write(content)
    logger.info("上传文件已保存 %s (%d bytes)", temp_path, os.path.getsize(temp_path))
    return temp_path


def _sparse_to_ndarray(mat) -> np.ndarray:
    if mat is None:
        return np.array([])
    if hasattr(mat, "toarray"):
        return mat.toarray()
    return np.asarray(mat)


def _plot_distance_hist(distances: np.ndarray, output_dir: str) -> Optional[str]:
    if not PLOT_AVAILABLE or distances.size == 0:
        return None
    try:
        # 过滤掉无穷大和 NaN 值
        valid_distances = distances[np.isfinite(distances)]
        if valid_distances.size == 0:
            logger.warning("没有有效的距离值用于绘图")
            return None
        
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.hist(valid_distances, bins=40, color="coral", alpha=0.85, edgecolor="black")
        ax.set_xlabel("mean neighbor distance")
        ax.set_ylabel("count")
        ax.set_title("SpaGE/KNN distance distribution")
        plt.tight_layout()
        file_id = f"{uuid.uuid4()}.png"
        path = os.path.join(output_dir, file_id)
        plt.savefig(path, dpi=200, bbox_inches="tight")
        plt.close(fig)
        return file_id
    except Exception as e:
        logger.warning("绘制距离分布失败: %s", e)
        return None


def _cleanup(paths: Iterable[str]) -> None:
    for p in paths:
        if p and os.path.exists(p):
            try:
                os.remove(p)
            except Exception as e:  # pragma: no cover - best effort
                logger.debug("清理临时文件失败 %s: %s", p, e)


def _select_genes(
    adata_sc: "ad.AnnData", adata_sp: "ad.AnnData", top_genes: int
) -> Sequence[str]:
    common = adata_sc.var_names.intersection(adata_sp.var_names)
    if len(common) == 0:
        raise ValueError("单细胞与空间数据没有共同基因，无法插补")
    if top_genes is None or top_genes <= 0:
        return list(common)
    
    # 创建数据副本并清理无穷大和 NaN 值
    adata_sc_clean = adata_sc[:, common].copy()
    sc_matrix = _sparse_to_ndarray(adata_sc_clean.X)
    
    # 替换无穷大和 NaN 值为 0
    if np.any(~np.isfinite(sc_matrix)):
        logger.warning("检测到数据中的无穷大或 NaN 值，将进行清理")
        sc_matrix = np.where(np.isfinite(sc_matrix), sc_matrix, 0.0)
        adata_sc_clean.X = sc_matrix
    
    try:
        hvgs = sc.pp.highly_variable_genes(
            adata_sc_clean, n_top_genes=min(top_genes, len(common)), inplace=False
        )
        hvgs = hvgs.index[hvgs["highly_variable"]].tolist()
        selected = [g for g in hvgs if g in common]
        if not selected:
            return list(common)
        return selected
    except Exception as e:
        logger.warning("高度可变基因选择失败，使用所有共同基因: %s", e)
        # 如果选择失败，返回所有共同基因
        return list(common[:top_genes]) if top_genes < len(common) else list(common)


def _run_spage_if_available(
    adata_sp: "ad.AnnData",
    adata_sc: "ad.AnnData",
    genes: Sequence[str],
    k_neighbors: int,
    n_pcs: int,
    seed: int,
) -> Optional["ad.AnnData"]:
    if not SPAGE_AVAILABLE:
        return None
    try:
        # SpaGE 输入要求行是细胞，列是基因
        sc_mat = _sparse_to_ndarray(adata_sc[:, genes].X)
        sp_mat = _sparse_to_ndarray(adata_sp[:, genes].X)
        # SpaGE 返回 pandas DataFrame，索引为空间 spots，列为基因
        pred = SpaGE.SpaGE(sp_mat, sc_mat, genes, k=k_neighbors, n_pcs=n_pcs, seed=seed)
        adata_imputed = ad.AnnData(
            X=np.asarray(pred.values, dtype=float),
            obs=adata_sp.obs.copy(),
            var=pd.DataFrame(index=genes),
        )
        # 保留空间坐标
        for key in adata_sp.obsm_keys():
            adata_imputed.obsm[key] = adata_sp.obsm[key]
        return adata_imputed
    except Exception as e:
        logger.warning("SpaGE 原生调用失败，回退 KNN 实现: %s", e)
        return None


def _knn_impute(
    adata_sp: "ad.AnnData",
    adata_sc: "ad.AnnData",
    genes: Sequence[str],
    k_neighbors: int,
    n_pcs: int,
    seed: int,
) -> Tuple["ad.AnnData", np.ndarray]:
    sc_use = adata_sc[:, genes].copy()
    sp_use = adata_sp[:, genes].copy()

    sc.pp.normalize_total(sc_use, target_sum=1e4)
    sc.pp.log1p(sc_use)
    sc.pp.normalize_total(sp_use, target_sum=1e4)
    sc.pp.log1p(sp_use)

    sc_matrix = _sparse_to_ndarray(sc_use.X)
    sp_matrix = _sparse_to_ndarray(sp_use.X)

    n_components = max(2, min(n_pcs, len(genes), sc_use.shape[0] - 1))
    svd = TruncatedSVD(n_components=n_components, random_state=seed)
    sc_emb = svd.fit_transform(sc_matrix)
    sp_emb = svd.transform(sp_matrix)

    n_neighbors_eff = min(max(1, k_neighbors), sc_emb.shape[0])
    nn = NearestNeighbors(n_neighbors=n_neighbors_eff, metric="euclidean")
    nn.fit(sc_emb)
    distances, indices = nn.kneighbors(sp_emb, return_distance=True)
    weights = 1.0 / (distances + 1e-8)
    weights = weights / weights.sum(axis=1, keepdims=True)

    sc_dense = _sparse_to_ndarray(sc_use.X)
    imputed_matrix = (weights[:, :, None] * sc_dense[indices]).sum(axis=1)

    adata_imputed = ad.AnnData(
        X=imputed_matrix,
        obs=adata_sp.obs.copy(),
        var=pd.DataFrame(index=genes),
    )
    for key in adata_sp.obsm_keys():
        adata_imputed.obsm[key] = adata_sp.obsm[key]

    mean_dist = distances.mean(axis=1)
    return adata_imputed, mean_dist


@app.post("/api/impute")
async def spage_impute(
    spatial_file: UploadFile = File(..., description="空间转录组 h5ad"),
    single_cell_file: UploadFile = File(..., description="单细胞参考 h5ad"),
    spatial_file_type: Literal["auto", "h5ad", "10x_h5", "csv", "tsv"] = Form("auto"),
    single_cell_file_type: Literal["auto", "h5ad", "10x_h5", "csv", "tsv"] = Form(
        "auto"
    ),
    k_neighbors: int = Form(10),
    n_pcs: int = Form(30),
    top_genes: int = Form(3000),
    seed: int = Form(1234),
) -> JSONResponse:
    """
    使用 SpaGE（可用时）或 KNN/SVD 近邻插补将单细胞表达映射到空间数据。
    """
    if not BIO_AVAILABLE:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "核心生信依赖未安装"},
        )

    spatial_path = None
    sc_path = None
    try:
        spatial_path = _save_upload(spatial_file)
        sc_path = _save_upload(single_cell_file)

        adata_sp = _read_adata(spatial_path, spatial_file_type)
        adata_sc = _read_adata(sc_path, single_cell_file_type)

        genes = _select_genes(adata_sc, adata_sp, top_genes)

        stats: Dict[str, Any] = {
            "k_neighbors": int(k_neighbors),
            "n_pcs": int(n_pcs),
            "top_genes": int(top_genes),
            "seed": int(seed),
            "spatial_shape": adata_sp.shape,
            "single_cell_shape": adata_sc.shape,
            "genes_used": len(genes),
            "backend": "SpaGE" if SPAGE_AVAILABLE else "knn",
        }

        # 先尝试原生 SpaGE
        imputed = _run_spage_if_available(
            adata_sp, adata_sc, genes, k_neighbors, n_pcs, seed
        )
        mean_dist = np.array([])
        if imputed is None:
            imputed, mean_dist = _knn_impute(
                adata_sp, adata_sc, genes, k_neighbors, n_pcs, seed
            )
            stats["backend"] = "knn"
            stats["mean_neighbor_distance_summary"] = {
                "min": float(np.min(mean_dist)) if mean_dist.size else None,
                "max": float(np.max(mean_dist)) if mean_dist.size else None,
                "mean": float(np.mean(mean_dist)) if mean_dist.size else None,
                "median": float(np.median(mean_dist)) if mean_dist.size else None,
            }

        h5ad_id = f"{uuid.uuid4()}.h5ad"
        mapping_id = f"{uuid.uuid4()}.csv"
        stats_id = f"{uuid.uuid4()}.json"

        imputed_path = os.path.join(OUTPUT_DIR, h5ad_id)
        mapping_path = os.path.join(OUTPUT_DIR, mapping_id)
        stats_path = os.path.join(OUTPUT_DIR, stats_id)

        imputed.write_h5ad(imputed_path)

        if mean_dist.size == 0:
            # SpaGE 情况下给一个占位
            mean_dist = np.zeros(adata_sp.n_obs)

        mapping_df = pd.DataFrame(
            {
                "spatial_id": adata_sp.obs_names,
                "mean_neighbor_distance": mean_dist,
                "mapping_score": 1.0 / (1e-8 + mean_dist),
            }
        )
        mapping_df.to_csv(mapping_path, index=False)

        with open(stats_path, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)

        qc_png = _plot_distance_hist(mean_dist, OUTPUT_DIR)

        # 生成统计信息文本
        stats_text_parts = []
        stats_text_parts.append("=" * 60)
        stats_text_parts.append("SpaGE 空间插补统计报告")
        stats_text_parts.append("=" * 60)
        stats_text_parts.append(f"\n【一、分析参数】")
        stats_text_parts.append(f"  k_neighbors: {k_neighbors}")
        stats_text_parts.append(f"  n_pcs: {n_pcs}")
        stats_text_parts.append(f"  top_genes: {top_genes}")
        stats_text_parts.append(f"  seed: {seed}")
        stats_text_parts.append(f"  backend: {stats.get('backend', 'unknown')}")
        stats_text_parts.append(f"\n【二、数据统计】")
        spatial_shape = stats.get('spatial_shape', (0, 0))
        sc_shape = stats.get('single_cell_shape', (0, 0))
        stats_text_parts.append(f"  空间数据细胞数: {spatial_shape[0]:,}")
        stats_text_parts.append(f"  空间数据基因数: {spatial_shape[1]:,}")
        stats_text_parts.append(f"  单细胞参考数据细胞数: {sc_shape[0]:,}")
        stats_text_parts.append(f"  单细胞参考数据基因数: {sc_shape[1]:,}")
        stats_text_parts.append(f"  使用的基因数: {stats.get('genes_used', 0):,}")
        stats_text_parts.append(f"\n【三、映射统计】")
        if mean_dist.size > 0:
            stats_text_parts.append(f"  平均邻居距离: {float(np.mean(mean_dist)):.4f}")
            stats_text_parts.append(f"  最小距离: {float(np.min(mean_dist)):.4f}")
            stats_text_parts.append(f"  最大距离: {float(np.max(mean_dist)):.4f}")
            stats_text_parts.append(f"  中位数距离: {float(np.median(mean_dist)):.4f}")
        elif 'mean_neighbor_distance_summary' in stats:
            dist_summary = stats['mean_neighbor_distance_summary']
            stats_text_parts.append(f"  平均邻居距离: {dist_summary.get('mean', 0):.4f}")
            stats_text_parts.append(f"  最小距离: {dist_summary.get('min', 0):.4f}")
            stats_text_parts.append(f"  最大距离: {dist_summary.get('max', 0):.4f}")
            stats_text_parts.append(f"  中位数距离: {dist_summary.get('median', 0):.4f}")
        else:
            stats_text_parts.append("  距离统计: 不可用（SpaGE 模式）")
        
        stats_text = "\n".join(stats_text_parts)
        
        # 保存统计信息到文件
        statistics_id = f"{uuid.uuid4()}.txt"
        statistics_path = os.path.join(OUTPUT_DIR, statistics_id)
        with open(statistics_path, "w", encoding="utf-8") as f:
            f.write(stats_text)

        data_dict: Dict[str, Any] = {
            "imputed_spatial_data.h5ad": h5ad_id,
            "mapping_scores.csv": mapping_id,
            "imputation_stats.json": stats_id,
            "statistics.txt": statistics_id,
        }
        if qc_png:
            data_dict["imputation_qc.png"] = qc_png

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "SpaGE 插补完成",
                "data": data_dict,
            },
        )
    except Exception as e:
        logger.error("SpaGE 插补失败: %s", e, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": "SpaGE 插补失败",
                "error": {"error_type": type(e).__name__, "error_message": str(e)},
            },
        )
    finally:
        _cleanup((spatial_path, sc_path))


@app.get("/api/download/{file_id}")
async def download_file(file_id: str) -> FileResponse:
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
    else:
        media_type = "application/octet-stream"

    filename = os.path.basename(file_path)
    logger.info("下载文件 %s", file_path)
    return FileResponse(path=file_path, filename=filename, media_type=media_type)


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "bio_available": BIO_AVAILABLE,
        "spage_available": SPAGE_AVAILABLE,
        "output_dir": OUTPUT_DIR,
    }


if __name__ == "__main__":
    import uvicorn

    _port = int(os.getenv("PORT", 60891))
    uvicorn.run(app, host="0.0.0.0", port=_port)
