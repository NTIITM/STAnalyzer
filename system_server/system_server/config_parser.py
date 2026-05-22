"""
服务配置解析器
用于解析服务项目的配置文件，提取端口号、服务名称等信息
"""
import json
import re
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class ServiceConfigParser:
    """服务配置解析器"""
    
    def __init__(self, service_path: Path):
        """
        初始化配置解析器
        
        Args:
            service_path: 服务项目根目录路径
        """
        self.service_path = Path(service_path)
        if not self.service_path.exists():
            raise ValueError(f"服务路径不存在: {service_path}")
    
    def parse(self) -> Dict[str, Any]:
        """
        解析服务配置
        
        Returns:
            包含服务配置信息的字典，包括：
            - name: 服务名称
            - port: 服务端口号
            - baseurl: 服务基础URL
            - description: 服务描述
            - version: 服务版本
            - service_suffix: API服务后缀
            - download_suffix: 下载服务后缀
            - status: 服务状态
            - accepted_files: 接受的输入文件配置（必需）
            - output_config: 输出文件配置（必需）
            - parameter_template: 参数模板（可选）
            - parameter_schema: 参数模式（可选）
            
        Raises:
            ValueError: 如果配置缺少必需字段或格式不正确
        """
        config = {}
        
        # 1. 尝试从 service_config.json 读取配置
        config_json_path = self.service_path / "service_config.json"
        if config_json_path.exists():
            try:
                with open(config_json_path, 'r', encoding='utf-8') as f:
                    json_config = json.load(f)
                    config.update(self._parse_json_config(json_config))
            except ValueError as e:
                # ValueError 是配置格式错误，应该抛出
                logger.error(f"解析 service_config.json 失败: {e}")
                raise
            except Exception as e:
                # 其他错误（如文件读取错误）记录警告但不阻止解析
                logger.warning(f"解析 service_config.json 失败: {e}")
        
        # 2. 从 main.py 中提取端口号（如果配置文件中没有）
        if 'port' not in config:
            port = self._extract_port_from_main()
            if port:
                config['port'] = port
        
        # 3. 从 main.py 中提取服务名称（如果配置文件中没有）
        if 'name' not in config:
            name = self._extract_name_from_main()
            if name:
                config['name'] = name
        
        # 4. 设置默认值
        config.setdefault('port', 8080)
        config.setdefault('name', self.service_path.name)
        config.setdefault('baseurl', f"http://localhost:{config['port']}")
        config.setdefault('description', '')
        config.setdefault('version', '1.0.0')
        config.setdefault('status', 'active')
        
        # 5. 添加路径信息
        config['service_path'] = str(self.service_path)
        config['service_dir'] = self.service_path.name
        
        return config
    
    def _parse_json_config(self, json_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析 JSON 配置文件
        
        要求：
        - accepted_files: 必须存在，定义服务接受的输入文件类型
        - output_config.items: 必须存在，每个输出项必须包含 file_type_id
        
        Args:
            json_config: JSON配置字典
            
        Returns:
            解析后的配置字典
            
        Raises:
            ValueError: 如果缺少必需字段或格式不正确
        """
        config = {}
        
        # 提取基本信息
        if 'name' in json_config:
            config['name'] = json_config['name']
        if 'description' in json_config:
            config['description'] = json_config['description']
        if 'version' in json_config:
            config['version'] = json_config['version']
        if 'status' in json_config:
            config['status'] = json_config['status']
        
        # 提取端口号（从 baseurl 中）
        if 'baseurl' in json_config:
            baseurl = json_config['baseurl']
            config['baseurl'] = baseurl
            # 从 URL 中提取端口号
            port_match = re.search(r':(\d+)', baseurl)
            if port_match:
                config['port'] = int(port_match.group(1))
        
        # 提取 API 路径
        if 'service_suffix' in json_config:
            config['service_suffix'] = json_config['service_suffix']
        if 'download_suffix' in json_config:
            config['download_suffix'] = json_config['download_suffix']
        
        # 提取参数模板
        if 'parameter_template' in json_config:
            config['parameter_template'] = json_config['parameter_template']
        
        # 提取参数模式
        if 'parameter_schema' in json_config:
            config['parameter_schema'] = json_config['parameter_schema']

        # 验证并提取输入文件配置（必需字段）
        if 'accepted_files' not in json_config:
            raise ValueError(
                "配置缺少必需字段 'accepted_files'。"
                "该字段用于定义服务接受的输入文件类型，格式："
                '{"filename.h5ad": {"file_type_ids": ["file_type_id"], "description": "..."}}'
            )
        
        accepted_files = json_config['accepted_files']
        if not isinstance(accepted_files, dict):
            raise ValueError(
                f"'accepted_files' 必须是字典类型，当前类型: {type(accepted_files).__name__}"
            )
        
        # 验证 accepted_files 结构
        for filename, file_config in accepted_files.items():
            if not isinstance(file_config, dict):
                raise ValueError(
                    f"'accepted_files.{filename}' 必须是字典类型，当前类型: {type(file_config).__name__}"
                )
            if 'file_type_ids' not in file_config:
                raise ValueError(
                    f"'accepted_files.{filename}' 缺少必需字段 'file_type_ids'"
                )
            file_type_ids = file_config['file_type_ids']
            if not isinstance(file_type_ids, list):
                raise ValueError(
                    f"'accepted_files.{filename}.file_type_ids' 必须是列表类型，当前类型: {type(file_type_ids).__name__}"
                )
            if not file_type_ids:
                raise ValueError(
                    f"'accepted_files.{filename}.file_type_ids' 不能为空列表"
                )
            for ft_id in file_type_ids:
                if not isinstance(ft_id, str) or not ft_id.strip():
                    raise ValueError(
                        f"'accepted_files.{filename}.file_type_ids' 中的每个元素必须是非空字符串"
                    )
        
        config['accepted_files'] = accepted_files
        
        # 验证并提取输出配置（必需字段）
        if 'output_config' not in json_config:
            raise ValueError(
                "配置缺少必需字段 'output_config'。"
                "该字段用于定义服务的输出结果，格式："
                '{"collection_description": "...", "items": [{"type": "file", "filename": "...", "file_type_id": "..."}]}'
            )
        
        output_config = json_config['output_config']
        if not isinstance(output_config, dict):
            raise ValueError(
                f"'output_config' 必须是字典类型，当前类型: {type(output_config).__name__}"
            )
        
        if 'items' not in output_config:
            raise ValueError("'output_config' 缺少必需字段 'items'")
        
        items = output_config['items']
        if not isinstance(items, list):
            raise ValueError(
                f"'output_config.items' 必须是列表类型，当前类型: {type(items).__name__}"
            )
        
        if not items:
            raise ValueError("'output_config.items' 不能为空列表")
        
        # 验证每个输出项都包含 file_type_id
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                raise ValueError(
                    f"'output_config.items[{idx}]' 必须是字典类型，当前类型: {type(item).__name__}"
                )
            if 'file_type_id' not in item:
                raise ValueError(
                    f"'output_config.items[{idx}]' 缺少必需字段 'file_type_id'。"
                    "每个输出项必须包含 file_type_id 字段，用于标识输出文件的类型。"
                )
            file_type_id = item['file_type_id']
            if not isinstance(file_type_id, str) or not file_type_id.strip():
                raise ValueError(
                    f"'output_config.items[{idx}].file_type_id' 必须是非空字符串"
                )
        
        config['output_config'] = output_config
        
        return config
    
    def _extract_port_from_main(self) -> Optional[int]:
        """从 main.py 中提取端口号"""
        main_py_path = self.service_path / "main.py"
        if not main_py_path.exists():
            return None
        
        try:
            with open(main_py_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 查找 uvicorn.run 中的 port 参数
            patterns = [
                r'uvicorn\.run\([^)]*port\s*=\s*(\d+)',
                r'port\s*=\s*(\d+)',
                r':(\d+)\)',  # 匹配 uvicorn.run(app, host="0.0.0.0", port=8080)
            ]
            
            for pattern in patterns:
                match = re.search(pattern, content)
                if match:
                    return int(match.group(1))
            
            # 查找环境变量 PORT
            env_match = re.search(r'os\.getenv\(["\']PORT["\']\s*,\s*(\d+)', content)
            if env_match:
                return int(env_match.group(1))
            
        except Exception as e:
            logger.warning(f"从 main.py 提取端口号失败: {e}")
        
        return None
    
    def _extract_name_from_main(self) -> Optional[str]:
        """从 main.py 中提取服务名称"""
        main_py_path = self.service_path / "main.py"
        if not main_py_path.exists():
            return None
        
        try:
            with open(main_py_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 查找 FastAPI 的 title 参数
            title_match = re.search(r'FastAPI\([^)]*title\s*=\s*["\']([^"\']+)["\']', content)
            if title_match:
                return title_match.group(1)
            
        except Exception as e:
            logger.warning(f"从 main.py 提取服务名称失败: {e}")
        
        return None

