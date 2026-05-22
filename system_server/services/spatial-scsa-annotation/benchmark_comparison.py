#!/usr/bin/env python3
"""
性能比较脚本：比较 SCSA 和 Marker-Gene 两种标注方法的性能
使用 service-fixer 工作流程进行测试和评估
"""
import requests
import json
import time
import os
import sys
from pathlib import Path
import pandas as pd
import anndata as ad
import numpy as np
from datetime import datetime
import subprocess

# ===== CONFIGURATION =====
SCSA_SERVICE_NAME = "spatial-scsa-annotation"
SCSA_BASE_URL = "http://localhost:50008"
SCSA_HEALTH_ENDPOINT = f"{SCSA_BASE_URL}/health"
SCSA_PROCESSING_ENDPOINT = f"{SCSA_BASE_URL}/api/annotate"

MARKER_SERVICE_NAME = "spatial-marker-gene-annotation"
MARKER_BASE_URL = "http://localhost:50007"
MARKER_HEALTH_ENDPOINT = f"{MARKER_BASE_URL}/health"
MARKER_PROCESSING_ENDPOINT = f"{MARKER_BASE_URL}/api/annotate"

# Test data path
TEST_DATA_PATH = "/home/common/hwluo/project/Data/ST/151507_hvg.h5ad"
CLUSTER_KEY = "layer"  # 使用 layer 列作为 cluster

# Output directory
OUTPUT_DIR = "./benchmark_results"
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

# ===== HELPER FUNCTIONS =====

def check_service_health(service_name: str, endpoint: str):
    """检查服务健康状态"""
    try:
        response = requests.get(endpoint, timeout=10)
        response.raise_for_status()
        return True, response.json()
    except Exception as e:
        return False, str(e)


