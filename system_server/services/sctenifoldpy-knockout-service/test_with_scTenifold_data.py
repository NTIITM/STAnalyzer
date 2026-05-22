#!/usr/bin/env python3
"""
使用 scTenifold 内置测试数据进行测试
"""
import os
import sys
import tempfile
import requests
import time
import json
import anndata as ad
import pandas as pd
import numpy as np

try:
    from scTenifold.data import get_test_df
    from scTenifold import scTenifoldKnk
    HAS_SCTENIFOLD = True
except ImportError as e:
    print(f"❌ 无法导入 scTenifold: {e}")
    print("请确保已安装 scTenifold 库")
    sys.exit(1)

# 服务地址
# 如果在容器内运行，使用容器内端口 8080；否则使用宿主机端口 40337
import os
if os.path.exists("/.dockerenv"):
    BASE_URL = "http://localhost:8080"  # 容器内端口
else:
    BASE_URL = "http://localhost:40337"  # 宿主机端口
HEALTH_ENDPOINT = f"{BASE_URL}/health"
VIRTUAL_KNOCKOUT_ENDPOINT = f"{BASE_URL}/api/virtual-knockout"
DOWNLOAD_ENDPOINT = f"{BASE_URL}/api/download"


def create_h5ad_from_test_data():
    """从 scTenifold 测试数据创建 h5ad 文件"""
    print("=" * 60)
    print("获取 scTenifold 测试数据...")
    
    try:
        # 获取测试数据
        df = get_test_df()
        print(f"✅ 成功获取测试数据")
        print(f"   数据形状: {df.shape} (基因 x 细胞)")
        print(f"   基因数: {df.shape[0]}")
        print(f"   细胞数: {df.shape[1]}")
        print(f"   前5个基因: {list(df.index[:5])}")
        
        # 创建 AnnData 对象
        # scTenifold 返回的是 genes x cells 的 DataFrame
        # AnnData 需要 cells x genes，所以需要转置
        adata = ad.AnnData(X=df.T.values)  # 转置为 cells x genes
        adata.var_names = df.index  # 基因名
        adata.obs_names = df.columns  # 细胞名
        
        # 保存为临时 h5ad 文件
        temp_fd, temp_path = tempfile.mkstemp(suffix=".h5ad", prefix="sctenifold_test_")
        os.close(temp_fd)
        
        adata.write(temp_path)
        print(f"✅ 已创建临时 h5ad 文件: {temp_path}")
        
        return temp_path, df
        
    except Exception as e:
        print(f"❌ 创建测试数据失败: {e}")
        import traceback
        traceback.print_exc()
        return None, None


