#!/usr/bin/env python3
"""
测试 SpatialDE 服务 API
"""
import requests
import json

BASE_URL = "http://localhost:42593"

def test_health():
    """测试健康检查接口"""
    print("Testing health endpoint...")
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    print()

def test_analyze(file_path: str):
    """测试分析接口"""
    print(f"Testing analyze endpoint with file: {file_path}")
    
    with open(file_path, 'rb') as f:
        files = {'file': f}
        data = {
            'file_type': 'h5ad',
            'normalize': True,
            'use_highly_variable': True,
            'min_counts': 1,
            'min_cells': 10,
        }
        
        response = requests.post(f"{BASE_URL}/api/analyze", files=files, data=data)
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        print()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        test_analyze(sys.argv[1])
    else:
        test_health()
        print("Usage: python test_api.py <path_to_h5ad_file>")

