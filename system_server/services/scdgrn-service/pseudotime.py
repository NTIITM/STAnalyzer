#!/usr/bin/env python3
"""
Pseudo-time calculation module for single-cell data
Supports multiple methods to segment cells into time points based on pseudo-time values:
- kmeans: KMeans clustering with automatic cluster number selection
- equal_width: Equal-width binning
- equal_frequency: Equal-frequency binning (quantile-based)
- density: Density-based binning using KDE
- gmm: Gaussian Mixture Model clustering

Also supports computing pseudo-time from scratch using:
- dpt: Diffusion Pseudotime (DPT) using scanpy
- pca_trajectory: PCA-based trajectory inference
"""
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.mixture import GaussianMixture
from sklearn.metrics import davies_bouldin_score
from sklearn.decomposition import PCA
from scipy.stats import gaussian_kde
from scipy.sparse import issparse
from typing import List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

try:
    import scanpy as sc
    SCANPY_AVAILABLE = True
except ImportError:
    SCANPY_AVAILABLE = False
    logger.warning("scanpy not available. DPT method will not work.")


def calculate_pseudotime_kmeans(
    pseudo_time_values: np.ndarray,
    max_clusters: int = 6,
    min_clusters: int = 2,
    apply_sqrt_transform: bool = True
) -> Tuple[np.ndarray, int]:
    """
    Calculate time point assignments using KMeans clustering on pseudo-time values
    
    Args:
        pseudo_time_values: 1D array of pseudo-time values for each cell
        max_clusters: Maximum number of clusters to test
        min_clusters: Minimum number of clusters to test
        apply_sqrt_transform: Whether to apply square root transformation if range >= 1
    
    Returns:
        Tuple of (cluster_labels, optimal_n_clusters)
        - cluster_labels: Array of cluster labels (time points) for each cell
        - optimal_n_clusters: Optimal number of clusters determined by DB index
    """
    logger.info(f"Calculating pseudo-time clusters from {len(pseudo_time_values)} cells")
    
    # Apply square root transformation if needed
    if apply_sqrt_transform:
        time_range = np.max(pseudo_time_values) - np.min(pseudo_time_values)
        if time_range == 1 or time_range > 1:
            pseudo_time_values = np.sqrt(np.array(pseudo_time_values))
            logger.info("Applied square root transformation to pseudo-time values")
    
    # Reshape to 2D for KMeans
    pseudo_time_2d = pseudo_time_values.reshape(-1, 1)
    
    # Find optimal number of clusters using Davies-Bouldin index
    db_scores = {}
    for n_clusters in range(min_clusters, max_clusters + 1):
        # Initialize cluster centers based on pseudo-time distribution
        init_centers = np.array([
            [pseudo_time_values[int(np.floor(i))]] 
            for i in np.linspace(0, len(pseudo_time_values) - 1, n_clusters)
        ])
        
        kmeans = KMeans(n_clusters=n_clusters, init=init_centers, n_init=1, random_state=42)
        kmeans.fit(pseudo_time_2d)
        labels = kmeans.labels_
        
        # Calculate DB index
        db_score = davies_bouldin_score(pseudo_time_2d, labels)
        db_scores[n_clusters] = db_score
        logger.info(f"  n_clusters={n_clusters}: DB index={db_score:.4f}")
    
    # Find optimal number of clusters (minimum DB index)
    optimal_n_clusters = min(db_scores, key=db_scores.get)
    best_db_score = db_scores[optimal_n_clusters]
    logger.info(f"Optimal number of clusters: {optimal_n_clusters} (DB index: {best_db_score:.4f})")
    
    # Perform final clustering with optimal number of clusters
    init_centers = np.array([
        [pseudo_time_values[int(np.floor(i))]] 
        for i in np.linspace(0, len(pseudo_time_values) - 1, optimal_n_clusters)
    ])
    kmeans = KMeans(n_clusters=optimal_n_clusters, init=init_centers, n_init=1, random_state=42)
    kmeans.fit(pseudo_time_2d)
    cluster_labels = kmeans.labels_
    
    # Sort clusters by their mean pseudo-time value to ensure temporal ordering
    cluster_means = {}
    for cluster_id in range(optimal_n_clusters):
        mask = cluster_labels == cluster_id
        cluster_means[cluster_id] = np.mean(pseudo_time_values[mask])
    
    # Create mapping from old cluster ID to new time point ID (sorted by mean pseudo-time)
    sorted_clusters = sorted(cluster_means.items(), key=lambda x: x[1])
    cluster_mapping = {old_id: new_id for new_id, (old_id, _) in enumerate(sorted_clusters)}
    
    # Remap labels to ensure temporal ordering
    time_point_labels = np.array([cluster_mapping[label] for label in cluster_labels])
    
    logger.info(f"Cluster centers: {kmeans.cluster_centers_.flatten()}")
    logger.info(f"Time point distribution: {dict(zip(*np.unique(time_point_labels, return_counts=True)))}")
    
    return time_point_labels, optimal_n_clusters


