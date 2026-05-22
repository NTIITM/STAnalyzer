#!/usr/bin/env python3
"""
测试 GraphST 空间聚类服务的 API
"""
import requests
import json
import time
import sys

# 配置
API_URL = "http://localhost:48244/api/graphst-cluster"
DATA_FILE = "/home/common/hwluo/project/Data/ST/151507_hvg.h5ad"

def test_graphst_cluster():
    """测试 GraphST 聚类 API"""
    print("=" * 60)
    print("GraphST 空间聚类服务测试")
    print("=" * 60)
    print(f"数据文件: {DATA_FILE}")
    print(f"API 端点: {API_URL}")
    print()
    
    # 检查服务是否可用
    try:
        health_response = requests.get("http://localhost:48244/health", timeout=5)
        if health_response.status_code == 200:
            print("✓ 服务健康检查通过")
            print(f"  响应: {health_response.json()}")
        else:
            print(f"✗ 服务健康检查失败: {health_response.status_code}")
            return
    except Exception as e:
        print(f"✗ 无法连接到服务: {e}")
        return
    
    print()
    print("开始上传数据并调用聚类 API...")
    print("-" * 60)
    
    # 准备请求参数
    with open(DATA_FILE, 'rb') as f:
        files = {'file': ('151507_hvg.h5ad', f, 'application/octet-stream')}
        data = {
            'file_type': 'h5ad',
            'resolution': 1.0,
            'algorithm': 'leiden',
            'random_state': 41,
            'device': 'cpu',  # 使用 CPU 以避免 GPU 相关问题
            'epochs': 100,  # 减少 epoch 数量以加快测试
        }
        
        start_time = time.time()
        try:
            print("正在发送请求...")
            response = requests.post(API_URL, files=files, data=data, timeout=3600)
            elapsed_time = time.time() - start_time
            
            print(f"\n请求完成 (耗时: {elapsed_time:.2f} 秒)")
            print("-" * 60)
            print(f"状态码: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print("\n✓ 聚类成功!")
                print(f"消息: {result.get('message', 'N/A')}")
                
                if 'data' in result:
                    print("\n生成的文件:")
                    for filename, file_id in result['data'].items():
                        print(f"  - {filename}: {file_id}")
                    
                    # 尝试下载统计报告
                    if 'statistics.txt' in result['data']:
                        stats_id = result['data']['statistics.txt']
                        stats_url = f"http://localhost:48244/api/download/{stats_id}"
                        try:
                            stats_response = requests.get(stats_url, timeout=10)
                            if stats_response.status_code == 200:
                                print("\n统计报告预览 (前 50 行):")
                                print("-" * 60)
                                stats_lines = stats_response.text.split('\n')[:50]
                                for line in stats_lines:
                                    print(line)
                        except Exception as e:
                            print(f"\n无法下载统计报告: {e}")
            else:
                print(f"\n✗ 聚类失败")
                print(f"响应: {response.text}")
                
        except requests.exceptions.Timeout:
            print("\n✗ 请求超时 (超过 3600 秒)")
        except Exception as e:
            print(f"\n✗ 请求失败: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_graphst_cluster()


































