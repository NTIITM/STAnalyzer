#!/usr/bin/env python3
"""调试脚本：检查数据文件结构"""
import scanpy as sc
import sys

data_file = sys.argv[1] if len(sys.argv) > 1 else '/home/common/hwluo/project/spatial_domain_data.h5ad'

print(f"Reading data file: {data_file}")
adata = sc.read_h5ad(data_file)

print(f"\n=== 数据基本信息 ===")
print(f"Shape: {adata.shape} (cells x genes)")
print(f"Number of cells: {adata.n_obs}")
print(f"Number of genes: {adata.n_vars}")

print(f"\n=== 基因名信息 ===")
print(f"First 30 gene names: {list(adata.var_names[:30])}")
print(f"Last 30 gene names: {list(adata.var_names[-30:])}")
print(f"Gene names containing 'x': {[g for g in adata.var_names if 'x' in str(g).lower()][:10]}")
print(f"Gene names containing 'y': {[g for g in adata.var_names if 'y' in str(g).lower()][:10]}")

print(f"\n=== 空间坐标信息 ===")
print(f"obsm keys: {list(adata.obsm_keys())}")
if 'spatial' in adata.obsm_keys():
    coords = adata.obsm['spatial']
    print(f"Spatial coords shape: {coords.shape}")
    print(f"Spatial coords (first 5):\n{coords[:5]}")

print(f"\n=== 表达矩阵信息 ===")
print(f"X shape: {adata.X.shape}")
print(f"X type: {type(adata.X)}")
if hasattr(adata.X, 'toarray'):
    expr = adata.X.toarray()
else:
    expr = adata.X
print(f"Expression matrix stats:")
print(f"  Min: {expr.min()}, Max: {expr.max()}, Mean: {expr.mean():.2f}")
print(f"  Non-zero entries: {(expr > 0).sum()} / {expr.size}")

print(f"\n=== 基因筛选测试 ===")
gene_counts = expr.sum(axis=0)
cell_counts = (expr > 0).sum(axis=0)
print(f"Gene counts: min={gene_counts.min()}, max={gene_counts.max()}, mean={gene_counts.mean():.2f}")
print(f"Cell counts: min={cell_counts.min()}, max={cell_counts.max()}, mean={cell_counts.mean():.2f}")

min_counts = 1
min_cells = 10
min_counts_mask = gene_counts >= min_counts
min_cells_mask = cell_counts >= min_cells
final_mask = min_counts_mask & min_cells_mask
print(f"\nFiltering with min_counts={min_counts}, min_cells={min_cells}:")
print(f"  Genes passing min_counts: {min_counts_mask.sum()}")
print(f"  Genes passing min_cells: {min_cells_mask.sum()}")
print(f"  Genes passing both: {final_mask.sum()}")

if final_mask.sum() > 0:
    filtered_genes = adata.var_names[final_mask].tolist()
    print(f"\nFiltered gene names (first 20): {filtered_genes[:20]}")
    print(f"Filtered gene names (last 20): {filtered_genes[-20:]}")

