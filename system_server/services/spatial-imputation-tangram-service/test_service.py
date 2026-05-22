#!/usr/bin/env python3
"""
测试 Tangram 空间插补服务
使用 data/without 目录下的测试数据
"""
import requests
import json
import time
import os

# 服务配置
BASE_URL = "http://localhost:38411"
TEST_DATA_DIR = "/home/common/hwluo/project/system_server/services/spatial-imputation-tangram-service/data/without"

# 测试数据文件
SPATIAL_FILE = os.path.join(TEST_DATA_DIR, "slideseq_MOp_1217.h5ad")
SINGLE_CELL_FILE = os.path.join(TEST_DATA_DIR, "mop_sn_tutorial.h5ad")

def test_health():
    """测试健康检查端点"""
    print("=" * 60)
    print("Testing /health endpoint...")
    print("=" * 60)
    
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()
    
    return response.status_code == 200

def test_impute():
    """测试插补端点"""
    print("=" * 60)
    print("Testing /api/impute endpoint...")
    print("=" * 60)
    
    # 检查文件是否存在
    if not os.path.exists(SPATIAL_FILE):
        print(f"ERROR: Spatial file not found: {SPATIAL_FILE}")
        return False
    
    if not os.path.exists(SINGLE_CELL_FILE):
        print(f"ERROR: Single-cell file not found: {SINGLE_CELL_FILE}")
        return False
    
    print(f"Spatial file: {SPATIAL_FILE} ({os.path.getsize(SPATIAL_FILE) / 1024 / 1024:.2f} MB)")
    print(f"Single-cell file: {SINGLE_CELL_FILE} ({os.path.getsize(SINGLE_CELL_FILE) / 1024 / 1024:.2f} MB)")
    print()
    
    # 准备文件上传
    files = {
        'spatial_file': ('slideseq_MOp_1217.h5ad', open(SPATIAL_FILE, 'rb'), 'application/octet-stream'),
        'single_cell_file': ('mop_sn_tutorial.h5ad', open(SINGLE_CELL_FILE, 'rb'), 'application/octet-stream'),
    }
    
    # 准备参数（使用默认值）
    data = {
        'spatial_file_type': 'auto',
        'single_cell_file_type': 'auto',
        'mode': 'cells',
        'n_epochs': 250,
        'learning_rate': 0.005,
        'lambda_dreg': 5.0,
        'top_genes': 3000,
        'seed': 1234,
    }
    
    print("Sending request...")
    print(f"Parameters: {json.dumps(data, indent=2)}")
    print()
    
    try:
        # 发送请求
        start_time = time.time()
        response = requests.post(
            f"{BASE_URL}/api/impute",
            files=files,
            data=data,
            timeout=3600  # 1 hour timeout for large files
        )
        elapsed_time = time.time() - start_time
        
        print(f"Status Code: {response.status_code}")
        print(f"Elapsed Time: {elapsed_time:.2f} seconds")
        print()
        
        if response.status_code == 200:
            result = response.json()
            print("SUCCESS! Response:")
            print(json.dumps(result, indent=2))
            
            # 检查输出文件
            if 'output_files' in result:
                print("\nOutput files:")
                for file_info in result['output_files']:
                    print(f"  - {file_info.get('filename', 'unknown')}: {file_info.get('file_id', 'N/A')}")
            
            return True
        else:
            print("ERROR! Response:")
            try:
                error_data = response.json()
                print(json.dumps(error_data, indent=2))
            except:
                print(response.text)
            return False
            
    except requests.exceptions.Timeout:
        print("ERROR: Request timed out (exceeded 1 hour)")
        return False
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {str(e)}")
        return False
    finally:
        # 关闭文件
        files['spatial_file'][1].close()
        files['single_cell_file'][1].close()

def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("Tangram Spatial Imputation Service Test")
    print("=" * 60 + "\n")
    
    # 测试健康检查
    if not test_health():
        print("Health check failed. Service may not be running.")
        return
    
    # 测试插补端点
    success = test_impute()
    
    print("\n" + "=" * 60)
    if success:
        print("TEST PASSED!")
    else:
        print("TEST FAILED!")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    main()
