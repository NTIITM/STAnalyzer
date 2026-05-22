import scanpy as sc
import squidpy as sq
import pandas as pd
import matplotlib.pyplot as plt
import os
import time

def process_point_pattern(
        adata_path: str,
        cluster_key: str,
        mode: str,
        spatial_metric: str,
        n_simulations: int,
        seed: int,
        output_dir: str
):
    start_time = time.time()
    
    # 1. Load data
    adata = sc.read_h5ad(adata_path)
    
    if cluster_key not in adata.obs.columns:
        raise ValueError(f"Cluster key '{cluster_key}' not found in adata.obs.")
    
    if 'spatial' not in adata.obsm.keys():
        raise ValueError("Spatial coordinates 'spatial' not found in adata.obsm.")
        
    categories = adata.obs[cluster_key].unique()
    if len(categories) == 0:
        raise ValueError(f"No categories found in cluster_key '{cluster_key}'.")
        
    # 2. Compute Ripley's statistic
    # sq.gr.ripley calculates K, L, F, or G depending on the mode argument
    # By default, Squidpy's ripley computes on a discrete clustered annotation
    
    sq.gr.ripley(
        adata,
        cluster_key=cluster_key,
        mode=mode,
        metric=spatial_metric,
        n_simulations=n_simulations,
        seed=seed
    )
    
    # 3. Extract Statistics
    # The results are stored in adata.uns[f'{mode}_stat'] (e.g. 'L_stat' for mode='L')
    stat_key = f"{mode}_stat"
    if stat_key not in adata.uns:
        raise RuntimeError(f"Expected to find '{stat_key}' in adata.uns but failed. Squidpy computation might have failed.")
    
    ripley_results = adata.uns[stat_key]
    
    # Ripley results usually contain distance bins (bins), statistics (stats), p-values, 
    # and theoretical envelopes. Let's dump the underlying dataframe if accessible.
    
    csv_filename = "ripley_statistics.csv"
    
    # In Squidpy, ripley_results is typically a DataFrame or dictionary containing DataFrames per category
    # Let's extract and format it robustly
    combined_dfs = []
    
    if isinstance(ripley_results, dict):
        for cat, df in ripley_results.items():
            if isinstance(df, pd.DataFrame):
                df_copy = df.copy()
                df_copy['category'] = cat
                combined_dfs.append(df_copy)
                
        if len(combined_dfs) > 0:
            final_df = pd.concat(combined_dfs, axis=0)
            final_df.to_csv(os.path.join(output_dir, csv_filename), index=False)
        else:
            with open(os.path.join(output_dir, csv_filename), 'w') as f:
                f.write("No dataframe results extracted.")
    elif isinstance(ripley_results, pd.DataFrame):
        ripley_results.to_csv(os.path.join(output_dir, csv_filename))
    else:
        # Fallback dump
        pd.DataFrame({"info": ["Results format not natively convertible to CSV", type(ripley_results)]}).to_csv(os.path.join(output_dir, csv_filename))

    
    # 4. Plot Heatmap / Lineplot
    plot_filename = "ripley_function_plot.png"
    plt.close('all')
    fig, ax = plt.subplots(figsize=(10, 8))
    
    try:
        sq.pl.ripley(adata, cluster_key=cluster_key, mode=mode, ax=ax)
        fig.savefig(os.path.join(output_dir, plot_filename), dpi=300, bbox_inches='tight')
    except Exception as e:
        # Some old versions of squidpy have ax handling bugs. Fallback if needed.
        print(f"Warning: Failed to plot directly on ax: {e}. Saving via scanpy mechanisms or creating empty.")
        fig.savefig(os.path.join(output_dir, plot_filename), dpi=300, bbox_inches='tight')
    finally:
        plt.close(fig)

    end_time = time.time()
    
    # 5. Generate statistics
    stats_filename = "statistics.txt"
    with open(os.path.join(output_dir, stats_filename), 'w', encoding='utf-8') as f:
        f.write(f"=== Spatial Point Pattern Statistics (Ripley's {mode}) ===\n\n")
        f.write(f"Total Spots/Cells Processed: {adata.shape[0]}\n")
        f.write(f"Cluster Key Used: '{cluster_key}'\n")
        f.write(f"Number of Unique Clusters: {len(categories)}\n")
        f.write(f"Simulations (for CSR envelope): {n_simulations}\n")
        f.write(f"Random Seed: {seed}\n")
        f.write(f"Processing Time: {end_time - start_time:.2f} seconds\n\n")
        
        f.write("Output Artifacts:\n")
        f.write(f" - {csv_filename}: Underlying calculation scores (empiric, theory, CSR limits).\n")
        f.write(f" - {plot_filename}: Visual line plots for all clusters against distance thresholds.\n")
        
    return {
        "ripley_statistics.csv": csv_filename,
        "ripley_function_plot.png": plot_filename,
        "statistics.txt": stats_filename
    }
