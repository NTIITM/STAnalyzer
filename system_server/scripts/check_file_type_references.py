#!/usr/bin/env python
"""
检查服务配置中引用的文件类型是否都在文件类型定义中存在，并生成引用关系报告

Usage:
    python scripts/check_file_type_references.py
    python scripts/check_file_type_references.py --verbose
    python scripts/check_file_type_references.py --output reference_report.json
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Any

# 确保项目根目录在路径中
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger("check_file_type_references")


def load_file_types() -> Dict[str, Dict[str, Any]]:
    """
    加载所有已定义的文件类型
    
    Returns:
        字典：{file_type_id: file_type_info}
    """
    file_types: Dict[str, Dict[str, Any]] = {}
    
    # 从 seed_file_types.py 读取
    seed_file = PROJECT_ROOT.parent / "textMSA" / "scripts" / "seed_file_types.py"
    if not seed_file.exists():
        logger.warning(f"文件类型定义文件不存在: {seed_file}")
        return file_types
    
    try:
        # 方法1：尝试直接导入模块（如果路径正确）
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("seed_file_types", seed_file)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                if hasattr(module, "DEFAULT_FILE_TYPES"):
                    for file_type in module.DEFAULT_FILE_TYPES:
                        file_type_id = file_type.get("file_type_id")
                        if file_type_id:
                            file_types[file_type_id] = file_type.copy()
                    logger.debug(f"通过导入模块从 {seed_file} 加载了 {len(file_types)} 个文件类型")
                    return file_types
        except Exception as e:
            logger.debug(f"导入模块方法失败: {e}，尝试解析文件内容")
        
        # 方法2：解析文件内容（使用AST或正则表达式）
        with open(seed_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 使用正则表达式提取 file_type_id 和相关信息
        # 匹配每个字典块
        dict_pattern = r'\{\s*"file_type_id":\s*"([^"]+)",\s*"name":\s*"([^"]+)",\s*"display_name":\s*"([^"]+)",\s*"description":\s*"([^"]+)",\s*"category":\s*"([^"]+)",\s*"extensions":\s*\[([^\]]+)\]\s*\}'
        matches = re.finditer(dict_pattern, content, re.MULTILINE | re.DOTALL)
        
        for match in matches:
            file_type_id = match.group(1)
            name = match.group(2)
            display_name = match.group(3)
            description = match.group(4)
            category = match.group(5)
            extensions_str = match.group(6)
            
            # 解析扩展名
            extensions = []
            for ext_match in re.finditer(r'"([^"]+)"', extensions_str):
                extensions.append(ext_match.group(1))
            
            file_types[file_type_id] = {
                "file_type_id": file_type_id,
                "name": name,
                "display_name": display_name,
                "description": description,
                "category": category,
                "extensions": extensions
            }
        
        if file_types:
            logger.debug(f"通过解析文件从 {seed_file} 加载了 {len(file_types)} 个文件类型")
        else:
            # 方法3：简单提取 file_type_id（备用方法）
            logger.debug("使用备用方法：仅提取 file_type_id")
            pattern = r'"file_type_id":\s*"([^"]+)"'
            matches = re.findall(pattern, content)
            for file_type_id in matches:
                if file_type_id not in file_types:
                    file_types[file_type_id] = {
                        "file_type_id": file_type_id,
                        "name": file_type_id,
                        "display_name": file_type_id,
                        "description": "",
                        "category": "unknown",
                        "extensions": []
                    }
            logger.debug(f"通过备用方法从 {seed_file} 加载了 {len(file_types)} 个文件类型")
            
    except Exception as e:
        logger.error(f"加载文件类型定义失败: {e}")
        import traceback
        logger.debug(traceback.format_exc())
    
    return file_types


def collect_file_type_references(services_dir: Path) -> Dict[str, List[str]]:
    """
    收集所有服务配置中的文件类型引用
    
    Returns:
        字典：{file_type_id: [service_id1, service_id2, ...]}
    """
    references: Dict[str, List[str]] = defaultdict(list)
    
    for service_dir in sorted(services_dir.iterdir()):
        if not service_dir.is_dir():
            continue
        
        config_path = service_dir / "service_config.json"
        if not config_path.exists():
            continue
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            service_id = config.get("service_id") or config.get("name", service_dir.name)
            
            # 收集 accepted_files 中的引用（使用 file_type_ids 数组）
            if "accepted_files" in config:
                accepted_files = config["accepted_files"]
                if isinstance(accepted_files, dict):
                    for filename, file_type_config in accepted_files.items():
                        if isinstance(file_type_config, dict):
                            file_type_ids = file_type_config.get("file_type_ids", [])
                            if isinstance(file_type_ids, list):
                                for file_type_id in file_type_ids:
                                    if isinstance(file_type_id, str) and file_type_id:
                                        if service_id not in references[file_type_id]:
                                            references[file_type_id].append(service_id)
            
            # 收集 output_config.items 中的引用（使用 file_type_id 字符串）
            if "output_config" in config:
                output_config = config["output_config"]
                if isinstance(output_config, dict):
                    items = output_config.get("items", [])
                    if isinstance(items, list):
                        for item in items:
                            if isinstance(item, dict):
                                file_type_id = item.get("file_type_id")
                                if isinstance(file_type_id, str) and file_type_id:
                                    if service_id not in references[file_type_id]:
                                        references[file_type_id].append(service_id)
                                
                                # 兼容旧的 file_type_ids 格式
                                file_type_ids = item.get("file_type_ids", [])
                                if isinstance(file_type_ids, list):
                                    for ft_id in file_type_ids:
                                        if isinstance(ft_id, str) and ft_id:
                                            if service_id not in references[ft_id]:
                                                references[ft_id].append(service_id)
        except Exception as e:
            logger.warning(f"处理 {config_path} 失败: {e}")
    
    return dict(references)


def collect_service_file_types(services_dir: Path) -> Dict[str, Dict[str, List[str]]]:
    """
    收集每个服务使用的文件类型（区分输入和输出）
    
    Returns:
        字典：{service_id: {"input": [file_type_id1, ...], "output": [file_type_id2, ...]}}
    """
    service_file_types: Dict[str, Dict[str, List[str]]] = defaultdict(lambda: {"input": [], "output": []})
    
    for service_dir in sorted(services_dir.iterdir()):
        if not service_dir.is_dir():
            continue
        
        config_path = service_dir / "service_config.json"
        if not config_path.exists():
            continue
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            service_id = config.get("service_id") or config.get("name", service_dir.name)
            
            # 收集输入文件类型（accepted_files）
            if "accepted_files" in config:
                accepted_files = config["accepted_files"]
                if isinstance(accepted_files, dict):
                    for filename, file_type_config in accepted_files.items():
                        if isinstance(file_type_config, dict):
                            file_type_ids = file_type_config.get("file_type_ids", [])
                            if isinstance(file_type_ids, list):
                                for file_type_id in file_type_ids:
                                    if isinstance(file_type_id, str) and file_type_id:
                                        if file_type_id not in service_file_types[service_id]["input"]:
                                            service_file_types[service_id]["input"].append(file_type_id)
            
            # 收集输出文件类型（output_config.items）
            if "output_config" in config:
                output_config = config["output_config"]
                if isinstance(output_config, dict):
                    items = output_config.get("items", [])
                    if isinstance(items, list):
                        for item in items:
                            if isinstance(item, dict):
                                file_type_id = item.get("file_type_id")
                                if isinstance(file_type_id, str) and file_type_id:
                                    if file_type_id not in service_file_types[service_id]["output"]:
                                        service_file_types[service_id]["output"].append(file_type_id)
                                
                                # 兼容旧的 file_type_ids 格式
                                file_type_ids = item.get("file_type_ids", [])
                                if isinstance(file_type_ids, list):
                                    for ft_id in file_type_ids:
                                        if isinstance(ft_id, str) and ft_id:
                                            if ft_id not in service_file_types[service_id]["output"]:
                                                service_file_types[service_id]["output"].append(ft_id)
        except Exception as e:
            logger.warning(f"处理 {config_path} 失败: {e}")
    
    return dict(service_file_types)


def analyze_references(
    defined_types: Set[str],
    referenced_types: Set[str],
    file_types_info: Dict[str, Dict[str, Any]],
    references: Dict[str, List[str]]
) -> Dict[str, Any]:
    """
    分析文件类型引用关系
    
    Returns:
        分析结果字典
    """
    unused_types = defined_types - referenced_types
    missing_types = referenced_types - defined_types
    
    # 统计每个文件类型的使用次数
    usage_stats = {}
    for file_type_id in defined_types:
        usage_stats[file_type_id] = {
            "used": file_type_id in referenced_types,
            "reference_count": len(references.get(file_type_id, [])),
            "services": references.get(file_type_id, []),
            "info": file_types_info.get(file_type_id, {})
        }
    
    return {
        "defined_count": len(defined_types),
        "referenced_count": len(referenced_types),
        "unused_types": sorted(unused_types),
        "missing_types": sorted(missing_types),
        "used_count": len(defined_types & referenced_types),
        "usage_stats": usage_stats
    }


def print_report(
    analysis: Dict[str, Any],
    service_file_types: Dict[str, Dict[str, List[str]]],
    file_types_info: Dict[str, Dict[str, Any]],
    verbose: bool = False
) -> None:
    """
    打印引用关系报告
    """
    print("=" * 80)
    print("文件类型引用检查报告")
    print("=" * 80)
    print()
    
    # 总体统计
    print("## 总体统计")
    print(f"已定义的文件类型数量: {analysis['defined_count']}")
    print(f"被引用的文件类型数量: {analysis['referenced_count']}")
    print(f"实际使用的文件类型数量: {analysis['used_count']}")
    print(f"未使用的文件类型数量: {len(analysis['unused_types'])}")
    print(f"缺失的文件类型数量: {len(analysis['missing_types'])}")
    print()
    
    # 缺失的文件类型
    if analysis['missing_types']:
        print("## ⚠️  缺失的文件类型（被引用但未定义）")
        for file_type_id in analysis['missing_types']:
            services = [s for s, ft in service_file_types.items() 
                       if file_type_id in ft.get("input", []) or file_type_id in ft.get("output", [])]
            print(f"  - {file_type_id}")
            if services:
                print(f"    被以下服务引用: {', '.join(services)}")
        print()
    else:
        print("## ✅ 所有引用的文件类型都已定义")
        print()
    
    # 未使用的文件类型
    if analysis['unused_types']:
        print("## 📋 未使用的文件类型（已定义但未被引用）")
        for file_type_id in sorted(analysis['unused_types']):
            info = file_types_info.get(file_type_id, {})
            display_name = info.get("display_name", file_type_id)
            category = info.get("category", "unknown")
            print(f"  - {file_type_id} ({display_name})")
            if verbose:
                description = info.get("description", "")
                if description:
                    print(f"    描述: {description}")
                print(f"    分类: {category}")
        print()
    else:
        print("## ✅ 所有定义的文件类型都被使用")
        print()
    
    # 文件类型使用统计
    if verbose:
        print("## 📊 文件类型使用统计")
        # 按使用次数排序
        usage_stats = analysis['usage_stats']
        sorted_stats = sorted(
            usage_stats.items(),
            key=lambda x: (x[1]['reference_count'], x[0]),
            reverse=True
        )
        
        for file_type_id, stats in sorted_stats:
            info = stats['info']
            display_name = info.get("display_name", file_type_id)
            reference_count = stats['reference_count']
            services = stats['services']
            
            status = "✅" if stats['used'] else "❌"
            print(f"{status} {file_type_id} ({display_name})")
            print(f"    被 {reference_count} 个服务引用")
            if services:
                print(f"    服务列表: {', '.join(sorted(services))}")
        print()
    
    # 服务-文件类型映射
    if verbose:
        print("## 🔗 服务-文件类型映射关系")
        for service_id in sorted(service_file_types.keys()):
            ft = service_file_types[service_id]
            print(f"\n### {service_id}")
            if ft.get("input"):
                print(f"  输入文件类型: {', '.join(sorted(ft['input']))}")
            if ft.get("output"):
                print(f"  输出文件类型: {', '.join(sorted(ft['output']))}")
        print()
    
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description="检查服务配置中引用的文件类型是否都在文件类型定义中存在"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="显示详细信息"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="输出JSON报告文件路径"
    )
    parser.add_argument(
        "--services-dir",
        type=str,
        default=None,
        help="服务配置目录路径（默认: system_server/services）"
    )
    args = parser.parse_args()
    
    # 配置日志
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format="[%(levelname)s] %(message)s")
    
    # 确定服务目录
    if args.services_dir:
        services_dir = Path(args.services_dir)
    else:
        services_dir = PROJECT_ROOT / "services"
    
    if not services_dir.exists():
        logger.error(f"服务目录不存在: {services_dir}")
        sys.exit(1)
    
    logger.info("加载文件类型定义...")
    file_types_info = load_file_types()
    defined_types = set(file_types_info.keys())
    logger.info(f"已加载 {len(defined_types)} 个文件类型定义")
    
    logger.info("扫描服务配置文件...")
    references = collect_file_type_references(services_dir)
    referenced_types = set(references.keys())
    logger.info(f"发现 {len(referenced_types)} 个被引用的文件类型")
    
    logger.info("收集服务-文件类型映射...")
    service_file_types = collect_service_file_types(services_dir)
    logger.info(f"已处理 {len(service_file_types)} 个服务")
    
    logger.info("分析引用关系...")
    analysis = analyze_references(
        defined_types,
        referenced_types,
        file_types_info,
        references
    )
    
    # 打印报告
    print_report(analysis, service_file_types, file_types_info, args.verbose)
    
    # 生成JSON报告
    if args.output:
        report = {
            "summary": {
                "defined_count": analysis["defined_count"],
                "referenced_count": analysis["referenced_count"],
                "used_count": analysis["used_count"],
                "unused_count": len(analysis["unused_types"]),
                "missing_count": len(analysis["missing_types"])
            },
            "unused_types": analysis["unused_types"],
            "missing_types": analysis["missing_types"],
            "usage_stats": analysis["usage_stats"],
            "service_file_types": service_file_types,
            "references": references
        }
        
        output_path = Path(args.output)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        logger.info(f"JSON报告已保存到: {output_path}")
    
    # 如果有缺失的文件类型，返回非零退出码
    if analysis["missing_types"]:
        logger.error("发现缺失的文件类型，请检查并修复！")
        sys.exit(1)
    
    logger.info("检查完成！")


if __name__ == "__main__":
    main()

