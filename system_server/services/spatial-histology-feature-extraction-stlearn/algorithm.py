import scanpy as sc
import stlearn as st
import matplotlib.pyplot as plt
import os
import time

def process_histology_features(
        adata_path: str,
        use_gpu: bool,
        cnn_base: str,
        n_components: int,
        physical_distance: float,
        output_dir: str
):
    start_time = time.time()
    
    # 1. Load data
    adata = sc.read_h5ad(adata_path)
    
    # stlearn requires unstructured components like 'spatial' containing 'images'
    # For a typical 10x Visium downloaded structure:
    # adata.uns['spatial'][library_id]['images']['hires']
    
    if 'spatial' not in adata.uns:
        raise ValueError("No 'spatial' metadata found in uns. stLearn requires 10x Visium formatted data containing images.")
        
    # We enforce finding the first library
    library_id = list(adata.uns['spatial'].keys())[0]
    
    if 'images' not in adata.uns['spatial'][library_id]:
        raise ValueError(f"No 'images' found inside uns['spatial']['{library_id}']. Ensure Visium H&E image is loaded.")
        
    # 2. Extract morphological features from the H&E image using deep learning (ResNet50 / VGG16)
    if use_gpu:
        device = 'cuda'
    else:
        device = 'cpu'
        
    # This calls torchvision pre-trained models
    st.pp.tiling(adata, out_path=os.path.join(output_dir, "tiles"), crop_size=40)
    st.pp.extract_feature(adata, cnn_base=cnn_base, n_pca=n_components, device=device)
    
    # 3. SME (Spatial Morphological gene Expression) Normalization
    # It incorporates morphological variance and spatial proximity into transcript expression values.
    
    # First, calculate spatial distance based on physical mapping
    st.spatial.SME.SME_normalize(adata, use_data="raw", spatial_distance=physical_distance)
    # The SME normalized expression matrix will be stored in adata.obsm['SME_normalized']
    # Alternatively we can replace adata.X with it
    adata.X = adata.obsm['SME_normalized']
    
    # 4. Save modified AnnData
    h5ad_filename = "sme_normalized_data.h5ad"
    adata.write_h5ad(os.path.join(output_dir, h5ad_filename))
    
    # 5. Extract intermediate visualization of PCA on Morphology
    plot_filename = "morphology_PCA_plot.png"
    plt.close('all')
    fig, ax = plt.subplots(figsize=(8, 8))
    # plot the spatial coordinates colored by the first PCA component of morphological features
    try:
        sc.pl.spatial(adata, color="X_pca_morphology", components=['1'], ax=ax, show=False)
        fig.savefig(os.path.join(output_dir, plot_filename), dpi=300, bbox_inches='tight')
    except Exception as e:
        print(f"Warning: Failed to plot spatial morphology: {e}")
        fig.savefig(os.path.join(output_dir, plot_filename), dpi=300, bbox_inches='tight')
    finally:
        plt.close(fig)
        
    end_time = time.time()
    
    stats_filename = "statistics.txt"
    with open(os.path.join(output_dir, stats_filename), 'w', encoding='utf-8') as f:
        f.write(f"=== Histology Feature Extraction & SME Normalization (stLearn) ===\n\n")
        f.write(f"Total Spots Processed: {adata.shape[0]}\n")
        f.write(f"Total Genes: {adata.shape[1]}\n")
        f.write(f"CNN Base Model: {cnn_base}\n")
        f.write(f"PCA Morphological Components: {n_components}\n")
        f.write(f"Hardware utilized: {device}\n")
        f.write(f"Processing Time: {end_time - start_time:.2f} seconds\n\n")
        f.write("Output Artifacts:\n")
        f.write(f" - {h5ad_filename}: AnnData updated with morphological features (obsm['X_morphology']) and SME normalized X matrix.\n")
        f.write(f" - {plot_filename}: Projection of first morphological principal component on spatial axes.\n")
        
    return {
        "sme_normalized_data.h5ad": h5ad_filename,
        "morphology_PCA_plot.png": plot_filename,
        "statistics.txt": stats_filename
    }
