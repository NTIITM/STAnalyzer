#!/usr/bin/env python3
"""Spatial TF activity inference service (pure Python, decoupler-based)."""
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


def _setup_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_dir = os.getenv("LOG_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "log"))
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "spatial_tf_activity.log")
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handlers = [logging.StreamHandler(), logging.FileHandler(log_path)]
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = []
    for handler in handlers:
        handler.setFormatter(formatter)
        root.addHandler(handler)


_setup_logging()

try:
    import anndata as ad
    import decoupler as dc
    import networkx as nx
    import omnipath.interactions as opi
    from matplotlib import pyplot as plt
    from sklearn.neighbors import NearestNeighbors, radius_neighbors_graph

    BIO_AVAILABLE = True
except Exception as exc:  # pragma: no cover
    logging.error("Failed to import bioinformatics dependencies: %s", exc)
    BIO_AVAILABLE = False
LOGGER = logging.getLogger("spatial-tf-activity-service")

OUTPUT_DIR = os.getenv("OUTPUT_DIR", os.path.join(os.path.dirname(__file__), "outputs"))
os.makedirs(OUTPUT_DIR, exist_ok=True)

LOGGER.info("Spatial TF activity service initialized (BIO_AVAILABLE=%s)", BIO_AVAILABLE)

def _make_output_name(ext: str) -> str:
    """Return a unique filename with given extension."""
    suffix = ext.lstrip(".")
    return f"{uuid.uuid4()}.{suffix}"

app = FastAPI(title="Spatial TF Activity Service", version="1.0.0")


def _handle_error(step: str, error: Exception) -> Dict[str, Any]:
    return {
        "step": step,
        "error_type": type(error).__name__,
        "error_message": str(error),
        "traceback": traceback.format_exc(),
    }


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


def _get_clusters(adata: "ad.AnnData", cluster_key: Optional[str] = None) -> Tuple[pd.Series, str]:
    if cluster_key is not None:
        if cluster_key in adata.obs:
            return adata.obs[cluster_key].astype(str), cluster_key
        raise ValueError(f"Cluster labels not found: specified cluster_key '{cluster_key}' not found in obs columns.")
    for key in ["cluster", "clusters", "leiden", "louvain", "banksy"]:
        if key in adata.obs:
            return adata.obs[key].astype(str), key
    raise ValueError("Cluster labels not found: expected obs column in {cluster, clusters, leiden, louvain, banksy}.")


def _build_graph(coords: np.ndarray, knn_k: int, radius: Optional[float]) -> nx.Graph:
    if radius:
        adj = radius_neighbors_graph(coords, radius=radius, mode="distance", include_self=False).toarray()
    else:
        nn = NearestNeighbors(n_neighbors=knn_k + 1).fit(coords)
        dist, idx = nn.kneighbors(coords)
        # drop self (index 0)
        rows = []
        cols = []
        data = []
        for i, (drow, irow) in enumerate(zip(dist, idx)):
            for d, j in zip(drow[1:], irow[1:]):
                rows.append(i)
                cols.append(j)
                data.append(d)
        adj = np.zeros((coords.shape[0], coords.shape[0]))
        adj[rows, cols] = data
    G = nx.from_numpy_array(adj)
    return G


def _smooth_scores(scores: pd.DataFrame, graph: nx.Graph, sigma: float) -> pd.DataFrame:
    mat = scores.to_numpy()
    degs = np.array([graph.degree(i) for i in range(graph.number_of_nodes())], dtype=float)
    degs[degs == 0] = 1.0
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


