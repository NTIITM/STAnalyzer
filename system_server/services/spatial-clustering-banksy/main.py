#!/usr/bin/env python3
"""
BANKSY空间域识别服务
提供基于空间邻域加权表达的空间域识别功能
"""
import os
import tempfile
import uuid
from typing import Dict, Literal

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse

# 导入生信依赖
import anndata as ad
import scanpy as sc
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif'] = ['Arial', 'DejaVu Sans', 'Liberation Sans']
plt.rcParams['axes.unicode_minus'] = False

try:
    from algorithm import detect_spatial_domains_banksy
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from algorithm import detect_spatial_domains_banksy

app = FastAPI(
    title="BANKSY空间域识别服务",
    description="基于空间邻域加权表达的空间域识别",
    version="1.0.0",
)

# 输出目录
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def read_adata(file_path: str, file_type: Literal["auto", "h5ad", "10x_h5", "csv", "tsv"] = "auto") -> ad.AnnData:
    """读取AnnData文件"""
    if file_type == "auto":
        if file_path.endswith(".h5ad"):
            return ad.read_h5ad(file_path)
        if file_path.endswith(".h5"):
            return sc.read_10x_h5(file_path)
        if file_path.endswith(".csv"):
            df = pd.read_csv(file_path, index_col=0)
            return ad.AnnData(X=df.values, var=pd.DataFrame(index=df.columns))
        if file_path.endswith(".tsv"):
            df = pd.read_csv(file_path, sep="\t", index_col=0)
            return ad.AnnData(X=df.values, var=pd.DataFrame(index=df.columns))
        return sc.read(file_path)
    
    if file_type == "h5ad":
        return ad.read_h5ad(file_path)
    if file_type == "10x_h5":
        return sc.read_10x_h5(file_path)
    if file_type == "csv":
        df = pd.read_csv(file_path, index_col=0)
        return ad.AnnData(X=df.values, var=pd.DataFrame(index=df.columns))
    if file_type == "tsv":
        df = pd.read_csv(file_path, sep="\t", index_col=0)
        return ad.AnnData(X=df.values, var=pd.DataFrame(index=df.columns))
    raise ValueError(f"不支持的文件类型: {file_type}")


def generate_plots(adata: ad.AnnData, output_dir: str, cluster_key: str, used_spatial: bool) -> Dict[str, str]:
    """生成空间域可视化图"""
    plot_files = {}
    if cluster_key not in adata.obs.columns:
        return plot_files
    
    os.makedirs(output_dir, exist_ok=True)
    
    # 设置scanpy绘图参数
    sc.settings.set_figure_params(dpi=300, facecolor='white', figsize=(10, 8))
    sc.settings.figdir = output_dir
    sc.settings.autosave = True
    sc.settings.autoshow = False
    
    # 1. UMAP图
    try:
        if 'X_umap' not in adata.obsm_keys():
            if 'X_pca' not in adata.obsm_keys():
                sc.tl.pca(adata, n_comps=30)
            # 在计算UMAP之前需要先构建neighbors图
            if 'neighbors' not in adata.uns:
                sc.pp.neighbors(adata, n_neighbors=15, n_pcs=30)
            sc.tl.umap(adata)
        
        if 'X_umap' in adata.obsm_keys():
            umap_id = f"{uuid.uuid4()}.png"
            save_name = umap_id.replace('.png', '')
            sc.pl.umap(adata, color=cluster_key, title='BANKSY Domains on UMAP', show=False, save=f'_{save_name}.png')
            
            scanpy_output = os.path.join(output_dir, f"umap_{save_name}.png")
            umap_path = os.path.join(output_dir, umap_id)
            if os.path.exists(scanpy_output):
                import shutil
                shutil.move(scanpy_output, umap_path)
                plot_files['domain_umap'] = umap_id
    except Exception as e:
        print(f"生成UMAP图失败: {e}")
    
    # 2. 空间分布图
    if used_spatial and 'spatial' in adata.obsm_keys():
        try:
            coords = adata.obsm['spatial']
            if coords is not None and coords.shape[0] == adata.n_obs:
                spatial_id = f"{uuid.uuid4()}.png"
                save_name = spatial_id.replace('.png', '')
                
                # 尝试使用空间背景图像
                library_id = None
                img_key = None
                if 'spatial' in adata.uns:
                    spatial_uns = adata.uns['spatial']
                    if isinstance(spatial_uns, dict):
                        for lib_id, lib_data in spatial_uns.items():
                            if isinstance(lib_data, dict) and 'images' in lib_data:
                                library_id = lib_id
                                images = lib_data['images']
                                for key in ['hires', 'lowres', 'fullres']:
                                    if key in images:
                                        img_key = key
                                        break
                                if img_key:
                                    break
                
                try:
                    if library_id and img_key:
                        sc.pl.spatial(adata, color=cluster_key, library_id=library_id, img_key=img_key,
                                     alpha=0.7, size=1.5, title='BANKSY Domains on Spatial Coordinates',
                                     show=False, save=f'_{save_name}.png')
                    else:
                        sc.pl.embedding(adata, basis='spatial', color=cluster_key,
                                       title='BANKSY Domains on Spatial Coordinates',
                                       show=False, save=f'_{save_name}.png')
                except:
                    sc.pl.embedding(adata, basis='spatial', color=cluster_key,
                                   title='BANKSY Domains on Spatial Coordinates',
                                   show=False, save=f'_{save_name}.png')
                
                # scanpy 的 sc.pl.spatial() 保存的文件名是 show_*.png，而不是 spatial_*.png
                # sc.pl.embedding() 保存的文件名是 embedding_*.png
                possible_outputs = [
                    os.path.join(output_dir, f"show_{save_name}.png"),  # sc.pl.spatial() 的默认命名
                    os.path.join(output_dir, f"spatial_{save_name}.png"),  # 可能的命名
                    os.path.join(output_dir, f"embedding_{save_name}.png"),  # sc.pl.embedding() 的默认命名
                ]
                
                spatial_path = os.path.join(output_dir, spatial_id)
                for scanpy_output in possible_outputs:
                    if os.path.exists(scanpy_output):
                        import shutil
                        shutil.move(scanpy_output, spatial_path)
                        plot_files['domain_spatial'] = spatial_id
                        break
        except Exception as e:
            print(f"生成空间图失败: {e}")
    
    return plot_files


