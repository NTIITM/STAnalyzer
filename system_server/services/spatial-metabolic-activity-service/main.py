#!/usr/bin/env python3
"""Spatial metabolic pathway activity service (pure Python, gseapy ssGSEA)."""
from __future__ import annotations

import logging
import os
import tempfile
import traceback
import uuid
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

try:
    import anndata as ad
    import gseapy as gp
    import networkx as nx
    from matplotlib import pyplot as plt
    from sklearn.neighbors import NearestNeighbors, radius_neighbors_graph
    # squidpy has zarr version conflicts, skip it since it's not used in code
    # import squidpy as sq  # noqa: F401 - ensures dependency availability

    BIO_AVAILABLE = True
except Exception as exc:  # pragma: no cover
    logging.error("Failed to import bioinformatics dependencies: %s", exc)
    BIO_AVAILABLE = False


def _setup_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_dir = os.getenv("LOG_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "log"))
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "spatial_metabolic_activity.log")
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handlers = [logging.StreamHandler(), logging.FileHandler(log_path)]
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = []
    for handler in handlers:
        handler.setFormatter(formatter)
        root.addHandler(handler)


_setup_logging()
LOGGER = logging.getLogger("spatial-metabolic-activity-service")

OUTPUT_DIR = os.getenv("OUTPUT_DIR", os.path.join(os.path.dirname(__file__), "outputs"))
os.makedirs(OUTPUT_DIR, exist_ok=True)

# GMT 文件目录（本地基因集库）
GMT_DIR = os.getenv("GMT_DIR", os.path.join(os.path.dirname(__file__), "gmt"))
os.makedirs(GMT_DIR, exist_ok=True)

# 是否优先使用本地文件（环境变量控制）
USE_LOCAL_FIRST = os.getenv("USE_LOCAL_GMT", "true").lower() == "true"

def _make_output_name(ext: str) -> str:
    """Return a unique filename with the given extension."""
    suffix = ext.lstrip(".")
    return f"{uuid.uuid4()}.{suffix}"

app = FastAPI(title="Spatial Metabolic Activity Service", version="1.0.0")


