#!/usr/bin/env python3
"""
Convert test data to h5ad format for scDGRN service testing
"""
import os
import sys
import pandas as pd
import numpy as np
import anndata as ad
from typing import List, Dict
import zipfile
import tempfile

def create_test_h5ad_from_zip(zip_path: str, output_path: str, time_column: str = "time") -> str:
    """
    Convert ZIP file containing multiple CSV files (one per timepoint) to h5ad format
    
    Args:
        zip_path: Path to ZIP file containing CSV files (t0.csv, t1.csv, etc.)
        output_path: Path to save the h5ad file
        time_column: Name of the time column in obs
    
    Returns:
        Path to created h5ad file
    """
    print(f"Reading ZIP file: {zip_path}")
    
    # Read all timepoint files from ZIP
    timepoint_data = {}
    with zipfile.ZipFile(zip_path, 'r') as zf:
        for filename in sorted(zf.namelist()):
            if filename.endswith('.csv'):
                # Extract timepoint number from filename (e.g., t0.csv -> 0, expression_t1.csv -> 1)
                if filename.startswith('t') and filename[1].isdigit():
                    timepoint = int(filename[1])
                elif 't' in filename.lower():
                    # Try to extract number after 't'
                    parts = filename.lower().split('t')
                    if len(parts) > 1 and parts[1][0].isdigit():
                        timepoint = int(parts[1][0])
                    else:
                        continue
                else:
                    continue
                
                print(f"  Reading timepoint {timepoint} from {filename}")
                with zf.open(filename) as f:
                    df = pd.read_csv(f, index_col=0)
                    timepoint_data[timepoint] = df
    
    if not timepoint_data:
        raise ValueError("No valid CSV files found in ZIP archive")
    
    print(f"Found {len(timepoint_data)} timepoints: {sorted(timepoint_data.keys())}")
    
    # Get common genes and cells across all timepoints
    all_genes = set()
    all_cells = set()
    for df in timepoint_data.values():
        all_genes.update(df.index)
        all_cells.update(df.columns)
    
    genes = sorted(list(all_genes))
    cells = sorted(list(all_cells))
    
    print(f"Total genes: {len(genes)}, Total cells: {len(cells)}")
    
    # Create AnnData object with layers for each timepoint
    # Use the first timepoint as the main X matrix
    first_tp = min(timepoint_data.keys())
    first_df = timepoint_data[first_tp]
    
    # Align data to common genes and cells
    aligned_data = first_df.reindex(index=genes, columns=cells, fill_value=0)
    X = aligned_data.values.T  # AnnData expects cells x genes
    
    # Create obs (cell metadata) with time information
    obs_data = []
    for tp in sorted(timepoint_data.keys()):
        df = timepoint_data[tp]
        tp_cells = [c for c in cells if c in df.columns]
        for cell in tp_cells:
            obs_data.append({time_column: tp, 'cell_id': cell})
    
    obs = pd.DataFrame(obs_data)
    
    # Create var (gene metadata)
    var = pd.DataFrame(index=genes)
    var.index.name = 'gene_id'
    
    # Create layers for each timepoint
    layers = {}
    for tp in sorted(timepoint_data.keys()):
        df = timepoint_data[tp]
        aligned = df.reindex(index=genes, columns=cells, fill_value=0)
        layers[f'timepoint_{tp}'] = aligned.values.T  # cells x genes
    
    # Create AnnData object
    adata = ad.AnnData(X=X, obs=obs, var=var, layers=layers)
    
    # Save to h5ad
    print(f"Saving to h5ad format: {output_path}")
    adata.write(output_path)
    print(f"✓ Successfully created h5ad file: {output_path}")
    print(f"  Shape: {adata.shape} (cells x genes)")
    print(f"  Timepoints in layers: {list(layers.keys())}")
    print(f"  Time column in obs: {time_column}")
    
    return output_path


def create_h5ad_from_network_zip(network_zip_path: str, output_path: str, 
                                  num_cells: int = 200, time_points: int = 6, 
                                  time_column: str = "time", max_genes: int = None) -> str:
    """
    Create h5ad file from network ZIP file by extracting gene list and generating synthetic expression data
    
    Args:
        network_zip_path: Path to ZIP file containing network CSV (from, to, edge_type)
        output_path: Path to save the h5ad file
        num_cells: Number of cells per timepoint
        time_points: Number of timepoints
        time_column: Name of the time column in obs
        max_genes: Maximum number of genes to use (None = use all)
    
    Returns:
        Path to created h5ad file
    """
    print(f"Reading network ZIP file: {network_zip_path}")
    
    # Extract gene list from network file
    with zipfile.ZipFile(network_zip_path, 'r') as zf:
        csv_files = [f for f in zf.namelist() if f.endswith('.csv')]
        if not csv_files:
            raise ValueError("No CSV file found in ZIP archive")
        
        network_file = csv_files[0]
        print(f"  Reading network from {network_file}")
        with zf.open(network_file) as f:
            df = pd.read_csv(f)
        
        # Extract unique genes from 'from' and 'to' columns
        if 'from' in df.columns and 'to' in df.columns:
            all_genes = set(df['from'].unique()) | set(df['to'].unique())
        else:
            raise ValueError(f"Network file must contain 'from' and 'to' columns. Found: {list(df.columns)}")
    
    genes = sorted(list(all_genes))
    if max_genes and len(genes) > max_genes:
        print(f"  Limiting to {max_genes} genes (from {len(genes)} total)")
        genes = genes[:max_genes]
    
    print(f"  Found {len(genes)} unique genes")
    print(f"  Sample genes: {genes[:10]}")
    
    # Generate synthetic expression data based on these genes
    return create_synthetic_h5ad_with_genes(
        output_path, genes, num_cells, time_points, time_column
    )