def calculate_pseudotime_equal_width(
    pseudo_time_values: np.ndarray,
    n_bins: int = 6
) -> Tuple[np.ndarray, int]:
    """
    Calculate time point assignments using equal-width binning
    
    Args:
        pseudo_time_values: 1D array of pseudo-time values for each cell
        n_bins: Number of bins (time points) to create
    
    Returns:
        Tuple of (bin_labels, n_bins)
        - bin_labels: Array of bin labels (time points) for each cell
        - n_bins: Number of bins used
    """
    logger.info(f"Calculating pseudo-time bins using equal-width method with {n_bins} bins")
    
    # Create equal-width bins
    bin_edges = np.linspace(
        np.min(pseudo_time_values),
        np.max(pseudo_time_values),
        n_bins + 1
    )
    
    # Assign each cell to a bin
    bin_labels = np.digitize(pseudo_time_values, bin_edges) - 1
    
    # Handle edge case: last value might be exactly at max, assign to last bin
    bin_labels[bin_labels == n_bins] = n_bins - 1
    bin_labels[bin_labels < 0] = 0
    
    logger.info(f"Bin edges: {bin_edges}")
    logger.info(f"Time point distribution: {dict(zip(*np.unique(bin_labels, return_counts=True)))}")
    
    return bin_labels, n_bins


def calculate_pseudotime_equal_frequency(
    pseudo_time_values: np.ndarray,
    n_bins: int = 6
) -> Tuple[np.ndarray, int]:
    """
    Calculate time point assignments using equal-frequency binning (quantile-based)
    
    Args:
        pseudo_time_values: 1D array of pseudo-time values for each cell
        n_bins: Number of bins (time points) to create
    
    Returns:
        Tuple of (bin_labels, n_bins)
        - bin_labels: Array of bin labels (time points) for each cell
        - n_bins: Number of bins used
    """
    logger.info(f"Calculating pseudo-time bins using equal-frequency method with {n_bins} bins")
    
    # Calculate quantile edges
    quantiles = np.linspace(0, 100, n_bins + 1)
    bin_edges = np.percentile(pseudo_time_values, quantiles)
    
    # Ensure unique bin edges (handle duplicate values)
    unique_edges = []
    for edge in bin_edges:
        if len(unique_edges) == 0 or edge > unique_edges[-1]:
            unique_edges.append(edge)
        else:
            unique_edges.append(unique_edges[-1] + 1e-10)
    bin_edges = np.array(unique_edges)
    
    # Assign each cell to a bin
    bin_labels = np.digitize(pseudo_time_values, bin_edges) - 1
    
    # Handle edge cases
    bin_labels[bin_labels == len(bin_edges) - 1] = len(bin_edges) - 2
    bin_labels[bin_labels < 0] = 0
    
    # Ensure we have exactly n_bins
    if len(np.unique(bin_labels)) < n_bins:
        # Redistribute cells to ensure n_bins
        sorted_indices = np.argsort(pseudo_time_values)
        cells_per_bin = len(pseudo_time_values) // n_bins
        bin_labels = np.zeros(len(pseudo_time_values), dtype=int)
        for i in range(n_bins):
            start_idx = i * cells_per_bin
            end_idx = (i + 1) * cells_per_bin if i < n_bins - 1 else len(pseudo_time_values)
            bin_labels[sorted_indices[start_idx:end_idx]] = i
    
    logger.info(f"Quantile edges: {bin_edges}")
    logger.info(f"Time point distribution: {dict(zip(*np.unique(bin_labels, return_counts=True)))}")
    
    return bin_labels, n_bins


