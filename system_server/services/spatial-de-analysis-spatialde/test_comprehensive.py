#!/usr/bin/env python3
"""
SpatialDE 服务全面测试脚本
测试各种场景和边界情况
"""
import requests
import json
import sys
import time

BASE_URL = "http://localhost:42593"

def test_health():
    """测试健康检查接口"""
    print("=" * 60)
    print("测试 1: 健康检查接口")
    print("=" * 60)
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=10)
        assert response.status_code == 200, f"期望状态码 200，实际 {response.status_code}"
        data = response.json()
        assert data.get("status") == "healthy", f"期望状态 healthy，实际 {data.get('status')}"
        print("✓ 健康检查通过")
        return True
    except Exception as e:
        print(f"✗ 健康检查失败: {e}")
        return False

def test_analyze_basic(file_path: str):
    """测试基本分析功能"""
    print("\n" + "=" * 60)
    print("测试 2: 基本分析功能（默认参数）")
    print("=" * 60)
    try:
        with open(file_path, 'rb') as f:
            files = {'file': f}
            data = {
                'file_type': 'h5ad',
                'normalize': True,
                'use_highly_variable': True,
                'min_counts': 1,
                'min_cells': 10,
            }
            
            print(f"发送请求到 {BASE_URL}/api/analyze...")
            start_time = time.time()
            response = requests.post(f"{BASE_URL}/api/analyze", files=files, data=data, timeout=600)
            elapsed = time.time() - start_time
            
            assert response.status_code == 200, f"期望状态码 200，实际 {response.status_code}"
            result = response.json()
            assert result.get("success") == True, f"期望 success=True，实际 {result.get('success')}"
            assert "data" in result, "结果中缺少 'data' 字段"
            
            data_fields = result["data"]
            assert "spatial_de_results.csv" in data_fields, "缺少结果 CSV 文件"
            assert "spatial_de_data.h5ad" in data_fields, "缺少结果 H5AD 文件"
            assert "statistics.txt" in data_fields, "缺少统计文件"
            
            print(f"✓ 基本分析通过（耗时: {elapsed:.2f}秒）")
            print(f"  返回文件数: {len(data_fields)}")
            return True
    except Exception as e:
        print(f"✗ 基本分析失败: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"  响应内容: {e.response.text[:500]}")
        return False

def test_analyze_custom_params(file_path: str):
    """测试自定义参数"""
    print("\n" + "=" * 60)
    print("测试 3: 自定义参数（更严格的筛选）")
    print("=" * 60)
    try:
        with open(file_path, 'rb') as f:
            files = {'file': f}
            data = {
                'file_type': 'h5ad',
                'normalize': False,  # 不标准化
                'use_highly_variable': False,  # 不使用高变基因
                'min_counts': 5,  # 更严格的筛选
                'min_cells': 20,
            }
            
            print(f"发送请求（min_counts=5, min_cells=20）...")
            start_time = time.time()
            response = requests.post(f"{BASE_URL}/api/analyze", files=files, data=data, timeout=600)
            elapsed = time.time() - start_time
            
            assert response.status_code == 200, f"期望状态码 200，实际 {response.status_code}"
            result = response.json()
            assert result.get("success") == True, f"期望 success=True，实际 {result.get('success')}"
            
            print(f"✓ 自定义参数测试通过（耗时: {elapsed:.2f}秒）")
            return True
    except Exception as e:
        print(f"✗ 自定义参数测试失败: {e}")
        return False

def test_analyze_minimal_params(file_path: str):
    """测试最小参数（宽松筛选）"""
    print("\n" + "=" * 60)
    print("测试 4: 最小参数（宽松筛选）")
    print("=" * 60)
    try:
        with open(file_path, 'rb') as f:
            files = {'file': f}
            data = {
                'file_type': 'h5ad',
                'min_counts': 1,
                'min_cells': 1,  # 非常宽松
            }
            
            print(f"发送请求（min_counts=1, min_cells=1）...")
            start_time = time.time()
            response = requests.post(f"{BASE_URL}/api/analyze", files=files, data=data, timeout=600)
            elapsed = time.time() - start_time
            
            assert response.status_code == 200, f"期望状态码 200，实际 {response.status_code}"
            result = response.json()
            assert result.get("success") == True, f"期望 success=True，实际 {result.get('success')}"
            
            print(f"✓ 最小参数测试通过（耗时: {elapsed:.2f}秒）")
            return True
    except Exception as e:
        print(f"✗ 最小参数测试失败: {e}")
        return False

def test_error_handling():
    """测试错误处理"""
    print("\n" + "=" * 60)
    print("测试 5: 错误处理（无效文件）")
    print("=" * 60)
    try:
        # 测试无效文件
        files = {'file': ('invalid.txt', b'not a valid h5ad file', 'text/plain')}
        data = {'file_type': 'h5ad'}
        
        response = requests.post(f"{BASE_URL}/api/analyze", files=files, data=data, timeout=30)
        
        # 应该返回错误，但不应该崩溃
        assert response.status_code in [400, 422, 500], f"期望错误状态码，实际 {response.status_code}"
        result = response.json()
        assert result.get("success") == False, "期望 success=False"
        
        print(f"✓ 错误处理正常（返回状态码: {response.status_code}）")
        return True
    except Exception as e:
        print(f"✗ 错误处理测试失败: {e}")
        return False

def test_result_validation(file_path: str):
    """测试结果验证"""
    print("\n" + "=" * 60)
    print("测试 6: 结果验证（检查结果质量）")
    print("=" * 60)
    try:
        with open(file_path, 'rb') as f:
            files = {'file': f}
            data = {
                'file_type': 'h5ad',
                'min_counts': 1,
                'min_cells': 10,
            }
            
            response = requests.post(f"{BASE_URL}/api/analyze", files=files, data=data, timeout=600)
            assert response.status_code == 200
            result = response.json()
            assert result.get("success") == True
            
            # 验证返回的文件ID格式
            data_fields = result["data"]
            for key, file_id in data_fields.items():
                assert isinstance(file_id, str), f"{key} 的文件ID应该是字符串"
                assert len(file_id) > 0, f"{key} 的文件ID不应为空"
                # 检查是否是UUID格式（至少包含连字符）
                if '-' in file_id:
                    assert len(file_id.split('-')) == 5, f"{key} 的文件ID应该是UUID格式"
            
            print("✓ 结果格式验证通过")
            print(f"  返回的文件: {list(data_fields.keys())}")
            return True
    except Exception as e:
        print(f"✗ 结果验证失败: {e}")
        return False

def run_all_tests(file_path: str):
    """运行所有测试"""
    print("\n" + "=" * 80)
    print("开始全面测试 SpatialDE 服务")
    print("=" * 80)
    
    tests = [
        ("健康检查", lambda: test_health()),
        ("基本分析", lambda: test_analyze_basic(file_path)),
        ("自定义参数", lambda: test_analyze_custom_params(file_path)),
        ("最小参数", lambda: test_analyze_minimal_params(file_path)),
        ("错误处理", test_error_handling),
        ("结果验证", lambda: test_result_validation(file_path)),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n✗ 测试 '{name}' 发生异常: {e}")
            results.append((name, False))
    
    # 汇总结果
    print("\n" + "=" * 80)
    print("测试结果汇总")
    print("=" * 80)
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{status:8} - {name}")
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！")
        return 0
    else:
        print(f"\n⚠️  有 {total - passed} 个测试失败")
        return 1

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python test_comprehensive.py <path_to_h5ad_file>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    exit_code = run_all_tests(file_path)
    sys.exit(exit_code)

