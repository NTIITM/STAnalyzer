#!/usr/bin/env python3
"""
测试 scTenifoldpy Virtual Gene Knockout 服务
"""
import requests
import os
import time
import sys
import json

# 服务地址
BASE_URL = "http://localhost:44030"
HEALTH_ENDPOINT = f"{BASE_URL}/health"  # 使用实际运行的端点
VIRTUAL_KNOCKOUT_ENDPOINT = f"{BASE_URL}/api/virtual-knockout"
DOWNLOAD_ENDPOINT = f"{BASE_URL}/api/download"

# 测试数据路径 - 使用一个较小的测试文件
TEST_DATA_DIR = "/home/common/hwluo/project/Data/ST"
TEST_H5AD = os.path.join(TEST_DATA_DIR, "151507_normalized.h5ad")

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

def test_virtual_knockout():
    """测试虚拟敲除端点"""
    print("=" * 60)
    print("测试虚拟敲除端点...")
    
    if not os.path.exists(TEST_H5AD):
        print(f"⚠️  测试数据文件不存在: {TEST_H5AD}")
        print("请确保测试数据文件存在")
        return False
    
    try:
        # 准备表单数据 - 使用数据中存在的基因
        data = {
            "ko_genes": "ISG15",  # 使用测试数据中存在的基因
            "n_components": "20",
            "n_iter": "3",
            "knn": "5",
            "qc_min_lib_size": "10",
            "qc_min_percent": "0.001",
            "max_genes": "3000",
            "random_seed": "1",
        }
        
        # 准备文件
        with open(TEST_H5AD, "rb") as f:
            files = {
                "file": (os.path.basename(TEST_H5AD), f, "application/octet-stream")
            }
            
            print(f"发送请求到: {VIRTUAL_KNOCKOUT_ENDPOINT}")
            print(f"敲除基因: {data['ko_genes']}")
            print(f"文件: {TEST_H5AD}")
            
            start_time = time.time()
            response = requests.post(
                VIRTUAL_KNOCKOUT_ENDPOINT,
                data=data,
                files=files,
                timeout=600  # 10分钟超时，因为分析可能需要较长时间
            )
            elapsed_time = time.time() - start_time
            
            print(f"状态码: {response.status_code}")
            print(f"耗时: {elapsed_time:.2f} 秒")
            print(f"Content-Type: {response.headers.get('Content-Type', 'N/A')}")
            print(f"响应前500字符: {response.text[:500]}")
            
            if response.status_code == 200:
                try:
                    result = response.json()
                except Exception as e:
                    print(f"⚠️  响应不是有效的JSON: {e}")
                    print(f"完整响应: {response.text}")
                    return None
                print(f"响应: {json.dumps(result, indent=2, ensure_ascii=False)}")
                
                # 检查返回格式
                if result.get("success") and "data" in result:
                    file_ids = result["data"]
                    print(f"\n✅ 虚拟敲除分析成功!")
                    print(f"返回的文件ID:")
                    for filename, file_id in file_ids.items():
                        print(f"  {filename}: {file_id}")
                    return file_ids
                else:
                    print(f"⚠️  返回格式不正确: {result}")
                    return None
            else:
                print(f"❌ 请求失败")
                try:
                    error_info = response.json()
                    print(f"错误信息: {json.dumps(error_info, indent=2, ensure_ascii=False)}")
                except:
                    print(f"错误信息: {response.text[:500]}")
                return None
                
    except requests.exceptions.Timeout:
        print(f"❌ 请求超时（超过10分钟）")
        return None
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_download(file_ids):
    """测试下载端点"""
    print("=" * 60)
    print("测试下载端点...")
    
    if not file_ids:
        print("⚠️  没有可用的文件ID，跳过下载测试")
        return False
    
    success_count = 0
    for filename, file_id in file_ids.items():
        try:
            download_url = f"{DOWNLOAD_ENDPOINT}/{file_id}"
            print(f"\n下载文件: {filename} (ID: {file_id})")
            
            response = requests.get(download_url, timeout=30)
            print(f"状态码: {response.status_code}")
            
            if response.status_code == 200:
                # 检查Content-Type
                content_type = response.headers.get("Content-Type", "")
                print(f"Content-Type: {content_type}")
                
                # 保存文件到临时位置
                output_path = f"/tmp/test_download_{file_id}"
                with open(output_path, "wb") as f:
                    f.write(response.content)
                
                file_size = os.path.getsize(output_path)
                print(f"✅ 文件下载成功: {output_path} ({file_size} bytes)")
                success_count += 1
            else:
                print(f"❌ 下载失败")
                try:
                    error_info = response.json()
                    print(f"错误信息: {json.dumps(error_info, indent=2, ensure_ascii=False)}")
                except:
                    print(f"错误信息: {response.text[:500]}")
                    
        except Exception as e:
            print(f"❌ 下载测试失败: {e}")
            import traceback
            traceback.print_exc()
    
    return success_count == len(file_ids)

def main():
    """主测试函数"""
    print("=" * 60)
    print("scTenifoldpy Virtual Gene Knockout 服务测试")
    print("=" * 60)
    
    # 测试健康检查
    if not test_health():
        print("\n❌ 健康检查失败，服务可能未运行")
        print(f"请确保服务运行在 {BASE_URL}")
        sys.exit(1)
    
    # 测试虚拟敲除
    file_ids = test_virtual_knockout()
    
    # 测试下载
    if file_ids:
        test_download(file_ids)
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

if __name__ == "__main__":
    main()

