"""
数据分析工具：使用 PythonREPL 生成并执行代码分析数据文件。

该工具基于 langgraph 框架实现，独立于旧工具。
"""

from __future__ import annotations

import json
from typing import Any

from textmsa.logging_config import get_logger
from textmsa.services.agent.llm_client import LLMClient, LLMRequest
from textmsa.services.file.file_service import get_file_service
from textmsa.services.analysis.tools.file_reader_tool import FileReaderTool
from textmsa.services.data.mongodb_models import FileInfo, file_info_from_dict
from textmsa.settings import get_codegen_llm_config

logger = get_logger(__name__)

# 尝试导入 PythonREPL
try:
    from langchain_experimental.utilities import PythonREPL
except ImportError:
    PythonREPL = None  # type: ignore
    logger.warning("PythonREPL not available. Please install langchain-experimental.")


class DataAnalysisTool:
    """
    数据分析工具，使用 PythonREPL 生成并执行代码分析数据文件
    
    注意：不使用 try-catch，异常直接向上抛出。
    """

    def __init__(
        self,
        *,
        llm_client: LLMClient | None = None,
        python_repl: Any | None = None,
        max_code_length: int = 10000,
        execution_timeout: int = 300,
    ) -> None:
        """
        初始化数据分析工具
        
        Args:
            llm_client: LLM 客户端，用于生成代码
            python_repl: PythonREPL 实例，如果为 None 则自动创建
            max_code_length: 最大代码长度限制
            execution_timeout: 代码执行超时时间（秒）
        """
        if llm_client is None:
            llm_config = get_codegen_llm_config()
            self._llm_client = LLMClient(config=llm_config)
        else:
            self._llm_client = llm_client
        
        self._max_code_length = max_code_length
        self._execution_timeout = execution_timeout
        self._file_service = get_file_service()
        self._file_reader = FileReaderTool()

        # 初始化 PythonREPL
        if python_repl is not None:
            self._python_repl = python_repl
        elif PythonREPL is not None:
            self._python_repl = PythonREPL()
        else:
            raise ImportError(
                "PythonREPL is not available. Please install langchain-experimental or langchain."
            )

        logger.info(
            "DataAnalysisTool initialized",
            extra={
                "max_code_length": max_code_length,
                "execution_timeout": execution_timeout,
            },
        )

    def analyze(
        self,
        *,
        question: str,
        file_id: str | None = None,
        user_id: str | None = None,
        language: str = "zh",
    ) -> str:
        """
        分析数据文件并返回分析结果
        
        Args:
            question: 用户问题或分析要求
            file_info: 文件信息（字典或 FileInfo 对象），如果提供则直接使用
            file_id: 文件ID（如果 file_info 未提供，则通过 file_id 获取）
            user_id: 用户ID（如果 file_id 提供，则必须提供 user_id）
        
        Returns:
            分析结果字符串
            
        Raises:
            Exception: 如果分析失败，直接抛出异常（不捕获）
        """

        # 通过 file_service 获取 FileInfo
        file_info_dict = self._file_service.get_file_info(file_id, user_id)

        
        # 构建 prompt
        prompt = self._build_prompt(
            question=question,
            file_info=file_info_dict,
            language=language,
        )
        
        # 生成代码
        llm_response = self._generate_code(prompt=prompt)
        
        # 提取代码
        extracted_code = self._extract_code(llm_response=llm_response)
        
        if not extracted_code:
            raise ValueError("无法从 LLM 响应中提取代码")
        
        # 执行代码
        execution_result = self._run_code(code=extracted_code)
        
        if not execution_result["success"]:
            error_msg = execution_result.get("error", "未知错误")
            raise RuntimeError(f"代码执行失败: {error_msg}")
        
        # 返回执行结果
        stdout = execution_result.get("stdout", "")
        stderr = execution_result.get("stderr", "")
        
        if stderr:
            return f"{stdout}\n\n警告：{stderr}"
        return stdout

    def _build_prompt(
        self,
        *,
        question: str,
        file_info: dict[str, Any],
        language: str = "zh",
    ) -> str:
        """
        构建代码生成的 prompt
        
        Args:
            question: 用户问题
            file_info: 文件信息字典
            language: 语言代码，默认为中文（"zh"）
        
        Returns:
            prompt 字符串
        """
        file_path = file_info.get("file_path")
        file_type = file_info.get("file_type_name") or file_info.get("file_type")
        filename = file_info.get("filename")
        
        # 尝试读取文件预览
        file_preview = None
        if file_path:
            try:
                file_preview = self._file_reader._read_preview(
                    file_path=file_path,
                    file_type=file_type or "unknown",
                    filename=filename or "unknown",
                )
            except Exception:
                pass
        
        # 构建 prompt
        prompt_parts = [
            "你是一个专业的 Python 数据分析助手。请根据以下信息生成 Python 代码。",
            "",
            "任务描述：",
            question,
            "",
        ]
        
        if file_path:
            prompt_parts.extend([
                "数据信息：",
                f"- 文件路径：{file_path}",
            ])
            if file_type:
                prompt_parts.append(f"- 文件类型：{file_type}")
            if filename:
                prompt_parts.append(f"- 文件名：{filename}")
            prompt_parts.append("")
            
            # 添加文件预览
            if file_preview:
                prompt_parts.append("文件预览：")
                prompt_parts.append(json.dumps(file_preview, ensure_ascii=False, indent=2))
                prompt_parts.append("")
        
        # 添加数据读取代码示例
        if file_path and file_type:
            prompt_parts.extend([
                "数据读取代码示例：",
                "",
            ])
            
            if file_type == "csv":
                prompt_parts.extend([
                    "import pandas as pd",
                    f"df = pd.read_csv('{file_path}')",
                    "print(df.head())",
                    "print(df.info())",
                    "",
                ])
            elif file_type == "excel":
                prompt_parts.extend([
                    "import pandas as pd",
                    f"df = pd.read_excel('{file_path}')",
                    "print(df.head())",
                    "print(df.info())",
                    "",
                ])
            elif file_type == "h5ad":
                prompt_parts.extend([
                    "import anndata as ad",
                    f"adata = ad.read_h5ad('{file_path}')",
                    "print(adata.shape)",
                    "print(adata.obs.head())",
                    "",
                ])
        
        # 添加要求和格式约束
        prompt_parts.extend([
            "要求：",
            "1. 读取数据文件，使用 pandas（或 anndata 处理 h5ad）完成必要的加载与预处理。",
            "2. 依据任务描述执行分析，充分利用上方“文件预览”中的字段/列名/示例值，避免胡乱猜测。",
            "3. 生成清晰的 Markdown 结构化输出字符串，并用 print() 输出。推荐结构：",
            "   - # 分析概览",
            "   - ## 数据预览（可展示 head()/shape/列信息）",
            "   - ## 主要发现 / 统计结果（表格可用 DataFrame.to_markdown()）",
            "4. 所有 stdout 必须是 Markdown 文本，避免杂乱输出；如有警告/异常需在 Markdown 中说明。",
            "5. 不要写入源数据文件；如需输出文件，仅写入当前目录的临时文件并在 Markdown 中引用。",
            "",
            "请生成完整、可执行的 Python 代码。",
            "必须以 JSON 格式返回代码，格式如下：",
            "",
            '{"code": "你的 Python 代码"}',
            "",
            "只返回 JSON 格式，不要包含其他说明文字。",
        ])
        
        return "\n".join(prompt_parts)

    def _generate_code(
        self,
        *,
        prompt: str,
        temperature: float = 0.2,
    ) -> str:
        """
        使用 LLM 生成 Python 代码
        
        Args:
            prompt: 代码生成 prompt
            temperature: LLM 温度参数
        
        Returns:
            LLM 的原始响应
        """
        request = LLMRequest(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是一个专业的 Python 数据分析代码生成助手。"
                        "你的任务是生成完整、可执行的 Python 代码来处理数据分析和数据读取任务。"
                        '必须以 JSON 格式返回代码，格式为：{"code": "你的 Python 代码"}'
                        "只返回 JSON 格式，不要包含其他说明文字。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
            max_tokens=5000,
        )
        
        response = self._llm_client.chat(request)
        return response.content.strip()

    def _extract_code(self, llm_response: str) -> str:
        """
        从 LLM 响应中提取 Python 代码
        
        支持 JSON 格式：{"code": "..."}
        
        Args:
            llm_response: LLM 的响应文本
        
        Returns:
            提取出的 Python 代码
        """
        if not llm_response:
            return ""
        
        # 清理响应
        text = llm_response.strip()
        
        # 移除 markdown 代码块标记
        import re
        text = re.sub(r'^```json\s*\n', '', text, flags=re.MULTILINE)
        text = re.sub(r'^```\s*$', '', text, flags=re.MULTILINE)
        text = text.strip()
        
        # 尝试解析 JSON
        try:
            data = json.loads(text)
            if isinstance(data, dict) and "code" in data:
                code = data["code"]
                if isinstance(code, str):
                    return code.strip()
        except json.JSONDecodeError:
            pass
        
        # 尝试提取 JSON 对象
        brace_count = 0
        start_idx = -1
        for i, char in enumerate(text):
            if char == '{':
                if start_idx == -1:
                    start_idx = i
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0 and start_idx != -1:
                    json_str = text[start_idx:i+1]
                    try:
                        data = json.loads(json_str)
                        if isinstance(data, dict) and "code" in data:
                            code = data["code"]
                            if isinstance(code, str):
                                return code.strip()
                    except json.JSONDecodeError:
                        pass
                    start_idx = -1
        
        return ""

    def _run_code(self, code: str) -> dict[str, Any]:
        """
        使用 PythonREPL 执行代码
        
        Args:
            code: 要执行的 Python 代码
        
        Returns:
            执行结果字典
        """
        if not code:
            return {
                "success": False,
                "error": "代码为空",
                "stdout": "",
                "stderr": "",
            }
        
        # 检查代码长度
        if len(code) > self._max_code_length:
            return {
                "success": False,
                "error": f"代码长度超过限制 ({len(code)} > {self._max_code_length})",
                "stdout": "",
                "stderr": "",
            }
        
        # 执行代码
        try:
            result = self._python_repl.run(code)
            stdout = result if isinstance(result, str) else str(result)
            
            return {
                "success": True,
                "stdout": stdout,
                "stderr": "",
            }
        except Exception as exc:
            return {
                "success": False,
                "error": str(exc),
                "stdout": "",
                "stderr": str(exc),
            }


__all__ = ["DataAnalysisTool"]