def create_synthetic_h5ad_with_genes(output_path: str, gene_names: List[str], 
                                     num_cells: int = 200, time_points: int = 6, 
                                     time_column: str = "time") -> str:
    """
    Create synthetic h5ad test data with specified gene names
    
    Args:
        output_path: Path to save the h5ad file
        gene_names: List of gene names to use
        num_cells: Number of cells per timepoint
        time_points: Number of timepoints
        time_column: Name of the time column in obs
    
    Returns:
        Path to created h5ad file
    """
    num_genes = len(gene_names)
    print(f"Creating synthetic h5ad data...")
    print(f"  Genes: {num_genes}, Cells per timepoint: {num_cells}, Timepoints: {time_points}")
    
    np.random.seed(42)
    
    # Create data for each timepoint
    obs_data = []
    all_expression = []
    
    for tp in range(time_points):
        # Generate expression data for this timepoint
        # Use log-normal distribution to simulate real expression data
        expression = np.random.lognormal(mean=2, sigma=1, size=(num_cells, num_genes))
        # Add time-dependent variation
        expression = expression * (1 + 0.1 * tp * np.random.rand(num_cells, num_genes))
        
        all_expression.append(expression)
        
        # Add cell metadata
        for i in range(num_cells):
            obs_data.append({
                time_column: tp,
                'cell_id': f"Cell_t{tp}_{i}"
            })
    
    # Concatenate all timepoints for X (cells x genes)
    X = np.vstack(all_expression)
    
    # Create obs and var
    obs = pd.DataFrame(obs_data)
    var = pd.DataFrame(index=gene_names)
    var.index.name = 'gene_id'
    
    # Create AnnData object (without layers, using obs time_column instead)
    adata = ad.AnnData(X=X, obs=obs, var=var)
    
    # Save to h5ad
    print(f"Saving to h5ad format: {output_path}")
    adata.write(output_path)
    print(f"✓ Successfully created h5ad file: {output_path}")
    print(f"  Shape: {adata.shape} (cells x genes)")
    print(f"  Timepoints in obs['{time_column}']: {sorted(obs[time_column].unique())}")
    print(f"  Total cells: {len(obs)}, Total genes: {len(var)}")
    
    return output_path


def create_synthetic_h5ad(output_path: str, num_genes: int = 100, num_cells: int = 200, 
                          time_points: int = 6, time_column: str = "time") -> str:
    """
    Create synthetic h5ad test data
    
    Args:
        output_path: Path to save the h5ad file
        num_genes: Number of genes
        num_cells: Number of cells per timepoint
        time_points: Number of timepoints
        time_column: Name of the time column in obs
    
    Returns:
        Path to created h5ad file
    """
    print(f"Creating synthetic h5ad data...")
    print(f"  Genes: {num_genes}, Cells per timepoint: {num_cells}, Timepoints: {time_points}")
    
    np.random.seed(42)
    gene_names = [f"Gene_{i}" for i in range(num_genes)]
    
    # Create data for each timepoint
    obs_data = []
    all_expression = []
    
    for tp in range(time_points):
        # Generate expression data for this timepoint
        # Use log-normal distribution to simulate real expression data
        expression = np.random.lognormal(mean=2, sigma=1, size=(num_cells, num_genes))
        # Add time-dependent variation
        expression = expression * (1 + 0.1 * tp * np.random.rand(num_cells, num_genes))
        
        all_expression.append(expression)
        
        # Add cell metadata
        for i in range(num_cells):
            obs_data.append({
                time_column: tp,
                'cell_id': f"Cell_t{tp}_{i}"
            })
    
    # Concatenate all timepoints for X (cells x genes)
    X = np.vstack(all_expression)
    
    # Create obs and var
    obs = pd.DataFrame(obs_data)
    var = pd.DataFrame(index=gene_names)
    var.index.name = 'gene_id'
    
    # Create AnnData object (without layers, using obs time_column instead)
    adata = ad.AnnData(X=X, obs=obs, var=var)
    
    # Save to h5ad
    print(f"Saving to h5ad format: {output_path}")
    adata.write(output_path)
    print(f"✓ Successfully created h5ad file: {output_path}")
    print(f"  Shape: {adata.shape} (cells x genes)")
    print(f"  Timepoints in obs['{time_column}']: {sorted(obs[time_column].unique())}")
    print(f"  Total cells: {len(obs)}, Total genes: {len(var)}")
    
    return output_path


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Convert test data to h5ad format")
    parser.add_argument("--input", "-i", type=str, help="Input ZIP file path (optional)")
    parser.add_argument("--output", "-o", type=str, required=True, help="Output h5ad file path")
    parser.add_argument("--genes", "-g", type=int, default=100, help="Number of genes for synthetic data")
    parser.add_argument("--cells", "-c", type=int, default=200, help="Number of cells per timepoint for synthetic data")
    parser.add_argument("--timepoints", "-t", type=int, default=6, help="Number of timepoints")
    parser.add_argument("--time-column", type=str, default="time", help="Name of time column in obs")
    parser.add_argument("--network", "-n", action="store_true", help="Treat input ZIP as network file (from, to, edge_type)")
    parser.add_argument("--max-genes", type=int, default=None, help="Maximum number of genes to use from network file")
    
    args = parser.parse_args()
    
    if args.input:
        if args.network:
            # Convert from network ZIP
            create_h5ad_from_network_zip(args.input, args.output, args.cells, args.timepoints, args.time_column, args.max_genes)
        else:
            # Convert from expression ZIP
            create_test_h5ad_from_zip(args.input, args.output, args.time_column)
    else:
        # Create synthetic data
        create_synthetic_h5ad(args.output, args.genes, args.cells, args.timepoints, args.time_column)

