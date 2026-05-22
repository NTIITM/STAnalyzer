#!/usr/bin/env python3
"""
测试 SpaTrack 轨迹推断服务
"""
import requests
import os
import sys

BASE_URL = "http://localhost:44988"


def test_health():
    """测试健康检查端点"""
    print("Testing /health endpoint...")
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    assert response.status_code == 200
    print("✓ Health check passed\n")


def test_spatrack_pseudotime(file_path: str):
    """测试轨迹推断端点"""
    print(f"Testing /api/spatrack-pseudotime endpoint with file: {file_path}")
    
    if not os.path.exists(file_path):
        print(f"✗ File not found: {file_path}")
        return False
    
    with open(file_path, "rb") as f:
        files = {"file": (os.path.basename(file_path), f, "application/octet-stream")}
        data = {
            "file_type": "h5ad",
            "cluster_key": "layer",
            "n_neigh_pos": "50",
            "entropy_method": "auto",
        }
        
        response = requests.post(
            f"{BASE_URL}/api/spatrack-pseudotime",
            files=files,
            data=data,
        )
    
    print(f"Status: {response.status_code}")
    result = response.json()
    
    if response.status_code == 200 and result.get("success"):
        print("✓ Trajectory inference successful")
        print(f"  Result ID: {result.get('result_id')}")
        print(f"  Outputs: {list(result.get('outputs', {}).keys())}")
        print(f"  Pseudotime stats: {result.get('pseudotime_stats')}")
        
        # 测试下载
        if "h5ad" in result.get("outputs", {}):
            file_id = result["outputs"]["h5ad"]
            download_url = f"{BASE_URL}/api/download/{file_id}"
            print(f"\nTesting download: {download_url}")
            download_response = requests.get(download_url)
            if download_response.status_code == 200:
                print(f"✓ Download successful ({len(download_response.content)} bytes)")
            else:
                print(f"✗ Download failed: {download_response.status_code}")
        
        return True
    else:
        print("✗ Trajectory inference failed")
        print(f"  Error: {result.get('message', 'Unknown error')}")
        if "suggestions" in result:
            print("  Suggestions:")
            for suggestion in result["suggestions"]:
                if isinstance(suggestion, dict):
                    print(f"    - {suggestion.get('issue', 'Unknown issue')}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("SpaTrack Service Test")
    print("=" * 60)
    print()
    
    # 测试健康检查
    try:
        test_health()
    except Exception as e:
        print(f"✗ Health check failed: {e}\n")
        sys.exit(1)
    
    # 测试轨迹推断（需要提供测试文件路径）
    if len(sys.argv) > 1:
        test_file = sys.argv[1]
        try:
            success = test_spatrack_pseudotime(test_file)
            if not success:
                sys.exit(1)
        except Exception as e:
            print(f"✗ Test failed: {e}")
            sys.exit(1)
    else:
        print("Skipping trajectory inference test (no file provided)")
        print("Usage: python test_service.py <path_to_test_data.h5ad>")
    
    print("\n" + "=" * 60)
    print("All tests passed! ✓")
    print("=" * 60)

