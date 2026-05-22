#!/usr/bin/env python3
"""
scDGRN Gene Regulatory Network Discovery Service
Dynamic gene regulatory network discovery from time-series single-cell transcriptomics data
using GTransformer model
"""
import os
# GPU visibility configuration - must be set before importing PyTorch
# If NVIDIA_VISIBLE_DEVICES is set, use it to limit CUDA visible devices
nvidia_visible_devices = os.getenv("NVIDIA_VISIBLE_DEVICES")
if nvidia_visible_devices and nvidia_visible_devices != "all":
    # Set CUDA_VISIBLE_DEVICES for PyTorch to respect GPU visibility
    os.environ["CUDA_VISIBLE_DEVICES"] = nvidia_visible_devices

import tempfile
import uuid
import logging
from typing import Dict, List, Optional
import warnings

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError

# Import PyTorch and data processing libraries
import torch
import torch.nn.functional as F
from torch.optim import Adam
from torch.utils.data import DataLoader, TensorDataset
import pandas as pd
import numpy as np
import anndata as ad
import networkx as nx
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import matplotlib.patches as mpatches

# Import scDGRN model and utilities
try:
    from gTrans_dgrn import GTransformer
    from utils import scRNADataset, load_data, adj2saprse_tensor
    from pseudotime import segment_cells_by_pseudotime
except ImportError as e:
    raise ImportError(f"Failed to import gTrans_dgrn, utils, or pseudotime: {e}")

