#!/usr/bin/env python
"""
Seed default file types into MongoDB.

Usage:
    poetry run python scripts/seed_file_types.py
    poetry run python scripts/seed_file_types.py --dry-run
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Dict, List

# Ensure project root is on sys.path when executed via `python scripts/...`
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from textmsa.services.data.user_data_manager_mongodb import UserDataManagerMongoDB

logger = logging.getLogger("textmsa.seed_file_types")

# Default type list (English, aligned with docs/file-type-minimal-plan.md)
DEFAULT_FILE_TYPES: List[Dict[str, object]] = [
    {
        "file_type_id": "spatial_rna_seq_data",
        "name": "spatial_rna_seq_data",
        "display_name": "Spatial transcriptomics raw data",
        "description": "AnnData object (h5ad format) containing raw spatial transcriptomics expression matrix with spatial coordinates stored in obsm['spatial']. Includes gene expression counts (X matrix), cell/spot metadata (obs), gene metadata (var), and optional histology images or other spatial metadata. This is the initial data format before any preprocessing, filtering, or normalization steps. Supports both h5ad files and 10x Visium format archive files (zip or tar.gz, automatically converted to h5ad on upload).",
        "category": "spatial_transcriptomics",
        "extensions": [".h5ad",".gz"],
        "meta": {"obsm_required": ["spatial"]},
    },
    {
        "file_type_id": "preprocessed_spatial_data",
        "name": "preprocessed_spatial_data",
        "display_name": "Preprocessed spatial data",
        "description": "AnnData object (h5ad format) containing preprocessed spatial transcriptomics data. Has undergone quality control filtering (removed low-quality cells/spots and genes), normalization (e.g., log-normalization, SCTransform), and optionally dimensionality reduction (PCA). Contains spatial coordinates in obsm['spatial'], normalized expression matrix (X), cell/spot metadata with QC metrics (obs), gene metadata (var), and low-dimensional embeddings (obsm) such as PCA or UMAP if computed.",
        "category": "spatial_transcriptomics",
        "extensions": [".h5ad",".gz"],
        "meta": {"obsm_required": ["spatial"]},
    },
    {
        "file_type_id": "clustered_spatial_rna_seq_data",
        "name": "clustered_spatial_rna_seq_data",
        "display_name": "Clustered spatial data",
        "description": "AnnData object (h5ad format) containing spatial transcriptomics data with clustering labels assigned to cells/spots. Includes cluster assignments stored in obs (typically 'leiden' or 'louvain' columns), spatial coordinates in obsm['spatial'], low-dimensional embeddings (UMAP, t-SNE, or PCA in obsm), neighbor graph (uns), and clustering parameters (uns). Used for identifying spatially coherent groups, domains, or cell populations in tissue.",
        "category": "spatial_transcriptomics",
        "extensions": [".h5ad"],
        "meta": {"obsm_required": ["spatial"]},
    },
    {
        "file_type_id": "annotated_spatial_rna_seq_data",
        "name": "annotated_spatial_rna_seq_data",
        "display_name": "Annotated spatial data",
        "description": "AnnData object (h5ad format) containing spatial transcriptomics data with cell type annotations, region labels, or other metadata assignments. Includes annotation labels stored in obs (e.g., 'cell_type', 'annotation', 'region'), spatial coordinates in obsm['spatial'], expression matrix (X), and optionally confidence scores or annotation metadata. Annotations may be derived from marker gene analysis, reference-based annotation, or manual curation.",
        "category": "spatial_transcriptomics",
        "extensions": [".h5ad"],
        "meta": {"obsm_required": ["spatial"]},
    },
    {
        "file_type_id": "imputed_spatial_data",
        "name": "imputed_spatial_data",
        "display_name": "Imputed spatial expression",
        "description": "AnnData object (h5ad format) containing spatial transcriptomics data with imputed or mapped expression from single-cell reference data. The expression matrix (X) contains imputed gene expression values derived from methods such as Tangram, SpaGE, or other spatial-to-single-cell mapping approaches. Preserves spatial coordinates in obsm['spatial'], original spot/cell metadata in obs, and includes imputation parameters and statistics in uns. Used to enhance spatial data resolution or predict expression of unmeasured genes.",
        "category": "spatial_transcriptomics",
        "extensions": [".h5ad"],
        "meta": {"obsm_required": ["spatial"]},
    },
    {
        "file_type_id": "deconvolved_spatial_data",
        "name": "deconvolved_spatial_data",
        "display_name": "Deconvolved spatial data",
        "description": "AnnData object (h5ad format) containing spatial transcriptomics data after cell-type deconvolution analysis. Includes inferred cell-type abundance estimates stored in obsm (e.g., 'means_cell_abundance_w_sf', 'q05_cell_abundance_w_sf'), spatial coordinates preserved in obsm['spatial'], original expression matrix (X), and deconvolution parameters and statistics in uns. Used to estimate the proportion of different cell types at each spatial location, typically using methods like cell2location, CARD, or similar approaches.",
        "category": "spatial_transcriptomics",
        "extensions": [".h5ad"],
        "meta": {"obsm_required": ["spatial"]},
    },
    {
        "file_type_id": "trajectory_spatial_data",
        "name": "trajectory_spatial_data",
        "display_name": "Spatial trajectory data",
        "description": "AnnData object (h5ad format) containing spatial transcriptomics data with trajectory inference results. Includes pseudotime values in obs['pseudotime'] indicating progression along inferred trajectories, trajectory connectivities or branch assignments in obs, spatial coordinates in obsm['spatial'], and optionally UMAP or other embeddings in obsm. Used to identify developmental trajectories, spatial gradients, or temporal ordering of cells/spots in tissue context.",
        "category": "spatial_transcriptomics",
        "extensions": [".h5ad"],
        "meta": {"obs_required": ["pseudotime"]},
    },
    {
        "file_type_id": "single_cell_rna_seq_data",
        "name": "single_cell_rna_seq_data",
        "display_name": "Single-cell RNA-seq raw data",
        "description": "AnnData object (h5ad) containing raw single-cell RNA-seq expression matrix. Includes gene expression counts (X matrix), cell metadata (obs with cell barcodes and QC metrics), gene metadata (var with gene identifiers), and optionally batch information or other annotations. This is the initial data format before preprocessing, filtering, or normalization steps.",
        "category": "single_cell",
        "extensions": [".h5ad",".gz"],
    },
    {
        "file_type_id": "preprocessed_single_cell_data",
        "name": "preprocessed_single_cell_data",
        "display_name": "Preprocessed single-cell data",
        "description": "AnnData object (h5ad format) containing preprocessed single-cell RNA-seq data. Has undergone quality control filtering (removed low-quality cells and genes), normalization (e.g., log-normalization, SCTransform), highly variable gene selection, and dimensionality reduction (PCA). Contains normalized expression matrix (X), cell metadata with QC metrics (obs), gene metadata (var), and low-dimensional embeddings (obsm) such as PCA or UMAP if computed.",
        "category": "single_cell",
        "extensions": [".h5ad"],
    },
    {
        "file_type_id": "clustered_single_cell_data",
        "name": "clustered_single_cell_data",
        "display_name": "Clustered single-cell data",
        "description": "AnnData object (h5ad format) containing single-cell RNA-seq data with clustering labels assigned to cells. Includes cluster assignments stored in obs (typically 'leiden' or 'louvain' columns), low-dimensional embeddings (UMAP, t-SNE, or PCA in obsm), neighbor graph (uns), and clustering parameters (uns). Used for identifying distinct cell populations or cell types based on expression similarity.",
        "category": "single_cell",
        "extensions": [".h5ad"],
    },
    {
        "file_type_id": "gwas_genotype_raw",
        "name": "gwas_genotype_raw",
        "display_name": "GWAS raw genotype",
        "description": "Original GWAS (Genome-Wide Association Study) genotype files in standard formats. Supports PLINK binary format (.bed, .bim, .fam file set), PLINK text format (.raw), VCF (Variant Call Format), or BCF (Binary VCF). Contains unprocessed genotype data with variants (SNPs/indels) and sample genotypes, typically requiring quality control, filtering, and imputation before association analysis.",
        "category": "genomics",
        "extensions": [".raw", ".vcf", ".bcf", ".bed", ".bim", ".fam"],
    },
    {
        "file_type_id": "gwas_genotype_processed",
        "name": "gwas_genotype_processed",
        "display_name": "Processed GWAS genotype",
        "description": "GWAS genotype data after quality control and imputation steps. Has undergone variant and sample filtering (removed low-quality variants, samples with high missingness, Hardy-Weinberg equilibrium violations), missing genotype imputation, and format standardization. Available in PLINK binary format (.bed, .bim, .fam) or VCF/BCF format. Ready for association testing with phenotype data.",
        "category": "genomics",
        "extensions": [".bed", ".bim", ".fam", ".vcf", ".bcf"],
    },
    {
        "file_type_id": "gwas_phenotype",
        "name": "gwas_phenotype",
        "display_name": "GWAS phenotype/covariate",
        "description": "CSV or TSV file containing GWAS phenotype and covariate data. Includes sample identifiers matching genotype data, phenotype values (continuous traits like height, blood pressure, or categorical traits like disease status), and covariates (age, sex, batch, principal components, or other confounding variables). Used as input for GWAS association analysis after alignment with genotype data.",
        "category": "genomics",
        "extensions": [".csv", ".tsv"],
    },
    {
        "file_type_id": "phenotype_processed_csv",
        "name": "phenotype_processed_csv",
        "display_name": "Processed phenotype table",
        "description": "CSV file containing processed GWAS phenotype and covariate data after quality control, encoding, alignment, and standardization. Typical columns include: sample_id (sample identifier matching genotype data), phenotype values (continuous or categorical traits), and covariates (age, sex, batch, principal components, or other confounding variables). Used as input for GWAS association testing after preprocessing steps such as missing value imputation, outlier removal, and normalization.",
        "category": "genomics",
        "extensions": [".csv"],
    },
    {
        "file_type_id": "dge_results_csv",
        "name": "dge_results_csv",
        "display_name": "Differential expression results",
        "description": "CSV file containing differential gene expression (DGE) analysis results comparing groups, clusters, or spatial domains. Typical columns include: group (group identifier for comparison, e.g., cluster or spatial region), gene (gene identifier/symbol), score (gene score from rank_genes_groups method), pval (raw statistical p-value from differential expression test), pval_adj (adjusted p-value using multiple testing correction such as Benjamini-Hochberg), logfoldchange (log2 fold change between group and reference), and optionally mean expression values per group.",
        "category": "transcriptomics",
        "extensions": [".csv"],
        "meta": {"columns_required": ["group", "gene", "pval_adj", "logfoldchange"]},
    },
    {
        "file_type_id": "pathway_enrichment_csv",
        "name": "pathway_enrichment_csv",
        "display_name": "Pathway/GO enrichment results",
        "description": "CSV file containing functional enrichment analysis results from pathway or gene ontology (GO) databases. Each row represents an enriched pathway or gene set. Typical columns include: Term (pathway or gene set name, e.g., GO term, KEGG pathway, Reactome pathway, or MSigDB gene set), pval_adj (adjusted p-value for enrichment significance), gene_ratio (ratio of input genes found in the pathway), overlap (number of overlapping genes), pval (raw p-value), odds_ratio (enrichment odds ratio), and gene lists or other enrichment statistics.",
        "category": "transcriptomics",
        "extensions": [".csv"],
        "meta": {"columns_required": ["term", "pval_adj", "gene_ratio"]},
    },
    {
        "file_type_id": "ligrec_interactions_csv",
        "name": "ligrec_interactions_csv",
        "display_name": "Ligand-receptor interactions",
        "description": "CSV file containing ligand-receptor interaction analysis results or prioritization scores. Identifies potential cell-cell communication through ligand-receptor pairs. Typical columns include: ligand (ligand gene identifier), receptor (receptor gene identifier), score (interaction strength or prioritization score), source (sender cell type or cluster), target (receiver cell type or cluster), pval or pvalue (statistical significance if available), and optionally mean expression values or other interaction metrics.",
        "category": "single_cell",
        "extensions": [".csv"],
        "meta": {"columns_required": ["ligand", "receptor", "score"]},
    },
    {
        "file_type_id": "cell_abundance_matrix_csv",
        "name": "cell_abundance_matrix_csv",
        "display_name": "Cell abundance matrix",
        "description": "CSV file containing cell-type abundance matrix per spatial location. Rows represent spatial locations (spots/cells), columns represent cell types. Values indicate the estimated abundance or proportion of each cell type at each spatial location, typically derived from deconvolution methods such as cell2location or similar approaches.",
        "category": "spatial_transcriptomics",
        "extensions": [".csv"],
        "meta": {"columns_required": []},
    },
    {
        "file_type_id": "mapping_scores_csv",
        "name": "mapping_scores_csv",
        "display_name": "Mapping/imputation scores",
        "description": "CSV file containing mapping scores and distances for spatial-to-single-cell mapping or imputation. Typical columns include: spot_id (spatial location identifier), nearest_cell_id (identifier of nearest single-cell reference cell), distance (distance in PCA space or expression space), mapping_score (confidence score for the mapping), and n_neighbors (number of neighbors used in imputation).",
        "category": "spatial_transcriptomics",
        "extensions": [".csv"],
        "meta": {"columns_required": ["cell_id", "score"]},
    },
    {
        "file_type_id": "spatialde_results_csv",
        "name": "spatialde_results_csv",
        "display_name": "SpatialDE results",
        "description": "CSV file containing SpatialDE or NaiveDE spatially variable gene analysis results. Identifies genes with spatially structured expression patterns. Required columns include: gene (gene identifier), pval (raw p-value from spatial variation test), qval (adjusted p-value, FDR-corrected), l (length scale parameter indicating spatial correlation range), and FSV (fraction of spatial variance, proportion of variance explained by spatial structure). Additional columns may include model fit statistics, mean expression, or other spatial variation metrics.",
        "category": "spatial_transcriptomics",
        "extensions": [".csv"],
        "meta": {"columns_required": ["gene", "pval", "qval", "l", "FSV"]},
    },
    {
        "file_type_id": "coexpression_edges_csv",
        "name": "coexpression_edges_csv",
        "display_name": "Coexpression network edges",
        "description": "CSV file containing edge list for gene coexpression networks. Each row represents a connection between two genes based on expression correlation. Typical columns include: gene1 (first gene identifier in the edge), gene2 (second gene identifier in the edge), correlation (correlation coefficient, e.g., Pearson or Spearman), pval (p-value for correlation significance if available), and optionally weight or other edge attributes. Used to construct gene coexpression networks for module detection and pathway analysis.",
        "category": "transcriptomics",
        "extensions": [".csv"],
        "meta": {"columns_required": ["gene1", "gene2", "correlation"]},
    },
    {
        "file_type_id": "grn_network_csv",
        "name": "grn_network_csv",
        "display_name": "Gene regulatory network results",
        "description": "CSV file containing gene regulatory network (GRN) inference results from time-series single-cell transcriptomics data. Each row represents a regulatory interaction (edge) between a transcription factor (TF) and its target gene. Typical columns include: TF (transcription factor gene identifier or index), Target (target gene identifier or index), score (regulatory interaction strength or confidence score), and time_point (time point identifier for dynamic networks). May include additional columns such as pval (statistical significance), direction (activation/repression), or other interaction metrics. Used to identify regulatory relationships, construct regulatory networks, and analyze temporal dynamics of gene regulation.",
        "category": "transcriptomics",
        "extensions": [".csv"],
        "meta": {"columns_required": ["TF", "Target", "score"]},
    },
    {
        "file_type_id": "module_genes_csv",
        "name": "module_genes_csv",
        "display_name": "Module genes",
        "description": "CSV file containing gene membership information for coexpression modules. Each row represents a gene assigned to a specific module. Typical columns include: module (coexpression module identifier, often a number or color name), gene (gene identifier/symbol), and optionally module_score (gene's contribution to the module) or other membership metrics. Used to identify groups of coexpressed genes that may share biological functions or regulatory mechanisms.",
        "category": "transcriptomics",
        "extensions": [".csv"],
        "meta": {"columns_required": ["module", "gene"]},
    },
    {
        "file_type_id": "module_enrichment_csv",
        "name": "module_enrichment_csv",
        "display_name": "Module enrichment results",
        "description": "CSV file containing functional enrichment analysis results for gene coexpression modules. Each row represents an enriched pathway or gene set for a specific module. Typical columns include: module (coexpression module identifier), term (pathway or gene set name, e.g., GO term or KEGG pathway), pval_adj (adjusted p-value for enrichment significance), gene_ratio (ratio of module genes in the pathway), and other enrichment statistics.",
        "category": "transcriptomics",
        "extensions": [".csv"],
        "meta": {"columns_required": ["module", "term", "pval_adj"]},
    },
    {
        "file_type_id": "spatial_autocorr_results_csv",
        "name": "spatial_autocorr_results_csv",
        "display_name": "Spatial autocorrelation results",
        "description": "CSV file containing spatial autocorrelation analysis results for each gene. Measures the spatial clustering or dispersion of gene expression patterns. Typical columns include: gene (gene identifier), morans_i or gearys_c (autocorrelation statistic value), pval (raw p-value from statistical test), pval_adj (adjusted p-value for multiple testing correction), and optionally z_score or other test statistics. Positive autocorrelation indicates spatial clustering, negative indicates spatial dispersion.",
        "category": "spatial_transcriptomics",
        "extensions": [".csv"],
        "meta": {"columns_required": ["gene", "pval", "pval_adj"]},
    },
    {
        "file_type_id": "spatial_neighborhood_enrichment_csv",
        "name": "spatial_neighborhood_enrichment_csv",
        "display_name": "Spatial neighborhood enrichment",
        "description": "CSV file containing spatial neighborhood enrichment analysis results. Typically computed using tools like Squidpy to assess co-localization or repulsion between spatial domains or cell types. Matrix represents pairwise enrichment z-scores where rows and columns are cluster or cell type labels. High positive z-scores indicate spatial co-localization, while negative scores indicate spatial avoidance in the tissue microenvironment.",
        "category": "spatial_transcriptomics",
        "extensions": [".csv"],
    },
    {
        "file_type_id": "spatial_point_pattern_csv",
        "name": "spatial_point_pattern_csv",
        "display_name": "Spatial point pattern statistics",
        "description": "CSV file containing spatial point pattern statistics results, such as Ripley's K, L, or G function values across various distance radii. Typically used to evaluate whether specific biological features or cell types exhibit clustered, dispersed, or random spatial distributions. Contains spatial distance bins and corresponding calculated metric values, alongside theoretical expected values under Complete Spatial Randomness (CSR) for comparison.",
        "category": "spatial_transcriptomics",
        "extensions": [".csv"],
    },
    {
        "file_type_id": "generic_csv",
        "name": "generic_csv",
        "display_name": "Generic CSV",
        "description": "Generic comma-separated values (CSV) table file. Used as a fallback type for various analysis results that do not fit into specific categories, such as pathway activity scores, transcription factor activity scores, annotation statistics, cluster summaries, or other tabular data outputs.",
        "category": "generic",
        "extensions": [".csv"],
    },
    {
        "file_type_id": "generic_tsv",
        "name": "generic_tsv",
        "display_name": "Generic TSV",
        "description": "Generic tab-separated values (TSV) table file. Used as a fallback type for various analysis results that do not fit into specific categories, similar to generic_csv but using tab delimiters. Suitable for tabular data outputs that require tab separation or are provided in .tsv/.txt format.",
        "category": "generic",
        "extensions": [".tsv", ".txt"],
    },
    {
        "file_type_id": "qc_summary_json",
        "name": "qc_summary_json",
        "display_name": "QC summary (JSON)",
        "description": "JSON file containing quality control metrics, run statistics, and analysis parameters. Typically includes run parameters (algorithm settings, thresholds), device information, data statistics (gene counts, observation counts), quality metrics, gene intersection information, distance summaries, and other metadata for reproducibility and result interpretation.",
        "category": "generic",
        "extensions": [".json"],
    },
    {
        "file_type_id": "model_params_json",
        "name": "model_params_json",
        "display_name": "Model parameters (JSON)",
        "description": "JSON file containing serialized model parameters, algorithm configurations, or analysis settings. Includes hyperparameters, thresholds, random seeds, and other configuration details used during analysis. Used for reproducibility, result interpretation, and ensuring consistent analysis parameters across runs or for sharing analysis configurations.",
        "category": "generic",
        "extensions": [".json"],
    },
    {
        "file_type_id": "txt_report",
        "name": "txt_report",
        "display_name": "Text report",
        "description": "Plain-text report file (UTF-8 encoding) containing comprehensive analysis statistics, summary information, and workflow details. Typically includes analysis parameters, data overview (observation counts, gene counts, cluster information), statistical summaries, quality control metrics, and references to output files. Used for documenting analysis results and reproducibility.",
        "category": "document",
        "extensions": [".txt"],
    },
    {
        "file_type_id": "pdf_report",
        "name": "pdf_report",
        "display_name": "PDF report",
        "description": "PDF (Portable Document Format) file containing formatted analysis reports, visualizations, or documentation. Typically includes text summaries, figures, tables, and other formatted content suitable for sharing, publication, or archival purposes. Provides a standardized, non-editable format for comprehensive analysis documentation.",
        "category": "document",
        "extensions": [".pdf"],
    },
    {
        "file_type_id": "generic_png",
        "name": "generic_png",
        "display_name": "PNG image",
        "description": "Generic PNG (Portable Network Graphics) image file. Used for various visualization outputs that do not fit into specific plot categories, such as QC plots, distribution histograms, bar charts, scatter plots, volcano plots, or other general-purpose visualizations. Typically generated at 300 DPI resolution for publication quality.",
        "category": "image",
        "extensions": [".png"],
    },
    {
        "file_type_id": "spatial_plot_png",
        "name": "spatial_plot_png",
        "display_name": "Spatial plot (PNG)",
        "description": "PNG image file (typically 300 DPI) containing spatial overlay plots showing data mapped onto spatial coordinates. Visualizes spatial distribution of features such as clusters, cell types, gene expression, domain assignments, boundaries, or other annotations overlaid on the original spatial tissue coordinates. Used to assess spatial patterns, continuity, and organization of biological features in tissue context.",
        "category": "image",
        "extensions": [".png"],
        "meta": {"plot_type": "spatial"},
    },
    {
        "file_type_id": "umap_plot_png",
        "name": "umap_plot_png",
        "display_name": "UMAP plot (PNG)",
        "description": "PNG image file (typically 300 DPI) containing UMAP (Uniform Manifold Approximation and Projection) embedding visualization. Shows cells or spots projected into 2D space based on expression similarity, colored by clusters, cell types, annotations, or other metadata. Used to assess separation of groups, identify cell populations, and visualize high-dimensional expression patterns in a low-dimensional space.",
        "category": "image",
        "extensions": [".png"],
        "meta": {"plot_type": "umap"},
    },
    {
        "file_type_id": "heatmap_png",
        "name": "heatmap_png",
        "display_name": "Heatmap (PNG)",
        "description": "PNG image file (typically 300 DPI) containing heatmap visualizations. Displays expression values, scores, or other quantitative data as color-coded matrices. Typically includes hierarchical clustering dendrograms for rows (genes/features) and columns (samples/cells), annotation bars for group membership, and color scales. Used to visualize expression patterns, differential genes, domain-specific features, or other matrix-based data with clustering relationships.",
        "category": "image",
        "extensions": [".png"],
        "meta": {"plot_type": "heatmap"},
    },
    {
        "file_type_id": "network_png",
        "name": "network_png",
        "display_name": "Network plot (PNG)",
        "description": "PNG image file (typically 300 DPI) containing network or graph visualizations. Displays nodes (genes, cells, or other entities) connected by edges (interactions, correlations, or relationships). May include node coloring by modules or attributes, edge weights, layout algorithms (force-directed, circular, etc.), and legends. Used to visualize coexpression networks, ligand-receptor interactions, spatial communication networks, or other graph-structured biological relationships.",
        "category": "image",
        "extensions": [".png"],
        "meta": {"plot_type": "network"},
    },
    {
        "file_type_id": "generic_jpg",
        "name": "generic_jpg",
        "display_name": "JPG image",
        "description": "JPEG/JPG (Joint Photographic Experts Group) image file. Compressed raster image format suitable for photographs or complex images with many colors. Used for various visualization outputs, typically at standard resolution. Note: PNG format is generally preferred for scientific plots due to lossless compression, but JPG may be used for specific use cases requiring smaller file sizes.",
        "category": "image",
        "extensions": [".jpg", ".jpeg"],
    },
    {
        "file_type_id": "generic_svg",
        "name": "generic_svg",
        "display_name": "SVG image",
        "description": "SVG (Scalable Vector Graphics) image file. Vector-based image format that scales without quality loss, making it ideal for plots, diagrams, and illustrations. SVG files are XML-based and can be edited, styled with CSS, and embedded in web pages. Preferred for publication-quality figures that require scalability and editability.",
        "category": "image",
        "extensions": [".svg"],
    },
    {
        "file_type_id": "unknown",
        "name": "unknown",
        "display_name": "Unknown file type",
        "description": "Placeholder file type for legacy files, unrecognized formats, or files that do not match any defined file type schema. Used as a fallback when the actual file type cannot be determined or when handling legacy data that predates the current file type classification system.",
        "category": "generic",
        "extensions": [".unknown"],
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed default file types into MongoDB.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show which records would be created without writing to MongoDB.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser.parse_args()


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="[%(levelname)s] %(message)s")


def ensure_default_types(manager: UserDataManagerMongoDB, dry_run: bool = False) -> None:
    created, skipped = [], []
    for payload in DEFAULT_FILE_TYPES:
        name = payload["name"]
        existing = manager.get_file_type_by_name(name)
        if existing:
            skipped.append(name)
            logger.debug("File type '%s' already exists (id=%s)", name, existing.get("file_type_id"))
            continue
        if dry_run:
            created.append(name)
            logger.info("[DRY-RUN] would create file type '%s'", name)
            continue
        created_doc = manager.create_file_type(payload)
        created.append(name)
        logger.info(
            "Created file type '%s' (id=%s)",
            name,
            created_doc.get("file_type_id"),
        )
    logger.info("Seed summary: created=%d, skipped=%d", len(created), len(skipped))
    if skipped:
        logger.info("Skipped names: %s", ", ".join(skipped))
    if dry_run and created:
        logger.info("Dry-run pending creations: %s", ", ".join(created))


def main() -> None:
    args = parse_args()
    configure_logging(args.verbose)
    manager = UserDataManagerMongoDB()
    ensure_default_types(manager, dry_run=args.dry_run)


if __name__ == "__main__":
    main()