def _handle_error(step: str, error: Exception, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Return structured error info with lightweight suggestions for the client."""
    msg_lower = str(error).lower()
    suggestions: List[Dict[str, Any]] = []

    if "gene set" in msg_lower or "library" in msg_lower or "enrichr" in msg_lower:
        suggestions.append(
            {
                "issue": "Gene set library unavailable",
                "recommendations": [
                    "Use supported presets: msigdb_hallmark_kegg, msigdb_hallmark, kegg, reactome",
                    "Ensure species is human or mouse (mapped to Human/Mouse for gseapy)",
                    "Confirm the service can reach Enrichr/gseapy endpoints (requires network access)",
                ],
            }
        )
    elif "spatial" in msg_lower and "coordinate" in msg_lower:
        suggestions.append(
            {
                "issue": "Missing spatial coordinates",
                "recommendations": [
                    "Provide obsm['spatial'] with at least two columns, or obs columns named x and y",
                    "Check spatial_key parameter matches the obsm key in the AnnData object",
                ],
            }
        )
    elif "cluster" in msg_lower:
        suggestions.append(
            {
                "issue": "Missing cluster labels",
                "recommendations": [
                    "Check that the cluster_key parameter matches an existing obs column in the AnnData object",
                    "Ensure the specified obs column contains cluster IDs",
                ],
            }
        )

    error_info: Dict[str, Any] = {
        "step": step,
        "error_type": type(error).__name__,
        "error_message": str(error),
        "traceback": traceback.format_exc(),
        "suggestions": suggestions,
    }
    if context:
        error_info["context"] = context
    return error_info


def _format_error_message(error_info: Dict[str, Any]) -> str:
    """Compact human-readable error summary."""
    parts = [
        f"{error_info.get('step', 'processing')} failed: {error_info.get('error_type')}: {error_info.get('error_message')}"
    ]
    context = error_info.get("context") or {}
    if context:
        ctx_str = ", ".join(f"{k}={v}" for k, v in context.items())
        parts.append(f"context: {ctx_str}")
    if error_info.get("suggestions"):
        recs = []
        for item in error_info["suggestions"]:
            issue = item.get("issue", "issue")
            for rec in item.get("recommendations", []):
                recs.append(f"{issue}: {rec}")
        if recs:
            parts.append("suggestions: " + "; ".join(recs))
    return " | ".join(parts)


def _read_adata(path: str, file_type: str) -> "ad.AnnData":
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


def _get_coords(adata: "ad.AnnData", spatial_key: str) -> np.ndarray:
    if spatial_key in adata.obsm:
        coords = np.asarray(adata.obsm[spatial_key])
        if coords.shape[1] >= 2:
            return coords[:, :2]
    if {"x", "y"}.issubset(adata.obs.columns):
        return adata.obs[["x", "y"]].to_numpy()
    raise ValueError(f"Spatial coordinates not found: require obsm['{spatial_key}'] or obs[['x','y']].")


def _get_clusters(adata: "ad.AnnData", cluster_key: str) -> Tuple[pd.Series, str]:
    if cluster_key in adata.obs:
        return adata.obs[cluster_key].astype(str), cluster_key
    raise ValueError(f"Cluster labels not found: expected obs column '{cluster_key}'.")


def _build_graph(coords: np.ndarray, knn_k: int, radius: Optional[float]) -> nx.Graph:
    if radius:
        adj = radius_neighbors_graph(coords, radius=radius, mode="distance", include_self=False).toarray()
    else:
        nn = NearestNeighbors(n_neighbors=knn_k + 1).fit(coords)
        dist, idx = nn.kneighbors(coords)
        rows = []
        cols = []
        data = []
        for drow, irow in zip(dist, idx):
            for d, j in zip(drow[1:], irow[1:]):
                rows.append(irow[0])
                cols.append(j)
                data.append(d)
        adj = np.zeros((coords.shape[0], coords.shape[0]))
        adj[rows, cols] = data
    G = nx.from_numpy_array(adj)
    return G


def _smooth_scores(scores: pd.DataFrame, graph: nx.Graph, sigma: float) -> pd.DataFrame:
    mat = scores.to_numpy()
    smoothed = []
    for i in range(graph.number_of_nodes()):
        neighbors = list(graph.neighbors(i))
        if not neighbors:
            smoothed.append(mat[i])
            continue
        weights = np.exp(-1.0 / max(sigma, 1e-6)) * np.ones(len(neighbors))
        weights = weights / weights.sum()
        smoothed.append(np.average(mat[neighbors], axis=0, weights=weights))
    smoothed_arr = np.vstack(smoothed)
    smoothed_df = pd.DataFrame(smoothed_arr, index=scores.index, columns=scores.columns)
    return smoothed_df


def _load_gmt_file(library_name: str) -> Optional[Dict[str, List[str]]]:
    """
    从本地 GMT 文件加载基因集库
    
    Args:
        library_name: 基因集库名称（不含 .gmt 扩展名）
    
    Returns:
        基因集字典，如果文件不存在则返回 None
    """
    gmt_file = os.path.join(GMT_DIR, f"{library_name}.gmt")
    if not os.path.exists(gmt_file):
        return None
    
    try:
        gene_sets: Dict[str, List[str]] = {}
        with open(gmt_file, 'r', encoding='utf-8') as f:
            for line in f:
                parts = line.strip().split('\t')
                if len(parts) < 3:
                    continue
                term = parts[0]
                # GMT 格式: term_name\tdescription\tgene1\tgene2\t...
                genes = [g.strip() for g in parts[2:] if g.strip()]
                if genes:
                    gene_sets[term] = genes
        LOGGER.info(f"成功从本地文件加载基因集库: {library_name} ({len(gene_sets)} 个基因集)")
        return gene_sets
    except Exception as exc:
        LOGGER.warning(f"读取本地 GMT 文件失败 {gmt_file}: {exc}")
        return None


def _load_gene_sets(gene_set_library: str, species: str) -> Dict[str, List[str]]:
    # Normalize species for gseapy ("Human"/"Mouse" work; other strings are passed through)
    species_norm = "Human" if species.lower().startswith("human") else "Mouse" if species.lower().startswith("mouse") else species
    is_mouse = species_norm.lower().startswith("mouse")

    hallmark_lib = "MSigDB_Hallmark_2020"
    kegg_lib = "KEGG_2019_Mouse" if is_mouse else "KEGG_2021_Human"
    reactome_lib = "Reactome_2022"

    if gene_set_library == "msigdb_hallmark_kegg":
        libraries = [hallmark_lib, kegg_lib]
    elif gene_set_library == "msigdb_hallmark":
        libraries = [hallmark_lib]
    elif gene_set_library == "kegg":
        libraries = [kegg_lib]
    elif gene_set_library == "reactome":
        libraries = [reactome_lib]
    else:
        raise ValueError("Custom gene sets not provided; please supply a GMT path in future extension.")

    gene_sets: Dict[str, List[str]] = {}
    use_local = USE_LOCAL_FIRST
    
    for lib in libraries:
        loaded = False
        
        # 尝试从本地文件加载
        if use_local:
            local_gene_sets = _load_gmt_file(lib)
            if local_gene_sets:
                gene_sets.update(local_gene_sets)
                loaded = True
        
        # 如果本地加载失败，尝试在线获取
        if not loaded:
            try:
                LOGGER.info(f"从在线源加载基因集库: {lib}")
                gs = gp.get_library(name=lib, organism=species_norm)
                gene_sets.update(gs)
                loaded = True
            except Exception as exc:
                # 如果在线获取失败，且本地文件也不可用，抛出异常
                if not use_local or not _load_gmt_file(lib):
                    raise RuntimeError(
                        f"Failed to load gene set library '{lib}' for species '{species_norm}'. "
                        f"Tried both local file and online source. "
                        f"Available examples: MSigDB_Hallmark_2020, KEGG_2021_Human, Reactome_2022."
                    ) from exc
                # 如果在线失败但本地可用，使用本地文件
                LOGGER.warning(f"在线加载失败，使用本地文件: {lib}")
                local_gene_sets = _load_gmt_file(lib)
                if local_gene_sets:
                    gene_sets.update(local_gene_sets)
                    loaded = True
    
    if not gene_sets:
        raise RuntimeError(f"No gene sets loaded for library '{gene_set_library}'")
    
    return gene_sets


def _run_ssgsea(
    adata: "ad.AnnData",
    gene_sets: Dict[str, List[str]],
    min_size: int,
    max_size: int,
    chunk_size: int,
) -> pd.DataFrame:
    expr = pd.DataFrame(adata.X.toarray() if hasattr(adata.X, "toarray") else adata.X, index=adata.obs_names, columns=adata.var_names)
    threads = max(1, min(8, max(1, chunk_size // 100)))
    res = gp.ssgsea(
        data=expr.T,  # genes x samples
        gene_sets=gene_sets,
        min_size=min_size,
        max_size=max_size,
        sample_norm_method="rank",
        processes=1,
        permutation_num=0,
        outdir=None,
        no_plot=True,
        threads=threads,
    )

    res_df = res.res2d
    # Recent gseapy versions return long-form columns [Name, Term, ES, NES]; pivot to samples x pathways.
    if {"Name", "Term", "NES"}.issubset(res_df.columns):
        scores = res_df.pivot(index="Name", columns="Term", values="NES")
    else:
        # Fallback for older/wider formats (samples as columns already)
        scores = res_df.T

    # Reorder to match original obs order and fill missing entries.
    scores = scores.reindex(index=adata.obs_names)
    scores = scores.fillna(0)
    return scores


def _summarize_by_cluster(scores: pd.DataFrame, clusters: pd.Series, top_k: int) -> pd.DataFrame:
    merged = scores.copy()
    merged["cluster"] = clusters
    mean_df = merged.groupby("cluster").mean(numeric_only=True)
    top_rows = []
    for cluster, row in mean_df.iterrows():
        top = row.sort_values(ascending=False).head(top_k)
        for path, val in top.items():
            top_rows.append({"cluster": cluster, "pathway": path, "score": float(val)})
    return pd.DataFrame(top_rows)


def _generate_report(
    adata: "ad.AnnData",
    scores: pd.DataFrame,
    clusters: pd.Series,
    cluster_key: str,
    cluster_summary: pd.DataFrame,
    params: Dict[str, Any],
    output_names: Dict[str, str],
    plots_name: str,
) -> str:
    lines: List[str] = []
    divider = "=" * 70
    lines.append(divider)
    lines.append("Spatial Metabolic Pathway Activity Report")
    lines.append(divider)

    lines.append("\nSection 1. Parameters")
    lines.append(f"  species: {params['species']}")
    lines.append(f"  gene_id_type: {params['gene_id_type']}")
    lines.append(f"  gene_set_library: {params['gene_set_library']}")
    lines.append(f"  min_size / max_size: {params['min_size']} / {params['max_size']}")
    lines.append(f"  smoothing: {params['smooth_scores']} (knn_k={params['knn_k']}, radius={params['radius']}, sigma={params['sigma']})")
    lines.append(f"  top_pathways_per_cluster: {params['top_pathways_per_cluster']}")
    lines.append(f"  chunk_size: {params['chunk_size']}")
    lines.append(f"  cluster_key: {params['cluster_key']}")

    lines.append("\nSection 2. Data overview")
    lines.append(f"  observations: {scores.shape[0]:,}")
    lines.append(f"  genes (input): {adata.n_vars:,}")
    lines.append(f"  pathways scored: {scores.shape[1]:,}")
    unique_clusters = sorted(clusters.unique())
    lines.append(f"  clusters ({cluster_key}): {len(unique_clusters)} -> {', '.join(map(str, unique_clusters))}")

    lines.append("\nSection 3. Score distribution")
    if scores.size == 0:
        lines.append("  score mean/median: N/A (no scores)")
        lines.append("  score min/max: N/A")
    else:
        vals = scores.to_numpy().ravel()
        lines.append(f"  score mean/median: {np.nanmean(vals):.4f} / {np.nanmedian(vals):.4f}")
        lines.append(f"  score min/max: {np.nanmin(vals):.4f} / {np.nanmax(vals):.4f}")

    lines.append("\nSection 4. Top pathways per cluster")
    if not cluster_summary.empty:
        for cluster in unique_clusters:
            top_rows = cluster_summary[cluster_summary["cluster"] == str(cluster)].head(3)
            if top_rows.empty:
                lines.append(f"  {cluster}: no pathways available")
            else:
                desc = ", ".join([f"{row.pathway} ({row.score:.3f})" for row in top_rows.itertuples()])
                lines.append(f"  {cluster}: {desc}")
    else:
        lines.append("  cluster summary is empty")

    lines.append("\nSection 5. Outputs")
    lines.append(f"  scores csv: {output_names['scores']}")
    lines.append(f"  cluster summary csv: {output_names['cluster_summary']}")
    lines.append(f"  report: {output_names['report']}")
        lines.append(f"  plots: {plots_name}")

    report_path = os.path.join(OUTPUT_DIR, output_names["report"])
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return report_path


def _save_outputs(
    scores: pd.DataFrame,
    cluster_summary: pd.DataFrame,
    output_names: Dict[str, str],
    plots_name: str,
) -> Dict[str, str]:
    scores_path = os.path.join(OUTPUT_DIR, output_names["scores"])
    cluster_path = os.path.join(OUTPUT_DIR, output_names["cluster_summary"])
    scores.reset_index().rename(columns={"index": "obs_id"}).to_csv(scores_path, index=False)
    cluster_summary.to_csv(cluster_path, index=False)
    outputs = {
        "pathway_activity_scores.csv": output_names["scores"],
        "pathway_cluster_summary.csv": output_names["cluster_summary"],
        "pathway_activity_report.txt": output_names["report"],
        "pathway_activity_plots.png": plots_name,
    }
    return outputs


def _plot_spatial(coords: np.ndarray, scores: pd.DataFrame, pathways: List[str], out_path: str) -> None:
    n = len(pathways)
    ncols = min(3, n)
    nrows = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(4 * ncols, 4 * nrows))
    axes = np.atleast_1d(axes).flatten()
    for ax, path in zip(axes, pathways):
        if path not in scores.columns:
            ax.axis("off")
            continue
        vals = scores[path].to_numpy()
        sc = ax.scatter(coords[:, 0], coords[:, 1], c=vals, cmap="plasma", s=10)
        ax.set_title(path)
        fig.colorbar(sc, ax=ax, fraction=0.046, pad=0.04)
    for j in range(len(pathways), len(axes)):
        axes[j].axis("off")
    fig.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def _process(
    input_path: str,
    file_type: str,
    spatial_key: str,
    cluster_key: str,
    species: str,
    gene_id_type: str,
    gene_set_library: str,
    smooth_scores: bool,
    knn_k: int,
    radius: Optional[float],
    sigma: float,
    top_pathways_per_cluster: int,
    chunk_size: int,
    min_size: int,
    max_size: int,
) -> Dict[str, Any]:
    if not BIO_AVAILABLE:
        raise RuntimeError("Bioinformatics dependencies are missing; install required packages.")

    adata = _read_adata(input_path, file_type)
    coords = _get_coords(adata, spatial_key)
    clusters, _ = _get_clusters(adata, cluster_key)

    if gene_id_type == "ensembl":
        adata.var_names = adata.var_names.str.replace(r"\\..*$", "", regex=True)

    gene_sets = _load_gene_sets(gene_set_library, species)
    scores = _run_ssgsea(adata, gene_sets, min_size=min_size, max_size=max_size, chunk_size=chunk_size)

    if smooth_scores:
        graph = _build_graph(coords, knn_k=knn_k, radius=radius)
        scores = _smooth_scores(scores, graph, sigma=sigma)

    cluster_summary = _summarize_by_cluster(scores, clusters, top_pathways_per_cluster)

    output_names = {
        "scores": _make_output_name(".csv"),
        "cluster_summary": _make_output_name(".csv"),
        "report": _make_output_name(".txt"),
    }

    # Always generate plots
        top_paths = cluster_summary.sort_values("score", ascending=False)["pathway"].unique()[: min(6, scores.shape[1])]
        plots_name = _make_output_name(".png")
        _plot_spatial(coords, scores, list(top_paths), os.path.join(OUTPUT_DIR, plots_name))

    report_path = _generate_report(
        adata=adata,
        scores=scores,
        clusters=clusters,
        cluster_key=cluster_key,
        cluster_summary=cluster_summary,
        params={
            "species": species,
            "gene_id_type": gene_id_type,
            "gene_set_library": gene_set_library,
            "smooth_scores": smooth_scores,
            "knn_k": knn_k,
            "radius": radius,
            "sigma": sigma,
            "top_pathways_per_cluster": top_pathways_per_cluster,
            "chunk_size": chunk_size,
            "min_size": min_size,
            "max_size": max_size,
            "cluster_key": cluster_key,
        },
        output_names=output_names,
        plots_name=plots_name,
    )

    outputs = _save_outputs(scores, cluster_summary, output_names, plots_name)
    return {"outputs": outputs}


@app.post("/api/spatial-metabolic-activity")
async def spatial_metabolic_activity(
    file: UploadFile = File(...),
    file_type: str = Form("auto"),
    spatial_key: str = Form("spatial"),
    cluster_key: str = Form("cluster"),
    species: str = Form("human"),
    gene_id_type: str = Form("symbol"),
    gene_set_library: str = Form("msigdb_hallmark_kegg"),
    smooth_scores: bool = Form(True),
    knn_k: int = Form(8),
    radius: Optional[float] = Form(None),
    sigma: float = Form(1.0),
    top_pathways_per_cluster: int = Form(10),
    chunk_size: int = Form(200),
    min_size: int = Form(10),
    max_size: int = Form(500),
) -> JSONResponse:
    if not BIO_AVAILABLE:
        return JSONResponse(status_code=500, content={"success": False, "message": "Bioinformatics packages are not installed"})

    temp_input_path = None
    try:
        uid = str(uuid.uuid4())
        temp_input_path = os.path.join(tempfile.gettempdir(), f"input_met_{uid}_{file.filename}")
        with open(temp_input_path, "wb") as f:
            f.write(await file.read())
        result = _process(
            input_path=temp_input_path,
            file_type=file_type,
            spatial_key=spatial_key,
            cluster_key=cluster_key,
            species=species,
            gene_id_type=gene_id_type,
            gene_set_library=gene_set_library,
            smooth_scores=smooth_scores,
            knn_k=knn_k,
            radius=radius,
            sigma=sigma,
            top_pathways_per_cluster=top_pathways_per_cluster,
            chunk_size=chunk_size,
            min_size=min_size,
            max_size=max_size,
        )
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Metabolic pathway activity inference completed",
                "data": result["outputs"],
            },
        )
    except Exception as exc:
        error_info = _handle_error(
            "processing",
            exc,
            context={
                "file_type": file_type,
                "species": species,
                "gene_set_library": gene_set_library,
                "smooth_scores": smooth_scores,
                "cluster_key": cluster_key,
            },
        )
        LOGGER.error("processing failed: %s", error_info.get("error_message"), exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": _format_error_message(error_info),
                "error": error_info,
            },
        )
    finally:
        if temp_input_path and os.path.exists(temp_input_path):
            try:
                os.remove(temp_input_path)
            except Exception as e:
                LOGGER.warning("Failed to clean up temp file: %s", e)


@app.get("/api/download/{file_id}")
async def download(file_id: str):
    target = os.path.join(OUTPUT_DIR, file_id)
    if not os.path.exists(target):
        raise HTTPException(status_code=404, detail=f"File not found or expired: file_id={file_id}")

    if target.endswith(".png"):
        media_type = "image/png"
    elif target.endswith(".csv"):
        media_type = "text/csv"
    elif target.endswith(".txt"):
        media_type = "text/plain; charset=utf-8"
    else:
        media_type = "application/octet-stream"

    return FileResponse(path=target, filename=os.path.basename(target), media_type=media_type)


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)

