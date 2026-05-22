"""
代码执行器
支持Python、R等多语言的代码执行
支持conda环境管理
"""
import os
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import time

from textmsa.logging_config import get_logger
from textmsa.services.data.mongodb_models import (
    SupportedLanguage,
    ExecutionEnvironment,
    CodegenStatus
)

logger = get_logger(__name__)


class CodegenExecutor:
    """代码执行器，支持多种语言的代码执行"""
    
    def __init__(self, work_dir: Optional[str] = None):
        """
        初始化代码执行器
        
        Args:
            work_dir: 工作目录（可选，默认使用临时目录）
        """
        if work_dir:
            self.work_dir = Path(work_dir)
            self.work_dir.mkdir(parents=True, exist_ok=True)
        else:
            self.work_dir = Path(tempfile.mkdtemp(prefix="codegen_exec_"))
        
        logger.info(f"CodegenExecutor初始化完成，工作目录: {self.work_dir}")
    
    def execute_code(
        self,
        code: str,
        language: SupportedLanguage,
        environment: Optional[ExecutionEnvironment] = None,
        input_file_path: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        timeout: int = 3600
    ) -> Dict[str, Any]:
        """
        执行代码
        
        Args:
            code: 要执行的代码
            language: 编程语言
            environment: 执行环境配置
            input_file_path: 输入文件路径
            parameters: 执行参数
            timeout: 超时时间（秒）
        
        Returns:
            执行结果字典，包含：
            - status: 执行状态（success/failed）
            - output: 标准输出
            - error: 错误输出
            - output_files: 输出文件列表
            - execution_time: 执行时间（秒）
        """
        logger.info(f"开始执行代码，语言: {language.value}")
        start_time = time.time()
        
        try:
            # 准备执行环境
            env_vars = self._prepare_environment(environment)
            
            # 根据语言选择执行方法
            if language == SupportedLanguage.PYTHON:
                result = self._execute_python(code, env_vars, input_file_path, parameters, timeout)
            elif language == SupportedLanguage.R:
                result = self._execute_r(code, env_vars, input_file_path, parameters, timeout)
            elif language == SupportedLanguage.JULIA:
                result = self._execute_julia(code, env_vars, input_file_path, parameters, timeout)
            elif language == SupportedLanguage.BASH:
                result = self._execute_bash(code, env_vars, input_file_path, parameters, timeout)
            else:
                raise ValueError(f"不支持的语言: {language.value}")
            
            execution_time = time.time() - start_time
            result['execution_time'] = execution_time
            result['status'] = 'success' if result.get('exit_code', 1) == 0 else 'failed'
            
            logger.info(f"代码执行完成，状态: {result['status']}, 耗时: {execution_time:.2f}秒")
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"代码执行失败: {e}", exc_info=True)
            return {
                'status': 'failed',
                'error': str(e),
                'output': '',
                'output_files': [],
                'execution_time': execution_time,
                'exit_code': 1
            }
    
    def _prepare_environment(self, environment: Optional[ExecutionEnvironment]) -> Dict[str, str]:
        """准备执行环境"""
        env_vars = os.environ.copy()
        
        if environment:
            # 如果指定了conda环境，激活conda环境
            if environment.conda_env:
                conda_path = self._find_conda()
                if conda_path:
                    # 设置conda环境路径
                    env_prefix = self._get_conda_env_path(environment.conda_env)
                    if env_prefix:
                        # 更新PATH
                        env_vars['PATH'] = f"{env_prefix}/bin:{env_vars.get('PATH', '')}"
                        # 设置其他环境变量
                        env_vars['CONDA_DEFAULT_ENV'] = environment.conda_env
                        env_vars['CONDA_PREFIX'] = env_prefix
        
        return env_vars
    
    def _find_conda(self) -> Optional[str]:
        """查找conda可执行文件路径"""
        # 尝试常见的conda路径
        conda_paths = [
            shutil.which('conda'),
            os.path.expanduser('~/anaconda3/bin/conda'),
            os.path.expanduser('~/miniconda3/bin/conda'),
            '/opt/conda/bin/conda',
            '/usr/local/bin/conda'
        ]
        
        for path in conda_paths:
            if path and os.path.exists(path):
                return path
        
        return None
    
    def _get_conda_env_path(self, env_name: str) -> Optional[str]:
        """获取conda环境路径"""
        conda_path = self._find_conda()
        if not conda_path:
            return None
        
        # 尝试获取环境路径
        try:
            result = subprocess.run(
                [conda_path, 'env', 'list', '--json'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                import json
                envs_data = json.loads(result.stdout)
                for env in envs_data.get('envs', []):
                    if env_name in env or os.path.basename(env) == env_name:
                        return env
        except Exception as e:
            logger.warning(f"获取conda环境路径失败: {e}")
        
        # 尝试默认路径
        default_paths = [
            os.path.expanduser(f'~/anaconda3/envs/{env_name}'),
            os.path.expanduser(f'~/miniconda3/envs/{env_name}'),
            f'/opt/conda/envs/{env_name}'
        ]
        
        for path in default_paths:
            if os.path.exists(path):
                return path
        
        return None
    
    def _execute_python(
        self,
        code: str,
        env_vars: Dict[str, str],
        input_file_path: Optional[str],
        parameters: Optional[Dict[str, Any]],
        timeout: int
    ) -> Dict[str, Any]:
        """执行Python代码"""
        # 创建临时脚本文件
        script_file = self.work_dir / "script.py"
        with open(script_file, 'w', encoding='utf-8') as f:
            f.write(code)
        
        # 准备命令
        python_cmd = self._get_python_command(env_vars)
        cmd = [python_cmd, str(script_file)]
        
        # 添加输入文件参数
        if input_file_path:
            cmd.append(input_file_path)
        
        # 添加其他参数
        if parameters:
            for key, value in parameters.items():
                cmd.extend([f"--{key}", str(value)])
        
        # 执行命令
        return self._run_command(cmd, env_vars, timeout)
    
    def _execute_r(
        self,
        code: str,
        env_vars: Dict[str, str],
        input_file_path: Optional[str],
        parameters: Optional[Dict[str, Any]],
        timeout: int
    ) -> Dict[str, Any]:
        """执行R代码"""
        # 创建临时脚本文件
        script_file = self.work_dir / "script.R"
        with open(script_file, 'w', encoding='utf-8') as f:
            f.write(code)
        
        # 准备命令
        r_cmd = self._get_r_command(env_vars)
        cmd = [r_cmd, '--vanilla', '--slave', '-f', str(script_file)]
        
        # 添加输入文件参数（通过环境变量传递）
        if input_file_path:
            env_vars['INPUT_FILE'] = input_file_path
        
        # 执行命令
        return self._run_command(cmd, env_vars, timeout)
    
    def _execute_julia(
        self,
        code: str,
        env_vars: Dict[str, str],
        input_file_path: Optional[str],
        parameters: Optional[Dict[str, Any]],
        timeout: int
    ) -> Dict[str, Any]:
        """执行Julia代码"""
        # 创建临时脚本文件
        script_file = self.work_dir / "script.jl"
        with open(script_file, 'w', encoding='utf-8') as f:
            f.write(code)
        
        # 准备命令
        julia_cmd = shutil.which('julia') or 'julia'
        cmd = [julia_cmd, str(script_file)]
        
        # 添加输入文件参数
        if input_file_path:
            cmd.append(input_file_path)
        
        # 执行命令
        return self._run_command(cmd, env_vars, timeout)
    
    def _execute_bash(
        self,
        code: str,
        env_vars: Dict[str, str],
        input_file_path: Optional[str],
        parameters: Optional[Dict[str, Any]],
        timeout: int
    ) -> Dict[str, Any]:
        """执行Bash脚本"""
        # 创建临时脚本文件
        script_file = self.work_dir / "script.sh"
        with open(script_file, 'w', encoding='utf-8') as f:
            f.write("#!/bin/bash\n")
            f.write(code)
        
        # 添加执行权限
        os.chmod(script_file, 0o755)
        
        # 准备命令
        cmd = ['bash', str(script_file)]
        
        # 添加输入文件参数
        if input_file_path:
            cmd.append(input_file_path)
        
        # 执行命令
        return self._run_command(cmd, env_vars, timeout)
    
    def _get_python_command(self, env_vars: Dict[str, str]) -> str:
        """获取Python命令路径"""
        # 如果设置了CONDA_PREFIX，使用conda环境的python
        if 'CONDA_PREFIX' in env_vars:
            python_path = Path(env_vars['CONDA_PREFIX']) / 'bin' / 'python'
            if python_path.exists():
                return str(python_path)
        
        # 否则使用系统python
        return shutil.which('python3') or shutil.which('python') or 'python'
    
    def _get_r_command(self, env_vars: Dict[str, str]) -> str:
        """获取R命令路径"""
        # 如果设置了CONDA_PREFIX，使用conda环境的R
        if 'CONDA_PREFIX' in env_vars:
            r_path = Path(env_vars['CONDA_PREFIX']) / 'bin' / 'R'
            if r_path.exists():
                return str(r_path)
        
        # 否则使用系统R
        return shutil.which('R') or 'R'
    
    def _run_command(
        self,
        cmd: List[str],
        env_vars: Dict[str, str],
        timeout: int
    ) -> Dict[str, Any]:
        """运行命令"""
        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.work_dir),
                env=env_vars,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            # 查找输出文件
            output_files = []
            for file_path in self.work_dir.glob('*'):
                if file_path.is_file() and file_path.name != 'script.py' and file_path.name != 'script.R' and file_path.name != 'script.jl' and file_path.name != 'script.sh':
                    output_files.append(str(file_path))
            
            return {
                'exit_code': result.returncode,
                'output': result.stdout,
                'error': result.stderr,
                'output_files': output_files
            }
            
        except subprocess.TimeoutExpired:
            logger.error(f"命令执行超时: {cmd}")
            return {
                'exit_code': 124,
                'output': '',
                'error': f'执行超时（超过{timeout}秒）',
                'output_files': []
            }
        except Exception as e:
            logger.error(f"命令执行失败: {e}", exc_info=True)
            return {
                'exit_code': 1,
                'output': '',
                'error': str(e),
                'output_files': []
            }
    
    def cleanup(self):
        """清理工作目录"""
        try:
            if self.work_dir.exists() and self.work_dir.is_dir():
                shutil.rmtree(self.work_dir)
                logger.info(f"工作目录已清理: {self.work_dir}")
        except Exception as e:
            logger.warning(f"清理工作目录失败: {e}")

