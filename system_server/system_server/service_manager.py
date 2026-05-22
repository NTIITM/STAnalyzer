"""
系统服务管理器
用于管理多个微服务的 Docker 打包和配置提取
"""
import json
import logging
import subprocess
import os
import signal
import socket
import shutil
from urllib.parse import urlsplit, urlunsplit
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

try:
    import psutil  # type: ignore[import]
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

from .config_parser import ServiceConfigParser

logger = logging.getLogger(__name__)


class ServiceManager:
    """系统服务管理器"""
    
    def __init__(
        self,
        services_base_dir: Optional[Path] = None,
        project_root: Optional[Path] = None,
        services_config_path: Optional[Path] = None,
    ):
        """
        初始化服务管理器
        
        Args:
            services_base_dir: 服务项目的基础目录，如果为 None 则使用 system_services 目录本身
        """
        current_file = Path(__file__).resolve()
        if services_base_dir is None:
            # 默认使用 system_services 目录（服务与 ServiceManager 同级）
            services_base_dir = current_file.parent
        
        self.services_base_dir = Path(services_base_dir).resolve()
        if project_root is None:
            if self.services_base_dir.name == "system_services":
                project_root = self.services_base_dir.parent.parent
            else:
                project_root = self.services_base_dir.parent
        self.project_root = Path(project_root).resolve()
        self.server_dir = self.project_root / "server"
        self.services: List[Dict[str, Any]] = []
        self.service_processes: Dict[str, subprocess.Popen] = {}  # 存储运行中的服务进程
        self._docker_compose_cmd: Optional[List[str]] = None
        if services_config_path is not None:
            self.services_config_path = Path(services_config_path).resolve()
        else:
            self.services_config_path = self.services_base_dir / "services_config.json"
        self._assigned_ports: Dict[str, int] = {}
    
    def discover_services(self, pattern: str = "*") -> List[Path]:
        """
        发现服务项目
        
        Args:
            pattern: 目录匹配模式，默认为 "*"（所有目录）
        
        Returns:
            服务项目路径列表
        """
        services = []
        
        if not self.services_base_dir.exists():
            logger.warning(f"服务基础目录不存在: {self.services_base_dir}")
            return services
        
        # 获取当前文件所在目录（排除 Python 文件和其他非服务目录）
        current_file_dir = Path(__file__).resolve().parent
        python_files = {f.stem for f in current_file_dir.glob("*.py")}
        
        # 查找所有包含 main.py 的目录
        for item in self.services_base_dir.iterdir():
            if not item.is_dir():
                continue
            
            # 跳过 __pycache__ 等隐藏目录
            if item.name.startswith('__') or item.name.startswith('.'):
                continue
            
            # 跳过 Python 模块目录（与 Python 文件同名的目录）
            if item.name in python_files:
                continue
            
            # 检查是否包含 main.py（标识为服务项目）
            main_py = item / "main.py"
            if main_py.exists():
                services.append(item)
                logger.info(f"发现服务项目: {item.name}")
        
        return services
    
    def process_service(self, service_path: Path, generate_docker: bool = True) -> Dict[str, Any]:
        """
        处理单个服务项目
        
        Args:
            service_path: 服务项目路径
            generate_docker: 是否生成 Dockerfile（已废弃，不再使用）
        
        Returns:
            服务配置信息
        """
        logger.info(f"处理服务项目: {service_path}")
        
        # 解析服务配置
        parser = ServiceConfigParser(service_path)
        config = parser.parse()
        
        return config
    
    def process_all_services(
        self,
        generate_docker: bool = True,
        output_config_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        处理所有服务项目
        
        Args:
            generate_docker: 是否生成 Dockerfile（已废弃，不再使用）
            output_config_path: 输出配置文件路径，如果为 None 则输出到 system_services 目录
        
        Returns:
            所有服务的配置信息
        """
        # 发现所有服务
        service_paths = self.discover_services()
        
        if not service_paths:
            logger.warning("未发现任何服务项目")
            return {
                'services': [],
                'total': 0,
                'summary': {}
            }
        
        # 处理每个服务
        all_configs = []
        self.services = []
        for service_path in service_paths:
            try:
                config = self.process_service(service_path, generate_docker)
                all_configs.append(config)
                self.services.append(config)
            except Exception as e:
                logger.error(f"处理服务失败 {service_path}: {e}")
                all_configs.append({
                    'service_path': str(service_path),
                    'service_dir': service_path.name,
                    'error': str(e)
                })
        
        # 生成汇总信息
        summary = self._generate_summary(all_configs)
        
        result = {
            'services': all_configs,
            'total': len(all_configs),
            'summary': summary
        }
        
        # 输出配置文件
        if output_config_path is None:
            output_config_path = self.services_config_path
        else:
            output_config_path = Path(output_config_path)
            self.services_config_path = output_config_path
        
        self._write_config_file(result, output_config_path)
        
        return result
    
    def _generate_summary(self, configs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """生成汇总信息"""
        summary = {
            'total_services': len(configs),
            'ports': [],
            'services_by_port': {},
            'services_by_status': {},
        }
        
        for config in configs:
            if 'port' in config:
                port = config['port']
                summary['ports'].append(port)
                
                if port not in summary['services_by_port']:
                    summary['services_by_port'][port] = []
                summary['services_by_port'][port].append({
                    'name': config.get('name', config.get('service_dir', 'unknown')),
                    'path': config.get('service_path', ''),
                })
            
            status = config.get('status', 'unknown')
            if status not in summary['services_by_status']:
                summary['services_by_status'][status] = []
            summary['services_by_status'][status].append(
                config.get('name', config.get('service_dir', 'unknown'))
            )
        
        # 排序端口列表
        summary['ports'] = sorted(set(summary['ports']))
        
        return summary
    
    def _write_config_file(self, config_data: Dict[str, Any], output_path: Path) -> None:
        """写入配置文件"""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"配置文件已生成: {output_path}")
    
    def _persist_services_snapshot(self) -> None:
        """将当前服务列表写入总配置文件"""
        if not self.services_config_path:
            return
        
        snapshot = {
            'services': self.services,
            'total': len(self.services),
            'summary': self._generate_summary(self.services),
        }
        self._write_config_file(snapshot, self.services_config_path)
    
    def _release_port(self, service_name: str) -> None:
        """释放服务已分配的端口"""
        if service_name in self._assigned_ports:
            del self._assigned_ports[service_name]
    
    def _cleanup_service_state(self, service_name: str) -> None:
        """清理服务的内部运行状态记录"""
        if service_name in self.service_processes:
            del self.service_processes[service_name]
        self._release_port(service_name)
    
    def _is_port_available_for_assignment(self, port: int) -> bool:
        """检测端口是否可用于分配"""
        if port in self._assigned_ports.values():
            return False
        return not self._is_port_in_use(port)
    
    def _find_free_port(self) -> int:
        """查找可用端口"""
        while True:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('localhost', 0))
                port = s.getsockname()[1]
            if self._is_port_available_for_assignment(port):
                return port
    
    def _coerce_baseurl_with_port(self, baseurl: Optional[str], port: int) -> str:
        """根据端口生成/更新 baseurl"""
        candidate = (baseurl or "").strip()
        if not candidate:
            return f"http://localhost:{port}"
        if "://" not in candidate:
            candidate = f"http://{candidate}"
        try:
            parts = urlsplit(candidate)
        except Exception:
            return f"http://localhost:{port}"
        
        scheme = parts.scheme or "http"
        hostname = parts.hostname or "localhost"
        netloc = hostname
        
        if parts.username:
            userinfo = parts.username
            if parts.password:
                userinfo = f"{userinfo}:{parts.password}"
            netloc = f"{userinfo}@{hostname}"
        
        netloc = f"{netloc}:{port}"
        return urlunsplit((scheme, netloc, parts.path or "", parts.query or "", parts.fragment or ""))
    
    def _update_service_port_config(
        self,
        service_name: str,
        service_config: Dict[str, Any],
        service_path: Path,
        port: int,
    ) -> None:
        """更新单个服务目录中的 service_config.json 端口信息"""
        config_path = Path(service_config.get('config_path') or (service_path / "service_config.json"))
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        payload: Dict[str, Any] = {}
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    payload = json.load(f)
            except Exception as exc:  # pragma: no cover - 容错
                logger.warning("读取服务配置失败 %s: %s", config_path, exc)
                payload = {}
        
        payload['port'] = port
        payload['baseurl'] = self._coerce_baseurl_with_port(
            payload.get('baseurl') or service_config.get('baseurl'),
            port,
        )
        
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception as exc:  # pragma: no cover - 写入失败
            logger.error("写入服务配置失败 %s: %s", config_path, exc)
        
        service_config['port'] = port
        service_config['baseurl'] = payload['baseurl']
        service_config['config_path'] = str(config_path)
        logger.info("服务 %s 端口已更新为 %s (配置: %s)", service_name, port, config_path)
        self._persist_services_snapshot()
    
    def _allocate_port(
        self,
        service_name: str,
        service_config: Dict[str, Any],
        service_path: Path,
    ) -> int:
        """为服务分配新的可用端口，并同步到 service_config.json"""
        if service_name in self._assigned_ports:
            port = self._assigned_ports[service_name]
            # 确保已分配的端口也同步到 service_config.json
            self._update_service_port_config(service_name, service_config, service_path, port)
            return port
        
        # 优先使用配置文件中已有的端口（如果可用）
        config_port = service_config.get('port')
        if config_port and self._is_port_available_for_assignment(config_port):
            port = config_port
            self._assigned_ports[service_name] = port
            self._update_service_port_config(service_name, service_config, service_path, port)
            logger.info(f"使用配置文件中的端口 {port} 启动服务 {service_name}")
            return port
        
        # 如果配置端口不可用，分配新端口
        port = self._find_free_port()
        self._assigned_ports[service_name] = port
        self._update_service_port_config(service_name, service_config, service_path, port)
        if config_port and config_port != port:
            logger.warning(
                f"服务 {service_name} 配置的端口 {config_port} 不可用，已分配新端口 {port}"
            )
        return port
    
    def get_service_config(self, service_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        获取服务配置
        
        Args:
            service_name: 服务名称，如果为 None 则返回所有服务配置
        
        Returns:
            服务配置信息
        """
        if service_name is None:
            return {'services': self.services}
        
        for service in self.services:
            if service.get('name') == service_name or service.get('service_dir') == service_name:
                return service
        
        return None
    
    def get_port_mapping(self) -> Dict[int, List[str]]:
        """
        获取端口映射
        
        Returns:
            端口到服务名称列表的映射
        """
        port_mapping = {}
        
        for service in self.services:
            port = service.get('port')
            if port:
                if port not in port_mapping:
                    port_mapping[port] = []
                port_mapping[port].append(
                    service.get('name', service.get('service_dir', 'unknown'))
                )
        
        return port_mapping
    
    def load_all_service_configs(self) -> Dict[str, Dict[str, Any]]:
        """
        加载所有服务的配置（从 service_config.json）
        
        Returns:
            服务名称到配置的映射
        """
        configs = {}
        service_paths = self.discover_services()
        
        for service_path in service_paths:
            try:
                parser = ServiceConfigParser(service_path)
                config = parser.parse()
                service_name = config.get('name', service_path.name)
                configs[service_name] = config
                logger.info(f"加载服务配置: {service_name}")
            except Exception as e:
                logger.error(f"加载服务配置失败 {service_path}: {e}")
        
        return configs
    
    def _resolve_service(self, service_name: str) -> Optional[Tuple[Dict[str, Any], Path]]:
        """
        根据名称解析服务配置和路径.

        Args:
            service_name: 服务名称或目录名

        Returns:
            (服务配置, 服务路径) 元组，如果未找到则返回 None
        """
        service_config = None
        service_path = None

        for service in self.services:
            if (
                service.get("name") == service_name
                or service.get("service_dir") == service_name
            ):
                service_config = service
                service_path_str = service.get("service_path")
                if service_path_str:
                    service_path = Path(service_path_str)
                break

        if service_config is None:
            candidate_path = self.services_base_dir / service_name
            if not candidate_path.exists():
                logger.error(f"服务不存在: {service_name}")
                return None
            parser = ServiceConfigParser(candidate_path)
            service_config = parser.parse()
            self.services.append(service_config)
            service_path = Path(service_config.get("service_path", candidate_path))

        if service_path is None:
            service_path = self.services_base_dir / service_config.get(
                "service_dir", service_name
            )

        return service_config, service_path

    def _get_docker_compose_command(self) -> Optional[List[str]]:
        """
        解析可用的 Docker Compose 命令.

        Returns:
            命令列表，例如 ["docker", "compose"] 或 ["docker-compose"]，若不存在则返回 None
        """
        if self._docker_compose_cmd == []:
            return None
        if self._docker_compose_cmd:
            return self._docker_compose_cmd

        # 优先使用 Docker Compose 插件
        docker_path = shutil.which("docker")
        if docker_path:
            try:
                result = subprocess.run(
                    [docker_path, "compose", "version"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if result.returncode == 0:
                    self._docker_compose_cmd = [docker_path, "compose"]
                    return self._docker_compose_cmd
            except Exception:
                pass

        # 回退到独立的 docker-compose 命令
        docker_compose_path = shutil.which("docker-compose")
        if docker_compose_path:
            self._docker_compose_cmd = [docker_compose_path]
            return self._docker_compose_cmd

        logger.error("未找到 Docker Compose 命令，请确认已安装 docker 或 docker-compose")
        self._docker_compose_cmd = []
        return None
    
    def _prepare_docker_env(self) -> Dict[str, str]:
        """
        准备 Docker 命令使用的环境变量，清理无效的 DOCKER_HOST 配置.
        
        Returns:
            清理后的环境变量字典
        """
        env = os.environ.copy()
        
        # 检查并清理无效的 DOCKER_HOST
        docker_host = env.get("DOCKER_HOST", "")
        if docker_host:
            # 检查是否是无效的 URL scheme（如 http+docker://）
            if "http+docker" in docker_host.lower() or not docker_host.startswith(("unix://", "tcp://", "tcp+tls://", "ssh://")):
                logger.warning(
                    "检测到无效的 DOCKER_HOST 值 '%s'，将移除该环境变量以使用默认 Docker socket",
                    docker_host
                )
                env.pop("DOCKER_HOST", None)
            # 如果 DOCKER_HOST 为空字符串，也移除它
            elif not docker_host.strip():
                env.pop("DOCKER_HOST", None)
        
        return env
    
    def _check_docker_image_exists(self, image_name: str) -> bool:
        """
        检查 Docker 镜像是否存在
        
        Args:
            image_name: 镜像名称（支持tag，如 "image:tag"）
        
        Returns:
            镜像是否存在
        """
        docker_path = shutil.which("docker")
        if not docker_path:
            logger.warning("未找到 docker 命令，无法检查镜像")
            return False
        
        try:
            result = subprocess.run(
                [docker_path, "images", "-q", image_name],
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
            return result.returncode == 0 and bool(result.stdout.strip())
        except Exception as e:
            logger.warning(f"检查镜像 {image_name} 时出错: {e}")
            return False
    
    def _get_image_name_from_compose(self, compose_file: Path, service_name: str) -> Optional[str]:
        """
        从 docker-compose.yml 中提取镜像名称
        
        Args:
            compose_file: docker-compose.yml 文件路径
            service_name: 服务名称
        
        Returns:
            镜像名称，如果无法确定则返回 None
        """
        try:
            import yaml
            with open(compose_file, 'r', encoding='utf-8') as f:
                compose_data = yaml.safe_load(f)
            
            if not compose_data or 'services' not in compose_data:
                return None
            
            service_config = compose_data['services'].get(service_name)
            if not service_config:
                return None
            
            # 优先使用 image 字段
            if 'image' in service_config:
                return service_config['image']
            
            # 如果没有 image 字段，使用 build 上下文推断镜像名称
            # docker-compose 通常使用 "{目录名}:latest" 或 "{项目名}_{服务名}:latest"
            if 'build' in service_config:
                # 尝试使用服务名称作为镜像名称
                image_name = f"{service_name}:latest"
                return image_name
            
            return None
        except ImportError:
            logger.warning("未安装 PyYAML，无法解析 docker-compose.yml")
            # 回退方案：使用服务名称
            return f"{service_name}:latest"
        except Exception as e:
            logger.warning(f"解析 docker-compose.yml 时出错: {e}")
            # 回退方案：使用服务名称
            return f"{service_name}:latest"
    
    def _get_container_name_from_compose(self, compose_file: Path, service_name: str) -> Optional[str]:
        """
        从 docker-compose.yml 中提取容器名称
        
        Args:
            compose_file: docker-compose.yml 文件路径
            service_name: 服务名称
        
        Returns:
            容器名称，如果无法确定则返回服务名称
        """
        try:
            import yaml
            with open(compose_file, 'r', encoding='utf-8') as f:
                compose_data = yaml.safe_load(f)
            
            if not compose_data or 'services' not in compose_data:
                return service_name
            
            service_config = compose_data['services'].get(service_name)
            if not service_config:
                return service_name
            
            # 优先使用 container_name 字段
            if 'container_name' in service_config:
                return service_config['container_name']
            
            return service_name
        except Exception:
            return service_name

    def start_service(
        self,
        service_name: str,
        background: bool = True,
        wait_ready: bool = False
    ) -> Optional[subprocess.Popen]:
        """
        启动单个服务
        
        Args:
            service_name: 服务名称或目录名
            background: 是否在后台运行
            wait_ready: 是否等待服务就绪
        
        Returns:
            服务进程对象，如果失败返回 None
        """
        resolved = self._resolve_service(service_name)
        if resolved is None:
            return None
        service_config, service_path = resolved
        
        # 检查服务是否已在运行
        if service_name in self.service_processes:
            process = self.service_processes[service_name]
            if process.poll() is None:  # 进程仍在运行
                logger.warning(f"服务 {service_name} 已在运行 (PID: {process.pid})")
                return process
            logger.info(
                "检测到服务 %s 先前的进程已结束 (退出码: %s)，清理状态",
                service_name,
                process.returncode,
            )
            self._cleanup_service_state(service_name)
        
        # 动态分配端口
        port = self._allocate_port(service_name, service_config, service_path)
        
        # 启动服务
        try:
            env = os.environ.copy()
            env['PYTHONUNBUFFERED'] = '1'
            env['PORT'] = str(port)
            
            # 使用 stpp conda 环境的 Python
            # 优先使用环境变量指定的 Python，否则使用 stpp 环境的 Python
            python_path = os.getenv('SERVICE_PYTHON', '/home/common/hwluo/anaconda3/envs/stpp/bin/python')
            if not os.path.exists(python_path):
                # 如果指定路径不存在，回退到系统 python
                python_path = 'python'
            
            cmd = [python_path, 'main.py']
            
            if background:
                process = subprocess.Popen(
                    cmd,
                    cwd=service_path,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )
            else:
                process = subprocess.Popen(
                    cmd,
                    cwd=service_path,
                    env=env,
                    stdout=None,
                    stderr=None
                )
            
            self.service_processes[service_name] = process
            logger.info(f"服务 {service_name} 已启动 (PID: {process.pid}, 端口: {port})")
            
            # 检查进程是否立即退出（常见于缺少依赖或配置错误）
            import time
            time.sleep(0.5)  # 等待进程启动
            
            if process.poll() is not None:
                # 进程已退出，读取错误输出
                exit_code = process.returncode
                error_output = ""
                try:
                    if process.stdout:
                        # 读取所有可用输出
                        import sys
                        if sys.platform != 'win32':
                            # 非 Windows 系统可以使用 select
                            try:
                                import select
                                if select.select([process.stdout], [], [], 0.1)[0]:
                                    error_output = process.stdout.read(5000)
                            except (ImportError, OSError):
                                # select 不可用或出错，直接读取
                                error_output = process.stdout.read(5000)
                        else:
                            # Windows 系统直接读取
                            error_output = process.stdout.read(5000)
                except Exception as read_err:
                    logger.debug(f"读取服务 {service_name} 输出时出错: {read_err}")
                
                # 记录错误信息
                logger.error(
                    f"服务 {service_name} 启动后立即退出 (PID: {process.pid}, 退出码: {exit_code})"
                )
                if error_output:
                    # 只记录前 1000 个字符，避免日志过长
                    error_preview = error_output[:1000] if len(error_output) > 1000 else error_output
                    logger.error(f"服务 {service_name} 错误输出:\n{error_preview}")
                    if len(error_output) > 1000:
                        logger.error(f"... (输出被截断，共 {len(error_output)} 字符)")
                
                # 清理状态
                self._cleanup_service_state(service_name)
                return None
            
            if wait_ready:
                # 等待服务就绪（简单实现，可以改进）
                time.sleep(2)
            
            return process
            
        except Exception as e:
            logger.error(f"启动服务失败 {service_name}: {e}")
            return None
    
    def start_service_docker(
        self,
        service_name: str,
        *,
        build: bool = False,
        detach: bool = True,
        extra_args: Optional[List[str]] = None,
    ) -> bool:
        """
        通过 Docker 启动服务.
        直接使用 docker run 命令启动容器，不依赖 docker-compose.yml 文件.
        如果容器已存在或正在运行，会先停止并删除，然后重新运行.

        Args:
            service_name: 服务名称或目录名
            build: 是否在启动前构建镜像（未使用，保留以兼容接口）
            detach: 是否以后台模式运行
            extra_args: 额外的参数（未使用，保留以兼容接口）

        Returns:
            是否启动成功
        """
        resolved = self._resolve_service(service_name)
        if resolved is None:
            return False
        service_config, service_path = resolved

        # 使用服务名称作为镜像名称和容器名称（标准化处理）
        import re
        normalized_name = service_name.lower().replace(' ', '-').replace('_', '-')
        normalized_name = re.sub(r'[^a-z0-9-]', '', normalized_name)
        
        # 尝试从配置中获取镜像名称，否则使用服务名称
        image_name = service_config.get('docker_image') or f"{normalized_name}:latest"
        container_name = normalized_name
        
        # 检查镜像是否存在
        image_exists = self._check_docker_image_exists(image_name)
        
        if not image_exists:
            logger.error(f"镜像 {image_name} 不存在，请先构建镜像")
            return False
        
        logger.info(f"检测到镜像 {image_name} 已存在，直接启动容器")
        
        # 分配端口
        port = self._allocate_port(service_name, service_config, service_path)
        
        # 使用 docker run 启动容器（会自动处理已存在的容器）
        return self._start_container_with_image(
            service_name, service_config, service_path,
            image_name, container_name, port, detach=detach
        )
    
    def _ensure_docker_network(self, network_name: str = "services-network") -> bool:
        """
        确保 Docker 网络存在，如果不存在则创建
        
        Args:
            network_name: 网络名称
        
        Returns:
            网络是否存在或创建成功
        """
        docker_path = shutil.which("docker")
        if not docker_path:
            logger.error("未找到 docker 命令")
            return False
        
        try:
            # 检查网络是否存在
            check_result = subprocess.run(
                [docker_path, "network", "ls", "--filter", f"name=^{network_name}$", "--format", "{{.Name}}"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            
            if network_name in check_result.stdout:
                logger.debug(f"Docker 网络 {network_name} 已存在")
                return True
            
            # 创建网络
            logger.info(f"创建 Docker 网络 {network_name}")
            create_result = subprocess.run(
                [docker_path, "network", "create", network_name],
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
            
            if create_result.returncode == 0:
                logger.info(f"Docker 网络 {network_name} 创建成功")
                return True
            else:
                logger.warning(f"创建 Docker 网络 {network_name} 失败: {create_result.stderr}")
                return False
                
        except Exception as e:
            logger.warning(f"检查/创建 Docker 网络时出错: {e}")
            return False
    
    def _stop_container_directly(
        self,
        service_name: str,
        service_config: Dict[str, Any],
        service_path: Path,
        remove_volumes: bool = False,
    ) -> bool:
        """
        直接使用 docker stop/rm 停止和删除容器（不依赖 docker-compose.yml）
        
        Args:
            service_name: 服务名称
            service_config: 服务配置
            service_path: 服务路径
            remove_volumes: 是否删除挂载卷
        
        Returns:
            是否停止成功
        """
        docker_path = shutil.which("docker")
        if not docker_path:
            logger.error("未找到 docker 命令")
            return False
        
        # 获取容器名称（与启动时使用的名称一致）
        import re
        normalized_name = service_name.lower().replace(' ', '-').replace('_', '-')
        normalized_name = re.sub(r'[^a-z0-9-]', '', normalized_name)
        container_name = normalized_name
        
        # 检查容器是否存在
        try:
            check_result = subprocess.run(
                [docker_path, "ps", "-a", "--filter", f"name=^{container_name}$", "--format", "{{.Names}}"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            if container_name not in check_result.stdout:
                logger.info(f"容器 {container_name} 不存在，无需停止")
                return True
            
            # 检查容器是否正在运行
            status_result = subprocess.run(
                [docker_path, "ps", "--filter", f"name=^{container_name}$", "--format", "{{.Status}}"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            if "Up" in status_result.stdout:
                logger.info(f"停止容器 {container_name}")
                # 先尝试优雅停止容器（增加超时时间到 30 秒）
                try:
                    stop_result = subprocess.run(
                        [docker_path, "stop", container_name],
                        capture_output=True,
                        text=True,
                        check=False,
                        timeout=30,
                    )
                    if stop_result.returncode != 0:
                        logger.warning(f"停止容器 {container_name} 失败: {stop_result.stderr}")
                        # 如果优雅停止失败，尝试强制停止
                        logger.info(f"尝试强制停止容器 {container_name}")
                        kill_result = subprocess.run(
                            [docker_path, "kill", container_name],
                            capture_output=True,
                            text=True,
                            check=False,
                            timeout=10,
                        )
                        if kill_result.returncode != 0:
                            logger.warning(f"强制停止容器 {container_name} 失败: {kill_result.stderr}")
                        else:
                            logger.info(f"容器 {container_name} 已强制停止")
                    else:
                        logger.info(f"容器 {container_name} 已停止")
                except subprocess.TimeoutExpired:
                    # 如果优雅停止超时，使用强制停止
                    logger.warning(f"停止容器 {container_name} 超时，尝试强制停止")
                    try:
                        kill_result = subprocess.run(
                            [docker_path, "kill", container_name],
                            capture_output=True,
                            text=True,
                            check=False,
                            timeout=10,
                        )
                        if kill_result.returncode != 0:
                            logger.warning(f"强制停止容器 {container_name} 失败: {kill_result.stderr}")
                        else:
                            logger.info(f"容器 {container_name} 已强制停止")
                    except subprocess.TimeoutExpired:
                        logger.error(f"强制停止容器 {container_name} 也超时")
                    except Exception as e:
                        logger.error(f"强制停止容器 {container_name} 时出现异常: {e}")
                except Exception as e:
                    logger.error(f"停止容器 {container_name} 时出现异常: {e}")
                    # 尝试强制停止
                    try:
                        logger.info(f"尝试强制停止容器 {container_name}")
                        kill_result = subprocess.run(
                            [docker_path, "kill", container_name],
                            capture_output=True,
                            text=True,
                            check=False,
                            timeout=10,
                        )
                        if kill_result.returncode == 0:
                            logger.info(f"容器 {container_name} 已强制停止")
                    except Exception as kill_error:
                        logger.error(f"强制停止容器 {container_name} 时出现异常: {kill_error}")
            
            # 删除容器
            logger.info(f"删除容器 {container_name}")
            rm_cmd = [docker_path, "rm", "-f"]
            if remove_volumes:
                rm_cmd.append("-v")
            rm_cmd.append(container_name)
            
            rm_result = subprocess.run(
                rm_cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
            if rm_result.returncode != 0:
                logger.warning(f"删除容器 {container_name} 失败: {rm_result.stderr}")
                return False
            
            logger.info(f"容器 {container_name} 已删除")
            return True
            
        except Exception as e:
            logger.error(f"停止容器 {container_name} 时出现异常: {e}")
            return False
    
    def _get_container_host_port(self, container_name: str) -> Optional[int]:
        """
        获取容器的宿主机端口映射
        
        Args:
            container_name: 容器名称
        
        Returns:
            宿主机端口号，如果未找到则返回 None
        """
        docker_path = shutil.which("docker")
        if not docker_path:
            return None
        
        try:
            # 使用 docker inspect 获取端口映射
            result = subprocess.run(
                [docker_path, "inspect", container_name, "--format", "{{json .HostConfig.PortBindings}}"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            if result.returncode != 0:
                return None
            
            import json
            port_bindings = json.loads(result.stdout.strip())
            # 查找 8080/tcp 的端口映射
            if "8080/tcp" in port_bindings and port_bindings["8080/tcp"]:
                host_port = port_bindings["8080/tcp"][0].get("HostPort")
                if host_port:
                    return int(host_port)
        except Exception as e:
            logger.debug(f"获取容器 {container_name} 端口映射时出错: {e}")
        
        return None
    
    def _start_container_with_image(
        self,
        service_name: str,
        service_config: Dict[str, Any],
        service_path: Path,
        image_name: str,
        container_name: str,
        port: int,
        detach: bool = True,
    ) -> bool:
        """
        使用已存在的镜像启动容器
        
        Args:
            service_name: 服务名称
            service_config: 服务配置
            service_path: 服务路径
            image_name: 镜像名称
            container_name: 容器名称
            port: 分配的端口
            detach: 是否在后台运行
        
        Returns:
            是否启动成功
        """
        docker_path = shutil.which("docker")
        if not docker_path:
            logger.error("未找到 docker 命令")
            return False
        
        # 确保网络存在
        self._ensure_docker_network("services-network")
        
        # 检查容器是否已存在，如果存在则检查端口映射是否匹配
        try:
            check_result = subprocess.run(
                [docker_path, "ps", "-a", "--filter", f"name=^{container_name}$", "--format", "{{.Names}}"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            if container_name in check_result.stdout:
                # 检查容器的端口映射
                container_host_port = self._get_container_host_port(container_name)
                if container_host_port is not None and container_host_port != port:
                    logger.warning(
                        f"容器 {container_name} 的端口映射 ({container_host_port}) 与配置端口 ({port}) 不匹配，将删除并重新创建容器"
                    )
                    # 停止并删除容器
                    self._stop_container_directly(service_name, service_config, service_path, remove_volumes=False)
                else:
                    # 端口匹配，检查容器状态
                    status_result = subprocess.run(
                        [docker_path, "ps", "--filter", f"name=^{container_name}$", "--format", "{{.Status}}"],
                        capture_output=True,
                        text=True,
                        check=False,
                        timeout=5,
                    )
                    if "Up" in status_result.stdout:
                        if container_host_port == port:
                            logger.info(f"容器 {container_name} 正在运行，端口匹配 ({port})，跳过重建")
                            return True
                        else:
                            # 端口不匹配，需要重新创建
                            logger.warning(
                                f"容器 {container_name} 正在运行但端口不匹配，将停止并重新创建"
                            )
                            self._stop_container_directly(service_name, service_config, service_path, remove_volumes=False)
                    else:
                        # 容器存在但未运行，端口匹配则直接启动
                        if container_host_port == port:
                            logger.info(f"容器 {container_name} 已存在但未运行，端口匹配 ({port})，尝试直接启动")
                            start_result = subprocess.run(
                                [docker_path, "start", container_name],
                                capture_output=True,
                                text=True,
                                check=False,
                                timeout=15,
                            )
                            if start_result.returncode == 0:
                                logger.info(f"容器 {container_name} 已启动")
                                return True
                            
                            logger.warning(
                                "容器 %s 启动失败，返回码=%s，stderr=%s；将尝试重新创建容器",
                                container_name,
                                start_result.returncode,
                                start_result.stderr.strip(),
                            )
        except Exception as e:
            logger.warning(f"检查容器状态时出错: {e}")
        
        # 构建 docker run 命令
        cmd = [docker_path, "run"]
        if detach:
            cmd.append("-d")
        else:
            cmd.append("-it")
        
        # 检查是否需要 GPU 支持（通过检查 docker-compose.yml 中的 NVIDIA_VISIBLE_DEVICES）
        gpu_support_needed = False
        nvidia_visible_devices = None
        compose_file = service_path / "docker-compose.yml"
        if compose_file.exists() and HAS_YAML:
            try:
                with open(compose_file, 'r', encoding='utf-8') as f:
                    compose_config = yaml.safe_load(f)
                    if compose_config and 'services' in compose_config:
                        for svc_name, svc_config in compose_config['services'].items():
                            if svc_config and 'environment' in svc_config:
                                for env_var in svc_config['environment']:
                                    if isinstance(env_var, str) and env_var.startswith('NVIDIA_VISIBLE_DEVICES='):
                                        nvidia_visible_devices = env_var.split('=', 1)[1]
                                        gpu_support_needed = True
                                        break
                                    elif isinstance(env_var, dict) and 'NVIDIA_VISIBLE_DEVICES' in env_var:
                                        nvidia_visible_devices = env_var['NVIDIA_VISIBLE_DEVICES']
                                        gpu_support_needed = True
                                        break
                            # 检查是否有 runtime: nvidia 配置
                            if svc_config and svc_config.get('runtime') == 'nvidia':
                                gpu_support_needed = True
            except Exception as e:
                logger.debug(f"读取 docker-compose.yml 时出错: {e}")
        
        # 如果检测到需要 GPU 支持，添加 --gpus 参数
        if gpu_support_needed:
            # 检查系统是否有 GPU 支持
            try:
                check_gpu = subprocess.run(
                    [docker_path, "info"],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=5,
                )
                if check_gpu.returncode == 0 and ('nvidia' in check_gpu.stdout.lower() or 'gpu' in check_gpu.stdout.lower()):
                    # 根据 NVIDIA_VISIBLE_DEVICES 设置 GPU 参数
                    # Docker --gpus 参数格式：
                    #   --gpus all                    # 使用所有 GPU
                    #   --gpus device=0               # 使用单个 GPU
                    #   --gpus device=0,1             # 使用多个 GPU（某些 Docker 版本可能不支持）
                    # 注意：如果指定了特定的设备 ID，使用 --gpus all 并通过 NVIDIA_VISIBLE_DEVICES 环境变量控制可见设备
                    # 这样可以避免 "cannot set both Count and DeviceIDs" 错误
                    if nvidia_visible_devices and nvidia_visible_devices.strip() and nvidia_visible_devices.strip() != "all":
                        # 清理设备 ID 字符串，移除空格
                        device_ids = nvidia_visible_devices.strip().replace(" ", "")
                        # 对于单个设备，使用 device=ID 格式；对于多个设备，使用 all 并通过环境变量控制
                        if ',' in device_ids:
                            # 多个设备：使用 --gpus all，通过 NVIDIA_VISIBLE_DEVICES 环境变量控制
                            cmd.extend(["--gpus", "all"])
                            logger.info(f"为容器 {container_name} 启用 GPU 支持 (设备: {device_ids}, 通过 NVIDIA_VISIBLE_DEVICES 控制)")
                        else:
                            # 单个设备：使用 device=ID 格式
                            cmd.extend(["--gpus", f"device={device_ids}"])
                            logger.info(f"为容器 {container_name} 启用 GPU 支持 (设备: {device_ids})")
                    else:
                        cmd.extend(["--gpus", "all"])
                        logger.info(f"为容器 {container_name} 启用 GPU 支持 (所有设备)")
                else:
                    logger.warning(f"检测到服务需要 GPU，但系统可能不支持 GPU，将使用 CPU 模式")
            except Exception as e:
                logger.warning(f"检查 GPU 支持时出错: {e}，将使用 CPU 模式")
        
        # 容器内端口固定为 8080，主机端口动态分配
        container_port = 8080
        # 统一将容器输出目录挂载到宿主机路径，便于集中管理
        host_output_dir = os.getenv("SERVICE_OUTPUT_DIR", str(self.project_root / "service_output"))
        cmd.extend([
            "--name", container_name,
            "-p", f"{port}:{container_port}",
            "-e", f"PORT={container_port}",
            "-e", f"OUTPUT_DIR=/app/outputs",
            "-v", f"{host_output_dir}:/app/outputs",
            "--network", "services-network",
            "--restart", "no",
        ])
        
        # 如果检测到 NVIDIA_VISIBLE_DEVICES，添加到环境变量
        if nvidia_visible_devices:
            cmd.extend(["-e", f"NVIDIA_VISIBLE_DEVICES={nvidia_visible_devices}"])
        
        cmd.append(image_name)
        
        logger.info(f"启动容器 {container_name} (镜像: {image_name}, 端口: {port})")
        logger.debug(f"执行 Docker 命令: {' '.join(cmd)}")
        try:
            result = subprocess.run(
                cmd,
                cwd=service_path,
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            
            if result.returncode != 0:
                stderr = result.stderr.strip()
                stdout = result.stdout.strip()
                logger.error(
                    "启动容器 %s 失败 (exit=%s): %s",
                    container_name,
                    result.returncode,
                    stderr or stdout,
                )
                return False
            
            logger.info(f"容器 {container_name} 已启动")
            return True
            
        except subprocess.TimeoutExpired:
            logger.error(f"启动容器 {container_name} 超时")
            return False
        except Exception as e:
            logger.error(f"启动容器 {container_name} 时出现异常: {e}")
            return False
    
    def _start_service_with_compose(
        self,
        service_name: str,
        service_config: Dict[str, Any],
        service_path: Path,
        build: bool = False,
        detach: bool = True,
        extra_args: Optional[List[str]] = None,
    ) -> bool:
        """
        使用 Docker Compose 启动服务
        
        Args:
            service_name: 服务名称
            service_config: 服务配置
            service_path: 服务路径
            build: 是否构建镜像
            detach: 是否在后台运行
            extra_args: 额外参数
        
        Returns:
            是否启动成功
        """
        compose_cmd = self._get_docker_compose_command()
        if not compose_cmd:
            logger.error(f"无法通过 Docker Compose 启动服务 {service_name}：未找到 Docker Compose 命令")
            return False

        compose_file = service_path / "docker-compose.yml"
        if not compose_file.exists():
            logger.error(f"服务 {service_name} 缺少 docker-compose.yml 文件: {compose_file}")
            return False

        # 分配端口
        port = self._allocate_port(service_name, service_config, service_path)

        cmd = compose_cmd + ["up"]
        if build:
            cmd.append("--build")
        if detach:
            cmd.append("-d")
        if extra_args:
            cmd.extend(extra_args)

        env = os.environ.copy()
        env["PORT"] = str(port)

        logger.info("通过 Docker Compose 启动服务 %s (端口: %s)", service_name, port)
        try:
            result = subprocess.run(
                cmd,
                cwd=service_path,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError as exc:
            logger.error(f"Docker Compose 未安装或不可用，无法启动服务 {service_name}: {exc}")
            return False
        except Exception as exc:
            logger.error(f"使用 Docker Compose 启动服务 {service_name} 时出现异常: {exc}")
            return False

        if result.returncode != 0:
            stderr = result.stderr.strip()
            stdout = result.stdout.strip()
            logger.error(
                "Docker Compose 启动服务 %s 失败 (exit=%s): %s",
                service_name,
                result.returncode,
                stderr or stdout,
            )
            return False

        if result.stdout:
            logger.debug("Docker Compose 输出 (%s): %s", service_name, result.stdout.strip())
        if result.stderr:
            logger.debug("Docker Compose 错误输出 (%s): %s", service_name, result.stderr.strip())

        logger.info("服务 %s 已通过 Docker Compose 启动", service_name)
        return True

    def start_api_server_docker(
        self,
        *,
        build: bool = False,
        detach: bool = True,
        extra_args: Optional[List[str]] = None,
    ) -> bool:
        """
        通过 Docker Compose 启动 API Server.

        Args:
            build: 是否在启动前构建镜像
            detach: 是否以后台模式运行
            extra_args: 额外 compose 参数
        """
        if not self.server_dir.exists():
            logger.error("未找到 API Server 目录: %s", self.server_dir)
            return False

        compose_cmd = self._get_docker_compose_command()
        if not compose_cmd:
            logger.error("无法通过 Docker 启动 API Server：未找到 Docker Compose 命令")
            return False

        compose_file = self.server_dir / "docker-compose.yml"
        if not compose_file.exists():
            logger.error("API Server 缺少 docker-compose.yml 文件: %s", compose_file)
            return False

        cmd = compose_cmd + ["-f", str(compose_file), "up"]
        if build:
            cmd.append("--build")
        if detach:
            cmd.append("-d")
        if extra_args:
            cmd.extend(extra_args)

        env = os.environ.copy()
        env.setdefault("TEXTMSA_PROJECT_ROOT", str(self.project_root))
        try:
            from textmsa.settings import get_server_config  # pylint: disable=import-outside-toplevel

            port = get_server_config().get("port")
            if port:
                env.setdefault("PORT", str(port))
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("获取服务器配置失败，使用默认端口: %s", exc)

        logger.info("通过 Docker Compose 启动 API Server")
        try:
            result = subprocess.run(
                cmd,
                cwd=self.server_dir,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError as exc:
            logger.error("Docker Compose 未安装或不可用，无法启动 API Server: %s", exc)
            return False
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("启动 API Server Docker 容器时出现异常: %s", exc)
            return False

        if result.returncode != 0:
            stderr = result.stderr.strip()
            stdout = result.stdout.strip()
            logger.error(
                "Docker Compose 启动 API Server 失败 (exit=%s): %s",
                result.returncode,
                stderr or stdout,
            )
            return False

        if result.stdout:
            logger.debug("Docker Compose 输出 (api-server): %s", result.stdout.strip())
        if result.stderr:
            logger.debug("Docker Compose 错误输出 (api-server): %s", result.stderr.strip())

        logger.info("API Server 已通过 Docker Compose 启动")
        return True
    
    def stop_service_docker(
        self,
        service_name: str,
        *,
        remove_volumes: bool = False,
        extra_args: Optional[List[str]] = None,
    ) -> bool:
        """
        停止单个服务的 Docker 容器.
        优先使用 docker-compose.yml，如果没有则直接使用 docker stop/rm 命令.

        Args:
            service_name: 服务名称或目录名
            remove_volumes: 是否删除挂载卷
            extra_args: 额外 compose 参数
        """
        resolved = self._resolve_service(service_name)
        if resolved is None:
            return False
        service_config, service_path = resolved

        # 直接使用 docker stop/rm 来停止容器，即便存在 docker-compose.yml 也不再依赖它
        # 这样与当前运行的容器（可能由 compose 启动）保持一致，通过容器名进行停止/删除
        return self._stop_container_directly(service_name, service_config, service_path, remove_volumes)

    def stop_api_server_docker(
        self,
        *,
        remove_volumes: bool = False,
        extra_args: Optional[List[str]] = None,
    ) -> bool:
        """
        停止 API Server 的 Docker 容器.
        """
        if not self.server_dir.exists():
            logger.error("未找到 API Server 目录: %s", self.server_dir)
            return False

        compose_cmd = self._get_docker_compose_command()
        if not compose_cmd:
            logger.error("无法停止 API Server：未找到 Docker Compose 命令")
            return False

        compose_file = self.server_dir / "docker-compose.yml"
        if not compose_file.exists():
            logger.error("API Server 缺少 docker-compose.yml 文件: %s", compose_file)
            return False

        # 先停止容器（内部会调用 docker stop）
        cmd = compose_cmd + ["-f", str(compose_file), "stop"]
        if extra_args:
            cmd.extend(extra_args)

        # 准备环境变量，清理无效的 DOCKER_HOST
        env = self._prepare_docker_env()
        
        logger.info("通过 Docker Compose 停止 API Server")
        try:
            result = subprocess.run(
                cmd,
                cwd=self.server_dir,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError as exc:
            logger.error("Docker Compose 未安装或不可用，无法停止 API Server: %s", exc)
            return False
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("停止 API Server Docker 容器时出现异常: %s", exc)
            return False

        if result.returncode != 0:
            stderr = result.stderr.strip()
            stdout = result.stdout.strip()
            logger.error(
                "Docker Compose 停止 API Server 失败 (exit=%s): %s",
                result.returncode,
                stderr or stdout,
            )
            return False

        if result.stdout:
            logger.debug("Docker Compose 输出 (api-server): %s", result.stdout.strip())
        if result.stderr:
            logger.debug("Docker Compose 错误输出 (api-server): %s", result.stderr.strip())

        logger.info("API Server 已通过 Docker Compose 停止",)

        # 如需删除容器和卷，额外执行 docker compose rm
        if remove_volumes:
            rm_cmd = compose_cmd + ["-f", str(compose_file), "rm", "-f", "-v"]
            if extra_args:
                rm_cmd.extend(extra_args)

            logger.info("删除 API Server 的容器和卷")
            try:
                rm_result = subprocess.run(
                    rm_cmd,
                    cwd=self.server_dir,
                    env=env,
                    capture_output=True,
                    text=True,
                    check=False,
                )
            except Exception as exc:  # pragma: no cover - defensive
                logger.error("删除 API Server 容器/卷时出现异常: %s", exc)
                return False

            if rm_result.returncode != 0:
                stderr = rm_result.stderr.strip()
                stdout = rm_result.stdout.strip()
                logger.error(
                    "删除 API Server 容器/卷失败 (exit=%s): %s",
                    rm_result.returncode,
                    stderr or stdout,
                )
                return False

            logger.info("API Server 的容器和卷已删除")

        return True
    
    def start_all_services(self, background: bool = True) -> Dict[str, Optional[subprocess.Popen]]:
        """
        启动所有服务
        
        Args:
            background: 是否在后台运行
        
        Returns:
            服务名称到进程对象的映射
        """
        # 确保已加载所有服务配置
        if not self.services:
            self.process_all_services(generate_docker=False)
        
        results = {}
        for service in self.services:
            service_name = service.get('name', service.get('service_dir'))
            process = self.start_service(service_name, background=background)
            results[service_name] = process
        
        return results
    
    def start_all_services_docker(
        self,
        *,
        build: bool = False,
        detach: bool = True,
        extra_args: Optional[List[str]] = None,
        include_server: bool = False,
    ) -> Dict[str, bool]:
        """
        通过 Docker Compose 启动所有服务

        Args:
            build: 是否在启动前构建镜像
            detach: 是否以后台模式运行
            extra_args: 额外的 compose 参数

        Returns:
            服务名称到启动结果的映射
        """
        if not self.services:
            self.process_all_services(generate_docker=False)

        results: Dict[str, bool] = {}
        for service in self.services:
            service_name = service.get("service_dir") or service.get("name")
            if not service_name:
                continue
            results[service_name] = self.start_service_docker(
                service_name,
                build=build,
                detach=detach,
                extra_args=extra_args,
            )
        if include_server:
            results["api-server"] = self.start_api_server_docker(
                build=build,
                detach=detach,
                extra_args=extra_args,
            )
        return results

    def stop_all_services_docker(
        self,
        *,
        remove_volumes: bool = False,
        extra_args: Optional[List[str]] = None,
        include_server: bool = False,
    ) -> Dict[str, bool]:
        """
        停止所有服务的 Docker 容器.

        Args:
            remove_volumes: 是否删除挂载卷
            extra_args: 额外 compose 参数
            include_server: 是否同时停止 API Server
        """
        if not self.services:
            self.process_all_services(generate_docker=False)

        results: Dict[str, bool] = {}
        for service in self.services:
            service_name = service.get("service_dir") or service.get("name")
            if not service_name:
                continue
            results[service_name] = self.stop_service_docker(
                service_name,
                remove_volumes=remove_volumes,
                extra_args=extra_args,
            )

        if include_server:
            results["api-server"] = self.stop_api_server_docker(
                remove_volumes=remove_volumes,
                extra_args=extra_args,
            )
        return results
    
    def stop_service(self, service_name: str, force: bool = False) -> bool:
        """
        停止单个服务
        
        Args:
            service_name: 服务名称
            force: 是否强制终止
        
        Returns:
            是否成功停止
        """
        # 确保已加载服务配置
        if not self.services:
            self.process_all_services(generate_docker=False)
        
        pid = None
        
        # 首先检查内部记录的进程
        if service_name in self.service_processes:
            process = self.service_processes[service_name]
            if process.poll() is None:  # 进程仍在运行
                pid = process.pid
            else:
                # 进程已停止，清理记录
                self._cleanup_service_state(service_name)
                logger.info(f"服务 {service_name} 已停止 (退出码: {process.returncode})")
                return True
        else:
            # 如果没有内部记录，尝试通过状态检测找到 PID
            status = self.get_service_status(service_name)
            if status.get('running') and status.get('pid'):
                pid = status['pid']
            else:
                logger.warning(f"服务 {service_name} 未在运行")
                return False
        
        # 通过 PID 停止进程
        if pid:
            try:
                if HAS_PSUTIL:
                    try:
                        proc = psutil.Process(pid)
                        if force:
                            proc.kill()
                        else:
                            proc.terminate()
                        
                        # 等待进程结束
                        try:
                            proc.wait(timeout=5)
                        except psutil.TimeoutExpired:
                            if not force:
                                logger.warning(f"服务 {service_name} 未在 5 秒内停止，尝试强制终止")
                            proc.kill()
                            proc.wait()
                        
                        logger.info(f"服务 {service_name} 已停止 (PID: {pid})")
                        
                        # 清理内部记录
                        self._cleanup_service_state(service_name)
                        
                        return True
                    except psutil.NoSuchProcess:
                        logger.info(f"服务 {service_name} 进程已不存在 (PID: {pid})")
                        self._cleanup_service_state(service_name)
                        return True
                    except psutil.AccessDenied:
                        logger.error(f"无权限停止服务 {service_name} (PID: {pid})")
                        return False
                else:
                    # 使用 os.kill 作为备选方案
                    try:
                        if force:
                            os.kill(pid, signal.SIGKILL)
                        else:
                            os.kill(pid, signal.SIGTERM)
                        
                        # 简单等待
                        import time
                        time.sleep(1)
                        
                        # 检查进程是否还存在
                        try:
                            os.kill(pid, 0)  # 检查进程是否存在
                            if force:
                                logger.warning(f"服务 {service_name} 未停止，已发送 SIGKILL")
                            else:
                                logger.warning(f"服务 {service_name} 未停止，尝试强制终止")
                                os.kill(pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass  # 进程已停止
                        
                        logger.info(f"服务 {service_name} 已停止 (PID: {pid})")
                        
                        # 清理内部记录
                        self._cleanup_service_state(service_name)
                        
                        return True
                    except ProcessLookupError:
                        logger.info(f"服务 {service_name} 进程已不存在 (PID: {pid})")
                        self._cleanup_service_state(service_name)
                        return True
                    except PermissionError:
                        logger.error(f"无权限停止服务 {service_name} (PID: {pid})")
                        return False
                        
            except Exception as e:
                logger.error(f"停止服务失败 {service_name}: {e}")
                return False
        
        return False
    
    def stop_all_services(self, force: bool = False) -> Dict[str, bool]:
        """
        停止所有服务
        
        Args:
            force: 是否强制终止
        
        Returns:
            服务名称到停止结果的映射
        """
        results = {}
        service_names = list(self.service_processes.keys())
        
        for service_name in service_names:
            results[service_name] = self.stop_service(service_name, force=force)
        
        return results
    
    def get_service_status(self, service_name: str) -> Dict[str, Any]:
        """
        获取服务状态
        
        Args:
            service_name: 服务名称
        
        Returns:
            服务状态信息
        """
        status = {
            'name': service_name,
            'running': False,
            'pid': None,
            'port': None,
            'port_in_use': False
        }
        
        # 获取服务配置
        service_config = self.get_service_config(service_name)
        if service_config:
            status['port'] = service_config.get('port')
            status['port_in_use'] = self._is_port_in_use(status['port']) if status['port'] else False
        
        # 检查进程状态（首先检查内部记录的进程）
        if service_name in self.service_processes:
            process = self.service_processes[service_name]
            if process.poll() is None:  # 进程仍在运行
                status['running'] = True
                status['pid'] = process.pid
            else:
                status['exit_code'] = process.returncode
        else:
            # 如果没有内部记录，尝试通过端口或进程名检测
            if status['port'] and status['port_in_use']:
                # 端口被占用，尝试找到对应的进程
                pid = self._find_process_by_port(status['port'])
                if pid:
                    status['running'] = True
                    status['pid'] = pid
                else:
                    # 端口被占用但找不到进程，仍然认为服务在运行
                    status['running'] = True
            else:
                # 尝试通过服务目录名查找进程
                service_path = None
                if service_config:
                    service_path = Path(service_config.get('service_path', ''))
                elif self.services_base_dir:
                    service_path = self.services_base_dir / service_name
                
                if service_path and service_path.exists():
                    pid = self._find_process_by_path(service_path)
                    if pid:
                        status['running'] = True
                        status['pid'] = pid

        if status['running']:
            status['status'] = "running"
            if status['pid']:
                status['message'] = f"进程 {status['pid']} 正在运行"
        elif status['port_in_use']:
            status['status'] = "unknown"
            status['message'] = f"端口 {status['port']} 被占用，但无法确认服务进程"
        else:
            status['status'] = "stopped"
            status['message'] = "服务未运行"
        
        return status
    
    def get_all_services_status(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有服务状态
        
        Returns:
            服务名称到状态信息的映射
        """
        # 确保已加载所有服务配置
        if not self.services:
            self.process_all_services(generate_docker=False)
        
        statuses = {}
        for service in self.services:
            service_name = service.get('name', service.get('service_dir'))
            statuses[service_name] = self.get_service_status(service_name)
        
        return statuses
    
    def _is_port_in_use(self, port: int) -> bool:
        """
        检查端口是否被占用
        
        Args:
            port: 端口号
        
        Returns:
            是否被占用
        """
        # 优先使用 psutil（如果可用）
        if HAS_PSUTIL:
            try:
                for conn in psutil.net_connections():
                    if conn.laddr.port == port:
                        return True
            except Exception:
                pass
        
        # 使用 socket 作为备选方案
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.1)
                result = s.connect_ex(('localhost', port))
                return result == 0
        except Exception:
            pass
        
        return False
    
    def _find_process_by_port(self, port: int) -> Optional[int]:
        """
        通过端口号查找进程 PID
        
        Args:
            port: 端口号
        
        Returns:
            进程 PID，如果未找到则返回 None
        """
        if HAS_PSUTIL:
            try:
                for conn in psutil.net_connections():
                    if conn.laddr.port == port and conn.pid:
                        return conn.pid
            except Exception:
                pass
        
        # 使用 lsof 作为备选方案（如果可用）
        try:
            result = subprocess.run(
                ['lsof', '-ti', f':{port}'],
                capture_output=True,
                text=True,
                timeout=1
            )
            if result.returncode == 0 and result.stdout.strip():
                return int(result.stdout.strip().split('\n')[0])
        except Exception:
            pass
        
        return None
    
    def _find_process_by_path(self, service_path: Path) -> Optional[int]:
        """
        通过服务路径查找进程 PID
        
        Args:
            service_path: 服务路径
        
        Returns:
            进程 PID，如果未找到则返回 None
        """
        if HAS_PSUTIL:
            try:
                service_path_str = str(service_path.resolve())
                for proc in psutil.process_iter(['pid', 'cwd', 'cmdline']):
                    try:
                        info = proc.info
                        cmdline = info.get('cmdline', [])
                        cwd = info.get('cwd', '')
                        
                        # 检查进程的工作目录或命令行是否包含服务路径
                        if (service_path_str in cwd or 
                            any(service_path_str in str(cmd) for cmd in cmdline)):
                            # 进一步检查是否是 main.py
                            if any('main.py' in str(cmd) for cmd in cmdline):
                                return info['pid']
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
            except Exception:
                pass
        
        return None
    
    def _get_process_listening_port(self, pid: int) -> Optional[int]:
        """
        获取进程监听的端口号
        
        Args:
            pid: 进程 PID
        
        Returns:
            端口号，如果未找到则返回 None
        """
        if HAS_PSUTIL:
            try:
                proc = psutil.Process(pid)
                for conn in proc.connections(kind='inet'):
                    if conn.status == psutil.CONN_LISTEN and conn.laddr:
                        return conn.laddr.port
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
            except Exception:
                pass
        
        # 使用 lsof 作为备选方案
        try:
            result = subprocess.run(
                ['lsof', '-Pan', '-p', str(pid), '-iTCP', '-sTCP:LISTEN'],
                capture_output=True,
                text=True,
                timeout=1
            )
            if result.returncode == 0 and result.stdout.strip():
                # 解析 lsof 输出，提取端口号
                for line in result.stdout.strip().split('\n')[1:]:  # 跳过标题行
                    parts = line.split()
                    if len(parts) >= 9:
                        # lsof 输出格式: COMMAND PID USER FD TYPE DEVICE SIZE/OFF NODE NAME
                        # NAME 字段格式: localhost:PORT
                        name = parts[-1]
                        if ':' in name:
                            try:
                                port_str = name.split(':')[-1]
                                return int(port_str)
                            except ValueError:
                                continue
        except Exception:
            pass
        
        return None
    
    def sync_port_from_running_service(
        self,
        service_name: str,
        force: bool = False
    ) -> Optional[int]:
        """
        从运行中的服务获取实际端口并同步到 service_config.json
        
        Args:
            service_name: 服务名称
            force: 是否强制同步（即使端口已分配也更新）
        
        Returns:
            同步的端口号，如果失败返回 None
        """
        resolved = self._resolve_service(service_name)
        if resolved is None:
            logger.warning(f"无法解析服务: {service_name}")
            return None
        
        service_config, service_path = resolved
        
        # 获取服务进程 PID
        pid = None
        if service_name in self.service_processes:
            process = self.service_processes[service_name]
            if process.poll() is None:  # 进程仍在运行
                pid = process.pid
        else:
            # 尝试通过端口或路径查找进程
            current_port = service_config.get('port')
            if current_port:
                pid = self._find_process_by_port(current_port)
            
            if not pid:
                pid = self._find_process_by_path(service_path)
        
        if not pid:
            logger.warning(f"无法找到服务 {service_name} 的运行进程")
            return None
        
        # 获取进程实际监听的端口
        actual_port = self._get_process_listening_port(pid)
        if not actual_port:
            logger.warning(f"无法获取服务 {service_name} (PID: {pid}) 的监听端口")
            return None
        
        # 检查是否需要同步
        current_port = service_config.get('port')
        assigned_port = self._assigned_ports.get(service_name)
        
        if actual_port == current_port and actual_port == assigned_port:
            logger.debug(f"服务 {service_name} 端口已同步 (端口: {actual_port})")
            return actual_port
        
        # 同步端口
        logger.info(
            f"同步服务 {service_name} 端口: {current_port} -> {actual_port} (PID: {pid})"
        )
        
        # 更新分配的端口
        self._assigned_ports[service_name] = actual_port
        
        # 更新 service_config.json
        self._update_service_port_config(service_name, service_config, service_path, actual_port)
        
        return actual_port
    
    def sync_all_running_services_ports(self, force: bool = False) -> Dict[str, Optional[int]]:
        """
        同步所有运行中服务的端口到 service_config.json
        
        Args:
            force: 是否强制同步
        
        Returns:
            服务名称到端口号的映射
        """
        results = {}
        
        # 确保已加载所有服务配置
        if not self.services:
            self.process_all_services(generate_docker=False)
        
        for service in self.services:
            service_name = service.get('name', service.get('service_dir'))
            if not service_name:
                continue
            
            results[service_name] = self.sync_port_from_running_service(service_name, force=force)
        
        return results
    
    def get_container_logs(
        self,
        service_name: str,
        tail: int = 100,
        follow: bool = False,
        since: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        获取 Docker 容器的日志
        
        Args:
            service_name: 服务名称
            tail: 返回最后 N 行日志（默认 100）
            follow: 是否持续跟踪日志（类似 tail -f）
            since: 只显示指定时间之后的日志（格式：2023-01-01T00:00:00 或 30m）
        
        Returns:
            包含日志内容和元数据的字典
        """
        docker_path = shutil.which("docker")
        if not docker_path:
            return {
                "success": False,
                "error": "未找到 docker 命令",
                "logs": ""
            }
        
        # 获取服务配置
        service_config = self.get_service_config(service_name)
        if not service_config:
            return {
                "success": False,
                "error": f"未找到服务配置: {service_name}",
                "logs": ""
            }
        
        # 获取容器名称
        service_path = Path(service_config.get('service_path', ''))
        if not service_path.exists():
            return {
                "success": False,
                "error": f"服务路径不存在: {service_path}",
                "logs": ""
            }
        
        compose_file = service_path / "docker-compose.yml"
        container_name = None
        if compose_file.exists():
            container_name = self._get_container_name_from_compose(compose_file, service_name)
        else:
            # 如果没有 docker-compose.yml，使用服务名称作为容器名
            container_name = service_name
        
        # 检查容器是否存在
        try:
            check_result = subprocess.run(
                [docker_path, "ps", "-a", "--filter", f"name=^{container_name}$", "--format", "{{.Names}}"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            if container_name not in check_result.stdout:
                return {
                    "success": False,
                    "error": f"容器 {container_name} 不存在",
                    "logs": "",
                    "container_name": container_name
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"检查容器状态时出错: {e}",
                "logs": "",
                "container_name": container_name
            }
        
        # 构建 docker logs 命令
        cmd = [docker_path, "logs"]
        
        if tail > 0:
            cmd.extend(["--tail", str(tail)])
        
        if since:
            cmd.extend(["--since", since])
        
        if follow:
            cmd.append("--follow")
        
        cmd.append(container_name)
        
        try:
            if follow:
                # 如果 follow=True，返回一个生成器（但这里我们只返回初始日志）
                # 实际应用中，follow 模式应该使用 WebSocket 或 Server-Sent Events
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=5,  # follow 模式下只读取 5 秒
                )
            else:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=10,
                )
            
            if result.returncode == 0:
                return {
                    "success": True,
                    "logs": result.stdout,
                    "container_name": container_name,
                    "service_name": service_name,
                    "tail": tail,
                    "follow": follow
                }
            else:
                return {
                    "success": False,
                    "error": result.stderr or "获取日志失败",
                    "logs": result.stdout,
                    "container_name": container_name
                }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "获取日志超时",
                "logs": "",
                "container_name": container_name
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"获取日志时出现异常: {e}",
                "logs": "",
                "container_name": container_name
            }