def _load_regulon(species: str, tf_set: str) -> pd.DataFrame:
    allowed_confidence = {"dorothea_a": ["A"], "dorothea_ab": ["A", "B"], "dorothea_abc": ["A", "B", "C"]}

    # decoupler 1.x ships DoRothEA, but some builds miss it in show_resources;
    # fall back to omnipath client if the decoupler call fails.
    try:
        net = dc.get_resource("DoRothEA", organism=species)
    except Exception as exc:  # pragma: no cover - network/cache issues
        LOGGER.warning("Falling back to omnipath DoRothEA (decoupler.get_resource failed: %s)", exc)
        net = opi.Dorothea().get(organism=species, genesymbols=True)

    # Normalize column names expected by decoupler's scoring functions.
    if "source_genesymbol" in net and "target_genesymbol" in net:
        net = net.drop(columns=[col for col in ["source", "target"] if col in net])
        net = net.rename(columns={"source_genesymbol": "source", "target_genesymbol": "target"})
    else:
        source_col = "source_genesymbol" if "source_genesymbol" in net else "source"
        target_col = "target_genesymbol" if "target_genesymbol" in net else "target"
        net = net.rename(columns={source_col: "source", target_col: "target"})

    if "confidence" in net.columns and tf_set in allowed_confidence:
        net = net[net["confidence"].isin(allowed_confidence[tf_set])]
    elif "confidence" not in net.columns:
        LOGGER.info("DoRothEA confidence column missing; skipping tf_set filter (tf_set=%s).", tf_set)

    # Ensure weights exist for VIPER; use sign from consensus flags when present.
    if "weight" not in net.columns:
        if {"consensus_stimulation", "consensus_inhibition"}.issubset(net.columns):
            stim = net["consensus_stimulation"].astype(bool)
            inhib = net["consensus_inhibition"].astype(bool)
            net["weight"] = np.where(stim & ~inhib, 1.0, np.where(inhib & ~stim, -1.0, 1.0))
        elif "mor" in net.columns:
            net["weight"] = net["mor"]
        else:
            net["weight"] = 1.0

    if "mor" not in net.columns:
        net["mor"] = np.sign(net["weight"])

    # VIPER requires unique regulator-target pairs.
    net = net.drop_duplicates(subset=["source", "target"])

    return net


def _run_tf_activity(
    adata: "ad.AnnData",
    net: pd.DataFrame,
    method: str,
    chunk_size: int,
) -> pd.DataFrame:
    expr = pd.DataFrame(adata.X.toarray() if hasattr(adata.X, "toarray") else adata.X, index=adata.obs_names, columns=adata.var_names)
    # Harmonize identifiers to maximize overlap between data and network.
    expr.columns = expr.columns.astype(str).str.upper().str.replace(r"\..*$", "", regex=True)
    net = net.copy()
    net["source"] = net["source"].astype(str).str.upper()
    net["target"] = net["target"].astype(str).str.upper().str.replace(r"\..*$", "", regex=True)
    net = net[net["target"].isin(expr.columns)].drop_duplicates(subset=["source", "target"])
    if net.empty:
        raise ValueError("No overlap between regulon targets and expression genes after harmonization.")

    tf_list = net["source"].unique()
    n_chunks = max(1, int(np.ceil(len(tf_list) / max(chunk_size, 1))))
    score_parts = []
    for chunk_tfs in np.array_split(tf_list, n_chunks):
        net_chunk = net[net["source"].isin(chunk_tfs)]
        if net_chunk.empty:
            continue
        chunk_min_n = 1
        if method == "aucell":
            estimate = dc.run_aucell(mat=expr, net=net_chunk, seed=None)
        else:
            estimate, _ = dc.run_viper(mat=expr, net=net_chunk, min_n=chunk_min_n, verbose=False)
        score_parts.append(estimate)
    scores = pd.concat(score_parts, axis=1)
    scores = scores.loc[:, ~scores.columns.duplicated()]
    return scores


def _summarize_by_cluster(scores: pd.DataFrame, clusters: pd.Series, top_k: int) -> pd.DataFrame:
    merged = scores.copy()
    merged["cluster"] = clusters
    mean_df = merged.groupby("cluster").mean(numeric_only=True)
    top_rows = []
    for cluster, row in mean_df.iterrows():
        top = row.sort_values(ascending=False).head(top_k)
        for tf, val in top.items():
            top_rows.append({"cluster": cluster, "tf": tf, "score": float(val)})
    return pd.DataFrame(top_rows)