@app.post("/api/detect")
async def detect_domains(
    file: UploadFile = File(...),
    file_type: Literal["auto", "h5ad", "10x_h5", "csv", "tsv"] = Form("auto"),
    n_neighbors: int = Form(15),
    lambda_adj: float = Form(0.2),
    resolution: float = Form(1.0),
    algorithm: Literal["leiden", "louvain"] = Form("leiden"),
    random_state: int = Form(0),
    n_pcs: int = Form(30),
    use_highly_variable: bool = Form(True),
) -> JSONResponse:
    """BANKSY空间域识别接口"""
    temp_input_path = None
    try:
        # 保存上传文件
        file_id = str(uuid.uuid4())
        temp_input_path = os.path.join(tempfile.gettempdir(), f"input_{file_id}_{file.filename}")
        with open(temp_input_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # 读取数据
        adata = read_adata(temp_input_path, file_type)
        
        # 检查空间坐标
        if 'spatial' not in adata.obsm_keys() and 'X_spatial' not in adata.obsm_keys() and 'spatial_coords' not in adata.obsm_keys():
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "缺少空间坐标，BANKSY方法需要空间坐标信息"},
            )
        
        # 执行BANKSY空间域识别
        cluster_key = "banksy"
        adata = detect_spatial_domains_banksy(
            adata,
            n_neighbors=n_neighbors,
            lambda_adj=lambda_adj,
            resolution=resolution,
            algorithm=algorithm,
            random_state=random_state,
            n_pcs=n_pcs,
            use_highly_variable=use_highly_variable
        )
        
        # 保存结果
        h5ad_id = f"{uuid.uuid4()}.h5ad"
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        output_file_path = os.path.join(OUTPUT_DIR, h5ad_id)
        adata.write_h5ad(output_file_path)
        
        # 生成可视化图
        plot_files = generate_plots(adata, OUTPUT_DIR, cluster_key, used_spatial=True)
        
        # 生成统计报告
        stats_text_parts = []
        stats_text_parts.append("=" * 60)
        stats_text_parts.append("BANKSY Spatial Domain Detection Statistical Report")
        stats_text_parts.append("=" * 60)
        stats_text_parts.append(f"\n[I. Analysis Parameters]")
        stats_text_parts.append(f"  Method: BANKSY (BANKSY: Spatial Clustering with Neighbor-Aware Gene Expression)")
        stats_text_parts.append(f"  Clustering algorithm: {algorithm}")
        stats_text_parts.append(f"  Number of neighbors: {n_neighbors}")
        stats_text_parts.append(f"  Lambda (neighbor weight): {lambda_adj}")
        stats_text_parts.append(f"  Resolution: {resolution}")
        stats_text_parts.append(f"  Random state: {random_state if random_state >= 0 else 'Non-deterministic'}")
        stats_text_parts.append(f"  Number of PCs: {n_pcs}")
        stats_text_parts.append(f"  Use highly variable genes: {'Yes' if use_highly_variable else 'No'}")
        
        stats_text_parts.append(f"\n[II. Data Statistics]")
        stats_text_parts.append(f"  Number of cells/spots: {adata.n_obs:,}")
        stats_text_parts.append(f"  Number of genes: {adata.n_vars:,}")
        
        if cluster_key in adata.obs.columns:
            domain_labels = adata.obs[cluster_key]
            n_domains = domain_labels.nunique()
            domain_counts = domain_labels.value_counts().sort_index()
            
            stats_text_parts.append(f"\n[III. Domain Detection Results]")
            stats_text_parts.append(f"  Number of spatial domains: {n_domains}")
            stats_text_parts.append(f"  Cell counts per domain:")
            for domain_id, count in domain_counts.items():
                percentage = (count / adata.n_obs) * 100
                stats_text_parts.append(f"    Domain {domain_id}: {count:,} ({percentage:.2f}%)")
            
            # Calculate differentially expressed genes for each domain
            stats_text_parts.append(f"\n[IV. Top 10 Differentially Expressed Genes per Domain]")
            try:
                # Ensure we have normalized data for DE analysis
                # Check X.max() safely for sparse matrices
                x_max = 0
                if hasattr(adata.X, 'max'):
                    try:
                        x_max = float(adata.X.max())
                    except:
                        if hasattr(adata.X, 'toarray'):
                            x_max = float(adata.X.toarray().max())
                        else:
                            x_max = float(np.max(adata.X))
                elif hasattr(adata.X, 'toarray'):
                    x_max = float(adata.X.toarray().max())
                else:
                    x_max = float(np.max(adata.X))
                
                if 'log1p' not in adata.layers and x_max > 20:
                    # Access raw counts from layers['counts'] (preprocessing service stores raw data here)
                    # For scanpy's rank_genes_groups, we need to set adata.raw if counts layer exists
                    if 'counts' in adata.layers and adata.raw is None:
                        # Create a copy of adata with counts layer as X for raw
                        adata_raw = adata.copy()
                        adata_raw.X = adata.layers['counts']
                        adata.raw = adata_raw
                    # Data might not be normalized, try to use raw if available
                    use_raw = adata.raw is not None
                else:
                    use_raw = False
                
                # Calculate differential expression
                sc.tl.rank_genes_groups(
                    adata,
                    groupby=cluster_key,
                    method='wilcoxon',
                    n_genes=10,
                    use_raw=use_raw
                )
                
                # Extract top genes for each domain
                if 'rank_genes_groups' in adata.uns:
                    result = adata.uns['rank_genes_groups']
                    domains = sorted(domain_labels.unique().astype(str))
                    
                    # Get available domain names from the result
                    available_domains = result['names'].dtype.names if result['names'].dtype.names else []
                    
                    for domain_id in domains:
                        domain_str = str(domain_id)
                        if domain_str in available_domains:
                            gene_names = result['names'][domain_str][:10]
                            scores = result['scores'][domain_str][:10]
                            pvals_adj = result['pvals_adj'][domain_str][:10]
                            logfoldchanges = result['logfoldchanges'][domain_str][:10]
                            
                            stats_text_parts.append(f"\n  Domain {domain_id}:")
                            for i, (gene, score, pval, logfc) in enumerate(zip(gene_names, scores, pvals_adj, logfoldchanges), 1):
                                stats_text_parts.append(
                                    f"    {i:2d}. {gene:15s} | Score: {score:7.2f} | "
                                    f"log2FC: {logfc:6.2f} | p_adj: {pval:.2e}"
                                )
                        else:
                            stats_text_parts.append(f"\n  Domain {domain_id}: No differential expression data available")
                else:
                    stats_text_parts.append("  Warning: Differential expression analysis failed")
            except Exception as e:
                stats_text_parts.append(f"  Warning: Differential expression analysis failed: {str(e)}")
        
        stats_text = "\n".join(stats_text_parts)
        
        # 保存统计报告
        statistics_id = f"{uuid.uuid4()}.txt"
        statistics_path = os.path.join(OUTPUT_DIR, statistics_id)
        with open(statistics_path, "w", encoding="utf-8") as f:
            f.write(stats_text)
        
        # 构建返回数据 - 参考 spatial-clustering 的返回格式
        data_dict = {"spatial_domain_data.h5ad": h5ad_id, "statistics.txt": statistics_id}
        expected_plots = {
            "domain_umap.png": "domain_umap",
            "domain_spatial.png": "domain_spatial",
        }
        
        for filename, plot_key in expected_plots.items():
            if plot_key in plot_files:
                data_dict[filename] = plot_files[plot_key]
        
        return JSONResponse(
            status_code=200,
            content={"success": True, "message": "BANKSY空间域识别完成", "data": data_dict},
        )
    except Exception as e:
        import traceback
        error_msg = str(e)
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"BANKSY空间域识别失败: {error_msg}"},
        )
    finally:
        if temp_input_path and os.path.exists(temp_input_path):
            try:
                os.remove(temp_input_path)
            except:
                pass


@app.get("/api/download/{file_id}")
async def download_file(file_id: str) -> FileResponse:
    """下载文件"""
    file_path = os.path.join(OUTPUT_DIR, file_id)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"文件不存在: {file_id}")
    
    if file_path.endswith(".png"):
        media_type = "image/png"
    else:
        media_type = "application/octet-stream"
    
    return FileResponse(path=file_path, filename=file_id, media_type=media_type)


@app.get("/health")
async def health():
    return {"status": "healthy", "output_dir": OUTPUT_DIR}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)