def test_direct_scTenifoldKnk(df):
    """直接测试 scTenifoldKnk（不通过服务）"""
    print("\n" + "=" * 60)
    print("直接测试 scTenifoldKnk...")
    
    try:
        # 选择存在于数据中的基因进行敲除
        available_genes = list(df.index)
        # 尝试使用示例中的基因名，如果不存在则使用数据中的前两个基因
        if "NG-568" in available_genes and "NG-1" in available_genes:
            ko_genes = ["NG-568", "NG-1"]
        else:
            ko_genes = available_genes[:2] if len(available_genes) >= 2 else [available_genes[0]]
        print(f"敲除基因: {ko_genes}")
        
        # 运行 scTenifoldKnk（使用用户提供的简化调用方式）
        print("运行 scTenifoldKnk...")
        start_time = time.time()
        
        sc = scTenifoldKnk(
            data=df,
            ko_method="default",
            ko_genes=ko_genes,
            qc_kws={"min_lib_size": 10, "min_percent": 0.001},
        )
        result = sc.build()
        
        elapsed_time = time.time() - start_time
        print(f"✅ scTenifoldKnk 运行成功 (耗时: {elapsed_time:.2f} 秒)")
        
        # 处理结果
        if isinstance(result, pd.DataFrame):
            result_df = result
        elif isinstance(result, dict):
            result_df = None
            for key, val in result.items():
                if isinstance(val, pd.DataFrame):
                    result_df = val
                    print(f"   使用结果字典中的键: {key}")
                    break
            if result_df is None:
                print(f"⚠️  结果字典中没有找到 DataFrame")
                print(f"   结果键: {list(result.keys())}")
                return False
        else:
            print(f"⚠️  结果类型未知: {type(result)}")
            return False
        
        print(f"   结果形状: {result_df.shape}")
        print(f"   结果列: {list(result_df.columns)}")
        print(f"   前5行:")
        print(result_df.head())
        
        return True
        
    except Exception as e:
        print(f"❌ 直接测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_service_with_test_data(h5ad_path, df):
    """使用测试数据通过服务 API 进行测试"""
    print("\n" + "=" * 60)
    print("通过服务 API 测试...")
    
    # 检查服务是否运行
    try:
        response = requests.get(HEALTH_ENDPOINT, timeout=5)
        if response.status_code != 200:
            print(f"⚠️  服务健康检查失败 (状态码: {response.status_code})")
            return False
        print("✅ 服务运行正常")
    except Exception as e:
        print(f"❌ 无法连接到服务: {e}")
        print(f"   请确保服务运行在 {BASE_URL}")
        return False
    
    # 选择一个存在于数据中的基因
    available_genes = list(df.index)
    ko_gene = available_genes[0] if available_genes else "GENE1"
    print(f"敲除基因: {ko_gene}")
    
    try:
        # 准备表单数据
        data = {
            "ko_genes": ko_gene,
            "n_components": "20",
            "n_iter": "3",
            "knn": "5",
            "qc_min_lib_size": "10",
            "qc_min_percent": "0.001",
            "max_genes": "3000",
            "random_seed": "1",
        }
        
        # 准备文件
        with open(h5ad_path, "rb") as f:
            files = {
                "file": (os.path.basename(h5ad_path), f, "application/octet-stream")
            }
            
            print(f"发送请求到: {VIRTUAL_KNOCKOUT_ENDPOINT}")
            
            start_time = time.time()
            response = requests.post(
                VIRTUAL_KNOCKOUT_ENDPOINT,
                data=data,
                files=files,
                timeout=600  # 10分钟超时
            )
            elapsed_time = time.time() - start_time
            
            print(f"状态码: {response.status_code}")
            print(f"耗时: {elapsed_time:.2f} 秒")
            
            if response.status_code == 200:
                try:
                    result = response.json()
                    print(f"响应: {json.dumps(result, indent=2, ensure_ascii=False)}")
                    
                    if result.get("success") and "data" in result:
                        file_ids = result["data"]
                        print(f"\n✅ 虚拟敲除分析成功!")
                        print(f"返回的文件ID:")
                        for filename, file_id in file_ids.items():
                            print(f"  {filename}: {file_id}")
                        
                        # 测试下载
                        print("\n测试文件下载...")
                        for filename, file_id in file_ids.items():
                            download_url = f"{DOWNLOAD_ENDPOINT}/{file_id}"
                            try:
                                dl_response = requests.get(download_url, timeout=30)
                                if dl_response.status_code == 200:
                                    file_size = len(dl_response.content)
                                    print(f"  ✅ {filename}: {file_size} bytes")
                                else:
                                    print(f"  ❌ {filename}: 下载失败 (状态码: {dl_response.status_code})")
                            except Exception as e:
                                print(f"  ❌ {filename}: 下载失败 - {e}")
                        
                        return True
                    else:
                        print(f"⚠️  返回格式不正确: {result}")
                        return False
                except Exception as e:
                    print(f"⚠️  响应解析失败: {e}")
                    print(f"响应内容: {response.text[:500]}")
                    return False
            else:
                print(f"❌ 请求失败")
                try:
                    error_info = response.json()
                    print(f"错误信息: {json.dumps(error_info, indent=2, ensure_ascii=False)}")
                except:
                    print(f"错误信息: {response.text[:500]}")
                return False
                
    except requests.exceptions.Timeout:
        print(f"❌ 请求超时（超过10分钟）")
        return False
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("=" * 60)
    print("使用 scTenifold 测试数据测试")
    print("=" * 60)
    
    # 创建测试数据
    h5ad_path, df = create_h5ad_from_test_data()
    if h5ad_path is None or df is None:
        print("\n❌ 无法创建测试数据")
        sys.exit(1)
    
    try:
        # 测试1: 直接使用 scTenifoldKnk
        direct_success = test_direct_scTenifoldKnk(df)
        
        # 测试2: 通过服务 API 测试
        service_success = test_service_with_test_data(h5ad_path, df)
        
        # 总结
        print("\n" + "=" * 60)
        print("测试总结")
        print("=" * 60)
        print(f"直接 scTenifoldKnk 测试: {'✅ 通过' if direct_success else '❌ 失败'}")
        print(f"服务 API 测试: {'✅ 通过' if service_success else '❌ 失败'}")
        
    finally:
        # 清理临时文件
        if h5ad_path and os.path.exists(h5ad_path):
            try:
                os.remove(h5ad_path)
                print(f"\n已清理临时文件: {h5ad_path}")
            except:
                pass


if __name__ == "__main__":
    main()

