# Spatial TF Activity Service

Pure-Python spatial TF activity inference for clustered spatial RNA-seq data, built with FastAPI + decoupler-py. Implements DoRothEA-based VIPER/AUCell scoring, optional spatial smoothing, cluster summaries, and spatial heatmaps.

## Quick start
```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 56110
```

POST `/api/spatial-tf-activity` with form-data:
- `file`: clustered_spatial_rna_seq_data (h5ad/csv/tsv)
- Optional params: `file_type`, `spatial_key`, `species`, `gene_id_type`, `tf_set`, `method`, `smooth_scores`, `knn_k`, `radius`, `sigma`, `top_tfs_per_cluster`, `generate_plots`, `chunk_size`

Outputs (stored in `outputs/`):
- `tf_activity_scores.csv`
- `tf_cluster_summary.csv`
- `tf_activity_report.txt`
- `tf_activity_plots.png` (when `generate_plots=true`)