def calculate_pseudotime_density(
    pseudo_time_values: np.ndarray,
    n_bins: int = 6,
    bandwidth: Optional[float] = None
) -> Tuple[np.ndarray, int]:
    """
    Calculate time point assignments using density-based binning with KDE
    
    Args:
        pseudo_time_values: 1D array of pseudo-time values for each cell
        n_bins: Number of bins (time points) to create
        bandwidth: Bandwidth for KDE (if None, uses automatic selection)
    
    Returns:
        Tuple of (bin_labels, n_bins)
        - bin_labels: Array of bin labels (time points) for each cell
        - n_bins: Number of bins used
    """
    logger.info(f"Calculating pseudo-time bins using density-based method with {n_bins} bins")
    
    # Fit KDE
    try:
        kde = gaussian_kde(pseudo_time_values, bw_method=bandwidth)
    except Exception as e:
        logger.warning(f"KDE fitting failed: {e}. Falling back to equal-width binning.")
        return calculate_pseudotime_equal_width(pseudo_time_values, n_bins)
    
    # Evaluate density at evenly spaced points
    x_eval = np.linspace(
        np.min(pseudo_time_values),
        np.max(pseudo_time_values),
        1000
    )
    density = kde(x_eval)
    
    # Find local minima in density to use as bin boundaries
    # Use a simple approach: divide by density-weighted quantiles
    # Create bins based on cumulative density
    cumulative_density = np.cumsum(density)
    cumulative_density = cumulative_density / cumulative_density[-1]
    
    # Find quantile positions in cumulative density
    quantile_positions = np.linspace(0, 1, n_bins + 1)
    bin_edges_indices = []
    for q in quantile_positions:
        idx = np.argmin(np.abs(cumulative_density - q))
        bin_edges_indices.append(idx)
    
    bin_edges = x_eval[np.array(bin_edges_indices)]
    
    # Assign cells to bins
    bin_labels = np.digitize(pseudo_time_values, bin_edges) - 1
    bin_labels[bin_labels == n_bins] = n_bins - 1
    bin_labels[bin_labels < 0] = 0
    
    logger.info(f"Density-based bin edges: {bin_edges}")
    logger.info(f"Time point distribution: {dict(zip(*np.unique(bin_labels, return_counts=True)))}")
    
    return bin_labels, n_bins


