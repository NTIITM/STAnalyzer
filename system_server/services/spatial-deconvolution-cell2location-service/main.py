#!/usr/bin/env python3
"""
cell2location 空间去卷积服务
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
    import numpy as np
    if not hasattr(np, "float_"):
        np.float_ = np.float64  # backward compat for scanpy/cell2location on numpy>=2
    import anndata as ad
    import scanpy as sc
    import pandas as pd
    import torch
    import scvi
    import cell2location
    from cell2location.models import RegressionModel, Cell2location
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    BIO_AVAILABLE = True
    C2L_AVAILABLE = True
    PLOT_AVAILABLE = True
except Exception as e:  # pragma: no cover - import guard
    logging.warning("核心依赖导入失败: %s", e)
    BIO_AVAILABLE = False
    C2L_AVAILABLE = False
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
    title="cell2location 空间去卷积服务",
    description="使用 cell2location 估计空间转录组每个 spot/cell 的细胞类型丰度。",
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
    """保存上传文件到临时路径"""
    temp_path = os.path.join(
        tempfile.gettempdir(), f"input_{uuid.uuid4()}_{upload.filename}"
    )
    with open(temp_path, "wb") as f:
        content = upload.file.read()
        f.write(content)
    logger.info("上传文件已保存 %s (%d bytes)", temp_path, os.path.getsize(temp_path))
    return temp_path


def _cleanup(paths: Tuple[Optional[str], ...]) -> None:
    for p in paths:
        if p and os.path.exists(p):
            try:
                os.remove(p)
            except Exception as e:  # pragma: no cover - best effort
                logger.debug("清理临时文件失败 %s: %s", p, e)


def _align_genes(
    adata_sp: "ad.AnnData", adata_sc: "ad.AnnData"
) -> Tuple["ad.AnnData", "ad.AnnData", int]:
    common = adata_sp.var_names.intersection(adata_sc.var_names)
    if len(common) == 0:
        raise ValueError("空间数据与参考数据没有共有基因，无法建模")
    adata_sp = adata_sp[:, common].copy()
    adata_sc = adata_sc[:, common].copy()
    return adata_sp, adata_sc, len(common)


def _plot_abundance_sum(values: np.ndarray, output_dir: str) -> Optional[str]:
    if not PLOT_AVAILABLE or values.size == 0:
        return None
    try:
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.hist(values, bins=40, color="mediumseagreen", alpha=0.8, edgecolor="black")
        ax.set_xlabel("total inferred cells per location")
        ax.set_ylabel("count")
        ax.set_title("cell2location abundance distribution")
        plt.tight_layout()
        file_id = f"{uuid.uuid4()}.png"
        file_path = os.path.join(output_dir, file_id)
        plt.savefig(file_path, dpi=200, bbox_inches="tight")
        plt.close(fig)
        return file_id
    except Exception as e:
        logger.warning("绘制丰度分布失败: %s", e)
        return None


@app.post("/api/deconvolve")
async def cell2location_deconvolve(
    spatial_file: UploadFile = File(..., description="空间转录组 h5ad"),
    single_cell_file: UploadFile = File(..., description="单细胞参考 h5ad"),
    spatial_file_type: Literal["auto", "h5ad", "10x_h5", "csv", "tsv"] = Form("auto"),
    single_cell_file_type: Literal["auto", "h5ad", "10x_h5", "csv", "tsv"] = Form(
        "auto"
    ),
    cell_type_col: str = Form("cell_type"),
    sc_batch_key: Optional[str] = Form(None),
    sp_batch_key: Optional[str] = Form(None),
    N_cells_per_location: float = Form(30.0),
    detection_alpha: float = Form(200.0),
    max_epochs_ref: int = Form(250),
    max_epochs_spatial: int = Form(300),
    use_gpu: bool = Form(False),
) -> JSONResponse:
    """
    使用 cell2location 对空间数据做细胞成分去卷积，返回丰度矩阵与统计信息。
    """
    if not BIO_AVAILABLE or not C2L_AVAILABLE:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": "核心生信依赖未安装（anndata/scanpy/cell2location/scvi/torch）",
            },
        )

    spatial_path = None
    sc_path = None
    try:
        spatial_path = _save_upload(spatial_file)
        sc_path = _save_upload(single_cell_file)

        adata_sp = _read_adata(spatial_path, spatial_file_type)
        adata_sc = _read_adata(sc_path, single_cell_file_type)

        if cell_type_col not in adata_sc.obs:
            raise ValueError(f"单细胞参考缺少细胞类型列: {cell_type_col}")

        if sc_batch_key and sc_batch_key not in adata_sc.obs:
            raise ValueError(f"单细胞参考缺少批次列: {sc_batch_key}")
        if sp_batch_key and sp_batch_key not in adata_sp.obs:
            raise ValueError(f"空间数据缺少批次列: {sp_batch_key}")

        if not sc_batch_key:
            sc_batch_key = "batch_dummy_sc"
            adata_sc.obs[sc_batch_key] = "batch0"
        if not sp_batch_key:
            sp_batch_key = "batch_dummy_sp"
            adata_sp.obs[sp_batch_key] = "batch0"

        adata_sp, adata_sc, n_common = _align_genes(adata_sp, adata_sc)

        device = "gpu" if use_gpu and torch.cuda.is_available() else "cpu"
        stats: Dict[str, Any] = {
            "cell_type_col": cell_type_col,
            "sc_batch_key": sc_batch_key,
            "sp_batch_key": sp_batch_key,
            "N_cells_per_location": float(N_cells_per_location),
            "detection_alpha": float(detection_alpha),
            "max_epochs_ref": int(max_epochs_ref),
            "max_epochs_spatial": int(max_epochs_spatial),
            "use_gpu": use_gpu and torch.cuda.is_available(),
            "device": device,
            "spatial_shape": adata_sp.shape,
            "single_cell_shape": adata_sc.shape,
            "common_genes": n_common,
        }

        # 训练参考模型
        RegressionModel.setup_anndata(
            adata_sc, batch_key=sc_batch_key, labels_key=cell_type_col
        )
        ref_model = RegressionModel(adata_sc)
        # scvi>=1.4 的 TrainRunner 若收到重复 devices 会报错，这里仅指定 accelerator。
        ref_model.train(max_epochs=max_epochs_ref, accelerator=device)
        ref_model.export_posterior(
            adata_sc, sample_kwargs={"num_samples": 100, "batch_size": None}
        )
        mu = adata_sc.varm.get("means_per_cluster_mu_fg")
        if mu is None:
            raise RuntimeError("未生成参考签名 means_per_cluster_mu_fg")
        reference_signatures = pd.DataFrame(mu)
        reference_signatures.columns = [
            col.replace("means_per_cluster_mu_fg_", "") for col in reference_signatures.columns
        ]

        # 训练空间模型
        Cell2location.setup_anndata(adata_sp, batch_key=sp_batch_key)
        c2l_model = Cell2location(
            adata_sp,
            cell_state_df=reference_signatures,
            N_cells_per_location=N_cells_per_location,
            detection_alpha=detection_alpha,
        )
        c2l_model.train(max_epochs=max_epochs_spatial, accelerator=device)

        posterior = c2l_model.export_posterior(
            adata=adata_sp,
            sample_kwargs={"num_samples": 1000, "batch_size": None},
        )

        abundance = posterior.obsm.get("means_cell_abundance_w_sf")
        q05 = posterior.obsm.get("q05_cell_abundance_w_sf")

        if abundance is None:
            raise RuntimeError("未从 cell2location 输出中获得丰度矩阵")

        # Handle abundance: it may be a DataFrame or array
        if isinstance(abundance, pd.DataFrame):
            # Extract cell type names from column names (remove prefix)
            # Column names are like "meanscell_abundance_w_sf_Bcell" or "means_cell_abundance_w_sf_Bcell"
            abundance_df = abundance.copy()
            # Try to extract cell type names by removing common prefixes
            new_cols = []
            for col in abundance_df.columns:
                # Remove prefixes like "meanscell_abundance_w_sf_" or "means_cell_abundance_w_sf_"
                for prefix in ["meanscell_abundance_w_sf_", "means_cell_abundance_w_sf_"]:
                    if col.startswith(prefix):
                        new_cols.append(col[len(prefix):])
                        break
                else:
                    # If no prefix matches, use the original column name
                    new_cols.append(col)
            abundance_df.columns = new_cols
            abundance_df.index = posterior.obs_names
        else:
            # If it's an array, create DataFrame with reference column names
            abundance_df = pd.DataFrame(
                abundance,
                index=posterior.obs_names,
                columns=reference_signatures.columns,
            )

        if q05 is not None:
            if isinstance(q05, pd.DataFrame):
                # Extract cell type names from column names
                q05_df = q05.copy()
                new_cols = []
                for col in q05_df.columns:
                    for prefix in ["q05cell_abundance_w_sf_", "q05_cell_abundance_w_sf_"]:
                        if col.startswith(prefix):
                            new_cols.append(col[len(prefix):])
                            break
                    else:
                        new_cols.append(col)
                q05_df.columns = new_cols
                q05_df.index = posterior.obs_names
            else:
                q05_df = pd.DataFrame(
                    q05, index=posterior.obs_names, columns=reference_signatures.columns
                )
        else:
            q05_df = None

        total_per_loc = abundance_df.sum(axis=1).values

        h5ad_id = f"{uuid.uuid4()}.h5ad"
        abundance_id = f"{uuid.uuid4()}.csv"
        stats_id = f"{uuid.uuid4()}.json"

        result_h5ad_path = os.path.join(OUTPUT_DIR, h5ad_id)
        abundance_path = os.path.join(OUTPUT_DIR, abundance_id)
        stats_path = os.path.join(OUTPUT_DIR, stats_id)

        posterior.write_h5ad(result_h5ad_path)
        abundance_df.to_csv(abundance_path)

        stats["total_cells_per_location_summary"] = {
            "min": float(np.min(total_per_loc)) if total_per_loc.size else None,
            "max": float(np.max(total_per_loc)) if total_per_loc.size else None,
            "mean": float(np.mean(total_per_loc)) if total_per_loc.size else None,
            "median": float(np.median(total_per_loc)) if total_per_loc.size else None,
        }

        if q05_df is not None:
            q05_id = f"{uuid.uuid4()}.csv"
            q05_path = os.path.join(OUTPUT_DIR, q05_id)
            q05_df.to_csv(q05_path)
        else:
            q05_id = None

        with open(stats_path, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)

        qc_png_id = _plot_abundance_sum(total_per_loc, OUTPUT_DIR)

        data_dict: Dict[str, Any] = {
            "cell2location_results.h5ad": h5ad_id,
            "cell_abundance.csv": abundance_id,
            "run_stats.json": stats_id,
        }
        if q05_id:
            data_dict["cell_abundance_q05.csv"] = q05_id
        if qc_png_id:
            data_dict["abundance_qc.png"] = qc_png_id

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "cell2location 去卷积完成",
                "data": data_dict,
            },
        )
    except Exception as e:
        logger.error("cell2location 去卷积失败: %s", e, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": "cell2location 去卷积失败",
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
        "cell2location_available": C2L_AVAILABLE,
        "output_dir": OUTPUT_DIR,
    }


if __name__ == "__main__":
    import uvicorn

    _port = int(os.getenv("PORT", 60910))
    uvicorn.run(app, host="0.0.0.0", port=_port)


