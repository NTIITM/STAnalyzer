#!/usr/bin/env python3
"""
Giotto-CPDB Spatial Interaction Service
"""
from __future__ import annotations

import logging
import os
import tempfile
import traceback
import uuid
from collections import defaultdict
from logging.handlers import RotatingFileHandler
from typing import Any, DefaultDict, Dict, List, Literal, Optional, Tuple

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse

try:
    import anndata as ad
    import numpy as np
    import pandas as pd
    import seaborn as sns
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    BIO_AVAILABLE = True
except Exception as exc:  # pragma: no cover
    logging.error("Dependency import failed: %s", exc)
    BIO_AVAILABLE = False

# 导入数据库模块
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from database import filter_available_pairs
from utils.r_plotting import plot_heatmap


def _setup_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_dir = os.getenv("LOG_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "log"))
    os.makedirs(log_dir, exist_ok=True)
    path = os.path.join(log_dir, "giotto_cpdb.log")
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handlers = [
        RotatingFileHandler(path, maxBytes=5 * 1024 * 1024, backupCount=3),
        logging.StreamHandler(),
    ]
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = []
    for handler in handlers:
        handler.setFormatter(formatter)
        root.addHandler(handler)


_setup_logging()
LOGGER = logging.getLogger("giotto-cpdb-service")

app = FastAPI(
    title="Giotto-CPDB Spatial Interaction Service",
    version="1.0.0",
    description="Combines spatial neighborhood with ligand-receptor expression to output Giotto/CPDB-style significant interactions and z-scores.",
)

OUTPUT_DIR = os.getenv("OUTPUT_DIR", os.path.join(os.path.dirname(__file__), "outputs"))
os.makedirs(OUTPUT_DIR, exist_ok=True)


def _format_error_info_to_message(error_info: Dict[str, Any]) -> str:
    """Format the error_info dictionary into a readable string message (aligned with preprocessing service style)"""
    parts: List[str] = []
    parts.append(f"Error Type: {error_info.get('error_type', 'Unknown')}")
    parts.append(f"Error Message: {error_info.get('error_message', 'Unknown error')}")

    if "diagnosis" in error_info:
        parts.append(f"\nDiagnosis: {error_info['diagnosis']}")

    if "suggestions" in error_info and error_info["suggestions"]:
        parts.append("\nSuggestions:")
        for idx, suggestion in enumerate(error_info["suggestions"], 1):
            if isinstance(suggestion, dict):
                issue = suggestion.get("issue", "Unknown issue")
                recommendations = suggestion.get("recommendations", [])
                parts.append(f"\n  {idx}. {issue}:")
                for rec in recommendations:
                    parts.append(f"     - {rec}")

    if "traceback" in error_info:
        parts.append(f"\nTraceback:\n{error_info['traceback']}")

    return "\n".join(parts)


def _handle_error(step: str, error: Exception, include_traceback: bool = True) -> Dict[str, Any]:
    """Unified error handling, providing more detailed diagnosis and suggestions (referencing spatial-transcriptomics-preprocessing)"""
    error_info: Dict[str, Any] = {
        "error": True,
        "step": step,
        "error_type": type(error).__name__,
        "error_message": str(error),
        "suggestions": [],
    }
    if include_traceback:
        error_info["traceback"] = traceback.format_exc()

    msg_lower = str(error).lower()
    if "groupby" in msg_lower and ("required" in msg_lower or "not found" in msg_lower):
        error_info["diagnosis"] = "Invalid or missing 'groupby' parameter"
        error_info["suggestions"].append(
            {
                "issue": "'groupby' column is missing or incorrectly specified",
                "recommendations": [
                    "Ensure the 'groupby' parameter is provided and is a valid column name in your AnnData object's .obs.columns",
                    "Check for typos in the 'groupby' parameter",
                    "Verify that the input data contains the specified 'groupby' column",
                ],
            }
        )
    elif "file" in msg_lower or "read" in msg_lower or "format" in msg_lower:
        error_info["diagnosis"] = "File reading or format issue"
        error_info["suggestions"].append(
            {
                "issue": "File format mismatch or file corrupted",
                "recommendations": [
                    "Check if file format is correct (supported formats: h5ad, csv, tsv)",
                    "Try explicitly specifying the file_type parameter",
                    "Ensure the file is not corrupted and uploaded completely",
                    "Check file encoding for CSV/TSV files (UTF-8 recommended)",
                ],
    }
        )
    elif "interaction" in msg_lower and "not found" in msg_lower or "empty" in msg_lower and "interactions" in msg_lower:
        error_info["diagnosis"] = "No interactions found above the specified thresholds."
        error_info["suggestions"].append(
            {
                "issue": "No significant interactions detected",
                "recommendations": [
                    "Try reducing 'min_expr' threshold to include more interactions",
                    "Try reducing 'pval_threshold' to include more interactions",
                    "Check that cluster labels are present in the data and that the 'groupby' parameter is correctly specified",
                    "Verify ligand-receptor pairs are available in the expression matrix and that genes are correctly named",
                ],
            }
        )
    if not error_info["suggestions"]:
        error_info["suggestions"].append(
            {
                "issue": "Unknown error",
                "recommendations": [
                    "Check input data format and content",
                    "Verify all parameter values are reasonable",
                    "Review detailed error stack trace for more clues",
                    "Ensure that `groupby` parameter is correctly specified and exists in `adata.obs.columns`",
                ],
            }
        )

    LOGGER.error("Step %s failed: %s", step, error, exc_info=True)
    return error_info


def _read_adata(path: str, file_type: Literal["auto", "h5ad", "csv", "tsv"]) -> "ad.AnnData":
    if file_type == "auto":
        if path.endswith(".h5ad"):
            file_type = "h5ad"
        elif path.endswith(".tsv"):
            file_type = "tsv"
        else:
            file_type = "csv"
    if file_type == "h5ad":
        return ad.read_h5ad(path)
    if file_type in {"csv", "tsv"}:
        sep = "," if file_type == "csv" else "\t"
        df = pd.read_csv(path, sep=sep, index_col=0)
        return ad.AnnData(X=df.values, obs=pd.DataFrame(index=df.index), var=pd.DataFrame(index=df.columns))
    raise ValueError(f"Unsupported file_type: {file_type}")


def _ensure_groupby(adata: "ad.AnnData", groupby: Optional[str]) -> str:
    if groupby is None:
        raise HTTPException(
            status_code=400,
            detail=_format_error_info_to_message(
                _handle_error(
                    "_ensure_groupby",
                    ValueError("'groupby' parameter is required and cannot be empty."),
                    include_traceback=False,
                )
            ),
        )
    if groupby not in adata.obs.columns:
        raise HTTPException(
            status_code=400,
            detail=_format_error_info_to_message(
                _handle_error(
                    "_ensure_groupby",
                    ValueError(f"Specified groupby column '{groupby}' not found in data."),
                    include_traceback=False,
                )
            ),
        )
    return groupby


def _extract_coords(adata: "ad.AnnData", spatial_key: Optional[str]) -> Optional[pd.DataFrame]:
    if spatial_key and spatial_key in adata.obsm:
        coords = adata.obsm[spatial_key]
        if coords.shape[1] >= 2:
            return pd.DataFrame(coords[:, :2], columns=["x", "y"], index=adata.obs_names)
    if {"x", "y"}.issubset(adata.obs.columns):
        return adata.obs[["x", "y"]]
    return None


def _compute_centroids_and_dist(adata: "ad.AnnData", groupby: str, spatial_key: Optional[str]) -> Optional[pd.DataFrame]:
    coords = _extract_coords(adata, spatial_key)
    if coords is None:
        return None
    coords = coords.copy()
    coords["group"] = adata.obs[groupby].astype(str).values
    centroids = coords.groupby("group")[["x", "y"]].mean()
    arr = centroids.to_numpy()
    diff = arr[:, None, :] - arr[None, :, :]
    dist = np.sqrt((diff ** 2).sum(axis=2))
    return pd.DataFrame(dist, index=centroids.index, columns=centroids.index)


def _filter_lr(group_means: pd.DataFrame) -> List[Dict[str, str]]:
    """Query and filter ligand-receptor pairs from the database"""
    available_genes = group_means.columns.tolist()
    filtered = filter_available_pairs(available_genes)
    
    # Convert to format required by the service
    result = []
    for pair in filtered:
        result.append({
            "ligand": pair.get("ligand", ""),
            "receptor": pair.get("receptor", ""),
        })
    
    return result


def _score_observed(
    group_means: pd.DataFrame,
    dist_df: Optional[pd.DataFrame],
    lr_pairs: List[Dict[str, str]],
    min_expr: float,
    spatial_radius: float,
) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    groups = group_means.index.tolist()
    for entry in lr_pairs:
        ligand_vec = group_means[entry["ligand"]]
        receptor_vec = group_means[entry["receptor"]]
        for sender in groups:
            lig_expr = float(ligand_vec.loc[sender])
            if lig_expr < min_expr:
                continue
            for receiver in groups:
                rec_expr = float(receptor_vec.loc[receiver])
                if rec_expr < min_expr:
                    continue
                spatial_weight = 1.0
                if dist_df is not None:
                    distance = float(dist_df.loc[sender, receiver])
                    spatial_weight = float(np.exp(-distance / max(spatial_radius, 1e-6)))
                score = lig_expr * rec_expr * spatial_weight
                rows.append(
                    {
                        "sender": sender,
                        "receiver": receiver,
                        "ligand": entry["ligand"],
                        "receptor": entry["receptor"],
                        "expr_score": lig_expr * rec_expr,
                        "spatial_weight": spatial_weight,
                        "score": score,
                    }
                )
    return pd.DataFrame(rows)


def _permutation_scores(
    expr_df: pd.DataFrame,
    groupby: str,
    lr_pairs: List[Dict[str, str]],
    spatial_scores: Dict[Tuple[str, str], float],
    groups: List[str],
    n_permutations: int,
    seed: int,
) -> DefaultDict[Tuple[str, str, str, str], List[float]]:
    rng = np.random.default_rng(seed)
    rows: DefaultDict[Tuple[str, str, str, str], List[float]] = defaultdict(list)
    labels = expr_df[groupby].values.astype(str)
    expr_only = expr_df.drop(columns=[groupby]).copy()
    for _ in range(n_permutations):
        shuffled = rng.permutation(labels)
        expr_only[groupby] = shuffled
        perm_means = expr_only.groupby(groupby).mean().reindex(groups).fillna(0.0)
        for entry in lr_pairs:
            ligand_vec = perm_means[entry["ligand"]]
            receptor_vec = perm_means[entry["receptor"]]
            for sender in groups:
                for receiver in groups:
                    expr_score = float(ligand_vec.loc[sender] * receptor_vec.loc[receiver])
                    spatial_weight = spatial_scores.get((sender, receiver), 1.0)
                    rows[(entry["ligand"], entry["receptor"], sender, receiver)].append(expr_score * spatial_weight)
    return rows


def _compute_zscores(
    observed: pd.DataFrame,
    perm_scores: DefaultDict[Tuple[str, str, str, str], List[float]],
) -> pd.DataFrame:
    if observed.empty:
        return observed
    pvals: List[float] = []
    zscores: List[float] = []
    for row in observed.itertuples():
        key = (row.ligand, row.receptor, row.sender, row.receiver)
        null = perm_scores.get(key, [])
        if not null:
            pvals.append(1.0)
            zscores.append(0.0)
            continue
        null_arr = np.asarray(null)
        mean = null_arr.mean()
        std = null_arr.std(ddof=1) if len(null_arr) > 1 else 1.0
        z = (row.score - mean) / (std or 1.0)
        greater = (null_arr >= row.score).sum()
        pval = (greater + 1) / (len(null_arr) + 1)
        pvals.append(float(pval))
        zscores.append(float(z))
    observed = observed.copy()
    observed["zscore"] = zscores
    observed["pvalue"] = pvals
    observed["adjusted_p"] = np.minimum(1.0, observed["pvalue"] * len(observed))
    observed.sort_values(by="zscore", ascending=False, inplace=True)
    return observed


def _write_placeholder_plot(path: str, title: str, message: str) -> str:
    plt.figure(figsize=(6, 3))
    plt.axis("off")
    plt.title(title, fontsize=12)
    plt.text(0.5, 0.5, message, ha="center", va="center", fontsize=11, wrap=True)
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()
    return path


def _plot_heatmap(df: pd.DataFrame, filename: str) -> str:
    """Plots a heatmap, with filename as full filename (UUID+extension), aligned with other service download methods."""
    path = os.path.join(OUTPUT_DIR, filename)
    if df.empty:
        LOGGER.warning("Giotto-CPDB heatmap data is empty, generating a placeholder plot.")
        return _write_placeholder_plot(
            path,
            "Giotto-CPDB Heatmap",
            "No visualization data available, placeholder generated.",
        )
    pivot = df.pivot_table(
        index="sender",
        columns="receiver",
        values="zscore",
        aggfunc="max",
        fill_value=0.0,
    )
    try:
        result = plot_heatmap(
            pivot,
            path,
            "Giotto-CPDB z-score map",
            colormap="coolwarm",
            width=max(4, pivot.shape[1] * 0.5),
            height=max(4, pivot.shape[0] * 0.5),
        )
    except Exception as exc:  # pragma: no cover
        LOGGER.error("Giotto-CPDB heatmap plotting failed: %s", exc, exc_info=True)
        result = None
    final_path = result or path
    if not os.path.exists(final_path):
        LOGGER.warning("Giotto-CPDB heatmap file missing, generating a placeholder plot.")
        final_path = _write_placeholder_plot(
            path,
            "Giotto-CPDB Heatmap",
            "Plotting failed, placeholder generated.",
        )
    return final_path


def _write_summary(df: pd.DataFrame, params: Dict[str, Any], filename: str) -> str:
    """Writes a summary file with detailed statistics."""
    lines = ["=" * 60, "Giotto-CPDB Summary Report", "=" * 60]
    lines.append("\nAnalysis Parameters:")
    for key, value in params.items():
        lines.append(f"- {key}: {value}")
    lines.append("\nSummary Statistics:")
    if df.empty:
        lines.append("No significant interactions found.")
    else:
        lines.append(f"Total significant interactions: {len(df)}")
        lines.append("Top 10 Interactions (sorted by z-score):")
        for row in df.head(10).itertuples():
            lines.append(
                f"- {row.sender}->{row.receiver} {row.ligand}-{row.receptor} "
                f"(z={row.zscore:.2f}, p={row.pvalue:.4f}, adj.p={row.adjusted_p:.4f})"
            )
    summary_path = os.path.join(OUTPUT_DIR, filename)
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return summary_path


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    LOGGER.error("Invalid parameters: %s", exc, exc_info=True)
    return JSONResponse(status_code=422, content={"success": False, "message": "Invalid parameters", "error": exc.errors()})


@app.exception_handler(Exception)
async def general_handler(request: Request, exc: Exception) -> JSONResponse:
    LOGGER.error("Unhandled exception: %s", exc, exc_info=True)
    return JSONResponse(status_code=500, content={"success": False, "message": "Internal server error", "error": _handle_error("server", exc)})


@app.post("/api/giotto-cpdb")
async def run_giotto_cpdb(
    file: UploadFile = File(...),
    file_type: Literal["auto", "h5ad", "csv", "tsv"] = Form("auto"),
    spatial_key: Optional[str] = Form("spatial"),
    min_expr: float = Form(0.05),
    spatial_radius: float = Form(30.0),
    n_permutations: int = Form(100),
    pval_threshold: float = Form(0.05),
    groupby: Optional[str] = Form(None),
) -> JSONResponse:
    if not BIO_AVAILABLE:
        raise HTTPException(status_code=500, detail="Dependencies missing")
    temp_path: Optional[str] = None
    try:
        # Each upload task has a top-level ID for logging only; actual output files have independent UUIDs
        request_id = str(uuid.uuid4())
        tmp_fd, temp_path = tempfile.mkstemp(
            prefix=f"giotto_cpdb_{request_id}_",
            suffix=os.path.splitext(file.filename or "")[-1],
        )
        with os.fdopen(tmp_fd, "wb") as tmp_file:
            tmp_file.write(await file.read())
        LOGGER.info("Giotto-CPDB Request %s: Input file saved to temporary path %s", request_id, temp_path)
        adata = _read_adata(temp_path, file_type)
        group_key = _ensure_groupby(adata, groupby)
        dist_df = _compute_centroids_and_dist(adata, group_key, spatial_key)
        expr = adata.to_df()
        expr[group_key] = adata.obs[group_key].astype(str).values
        group_means = expr.groupby(group_key).mean()
        lr_pairs = _filter_lr(group_means)
        observed = _score_observed(group_means, dist_df, lr_pairs, min_expr, spatial_radius)
        if observed.empty:
            raise HTTPException(status_code=400, detail=_format_error_info_to_message(_handle_error("giotto_cpdb", ValueError("No interactions found above the specified thresholds."), include_traceback=False)))
        spatial_scores = {
            (row.sender, row.receiver): row.spatial_weight for row in observed.itertuples()
        }
        perm_scores = _permutation_scores(
            expr,
            group_key,
            lr_pairs,
            spatial_scores,
            group_means.index.tolist(),
            max(10, min(500, n_permutations)),
            seed=42,
        )
        observed = _compute_zscores(observed, perm_scores)
        significant = observed[observed["pvalue"] <= pval_threshold].copy()
        
        # Generate independent UUIDs for each output file (aligned with spatial-transcriptomics-preprocessing)
        results_id = f"{uuid.uuid4()}.csv"
        results_path = os.path.join(OUTPUT_DIR, results_id)
        observed.to_csv(results_path, index=False)
        
        sig_id = f"{uuid.uuid4()}.csv"
        sig_path = os.path.join(OUTPUT_DIR, sig_id)
        significant.to_csv(sig_path, index=False)
        
        plot_id = f"{uuid.uuid4()}.png"
        _plot_heatmap(observed, plot_id)
        
        summary_id = f"{uuid.uuid4()}.txt"
        summary_path = _write_summary(
            significant if not significant.empty else observed.head(20),
            {
                "groupby": group_key,
                "min_expr": min_expr,
                "spatial_radius": spatial_radius,
                "pval_threshold": pval_threshold,
                "n_permutations": n_permutations,
            },
            summary_id,
        )
        payload = {
            "success": True,
            "message": "Giotto-CPDB style analysis completed successfully",
            "data": {
                # Filename -> unique file_id (UUID+extension) for each file
                "giotto_cpdb_results.csv": results_id,
                "giotto_cpdb_significant.csv": sig_id,
                "giotto_cpdb_heatmap.png": plot_id,
                "giotto_cpdb_summary.txt": summary_id,
            },
        }
        return JSONResponse(status_code=200, content=payload)
    except HTTPException:
        raise
    except Exception as exc:
        # Use consistent error message format with spatial-transcriptomics-preprocessing
        error_info = _handle_error("giotto_cpdb", exc)
        error_message = _format_error_info_to_message(error_info)
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": error_message},
        )
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                LOGGER.warning("Failed to clean up temporary file: %s", temp_path)


@app.get("/api/download/{file_id}")
async def download_file(file_id: str) -> FileResponse:
    """
    Downloads a file by file_id.
    - file_id is the full filename (UUID+extension), aligned with spatial-transcriptomics-preprocessing
    - Looks for the corresponding file directly under OUTPUT_DIR
    """
    path = os.path.join(OUTPUT_DIR, file_id)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"File not found or cleaned up: file_id={file_id}")

    if path.endswith(".csv"):
        media_type = "text/csv"
    elif path.endswith(".png"):
        media_type = "image/png"
    elif path.endswith(".txt"):
        media_type = "text/plain"
    else:
        media_type = "application/octet-stream"

    filename = os.path.basename(path)
    LOGGER.info("Downloading file: %s (file_id=%s)", path, file_id)
    return FileResponse(path, filename=filename, media_type=media_type)


@app.get("/health")
async def health() -> Dict[str, Any]:
    return {"status": "healthy", "bio_available": BIO_AVAILABLE, "output_dir": OUTPUT_DIR}


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    port = int(os.getenv("PORT", "36509"))
    uvicorn.run(app, host="0.0.0.0", port=port)