def calculate_pseudotime_gmm(
    pseudo_time_values: np.ndarray,
    max_components: int = 6,
    min_components: int = 2
) -> Tuple[np.ndarray, int]:
    """
    Calculate time point assignments using Gaussian Mixture Model clustering
    
    Args:
        pseudo_time_values: 1D array of pseudo-time values for each cell
        max_components: Maximum number of components to test
        min_components: Minimum number of components to test
    
    Returns:
        Tuple of (component_labels, optimal_n_components)
        - component_labels: Array of component labels (time points) for each cell
        - optimal_n_components: Optimal number of components determined by BIC
    """
    logger.info(f"Calculating pseudo-time clusters using GMM from {len(pseudo_time_values)} cells")
    
    # Reshape to 2D for GMM
    pseudo_time_2d = pseudo_time_values.reshape(-1, 1)
    
    # Find optimal number of components using BIC
    bic_scores = {}
    for n_components in range(min_components, max_components + 1):
        gmm = GaussianMixture(
            n_components=n_components,
            random_state=42,
            covariance_type='full'
        )
        gmm.fit(pseudo_time_2d)
        bic = gmm.bic(pseudo_time_2d)
        bic_scores[n_components] = bic
        logger.info(f"  n_components={n_components}: BIC={bic:.4f}")
    
    # Find optimal number of components (minimum BIC)
    optimal_n_components = min(bic_scores, key=bic_scores.get)
    best_bic = bic_scores[optimal_n_components]
    logger.info(f"Optimal number of components: {optimal_n_components} (BIC: {best_bic:.4f})")
    
    # Perform final GMM with optimal number of components
    gmm = GaussianMixture(
        n_components=optimal_n_components,
        random_state=42,
        covariance_type='full'
    )
    gmm.fit(pseudo_time_2d)
    component_labels = gmm.predict(pseudo_time_2d)
    
    # Sort components by their mean pseudo-time value to ensure temporal ordering
    component_means = {}
    for component_id in range(optimal_n_components):
        mask = component_labels == component_id
        component_means[component_id] = np.mean(pseudo_time_values[mask])
    
    # Create mapping from old component ID to new time point ID (sorted by mean pseudo-time)
    sorted_components = sorted(component_means.items(), key=lambda x: x[1])
    component_mapping = {old_id: new_id for new_id, (old_id, _) in enumerate(sorted_components)}
    
    # Remap labels to ensure temporal ordering
    time_point_labels = np.array([component_mapping[label] for label in component_labels])
    
    logger.info(f"Component means: {[component_means[i] for i in range(optimal_n_components)]}")
    logger.info(f"Time point distribution: {dict(zip(*np.unique(time_point_labels, return_counts=True)))}")
    
    return time_point_labels, optimal_n_components


def compute_pseudotime_dpt(
    adata,
    n_neighbors: int = 15,
    n_pcs: int = 40,
    root_cell: Optional[int] = None,
    use_rep: Optional[str] = None
) -> np.ndarray:
    """
    Compute pseudo-time using Diffusion Pseudotime (DPT) method from scanpy
    
    Args:
        adata: AnnData object
        n_neighbors: Number of neighbors for kNN graph
        n_pcs: Number of principal components to use
        root_cell: Index of root cell (if None, automatically selects cell with minimum expression)
        use_rep: Representation to use ('X_pca', 'X', etc.). If None, computes PCA if needed.
    
    Returns:
        Array of pseudo-time values for each cell
    """
    if not SCANPY_AVAILABLE:
        raise ImportError("scanpy is required for DPT method. Please install scanpy.")
    
    logger.info("Computing pseudo-time using DPT method...")
    
    # Store original state
    adata.uns['original_neighbors'] = 'neighbors' in adata.uns
    
    # Preprocess if needed
    if use_rep is None:
        # Check if PCA exists
        if 'X_pca' not in adata.obsm.keys():
            logger.info("Computing PCA...")
            sc.pp.pca(adata, n_comps=min(n_pcs, adata.n_vars, adata.n_obs - 1))
        use_rep = 'X_pca'
    
    # Compute neighbors graph if not exists
    if 'neighbors' not in adata.uns:
        logger.info(f"Computing kNN graph with {n_neighbors} neighbors...")
        sc.pp.neighbors(adata, n_neighbors=n_neighbors, n_pcs=n_pcs, use_rep=use_rep)
    
    # Select root cell if not provided
    if root_cell is None:
        # Use cell with minimum total expression as root
        if issparse(adata.X):
            total_expr = np.array(adata.X.sum(axis=1)).flatten()
        else:
            total_expr = adata.X.sum(axis=1)
        root_cell = int(np.argmin(total_expr))
        logger.info(f"Automatically selected root cell {root_cell} (minimum expression)")
    
    # Compute DPT
    logger.info(f"Computing DPT with root cell {root_cell}...")
    sc.tl.dpt(adata, n_dcs=10)
    
    # Get pseudo-time values
    if 'dpt_pseudotime' in adata.obs.columns:
        pseudotime = adata.obs['dpt_pseudotime'].values
    else:
        # Fallback: use diffusion distances
        logger.warning("dpt_pseudotime not found, using diffusion distances")
        if 'X_diffmap' in adata.obsm:
            # Use first diffusion component as pseudo-time
            pseudotime = adata.obsm['X_diffmap'][:, 0]
            # Normalize to [0, 1]
            pseudotime = (pseudotime - pseudotime.min()) / (pseudotime.max() - pseudotime.min() + 1e-10)
        else:
            raise ValueError("Could not compute DPT. Please check scanpy installation and data format.")
    
    logger.info(f"Computed pseudo-time: min={pseudotime.min():.4f}, max={pseudotime.max():.4f}, mean={pseudotime.mean():.4f}")
    
    return pseudotime


