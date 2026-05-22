#!/usr/bin/env python3
"""
测试 BANKSY 算法
使用 /home/common/hwluo/project/Data/ST/151507.h5ad 数据
"""

import sys
import os
import scanpy as sc
import numpy as np
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from algorithm import detect_spatial_domains_banksy

def test_banksy():
    """测试 BANKSY 算法"""
    
    # 数据路径（支持容器内外路径）
    data_path = os.getenv("TEST_DATA_PATH", "/data/ST/151507.h5ad")
    if not os.path.exists(data_path):
        # 尝试本地路径
        data_path = "/home/common/hwluo/project/Data/ST/151507.h5ad"
    
    print("=" * 60)
    print("BANKSY 算法测试")
    print("=" * 60)
    
    # 1. 加载数据
    print("\n1. 加载数据...")
    adata = sc.read_h5ad(data_path)
    print(f"   数据形状: {adata.shape}")
    print(f"   观察列: {list(adata.obs.columns)}")
    print(f"   空间坐标键: {list(adata.obsm.keys())}")
    
    # 检查空间坐标
    if 'spatial' in adata.obsm:
        spatial_coords = adata.obsm['spatial']
        print(f"   空间坐标形状: {spatial_coords.shape}")
        print(f"   空间坐标范围: X=[{spatial_coords[:, 0].min():.2f}, {spatial_coords[:, 0].max():.2f}], "
              f"Y=[{spatial_coords[:, 1].min():.2f}, {spatial_coords[:, 1].max():.2f}]")
    else:
        print("   警告: 未找到空间坐标信息")
        return
    
    # 2. 数据预处理
    print("\n2. 数据预处理...")
    # 确保变量名唯一
    adata.var_names_make_unique()
    
    # 基本统计
    print(f"   总计数范围: [{adata.X.sum(axis=1).min():.0f}, {adata.X.sum(axis=1).max():.0f}]")
    
    # 3. 运行 BANKSY 算法
    print("\n3. 运行 BANKSY 算法...")
    try:
        result = detect_spatial_domains_banksy(
            adata=adata,
            spatial_key='spatial',
            algorithm='leiden',
            resolution=0.5,
            n_neighbors=15
        )
        
        print("   ✓ BANKSY 算法运行成功!")
        print(f"   结果形状: {result.shape}")
        
        # 检查聚类结果
        cluster_key = 'banksy_leiden'
        if cluster_key in result.obs.columns:
            n_clusters = result.obs[cluster_key].nunique()
            print(f"   聚类数量: {n_clusters}")
            print(f"   聚类分布:")
            print(result.obs[cluster_key].value_counts().sort_index())
        else:
            print(f"   警告: 未找到聚类结果列 '{cluster_key}'")
            print(f"   可用的 obs 列: {list(result.obs.columns)}")
        
        # 检查嵌入
        if 'X_banksy' in result.obsm:
            print(f"   BANKSY 嵌入形状: {result.obsm['X_banksy'].shape}")
        else:
            print("   警告: 未找到 BANKSY 嵌入")
            print(f"   可用的 obsm 键: {list(result.obsm.keys())}")
        
        # 4. 保存结果
        print("\n4. 保存结果...")
        output_dir = os.getenv("OUTPUT_DIR", "/app/outputs")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "test_output_151507.h5ad")
        result.write(output_path)
        print(f"   结果已保存到: {output_path}")
        
        print("\n" + "=" * 60)
        print("测试完成!")
        print("=" * 60)
        
        return result
        
    except Exception as e:
        print(f"\n✗ 错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    test_banksy()

