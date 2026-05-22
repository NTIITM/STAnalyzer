"""
服务扫描器
用于扫描和发现服务项目，收集服务配置信息
"""
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from system_server.config_parser import ServiceConfigParser

logger = logging.getLogger(__name__)

# 配置文件查找顺序
CONFIG_FALLBACK_FILES = (
    "server_config.json",
    "service_config.json",
)
CONFIG_GLOB_PATTERNS = (
    "*_service.json",
    "*service_config.json",
    "*server_config.json",
)


def find_config_file(
    service_dir: Path,
    explicit_name: Optional[str] = None,
) -> Optional[Path]:
    """
    查找服务的配置文件
    
    Args:
        service_dir: 服务目录路径
        explicit_name: 显式指定的配置文件名
        
    Returns:
        配置文件路径，如果未找到则返回 None
    """
    candidates: List[Path] = []

    if explicit_name:
        candidates.append(service_dir / explicit_name)
    else:
        for name in CONFIG_FALLBACK_FILES:
            candidates.append(service_dir / name)

    for candidate in candidates:
        if candidate.is_file():
            return candidate

    # Fallback: look for pattern like *_service.json
    for pattern in CONFIG_GLOB_PATTERNS:
        matches = sorted(service_dir.glob(pattern))
        for match in matches:
            if match.is_file():
                return match

    return None


def discover_services(services_base_dir: Path) -> List[Path]:
    """
    发现服务项目
    
    Args:
        services_base_dir: 服务基础目录
        
    Returns:
        服务项目路径列表
    """
    services = []
    
    if not services_base_dir.exists():
        logger.warning(f"服务基础目录不存在: {services_base_dir}")
        return services
    
    # 查找所有包含 main.py 的目录
    for item in services_base_dir.iterdir():
        if not item.is_dir():
            continue
        
        # 跳过 __pycache__ 等隐藏目录
        if item.name.startswith('__') or item.name.startswith('.'):
            continue
        
        # 检查是否包含 main.py（标识为服务项目）
        main_py = item / "main.py"
        if main_py.exists():
            services.append(item)
            logger.info(f"发现服务项目: {item.name}")
    
    return services


def extract_port_from_baseurl(baseurl: str) -> Optional[int]:
    """
    从 baseurl 中提取端口号
    
    Args:
        baseurl: 基础URL字符串
        
    Returns:
        端口号，如果未找到则返回 None
    """
    parts = baseurl.split(":")
    if len(parts) >= 3:
        try:
            return int(parts[2].split("/")[0])
        except (ValueError, IndexError):
            return None
    return None


def build_service_entry(
    service_dir: Path,
    config_path: Optional[Path],
    config_data: Dict[str, Any],
    parser_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    构建服务条目
    
    Args:
        service_dir: 服务目录路径
        config_path: 配置文件路径
        config_data: 配置文件原始数据
        parser_data: 解析器解析的数据
        
    Returns:
        服务条目字典
    """
    entry: Dict[str, Any] = {}
    entry.update(parser_data or {})
    entry.update(config_data or {})

    entry.setdefault("name", service_dir.name)
    entry.setdefault("service_dir", service_dir.name)
    entry.setdefault("service_path", str(service_dir))

    if config_path:
        entry["config_path"] = str(config_path)

    if "port" not in entry and "baseurl" in entry:
        port = extract_port_from_baseurl(entry["baseurl"])
        if port:
            entry["port"] = port

    return entry


def collect_service_configs(
    base_dir: Path,
    config_name: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    收集所有服务的配置
    
    Args:
        base_dir: 服务基础目录
        config_name: 显式指定的配置文件名
        
    Returns:
        服务配置列表
    """
    services: List[Dict[str, Any]] = []

    if not base_dir.exists():
        logger.error("服务目录不存在: %s", base_dir)
        return services

    for sub_dir in sorted(base_dir.iterdir()):
        if (
            not sub_dir.is_dir()
            or sub_dir.name.startswith(".")
            or sub_dir.name.startswith("__")
        ):
            continue

        parser_data: Dict[str, Any] = {}
        try:
            parser = ServiceConfigParser(sub_dir)
            parser_data = parser.parse()
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.warning("解析服务目录 %s 失败: %s", sub_dir, exc)
            parser_data = {
                "service_dir": sub_dir.name,
                "service_path": str(sub_dir),
            }

        config_path = find_config_file(sub_dir, config_name)
        raw_config: Dict[str, Any] = {}
        config_error: Optional[str] = None

        if config_path:
            try:
                with open(config_path, "r", encoding="utf-8") as fp:
                    payload = json.load(fp)
                    if isinstance(payload, dict):
                        raw_config = payload
                    else:
                        config_error = "配置文件不是 JSON 对象"
            except Exception as exc:  # pylint: disable=broad-exception-caught
                config_error = str(exc)
                logger.warning("读取配置失败 %s: %s", config_path, exc)

        service_entry = build_service_entry(sub_dir, config_path, raw_config, parser_data)
        if config_error:
            service_entry["error"] = config_error
        services.append(service_entry)

    return services


def build_summary(services: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    构建服务汇总信息
    
    Args:
        services: 服务配置列表
        
    Returns:
        汇总信息字典
    """
    summary: Dict[str, Any] = {
        "total_services": len(services),
        "ports": [],
        "services_by_port": {},
        "services_by_status": {},
    }

    for service in services:
        port = service.get("port")
        if port is not None:
            summary["ports"].append(port)
            summary["services_by_port"].setdefault(port, []).append(
                {
                    "name": service.get("name", service.get("service_dir", "")),
                    "path": service.get("service_path", ""),
                }
            )

        status = service.get("status", "unknown")
        summary["services_by_status"].setdefault(status, []).append(
            service.get("name", service.get("service_dir", ""))
        )

    summary["ports"] = sorted(set(summary["ports"]))
    return summary

