import scanpy as sc
import pandas as pd
import numpy as np
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

# 读取数据
scsa_adata = sc.read_h5ad('benchmark_results/20260104_143905/spatial-scsa-annotation_annotated_data.h5ad')
marker_adata = sc.read_h5ad('benchmark_results/20260104_143905/spatial-marker-gene-annotation_annotated_data.h5ad')

# Access raw counts from layers['counts'] (preprocessing service stores raw data here)
if 'counts' in scsa_adata.layers:
    X = scsa_adata.layers['counts']
    gene_names = scsa_adata.var_names
else:
    # Fallback: use X if counts layer is not available
    X = scsa_adata.X
    gene_names = scsa_adata.var_names

if hasattr(X, 'toarray'):
    X = X.toarray()

# 获取所有基因名（大写）
all_genes_upper = {g.upper(): g for g in gene_names}

# 大脑相关标志基因（尝试多种可能的命名）
marker_genes = {
    'Neuron': ['TUBB3', 'MAP2', 'SYP', 'SNAP25', 'RBFOX3', 'NEUN', 'GAD1', 'GAD2', 'VGLUT1', 'VGLUT2', 
               'TBR1', 'FEZF2', 'BCL11B', 'CTIP2', 'SATB2', 'CUX1', 'CUX2', 'RORB', 'FOXP2'],
    'Astrocyte': ['GFAP', 'AQP4', 'S100B', 'ALDH1L1', 'SLC1A3', 'GLAST', 'VIM', 'FABP7'],
    'Oligodendrocyte': ['MBP', 'MOG', 'OLIG2', 'PLP1', 'CNP', 'MOBP', 'MAG', 'CLDN11'],
    'Microglia': ['AIF1', 'CX3CR1', 'P2RY12', 'TMEM119', 'C1QA'],
    'Endothelial': ['PECAM1', 'CLDN5', 'FLT1', 'KDR', 'ENG'],
    'Schwann': ['MPZ', 'PMP22', 'SOX10', 'ERBB3']  # 施万细胞（外周神经系统）
}

def find_markers_in_data(marker_list):
    """找到数据中实际存在的标志基因"""
    found = []
    for marker in marker_list:
        if marker in all_genes_upper:
            found.append(all_genes_upper[marker])
        # 尝试小写
        elif marker.lower() in all_genes_upper:
            found.append(all_genes_upper[marker.lower()])
    return found

def check_marker_expression(adata, cluster_id, marker_list):
    """检查标志基因在指定 cluster 中的表达"""
    cluster_mask = adata.obs['layer'] == cluster_id
    if cluster_mask.sum() == 0:
        return []
    
    cluster_expr = X[cluster_mask, :]
    other_expr = X[~cluster_mask, :]
    
    results = []
    found_markers = find_markers_in_data(marker_list)
    
    for marker in found_markers:
        idx = list(gene_names).index(marker)
        mean_cluster = np.mean(cluster_expr[:, idx])
        mean_other = np.mean(other_expr[:, idx])
        log2fc = np.log2((mean_cluster + 1) / (mean_other + 1))
        results.append({
            'marker': marker,
            'mean_cluster': mean_cluster,
            'mean_other': mean_other,
            'log2fc': log2fc
        })
    
    return results

print('=' * 100)
print('综合分析报告：SCSA vs Marker-Gene 标注结果比较')
print('=' * 100)

clusters = ['Layer_1', 'Layer_2', 'Layer_3', 'Layer_4', 'Layer_5', 'Layer_6', 'WM']

results = []

