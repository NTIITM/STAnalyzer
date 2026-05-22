#!/usr/bin/env python3
"""
PASTE 3D Spatial Alignment API Server
Generates rich 3D visualizations and comprehensive alignment statistics.
"""

import os
import tempfile
import uuid
import logging

import numpy as np
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse
import anndata as ad
import scanpy as sc
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

from algorithm import align_slices

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="PASTE 3D Spatial Alignment",
    description="Align multiple spatial transcriptomics slices using FGW optimal transport (PASTE) and visualize results in 3D.",
    version="1.0.0",
)

OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ─── Visualization Helpers ────────────────────────────────────────────────────

def _get_spatial_coords(adata: ad.AnnData) -> np.ndarray:
    for key in ("spatial", "X_spatial", "spatial_coords"):
        if key in adata.obsm:
            return adata.obsm[key][:, :2].astype(np.float64)
    raise ValueError("No 'spatial' coordinates found in obsm.")


def _top_cluster_colors(adata: ad.AnnData, palette: list) -> np.ndarray:
    """Colour each spot by its cluster (leiden > louvain > uniform fallback)."""
    for key in ("leiden", "louvain", "cluster", "cell_type"):
        if key in adata.obs:
            cats = adata.obs[key].astype("category").cat.codes.values
            cmap = plt.cm.get_cmap("tab20", cats.max() + 1)
            return cmap(cats)
    # Fallback: colour by first PC score (continuous)
    if "X_pca" in adata.obsm:
        vals = adata.obsm["X_pca"][:, 0]
        vals = (vals - vals.min()) / (vals.ptp() + 1e-9)
        cmap = plt.cm.get_cmap(palette[0])
        return cmap(vals)
    # Absolute fallback: uniform colour
    n = adata.n_obs
    c = np.array(plt.cm.get_cmap(palette[0])(0.5))
    return np.tile(c, (n, 1))


def _make_3d_plot(
    s1: ad.AnnData,
    s2: ad.AnnData,
    pi: np.ndarray,
    output_path: str,
) -> None:
    """
    Render a 3D stacked scatter of the two aligned slices.
    
    - Slice 1 sits at z=0 (cool palette)
    - Slice 2 sits at z=1 (warm palette, coordinates projected into slice-1 space)
    - Grey lines connect the top-50 strongest transport links from pi
    """
    coords1 = _get_spatial_coords(s1)
    coords2 = _get_spatial_coords(s2)

    colors1 = _top_cluster_colors(s1, ["Blues"])
    colors2 = _top_cluster_colors(s2, ["Reds"])

    fig = plt.figure(figsize=(14, 10))
    ax = fig.add_subplot(111, projection="3d")

    # ── Slice 1 at z=0 ──────────────────────────────────────────────────────
    ax.scatter(
        coords1[:, 0], coords1[:, 1],
        zs=0, zdir="z",
        c=colors1, s=6, alpha=0.7, label="Slice 1",
        depthshade=True,
    )

    # ── Slice 2 at z=1 ──────────────────────────────────────────────────────
    ax.scatter(
        coords2[:, 0], coords2[:, 1],
        zs=1, zdir="z",
        c=colors2, s=6, alpha=0.7, label="Slice 2 (aligned)",
        depthshade=True,
    )

    # ── Transport lines: top-N strongest links ───────────────────────────────
    n_links = min(50, pi.shape[0], pi.shape[1])
    if pi is not None and n_links > 0:
        # Find the top-N (source, target) pairs by coupling mass
        flat_idx = np.argsort(pi.ravel())[::-1][:n_links]
        row_idx, col_idx = np.unravel_index(flat_idx, pi.shape)
        for r, c in zip(row_idx, col_idx):
            xs = [coords1[r, 0], coords2[c, 0]]
            ys = [coords1[r, 1], coords2[c, 1]]
            zs = [0, 1]
            ax.plot(xs, ys, zs, color="grey", alpha=0.25, linewidth=0.6)

    ax.set_xlabel("X", labelpad=10)
    ax.set_ylabel("Y", labelpad=10)
    ax.set_zlabel("Slice (Z)", labelpad=10)
    ax.set_zticks([0, 1])
    ax.set_zticklabels(["Slice 1", "Slice 2"])
    ax.set_title("PASTE 3D Spatial Alignment\n(Grey lines = top-50 optimal transport links)", pad=15)
    ax.legend(loc="upper left", markerscale=3)
    ax.view_init(elev=25, azim=-60)   # default viewpoint

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"3D plot saved: {output_path}")


def _make_2d_comparison(
    s1: ad.AnnData,
    s2_orig: ad.AnnData,
    s2_aligned: ad.AnnData,
    output_path: str,
) -> None:
    """
    Side-by-side 2-panel 2D scatter:
      Left : slice 1 vs slice 2 BEFORE alignment (slice 2 in original coords)
      Right: slice 1 vs slice 2 AFTER alignment (slice 2 projected into slice 1 space)
    """
    c1 = _get_spatial_coords(s1)
    try:
        c2_orig = _get_spatial_coords(s2_orig)
    except Exception:
        c2_orig = _get_spatial_coords(s2_aligned)
    c2_align = _get_spatial_coords(s2_aligned)

    fig, (ax_pre, ax_post) = plt.subplots(1, 2, figsize=(14, 6))

    for ax, c2, title in [
        (ax_pre, c2_orig, "Before Alignment"),
        (ax_post, c2_align, "After Alignment (PASTE FGW-OT)"),
    ]:
        ax.scatter(c1[:, 0], c1[:, 1], c="steelblue", s=4, alpha=0.6, label="Slice 1")
        ax.scatter(c2[:, 0], c2[:, 1], c="tomato", s=4, alpha=0.6, label="Slice 2")
        ax.set_title(title, fontsize=13)
        ax.legend(markerscale=3)
        ax.set_aspect("equal")
        ax.axis("off")

    fig.suptitle("Spatial Slice Alignment Comparison", fontsize=15, y=1.01)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"Comparison plot saved: {output_path}")