warnings.filterwarnings("ignore")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="scDGRN Gene Regulatory Network Discovery Service",
    description="Dynamic gene regulatory network discovery from time-series single-cell transcriptomics data using scDGRN",
    version="1.0.0",
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle request validation errors and log detailed information"""
    error_details = exc.errors()
    error_body = exc.body if hasattr(exc, 'body') else None
    logger.error(
        "Request validation failed (422): %s %s\nError details: %s\nRequest body (first 500 chars): %s",
        request.method,
        request.url.path,
        error_details,
        str(error_body)[:500] if error_body else None,
        exc_info=True
    )
    
    # Format error details for better readability
    formatted_errors = []
    for error in error_details:
        field = ".".join(str(loc) for loc in error.get("loc", []))
        msg = error.get("msg", "Validation error")
        error_type = error.get("type", "unknown")
        formatted_errors.append({
            "field": field,
            "message": msg,
            "type": error_type
        })
    
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "message": "Request parameter validation failed",
            "error": {
                "error_type": "RequestValidationError",
                "error_message": "One or more request parameters are invalid",
                "details": formatted_errors,
                "suggestion": "Please check the API documentation and ensure all required parameters are provided with correct types and values."
            },
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with detailed error information"""
    logger.error(
        "HTTP exception (%d): %s %s\nDetail: %s",
        exc.status_code,
        request.method,
        request.url.path,
        exc.detail,
        exc_info=True
    )
    
    # If detail is already a dict, return it as is; otherwise wrap it
    if isinstance(exc.detail, dict):
        error_content = exc.detail
    else:
        error_content = {
            "error_type": "HTTPException",
            "error_message": str(exc.detail),
            "status_code": exc.status_code
        }
    
    # Build a detailed message from error_content
    error_type = error_content.get("error_type", "UnknownError")
    error_message = error_content.get("error_message", str(exc.detail))
    detailed_message = f"{error_type}: {error_message}"
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": detailed_message,
            "error": error_content
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle all other unhandled exceptions"""
    logger.error(
        "Unhandled exception: %s %s\nException: %s",
        request.method,
        request.url.path,
        str(exc),
        exc_info=True
    )
    
    error_type = type(exc).__name__
    error_message = str(exc)
    detailed_message = f"{error_type}: {error_message}"
    
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": detailed_message,
            "error": {
                "error_type": error_type,
                "error_message": error_message,
                "suggestion": "Please check the server logs for more details. If the problem persists, please contact the administrator."
            }
        }
    )


# Output directory
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Log GPU visibility configuration
if nvidia_visible_devices and nvidia_visible_devices != "all":
    logger.info(f"GPU visibility limited to devices: {nvidia_visible_devices} (CUDA_VISIBLE_DEVICES={os.getenv('CUDA_VISIBLE_DEVICES')})")

# Device configuration
DEVICE = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')

# Default model configuration
DEFAULT_CONFIG = {
    "input_dim": 85,
    "hidden_dim": [128, 64, 32],
    "output_dim": 16,
    "num_head": [3, 3],
    "alpha": 0.2,
    "type": "dot",
    "reduction": "concate",
    "learning_rate": 3e-3,
    "epochs": 5,
    "batch_size": 512,
    "inference_batch_size": 10000,  # Batch size for inference to reduce memory usage
    "top_percent_threshold": 0.2,
    "loop": False,
    "seed": 8,
}


def read_h5ad_file(
    file_path: str, 
    time_column: str = "time",
    pseudotime_method: str = "none",
    pseudotime_column: str = "pseudotime",
    max_clusters: int = 6,
    min_clusters: int = 2,
    n_bins: int = 6,
    bandwidth: Optional[float] = None,
    compute_pseudotime: bool = True,
    pseudotime_compute_method: str = "dpt",
    n_neighbors: int = 15,
    n_pcs: int = 40,
    time_order: Optional[str] = None
) -> tuple:
    """
    Read h5ad file and extract time-series expression data
    
    Args:
        file_path: Path to h5ad file
        time_column: Column name in obs containing time point information
        pseudotime_method: Method for pseudo-time segmentation:
            - 'none': Use existing time column
            - 'kmeans': KMeans clustering
            - 'equal_width': Equal-width binning
            - 'equal_frequency': Equal-frequency binning
            - 'density': Density-based binning
            - 'gmm': Gaussian Mixture Model
        pseudotime_column: Column name in obs containing pseudo-time values
        max_clusters: Maximum number of clusters/components (for kmeans, gmm)
        min_clusters: Minimum number of clusters/components (for kmeans, gmm)
        n_bins: Number of bins/time points (for equal_width, equal_frequency, density)
        bandwidth: Bandwidth for KDE in density method (None for automatic)
        compute_pseudotime: If True, compute pseudo-time from data if not present
        pseudotime_compute_method: Method to compute pseudo-time if not present:
            - 'dpt': Diffusion Pseudotime (requires scanpy)
            - 'pca_trajectory': PCA-based trajectory inference
        n_neighbors: Number of neighbors for DPT method
        n_pcs: Number of principal components for DPT/PCA methods
        time_order: Optional string specifying time order (comma-separated, e.g., "E10.5,E12.5,E14.5").
                   If None, uses default sorting. If provided, only time points in this list will be used.
    
    Returns:
        Tuple of (List of expression dataframes, AnnData object, List of time values)
    """
    logger.info(f"Reading h5ad file: {file_path}")
    adata = ad.read_h5ad(file_path)
    
    # Apply pseudo-time segmentation if method is specified
    if pseudotime_method != "none":
        logger.info(f"Applying pseudo-time segmentation using method: {pseudotime_method}")
        segment_cells_by_pseudotime(
            adata,
            pseudo_time_column=pseudotime_column,
            method=pseudotime_method,
            max_clusters=max_clusters,
            min_clusters=min_clusters,
            n_bins=n_bins,
            bandwidth=bandwidth,
            time_column_name=time_column,
            compute_pseudotime=compute_pseudotime,
            pseudotime_compute_method=pseudotime_compute_method,
            n_neighbors=n_neighbors,
            n_pcs=n_pcs
        )
    
    # Check if time information is in obs
    if time_column in adata.obs.columns:
        logger.info(f"Found time information in obs['{time_column}']")
        # Filter out NaN values and convert to list for sorting
        unique_values = adata.obs[time_column].unique()
        # Remove NaN values
        available_time_values = [v for v in unique_values if pd.notna(v)]
        
        if len(available_time_values) == 0:
            raise ValueError(
                f"Time column '{time_column}' exists but contains no valid (non-NaN) values. "
                f"Please check your data or specify a different time_column."
            )
        
        # Handle time_order parameter
        if time_order:
            # Parse time_order string into list
            if not isinstance(time_order, str) or not time_order.strip():
                raise ValueError(
                    f"time_order parameter must be a non-empty comma-separated string. "
                    f"Received: {repr(time_order)}"
                )
            
            time_order_list = [t.strip() for t in time_order.split(',') if t.strip()]
            
            if len(time_order_list) == 0:
                raise ValueError(
                    f"time_order parameter is empty or contains no valid values after parsing. "
                    f"Expected format: comma-separated string (e.g., 'E10.5,E12.5,E14.5'). "
                    f"Received: {repr(time_order)}"
                )
            
            # Check which values in time_order exist in data
            missing_values = [v for v in time_order_list if v not in available_time_values]
            if missing_values:
                raise ValueError(
                    f"The following time values specified in time_order do not exist in the data: {missing_values}. "
                    f"Available time values in column '{time_column}': {sorted(available_time_values)}. "
                    f"Please check your time_order parameter and ensure all values match the data."
                )
            
            # Filter to only include time values that exist in data and are in time_order
            time_values = [v for v in time_order_list if v in available_time_values]
            
            # Add any remaining time values that are not in time_order (at the end)
            remaining = [v for v in available_time_values if v not in time_order_list]
            if remaining:
                # Sort remaining values and append
                try:
                    # Try numeric sorting first
                    remaining_sorted = sorted(remaining, key=lambda x: float(x) if isinstance(x, (int, float)) or (isinstance(x, str) and x.replace('.', '').replace('-', '').isdigit()) else x)
                except:
                    # Fall back to string sorting
                    remaining_sorted = sorted(remaining)
                time_values.extend(remaining_sorted)
                logger.warning(
                    f"Some time values in the data are not in time_order and will be appended: {remaining_sorted}. "
                    f"Specified time_order: {time_order_list}"
                )
            
            if len(time_values) == 0:
                raise ValueError(
                    f"No valid time values found after processing time_order. "
                    f"This should not happen if validation passed. Please report this error."
                )
            
            logger.info(f"Using time order: {time_values}")
        else:
            # Default sorting: try numeric first, then string
            try:
                # Try to convert to numeric for sorting
                time_values = sorted(available_time_values, key=lambda x: float(x) if isinstance(x, (int, float)) or (isinstance(x, str) and x.replace('.', '').replace('-', '').isdigit()) else x)
            except:
                # Fall back to string sorting
                time_values = sorted(available_time_values)
            logger.info(f"Using default time order: {time_values}")
        
        expression_dfs = []
        actual_time_values = []  # Store actual time values that have data
        
        for time_val in time_values:
            time_mask = adata.obs[time_column] == time_val
            time_adata = adata[time_mask]
            
            # Skip empty time points
            if time_adata.n_obs == 0:
                logger.warning(f"Time point {time_val} has no cells, skipping...")
                continue
            
            # Convert to dense if sparse
            if hasattr(time_adata.X, 'toarray'):
                expr_matrix = time_adata.X.toarray()
            else:
                expr_matrix = time_adata.X
            
            # Create dataframe: rows are genes, columns are cells
            df = pd.DataFrame(
                expr_matrix.T,
                index=time_adata.var_names,
                columns=time_adata.obs_names
            )
            expression_dfs.append(df)
            actual_time_values.append(time_val)  # Store the actual time value
            logger.info(f"Time point {time_val}: {df.shape[0]} genes, {df.shape[1]} cells")
        
        if len(expression_dfs) == 0:
            raise ValueError(
                f"No time points with valid data found. All time points in column '{time_column}' have zero cells. "
                f"Available time values: {sorted(available_time_values)}. "
                f"Please check your data and ensure at least one time point has cells."
            )
        
        return expression_dfs, adata, actual_time_values
    
    # Check if time information is in layers
    elif hasattr(adata, 'layers') and adata.layers:
        logger.info("Found time information in layers")
        available_layer_names = [k for k in adata.layers.keys() if 'time' in k.lower() or k.isdigit()]
        
        if not available_layer_names:
            # If no time-specific layers, assume layers represent time points
            available_layer_names = list(adata.layers.keys())
        
        if len(available_layer_names) == 0:
            raise ValueError(
                f"No layers found in the data. Cannot extract time-series information from layers. "
                f"Please ensure your h5ad file contains layers or specify a time_column in obs metadata."
            )
        
        # Handle time_order parameter for layers
        if time_order:
            # Normalize: convert empty string to None
            if isinstance(time_order, str) and not time_order.strip():
                time_order = None
        
        if time_order:
            # Parse time_order string into list
            if not isinstance(time_order, str):
                raise ValueError(
                    f"time_order parameter must be a non-empty comma-separated string. "
                    f"Received: {repr(time_order)} (type: {type(time_order).__name__})"
                )
            
            time_order_list = [t.strip() for t in time_order.split(',') if t.strip()]
            
            if len(time_order_list) == 0:
                raise ValueError(
                    f"time_order parameter is empty or contains no valid values after parsing. "
                    f"Expected format: comma-separated string (e.g., 'layer1,layer2,layer3'). "
                    f"Received: {repr(time_order)}"
                )
            
            # Check which values in time_order exist in data
            missing_values = [v for v in time_order_list if v not in available_layer_names]
            if missing_values:
                raise ValueError(
                    f"The following layer names specified in time_order do not exist in the data: {missing_values}. "
                    f"Available layer names: {sorted(available_layer_names)}. "
                    f"Please check your time_order parameter and ensure all values match the layer names."
                )
            
            # Filter to only include layer names that exist and are in time_order
            layer_names = [v for v in time_order_list if v in available_layer_names]
            
            # Add any remaining layer names that are not in time_order (at the end)
            remaining = [v for v in available_layer_names if v not in time_order_list]
            if remaining:
                # Sort remaining values and append
                try:
                    # Try numeric sorting first
                    remaining_sorted = sorted(remaining, key=lambda x: float(x) if isinstance(x, (int, float)) or (isinstance(x, str) and x.replace('.', '').replace('-', '').isdigit()) else x)
                except:
                    # Fall back to string sorting
                    remaining_sorted = sorted(remaining)
                layer_names.extend(remaining_sorted)
                logger.warning(
                    f"Some layer names in the data are not in time_order and will be appended: {remaining_sorted}. "
                    f"Specified time_order: {time_order_list}"
                )
            
            if len(layer_names) == 0:
                raise ValueError(
                    f"No valid layer names found after processing time_order. "
                    f"This should not happen if validation passed. Please report this error."
                )
            
            logger.info(f"Using layer order: {layer_names}")
        else:
            # Default sorting: try numeric first, then string
            try:
                # Try to convert to numeric for sorting
                layer_names = sorted(available_layer_names, key=lambda x: float(x) if isinstance(x, (int, float)) or (isinstance(x, str) and x.replace('.', '').replace('-', '').isdigit()) else x)
            except:
                # Fall back to string sorting
                layer_names = sorted(available_layer_names)
            logger.info(f"Using default layer order: {layer_names}")
        
        expression_dfs = []
        actual_time_values = []  # Store actual layer names that have data
        
        for layer_name in layer_names:
            layer_data = adata.layers[layer_name]
            
            # Skip empty layers
            if layer_data.shape[0] == 0 or layer_data.shape[1] == 0:
                logger.warning(f"Layer {layer_name} is empty, skipping...")
                continue
            
            # Convert to dense if sparse
            if hasattr(layer_data, 'toarray'):
                expr_matrix = layer_data.toarray()
            else:
                expr_matrix = layer_data
            
            # Create dataframe: rows are genes, columns are cells
            df = pd.DataFrame(
                expr_matrix.T,
                index=adata.var_names,
                columns=adata.obs_names
            )
            
            # Skip if no cells
            if df.shape[1] == 0:
                logger.warning(f"Layer {layer_name} has no cells, skipping...")
                continue
            
            expression_dfs.append(df)
            actual_time_values.append(layer_name)  # Store the actual layer name
            logger.info(f"Layer {layer_name}: {df.shape[0]} genes, {df.shape[1]} cells")
        
        if len(expression_dfs) == 0:
            raise ValueError(
                f"No layers with valid data found. All layers have zero cells. "
                f"Available layer names: {sorted(available_layer_names)}. "
                f"Please check your data and ensure at least one layer has cells."
            )
        
        return expression_dfs, adata, actual_time_values
    
    else:
        # If no time information, check if time_column was specified
        if time_column and time_column != "time":
            raise ValueError(
                f"Time column '{time_column}' not found in obs metadata. "
                f"Available columns in obs: {sorted(adata.obs.columns.tolist())}. "
                f"Also checked layers but found none. "
                f"Please specify a valid time_column or ensure your data contains time information."
            )
        # If no time information, treat entire dataset as single time point
        logger.warning("No time information found. Treating entire dataset as single time point.")
        if hasattr(adata.X, 'toarray'):
            expr_matrix = adata.X.toarray()
        else:
            expr_matrix = adata.X
        
        df = pd.DataFrame(
            expr_matrix.T,
            index=adata.var_names,
            columns=adata.obs_names
        )
        # Return with a default time value
        return [df], adata, ["t0"]


def preprocess_expression_data(df: pd.DataFrame) -> torch.Tensor:
    """Preprocess expression data: log2 transformation and normalization"""
    # log2(x + 0.1) transformation
    df_log = df.apply(lambda x: np.log2(x + 0.1))
    
    # Normalization
    loader = load_data(df_log, normalize=True)
    feature = loader.exp_data()
    
    # Convert to tensor
    feature_tensor = torch.from_numpy(feature).float()
    return feature_tensor.to(DEVICE)


def load_training_network(
    network_file: str,
    gene_names: List[str],
    num_samples: int = 10000,
    seed: int = 8
) -> torch.Tensor:
    """
    Load training network from CSV file and convert to training data format
    
    Args:
        network_file: Path to network CSV file (network_human.csv or network_mouse.csv)
        gene_names: List of gene names from expression data (used for mapping)
        num_samples: Maximum number of training samples to generate
        seed: Random seed for reproducibility
    
    Returns:
        Tensor of shape (num_samples, 3) with columns [TF_index, Target_index, label]
        where label is 1 for positive edges and 0 for negative edges
    """
    logger.info(f"Loading training network from {network_file}...")
    
    # Read network CSV file
    network_df = pd.read_csv(network_file)
    logger.info(f"Loaded {len(network_df)} edges from network file")
    
    # Create gene name to index mapping (case-insensitive)
    gene_name_to_idx = {name.upper(): idx for idx, name in enumerate(gene_names)}
    
    # Extract positive edges (TF-Target pairs that exist in network)
    positive_pairs = []
    for _, row in network_df.iterrows():
        tf_name = str(row['from']).upper()
        target_name = str(row['to']).upper()
        
        # Check if both genes exist in expression data
        if tf_name in gene_name_to_idx and target_name in gene_name_to_idx:
            tf_idx = gene_name_to_idx[tf_name]
            target_idx = gene_name_to_idx[target_name]
            positive_pairs.append((tf_idx, target_idx))
    
    logger.info(f"Found {len(positive_pairs)} positive edges matching expression data genes")
    
    if len(positive_pairs) == 0:
        raise ValueError(
            f"No matching edges found between network file and expression data. "
            f"Please check that gene names in the network file match those in the expression data."
        )
    
    # Create set of positive pairs for fast lookup
    positive_pairs_set = set(positive_pairs)
    
    # Generate training samples
    np.random.seed(seed)
    num_genes = len(gene_names)
    
    # Calculate number of positive and negative samples
    # Use up to 50% positive samples, rest negative
    num_positive = min(len(positive_pairs), num_samples // 2)
    num_negative = num_samples - num_positive
    
    # Sample positive pairs
    if len(positive_pairs) > num_positive:
        positive_samples = np.random.choice(len(positive_pairs), num_positive, replace=False)
        selected_positive = [positive_pairs[i] for i in positive_samples]
    else:
        selected_positive = positive_pairs
    
    # Generate negative samples (random pairs that don't exist in network)
    negative_samples = []
    max_attempts = num_negative * 10  # Limit attempts to avoid infinite loop
    attempts = 0
    
    while len(negative_samples) < num_negative and attempts < max_attempts:
        tf_idx = np.random.randint(0, num_genes)
        target_idx = np.random.randint(0, num_genes)
        
        # Skip self-loops and existing positive edges
        if tf_idx != target_idx and (tf_idx, target_idx) not in positive_pairs_set:
            negative_samples.append((tf_idx, target_idx))
        
        attempts += 1
    
    if len(negative_samples) < num_negative:
        logger.warning(
            f"Could only generate {len(negative_samples)} negative samples "
            f"(requested {num_negative}). Using all available."
        )
    
    # Combine positive and negative samples
    all_pairs = selected_positive + negative_samples
    all_labels = [1.0] * len(selected_positive) + [0.0] * len(negative_samples)
    
    # Shuffle samples
    shuffle_indices = np.random.permutation(len(all_pairs))
    shuffled_pairs = [all_pairs[i] for i in shuffle_indices]
    shuffled_labels = [all_labels[i] for i in shuffle_indices]
    
    # Convert to numpy array with correct types: indices as int64, labels as float32
    tf_indices_array = np.array([pair[0] for pair in shuffled_pairs], dtype=np.int64)
    target_indices_array = np.array([pair[1] for pair in shuffled_pairs], dtype=np.int64)
    labels_array = np.array(shuffled_labels, dtype=np.float32)
    
    train_data_array = np.column_stack([tf_indices_array, target_indices_array, labels_array])
    
    logger.info(
        f"Generated training data: {len(selected_positive)} positive samples, "
        f"{len(negative_samples)} negative samples (total: {len(train_data_array)})"
    )
    
    # Convert to tensor
    train_data = torch.from_numpy(train_data_array).to(DEVICE)
    return train_data


def generate_single_network_subplot(
    grn_df: pd.DataFrame,
    time_point: str,
    ax,
    gene_names: Optional[List[str]] = None,
    node_size_factor: float = 300.0,
    min_node_size: float = 50.0,
    max_node_size: float = 1000.0
) -> None:
    """
    Generate a single network subplot for one time point
    
    Args:
        grn_df: DataFrame with columns ['TF', 'Target', 'score']
        time_point: Time point label (e.g., 't1', 't2')
        ax: Matplotlib axes object to draw on
        gene_names: Optional list of gene names for labeling (if None, uses indices)
        node_size_factor: Factor to scale node sizes
        min_node_size: Minimum node size
        max_node_size: Maximum node size
    """
    # Create directed graph from GRN results
    G = nx.DiGraph()
    
    # Add edges with scores
    for _, row in grn_df.iterrows():
        tf = int(row['TF'])
        target = int(row['Target'])
        score = float(row['score'])
        G.add_edge(tf, target, weight=score)
    
    if len(G.nodes()) == 0:
        ax.text(0.5, 0.5, f"No network data for {time_point}", 
                ha='center', va='center', transform=ax.transAxes)
        ax.axis('off')
        return
    
    # Calculate node attributes
    degrees = dict(G.degree())
    in_degrees = dict(G.in_degree())
    out_degrees = dict(G.out_degree())
    total_degrees = {node: degrees.get(node, 0) for node in G.nodes()}
    
    # Node color based on average score of connected edges
    node_scores = {}
    for node in G.nodes():
        in_edges = [(u, v, d) for u, v, d in G.in_edges(node, data=True)]
        out_edges = [(u, v, d) for u, v, d in G.out_edges(node, data=True)]
        all_edges = in_edges + out_edges
        if all_edges:
            avg_score = np.mean([d.get('weight', 0) for _, _, d in all_edges])
            node_scores[node] = avg_score
        else:
            node_scores[node] = 0.0
    
    # Normalize node sizes
    if total_degrees:
        max_degree = max(total_degrees.values())
        min_degree = min(total_degrees.values())
        if max_degree > min_degree:
            node_sizes = {
                node: min_node_size + (max_node_size - min_node_size) * 
                (total_degrees[node] - min_degree) / (max_degree - min_degree)
                for node in G.nodes()
            }
        else:
            node_sizes = {node: (min_node_size + max_node_size) / 2 for node in G.nodes()}
    else:
        node_sizes = {node: (min_node_size + max_node_size) / 2 for node in G.nodes()}
    
    # Normalize node scores for coloring (0-1 range)
    if node_scores:
        max_score = max(node_scores.values())
        min_score = min(node_scores.values())
        if max_score > min_score:
            normalized_scores = {
                node: (node_scores[node] - min_score) / (max_score - min_score)
                for node in G.nodes()
            }
        else:
            normalized_scores = {node: 0.5 for node in G.nodes()}
    else:
        normalized_scores = {node: 0.5 for node in G.nodes()}
    
    # Create colormap: light orange/yellow to dark red
    colors_list = ['#FFE5B4', '#FFCC99', '#FF9966', '#FF6633', '#CC3300', '#990000', '#660000']
    n_bins = 256
    cmap = LinearSegmentedColormap.from_list('custom', colors_list, N=n_bins)
    
    # Get node colors
    node_colors = [cmap(normalized_scores[node]) for node in G.nodes()]
    
    # Identify high-importance nodes (top 20% by degree or score) for green outline
    if len(G.nodes()) > 0:
        sorted_by_degree = sorted(G.nodes(), key=lambda x: total_degrees[x], reverse=True)
        top_n = max(1, int(len(sorted_by_degree) * 0.2))
        high_importance_nodes = set(sorted_by_degree[:top_n])
    else:
        high_importance_nodes = set()
    
    # Use spring layout for better visualization
    try:
        pos = nx.spring_layout(G, k=1.5, iterations=50, seed=42)
    except:
        pos = nx.spring_layout(G, k=1.0, iterations=30)
    
    # Draw edges (gray, thin)
    nx.draw_networkx_edges(
        G, pos,
        edge_color='gray',
        alpha=0.3,
        width=0.5,
        arrows=True,
        arrowsize=8,
        arrowstyle='->',
        ax=ax
    )
    
    # Draw nodes
    nodes_list = list(G.nodes())
    node_sizes_list = [node_sizes[node] for node in nodes_list]
    node_colors_list = [node_colors[i] for i, node in enumerate(nodes_list)]
    
    nx.draw_networkx_nodes(
        G, pos,
        nodelist=nodes_list,
        node_size=node_sizes_list,
        node_color=node_colors_list,
        alpha=0.9,
        ax=ax
    )
    
    # Add green outline for high-importance nodes
    if high_importance_nodes:
        high_imp_nodes = [node for node in nodes_list if node in high_importance_nodes]
        nx.draw_networkx_nodes(
            G, pos,
            nodelist=high_imp_nodes,
            node_size=[node_sizes[node] * 1.15 for node in high_imp_nodes],
            node_color='none',
            edgecolors='green',
            linewidths=2.0,
            alpha=0.8,
            ax=ax
        )
    
    # Add labels (gene names or indices)
    # Priority: Use TF_name and Target_name from DataFrame if available
    labels = {}
    if 'TF_name' in grn_df.columns and 'Target_name' in grn_df.columns:
        # Create mapping from node index to name using TF_name and Target_name columns
        node_to_name = {}
        for _, row in grn_df.iterrows():
            tf_idx = int(row['TF'])
            target_idx = int(row['Target'])
            if 'TF_name' in row:
                node_to_name[tf_idx] = str(row['TF_name'])
            if 'Target_name' in row:
                node_to_name[target_idx] = str(row['Target_name'])
        
        # Map all nodes to names
        for node in G.nodes():
            if node in node_to_name:
                labels[node] = node_to_name[node]
            else:
                labels[node] = f"Gene_{node}"
    elif gene_names and len(gene_names) > 0:
        # Fallback to gene_names parameter
        if not isinstance(gene_names, list):
            gene_names = list(gene_names)
        
        # Map node indices to gene names
        for node in G.nodes():
            if isinstance(node, (int, np.integer)) and 0 <= node < len(gene_names):
                labels[node] = str(gene_names[node])
            else:
                labels[node] = f"Gene_{node}"
    else:
        labels = {node: f"Gene_{node}" for node in G.nodes()}
    
    # Only label nodes with high degree to avoid clutter
    if len(G.nodes()) > 50:
        # Label top 30% of nodes by degree
        sorted_nodes = sorted(G.nodes(), key=lambda x: total_degrees[x], reverse=True)
        top_label_n = max(10, int(len(sorted_nodes) * 0.3))
        nodes_to_label = set(sorted_nodes[:top_label_n])
        labels = {node: labels[node] for node in nodes_to_label if node in labels}
    
    nx.draw_networkx_labels(
        G, pos,
        labels=labels,
        font_size=6,
        font_color='black',
        font_weight='bold',
        ax=ax
    )
    
    # Add time point label at top
    ax.set_title(f"Time Point {time_point}", fontsize=12, fontweight='bold', pad=10)
    
    # Remove axes
    ax.axis('off')


def generate_combined_network_graph(
    result_dict: Dict[str, pd.DataFrame],
    output_path: str,
    gene_names: Optional[List[str]] = None,
    dpi: int = 300,
    max_edges_per_timepoint: Optional[int] = 500
) -> str:
    """
    Generate a combined network graph visualization with all time points in subplots
    
    Args:
        result_dict: Dictionary mapping time point keys to GRN DataFrames
        output_path: Path to save the combined graph image
        gene_names: Optional list of gene names for labeling
        dpi: Resolution for output image
    
    Returns:
        Path to saved graph image
    """
    logger.info(f"Generating combined network graph with {len(result_dict)} time points...")
    
    if not result_dict:
        logger.warning("No time points to visualize")
        return None
    
    # Calculate subplot layout
    n_timepoints = len(result_dict)
    # Use a grid layout: try to make it roughly square
    n_cols = int(np.ceil(np.sqrt(n_timepoints)))
    n_rows = int(np.ceil(n_timepoints / n_cols))
    
    # Create figure with subplots
    figsize = (6 * n_cols, 5 * n_rows)
    fig, axes = plt.subplots(n_rows, n_cols, figsize=figsize, dpi=dpi)
    
    # Handle single subplot case
    if n_timepoints == 1:
        axes = [axes]
    elif n_rows == 1:
        axes = axes if isinstance(axes, np.ndarray) else [axes]
    else:
        axes = axes.flatten()
    
    # Sort time points for consistent ordering
    # Try to maintain the order from result_dict keys, but if needed, sort intelligently
    time_point_keys = list(result_dict.keys())
    
    # Try intelligent sorting: numeric first, then string
    def sort_key(x):
        """Sort key function that handles mixed numeric and string time values"""
        # Try to extract numeric part for sorting
        if isinstance(x, (int, float)):
            return (0, float(x))  # Numeric values first
        elif isinstance(x, str):
            # Try to extract leading numeric part
            import re
            match = re.match(r'^([+-]?\d*\.?\d+)', x)
            if match:
                return (0, float(match.group(1)))  # Numeric prefix
            else:
                return (1, x)  # Pure string, sort alphabetically
        else:
            return (1, str(x))
    
    try:
        sorted_time_points = sorted(time_point_keys, key=sort_key)
    except:
        # Fall back to simple string sorting
        sorted_time_points = sorted(time_point_keys)
    
    # Generate subplot for each time point
    for idx, time_point in enumerate(sorted_time_points):
        ax = axes[idx]
        grn_df = result_dict[time_point]
        
        # To speed up rendering, keep only top edges by score
        if max_edges_per_timepoint is not None and len(grn_df) > max_edges_per_timepoint:
            grn_df = grn_df.sort_values('score', ascending=False).head(max_edges_per_timepoint).copy()
            logger.info(
                f"Time point {time_point}: truncated edges to top {max_edges_per_timepoint} "
                f"from {len(result_dict[time_point])}"
            )
        generate_single_network_subplot(
            grn_df=grn_df,
            time_point=time_point,
            ax=ax,
            gene_names=gene_names,
            min_node_size=30.0,
            max_node_size=500.0
        )
    
    # Hide unused subplots
    for idx in range(n_timepoints, len(axes)):
        axes[idx].axis('off')
    
    # Add overall title
    fig.suptitle('Gene Regulatory Network Across Time Points', 
                 fontsize=16, fontweight='bold', y=0.995)
    
    plt.tight_layout(rect=[0, 0, 1, 0.98])
    
    # Save figure
    plt.savefig(output_path, dpi=dpi, bbox_inches='tight', facecolor='white')
    plt.close()
    
    logger.info(f"Combined network graph saved to {output_path}")
    return output_path


def generate_network_graph(
    grn_df: pd.DataFrame,
    time_point: str,
    output_path: str,
    gene_names: Optional[List[str]] = None,
    node_size_factor: float = 300.0,
    min_node_size: float = 50.0,
    max_node_size: float = 1000.0,
    figsize: tuple = (16, 12),
    dpi: int = 300
) -> str:
    """
    Generate network graph visualization for GRN results
    
    Args:
        grn_df: DataFrame with columns ['TF', 'Target', 'score']
        time_point: Time point label (e.g., 't1', 't2')
        output_path: Path to save the graph image
        gene_names: Optional list of gene names for labeling (if None, uses indices)
        node_size_factor: Factor to scale node sizes
        min_node_size: Minimum node size
        max_node_size: Maximum node size
        figsize: Figure size (width, height)
        dpi: Resolution for output image
    
    Returns:
        Path to saved graph image
    """
    logger.info(f"Generating network graph for {time_point}...")
    
    # Create directed graph from GRN results
    G = nx.DiGraph()
    
    # Add edges with scores
    for _, row in grn_df.iterrows():
        tf = int(row['TF'])
        target = int(row['Target'])
        score = float(row['score'])
        G.add_edge(tf, target, weight=score)
    
    if len(G.nodes()) == 0:
        logger.warning(f"No nodes in graph for {time_point}, skipping visualization")
        return None
    
    # Calculate node attributes
    # Node size based on degree (in-degree + out-degree)
    degrees = dict(G.degree())
    in_degrees = dict(G.in_degree())
    out_degrees = dict(G.out_degree())
    total_degrees = {node: degrees.get(node, 0) for node in G.nodes()}
    
    # Node color based on average score of connected edges
    node_scores = {}
    for node in G.nodes():
        in_edges = [(u, v, d) for u, v, d in G.in_edges(node, data=True)]
        out_edges = [(u, v, d) for u, v, d in G.out_edges(node, data=True)]
        all_edges = in_edges + out_edges
        if all_edges:
            avg_score = np.mean([d.get('weight', 0) for _, _, d in all_edges])
            node_scores[node] = avg_score
        else:
            node_scores[node] = 0.0
    
    # Normalize node sizes
    if total_degrees:
        max_degree = max(total_degrees.values())
        min_degree = min(total_degrees.values())
        if max_degree > min_degree:
            node_sizes = {
                node: min_node_size + (max_node_size - min_node_size) * 
                (total_degrees[node] - min_degree) / (max_degree - min_degree)
                for node in G.nodes()
            }
        else:
            node_sizes = {node: (min_node_size + max_node_size) / 2 for node in G.nodes()}
    else:
        node_sizes = {node: (min_node_size + max_node_size) / 2 for node in G.nodes()}
    
    # Normalize node scores for coloring (0-1 range)
    if node_scores:
        max_score = max(node_scores.values())
        min_score = min(node_scores.values())
        if max_score > min_score:
            normalized_scores = {
                node: (node_scores[node] - min_score) / (max_score - min_score)
                for node in G.nodes()
            }
        else:
            normalized_scores = {node: 0.5 for node in G.nodes()}
    else:
        normalized_scores = {node: 0.5 for node in G.nodes()}
    
    # Create colormap: light orange/yellow to dark red
    colors_list = ['#FFE5B4', '#FFCC99', '#FF9966', '#FF6633', '#CC3300', '#990000', '#660000']
    n_bins = 256
    cmap = LinearSegmentedColormap.from_list('custom', colors_list, N=n_bins)
    
    # Get node colors
    node_colors = [cmap(normalized_scores[node]) for node in G.nodes()]
    
    # Identify high-importance nodes (top 20% by degree or score) for green outline
    if len(G.nodes()) > 0:
        sorted_by_degree = sorted(G.nodes(), key=lambda x: total_degrees[x], reverse=True)
        top_n = max(1, int(len(sorted_by_degree) * 0.2))
        high_importance_nodes = set(sorted_by_degree[:top_n])
    else:
        high_importance_nodes = set()
    
    # Create figure
    plt.figure(figsize=figsize, dpi=dpi)
    ax = plt.gca()
    
    # Use spring layout for better visualization
    try:
        pos = nx.spring_layout(G, k=1.5, iterations=50, seed=42)
    except:
        pos = nx.spring_layout(G, k=1.0, iterations=30)
    
    # Draw edges (gray, thin)
    nx.draw_networkx_edges(
        G, pos,
        edge_color='gray',
        alpha=0.3,
        width=0.5,
        arrows=True,
        arrowsize=10,
        arrowstyle='->',
        ax=ax
    )
    
    # Draw nodes
    nodes_list = list(G.nodes())
    node_sizes_list = [node_sizes[node] for node in nodes_list]
    node_colors_list = [node_colors[i] for i, node in enumerate(nodes_list)]
    
    nx.draw_networkx_nodes(
        G, pos,
        nodelist=nodes_list,
        node_size=node_sizes_list,
        node_color=node_colors_list,
        alpha=0.9,
        ax=ax
    )
    
    # Add green outline for high-importance nodes
    if high_importance_nodes:
        high_imp_nodes = [node for node in nodes_list if node in high_importance_nodes]
        nx.draw_networkx_nodes(
            G, pos,
            nodelist=high_imp_nodes,
            node_size=[node_sizes[node] * 1.15 for node in high_imp_nodes],
            node_color='none',
            edgecolors='green',
            linewidths=2.0,
            alpha=0.8,
            ax=ax
        )
    
    # Add labels (gene names or indices)
    # Priority: Use TF_name and Target_name from DataFrame if available
    labels = {}
    if 'TF_name' in grn_df.columns and 'Target_name' in grn_df.columns:
        # Create mapping from node index to name using TF_name and Target_name columns
        node_to_name = {}
        for _, row in grn_df.iterrows():
            tf_idx = int(row['TF'])
            target_idx = int(row['Target'])
            if 'TF_name' in row:
                node_to_name[tf_idx] = str(row['TF_name'])
            if 'Target_name' in row:
                node_to_name[target_idx] = str(row['Target_name'])
        
        # Map all nodes to names
        for node in G.nodes():
            if node in node_to_name:
                labels[node] = node_to_name[node]
            else:
                labels[node] = f"Gene_{node}"
    elif gene_names and len(gene_names) > 0:
        # Fallback to gene_names parameter
        if not isinstance(gene_names, list):
            gene_names = list(gene_names)
        
        # Map node indices to gene names
        for node in G.nodes():
            if isinstance(node, (int, np.integer)) and 0 <= node < len(gene_names):
                labels[node] = str(gene_names[node])
            else:
                labels[node] = f"Gene_{node}"
    else:
        labels = {node: f"Gene_{node}" for node in G.nodes()}
    
    # Only label nodes with high degree to avoid clutter
    if len(G.nodes()) > 50:
        # Label top 30% of nodes by degree
        sorted_nodes = sorted(G.nodes(), key=lambda x: total_degrees[x], reverse=True)
        top_label_n = max(10, int(len(sorted_nodes) * 0.3))
        nodes_to_label = set(sorted_nodes[:top_label_n])
        labels = {node: labels[node] for node in nodes_to_label if node in labels}
    
    nx.draw_networkx_labels(
        G, pos,
        labels=labels,
        font_size=8,
        font_color='black',
        font_weight='bold',
        ax=ax
    )
    
    # Add time point label at bottom
    plt.text(0.5, -0.05, f"({time_point})", 
             transform=ax.transAxes,
             ha='center', va='top',
             fontsize=16, fontweight='bold')
    
    # Remove axes
    ax.axis('off')
    plt.tight_layout()
    
    # Save figure
    plt.savefig(output_path, dpi=dpi, bbox_inches='tight', facecolor='white')
    plt.close()
    
    logger.info(f"Network graph saved to {output_path}")
    return output_path


def perform_grn_inference(
    expression_dfs: List[pd.DataFrame],
    adata,
    time_column: str = 'time',
    time_points: int = 6,
    config: Dict = None,
    time_values: Optional[List] = None,
    species: Optional[str] = None
) -> Dict[str, pd.DataFrame]:
    """
    Perform gene regulatory network inference
    
    Args:
        expression_dfs: List of time-series expression dataframes
        adata: AnnData object
        time_column: Column name in obs containing time point information
        time_points: Number of time points
        config: Model configuration dictionary
        time_values: Optional list of time values (strings) corresponding to each time point.
                    If None, uses t1, t2, t3, etc.
        species: Optional string specifying species ('human' or 'mouse').
                 If None, uses random training data.
    
    Returns:
        Dictionary of GRN network results for each time point (keys are time values)
    """
    if config is None:
        config = DEFAULT_CONFIG.copy()
    
    try:
        # 1. Preprocess expression data
        logger.info("Preprocessing expression data...")
        data_features_raw = []
        num_cells_list = []
        
        # First pass: preprocess all time points and collect cell counts
        for i, df in enumerate(expression_dfs):
            feature = preprocess_expression_data(df)
            data_features_raw.append(feature)
            num_cells_list.append(feature.shape[1])
            logger.info(f"  Time point {i+1}: {df.shape[0]} genes, {df.shape[1]} cells")
        
        # Find maximum number of cells across all time points
        max_cells = max(num_cells_list)
        min_cells = min(num_cells_list)
        
        if max_cells != min_cells:
            logger.warning(
                f"Different cell counts detected across time points: "
                f"min={min_cells}, max={max_cells}. "
                f"Unifying to {max_cells} cells per time point using random sampling."
            )
        
        # Second pass: unify all time points to max_cells
        data_features = []
        np.random.seed(config.get("seed", 8))
        for i, feature in enumerate(data_features_raw):
            current_cells = feature.shape[1]
            if current_cells < max_cells:
                # Random sampling with replacement to reach max_cells
                indices = np.random.choice(current_cells, size=max_cells, replace=True)
                feature_unified = feature[:, indices]
                logger.info(
                    f"  Time point {i+1}: sampled from {current_cells} to {max_cells} cells "
                    f"(with replacement)"
                )
            elif current_cells > max_cells:
                # Random sampling without replacement to reduce to max_cells
                indices = np.random.choice(current_cells, size=max_cells, replace=False)
                feature_unified = feature[:, indices]
                logger.info(
                    f"  Time point {i+1}: sampled from {current_cells} to {max_cells} cells "
                    f"(without replacement)"
                )
            else:
                # Already has max_cells, no need to sample
                feature_unified = feature
            
            data_features.append(feature_unified)
            # Clear original feature to free memory
            if feature_unified is not feature:
                del feature
        
        # Clear raw features list to free memory
        del data_features_raw
        torch.cuda.empty_cache()
        
        logger.info(f"  Unified all time points to {max_cells} cells per time point")
        
        # 2. Generate TF and gene indices (use all genes as TFs)
        if len(expression_dfs) == 0:
            raise ValueError("No expression data available. expression_dfs is empty.")
        
        # Check that all time points have the same number of genes
        num_genes = expression_dfs[0].shape[0]
        for i, df in enumerate(expression_dfs):
            if df.shape[0] != num_genes:
                raise ValueError(
                    f"Inconsistent number of genes across time points: "
                    f"time point 0 has {num_genes} genes, time point {i} has {df.shape[0]} genes"
                )
        
        tf_indices = torch.arange(num_genes, device=DEVICE)
        gene_indices = list(range(num_genes))
        
        # 3. Generate training set (TF-Target pairs)
        num_tf = len(tf_indices)
        num_samples = min(10000, num_tf * len(gene_indices))
        
        # Get gene names from expression data
        gene_names = expression_dfs[0].index.tolist()
        
        # Load training data from network file or generate random data
        if species and species.lower() in ['human', 'mouse']:
            # Determine network file path
            service_dir = os.path.dirname(os.path.abspath(__file__))
            if species.lower() == 'human':
                network_file = os.path.join(service_dir, 'network_human.csv')
            else:  # mouse
                network_file = os.path.join(service_dir, 'network_mouse.csv')
            
            if not os.path.exists(network_file):
                raise FileNotFoundError(
                    f"Training network file not found: {network_file}. "
                    f"Please ensure the file exists in the service directory."
                )
            
            logger.info(f"Using real training data from {network_file}")
            train_data = load_training_network(
                network_file=network_file,
                gene_names=gene_names,
                num_samples=num_samples,
                seed=config.get("seed", 8)
            )
        else:
            # Randomly generate training pairs (fallback to original behavior)
            logger.info("Using random training data (no species specified)")
        np.random.seed(config.get("seed", 8))
        tf_samples = np.random.choice(tf_indices.cpu().numpy(), num_samples, replace=True)
        target_samples = np.random.choice(gene_indices, num_samples, replace=True)
        labels = np.random.randint(0, 2, num_samples).astype(np.float32)
        
        train_data = torch.from_numpy(
            np.column_stack([tf_samples.astype(np.int64), target_samples.astype(np.int64), labels])
        ).to(DEVICE)
        
        # 4. Build adjacency matrix
        num_genes_in_adj = int(max(train_data[:, 0].max().item(), train_data[:, 1].max().item()) + 1)
        train_loader_util = scRNADataset(train_data.cpu().numpy(), num_genes_in_adj, flag=False)
        adj_matrix = train_loader_util.Adj_Generate(tf_indices.cpu(), loop=config.get("loop", False))
        adj = adj2saprse_tensor(adj_matrix).to(DEVICE)
        
        # 5. Initialize model
        logger.info("Initializing GTransformer model...")
        model = GTransformer(
            adata=adata,
            time_column=time_column,
            hidden_dim=config["hidden_dim"],
            output_dim=config["output_dim"],
            num_head=config["num_head"],
            alpha=config["alpha"],
            attention_type=config["type"],
            reduction=config["reduction"],
            device=DEVICE
        ).to(DEVICE)
        
        optimizer = Adam(model.parameters(), lr=config["learning_rate"])
        
        # 6. Train model
        logger.info(f"Starting model training ({config['epochs']} epochs)...")
        train_dataset = TensorDataset(train_data[:, :-1], train_data[:, -1].float())
        
        for epoch in range(config["epochs"]):
            model.train()
            running_loss = 0.0
            
            for train_x, train_y in DataLoader(train_dataset, batch_size=config["batch_size"], shuffle=True):
                optimizer.zero_grad()
                train_y = train_y.to(DEVICE).view(-1, 1).float()
                train_x = train_x.long().to(DEVICE)  # Ensure indices are long type
                
                # Use actual number of time points for recons_tp
                # Ensure recons_tp matches the actual number of time points in data_features
                actual_recons_tp = len(data_features)
                pred, _, _ = model(data_features, adj, train_x, recons_tp=actual_recons_tp)
                pred = torch.sigmoid(pred)
                
                loss = F.binary_cross_entropy(pred, train_y)
                loss.backward()
                optimizer.step()
                running_loss += loss.item()
                
                # Clear intermediate tensors to free memory
                del pred, loss
                
            # Clear CUDA cache after each epoch
            torch.cuda.empty_cache()
            logger.info(f"  Epoch {epoch + 1}/{config['epochs']}, Loss: {running_loss / len(train_dataset):.6f}")
        
        logger.info("Training completed, starting inference...")
        
        # Clear training-related tensors to free memory
        del train_data, train_dataset
        torch.cuda.empty_cache()
        
        # 7. Prepare TF and gene indices for inference
        tf_all = tf_indices.cpu().tolist()
        target_all = gene_indices
        num_genes = len(tf_all)
        total_pairs = num_genes * len(target_all)
        
        # Use batch processing for inference to reduce memory usage
        inference_batch_size = config.get("inference_batch_size", 10000)  # Default 10k pairs per batch
        
        # 8. Inference for each time point with batch processing
        results = {}
        model.eval()
        
        # Determine time point labels
        if time_values and len(time_values) == time_points:
            time_labels = time_values
        else:
            # Fall back to t1, t2, t3, etc.
            time_labels = [f"t{i}" for i in range(1, time_points + 1)]
        
        with torch.no_grad():
            for i in range(1, time_points + 1):
                recons_tp = i
                time_label = time_labels[i - 1]  # Use actual time value or t1, t2, etc.
                logger.info(f"  Time point {time_label} (recons_tp={recons_tp}): Processing {total_pairs} TF-Target pairs in batches of {inference_batch_size}...")
                
                all_scores = []
                all_tf_indices = []
                all_target_indices = []
                
                # Process in batches to avoid OOM
                for batch_start in range(0, total_pairs, inference_batch_size):
                    batch_end = min(batch_start + inference_batch_size, total_pairs)
                    
                    # Generate batch pairs
                    batch_pairs = []
                    for idx in range(batch_start, batch_end):
                        tf_idx = idx // num_genes
                        target_idx = idx % num_genes
                        batch_pairs.append([tf_all[tf_idx], target_all[target_idx]])
                    
                    # Convert to tensor
                    exp_data_tensor_batch = torch.tensor(batch_pairs, device=DEVICE, dtype=torch.long)
                    
                    # Inference
                    score_batch, _, _ = model(data_features, adj, exp_data_tensor_batch, recons_tp)
                    score_batch = torch.sigmoid(score_batch).cpu().flatten().numpy()
                    
                    # Collect results
                    all_scores.extend(score_batch)
                    all_tf_indices.extend([p[0] for p in batch_pairs])
                    all_target_indices.extend([p[1] for p in batch_pairs])
                    
                    # Clear batch tensor
                    del exp_data_tensor_batch, score_batch
                    torch.cuda.empty_cache()
                
                # Create result dataframe
                result_df = pd.DataFrame({
                    'TF': all_tf_indices,
                    'Target': all_target_indices,
                    'score': all_scores
                })
                
                # Select top N% edges
                df_sorted = result_df.sort_values(by='score', ascending=False)
                num_rows = int(len(df_sorted) * config["top_percent_threshold"])
                df_top = df_sorted.head(num_rows)
                
                results[time_label] = df_top  # Use actual time value as key
                logger.info(f"  Time point {time_label}: Selected {num_rows} regulatory edges (top {config['top_percent_threshold']*100}%)")
                
                # Clear intermediate results
                del all_scores, all_tf_indices, all_target_indices, result_df, df_sorted
                torch.cuda.empty_cache()
        
        return results
        
    except Exception as e:
        logger.error(f"Error during GRN inference: {e}", exc_info=True)
        raise


@app.post("/api/grn-discovery")
async def grn_discovery(
    file: UploadFile = File(..., description="Time-series expression data in h5ad format"),
    epochs: int = Form(5, description="Number of training epochs"),
    batch_size: int = Form(512, description="Batch size"),
    learning_rate: float = Form(3e-3, description="Learning rate"),
    top_percent: float = Form(0.2, description="Top percentage threshold for selecting high-scoring regulatory edges"),
    time_column: str = Form("time", description="Column name in obs metadata containing time point information"),
    pseudotime_method: str = Form("none", description="Pseudo-time segmentation method: 'none', 'kmeans', 'equal_width', 'equal_frequency', 'density', or 'gmm'"),
    pseudotime_column: str = Form("pseudotime", description="Column name in obs containing pseudo-time values"),
    max_clusters: int = Form(6, description="Maximum number of clusters/components (for kmeans, gmm methods)"),
    min_clusters: int = Form(2, description="Minimum number of clusters/components (for kmeans, gmm methods)"),
    n_bins: int = Form(6, description="Number of bins/time points (for equal_width, equal_frequency, density methods)"),
    bandwidth: Optional[float] = Form(None, description="Bandwidth for KDE in density method (None for automatic)"),
    compute_pseudotime: bool = Form(True, description="If True, compute pseudo-time from data if not present"),
    pseudotime_compute_method: str = Form("dpt", description="Method to compute pseudo-time if not present: 'dpt' (Diffusion Pseudotime) or 'pca_trajectory'"),
    n_neighbors: int = Form(15, description="Number of neighbors for DPT method"),
    n_pcs: int = Form(40, description="Number of principal components for DPT/PCA methods"),
    time_order: Optional[str] = Form(None, description="Optional comma-separated string specifying time order (e.g., 'E10.5,E12.5,E14.5'). If None, uses default sorting."),
    species: Optional[str] = Form(None, description="Species selection: 'human' to use human training network, 'mouse' to use mouse training network. If None, uses random training data."),
) -> JSONResponse:
    """Gene regulatory network discovery endpoint"""
    temp_files = []
    try:
        # Parameter validation
        if epochs <= 0:
            raise HTTPException(
                status_code=400,
                detail={
                    "error_type": "ParameterValidationError",
                    "error_message": f"epochs must be positive, got {epochs}",
                    "suggestion": "Please provide a positive integer for epochs (e.g., 5, 10, 20)."
                }
            )
        
        if batch_size <= 0:
            raise HTTPException(
                status_code=400,
                detail={
                    "error_type": "ParameterValidationError",
                    "error_message": f"batch_size must be positive, got {batch_size}",
                    "suggestion": "Please provide a positive integer for batch_size (e.g., 256, 512, 1024)."
                }
            )
        
        if learning_rate <= 0:
            raise HTTPException(
                status_code=400,
                detail={
                    "error_type": "ParameterValidationError",
                    "error_message": f"learning_rate must be positive, got {learning_rate}",
                    "suggestion": "Please provide a positive float for learning_rate (e.g., 0.001, 0.003)."
                }
            )
        
        if not (0 < top_percent <= 1):
            raise HTTPException(
                status_code=400,
                detail={
                    "error_type": "ParameterValidationError",
                    "error_message": f"top_percent must be between 0 and 1, got {top_percent}",
                    "suggestion": "Please provide a value between 0 and 1 for top_percent (e.g., 0.1, 0.2, 0.3)."
                }
            )
        
        valid_pseudotime_methods = ["none", "kmeans", "equal_width", "equal_frequency", "density", "gmm"]
        if pseudotime_method not in valid_pseudotime_methods:
            raise HTTPException(
                status_code=400,
                detail={
                    "error_type": "ParameterValidationError",
                    "error_message": f"pseudotime_method must be one of {valid_pseudotime_methods}, got '{pseudotime_method}'",
                    "suggestion": f"Please provide a valid pseudotime_method: {', '.join(valid_pseudotime_methods)}"
                }
            )
        
        if max_clusters < min_clusters:
            raise HTTPException(
                status_code=400,
                detail={
                    "error_type": "ParameterValidationError",
                    "error_message": f"max_clusters ({max_clusters}) must be >= min_clusters ({min_clusters})",
                    "suggestion": "Please ensure max_clusters >= min_clusters."
                }
            )
        
        if min_clusters < 2:
            raise HTTPException(
                status_code=400,
                detail={
                    "error_type": "ParameterValidationError",
                    "error_message": f"min_clusters must be >= 2, got {min_clusters}",
                    "suggestion": "Please provide min_clusters >= 2."
                }
            )
        
        if n_bins < 2:
            raise HTTPException(
                status_code=400,
                detail={
                    "error_type": "ParameterValidationError",
                    "error_message": f"n_bins must be >= 2, got {n_bins}",
                    "suggestion": "Please provide n_bins >= 2."
                }
            )
        
        valid_pseudotime_compute_methods = ["dpt", "pca_trajectory"]
        if pseudotime_compute_method not in valid_pseudotime_compute_methods:
            raise HTTPException(
                status_code=400,
                detail={
                    "error_type": "ParameterValidationError",
                    "error_message": f"pseudotime_compute_method must be one of {valid_pseudotime_compute_methods}, got '{pseudotime_compute_method}'",
                    "suggestion": f"Please provide a valid pseudotime_compute_method: {', '.join(valid_pseudotime_compute_methods)}"
                }
            )
        
        # Validate species parameter
        if species is not None:
            species_lower = species.lower()
            if species_lower not in ['human', 'mouse']:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error_type": "ParameterValidationError",
                        "error_message": f"species must be 'human' or 'mouse', got '{species}'",
                        "suggestion": "Please provide 'human' or 'mouse' for species, or None to use random training data."
                }
            )
        
        if n_neighbors <= 0:
            raise HTTPException(
                status_code=400,
                detail={
                    "error_type": "ParameterValidationError",
                    "error_message": f"n_neighbors must be positive, got {n_neighbors}",
                    "suggestion": "Please provide a positive integer for n_neighbors (e.g., 10, 15, 20)."
                }
            )
        
        if n_pcs <= 0:
            raise HTTPException(
                status_code=400,
                detail={
                    "error_type": "ParameterValidationError",
                    "error_message": f"n_pcs must be positive, got {n_pcs}",
                    "suggestion": "Please provide a positive integer for n_pcs (e.g., 30, 40, 50)."
                }
            )
        
        if bandwidth is not None and bandwidth <= 0:
            raise HTTPException(
                status_code=400,
                detail={
                    "error_type": "ParameterValidationError",
                    "error_message": f"bandwidth must be positive if provided, got {bandwidth}",
                    "suggestion": "Please provide a positive float for bandwidth or None for automatic selection."
                }
            )
        
        # Validate file extension
        if not file.filename or not file.filename.endswith('.h5ad'):
            raise HTTPException(
                status_code=400,
                detail={
                    "error_type": "FileValidationError",
                    "error_message": f"File must be in h5ad format, got filename: {file.filename}",
                    "suggestion": "Please upload a file with .h5ad extension."
                }
            )
        # 1. Save uploaded h5ad file
        file_id = str(uuid.uuid4())
        temp_h5ad_path = os.path.join(tempfile.gettempdir(), f"expression_{file_id}.h5ad")
        with open(temp_h5ad_path, "wb") as f:
            content = await file.read()
            f.write(content)
        temp_files.append(temp_h5ad_path)
        
        # 2. Read h5ad file and extract time-series expression data
        logger.info("Reading h5ad file and extracting time-series data...")
        try:
            expression_dfs, adata, time_values = read_h5ad_file(
                temp_h5ad_path, 
                time_column=time_column,
                pseudotime_method=pseudotime_method,
                pseudotime_column=pseudotime_column,
                max_clusters=max_clusters,
                min_clusters=min_clusters,
                n_bins=n_bins,
                bandwidth=bandwidth,
                compute_pseudotime=compute_pseudotime,
                pseudotime_compute_method=pseudotime_compute_method,
                n_neighbors=n_neighbors,
                n_pcs=n_pcs,
                time_order=time_order
            )
        except ValueError as e:
            # ValueError from read_h5ad_file contains detailed error messages
            logger.error(f"Parameter validation error: {e}", exc_info=True)
            raise HTTPException(
                status_code=400,
                detail={
                    "error_type": "ParameterValidationError",
                    "error_message": str(e),
                    "suggestion": "Please check your parameters (time_column, time_order, etc.) and ensure they match your data."
                }
            )
        except Exception as e:
            logger.error(f"Error reading h5ad file: {e}", exc_info=True)
            raise HTTPException(
                status_code=400,
                detail={
                    "error_type": "FileReadError",
                    "error_message": f"Failed to read h5ad file: {str(e)}",
                    "suggestion": "Please ensure the file is a valid h5ad format and contains the required data."
                }
            )
        
        # Use the detected number of time points instead of the user-specified value
        detected_time_points = len(expression_dfs)
        if detected_time_points == 0:
            raise HTTPException(
                status_code=400,
                detail={
                    "error_type": "NoTimePointsError",
                    "error_message": "No time points found in the data.",
                    "suggestion": f"Please check your time_column parameter ('{time_column}') or pseudo-time segmentation settings. "
                                 f"Ensure the time column exists in obs metadata and contains valid time values."
                }
            )
        
        # Filter out empty time points (cells == 0)
        expression_dfs = [df for df in expression_dfs if df.shape[1] > 0]
        if len(expression_dfs) == 0:
            raise HTTPException(
                status_code=400,
                detail={
                    "error_type": "EmptyTimePointsError",
                    "error_message": "All time points have zero cells.",
                    "suggestion": "Please check your data and ensure at least one time point contains cells."
                }
            )
        
        # Log filtered time points
        filtered_time_points = len(expression_dfs)
        if filtered_time_points < detected_time_points:
            logger.warning(f"Filtered out {detected_time_points - filtered_time_points} empty time points")
        
        # Use all time points from data (no limit)
        time_points = filtered_time_points
        logger.info(f"Using {time_points} time points from data")
        
        # 3. Configure model parameters
        config = DEFAULT_CONFIG.copy()
        config.update({
            "epochs": epochs,
            "batch_size": batch_size,
            "learning_rate": learning_rate,
            "top_percent_threshold": top_percent,
        })
        
        # 4. Perform GRN inference
        logger.info("Starting GRN inference...")
        result_dict = await run_in_threadpool(
            perform_grn_inference,
            expression_dfs,
            adata,
            time_column,
            time_points,
            config,
            time_values,  # Pass actual time values
            species  # Pass species parameter
        )
        
        # 5. Merge results from all time points into one file
        logger.info("Merging results from all time points...")
        
        # Get gene names from expression data for mapping indices to names
        gene_names = None
        if len(expression_dfs) > 0:
            gene_names = expression_dfs[0].index.tolist()
            logger.info(f"Retrieved {len(gene_names)} gene names for result file")
        
        merged_results = []
        for time_key, df_result in result_dict.items():
            df_with_time = df_result.copy()
            df_with_time['time_point'] = time_key
            
            # Add TF_name and Target_name columns if gene names are available
            if gene_names and len(gene_names) > 0:
                df_with_time['TF_name'] = df_with_time['TF'].apply(
                    lambda x: gene_names[x] if isinstance(x, (int, np.integer)) and 0 <= x < len(gene_names) else f"Gene_{x}"
                )
                df_with_time['Target_name'] = df_with_time['Target'].apply(
                    lambda x: gene_names[x] if isinstance(x, (int, np.integer)) and 0 <= x < len(gene_names) else f"Gene_{x}"
                )
            else:
                df_with_time['TF_name'] = df_with_time['TF'].apply(lambda x: f"Gene_{x}")
                df_with_time['Target_name'] = df_with_time['Target'].apply(lambda x: f"Gene_{x}")
            
            merged_results.append(df_with_time)
        
        merged_df = pd.concat(merged_results, ignore_index=True)
        
        # Remove original TF and Target columns (indices), keep only TF_name and Target_name
        # Then rename TF_name -> TF and Target_name -> Target
        # This ensures the output only contains gene names, not indices
        merged_df = merged_df.drop(columns=['TF', 'Target'], errors='ignore')
        merged_df = merged_df.rename(columns={'TF_name': 'TF', 'Target_name': 'Target'})
        
        # Reorder columns: TF, Target, score, time_point
        column_order = ['TF', 'Target', 'score', 'time_point']
        merged_df = merged_df[column_order]
        
        # 6. Save merged result file
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        result_id = f"{uuid.uuid4()}.csv"
        result_path = os.path.join(OUTPUT_DIR, result_id)
        merged_df.to_csv(result_path, index=False)
        
        data_dict = {"grn_results.csv": result_id}
        
        # 7. Generate statistics report
        stats_parts = []
        stats_parts.append("=" * 60)
        stats_parts.append("scDGRN Gene Regulatory Network Discovery Statistics Report")
        stats_parts.append("=" * 60)
        stats_parts.append(f"\n[I. Analysis Parameters]")
        stats_parts.append(f"  Method: scDGRN (Single-cell Dynamic Gene Regulatory Network)")
        stats_parts.append(f"  Number of time points: {time_points}")
        stats_parts.append(f"  Pseudo-time method: {pseudotime_method}")
        if pseudotime_method != "none":
            stats_parts.append(f"  Pseudo-time column: {pseudotime_column}")
            if pseudotime_method in ["kmeans", "gmm"]:
                stats_parts.append(f"  Cluster/component range: {min_clusters}-{max_clusters}")
            elif pseudotime_method in ["equal_width", "equal_frequency", "density"]:
                stats_parts.append(f"  Number of bins: {n_bins}")
                if pseudotime_method == "density" and bandwidth is not None:
                    stats_parts.append(f"  KDE bandwidth: {bandwidth}")
        stats_parts.append(f"  Training epochs: {epochs}")
        stats_parts.append(f"  Batch size: {batch_size}")
        stats_parts.append(f"  Learning rate: {learning_rate}")
        stats_parts.append(f"  Top percentage threshold: {top_percent * 100}%")
        if species:
            stats_parts.append(f"  Species: {species}")
        else:
            stats_parts.append(f"  Species: Not specified (using random training data)")
        
        stats_parts.append(f"\n[II. Data Statistics]")
        stats_parts.append(f"  Number of genes: {expression_dfs[0].shape[0]:,}")
        stats_parts.append(f"  Number of cells: {expression_dfs[0].shape[1]:,}")
        
        stats_parts.append(f"\n[III. Results Statistics]")
        for time_key, df_result in result_dict.items():
            stats_parts.append(f"  {time_key}:")
            stats_parts.append(f"    Number of regulatory edges: {len(df_result):,}")
            stats_parts.append(f"    Mean score: {df_result['score'].mean():.4f}")
            stats_parts.append(f"    Max score: {df_result['score'].max():.4f}")
            stats_parts.append(f"    Min score: {df_result['score'].min():.4f}")
        
        stats_text = "\n".join(stats_parts)
        
        # Save statistics report
        statistics_id = f"{uuid.uuid4()}.txt"
        statistics_path = os.path.join(OUTPUT_DIR, statistics_id)
        with open(statistics_path, "w", encoding="utf-8") as f:
            f.write(stats_text)
        
        data_dict["statistics.txt"] = statistics_id
        
        # 8. Generate combined network graph for all time points
        logger.info("Generating combined network graph...")
        try:
            # Update result_dict to include TF_name and Target_name columns
            # (they were already added during merging, but we need to update result_dict for graph generation)
            updated_result_dict = {}
            for time_key, df_result in result_dict.items():
                df_with_names = df_result.copy()
                if gene_names and len(gene_names) > 0:
                    df_with_names['TF_name'] = df_with_names['TF'].apply(
                        lambda x: gene_names[x] if isinstance(x, (int, np.integer)) and 0 <= x < len(gene_names) else f"Gene_{x}"
                    )
                    df_with_names['Target_name'] = df_with_names['Target'].apply(
                        lambda x: gene_names[x] if isinstance(x, (int, np.integer)) and 0 <= x < len(gene_names) else f"Gene_{x}"
                    )
                else:
                    df_with_names['TF_name'] = df_with_names['TF'].apply(lambda x: f"Gene_{x}")
                    df_with_names['Target_name'] = df_with_names['Target'].apply(lambda x: f"Gene_{x}")
                updated_result_dict[time_key] = df_with_names
            
            # Generate combined graph for all time points
            graph_id = f"{uuid.uuid4()}.png"
            graph_path = os.path.join(OUTPUT_DIR, graph_id)
            
            graph_file = generate_combined_network_graph(
                result_dict=updated_result_dict,
                output_path=graph_path,
                gene_names=gene_names,
                max_edges_per_timepoint=500
            )
            
            if graph_file:
                data_dict["network_graph.png"] = graph_id
                logger.info(f"Generated combined network graph with {len(result_dict)} time points")
        except Exception as e:
            logger.warning(f"Failed to generate network graph: {e}", exc_info=True)
            # Don't fail the entire request if graph generation fails
        
        logger.info("GRN discovery completed successfully")
        return JSONResponse(
            status_code=200,
            content={"success": True, "message": "Gene regulatory network discovery completed", "data": data_dict},
        )
        
    except HTTPException:
        # Re-raise HTTPException to be handled by http_exception_handler
        raise
    except ValueError as e:
        # ValueError should be converted to HTTPException with 400 status
        logger.error(f"ValueError in GRN discovery: {e}", exc_info=True)
        raise HTTPException(
            status_code=400,
            detail={
                "error_type": "ValueError",
                "error_message": str(e),
                "suggestion": "Please check your input parameters and data format."
            }
        )
    except Exception as e:
        # Other exceptions will be handled by general_exception_handler
        import traceback
        error_msg = f"GRN discovery failed: {str(e)}"
        logger.error(f"{error_msg}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail={
                "error_type": type(e).__name__,
                "error_message": error_msg,
                "suggestion": "Please check the server logs for more details. If the problem persists, please contact the administrator."
            }
        )
    finally:
        # Clean up temporary files
        for temp_file in temp_files:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception:
                    pass


@app.get("/api/download/{file_id}")
async def download_file(file_id: str) -> FileResponse:
    """Download result file"""
    file_path = os.path.join(OUTPUT_DIR, file_id)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"File not found: {file_id}")
    
    if file_path.endswith(".csv"):
        media_type = "text/csv"
    elif file_path.endswith(".txt"):
        media_type = "text/plain"
    elif file_path.endswith(".png"):
        media_type = "image/png"
    else:
        media_type = "application/octet-stream"
    
    return FileResponse(path=file_path, filename=file_id, media_type=media_type)


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "output_dir": OUTPUT_DIR,
        "device": str(DEVICE),
        "cuda_available": torch.cuda.is_available(),
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