def _generate_report(
    adata: "ad.AnnData",
    scores: pd.DataFrame,
    clusters: pd.Series,
    cluster_key: str,
    cluster_summary: pd.DataFrame,
    params: Dict[str, Any],
    output_names: Dict[str, str],
    plots_name: Optional[str],
) -> str:
    lines: List[str] = []
    divider = "=" * 70
    lines.append(divider)
    lines.append("Spatial TF Activity Report")
    lines.append(divider)

    lines.append("\nSection 1. Parameters")
    lines.append(f"  species: {params['species']}")
    lines.append(f"  gene_id_type: {params['gene_id_type']}")
    lines.append(f"  tf_set: {params['tf_set']}")
    lines.append(f"  method: {params['method']}")
    lines.append(f"  smoothing: {params['smooth_scores']} (knn_k={params['knn_k']}, radius={params['radius']}, sigma={params['sigma']})")
    lines.append(f"  top_tfs_per_cluster: {params['top_tfs_per_cluster']}")
    lines.append(f"  generate_plots: {params['generate_plots']}")
    lines.append(f"  chunk_size: {params['chunk_size']}")

    lines.append("\nSection 2. Data overview")
    lines.append(f"  observations: {scores.shape[0]:,}")
    lines.append(f"  genes (input): {adata.n_vars:,}")
    lines.append(f"  TFs scored: {scores.shape[1]:,}")
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

    lines.append("\nSection 4. Top TFs per cluster")
    if not cluster_summary.empty:
        for cluster in unique_clusters:
            top_rows = cluster_summary[cluster_summary["cluster"] == str(cluster)].head(3)
            if top_rows.empty:
                lines.append(f"  {cluster}: no TFs available")
            else:
                desc = ", ".join([f"{row.tf} ({row.score:.3f})" for row in top_rows.itertuples()])
                lines.append(f"  {cluster}: {desc}")
    else:
        lines.append("  cluster summary is empty")

    lines.append("\nSection 5. Outputs")
    lines.append(f"  scores csv: {output_names['scores']}")
    lines.append(f"  cluster summary csv: {output_names['cluster_summary']}")
    lines.append(f"  report: {output_names['report']}")
    if plots_name:
        lines.append(f"  plots: {plots_name}")

    report_path = os.path.join(OUTPUT_DIR, output_names["report"])
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return report_path


def _save_outputs(
    scores: pd.DataFrame,
    cluster_summary: pd.DataFrame,
    output_names: Dict[str, str],
    plots_name: Optional[str],
) -> Dict[str, str]:
    scores_path = os.path.join(OUTPUT_DIR, output_names["scores"])
    cluster_path = os.path.join(OUTPUT_DIR, output_names["cluster_summary"])
    scores.reset_index().rename(columns={"index": "obs_id"}).to_csv(scores_path, index=False)
    cluster_summary.to_csv(cluster_path, index=False)
    outputs = {
        "tf_activity_scores.csv": output_names["scores"],
        "tf_cluster_summary.csv": output_names["cluster_summary"],
        "tf_activity_report.txt": output_names["report"],
    }
    if plots_name:
        outputs["tf_activity_plots.png"] = plots_name
    return outputs


def _plot_spatial(adata: "ad.AnnData", coords: np.ndarray, scores: pd.DataFrame, genes: List[str], out_path: str) -> None:
    n = len(genes)
    ncols = min(3, n)
    nrows = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(4 * ncols, 4 * nrows))
    axes = np.atleast_1d(axes).flatten()
    for ax, gene in zip(axes, genes):
        if gene not in scores.columns:
            ax.axis("off")
            continue
        vals = scores[gene].to_numpy()
        sc = ax.scatter(coords[:, 0], coords[:, 1], c=vals, cmap="viridis", s=10)
        ax.set_title(gene)
        fig.colorbar(sc, ax=ax, fraction=0.046, pad=0.04)
    for j in range(len(genes), len(axes)):
        axes[j].axis("off")
    fig.tight_layout()
    fig.savefig(out_path, dpi=200)
    plt.close(fig)