def run_annotation(service_name: str, base_url: str, endpoint: str, test_data_path: str, 
                   cluster_key: str, params: dict):
    """运行标注任务并记录性能指标"""
    print(f"\n{'=' * 80}")
    print(f"运行 {service_name} 标注")
    print(f"{'=' * 80}")
    
    if not os.path.exists(test_data_path):
        print(f"✗ 测试数据不存在: {test_data_path}")
        return None
    
    # 准备参数
    data = params.copy()
    data['cluster_key'] = cluster_key
    
    metrics = {
        'service_name': service_name,
        'cluster_key': cluster_key,
        'parameters': data.copy(),
        'start_time': time.time(),
        'end_time': None,
        'duration': None,
        'success': False,
        'job_id': None,
        'error': None,
        'output_files': {},
        'data_stats': {}
    }
    
    try:
        # 上传文件并开始处理
        print(f"上传文件: {test_data_path}")
        print(f"参数: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        with open(test_data_path, 'rb') as f:
            files = {'file': (os.path.basename(test_data_path), f, 'application/octet-stream')}
            
            start_time = time.time()
            response = requests.post(endpoint, files=files, data=data, timeout=1800)  # 30分钟超时
            end_time = time.time()
            
            response.raise_for_status()
            result = response.json()
            
            metrics['end_time'] = end_time
            metrics['duration'] = end_time - start_time
            
            if result.get('success'):
                metrics['success'] = True
                # SCSA 服务返回 job_id，Marker-Gene 服务返回 data 字典（包含文件路径）
                metrics['job_id'] = result.get('job_id')
                metrics['output_files'] = result.get('output_files', result.get('data', {}))
                
                # Marker-Gene 服务：从 data 中提取文件路径
                if not metrics['job_id'] and 'data' in result:
                    data_dict = result.get('data', {})
                    if 'annotated_data.h5ad' in data_dict:
                        file_path = data_dict['annotated_data.h5ad']
                        # 保存完整路径以便后续使用
                        metrics['annotated_data_path'] = file_path
                        # 尝试从路径提取 job_id
                        import re
                        match = re.search(r'/([^/]+)/annotated_data\.h5ad', file_path)
                        if match:
                            metrics['job_id'] = match.group(1)
                        else:
                            metrics['job_id'] = f"marker_{int(time.time())}"
                
                print(f"✓ 标注完成")
                print(f"  任务ID: {metrics.get('job_id', 'N/A')}")
                print(f"  耗时: {metrics['duration']:.2f} 秒 ({metrics['duration']/60:.2f} 分钟)")
                output_files_list = list(metrics['output_files'].keys()) if isinstance(metrics['output_files'], dict) else []
                print(f"  输出文件: {output_files_list}")
            else:
                metrics['error'] = result.get('message', 'Unknown error')
                print(f"✗ 标注失败: {metrics['error']}")
                
    except requests.exceptions.Timeout:
        metrics['error'] = "Request timeout (exceeded 30 minutes)"
        print(f"✗ 请求超时")
    except Exception as e:
        metrics['error'] = str(e)
        print(f"✗ 标注失败: {e}")
        import traceback
        traceback.print_exc()
    
    return metrics


def download_and_analyze(service_name: str, base_url: str, job_id: str, 
                         output_dir: str, cluster_key: str, output_files: dict = None):
    """下载结果文件并分析数据质量"""
    print(f"\n下载和分析 {service_name} 结果...")
    
    analysis = {
        'service_name': service_name,
        'job_id': job_id,
        'files_downloaded': [],
        'data_loaded': False,
        'stats': {}
    }
    
    h5ad_path = None
    
    try:
        # Marker-Gene 服务返回的是文件名（UUID），需要从服务输出目录获取
        if service_name == 'spatial-marker-gene-annotation' and output_files:
            if 'annotated_data.h5ad' in output_files:
                file_name = output_files['annotated_data.h5ad']  # 这是文件名，不是路径
                
                # 获取服务的输出目录
                try:
                    health_response = requests.get(f"{base_url}/health", timeout=10)
                    health_data = health_response.json()
                    service_output_dir = health_data.get('output_dir', '/app/outputs')
                except:
                    service_output_dir = '/app/outputs'
                
                # 尝试在服务输出目录中查找文件
                possible_paths = [
                    os.path.join(service_output_dir, file_name),
                    os.path.join('/app/outputs', file_name),
                    os.path.join('/tmp', file_name),
                ]
                
                file_path = None
                for path in possible_paths:
                    if os.path.exists(path):
                        file_path = path
                        break
                
                if file_path and os.path.exists(file_path):
                    h5ad_path = os.path.join(output_dir, f"{service_name}_annotated_data.h5ad")
                    os.makedirs(output_dir, exist_ok=True)
                    import shutil
                    shutil.copy2(file_path, h5ad_path)
                    analysis['files_downloaded'].append('annotated_data.h5ad')
                    print(f"  ✓ 已复制: annotated_data.h5ad (从 {file_path})")
                else:
                    print(f"  ⚠ 无法找到文件: {file_name}，尝试下载方式...")
                    # 继续尝试下载方式
        
        # 如果还没有获取到文件，尝试下载
        if not h5ad_path:
            h5ad_path = os.path.join(output_dir, f"{service_name}_annotated_data.h5ad")
            
            # SCSA 服务使用 /api/download/{job_id}/{filename}
            # Marker-Gene 服务使用 /api/download/{file_id}（file_id 就是文件名）
            if service_name == 'spatial-scsa-annotation' and job_id:
                download_url = f"{base_url}/api/download/{job_id}/annotated_data.h5ad"
            elif service_name == 'spatial-marker-gene-annotation' and output_files and 'annotated_data.h5ad' in output_files:
                # Marker-Gene 服务返回的是文件名（UUID），直接使用
                file_id = output_files['annotated_data.h5ad']
                download_url = f"{base_url}/api/download/{file_id}"
            else:
                download_url = None
            
            if download_url:
                try:
                    response = requests.get(download_url, timeout=300)
                    response.raise_for_status()
                    
                    os.makedirs(output_dir, exist_ok=True)
                    with open(h5ad_path, 'wb') as f:
                        f.write(response.content)
                    
                    analysis['files_downloaded'].append('annotated_data.h5ad')
                    print(f"  ✓ 已下载: annotated_data.h5ad")
                except requests.exceptions.HTTPError as e:
                    if e.response.status_code == 404:
                        print(f"  ⚠ 文件不存在: {download_url}")
                    else:
                        raise
                except Exception as e:
                    print(f"  ✗ 下载失败: {e}")
        
        if not h5ad_path or not os.path.exists(h5ad_path):
            print(f"  ✗ 无法获取 annotated_data.h5ad")
            return analysis
        
        # 加载并分析数据
        adata = ad.read_h5ad(h5ad_path)
        analysis['data_loaded'] = True
        
        # 基本统计
        analysis['stats'] = {
            'n_spots': adata.n_obs,
            'n_genes': adata.n_vars,
            'n_clusters': len(adata.obs[cluster_key].unique()) if cluster_key in adata.obs else 0,
        }
        
        # 细胞类型统计
        if 'cell_type' in adata.obs.columns:
            cell_types = adata.obs['cell_type']
            analysis['stats']['cell_types'] = {
                'unique_count': len(cell_types.unique()),
                'distribution': cell_types.value_counts().to_dict(),
                'unknown_count': (cell_types == 'Unknown').sum() if 'Unknown' in cell_types.values else 0,
                'unknown_percentage': ((cell_types == 'Unknown').sum() / len(cell_types) * 100) 
                                      if 'Unknown' in cell_types.values else 0
            }
        
        # 置信度/评分统计
        if 'cell_type_confidence' in adata.obs.columns:
            conf = adata.obs['cell_type_confidence']
            analysis['stats']['confidence'] = {
                'mean': float(conf.mean()),
                'median': float(conf.median()),
                'std': float(conf.std()),
                'min': float(conf.min()),
                'max': float(conf.max())
            }
        elif 'scsa_z_score' in adata.obs.columns:
            zscore = adata.obs['scsa_z_score']
            analysis['stats']['z_score'] = {
                'mean': float(zscore.mean()),
                'median': float(zscore.median()),
                'std': float(zscore.std()),
                'min': float(zscore.min()),
                'max': float(zscore.max())
            }
        
        # 下载统计文件
        stats_files = {
            'scsa': 'scsa_annotation_statistics.csv',
            'marker': 'cluster_annotation_statistics.csv'
        }
        
        for key, filename in stats_files.items():
            if service_name == 'spatial-scsa-annotation' and key == 'scsa':
                stats_url = f"{base_url}/api/download/{job_id}/{filename}"
                try:
                    response = requests.get(stats_url, timeout=60)
                    response.raise_for_status()
                    stats_path = os.path.join(output_dir, f"{service_name}_{filename}")
                    with open(stats_path, 'wb') as f:
                        f.write(response.content)
                    analysis['files_downloaded'].append(filename)
                    print(f"  ✓ 已下载: {filename}")
                except:
                    pass
            elif service_name == 'spatial-marker-gene-annotation' and key == 'marker':
                stats_url = f"{base_url}/api/download/{job_id}/{filename}"
                try:
                    response = requests.get(stats_url, timeout=60)
                    response.raise_for_status()
                    stats_path = os.path.join(output_dir, f"{service_name}_{filename}")
                    with open(stats_path, 'wb') as f:
                        f.write(response.content)
                    analysis['files_downloaded'].append(filename)
                    print(f"  ✓ 已下载: {filename}")
                except:
                    pass
        
    except Exception as e:
        print(f"  ✗ 下载或分析失败: {e}")
        import traceback
        traceback.print_exc()
    
    return analysis


def compare_results(scsa_analysis: dict, marker_analysis: dict, output_dir: str):
    """比较两种方法的结果"""
    print(f"\n{'=' * 80}")
    print("性能比较分析")
    print(f"{'=' * 80}")
    
    comparison = {
        'timestamp': TIMESTAMP,
        'test_data': TEST_DATA_PATH,
        'cluster_key': CLUSTER_KEY,
        'scsa': scsa_analysis,
        'marker': marker_analysis,
        'comparison': {}
    }
    
    # 1. 性能比较（处理时间）
    if scsa_analysis.get('duration') and marker_analysis.get('duration'):
        scsa_time = scsa_analysis['duration']
        marker_time = marker_analysis['duration']
        speedup = marker_time / scsa_time if scsa_time > 0 else 0
        
        comparison['comparison']['performance'] = {
            'scsa_duration_seconds': scsa_time,
            'scsa_duration_minutes': scsa_time / 60,
            'marker_duration_seconds': marker_time,
            'marker_duration_minutes': marker_time / 60,
            'speedup': speedup,
            'faster_method': 'SCSA' if scsa_time < marker_time else 'Marker-Gene'
        }
        
        print("\n1. 处理时间比较:")
        print(f"   SCSA:        {scsa_time:.2f} 秒 ({scsa_time/60:.2f} 分钟)")
        print(f"   Marker-Gene: {marker_time:.2f} 秒 ({marker_time/60:.2f} 分钟)")
        print(f"   更快的方法: {comparison['comparison']['performance']['faster_method']}")
        if speedup > 1:
            print(f"   加速比: {speedup:.2f}x")
    
    # 2. 数据质量比较
    scsa_stats = scsa_analysis.get('stats', {})
    marker_stats = marker_analysis.get('stats', {})
    
    if scsa_stats.get('cell_types') and marker_stats.get('cell_types'):
        scsa_ct = scsa_stats['cell_types']
        marker_ct = marker_stats['cell_types']
        
        comparison['comparison']['quality'] = {
            'scsa_cell_types': {
                'unique_count': scsa_ct.get('unique_count', 0),
                'unknown_percentage': scsa_ct.get('unknown_percentage', 0),
                'distribution': scsa_ct.get('distribution', {})
            },
            'marker_cell_types': {
                'unique_count': marker_ct.get('unique_count', 0),
                'unknown_percentage': marker_ct.get('unknown_percentage', 0),
                'distribution': marker_ct.get('distribution', {})
            }
        }
        
        print("\n2. 标注质量比较:")
        print(f"   SCSA 识别的细胞类型数: {scsa_ct.get('unique_count', 0)}")
        print(f"   Marker-Gene 识别的细胞类型数: {marker_ct.get('unique_count', 0)}")
        print(f"   SCSA Unknown 比例: {scsa_ct.get('unknown_percentage', 0):.2f}%")
        print(f"   Marker-Gene Unknown 比例: {marker_ct.get('unknown_percentage', 0):.2f}%")
    
    # 3. 评分比较
    if 'confidence' in marker_stats:
        comparison['comparison']['scoring'] = {
            'marker_confidence': marker_stats['confidence']
        }
        print("\n3. Marker-Gene 置信度统计:")
        conf = marker_stats['confidence']
        print(f"   平均置信度: {conf.get('mean', 0):.3f}")
        print(f"   中位数: {conf.get('median', 0):.3f}")
        print(f"   标准差: {conf.get('std', 0):.3f}")
    
    if 'z_score' in scsa_stats:
        if 'scoring' not in comparison['comparison']:
            comparison['comparison']['scoring'] = {}
        comparison['comparison']['scoring']['scsa_z_score'] = scsa_stats['z_score']
        print("\n4. SCSA Z-score 统计:")
        zscore = scsa_stats['z_score']
        print(f"   平均 Z-score: {zscore.get('mean', 0):.3f}")
        print(f"   中位数: {zscore.get('median', 0):.3f}")
        print(f"   标准差: {zscore.get('std', 0):.3f}")
    
    # 保存比较结果
    comparison_json = os.path.join(output_dir, f"benchmark_comparison_{TIMESTAMP}.json")
    with open(comparison_json, 'w', encoding='utf-8') as f:
        json.dump(comparison, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"\n比较结果已保存到: {comparison_json}")
    
    # 生成文本报告
    report_path = os.path.join(output_dir, f"benchmark_report_{TIMESTAMP}.txt")
    generate_text_report(comparison, report_path)
    
    return comparison


def generate_text_report(comparison: dict, report_path: str):
    """生成文本格式的性能报告"""
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("空间转录组细胞类型标注方法性能比较报告\n")
        f.write("=" * 80 + "\n\n")
        
        f.write(f"测试时间: {comparison['timestamp']}\n")
        f.write(f"测试数据: {comparison['test_data']}\n")
        f.write(f"Cluster 列: {comparison['cluster_key']}\n\n")
        
        # 性能部分
        if 'performance' in comparison['comparison']:
            perf = comparison['comparison']['performance']
            f.write("=" * 80 + "\n")
            f.write("1. 处理性能\n")
            f.write("=" * 80 + "\n")
            f.write(f"SCSA 方法:\n")
            f.write(f"  处理时间: {perf['scsa_duration_seconds']:.2f} 秒 ({perf['scsa_duration_minutes']:.2f} 分钟)\n")
            f.write(f"\nMarker-Gene 方法:\n")
            f.write(f"  处理时间: {perf['marker_duration_seconds']:.2f} 秒 ({perf['marker_duration_minutes']:.2f} 分钟)\n")
            f.write(f"\n更快的方法: {perf['faster_method']}\n")
            if perf.get('speedup', 0) > 1:
                f.write(f"加速比: {perf['speedup']:.2f}x\n")
            f.write("\n")
        
        # 质量部分
        if 'quality' in comparison['comparison']:
            qual = comparison['comparison']['quality']
            f.write("=" * 80 + "\n")
            f.write("2. 标注质量\n")
            f.write("=" * 80 + "\n")
            
            scsa_qual = qual['scsa_cell_types']
            marker_qual = qual['marker_cell_types']
            
            f.write(f"SCSA 方法:\n")
            f.write(f"  识别的细胞类型数: {scsa_qual['unique_count']}\n")
            f.write(f"  Unknown 比例: {scsa_qual['unknown_percentage']:.2f}%\n")
            f.write(f"  细胞类型分布:\n")
            for ct, count in sorted(scsa_qual['distribution'].items(), key=lambda x: x[1], reverse=True):
                f.write(f"    {ct}: {count}\n")
            
            f.write(f"\nMarker-Gene 方法:\n")
            f.write(f"  识别的细胞类型数: {marker_qual['unique_count']}\n")
            f.write(f"  Unknown 比例: {marker_qual['unknown_percentage']:.2f}%\n")
            f.write(f"  细胞类型分布:\n")
            for ct, count in sorted(marker_qual['distribution'].items(), key=lambda x: x[1], reverse=True):
                f.write(f"    {ct}: {count}\n")
            f.write("\n")
        
        # 评分部分
        if 'scoring' in comparison['comparison']:
            scoring = comparison['comparison']['scoring']
            f.write("=" * 80 + "\n")
            f.write("3. 评分统计\n")
            f.write("=" * 80 + "\n")
            
            if 'scsa_z_score' in scoring:
                zscore = scoring['scsa_z_score']
                f.write("SCSA Z-score:\n")
                f.write(f"  平均: {zscore.get('mean', 0):.3f}\n")
                f.write(f"  中位数: {zscore.get('median', 0):.3f}\n")
                f.write(f"  标准差: {zscore.get('std', 0):.3f}\n")
                f.write(f"  范围: [{zscore.get('min', 0):.3f}, {zscore.get('max', 0):.3f}]\n\n")
            
            if 'marker_confidence' in scoring:
                conf = scoring['marker_confidence']
                f.write("Marker-Gene 置信度:\n")
                f.write(f"  平均: {conf.get('mean', 0):.3f}\n")
                f.write(f"  中位数: {conf.get('median', 0):.3f}\n")
                f.write(f"  标准差: {conf.get('std', 0):.3f}\n")
                f.write(f"  范围: [{conf.get('min', 0):.3f}, {conf.get('max', 0):.3f}]\n\n")
        
        f.write("=" * 80 + "\n")
        f.write("报告结束\n")
        f.write("=" * 80 + "\n")
    
    print(f"文本报告已保存到: {report_path}")


def main():
    """主函数：执行完整的性能比较流程"""
    print("=" * 80)
    print("空间转录组细胞类型标注方法性能比较")
    print("=" * 80)
    
    # 检查测试数据
    if not os.path.exists(TEST_DATA_PATH):
        print(f"✗ 测试数据不存在: {TEST_DATA_PATH}")
        return
    
    # 检查数据中的 cluster 列
    try:
        adata = ad.read_h5ad(TEST_DATA_PATH)
        if CLUSTER_KEY not in adata.obs.columns:
            print(f"✗ 数据中不存在 '{CLUSTER_KEY}' 列")
            print(f"  可用的 obs 列: {list(adata.obs.columns)}")
            return
        print(f"✓ 测试数据检查通过")
        print(f"  数据维度: {adata.n_obs} spots × {adata.n_vars} genes")
        print(f"  Cluster 列 '{CLUSTER_KEY}': {len(adata.obs[CLUSTER_KEY].unique())} 个 cluster")
    except Exception as e:
        print(f"✗ 无法读取测试数据: {e}")
        return
    
    # 检查服务健康状态
    print("\n" + "=" * 80)
    print("检查服务状态")
    print("=" * 80)
    
    scsa_healthy, scsa_health_data = check_service_health(SCSA_SERVICE_NAME, SCSA_HEALTH_ENDPOINT)
    marker_healthy, marker_health_data = check_service_health(MARKER_SERVICE_NAME, MARKER_HEALTH_ENDPOINT)
    
    if scsa_healthy:
        print(f"✓ {SCSA_SERVICE_NAME} 服务正常")
    else:
        print(f"✗ {SCSA_SERVICE_NAME} 服务不可用: {scsa_health_data}")
        print("  请先启动服务: cd system_server/services/spatial-scsa-annotation && python main.py")
        return
    
    if marker_healthy:
        print(f"✓ {MARKER_SERVICE_NAME} 服务正常")
    else:
        print(f"✗ {MARKER_SERVICE_NAME} 服务不可用: {marker_health_data}")
        print("  请先启动服务")
        return
    
    # 创建输出目录
    output_dir = os.path.join(OUTPUT_DIR, TIMESTAMP)
    os.makedirs(output_dir, exist_ok=True)
    print(f"\n输出目录: {os.path.abspath(output_dir)}")
    
    # 运行 SCSA 标注
    scsa_params = {
        'foldchange': 1.5,
        'pvalue': 0.01,
        'celltype': 'normal',
        'target': 'cellmarker',
        'tissue': 'All',
        'rank_rep': True
    }
    
    scsa_metrics = run_annotation(
        SCSA_SERVICE_NAME, SCSA_BASE_URL, SCSA_PROCESSING_ENDPOINT,
        TEST_DATA_PATH, CLUSTER_KEY, scsa_params
    )
    
    # 运行 Marker-Gene 标注
    marker_params = {
        'confidence_threshold': 0.10,
        'apply_smoothing': True,
        'smoothing_radius': 3
    }
    
    marker_metrics = run_annotation(
        MARKER_SERVICE_NAME, MARKER_BASE_URL, MARKER_PROCESSING_ENDPOINT,
        TEST_DATA_PATH, CLUSTER_KEY, marker_params
    )
    
    # 下载和分析结果
    scsa_analysis = download_and_analyze(
        SCSA_SERVICE_NAME, SCSA_BASE_URL, 
        scsa_metrics.get('job_id') if scsa_metrics else None,
        output_dir, CLUSTER_KEY,
        output_files=scsa_metrics.get('output_files') if scsa_metrics else None
    )
    scsa_analysis.update(scsa_metrics or {})
    
    marker_analysis = download_and_analyze(
        MARKER_SERVICE_NAME, MARKER_BASE_URL,
        marker_metrics.get('job_id') if marker_metrics else None,
        output_dir, CLUSTER_KEY,
        output_files=marker_metrics.get('output_files') if marker_metrics else None
    )
    marker_analysis.update(marker_metrics or {})
    
    # 比较结果
    comparison = compare_results(scsa_analysis, marker_analysis, output_dir)
    
    print("\n" + "=" * 80)
    print("性能比较完成！")
    print("=" * 80)
    print(f"结果保存在: {os.path.abspath(output_dir)}")


if __name__ == "__main__":
    main()

