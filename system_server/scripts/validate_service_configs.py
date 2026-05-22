#!/usr/bin/env python
"""
验证服务配置文件格式和文件类型引用

Usage:
    python scripts/validate_service_configs.py
    python scripts/validate_service_configs.py --service <service_id>
    python scripts/validate_service_configs.py --output report.json
    python scripts/validate_service_configs.py --strict  # 严格模式，不允许警告
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Any

# 确保项目根目录在路径中
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger("validate_service_configs")


def load_file_types() -> Set[str]:
    """
    加载所有已定义的文件类型ID
    
    Returns:
        文件类型ID集合
    """
    file_types: Set[str] = set()
    
    # 从 seed_file_types.py 读取
    seed_file = PROJECT_ROOT.parent / "textMSA" / "scripts" / "seed_file_types.py"
    if not seed_file.exists():
        logger.warning(f"文件类型定义文件不存在: {seed_file}")
        return file_types
    
    try:
        # 读取文件内容
        with open(seed_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 使用正则表达式提取 file_type_id
        pattern = r'"file_type_id":\s*"([^"]+)"'
        matches = re.findall(pattern, content)
        file_types.update(matches)
        
        logger.debug(f"从 {seed_file} 加载了 {len(file_types)} 个文件类型")
    except Exception as e:
        logger.error(f"加载文件类型定义失败: {e}")
    
    return file_types


def validate_service_config(
    config_path: Path,
    file_types: Set[str],
    strict: bool = False
) -> Dict[str, Any]:
    """
    验证单个服务配置文件
    
    Args:
        config_path: 配置文件路径
        file_types: 已定义的文件类型ID集合
        strict: 是否严格模式（警告视为错误）
    
    Returns:
        验证结果字典，包含：
        - valid: 是否有效
        - errors: 错误列表
        - warnings: 警告列表
        - service_id: 服务ID
    """
    result = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "service_id": None,
        "config_path": str(config_path)
    }
    
    # 1. 检查文件是否存在
    if not config_path.exists():
        result["valid"] = False
        result["errors"].append(f"配置文件不存在: {config_path}")
        return result
    
    # 2. 验证JSON格式
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        result["valid"] = False
        result["errors"].append(f"JSON格式错误: {e}")
        return result
    except Exception as e:
        result["valid"] = False
        result["errors"].append(f"读取配置文件失败: {e}")
        return result
    
    # 3. 提取服务ID
    result["service_id"] = config.get("service_id") or config.get("name", "unknown")
    
    # 4. 验证必需字段
    if "service_id" not in config and "name" not in config:
        result["warnings"].append("缺少 service_id 或 name 字段")
        if strict:
            result["valid"] = False
            result["errors"].append("严格模式：缺少 service_id 或 name 字段")
    
    # 5. 验证 accepted_files（新字段，可选但推荐）
    if "accepted_files" in config:
        accepted_files = config["accepted_files"]
        
        # 验证 accepted_files 结构
        if not isinstance(accepted_files, dict):
            result["valid"] = False
            result["errors"].append("accepted_files 必须是字典（对象）")
        else:
            # 验证每个 accepted_file（key为文件名，value为配置）
            for filename, file_type_config in accepted_files.items():
                if not isinstance(file_type_config, dict):
                    result["valid"] = False
                    result["errors"].append(
                        f"accepted_files['{filename}'] 必须是对象"
                    )
                    continue
                
                # 验证 file_type_ids（数组格式，单个类型使用单元素数组）
                if "file_type_ids" not in file_type_config:
                    result["valid"] = False
                    result["errors"].append(
                        f"accepted_files['{filename}'] 缺少 file_type_ids 字段"
                    )
                else:
                    file_type_ids = file_type_config["file_type_ids"]
                    if not isinstance(file_type_ids, list):
                        result["valid"] = False
                        result["errors"].append(
                            f"accepted_files['{filename}'].file_type_ids 必须是数组"
                        )
                    elif len(file_type_ids) == 0:
                        result["valid"] = False
                        result["errors"].append(
                            f"accepted_files['{filename}'].file_type_ids 不能为空数组"
                        )
                    else:
                        for file_type_id in file_type_ids:
                            if not isinstance(file_type_id, str):
                                result["valid"] = False
                                result["errors"].append(
                                    f"accepted_files['{filename}'].file_type_ids 中的元素必须是字符串"
                                )
                            elif file_type_id not in file_types:
                                result["valid"] = False
                                result["errors"].append(
                                    f"accepted_files['{filename}']: "
                                    f"未定义的文件类型 '{file_type_id}'"
                                )
                
                # 验证 description 字段（推荐）
                if "description" not in file_type_config:
                    result["warnings"].append(
                        f"accepted_files['{filename}'] 缺少 description 字段"
                    )
    else:
        result["warnings"].append("缺少 accepted_files 字段（新配置要求）")
    
    # 6. 验证 output_config
    if "output_config" not in config:
        result["warnings"].append("缺少 output_config 字段")
    else:
        output_config = config["output_config"]
        if not isinstance(output_config, dict):
            result["valid"] = False
            result["errors"].append("output_config 必须是对象")
        else:
            # 验证 items
            if "items" not in output_config:
                result["warnings"].append("output_config 缺少 items 字段")
            else:
                items = output_config["items"]
                if not isinstance(items, list):
                    result["valid"] = False
                    result["errors"].append("output_config.items 必须是数组")
                else:
                    # 验证每个输出项
                    for idx, item in enumerate(items):
                        if not isinstance(item, dict):
                            result["valid"] = False
                            result["errors"].append(
                                f"output_config.items[{idx}] 必须是对象"
                            )
                            continue
                        
                        # 验证 file_type_id（字符串格式，单个类型）
                        if "file_type_id" not in item:
                            # 检查是否有旧的 file_type_ids 字段
                            if "file_type_ids" in item:
                                result["valid"] = False
                                result["errors"].append(
                                    f"output_config.items[{idx}] 使用了旧的 file_type_ids 字段（数组），"
                                    f"应改为 file_type_id 字段（字符串）"
                                )
                            else:
                                result["valid"] = False
                                result["errors"].append(
                                    f"output_config.items[{idx}] 缺少 file_type_id 字段"
                                )
                        else:
                            file_type_id = item["file_type_id"]
                            if not isinstance(file_type_id, str):
                                result["valid"] = False
                                result["errors"].append(
                                    f"output_config.items[{idx}].file_type_id 必须是字符串"
                                )
                            elif file_type_id not in file_types:
                                result["valid"] = False
                                result["errors"].append(
                                    f"output_config.items[{idx}]: "
                                    f"未定义的文件类型 '{file_type_id}'"
                                )
                            
                            # 如果同时存在 file_type_ids，报告错误
                            if "file_type_ids" in item:
                                result["valid"] = False
                                result["errors"].append(
                                    f"output_config.items[{idx}] 同时存在 file_type_id 和 file_type_ids，"
                                    f"应只使用 file_type_id"
                                )
    
    # 在严格模式下，警告视为错误
    if strict and result["warnings"]:
        result["valid"] = False
        result["errors"].extend(result["warnings"])
        result["warnings"] = []
    
    return result


def validate_all_services(
    services_dir: Path,
    file_types: Set[str],
    service_filter: Optional[str] = None,
    strict: bool = False
) -> List[Dict[str, Any]]:
    """
    批量验证所有服务配置
    
    Args:
        services_dir: 服务目录
        file_types: 已定义的文件类型ID集合
        service_filter: 可选的服务ID过滤（只验证指定服务）
        strict: 是否严格模式
    
    Returns:
        验证结果列表
    """
    results = []
    
    if not services_dir.exists():
        logger.error(f"服务目录不存在: {services_dir}")
        return results
    
    # 扫描所有服务目录
    for service_dir in sorted(services_dir.iterdir()):
        if not service_dir.is_dir():
            continue
        
        # 如果指定了服务过滤，只验证匹配的服务
        if service_filter and service_dir.name != service_filter:
            continue
        
        config_path = service_dir / "service_config.json"
        if not config_path.exists():
            logger.debug(f"跳过 {service_dir.name}：配置文件不存在")
            continue
        
        logger.info(f"验证服务: {service_dir.name}")
        result = validate_service_config(config_path, file_types, strict)
        results.append(result)
    
    return results


def generate_report(results: List[Dict[str, Any]], output_file: Optional[Path] = None) -> None:
    """
    生成验证报告
    
    Args:
        results: 验证结果列表
        output_file: 可选的输出文件路径（JSON格式）
    """
    total = len(results)
    valid = sum(1 for r in results if r["valid"])
    invalid = total - valid
    
    # 控制台输出
    print("=" * 80)
    print("服务配置验证报告")
    print("=" * 80)
    print(f"总计: {total} 个服务")
    print(f"有效: {valid} 个")
    print(f"无效: {invalid} 个")
    print()
    
    # 详细结果
    for result in results:
        service_id = result["service_id"]
        status = "✓" if result["valid"] else "✗"
        print(f"{status} {service_id}")
        
        if result["errors"]:
            for error in result["errors"]:
                print(f"  错误: {error}")
        
        if result["warnings"]:
            for warning in result["warnings"]:
                print(f"  警告: {warning}")
        
        if result["errors"] or result["warnings"]:
            print()
    
    # JSON输出
    if output_file:
        report = {
            "summary": {
                "total": total,
                "valid": valid,
                "invalid": invalid
            },
            "results": results
        }
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n报告已保存到: {output_file}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="验证服务配置文件格式和文件类型引用"
    )
    parser.add_argument(
        "--service",
        type=str,
        help="只验证指定服务（服务ID）"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="输出JSON报告文件路径"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="严格模式：警告视为错误"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="启用详细日志"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    
    # 配置日志
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format="[%(levelname)s] %(message)s")
    
    # 加载文件类型
    logger.info("加载文件类型定义...")
    file_types = load_file_types()
    logger.info(f"已加载 {len(file_types)} 个文件类型")
    
    # 验证服务配置
    services_dir = PROJECT_ROOT / "services"
    logger.info(f"扫描服务目录: {services_dir}")
    
    results = validate_all_services(
        services_dir,
        file_types,
        service_filter=args.service,
        strict=args.strict
    )
    
    # 生成报告
    output_file = Path(args.output) if args.output else None
    generate_report(results, output_file)
    
    # 退出码
    invalid_count = sum(1 for r in results if not r["valid"])
    sys.exit(0 if invalid_count == 0 else 1)


if __name__ == "__main__":
    main()

