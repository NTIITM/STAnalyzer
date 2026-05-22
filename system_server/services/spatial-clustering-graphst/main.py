#!/usr/bin/env python3
"""
GraphST-based spatial clustering service
Uses GraphST to learn spatial expression representations and performs clustering.
"""
import os
import tempfile
import uuid
from typing import Dict, Literal

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse

import anndata as ad
import scanpy as sc
import pandas as pd
import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

plt.rcParams["font.sans-serif"] = ["Arial", "DejaVu Sans", "Liberation Sans"]
plt.rcParams["axes.unicode_minus"] = False

# Import GraphST
try:
    from GraphST.GraphST.GraphST import GraphST
except ImportError as e:  # pragma: no cover - runtime error message
    raise ImportError(
        "GraphST is not installed or cannot be imported. "
        "Please ensure GraphST is installed in the same environment, "
        "or add GraphST_proj/GraphST-main/GraphST to PYTHONPATH."
    ) from e


app = FastAPI(
    title="GraphST Spatial Clustering Service",
    description="Learn spatial expression representations using GraphST and perform spatial clustering",
    version="1.0.0",
)

# 输出目录
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def read_adata(file_path: str) -> ad.AnnData:
    """Read AnnData file. Only h5ad format is supported."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Input file does not exist: {file_path}")
    
    if file_path.endswith(".h5ad"):
        try:
            return ad.read_h5ad(file_path)
        except Exception as e:
            raise ValueError(f"Failed to read h5ad file '{file_path}': {str(e)}") from e
    
    raise ValueError(
        f"Cannot auto-detect file type (file: {file_path}). "
        f"Only .h5ad format is supported."
    )


def generate_plots(
    adata: ad.AnnData, output_dir: str, cluster_key: str, used_spatial: bool
) -> Dict[str, str]:
    """Generate clustering visualization plots (UMAP + spatial plot), consistent with other spatial clustering services."""
    plot_files: Dict[str, str] = {}
    if cluster_key not in adata.obs.columns:
        return plot_files

    os.makedirs(output_dir, exist_ok=True)

    sc.settings.set_figure_params(dpi=300, facecolor="white", figsize=(10, 8))
    sc.settings.figdir = output_dir
    sc.settings.autosave = True
    sc.settings.autoshow = False

    # 1. UMAP 图（优先基于 GraphST 表征）
    try:
        if "emb" in adata.obsm_keys():
            adata.obsm["X_graphst"] = adata.obsm["emb"]
            sc.pp.neighbors(adata, use_rep="X_graphst", n_neighbors=15)
            sc.tl.umap(adata)
        elif "X_umap" not in adata.obsm_keys():
            if "X_pca" not in adata.obsm_keys():
                sc.tl.pca(adata, n_comps=30)
            sc.tl.umap(adata)

        if "X_umap" in adata.obsm_keys():
            umap_id = f"{uuid.uuid4()}.png"
            save_name = umap_id.replace(".png", "")
            sc.pl.umap(
                adata,
                color=cluster_key,
                title="GraphST Clustering on UMAP",
                show=False,
                save=f"_{save_name}.png",
            )

            scanpy_output = os.path.join(output_dir, f"umap_{save_name}.png")
            umap_path = os.path.join(output_dir, umap_id)
            if os.path.exists(scanpy_output):
                import shutil

                shutil.move(scanpy_output, umap_path)
                plot_files["cluster_umap"] = umap_id
    except Exception as e:  # pragma: no cover - visualization failure is not fatal
        print(f"Failed to generate UMAP plot: {e}")

    # 2. 空间分布图
    if used_spatial and "spatial" in adata.obsm_keys():
        try:
            coords = adata.obsm["spatial"]
            if coords is not None and coords.shape[0] == adata.n_obs:
                spatial_id = f"{uuid.uuid4()}.png"
                save_name = spatial_id.replace(".png", "")

                library_id = None
                img_key = None
                if "spatial" in adata.uns:
                    spatial_uns = adata.uns["spatial"]
                    if isinstance(spatial_uns, dict):
                        for lib_id, lib_data in spatial_uns.items():
                            if isinstance(lib_data, dict) and "images" in lib_data:
                                library_id = lib_id
                                images = lib_data["images"]
                                for key in ["hires", "lowres", "fullres"]:
                                    if key in images:
                                        img_key = key
                                        break
                                if img_key:
                                    break

                try:
                    if library_id and img_key:
                        sc.pl.spatial(
                            adata,
                            color=cluster_key,
                            library_id=library_id,
                            img_key=img_key,
                            alpha=0.7,
                            size=1.5,
                            title="GraphST Clustering on Spatial Coordinates",
                            show=False,
                            save=f"_{save_name}.png",
                        )
                    else:
                        sc.pl.embedding(
                            adata,
                            basis="spatial",
                            color=cluster_key,
                            title="GraphST Clustering on Spatial Coordinates",
                            show=False,
                            save=f"_{save_name}.png",
                        )
                except Exception:
                    sc.pl.embedding(
                        adata,
                        basis="spatial",
                        color=cluster_key,
                        title="GraphST Clustering on Spatial Coordinates",
                        show=False,
                        save=f"_{save_name}.png",
                    )

                possible_outputs = [
                    os.path.join(output_dir, f"show_{save_name}.png"),
                    os.path.join(output_dir, f"spatial_{save_name}.png"),
                    os.path.join(output_dir, f"embedding_{save_name}.png"),
                ]

                spatial_path = os.path.join(output_dir, spatial_id)
                for scanpy_output in possible_outputs:
                    if os.path.exists(scanpy_output):
                        import shutil

                        shutil.move(scanpy_output, spatial_path)
                        plot_files["cluster_spatial"] = spatial_id
                        break
        except Exception as e:  # pragma: no cover
            print(f"Failed to generate spatial plot: {e}")

    return plot_files


@app.post("/api/graphst-cluster")
async def graphst_cluster(
    file: UploadFile = File(...),
    resolution: float = Form(1.0),
    algorithm: Literal["leiden", "louvain"] = Form("leiden"),
    random_state: int = Form(41),
    epochs: int = Form(600),
    neighborhoods: int = Form(6),
) -> JSONResponse:
    """
    GraphST spatial clustering endpoint.

    Process:
    1. Read AnnData file (h5ad format);
    2. Use GraphST for representation learning (obtain obsm['emb']);
    3. Perform neighbor graph + Leiden/Louvain clustering based on GraphST representations;
    4. Output h5ad, UMAP plot, spatial plot, and statistics report, consistent with existing spatial clustering services.
    """
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

        # Read data
        adata = read_adata(temp_input_path)

        # Check if spatial coordinates are available
        used_spatial = "spatial" in adata.obsm_keys() and adata.obsm["spatial"] is not None

        # Use CUDA device
        import torch

        if not torch.cuda.is_available():
            raise RuntimeError(
                "CUDA is not available. This service requires CUDA to run. "
                "Please ensure CUDA is properly installed and accessible."
            )

        torch_device = torch.device("cuda")

        # Run GraphST representation learning (datatype uses default value '10X')
        try:
            graphst_model = GraphST(
                adata=adata,
                device=torch_device,
                epochs=int(epochs),
                n_neighbors=int(neighborhoods),
            )
            adata_graphst = graphst_model.train()  # Returns AnnData with obsm['emb']
        except Exception as e:
            raise RuntimeError(
                f"GraphST model training failed: {str(e)}. "
                f"Please check if the input data format is correct "
                f"(requires expression matrix and spatial coordinates), "
                f"and if CUDA device is properly configured."
            ) from e

        if "emb" not in adata_graphst.obsm_keys():
            raise RuntimeError(
                "GraphST training completed, but expected 'emb' representation not found in adata.obsm. "
                f"Available obsm keys: {list(adata_graphst.obsm_keys())}"
            )

        # Perform clustering using GraphST representations
        adata = adata_graphst
        adata.obsm["X_graphst"] = adata.obsm["emb"]
        sc.pp.neighbors(adata, use_rep="X_graphst", n_neighbors=15)

        # Use algorithm name as temporary key, then copy to graphST
        temp_key = algorithm
        if algorithm == "leiden":
            sc.tl.leiden(
                adata,
                resolution=resolution,
                key_added=temp_key,
                random_state=random_state,
            )
        else:
            if hasattr(sc.tl, "louvain"):
                sc.tl.louvain(
                    adata,
                    resolution=resolution,
                    key_added=temp_key,
                    random_state=random_state,
                )
            else:
                raise RuntimeError("Louvain is not supported in the current environment. Please use leiden instead.")

        # Copy clustering results to graphST column
        cluster_key = "graphST"
        if temp_key not in adata.obs.columns:
            raise RuntimeError(
                f"Clustering algorithm {algorithm} executed, but expected clustering result column '{temp_key}' not found in adata.obs"
            )
        adata.obs[cluster_key] = adata.obs[temp_key].astype(str)

        # Save results
        h5ad_id = f"{uuid.uuid4()}.h5ad"
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        output_file_path = os.path.join(OUTPUT_DIR, h5ad_id)
        adata.write_h5ad(output_file_path)

        # Generate visualization plots (using graphST as clustering key)
        plot_files = generate_plots(adata, OUTPUT_DIR, cluster_key, used_spatial)

        # Generate statistics report
        stats_text_parts = []
        stats_text_parts.append("=" * 60)
        stats_text_parts.append("GraphST Spatial Clustering Statistical Report")
        stats_text_parts.append("=" * 60)
        stats_text_parts.append("\n[I. Analysis Parameters]")
        stats_text_parts.append("  Method: GraphST (Graph-based self-supervised contrastive learning)")
        stats_text_parts.append(f"  Device: cuda")
        stats_text_parts.append(f"  Epochs: {epochs}")
        stats_text_parts.append(f"  Neighborhoods: {neighborhoods}")
        stats_text_parts.append(f"  Clustering algorithm: {algorithm}")
        stats_text_parts.append(f"  Resolution: {resolution}")
        stats_text_parts.append(
            f"  Random state: {random_state if random_state >= 0 else 'Non-deterministic'}"
        )

        stats_text_parts.append("\n[II. Data Statistics]")
        stats_text_parts.append(f"  Number of cells/spots: {adata.n_obs:,}")
        stats_text_parts.append(f"  Number of genes: {adata.n_vars:,}")

        cluster_key = "graphST"
        if cluster_key in adata.obs.columns:
            cluster_labels = adata.obs[cluster_key]
            n_clusters = cluster_labels.nunique()
            cluster_counts = cluster_labels.value_counts().sort_index()

            stats_text_parts.append("\n[III. Clustering Results]")
            stats_text_parts.append(f"  Number of clusters: {n_clusters}")
            stats_text_parts.append(f"  Cluster label column: {cluster_key}")
            stats_text_parts.append("  Cell counts per cluster:")
            for cluster_id, count in cluster_counts.items():
                percentage = (count / adata.n_obs) * 100
                stats_text_parts.append(
                    f"    Cluster {cluster_id}: {count:,} ({percentage:.2f}%)"
                )

            # 差异表达分析
            stats_text_parts.append(
                "\n[IV. Top 10 Differentially Expressed Genes per Cluster]"
            )
            try:
                if "log1p" not in adata.layers and adata.X.max() > 20:
                    # Access raw counts from layers['counts'] (preprocessing service stores raw data here)
                    # For scanpy's rank_genes_groups, we need to set adata.raw if counts layer exists
                    if 'counts' in adata.layers and adata.raw is None:
                        # Create a copy of adata with counts layer as X for raw
                        adata_raw = adata.copy()
                        adata_raw.X = adata.layers['counts']
                        adata.raw = adata_raw
                    use_raw = adata.raw is not None
                else:
                    use_raw = False

                sc.tl.rank_genes_groups(
                    adata,
                    groupby=cluster_key,
                    method="wilcoxon",
                    n_genes=10,
                    use_raw=use_raw,
                )

                if "rank_genes_groups" in adata.uns:
                    result = adata.uns["rank_genes_groups"]
                    clusters = sorted(cluster_labels.unique().astype(str))
                    available_clusters = (
                        result["names"].dtype.names if result["names"].dtype.names else []
                    )

                    for cluster_id in clusters:
                        cluster_str = str(cluster_id)
                        if cluster_str in available_clusters:
                            gene_names = result["names"][cluster_str][:10]
                            scores = result["scores"][cluster_str][:10]
                            pvals_adj = result["pvals_adj"][cluster_str][:10]
                            logfoldchanges = result["logfoldchanges"][cluster_str][:10]

                            stats_text_parts.append(f"\n  Cluster {cluster_id}:")
                            for i, (gene, score, pval, logfc) in enumerate(
                                zip(gene_names, scores, pvals_adj, logfoldchanges), 1
                            ):
                                stats_text_parts.append(
                                    f"    {i:2d}. {gene:15s} | Score: {score:7.2f} | "
                                    f"log2FC: {logfc:6.2f} | p_adj: {pval:.2e}"
                                )
                        else:
                            stats_text_parts.append(
                                f"\n  Cluster {cluster_id}: No differential expression data available"
                            )
                else:
                    stats_text_parts.append(
                        "  Warning: Differential expression analysis failed"
                    )
            except Exception as e:  # pragma: no cover
                stats_text_parts.append(
                    f"  Warning: Differential expression analysis failed: {str(e)}"
                )

        stats_text = "\n".join(stats_text_parts)

        # Save statistics report
        statistics_id = f"{uuid.uuid4()}.txt"
        statistics_path = os.path.join(OUTPUT_DIR, statistics_id)
        with open(statistics_path, "w", encoding="utf-8") as f:
            f.write(stats_text)

        # Build response data
        data_dict = {
            "spatial_cluster_data.h5ad": h5ad_id,
            "statistics.txt": statistics_id,
        }
        expected_plots = {
            "cluster_umap.png": "cluster_umap",
            "cluster_spatial.png": "cluster_spatial",
        }
        for filename, plot_key in expected_plots.items():
            if plot_key in plot_files:
                data_dict[filename] = plot_files[plot_key]

        return JSONResponse(
            status_code=200,
            content={"success": True, "message": "GraphST spatial clustering completed", "data": data_dict},
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"GraphST spatial clustering failed: {str(e)}"},
        )
    finally:
        if temp_input_path and os.path.exists(temp_input_path):
            try:
                os.remove(temp_input_path)
            except Exception:
                pass


@app.get("/api/download/{file_id}")
async def download_file(file_id: str) -> FileResponse:
    """Download file, consistent with other spatial clustering services."""
    file_path = os.path.join(OUTPUT_DIR, file_id)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"File not found: {file_id}")

    if file_path.endswith(".png"):
        media_type = "image/png"
    else:
        media_type = "application/octet-stream"

    return FileResponse(path=file_path, filename=file_id, media_type=media_type)


@app.get("/health")
async def health():
    return {"status": "healthy", "output_dir": OUTPUT_DIR}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)