def compute_pseudotime_pca_trajectory(
    adata,
    n_pcs: int = 50,
    root_cell: Optional[int] = None
) -> np.ndarray:
    """
    Compute pseudo-time using PCA-based trajectory inference
    
    Args:
        adata: AnnData object
        n_pcs: Number of principal components to use
        root_cell: Index of root cell (if None, automatically selects cell with minimum PC1)
    
    Returns:
        Array of pseudo-time values for each cell
    """
    logger.info("Computing pseudo-time using PCA-based trajectory method...")
    
    # Get expression matrix
    if issparse(adata.X):
        X = adata.X.toarray()
    else:
        X = adata.X
    
    # Compute PCA
    logger.info(f"Computing PCA with {n_pcs} components...")
    pca = PCA(n_components=min(n_pcs, X.shape[1], X.shape[0] - 1))
    X_pca = pca.fit_transform(X)
    
    # Select root cell if not provided
    if root_cell is None:
        # Use cell with minimum PC1 as root
        root_cell = int(np.argmin(X_pca[:, 0]))
        logger.info(f"Automatically selected root cell {root_cell} (minimum PC1)")
    
    # Compute distances from root cell in PCA space
    root_pc = X_pca[root_cell, :]
    distances = np.sqrt(((X_pca - root_pc) ** 2).sum(axis=1))
    
    # Normalize to [0, 1]
    pseudotime = (distances - distances.min()) / (distances.max() - distances.min() + 1e-10)
    
    logger.info(f"Computed pseudo-time: min={pseudotime.min():.4f}, max={pseudotime.max():.4f}, mean={pseudotime.mean():.4f}")
    
    return pseudotime


