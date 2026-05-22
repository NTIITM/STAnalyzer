#!/usr/bin/env python3
"""
测试 BANKSY 服务的 API 端点
"""
import os
import sys
import requests
import json
import time
from pathlib import Path

# 服务地址
BASE_URL = "http://localhost:8080"

def test_health():
    """测试健康检查端点"""
    print("=" * 60)
    print("测试 1: 健康检查")
    print("=" * 60)
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=10)
        response.raise_for_status()
        data = response.json()
        print(f"✓ 健康检查成功")
        print(f"  状态: {data.get('status')}")
        print(f"  输出目录: {data.get('output_dir')}")
        return True
    except Exception as e:
        print(f"✗ 健康检查失败: {e}")
        return False

def test_detect(test_file_path):
    """测试空间域检测端点"""
    print("\n" + "=" * 60)
    print("测试 2: 空间域检测")
    print("=" * 60)
    
    if not os.path.exists(test_file_path):
        print(f"✗ 测试文件不存在: {test_file_path}")
        return None
    
    print(f"使用测试文件: {test_file_path}")
    print(f"文件大小: {os.path.getsize(test_file_path) / 1024 / 1024:.2f} MB")
    
    try:
        # 准备文件上传
        with open(test_file_path, 'rb') as f:
            files = {'file': (os.path.basename(test_file_path), f, 'application/octet-stream')}
            data = {
                'file_type': 'auto',
                'n_neighbors': 6,
                'lambda_adj': 0.2,
                'resolution': 0.8,
                'algorithm': 'leiden',
                'random_state': 0,
                'n_pcs': 30,
                'use_highly_variable': True
            }
            
            print("\n发送请求到 /api/detect...")
            print(f"参数: {json.dumps(data, indent=2)}")
            
            start_time = time.time()
            response = requests.post(
                f"{BASE_URL}/api/detect",
                files=files,
                data=data,
                timeout=600  # 10分钟超时
            )
            elapsed_time = time.time() - start_time
            
            print(f"\n响应时间: {elapsed_time:.2f} 秒")
            print(f"状态码: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"✓ 检测成功!")
                print(f"\n返回结果:")
                print(json.dumps(result, indent=2, ensure_ascii=False))
                
                # 检查返回的文件ID
                if result.get('success'):
                    file_ids = result.get('data', {})
                    print(f"\n生成的文件:")
                    for file_type, file_id in file_ids.items():
                        print(f"  {file_type}: {file_id}")
                    
                    return file_ids
                else:
                    print(f"✗ 检测失败: {result.get('message')}")
                    return None
            else:
                print(f"✗ 请求失败")
                print(f"响应内容: {response.text}")
                return None
                
    except requests.exceptions.Timeout:
        print(f"✗ 请求超时（超过10分钟）")
        return None
    except Exception as e:
        print(f"✗ 检测失败: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_download(file_id, file_type="h5ad"):
    """测试文件下载端点"""
    print("\n" + "=" * 60)
    print(f"测试 3: 下载文件 ({file_type})")
    print("=" * 60)
    
    try:
        print(f"下载文件ID: {file_id}")
        response = requests.get(
            f"{BASE_URL}/api/download/{file_id}",
            timeout=60,
            stream=True
        )
        
        if response.status_code == 200:
            # 保存文件
            output_dir = "./test_outputs"
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, f"downloaded_{file_id}")
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            file_size = os.path.getsize(output_path)
            print(f"✓ 下载成功!")
            print(f"  文件大小: {file_size / 1024 / 1024:.2f} MB")
            print(f"  保存路径: {output_path}")
            
            # 如果是h5ad文件，尝试读取验证
            if file_id.endswith('.h5ad'):
                try:
                    import scanpy as sc
                    adata = sc.read_h5ad(output_path)
                    print(f"  数据形状: {adata.shape}")
                    print(f"  观察列: {list(adata.obs.columns)[:10]}...")
                    if 'banksy_leiden' in adata.obs.columns:
                        n_clusters = adata.obs['banksy_leiden'].nunique()
                        print(f"  聚类数量: {n_clusters}")
                except Exception as e:
                    print(f"  警告: 无法读取h5ad文件: {e}")
            
            return True
        else:
            print(f"✗ 下载失败: 状态码 {response.status_code}")
            print(f"响应内容: {response.text[:500]}")
            return False
            
    except Exception as e:
        print(f"✗ 下载失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("BANKSY 服务 API 测试")
    print("=" * 60)
    
    # 查找测试数据
    test_data_paths = [
        "/home/common/hwluo/project/Data/ST/151507.h5ad",
        "/home/common/hwluo/project/system_server/services/banksy-service/outputs/test_output_151507.h5ad",
        "./test_output_151507.h5ad"
    ]
    
    test_file = None
    for path in test_data_paths:
        if os.path.exists(path):
            test_file = path
            break
    
    if not test_file:
        print("\n✗ 未找到测试数据文件")
        print("请确保以下文件之一存在:")
        for path in test_data_paths:
            print(f"  - {path}")
        return
    
    # 运行测试
    results = {}
    
    # 1. 健康检查
    results['health'] = test_health()
    
    if not results['health']:
        print("\n✗ 服务不可用，停止测试")
        return
    
    # 2. 空间域检测
    file_ids = test_detect(test_file)
    results['detect'] = file_ids is not None
    
    if file_ids:
        # 3. 下载结果文件
        download_results = {}
        for file_type, file_id in file_ids.items():
            download_results[file_type] = test_download(file_id, file_type)
        results['download'] = all(download_results.values())
    
    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    print(f"健康检查: {'✓' if results.get('health') else '✗'}")
    print(f"空间域检测: {'✓' if results.get('detect') else '✗'}")
    print(f"文件下载: {'✓' if results.get('download') else '✗'}")
    
    if all(results.values()):
        print("\n✓ 所有测试通过!")
    else:
        print("\n✗ 部分测试失败")

if __name__ == "__main__":
    main()

