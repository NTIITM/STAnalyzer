import scanpy as sc
import squidpy as sq
import pandas as pd
import matplotlib.pyplot as plt
import os
import time

def process_neighborhood_enrichment(
        adata_path: str,
        cluster_key: str,
        n_neighbors: int,
        radius: float,
        n_perms: int,
        seed: int,
        output_dir: str
):
    """
    Core algorithm for spatial neighborhood enrichment using Squidpy.
    """
    start_time = time.time()
    
    # 1. Load data
    adata = sc.read_h5ad(adata_path)
    
    if cluster_key not in adata.obs.columns:
        raise ValueError(f"Cluster key '{cluster_key}' not found in adata.obs.")
    
    # Ensure spatial coordinates exist
    if 'spatial' not in adata.obsm.keys():
        raise ValueError("Spatial coordinates 'spatial' not found in adata.obsm.")
        
    # 2. Compute spatial graph
    if radius is not None and radius > 0:
        sq.gr.spatial_neighbors(adata, radius=radius, coord_type='generic', set_diag=True)
        spatial_graph_method = f"Radius (r={radius})"
    else:
        sq.gr.spatial_neighbors(adata, n_neighs=n_neighbors, coord_type='generic', set_diag=True)
        spatial_graph_method = f"kNN (k={n_neighbors})"
        
    # 3. Compute neighborhood enrichment
    sq.gr.nhood_enrichment(
        adata,
        cluster_key=cluster_key,
        n_perms=n_perms,
        seed=seed
    )
    
    # 4. Extract results
    zscores_matrix = adata.uns[f'{cluster_key}_nhood_enrichment']['zscore']
    categories = adata.obs[cluster_key].cat.categories if hasattr(adata.obs[cluster_key], 'cat') else adata.obs[cluster_key].unique()
    
    zscores_df = pd.DataFrame(
        zscores_matrix,
        index=categories,
        columns=categories
    )
    
    csv_filename = "neighborhood_enrichment_zscores.csv"
    zscores_df.to_csv(os.path.join(output_dir, csv_filename))
    
    # 5. Plot heatmap
    heatmap_filename = "neighborhood_enrichment_heatmap.png"
    sq.pl.nhood_enrichment(
        adata,
        cluster_key=cluster_key,
        figsize=(8, 8),
        title="Neighborhood Enrichment",
        save=os.path.join(output_dir, heatmap_filename)
    )
    # Note: squidpy save logic appends paths peculiarly sometimes, 
    # but we will manually move it if squidpy puts it in a 'figures' dir.
    # To be safe, we plot manually using squidpy's returned axes or matplotlib
    # Wait, sq.pl.nhood_enrichment uses scanpy's save machinery which dumps to `figures/`.
    # Let's override this to guarantee it lands in output_dir:
    plt.close('all')
    fig, ax = plt.subplots(figsize=(8, 8))
    sq.pl.nhood_enrichment(adata, cluster_key=cluster_key, ax=ax)
    fig.savefig(os.path.join(output_dir, heatmap_filename), dpi=300, bbox_inches='tight')
    plt.close(fig)

    # 6. Save updated h5ad
    h5ad_filename = "enriched_spatial_data.h5ad"
    adata.write_h5ad(os.path.join(output_dir, h5ad_filename))
    
    end_time = time.time()
    
    # 7. Generate statistics
    stats_filename = "statistics.txt"
    with open(os.path.join(output_dir, stats_filename), 'w', encoding='utf-8') as f:
        f.write("=== Spatial Neighborhood Enrichment Statistics (Squidpy) ===\n\n")
        f.write(f"Total Spots/Cells Processed: {adata.shape[0]}\n")
        f.write(f"Cluster Key Used: '{cluster_key}'\n")
        f.write(f"Number of Unique Clusters: {len(categories)}\n")
        f.write(f"Spatial Graph Method: {spatial_graph_method}\n")
        f.write(f"Permutations: {n_perms}\n")
        f.write(f"Random Seed: {seed}\n")
        f.write(f"Processing Time: {end_time - start_time:.2f} seconds\n\n")
        
        f.write("Output Artifacts:\n")
        f.write(f" - {csv_filename}: Pairwise z-scores of spatial co-localization.\n")
        f.write(f" - {heatmap_filename}: Visual representation of the enrichment network.\n")
        f.write(f" - {h5ad_filename}: AnnData updated with spatial_neighbors graph and enrichment results.\n")
        
    return {
        "neighborhood_enrichment_zscores.csv": csv_filename,
        "neighborhood_enrichment_heatmap.png": heatmap_filename,
        "enriched_spatial_data.h5ad": h5ad_filename,
        "statistics.txt": stats_filename
    }