for cluster in clusters:
    print(f'\n{"="*100}')
    print(f'Cluster: {cluster}')
    print(f'{"="*100}')
    
    # 获取标注结果
    scsa_mask = scsa_adata.obs['layer'] == cluster
    marker_mask = marker_adata.obs['layer'] == cluster
    
    scsa_celltype = scsa_adata.obs[scsa_mask]['cell_type'].iloc[0] if scsa_mask.sum() > 0 else 'Unknown'
    marker_celltype = marker_adata.obs[marker_mask]['cell_type'].iloc[0] if marker_mask.sum() > 0 else 'Unknown'
    
    print(f'SCSA 标注:        {scsa_celltype}')
    print(f'Marker-Gene 标注: {marker_celltype}')
    
    # 检查各类标志基因
    celltype_scores = {}
    for celltype, markers in marker_genes.items():
        marker_results = check_marker_expression(scsa_adata, cluster, markers)
        if marker_results:
            high_expr = [m for m in marker_results if m['log2fc'] > 0.2]
            score = len(high_expr) / len(markers) if markers else 0
            celltype_scores[celltype] = {
                'score': score,
                'found_markers': len(marker_results),
                'high_expr': len(high_expr),
                'top_markers': sorted(high_expr, key=lambda x: x['log2fc'], reverse=True)[:5]
            }
        else:
            celltype_scores[celltype] = {'score': 0, 'found_markers': 0, 'high_expr': 0, 'top_markers': []}
    
    # 找出最可能的细胞类型
    best_match = max(celltype_scores.items(), key=lambda x: x[1]['score'])
    best_celltype, best_info = best_match
    
    print(f'\n标志基因分析结果:')
    for celltype, info in sorted(celltype_scores.items(), key=lambda x: x[1]['score'], reverse=True):
        if info['score'] > 0:
            top_markers_str = ", ".join([f"{m['marker']}(log2FC={m['log2fc']:.2f})" for m in info['top_markers']])
            print(f'  {celltype:20s}: {info["score"]:.1%} ({info["high_expr"]}/{info["found_markers"]} 标志基因高表达)')
            if info['top_markers']:
                print(f'    前5个标志基因: {top_markers_str}')
    
    print(f'\n生物学判断:')
    print(f'  最可能的细胞类型: {best_celltype} (匹配度: {best_info["score"]:.1%})')
    
    # 判断标注是否正确
    scsa_correct = False
    marker_correct = False
    
    # 检查 SCSA 标注
    scsa_lower = scsa_celltype.lower()
    if best_celltype.lower() in scsa_lower or any(m.lower() in scsa_lower for m in [best_celltype]):
        scsa_correct = True
    elif best_celltype == 'Astrocyte' and 'astrocyte' in scsa_lower:
        scsa_correct = True
    elif best_celltype == 'Oligodendrocyte' and 'oligodendrocyte' in scsa_lower:
        scsa_correct = True
    elif best_celltype == 'Neuron' and any(n in scsa_lower for n in ['neuron', 'neural']):
        scsa_correct = True
    
    # 检查 Marker-Gene 标注
    marker_lower = marker_celltype.lower()
    if best_celltype.lower() in marker_lower or any(m.lower() in marker_lower for m in [best_celltype]):
        marker_correct = True
    elif best_celltype == 'Astrocyte' and 'astrocyte' in marker_lower:
        marker_correct = True
    elif best_celltype == 'Oligodendrocyte' and 'oligodendrocyte' in marker_lower:
        marker_correct = True
    elif best_celltype == 'Neuron' and any(n in marker_lower for n in ['neuron', 'neural']):
        marker_correct = True
    # 特殊情况：Schwann cell 不应该出现在大脑皮层
    if 'schwann' in marker_lower and cluster in ['Layer_1', 'Layer_2', 'Layer_3', 'Layer_4', 'Layer_5', 'Layer_6', 'WM']:
        marker_correct = False  # Schwann cell 是外周神经系统的，不应该在大脑皮层
    
    print(f'  SCSA 标注正确性: {"✓ 正确" if scsa_correct else "✗ 错误"}')
    print(f'  Marker-Gene 标注正确性: {"✓ 正确" if marker_correct else "✗ 错误"}')
    
    # 特殊情况说明
    if 'pancreatic' in scsa_lower or 'acinar' in scsa_lower:
        print(f'  ⚠ 警告: SCSA 标注为胰腺相关细胞类型，这在大脑皮层数据中是不合理的')
    if 'schwann' in marker_lower:
        print(f'  ⚠ 警告: Marker-Gene 标注为施万细胞，这是外周神经系统的细胞，不应该出现在大脑皮层')
    
    results.append({
        'cluster': cluster,
        'scsa_celltype': scsa_celltype,
        'marker_celltype': marker_celltype,
        'best_match': best_celltype,
        'best_score': best_info['score'],
        'scsa_correct': scsa_correct,
        'marker_correct': marker_correct
    })

# 总结
print(f'\n{"="*100}')
print('总体评估')
print(f'{"="*100}')

scsa_correct_count = sum(1 for r in results if r['scsa_correct'])
marker_correct_count = sum(1 for r in results if r['marker_correct'])

print(f'\n标注正确率:')
print(f'  SCSA:        {scsa_correct_count}/{len(results)} ({scsa_correct_count/len(results):.1%})')
print(f'  Marker-Gene: {marker_correct_count}/{len(results)} ({marker_correct_count/len(results):.1%})')

print(f'\n详细结果:')
for r in results:
    scsa_status = "✓" if r['scsa_correct'] else "✗"
    marker_status = "✓" if r['marker_correct'] else "✗"
    print(f"  {r['cluster']:10s} | SCSA: {scsa_status} {r['scsa_celltype']:30s} | Marker: {marker_status} {r['marker_celltype']:30s} | 实际: {r['best_match']} ({r['best_score']:.1%})")

print(f'\n结论:')
if scsa_correct_count > marker_correct_count:
    print(f'  → SCSA 方法的标注结果更符合生物学实际情况')
elif marker_correct_count > scsa_correct_count:
    print(f'  → Marker-Gene 方法的标注结果更符合生物学实际情况')
else:
    print(f'  → 两种方法的标注正确率相同')