def segment_cells_by_pseudotime(
    adata,
    pseudo_time_column: str = "pseudotime",
    method: str = "kmeans",
    max_clusters: int = 6,
    min_clusters: int = 2,
    n_bins: int = 6,
    bandwidth: Optional[float] = None,
    time_column_name: str = "time",
    compute_pseudotime: bool = True,
    pseudotime_compute_method: str = "dpt",
    n_neighbors: int = 15,
    n_pcs: int = 40
) -> None:
    """
    Segment cells into time points based on pseudo-time values and add time column to adata.obs
    
    Args:
        adata: AnnData object
        pseudo_time_column: Column name in obs containing pseudo-time values
        method: Method to use for segmenting cells:
            - 'none': Use existing time column
            - 'kmeans': KMeans clustering with automatic cluster number selection
            - 'equal_width': Equal-width binning
            - 'equal_frequency': Equal-frequency binning (quantile-based)
            - 'density': Density-based binning using KDE
            - 'gmm': Gaussian Mixture Model clustering
        max_clusters: Maximum number of clusters/components (for kmeans, gmm)
        min_clusters: Minimum number of clusters/components (for kmeans, gmm)
        n_bins: Number of bins/time points (for equal_width, equal_frequency, density)
        bandwidth: Bandwidth for KDE in density method (None for automatic)
        time_column_name: Name of the time column to add/update in obs
        compute_pseudotime: If True, compute pseudo-time from data if not present
        pseudotime_compute_method: Method to compute pseudo-time if not present:
            - 'dpt': Diffusion Pseudotime (requires scanpy)
            - 'pca_trajectory': PCA-based trajectory inference
        n_neighbors: Number of neighbors for DPT method
        n_pcs: Number of principal components for DPT/PCA methods
    
    Returns:
        None (modifies adata in place)
    """
    if method == "none":
        logger.info("Using existing time column, skipping pseudo-time calculation")
        return
    
    # Check if pseudo-time column exists
    if pseudo_time_column not in adata.obs.columns:
        if compute_pseudotime:
            # Compute pseudo-time from data
            logger.info(
                f"Pseudo-time column '{pseudo_time_column}' not found. "
                f"Computing pseudo-time using {pseudotime_compute_method} method..."
            )
            if pseudotime_compute_method == "dpt":
                pseudo_time_values = compute_pseudotime_dpt(
                    adata,
                    n_neighbors=n_neighbors,
                    n_pcs=n_pcs
                )
            elif pseudotime_compute_method == "pca_trajectory":
                pseudo_time_values = compute_pseudotime_pca_trajectory(
                    adata,
                    n_pcs=n_pcs
                )
            else:
                raise ValueError(
                    f"Unknown pseudo-time computation method: {pseudotime_compute_method}. "
                    f"Supported methods: 'dpt', 'pca_trajectory'"
                )
            # Store computed pseudo-time
            adata.obs[pseudo_time_column] = pseudo_time_values
            logger.info(f"Computed and stored pseudo-time in obs['{pseudo_time_column}']")
        else:
            # If pseudo-time column doesn't exist, try to use time column as pseudo-time
            if time_column_name in adata.obs.columns:
                logger.info(
                    f"Pseudo-time column '{pseudo_time_column}' not found. "
                    f"Using '{time_column_name}' column values as pseudo-time values."
                )
                # Use time column values as pseudo-time values
                pseudo_time_values = adata.obs[time_column_name].values.astype(float)
                # Store in pseudo_time_column for consistency
                adata.obs[pseudo_time_column] = pseudo_time_values
            else:
                raise ValueError(
                    f"Pseudo-time column '{pseudo_time_column}' not found in adata.obs, "
                    f"and time column '{time_column_name}' is also not available. "
                    f"Set compute_pseudotime=True to compute pseudo-time from data. "
                    f"Available columns: {list(adata.obs.columns)}"
                )
    else:
        # Get pseudo-time values
        pseudo_time_values = adata.obs[pseudo_time_column].values
    
    # Calculate time point assignments based on method
    if method == "kmeans":
        time_point_labels, n_time_points = calculate_pseudotime_kmeans(
            pseudo_time_values,
            max_clusters=max_clusters,
            min_clusters=min_clusters
        )
    elif method == "equal_width":
        time_point_labels, n_time_points = calculate_pseudotime_equal_width(
            pseudo_time_values,
            n_bins=n_bins
        )
    elif method == "equal_frequency":
        time_point_labels, n_time_points = calculate_pseudotime_equal_frequency(
            pseudo_time_values,
            n_bins=n_bins
        )
    elif method == "density":
        time_point_labels, n_time_points = calculate_pseudotime_density(
            pseudo_time_values,
            n_bins=n_bins,
            bandwidth=bandwidth
        )
    elif method == "gmm":
        time_point_labels, n_time_points = calculate_pseudotime_gmm(
            pseudo_time_values,
            max_components=max_clusters,
            min_components=min_clusters
        )
    else:
        raise ValueError(
            f"Unknown pseudo-time method: {method}. "
            f"Supported methods: 'none', 'kmeans', 'equal_width', 'equal_frequency', 'density', 'gmm'"
        )
    
    # Add time column to obs
    adata.obs[time_column_name] = time_point_labels
    
    logger.info(
        f"Assigned {len(adata.obs)} cells to {n_time_points} time points "
        f"based on pseudo-time values using {method} method"
    )