def _process(
    input_path: str,
    file_type: str,
    spatial_key: str,
    cluster_key: Optional[str],
    species: str,
    gene_id_type: str,
    tf_set: str,
    method: str,
    smooth_scores: bool,
    knn_k: int,
    radius: Optional[float],
    sigma: float,
    top_tfs_per_cluster: int,
    generate_plots: bool,
    chunk_size: int,
) -> Dict[str, Any]:
    if not BIO_AVAILABLE:
        raise RuntimeError("Bioinformatics dependencies are missing; install required packages.")

    adata = _read_adata(input_path, file_type)
    coords = _get_coords(adata, spatial_key)
    clusters, final_cluster_key = _get_clusters(adata, cluster_key)

    if gene_id_type == "ensembl":
        adata.var_names = adata.var_names.str.replace(r"\\..*$", "", regex=True)

    net = _load_regulon(species, tf_set)
    scores = _run_tf_activity(adata, net, method, chunk_size)

    if smooth_scores:
        graph = _build_graph(coords, knn_k=knn_k, radius=radius)
        scores = _smooth_scores(scores, graph, sigma=sigma)

    cluster_summary = _summarize_by_cluster(scores, clusters, top_tfs_per_cluster)

    output_names = {
        "scores": _make_output_name(".csv"),
        "cluster_summary": _make_output_name(".csv"),
        "report": _make_output_name(".txt"),
    }

    plots_name: Optional[str] = None
    if generate_plots:
        top_genes = cluster_summary.sort_values("score", ascending=False)["tf"].unique()[: min(6, scores.shape[1])]
        plots_name = _make_output_name(".png")
        _plot_spatial(
            adata,
            coords,
            scores,
            list(top_genes),
            os.path.join(OUTPUT_DIR, plots_name),
        )

    report_path = _generate_report(
        adata=adata,
        scores=scores,
        clusters=clusters,
        cluster_key=final_cluster_key,
        cluster_summary=cluster_summary,
        params={
            "species": species,
            "gene_id_type": gene_id_type,
            "tf_set": tf_set,
            "method": method,
            "smooth_scores": smooth_scores,
            "knn_k": knn_k,
            "radius": radius,
            "sigma": sigma,
            "top_tfs_per_cluster": top_tfs_per_cluster,
            "generate_plots": generate_plots,
            "chunk_size": chunk_size,
        },
        output_names=output_names,
        plots_name=plots_name,
    )

    outputs = _save_outputs(scores, cluster_summary, output_names, plots_name)
    return {"outputs": outputs}


@app.get("/health")
async def health():
    """Health check endpoint"""
    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "service": "spatial-tf-activity-service",
            "bio_available": BIO_AVAILABLE
        }
    )


@app.post("/api/spatial-tf-activity")
async def spatial_tf_activity(
    file: UploadFile = File(...),
    file_type: str = Form("auto"),
    spatial_key: str = Form("spatial"),
    cluster_key: Optional[str] = Form(None),
    species: str = Form("human"),
    gene_id_type: str = Form("symbol"),
    tf_set: str = Form("dorothea_ab"),
    method: str = Form("viper"),
    smooth_scores: bool = Form(True),
    knn_k: int = Form(8),
    radius: Optional[float] = Form(None),
    sigma: float = Form(1.0),
    top_tfs_per_cluster: int = Form(10),
    generate_plots: bool = Form(True),
    chunk_size: int = Form(200),
) -> JSONResponse:
    if not BIO_AVAILABLE:
        return JSONResponse(status_code=500, content={"success": False, "message": "Bioinformatics packages are not installed"})

    temp_input_path = None
    try:
        uid = str(uuid.uuid4())
        temp_input_path = os.path.join(tempfile.gettempdir(), f"input_tf_{uid}_{file.filename}")
        with open(temp_input_path, "wb") as f:
            f.write(await file.read())

        result = _process(
            input_path=temp_input_path,
            file_type=file_type,
            spatial_key=spatial_key,
            cluster_key=cluster_key,
            species=species,
            gene_id_type=gene_id_type,
            tf_set=tf_set,
            method=method,
            smooth_scores=smooth_scores,
            knn_k=knn_k,
            radius=radius,
            sigma=sigma,
            top_tfs_per_cluster=top_tfs_per_cluster,
            generate_plots=generate_plots,
            chunk_size=chunk_size,
        )
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "TF activity inference completed",
                "data": result["outputs"],
            },
        )
    except Exception as exc:
        LOGGER.error("processing failed: %s", exc, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": "TF activity inference failed", "error": _handle_error("processing", exc)},
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

    LOGGER.info("Starting uvicorn server on 0.0.0.0:8080")
    uvicorn.run(app, host="0.0.0.0", port=8080, log_config=None)

