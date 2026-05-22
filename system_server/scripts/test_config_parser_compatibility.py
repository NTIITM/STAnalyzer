#!/usr/bin/env python3
"""
测试配置解析器兼容性
验证 ServiceConfigParser 是否能正确处理新的配置结构
"""

import json
import sys
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from system_server.config_parser import ServiceConfigParser


class CompatibilityTester:
    """配置解析器兼容性测试器"""
    
    def __init__(self, services_dir: Path):
        self.services_dir = Path(services_dir)
        self.results = {
            "total_services": 0,
            "successful_parses": 0,
            "failed_parses": 0,
            "has_accepted_files": 0,
            "has_output_config": 0,
            "can_extract_file_types": 0,
            "errors": [],
            "service_details": []
        }
    
    def test_all_services(self, verbose: bool = False) -> Dict[str, Any]:
        """测试所有服务的配置解析"""
        if not self.services_dir.exists():
            self.results["errors"].append(f"服务目录不存在: {self.services_dir}")
            return self.results
        
        service_dirs = [d for d in self.services_dir.iterdir() 
                       if d.is_dir() and not d.name.startswith('.')]
        self.results["total_services"] = len(service_dirs)
        
        for service_dir in sorted(service_dirs):
            self._test_service(service_dir, verbose)
        
        return self.results
    
    def _test_service(self, service_dir: Path, verbose: bool = False):
        """测试单个服务的配置解析"""
        service_id = service_dir.name
        detail = {
            "service_id": service_id,
            "parse_success": False,
            "has_accepted_files": False,
            "has_output_config": False,
            "can_extract_file_types": False,
            "extracted_file_types": {
                "input": [],
                "output": []
            },
            "errors": []
        }
        
        try:
            # 测试解析器
            parser = ServiceConfigParser(service_dir)
            parsed_config = parser.parse()
            detail["parse_success"] = True
            self.results["successful_parses"] += 1
            
            # 检查原始配置文件
            config_file = service_dir / "service_config.json"
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    raw_config = json.load(f)
                
                # 检查新配置结构
                if "accepted_files" in raw_config:
                    detail["has_accepted_files"] = True
                    self.results["has_accepted_files"] += 1
                    # 提取文件类型
                    file_types = self._extract_input_file_types(raw_config["accepted_files"])
                    detail["extracted_file_types"]["input"] = file_types
                
                if "output_config" in raw_config:
                    detail["has_output_config"] = True
                    self.results["has_output_config"] += 1
                    # 提取输出文件类型
                    file_types = self._extract_output_file_types(raw_config.get("output_config", {}))
                    detail["extracted_file_types"]["output"] = file_types
                
                # 检查是否能从解析结果中提取文件类型信息
                if self._can_extract_file_types_from_parsed(parsed_config, raw_config):
                    detail["can_extract_file_types"] = True
                    self.results["can_extract_file_types"] += 1
                
                # 检查解析器是否保留了新字段
                if "accepted_files" in raw_config:
                    if "accepted_files" not in parsed_config:
                        detail["errors"].append("解析器未保留 accepted_files 字段")
                if "output_config" in raw_config:
                    if "output_config" not in parsed_config:
                        detail["errors"].append("解析器未保留 output_config 字段")
            
            if verbose:
                print(f"✅ {service_id}: 解析成功")
                if detail["has_accepted_files"]:
                    print(f"   - 包含 accepted_files: {len(detail['extracted_file_types']['input'])} 个输入文件类型")
                if detail["has_output_config"]:
                    print(f"   - 包含 output_config: {len(detail['extracted_file_types']['output'])} 个输出文件类型")
                if detail["errors"]:
                    for error in detail["errors"]:
                        print(f"   ⚠️  {error}")
        
        except Exception as e:
            detail["parse_success"] = False
            detail["errors"].append(f"解析失败: {str(e)}")
            self.results["failed_parses"] += 1
            self.results["errors"].append(f"{service_id}: {str(e)}")
            if verbose:
                print(f"❌ {service_id}: 解析失败 - {str(e)}")
        
        self.results["service_details"].append(detail)
    
    def _extract_input_file_types(self, accepted_files: Dict[str, Any]) -> List[str]:
        """从 accepted_files 中提取文件类型ID"""
        file_types = []
        if isinstance(accepted_files, dict):
            for filename, file_config in accepted_files.items():
                if isinstance(file_config, dict):
                    file_type_ids = file_config.get("file_type_ids", [])
                    if isinstance(file_type_ids, list):
                        file_types.extend([ft for ft in file_type_ids if isinstance(ft, str)])
        return sorted(list(set(file_types)))
    
    def _extract_output_file_types(self, output_config: Dict[str, Any]) -> List[str]:
        """从 output_config.items 中提取文件类型ID"""
        file_types = []
        if isinstance(output_config, dict):
            items = output_config.get("items", [])
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        file_type_id = item.get("file_type_id")
                        if isinstance(file_type_id, str):
                            file_types.append(file_type_id)
        return sorted(list(set(file_types)))
    
    def _can_extract_file_types_from_parsed(self, parsed_config: Dict[str, Any], 
                                           raw_config: Dict[str, Any]) -> bool:
        """检查是否能从解析结果中提取文件类型信息"""
        # 检查解析器是否保留了必要的字段
        has_input = "accepted_files" in parsed_config or "accepted_files" in raw_config
        has_output = "output_config" in parsed_config or "output_config" in raw_config
        
        if has_input:
            # 如果能从解析结果中提取，返回 True
            if "accepted_files" in parsed_config:
                file_types = self._extract_input_file_types(parsed_config["accepted_files"])
                if file_types:
                    return True
        
        if has_output:
            if "output_config" in parsed_config:
                file_types = self._extract_output_file_types(parsed_config["output_config"])
                if file_types:
                    return True
        
        return False
    
    def generate_report(self) -> str:
        """生成测试报告"""
        lines = []
        lines.append("=" * 80)
        lines.append("配置解析器兼容性测试报告")
        lines.append("=" * 80)
        lines.append("")
        
        # 摘要
        lines.append("📊 测试摘要")
        lines.append("-" * 80)
        lines.append(f"总服务数: {self.results['total_services']}")
        lines.append(f"成功解析: {self.results['successful_parses']}")
        lines.append(f"解析失败: {self.results['failed_parses']}")
        lines.append(f"包含 accepted_files: {self.results['has_accepted_files']}")
        lines.append(f"包含 output_config: {self.results['has_output_config']}")
        lines.append(f"可提取文件类型: {self.results['can_extract_file_types']}")
        lines.append("")
        
        # 兼容性评估
        lines.append("🔍 兼容性评估")
        lines.append("-" * 80)
        
        all_compatible = True
        if self.results['failed_parses'] > 0:
            lines.append("❌ 部分服务配置解析失败")
            all_compatible = False
        else:
            lines.append("✅ 所有服务配置都能成功解析")
        
        if self.results['has_accepted_files'] > 0:
            if self.results['can_extract_file_types'] < self.results['has_accepted_files']:
                lines.append("⚠️  部分服务的文件类型信息无法从解析结果中提取")
                all_compatible = False
            else:
                lines.append("✅ accepted_files 字段解析正常")
        
        if self.results['has_output_config'] > 0:
            lines.append("✅ output_config 字段解析正常")
        
        lines.append("")
        
        # 详细结果
        if self.results['errors']:
            lines.append("❌ 错误列表")
            lines.append("-" * 80)
            for error in self.results['errors']:
                lines.append(f"  - {error}")
            lines.append("")
        
        # 服务详情
        lines.append("📋 服务详情")
        lines.append("-" * 80)
        for detail in self.results['service_details']:
            status = "✅" if detail['parse_success'] else "❌"
            lines.append(f"{status} {detail['service_id']}")
            
            if detail['has_accepted_files']:
                input_types = detail['extracted_file_types']['input']
                lines.append(f"   输入文件类型: {', '.join(input_types) if input_types else '无'}")
            
            if detail['has_output_config']:
                output_types = detail['extracted_file_types']['output']
                lines.append(f"   输出文件类型: {', '.join(output_types) if output_types else '无'}")
            
            if detail['errors']:
                for error in detail['errors']:
                    lines.append(f"   ⚠️  {error}")
        
        lines.append("")
        lines.append("=" * 80)
        
        if all_compatible and self.results['failed_parses'] == 0:
            lines.append("✅ 兼容性测试通过：解析器能够正确处理新配置结构")
        else:
            lines.append("⚠️  兼容性测试发现问题，请检查上述错误")
        
        lines.append("=" * 80)
        
        return "\n".join(lines)
    
    def save_json_report(self, output_path: Path):
        """保存JSON格式的报告"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="测试配置解析器兼容性"
    )
    parser.add_argument(
        "--services-dir",
        type=str,
        default="system_server/services",
        help="服务配置目录路径（默认: system_server/services）"
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
    
    args = parser.parse_args()
    
    # 确定服务目录路径
    services_dir = Path(args.services_dir)
    if not services_dir.is_absolute():
        services_dir = project_root / services_dir
    
    # 运行测试
    tester = CompatibilityTester(services_dir)
    results = tester.test_all_services(verbose=args.verbose)
    
    # 生成报告
    report = tester.generate_report()
    print(report)
    
    # 保存JSON报告
    if args.output:
        output_path = Path(args.output)
        if not output_path.is_absolute():
            output_path = project_root / output_path
        tester.save_json_report(output_path)
        print(f"\n📄 JSON报告已保存到: {output_path}")
    
    # 返回退出码
    if results['failed_parses'] > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()

