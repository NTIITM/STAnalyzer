#!/usr/bin/env python3
"""
测试 SpaGE 空间插补服务
"""
import requests
import os
import time
import sys

# 测试数据路径
TEST_DATA_DIR = "/home/common/hwluo/project/system_server/services/spatial-imputation-tangram-service/data/without"
SPATIAL_FILE = os.path.join(TEST_DATA_DIR, "slideseq_MOp_1217.h5ad")
SINGLE_CELL_FILE = os.path.join(TEST_DATA_DIR, "mop_sn_tutorial.h5ad")

# 服务地址
BASE_URL = "http://localhost:40153"
IMPUTE_ENDPOINT = f"{BASE_URL}/api/impute"
HEALTH_ENDPOINT = f"{BASE_URL}/health"

def test_health():
    """测试健康检查端点"""
    print("=" * 60)
    print("测试健康检查端点...")
    try:
        response = requests.get(HEALTH_ENDPOINT, timeout=5)
        print(f"状态码: {response.status_code}")
        print(f"响应: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"健康检查失败: {e}")
        return False

def test_impute():
    """测试插补端点"""
    print("=" * 60)
    print("测试插补端点...")
    
    if not os.path.exists(SPATIAL_FILE):
        print(f"错误: 空间数据文件不存在: {SPATIAL_FILE}")
        return False
    
    if not os.path.exists(SINGLE_CELL_FILE):
        print(f"错误: 单细胞数据文件不存在: {SINGLE_CELL_FILE}")
        return False
    
    print(f"空间数据文件: {SPATIAL_FILE} ({os.path.getsize(SPATIAL_FILE) / 1024 / 1024:.2f} MB)")
    print(f"单细胞数据文件: {SINGLE_CELL_FILE} ({os.path.getsize(SINGLE_CELL_FILE) / 1024 / 1024:.2f} MB)")
    
    try:
        with open(SPATIAL_FILE, 'rb') as f1, open(SINGLE_CELL_FILE, 'rb') as f2:
            files = {
                'spatial_file': ('slideseq_MOp_1217.h5ad', f1, 'application/octet-stream'),
                'single_cell_file': ('mop_sn_tutorial.h5ad', f2, 'application/octet-stream'),
            }
            data = {
                'spatial_file_type': 'auto',
                'single_cell_file_type': 'auto',
                'k_neighbors': 10,
                'n_pcs': 30,
                'top_genes': 3000,
                'seed': 1234,
            }
            
            print("\n发送请求...")
            start_time = time.time()
            response = requests.post(IMPUTE_ENDPOINT, files=files, data=data, timeout=600)
            elapsed_time = time.time() - start_time
            
            print(f"状态码: {response.status_code}")
            print(f"耗时: {elapsed_time:.2f} 秒")
            
            if response.status_code == 200:
                result = response.json()
                print(f"\n成功! 响应:")
                print(f"  success: {result.get('success')}")
                print(f"  message: {result.get('message')}")
                if 'data' in result:
                    print(f"  输出文件:")
                    for key, value in result['data'].items():
                        print(f"    {key}: {value}")
                return True
            else:
                print(f"\n失败! 响应:")
                print(response.text)
                return False
                
    except Exception as e:
        print(f"请求失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("开始测试 SpaGE 空间插补服务")
    print(f"服务地址: {BASE_URL}")
    
    # 先测试健康检查
    if not test_health():
        print("\n健康检查失败，请确保服务正在运行")
        print("启动服务: cd /home/common/hwluo/project/system_server/services/spatial-imputation-spage-service && python3 main.py")
        sys.exit(1)
    
    # 测试插补
    if test_impute():
        print("\n" + "=" * 60)
        print("所有测试通过!")
    else:
        print("\n" + "=" * 60)
        print("测试失败!")
        sys.exit(1)














