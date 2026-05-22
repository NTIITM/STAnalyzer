#!/usr/bin/env python3
"""
scTenifoldpy Virtual Gene Knockout Service
Accepts single-cell h5ad input, runs scTenifoldKnk, and returns perturbation scores.
"""
import os
import uuid
import json
import logging
import traceback
import tempfile
from typing import List, Dict, Any, Tuple, Optional

import numpy as np
import pandas as pd
import anndata as ad
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.exceptions import RequestValidationError
from fastapi.concurrency import run_in_threadpool

try:
    import matplotlib
    matplotlib.use("Agg")  # Use non-interactive backend
    import matplotlib.pyplot as plt
    import seaborn as sns
    HAS_PLOTTING = True
except Exception as e:  # pragma: no cover
    HAS_PLOTTING = False
    PLOTTING_IMPORT_ERROR = str(e)

try:
    from scTenifold import scTenifoldKnk  # type: ignore
    HAS_SCTENIFOLD = True
except Exception as e:  # pragma: no cover - environment dependent
    HAS_SCTENIFOLD = False
    SCTENIFOLD_IMPORT_ERROR = str(e)


def _setup_logging() -> logging.Logger:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_dir = os.getenv("LOG_DIR", os.path.dirname(os.path.abspath(__file__)))
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "service.log")
    fmt = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    logger = logging.getLogger("sctenifoldpy-knockout-service")
    logger.setLevel(level)
    logger.handlers = []
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    sh.setLevel(level)
    fh = logging.FileHandler(log_path)
    fh.setFormatter(fmt)
    fh.setLevel(level)
    logger.addHandler(sh)
    logger.addHandler(fh)
    return logger


logger = _setup_logging()

app = FastAPI(
    title="scTenifoldpy Virtual Gene Knockout",
    description="Virtual gene knockout using scTenifoldpy (scTenifoldKnk)",
    version="0.1.0",
)

OUTPUT_DIR = os.getenv("OUTPUT_DIR", os.path.join(os.path.dirname(__file__), "outputs"))
os.makedirs(OUTPUT_DIR, exist_ok=True)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    error_details = exc.errors()
    body = exc.body if hasattr(exc, "body") else None
    logger.error(
        "Validation failed: %s %s details=%s body=%s",
        request.method,
        request.url.path,
        error_details,
        str(body)[:400],
        exc_info=True,
    )
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "message": "Request parameter validation failed",
            "error": {
                "error_type": "RequestValidationError",
                "error_message": str(exc),
                "details": error_details,
            },
        },
    )