def _compute_stats(
    s1: ad.AnnData,
    s2_aligned: ad.AnnData,
    pi: np.ndarray,
    alpha: float,
    use_hvg: bool,
) -> str:
    lines = [
        "PASTE Alignment — Full Report",
        "=" * 40,
        f"Alpha (spatial weight):      {alpha}",
        f"Use highly-variable genes:   {use_hvg}",
        f"Slice 1 spots:               {s1.n_obs}",
        f"Slice 2 spots:               {s2_aligned.n_obs}",
        f"Slice 1 genes:               {s1.n_vars}",
        f"Slice 2 genes:               {s2_aligned.n_vars}",
    ]

    if pi is not None:
        mass = float(pi.sum())
        entropy = float(-(pi * np.log(pi + 1e-300)).sum())
        # Fraction of mass carried by the top-100 links
        flat_sorted = np.sort(pi.ravel())[::-1]
        top_mass = float(flat_sorted[:100].sum())
        lines += [
            "",
            "-- Coupling Matrix (π) Diagnostics --",
            f"Total transport mass:        {mass:.6f}",
            f"Entropy H(π):               {entropy:.4f}",
            f"Top-100 link mass fraction:  {top_mass / (mass + 1e-9):.4f}",
            f"π shape:                    {pi.shape[0]} × {pi.shape[1]}",
        ]

    # Coordinate convergence: centroid distance after alignment
    try:
        c1 = _get_spatial_coords(s1)
        c2 = _get_spatial_coords(s2_aligned)
        d_centroid = np.linalg.norm(c1.mean(0) - c2.mean(0))
        lines += [
            "",
            "-- Alignment Quality --",
            f"Centroid distance (aligned): {d_centroid:.4f}",
        ]
    except Exception:
        pass

    lines.append("")
    lines.append("Alignment successful.")
    return "\n".join(lines)


# ─── API Endpoint ─────────────────────────────────────────────────────────────

@app.post("/api/detect")
async def detect_domains(
    slice1: UploadFile = File(...),
    slice2: UploadFile = File(...),
    alpha: float = Form(0.1),
    use_highly_variable: bool = Form(True),
) -> JSONResponse:
    """
    PASTE 3D Spatial Alignment endpoint.
    Accepts two spatial .h5ad slices and returns:
      - aligned_data.h5ad  : projected slice 2 with updated spatial coords
      - alignment_3d.png   : 3D stacked scatter with OT links
      - comparison.png     : side-by-side before/after 2D comparison
      - statistics.txt     : full alignment statistics report
    """
    temp_path1 = temp_path2 = None
    try:
        # Save uploaded files
        tid = str(uuid.uuid4())
        temp_path1 = os.path.join(tempfile.gettempdir(), f"s1_{tid}.h5ad")
        temp_path2 = os.path.join(tempfile.gettempdir(), f"s2_{tid}.h5ad")
        with open(temp_path1, "wb") as f: f.write(await slice1.read())
        with open(temp_path2, "wb") as f: f.write(await slice2.read())

        adata1 = ad.read_h5ad(temp_path1)
        adata2 = ad.read_h5ad(temp_path2)
        adata2_original = adata2.copy()  # keep original coords for comparison panel

        # Run FGW-OT alignment
        b1, aligned_b2, pi = align_slices(
            adata1, adata2,
            alpha=alpha,
            use_highly_variable=use_highly_variable,
        )

        rid = str(uuid.uuid4())

        # 1. Save aligned h5ad
        h5ad_id = f"{rid}_aligned.h5ad"
        aligned_b2.write_h5ad(os.path.join(OUTPUT_DIR, h5ad_id))

        # 2. 3D stacked slice plot
        png3d_id = f"{rid}_3d.png"
        _make_3d_plot(b1, aligned_b2, pi, os.path.join(OUTPUT_DIR, png3d_id))

        # 3. Before/after 2D comparison plot
        cmp_id = f"{rid}_comparison.png"
        _make_2d_comparison(b1, adata2_original, aligned_b2, os.path.join(OUTPUT_DIR, cmp_id))

        # 4. Statistics report
        stats_id = f"{rid}_stats.txt"
        stats_text = _compute_stats(b1, aligned_b2, pi, alpha, use_highly_variable)
        with open(os.path.join(OUTPUT_DIR, stats_id), "w") as f:
            f.write(stats_text)
        logger.info(stats_text)

        data_dict = {
            "aligned_data.h5ad": h5ad_id,
            "alignment_plot.png": png3d_id,
            "statistics.txt": stats_id,
            "comparison.png": cmp_id,
        }

        return JSONResponse(status_code=200, content={
            "success": True,
            "message": "Alignment completed",
            "data": data_dict,
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={
            "success": False,
            "message": f"Alignment failed: {str(e)}",
        })
    finally:
        for p in [temp_path1, temp_path2]:
            if p and os.path.exists(p):
                try: os.remove(p)
                except: pass


@app.get("/api/download/{file_id}")
async def download_file(file_id: str) -> FileResponse:
    file_path = os.path.join(OUTPUT_DIR, file_id)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    media_type = "image/png" if file_path.endswith(".png") else "application/octet-stream"
    return FileResponse(path=file_path, filename=file_id, media_type=media_type)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "paste_alignment"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 51805))
    uvicorn.run(app, host="0.0.0.0", port=port)
