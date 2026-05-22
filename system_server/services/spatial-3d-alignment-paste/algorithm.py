"""
Native PASTE Algorithm Implementation
--------------------------------------
Implements Fused Gromov-Wasserstein optimal transport for spatial transcriptomics
slice alignment, following:

  Zeira et al., "Alignment and integration of spatial transcriptomics data"
  Nature Methods, 2022. https://doi.org/10.1038/s41592-022-01459-6

Core idea:
  Jointly minimise:
    (1 - alpha) * expression_cost + alpha * spatial_structure_cost
  using Fused Gromov-Wasserstein (FGW) optimal transport.

Dependencies: numpy, scipy, pot (Python Optimal Transport)
"""
import logging
import numpy as np
import anndata as ad

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _to_dense(X) -> np.ndarray:
    """Safely convert sparse / dense matrix to float32 ndarray."""
    if hasattr(X, "toarray"):
        return X.toarray().astype(np.float32)
    return np.asarray(X, dtype=np.float32)


def _intersect_genes(s1: ad.AnnData, s2: ad.AnnData):
    """Return both slices restricted to their common gene set."""
    common = s1.var_names.intersection(s2.var_names)
    if len(common) == 0:
        raise ValueError("No common genes found between the two slices.")
    return s1[:, common].copy(), s2[:, common].copy()


def _filter_hvg(s1: ad.AnnData, s2: ad.AnnData, use_highly_variable: bool):
    """Optionally restrict genes to HVGs present in both slices."""
    if not use_highly_variable:
        return s1, s2
    # Only use HVGs that are flagged in BOTH slices
    if "highly_variable" in s1.var and "highly_variable" in s2.var:
        hvg1 = set(s1.var_names[s1.var["highly_variable"]])
        hvg2 = set(s2.var_names[s2.var["highly_variable"]])
        hvg = list(hvg1 & hvg2)
        if len(hvg) >= 10:                # minimum gene floor
            logger.info(f"Using {len(hvg)} highly-variable genes for alignment")
            return s1[:, hvg].copy(), s2[:, hvg].copy()
    logger.info("HVG filtering skipped (flags not present or too few shared HVGs)")
    return s1, s2


def _get_spatial(adata: ad.AnnData) -> np.ndarray:
    """Retrieve 2-D spatial coordinates."""
    for key in ("spatial", "X_spatial", "spatial_coords"):
        if key in adata.obsm:
            return adata.obsm[key][:, :2].astype(np.float64)
    raise ValueError(
        "No spatial coordinates found in obsm. "
        "Expected key 'spatial', 'X_spatial', or 'spatial_coords'."
    )


def _normalise_expr(X: np.ndarray) -> np.ndarray:
    """Row-normalise expression matrix (make each cell sum to 1)."""
    row_sum = X.sum(axis=1, keepdims=True)
    row_sum[row_sum == 0] = 1.0
    return X / row_sum


def _pairwise_distances(coords: np.ndarray) -> np.ndarray:
    """Euclidean distance matrix for a set of 2-D points."""
    diff = coords[:, None, :] - coords[None, :, :]
    return np.sqrt((diff**2).sum(-1))


# ─────────────────────────────────────────────────────────────────────────────
# Core alignment
# ─────────────────────────────────────────────────────────────────────────────