def _read_h5ad_counts(file_path: str, max_genes: int = 3000) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Load h5ad and return genes x cells count matrix plus basic stats."""
    adata = ad.read_h5ad(file_path)
    if hasattr(adata.X, "toarray"):
        expr = adata.X.toarray()
    else:
        expr = np.asarray(adata.X)
    df = pd.DataFrame(expr.T, index=adata.var_names, columns=adata.obs_names)
    stats = {
        "cells": df.shape[1],
        "genes": df.shape[0],
    }
    if df.shape[0] > max_genes:
        # keep top variable genes to stabilize downstream steps
        variances = df.var(axis=1)
        top_genes = variances.sort_values(ascending=False).head(max_genes).index
        df = df.loc[top_genes]
        stats["genes_subsampled_to"] = max_genes
    return df, stats


def _serialize_error(step: str, error: Exception) -> Dict[str, Any]:
    return {
        "step": step,
        "error_type": type(error).__name__,
        "error_message": str(error),
        "traceback": traceback.format_exc(),
        "suggestions": [
            "Confirm scTenifoldpy is installed and compatible with the Python version.",
            "Ensure input h5ad has counts or normalized matrix in .X.",
            "Reduce max_genes if memory usage is high.",
        ],
    }


def _plot_top_genes(result_df: pd.DataFrame, ko_genes: List[str], output_path: str) -> str:
    """
    Generate horizontal bar chart for top 10 up- and down-regulated genes (excluding KO genes).
    
    Args:
        result_df: DataFrame with columns including 'Gene' and 'Z'
        ko_genes: List of knocked-out gene names to exclude
        output_path: Path to save the PNG image
    
    Returns:
        Path to the saved image
    """
    if not HAS_PLOTTING:
        logger.warning("Plotting libraries not available, skipping visualization")
        return output_path
    
    # Filter out KO genes
    ko_set = set(g.upper() for g in ko_genes)
    filtered_df = result_df[~result_df['Gene'].str.upper().isin(ko_set)].copy()
    
    if filtered_df.empty:
        logger.warning("No genes remaining after filtering KO genes")
        # Create placeholder plot
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.text(0.5, 0.5, "No genes to visualize\n(all genes are knocked out)", 
                ha='center', va='center', fontsize=12)
        ax.set_title("Top 10 Up- and Down-regulated Genes (excluding KO genes)")
        ax.axis('off')
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()
        return output_path
    
    # Get top 10 up-regulated (highest Z) and down-regulated (lowest Z)
    top_up = filtered_df.nlargest(10, 'Z')
    top_down = filtered_df.nsmallest(10, 'Z')
    
    # Prepare data for plotting
    up_genes = top_up['Gene'].tolist()
    up_zscores = top_up['Z'].tolist()
    down_genes = top_down['Gene'].tolist()
    down_zscores = top_down['Z'].tolist()
    
    # Reverse order for plotting (top to bottom)
    up_genes = up_genes[::-1]
    up_zscores = up_zscores[::-1]
    down_genes = down_genes[::-1]
    down_zscores = down_zscores[::-1]
    
    # Create figure
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Determine x-axis range
    all_zscores = up_zscores + down_zscores
    z_min = min(all_zscores) if all_zscores else -2.0
    z_max = max(all_zscores) if all_zscores else 2.0
    z_range = z_max - z_min
    x_min = z_min - z_range * 0.1
    x_max = z_max + z_range * 0.1
    
    # Plot up-regulated genes (red bars, positive Z)
    y_pos_up = np.arange(len(up_genes))
    ax.barh(y_pos_up, up_zscores, color='#d62728', alpha=0.8, label='Up-regulated')
    
    # Plot down-regulated genes (blue bars, negative Z)
    y_pos_down = np.arange(len(up_genes), len(up_genes) + len(down_genes))
    ax.barh(y_pos_down, down_zscores, color='#1f77b4', alpha=0.8, label='Down-regulated')
    
    # Set y-axis labels
    all_gene_labels = up_genes + down_genes
    ax.set_yticks(np.arange(len(all_gene_labels)))
    ax.set_yticklabels(all_gene_labels)
    
    # Add vertical line at Z=0
    ax.axvline(x=0, color='black', linestyle='-', linewidth=0.8, alpha=0.5)
    
    # Set labels and title
    ax.set_xlabel('Z-score', fontsize=12)
    ax.set_title('Top 10 Up- and Down-regulated Genes (excluding KO genes)', fontsize=14, fontweight='bold')
    ax.legend(loc='upper right', fontsize=10)
    
    # Set x-axis limits
    ax.set_xlim(x_min, x_max)
    
    # Invert y-axis to show top genes at top
    ax.invert_yaxis()
    
    # Add grid
    ax.grid(axis='x', alpha=0.3, linestyle='--')
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    logger.info("Top genes plot saved to: %s", output_path)
    return output_path


def _write_detailed_summary(
    result_df: pd.DataFrame,
    stats: Dict[str, Any],
    ko_genes: List[str],
    output_path: str,
) -> str:
    """
    Write detailed summary report similar to giotto-cpdb-service format.
    
    Args:
        result_df: DataFrame with knockout results
        stats: Statistics dictionary
        ko_genes: List of knocked-out gene names
        output_path: Path to save the summary file
    
    Returns:
        Path to the saved summary file
    """
    lines = ["=" * 60, "scTenifoldpy Virtual Gene Knockout Analysis Summary", "=" * 60]
    lines.append("")
    
    # Analysis parameters
    lines.append("Analysis Parameters:")
    lines.append("-" * 60)
    for key, value in stats.items():
        if key not in ['cells', 'genes', 'genes_subsampled_to']:
            lines.append(f"  {key}: {value}")
    lines.append("")
    
    # Dataset information
    lines.append("Dataset Information:")
    lines.append("-" * 60)
    lines.append(f"  Number of cells: {stats.get('cells', 'N/A')}")
    lines.append(f"  Number of genes: {stats.get('genes', 'N/A')}")
    if 'genes_subsampled_to' in stats:
        lines.append(f"  Genes subsampled to: {stats.get('genes_subsampled_to', 'N/A')}")
    lines.append("")
    
    # Knockout genes
    lines.append("Knocked-out Genes:")
    lines.append("-" * 60)
    for gene in ko_genes:
        lines.append(f"  - {gene}")
    lines.append("")
    
    # Filter out KO genes for statistics
    ko_set = set(g.upper() for g in ko_genes)
    filtered_df = result_df[~result_df['Gene'].str.upper().isin(ko_set)].copy()
    
    if not filtered_df.empty:
        # Top up-regulated genes
        top_up = filtered_df.nlargest(10, 'Z')
        lines.append("Top 10 Up-regulated Genes (excluding KO genes):")
        lines.append("-" * 60)
        for idx, (_, row) in enumerate(top_up.iterrows(), 1):
            # Use column names directly since they may contain special characters
            pval = row.get('p-value', row.get('p_value', 'N/A'))
            adj_pval = row.get('adjusted p-value', row.get('adjusted_p-value', row.get('adjusted_p_value', 'N/A')))
            if isinstance(pval, (int, float)):
                pval_str = f"{pval:.4e}"
            else:
                pval_str = str(pval)
            if isinstance(adj_pval, (int, float)):
                adj_pval_str = f"{adj_pval:.4e}"
            else:
                adj_pval_str = str(adj_pval)
            gene_name = row.get('Gene', 'N/A')
            z_score = row.get('Z', 0.0)
            fc = row.get('FC', 0.0)
            lines.append(
                f"  {idx:2d}. {gene_name:15s} | Z={z_score:8.3f} | "
                f"FC={fc:8.3f} | p={pval_str} | adj_p={adj_pval_str}"
            )
        lines.append("")
        
        # Top down-regulated genes
        top_down = filtered_df.nsmallest(10, 'Z')
        lines.append("Top 10 Down-regulated Genes (excluding KO genes):")
        lines.append("-" * 60)
        for idx, (_, row) in enumerate(top_down.iterrows(), 1):
            # Use column names directly since they may contain special characters
            pval = row.get('p-value', row.get('p_value', 'N/A'))
            adj_pval = row.get('adjusted p-value', row.get('adjusted_p-value', row.get('adjusted_p_value', 'N/A')))
            if isinstance(pval, (int, float)):
                pval_str = f"{pval:.4e}"
            else:
                pval_str = str(pval)
            if isinstance(adj_pval, (int, float)):
                adj_pval_str = f"{adj_pval:.4e}"
            else:
                adj_pval_str = str(adj_pval)
            gene_name = row.get('Gene', 'N/A')
            z_score = row.get('Z', 0.0)
            fc = row.get('FC', 0.0)
            lines.append(
                f"  {idx:2d}. {gene_name:15s} | Z={z_score:8.3f} | "
                f"FC={fc:8.3f} | p={pval_str} | adj_p={adj_pval_str}"
            )
        lines.append("")
        
        # Summary statistics
        lines.append("Summary Statistics:")
        lines.append("-" * 60)
        lines.append(f"  Total genes analyzed: {len(filtered_df)}")
        lines.append(f"  Mean Z-score: {filtered_df['Z'].mean():.4f}")
        lines.append(f"  Median Z-score: {filtered_df['Z'].median():.4f}")
        lines.append(f"  Std Z-score: {filtered_df['Z'].std():.4f}")
        lines.append(f"  Min Z-score: {filtered_df['Z'].min():.4f}")
        lines.append(f"  Max Z-score: {filtered_df['Z'].max():.4f}")
        
        # Significant genes (adjusted p-value < 0.05)
        adj_p_col = 'adjusted p-value' if 'adjusted p-value' in filtered_df.columns else 'adjusted_p_value'
        sig_genes = filtered_df[filtered_df[adj_p_col] < 0.05] if adj_p_col in filtered_df.columns else pd.DataFrame()
        lines.append(f"  Significant genes (adj_p < 0.05): {len(sig_genes)}")
        
        # Up-regulated significant
        sig_up = sig_genes[sig_genes['Z'] > 0]
        lines.append(f"    - Up-regulated: {len(sig_up)}")
        
        # Down-regulated significant
        sig_down = sig_genes[sig_genes['Z'] < 0]
        lines.append(f"    - Down-regulated: {len(sig_down)}")
    else:
        lines.append("No genes remaining after filtering KO genes.")
    
    lines.append("")
    lines.append("=" * 60)
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    
    logger.info("Detailed summary saved to: %s", output_path)
    return output_path


def _run_virtual_knockout(
    h5ad_path: str,
    ko_genes: List[str],
    n_components: int,
    n_iter: int,
    knn: int,
    qc_min_lib_size: int,
    qc_min_percent: float,
    max_genes: int,
    random_seed: int,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    if not HAS_SCTENIFOLD:
        raise ImportError(f"scTenifoldpy not available: {SCTENIFOLD_IMPORT_ERROR}")

    df, stats = _read_h5ad_counts(h5ad_path, max_genes=max_genes)

    # Set random seed if provided (scTenifoldKnk doesn't accept seed parameter)
    if random_seed is not None:
        np.random.seed(random_seed)

    qc_kws = {"min_lib_size": qc_min_lib_size, "min_percent": qc_min_percent}
    # Note: scTenifold internally uses rank=K for tensor decomposition
    # According to scTenifold documentation, td_kws should not include 'rank' as it's handled internally
    # n_components parameter may be used internally by scTenifold, but is not directly passed to scTenifoldKnk
    # td_kws can include other tensor decomposition parameters like n_iter_max, tol, etc.
    td_kws = {}  # scTenifold handles rank/K internally; n_components may be used but not directly configurable
    ma_kws = {"n_neighbors": knn}  # ma_kws for manifold alignment
    dr_kws = {"n_iter": n_iter}  # dr_kws for dimension reduction/alignment

    model = scTenifoldKnk(
        data=df,
        ko_genes=ko_genes,
        qc_kws=qc_kws,
        td_kws=td_kws,
        ma_kws=ma_kws,
        dr_kws=dr_kws,
    )
    result = model.build()

    result_df: Optional[pd.DataFrame] = None
    if isinstance(result, pd.DataFrame):
        result_df = result
    elif isinstance(result, dict):
        for val in result.values():
            if isinstance(val, pd.DataFrame):
                result_df = val
                break
    if result_df is None:
        raise ValueError("scTenifoldpy returned unexpected result type; expected DataFrame or dict of DataFrames.")

    stats.update(
        {
            "ko_genes": ",".join(ko_genes),
            "n_components": n_components,
            "n_iter": n_iter,
            "knn": knn,
            "random_seed": random_seed,
        }
    )
    return result_df, stats


@app.post("/api/virtual-knockout")
async def virtual_knockout(
    file: UploadFile = File(..., description="h5ad file"),
    ko_genes: str = Form(..., description="Comma-separated gene symbols to knock out"),
    n_components: int = Form(20),
    n_iter: int = Form(3),
    knn: int = Form(5),
    qc_min_lib_size: int = Form(10),
    qc_min_percent: float = Form(0.001),
    max_genes: int = Form(3000),
    random_seed: int = Form(1),
) -> JSONResponse:
    """
    Virtual gene knockout analysis endpoint.
    
    Returns JSONResponse with success status, message, and data dictionary containing file IDs.
    Files can be downloaded using /api/download/{file_id} endpoint.
    """
    temp_path = None
    try:
        # Save uploaded file to temporary location
        temp_fd, temp_path = tempfile.mkstemp(
            prefix="sctenifold_knockout_",
            suffix=os.path.splitext(file.filename or "")[-1] or ".h5ad",
        )
        with os.fdopen(temp_fd, "wb") as tmp_file:
            tmp_file.write(await file.read())
        logger.info("Input file saved to temporary path: %s", temp_path)

        genes = [g.strip() for g in ko_genes.split(",") if g.strip()]
        if not genes:
            raise HTTPException(status_code=400, detail="ko_genes is required and must contain at least one gene")

        # Run virtual knockout analysis
        result_df, stats = await run_in_threadpool(
            _run_virtual_knockout,
            temp_path,
            genes,
            n_components,
            n_iter,
            knn,
            qc_min_lib_size,
            qc_min_percent,
            max_genes,
            random_seed,
        )

        # Generate file IDs (UUID + extension) for each output file
        results_id = f"{uuid.uuid4()}.csv"
        results_path = os.path.join(OUTPUT_DIR, results_id)
        result_df.to_csv(results_path, index=False)
        logger.info("Results saved to: %s", results_path)

        # Generate top genes visualization
        plot_id = f"{uuid.uuid4()}.png"
        plot_path = os.path.join(OUTPUT_DIR, plot_id)
        _plot_top_genes(result_df, genes, plot_path)
        logger.info("Top genes plot saved to: %s", plot_path)

        # Generate detailed summary
        summary_id = f"{uuid.uuid4()}.txt"
        summary_path = os.path.join(OUTPUT_DIR, summary_id)
        _write_detailed_summary(result_df, stats, genes, summary_path)
        logger.info("Detailed summary saved to: %s", summary_path)

        # Return JSONResponse matching other services' format
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Virtual gene knockout analysis completed",
                "data": {
                    "knockout_results.csv": results_id,
                    "top_genes_plot.png": plot_id,
                    "summary.txt": summary_id,
                },
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        error_info = _serialize_error("virtual_knockout", e)
        logger.error("Virtual knockout failed: %s", error_info, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"Virtual knockout analysis failed: {str(e)}",
                "error": error_info,
            },
        )
    finally:
        # Clean up temporary file
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                logger.warning("Failed to remove temporary file: %s", temp_path)


@app.get("/api/download/{file_id}")
async def download_file(file_id: str) -> FileResponse:
    """
    Download result files by file_id.
    
    file_id: UUID + extension (e.g., "123e4567-e89b-12d3-a456-426614174000.csv")
    Returns the file content or 404 if file not found.
    """
    file_path = os.path.join(OUTPUT_DIR, file_id)
    
    if not os.path.exists(file_path):
        logger.warning("File not found: file_id=%s", file_id)
        raise HTTPException(
            status_code=404,
            detail=f"File not found or expired: file_id={file_id}"
        )
    
    # Determine media type based on file extension
    if file_path.endswith(".csv"):
        media_type = "text/csv"
    elif file_path.endswith(".txt"):
        media_type = "text/plain"
    elif file_path.endswith(".png"):
        media_type = "image/png"
    elif file_path.endswith(".json"):
        media_type = "application/json"
    else:
        media_type = "application/octet-stream"
    
    filename = os.path.basename(file_path)
    logger.info("Downloading file: %s (file_id=%s)", file_path, file_id)
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type=media_type
    )


@app.get("/health")
async def health() -> Dict[str, Any]:
    """Health check endpoint"""
    return {
        "status": "healthy",
        "has_scTenifoldpy": HAS_SCTENIFOLD,
        "output_dir": OUTPUT_DIR,
    }

