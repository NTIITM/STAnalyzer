#!/usr/bin/env python3
"""
SpatialDE 空间差异表达分析服务
提供基于高斯过程的空间差异表达基因检测功能
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
    from algorithm import perform_spatial_de_analysis
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from algorithm import perform_spatial_de_analysis

app = FastAPI(
    title="SpatialDE 空间差异表达分析服务",
    description="基于高斯过程的空间差异表达基因检测",
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


def generate_plots(adata: ad.AnnData, results_df: pd.DataFrame, output_dir: str, spatial_key: str = "spatial") -> Dict[str, str]:
    """生成空间差异表达可视化图"""
    plot_files = {}
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        # 检查空间坐标
        if spatial_key not in adata.obsm_keys():
            for key in ['X_spatial', 'spatial_coords']:
                if key in adata.obsm_keys():
                    spatial_key = key
                    break
            else:
                return plot_files
        
        coords = adata.obsm[spatial_key]
        
        # 1. 火山图：FSV vs qval
        if 'FSV' in results_df.columns and 'qval' in results_df.columns:
            try:
                volcano_id = f"{uuid.uuid4()}.png"
                volcano_path = os.path.join(output_dir, volcano_id)
                
                fig, ax = plt.subplots(figsize=(8, 6))
                
                # 标记显著基因
                significant = results_df['qval'] < 0.05
                non_significant = ~significant
                
                ax.scatter(results_df.loc[non_significant, 'FSV'], 
                          -np.log10(results_df.loc[non_significant, 'qval'] + 1e-10),
                          c='gray', alpha=0.5, s=20, label='Non-significant')
                ax.scatter(results_df.loc[significant, 'FSV'],
                          -np.log10(results_df.loc[significant, 'qval'] + 1e-10),
                          c='red', alpha=0.7, s=30, label='Significant (qval < 0.05)')
                
                ax.axhline(-np.log10(0.05), c='black', linestyle='--', linewidth=1, label='qval = 0.05')
                ax.set_xlabel('Fraction Spatial Variance (FSV)', fontsize=12)
                ax.set_ylabel('-log10(q-value)', fontsize=12)
                ax.set_title('SpatialDE Volcano Plot', fontsize=14, fontweight='bold')
                ax.legend()
                ax.grid(True, alpha=0.3)
                
                plt.tight_layout()
                plt.savefig(volcano_path, dpi=300, bbox_inches='tight')
                plt.close()
                
                plot_files['volcano_plot'] = volcano_id
            except Exception as e:
                print(f"生成火山图失败: {e}")
        
        # 2. Top 显著基因的空间表达图
        if len(results_df) > 0:
            try:
                # 获取 top 5 显著基因
                top_genes = results_df.nsmallest(5, 'qval')['g'].tolist()
                
                # 检查这些基因是否在 adata 中
                available_genes = [g for g in top_genes if g in adata.var_names]
                
                if len(available_genes) > 0:
                    n_genes = min(5, len(available_genes))
                    fig, axes = plt.subplots(1, n_genes, figsize=(4*n_genes, 4))
                    if n_genes == 1:
                        axes = [axes]
                    
                    for i, gene in enumerate(available_genes[:n_genes]):
                        ax = axes[i]
                        
                        # 获取基因表达
                        if gene in adata.var_names:
                            gene_idx = adata.var_names.get_loc(gene)
                            if hasattr(adata.X, 'toarray'):
                                expr = adata.X[:, gene_idx].toarray().flatten()
                            else:
                                expr = adata.X[:, gene_idx]
                            
                            # 绘制空间表达图
                            scatter = ax.scatter(coords[:, 0], coords[:, 1], 
                                                c=expr, cmap='viridis', s=10, alpha=0.7)
                            ax.set_title(f'{gene}\nqval={results_df[results_df["g"]==gene]["qval"].values[0]:.2e}', 
                                       fontsize=10)
                            ax.set_xlabel('X coordinate', fontsize=9)
                            ax.set_ylabel('Y coordinate', fontsize=9)
                            ax.axis('equal')
                            plt.colorbar(scatter, ax=ax, fraction=0.046)
                    
                    spatial_expr_id = f"{uuid.uuid4()}.png"
                    spatial_expr_path = os.path.join(output_dir, spatial_expr_id)
                    plt.tight_layout()
                    plt.savefig(spatial_expr_path, dpi=300, bbox_inches='tight')
                    plt.close()
                    
                    plot_files['top_genes_spatial'] = spatial_expr_id
            except Exception as e:
                print(f"生成空间表达图失败: {e}")
        
    except Exception as e:
        print(f"生成可视化图失败: {e}")
    
    return plot_files


@app.post("/api/analyze")
async def analyze_spatial_de(
    file: UploadFile = File(...),
    file_type: Literal["auto", "h5ad", "10x_h5", "csv", "tsv"] = Form("auto"),
    min_counts: int = Form(1),
    min_cells: int = Form(10),
) -> JSONResponse:
    """SpatialDE 空间差异表达分析接口"""
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
                content={
                    "success": False, 
                    "message": "缺少空间坐标，SpatialDE 方法需要空间坐标信息",
                    "error": "Missing spatial coordinates in data"
                },
            )
        
        # 执行 SpatialDE 分析
        results_df, adata = perform_spatial_de_analysis(
            adata,
            min_counts=min_counts,
            min_cells=min_cells
        )
        
        # 保存结果到 CSV
        csv_id = f"{uuid.uuid4()}.csv"
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        csv_path = os.path.join(OUTPUT_DIR, csv_id)
        results_df.to_csv(csv_path, index=False)
        
        # 保存处理后的数据
        h5ad_id = f"{uuid.uuid4()}.h5ad"
        output_file_path = os.path.join(OUTPUT_DIR, h5ad_id)
        adata.write_h5ad(output_file_path)
        
        # 生成可视化图
        plot_files = generate_plots(adata, results_df, OUTPUT_DIR)
        
        # 生成统计报告
        stats_text_parts = []
        stats_text_parts.append("=" * 60)
        stats_text_parts.append("SpatialDE Spatial Differential Expression Analysis Report")
        stats_text_parts.append("=" * 60)
        stats_text_parts.append(f"\n[I. Analysis Parameters]")
        stats_text_parts.append(f"  Method: SpatialDE (Gaussian Process-based Spatial DE)")
        stats_text_parts.append(f"  Note: Input data is assumed to be preprocessed")
        stats_text_parts.append(f"  Minimum gene counts: {min_counts}")
        stats_text_parts.append(f"  Minimum cells expressing gene: {min_cells}")
        
        stats_text_parts.append(f"\n[II. Data Statistics]")
        stats_text_parts.append(f"  Number of cells/spots: {adata.n_obs:,}")
        stats_text_parts.append(f"  Total number of genes: {adata.n_vars:,}")
        stats_text_parts.append(f"  Number of genes analyzed: {len(results_df):,}")
        
        stats_text_parts.append(f"\n[III. SpatialDE Results Summary]")
        if len(results_df) > 0:
            n_significant = (results_df['qval'] < 0.05).sum() if 'qval' in results_df.columns else 0
            n_highly_significant = (results_df['qval'] < 0.01).sum() if 'qval' in results_df.columns else 0
            
            stats_text_parts.append(f"  Total genes tested: {len(results_df):,}")
            stats_text_parts.append(f"  Significant genes (qval < 0.05): {n_significant:,} ({100*n_significant/len(results_df):.2f}%)")
            stats_text_parts.append(f"  Highly significant genes (qval < 0.01): {n_highly_significant:,} ({100*n_highly_significant/len(results_df):.2f}%)")
            
            if 'FSV' in results_df.columns:
                stats_text_parts.append(f"  Mean FSV (Fraction Spatial Variance): {results_df['FSV'].mean():.4f}")
                stats_text_parts.append(f"  Median FSV: {results_df['FSV'].median():.4f}")
                stats_text_parts.append(f"  Max FSV: {results_df['FSV'].max():.4f}")
            
            if 'LLR' in results_df.columns:
                stats_text_parts.append(f"  Mean LLR (Log Likelihood Ratio): {results_df['LLR'].mean():.4f}")
                stats_text_parts.append(f"  Max LLR: {results_df['LLR'].max():.4f}")
            
            # Top 10 显著基因
            stats_text_parts.append(f"\n[IV. Top 10 Most Significant Spatially Variable Genes]")
            if 'qval' in results_df.columns:
                top_genes = results_df.nsmallest(10, 'qval')
                for i, (idx, row) in enumerate(top_genes.iterrows(), 1):
                    gene = row.get('g', 'N/A')
                    qval = row.get('qval', np.nan)
                    pval = row.get('pval', np.nan)
                    llr = row.get('LLR', np.nan)
                    fsv = row.get('FSV', np.nan)
                    l = row.get('l', np.nan)
                    
                    stats_text_parts.append(
                        f"  {i:2d}. {gene:15s} | qval: {qval:.2e} | pval: {pval:.2e} | "
                        f"LLR: {llr:7.2f} | FSV: {fsv:.4f} | l: {l:.4f}"
                    )
        else:
            stats_text_parts.append("  Warning: No genes passed filtering criteria")
        
        stats_text = "\n".join(stats_text_parts)
        
        # 保存统计报告
        statistics_id = f"{uuid.uuid4()}.txt"
        statistics_path = os.path.join(OUTPUT_DIR, statistics_id)
        with open(statistics_path, "w", encoding="utf-8") as f:
            f.write(stats_text)
        
        # 构建返回数据
        data_dict = {
            "spatial_de_results.csv": csv_id,
            "spatial_de_data.h5ad": h5ad_id,
            "statistics.txt": statistics_id
        }
        
        expected_plots = {
            "volcano_plot.png": "volcano_plot",
            "top_genes_spatial.png": "top_genes_spatial",
        }
        
        for filename, plot_key in expected_plots.items():
            if plot_key in plot_files:
                data_dict[filename] = plot_files[plot_key]
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True, 
                "message": "SpatialDE 空间差异表达分析完成", 
                "data": data_dict
            },
        )
    except ValueError as e:
        error_msg = str(e)
        return JSONResponse(
            status_code=400,
            content={
                "success": False, 
                "message": f"数据格式错误: {error_msg}",
                "error": error_msg
            },
        )
    except ImportError as e:
        error_msg = str(e)
        return JSONResponse(
            status_code=500,
            content={
                "success": False, 
                "message": f"依赖包缺失: {error_msg}",
                "error": error_msg
            },
        )
    except Exception as e:
        import traceback
        error_msg = str(e)
        error_traceback = traceback.format_exc()
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={
                "success": False, 
                "message": f"SpatialDE 分析失败: {error_msg}",
                "error": error_msg,
                "traceback": error_traceback
            },
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
    elif file_path.endswith(".csv"):
        media_type = "text/csv"
    elif file_path.endswith(".txt"):
        media_type = "text/plain"
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