def pairwise_align_native(
    slice1: ad.AnnData,
    slice2: ad.AnnData,
    alpha: float = 0.1,
    use_highly_variable: bool = True,
    eps: float = 5e-2,
    max_iter: int = 1000,
) -> np.ndarray:
    """
    Compute the FGW-OT coupling matrix (pi) between two spatial slices.

    Parameters
    ----------
    slice1, slice2 : AnnData
        Spatial slices with .X (expression) and .obsm['spatial'].
    alpha : float
        Weight on the spatial structure term (0 = expression only,
        1 = spatial structure only). Recommended: 0.1–0.3.
    use_highly_variable : bool
        Restrict to shared HVGs if available.
    eps : float
        Entropic regularisation coefficient for Sinkhorn solver.
    max_iter : int
        Maximum iterations for the FGW solver.

    Returns
    -------
    pi : ndarray, shape (n1, n2)
        Optimal transport coupling matrix.
    """
    import ot  # Python Optimal Transport (pot)

    # 1. Align to shared genes then optionally restrict to HVGs
    s1, s2 = _intersect_genes(slice1, slice2)
    s1, s2 = _filter_hvg(s1, s2, use_highly_variable)

    # 2. Extract and normalise expression matrices
    X1 = _normalise_expr(_to_dense(s1.X))  # (n1, g)
    X2 = _normalise_expr(_to_dense(s2.X))  # (n2, g)

    n1, n2 = s1.n_obs, s2.n_obs
    logger.info(f"Aligning: n1={n1} spots, n2={n2} spots, genes={s1.n_vars}")

    # 3. Expression cost matrix  M[i,j] = -cos_similarity(x1_i, x2_j)
    # Use 1 - normalised inner product as cost (range [0,1], lower = more similar)
    norms1 = np.linalg.norm(X1, axis=1, keepdims=True) + 1e-8
    norms2 = np.linalg.norm(X2, axis=1, keepdims=True) + 1e-8
    X1n = X1 / norms1
    X2n = X2 / norms2
    M = 1.0 - (X1n @ X2n.T).astype(np.float64)  # (n1, n2)

    # 4. Uniform marginals
    p = np.ones(n1, dtype=np.float64) / n1
    q = np.ones(n2, dtype=np.float64) / n2

    if alpha == 0.0:
        # Pure expression OT (no spatial term)
        logger.info("alpha=0: running pure expression OT (no spatial)")
        pi = ot.emd(p, q, M)
        return pi

    # 5. Intra-slice spatial distance matrices (Gromov term)
    coords1 = _get_spatial(s1)
    coords2 = _get_spatial(s2)

    # Normalise coordinates to [0,1] to make alpha scale-independent
    def _norm_coords(c):
        span = c.max(axis=0) - c.min(axis=0)
        span[span == 0] = 1.0
        return (c - c.min(axis=0)) / span

    coords1 = _norm_coords(coords1)
    coords2 = _norm_coords(coords2)

    C1 = _pairwise_distances(coords1)  # (n1, n1)
    C2 = _pairwise_distances(coords2)  # (n2, n2)

    # 6. Fused Gromov-Wasserstein
    logger.info(f"Running FGW-OT (alpha={alpha}, eps={eps}, max_iter={max_iter})")
    pi = ot.fused_gromov_wasserstein(
        M,
        C1,
        C2,
        p,
        q,
        loss_fun="square_loss",
        alpha=alpha,
        armijo=False,
        symmetric=True,
        max_iter=max_iter,
        tol_rel=1e-9,
        tol_abs=1e-9,
        verbose=False,
    )

    logger.info("FGW-OT alignment complete")
    return pi


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def align_slices(
    slice1: ad.AnnData,
    slice2: ad.AnnData,
    alpha: float = 0.1,
    use_highly_variable: bool = True,
):
    """
    Align two spatial transcriptomics slices using PASTE (FGW-OT).

    Returns
    -------
    s1_aligned : AnnData  – slice 1 (unchanged)
    s2_aligned : AnnData  – slice 2 with coordinates projected into slice 1 space
    pi         : ndarray  – (n1, n2) coupling matrix
    """
    # Restrict to shared genes first for the returned objects
    s1, s2 = _intersect_genes(slice1, slice2)

    pi = pairwise_align_native(
        slice1, slice2,
        alpha=alpha,
        use_highly_variable=use_highly_variable,
    )

    # ── Project slice-2 spots onto slice-1 space via the coupling matrix ──────
    # For each slice-2 spot j, its new position = weighted average of
    #   slice-1 positions, weights = pi[:, j] / pi[:, j].sum()
    new_s2 = s2.copy()
    try:
        coords1 = _get_spatial(s1)
        pi_norm = pi / (pi.sum(axis=0, keepdims=True) + 1e-300)  # (n1, n2)
        aligned_coords = coords1.T @ pi_norm                     # (2, n2)
        new_s2.obsm["spatial"] = aligned_coords.T.astype(np.float32)
        logger.info("Spatial coordinates of slice 2 projected into slice 1 space")
    except Exception as e:
        logger.warning(f"Coordinate projection skipped: {e}")

    # Store coupling matrix in .uns for downstream use
    new_s2.uns["paste_pi"] = pi
    s1.uns["paste_pi"] = pi

    return s1, new_s2, pi
