# Spatial Metabolic Activity Service

Pure-Python spatial pathway activity inference for clustered spatial RNA-seq data, built with FastAPI + gseapy ssGSEA. Supports MSigDB Hallmark + KEGG by default, optional spatial smoothing, cluster summaries, and spatial heatmaps.

## Quick start
```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 56111
```

POST `/api/spatial-metabolic-activity` with form-data:
- `file`: clustered_spatial_rna_seq_data (h5ad/csv/tsv)
- Optional params: `file_type`, `spatial_key`, `cluster_key`, `species`, `gene_id_type`, `gene_set_library`, `smooth_scores`, `knn_k`, `radius`, `sigma`, `top_pathways_per_cluster`, `chunk_size`, `min_size`, `max_size`

Outputs (stored in `outputs/`):
- `pathway_activity_scores.csv`
- `pathway_cluster_summary.csv`
- `pathway_activity_report.txt`
- `pathway_activity_plots.png`

