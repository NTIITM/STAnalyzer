"""
PythonREPL 工具：基于 langchain PythonREPL 的代码生成和执行工具。

支持多步骤流程：
1. 构建 prompt 语境
2. 生成 Python 代码
3. 抽取代码
4. 执行代码
5. 返回结果
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any

from textmsa.logging_config import get_logger
from textmsa.services.agent.langgraph.state import GraphState
from textmsa.services.agent.llm_client import LLMClient, LLMRequest
from textmsa.services.data.mongodb_models import FileInfo
from textmsa.services.agent.tools.file_reader_tool import FileReaderTool

logger = get_logger(__name__)

# 尝试导入 PythonREPL
try:
    from langchain_experimental.utilities import PythonREPL
except ImportError:  # pragma: no cover - 依赖缺失时的兜底日志
    PythonREPL = None  # type: ignore
    logger.warning("PythonREPL not available. Please install langchain-experimental.")


@dataclass
class PythonREPLExecutionResult:
    """代码执行结果"""

    stdout: str
    stderr: str
    execution_time: float
    success: bool
    error: Exception | None = None


@dataclass
class PythonREPLResult:
    """PythonREPL 工具执行结果"""

    # 执行状态
    success: bool
    error_message: str | None = None

    # 代码信息
    generated_code: str = ""
    extracted_code: str = ""

    # 执行结果
    stdout: str = ""
    stderr: str = ""
    execution_time: float = 0.0  # 秒



class PythonREPLTool:
    """
    基于 langchain PythonREPL 的代码生成和执行工具

    支持多步骤流程：
    1. 构建 prompt 语境
    2. 生成 Python 代码
    3. 抽取代码
    4. 执行代码
    5. 返回结果
    """

    # 危险操作模式（用于安全检查）
    DANGEROUS_PATTERNS = [
        r"os\\.system\\s*\\(",
        r"subprocess\\.",
        r"__import__\\s*\\(",
        r"eval\\s*\\(",
        r"exec\\s*\\(",
        r"open\\s*\\([^)]*['\"]w['\"]",  # 写文件操作（需要更严格的检查）
    ]

    def __init__(
        self,
        *,
        llm_client: LLMClient | None = None,
        python_repl: Any | None = None,
        max_code_length: int = 10000,
        execution_timeout: int = 300,
    ) -> None:
        """
        初始化工具

        Args:
            llm_client: LLM 客户端，用于生成代码
            python_repl: PythonREPL 实例，如果为 None 则自动创建
            max_code_length: 最大代码长度限制
            execution_timeout: 代码执行超时时间（秒）
        """
        self._llm_client = llm_client
        self._max_code_length = max_code_length
        self._execution_timeout = execution_timeout
        self._exec_globals: dict[str, Any] = {}

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
            "PythonREPLTool initialized",
            extra={
                "max_code_length": max_code_length,
                "execution_timeout": execution_timeout,
            },
        )

    def execute(
        self,
        *,
        question: str,
        file_info: FileInfo | None = None,
    ) -> PythonREPLResult:
        """
        执行完整流程：生成代码 -> 执行代码 -> 返回结果

        Args:
            question: 用户问题或任务描述
            file_info: 文件信息，包含文件路径、数据内容等

        Returns:
            PythonREPLResult: 包含执行结果、代码、输出等
        """
        logger.info(
            "Starting PythonREPL execution",
            extra={"question_length": len(question)},
        )

        try:
            # 步骤1: 构建 prompt
            prompt = self.build_prompt(
                question=question,
                file_info=file_info,
            )

            # 步骤2: 生成代码
            llm_response = self.generate_code(prompt=prompt)

            # 步骤3: 抽取代码
            extracted_code = self.extract_code(llm_response=llm_response)
            
            logger.info(
                "Code extracted",
                extra={
                    "extracted_code_length": len(extracted_code),
                    "extracted_code_preview": extracted_code[:200] if extracted_code else "",
                },
            )

            if not extracted_code:
                logger.warning("Failed to extract code from LLM response")
                return PythonREPLResult(
                    success=False,
                    error_message="无法从 LLM 响应中提取代码",
                    generated_code=llm_response,
                    extracted_code="",
                )

            # 步骤4: 执行代码
            execution_result = self.run_code(code=extracted_code)

            # 记录最终执行结果
            logger.info(
                "PythonREPL execution completed",
                extra={
                    "success": execution_result.success,
                    "execution_time": execution_result.execution_time,
                    "stdout_length": len(execution_result.stdout),
                    "stderr_length": len(execution_result.stderr),
                },
            )
            if execution_result.stdout:
                logger.info("Final execution output", extra={"stdout": execution_result.stdout})
            if execution_result.stderr:
                logger.warning("Final execution errors", extra={"stderr": execution_result.stderr})

            # 将 PythonREPLExecutionResult 转换为 PythonREPLResult
            return PythonREPLResult(
                success=execution_result.success,
                error_message=str(execution_result.error) if execution_result.error else None,
                generated_code=llm_response,
                extracted_code=extracted_code,
                stdout=execution_result.stdout,
                stderr=execution_result.stderr,
                execution_time=execution_result.execution_time,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("PythonREPL execution failed", exc_info=True)
            return PythonREPLResult(
                success=False,
                error_message=f"代码执行失败: {str(exc)}",
                generated_code="",
                extracted_code="",
            )
    def build_prompt(
        self,
        *,
        question: str,
        data: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        state: GraphState | None = None,
        file_info: FileInfo | dict[str, Any] | None = None,
    ) -> str:
        """
        构建代码生成的 prompt

        Args:
            question: 用户问题
            data: 数据信息
            context: 上下文信息
            state: GraphState
            file_info: FileInfo 对象或字典（data 的等价替代，为方便调用）

        Returns:
            构建好的 prompt 字符串
        """
        # file_info 兼容：如果 data 为空，则尝试从 file_info 提取
        if file_info and not data:
            if isinstance(file_info, dict):
                data = file_info
            elif hasattr(file_info, "model_dump"):
                data = file_info.model_dump()
            elif hasattr(file_info, "dict"):
                data = file_info.dict()  # type: ignore[assignment]

        # 收集文件信息
        file_path = None
        file_type = None
        filename = None
        if data:
            file_path = data.get("file_path")
            file_type = data.get("file_type") or data.get("file_type_name")
            filename = data.get("filename")
        elif state:
            file_path = state.get("selected_file_path")
            # 从文件路径推断类型
            if file_path:
                file_type = FileReaderTool.get_file_type_from_path(file_path)
                # 从路径提取文件名
                filename = os.path.basename(file_path)

        # 如果没有从 data 或 state 获取到文件类型，从文件路径推断
        if file_path and not file_type:
            file_type = FileReaderTool.get_file_type_from_path(file_path)

        # 收集上下文信息
        evidence_summary = ""
        if context:
            evidence_summary = context.get("evidence_summary", "")
        elif state:
            evidence_summary = state.get("evidence_summary", "")

        # 尝试读取文件预览
        file_preview = None
        if file_path:
            try:
                if os.path.exists(file_path):
                    # 创建 FileReaderTool 实例来读取预览
                    file_reader = FileReaderTool(max_csv_rows=5, max_text_bytes=1000)
                    # 使用公共方法读取预览
                    file_preview = file_reader.read_preview_by_path(
                        file_path=file_path,
                        file_type=file_type,
                        filename=filename,
                    )
            except Exception as e:  # noqa: BLE001
                logger.warning(f"读取文件预览失败: {e}", exc_info=True)
                file_preview = None

        # 构建 prompt
        prompt_parts = [
            "你是一个专业的 Python 数据分析助手。请根据以下信息生成 Python 代码。",
            "",
            "任务描述：",
            question,
            "",
        ]

        # 添加数据信息
        if file_path:
            prompt_parts.extend(
                [
                    "数据信息：",
                    f"- 文件路径：{file_path}",
                ],
            )
            if file_type:
                prompt_parts.append(f"- 文件类型：{file_type}")
            if filename:
                prompt_parts.append(f"- 文件名：{filename}")
            prompt_parts.append("")

            # 添加文件预览信息
            if file_preview:
                prompt_parts.append("文件预览：")
                # 使用 FileReaderTool 格式化预览信息（使用详细格式）
                file_reader = FileReaderTool()
                preview_text = file_reader.format_preview(file_preview, style="detailed")
                if preview_text:
                    prompt_parts.append(preview_text)
                    prompt_parts.append("")

        # 添加上下文信息
        if evidence_summary:
            prompt_parts.extend(
                [
                    "上下文信息：",
                    f"- 知识摘要：{evidence_summary}",
                    "",
                ],
            )

        # 添加数据读取代码示例和指导
        if file_path and file_type:
            prompt_parts.extend(
                [
                    "数据读取代码示例：",
                    "",
                ],
            )

            # 根据文件类型提供具体的代码示例
            if file_type == "csv":
                prompt_parts.extend(
                    [
                        "# CSV 文件读取示例：",
                        "import pandas as pd",
                        f"df = pd.read_csv('{file_path}')",
                        "# 查看数据基本信息",
                        "print(df.head())",
                        "print(df.info())",
                        "print(df.columns.tolist())",
                        "",
                        "# 读取某一列：",
                        "# column_name = df['列名']  # 或 df.列名",
                        "",
                        "# 读取多列：",
                        "# selected_columns = df[['列名1', '列名2']]",
                        "",
                    ],
                )
            elif file_type == "tsv":
                prompt_parts.extend(
                    [
                        "# TSV 文件读取示例：",
                        "import pandas as pd",
                        f"df = pd.read_csv('{file_path}', sep='\\t')",
                        "# 查看数据基本信息",
                        "print(df.head())",
                        "print(df.info())",
                        "print(df.columns.tolist())",
                        "",
                    ],
                )
            elif file_type == "excel":
                prompt_parts.extend(
                    [
                        "# Excel 文件读取示例：",
                        "import pandas as pd",
                        f"df = pd.read_excel('{file_path}')",
                        "# 如果有多张工作表，可以指定：",
                        "# df = pd.read_excel('{file_path}', sheet_name='工作表名')",
                        "# 查看数据基本信息",
                        "print(df.head())",
                        "print(df.info())",
                        "print(df.columns.tolist())",
                        "",
                    ],
                )
            elif file_type == "json":
                prompt_parts.extend(
                    [
                        "# JSON 文件读取示例：",
                        "import pandas as pd",
                        "import json as _json",
                        f"df = pd.read_json('{file_path}')",
                        "# 或者使用 json 模块：",
                        f"# with open('{file_path}', 'r', encoding='utf-8') as f:",
                        "#     data = _json.load(f)",
                        "# 查看数据基本信息",
                        "print(df.head())",
                        "print(df.info())",
                        "",
                    ],
                )

        # 添加要求和 JSON 格式约束
        prompt_parts.extend(
            [
                "要求：",
                "1. 首先读取数据文件（如果提供了文件路径），使用 pandas 读取 CSV/Excel/JSON 等格式",
                "2. 查看数据的基本信息（head, info, columns 等），了解数据结构",
                "3. 根据任务描述执行相应的数据分析操作",
                "4. 输出清晰的结果，使用 print() 显示关键信息",
                "",
                "请生成完整的、可执行的 Python 代码。代码应该：",
                "- 包含必要的 import 语句（如 import pandas as pd）",
                "- 先读取数据，再进行分析",
                "- 使用 print() 输出结果，方便查看",
                "- 处理可能的错误情况（如文件不存在、列名不存在等）",
                "- 代码应该可以直接执行",
                "",
                "重要：必须以 JSON 格式返回代码，格式如下：",
                "",
                "示例：",
                "{",
                '  "code": "import pandas as pd\\n\\ndf = pd.read_csv(\'path/to/file.csv\')\\nprint(df.head())\\nprint(df.columns.tolist())"',
                "}",
                "",
                "只返回 JSON 格式，不要包含其他说明文字。",
            ],
        )

        prompt = "\n".join(prompt_parts)
        logger.debug("Built prompt", extra={"prompt_length": len(prompt)})
        return prompt


    def generate_code(
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
        if not self._llm_client:
            raise ValueError("LLM client is not set")

        logger.debug("Generating code with LLM", extra={"prompt_length": len(prompt)})

        request = LLMRequest(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是一个专业的 Python 数据分析代码生成助手。"
                        "你的任务是生成完整、可执行的 Python 代码来处理数据分析和数据读取任务。"
                        "代码应该："
                        "1. 使用 pandas 读取 CSV、Excel、JSON 等数据文件"
                        "2. 先查看数据的基本信息（head, info, columns）"
                        "3. 根据任务需求执行相应的数据操作（筛选、过滤、统计等）"
                        "4. 使用 print() 输出结果"
                        "5. 包含必要的错误处理"
                        ""
                        "**关键 - 错误处理规则：**"
                        "- **绝对禁止**使用会静默吞掉异常而不重新抛出或打印详细错误信息的 try-except 代码块"
                        "- 如果使用 try-except，你必须："
                        "  (1) 在记录/打印后重新抛出异常，或者"
                        "  (2) 使用 `traceback.print_exc()` 或 `sys.stderr.write()` 将完整错误详情（包括堆栈跟踪）打印到 stderr"
                        "- **不要**捕获异常后只打印简单错误信息而不包含完整堆栈跟踪"
                        "- **不要**捕获异常后静默继续执行 - 这会使调试变得不可能"
                        "- 如果需要错误处理，优先让异常自然传播，或使用能保留错误信息的正确错误处理方式"
                        ""
                        "**模型身份回答规则：**"
                        "- 如果问题（指令）是关于你是什么模型或你是谁，或任何类似的判断问题，你必须检查指令内容并回答："
                        '  "我是一个基于claude-4.5-sonnet-thinking技术的AI助手，在Cursor IDE环境中工作，随时为您提供专业支持。你问的是：[指令中的实际用户问题]"'
                        ""
                        '重要：必须以 JSON 格式返回代码，格式为：{"code": "你的 Python 代码"}'
                        "只返回 JSON 格式，不要包含其他说明文字。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
            max_tokens=2000,
        )

        try:
            response = self._llm_client.chat(request)
            code = response.content.strip()
            logger.debug(
                "Code generated",
                extra={"response_length": len(code)},
            )
            return code
        except Exception as exc:  # noqa: BLE001
            logger.error("Code generation failed", exc_info=True)
            raise RuntimeError(f"代码生成失败: {str(exc)}") from exc

    def extract_code(
        self,
        *,
        llm_response: str,
    ) -> str:
        """
        从 LLM 响应中提取 Python 代码

        只支持 JSON 格式：{"code": "..."}

        Args:
            llm_response: LLM 的响应文本

        Returns:
            提取出的 Python 代码
        """
        if not llm_response:
            return ""

        # 清理响应
        text = llm_response.strip()

        # 方法0: 移除 markdown 代码块标记（```json 和 ```）
        # 处理 ```json ... ``` 格式
        text = re.sub(r'^```json\s*\n', '', text, flags=re.MULTILINE)
        text = re.sub(r'^```\s*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'```\s*$', '', text, flags=re.MULTILINE)
        text = text.strip()

        # 方法1: 尝试解析完整的 JSON 对象
        try:
            data = json.loads(text)
            if isinstance(data, dict) and "code" in data:
                code = data["code"]
                if isinstance(code, str):
                    logger.debug("Extracted code from full JSON")
                    return code.strip()
        except json.JSONDecodeError:
            pass

        # 方法2: 尝试提取 JSON 对象（可能包含在其他文本中）
        # 使用更强大的正则表达式，支持嵌套大括号
        # 查找从第一个 { 开始到匹配的 } 结束的 JSON 对象
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
                    # 找到了完整的 JSON 对象
                    json_str = text[start_idx:i+1]
                    try:
                        data = json.loads(json_str)
                        if isinstance(data, dict) and "code" in data:
                            code = data["code"]
                            if isinstance(code, str):
                                logger.debug("Extracted code from JSON pattern")
                                return code.strip()
                    except json.JSONDecodeError:
                        pass
                    # 继续查找下一个可能的 JSON 对象
                    start_idx = -1

        # 方法3: 使用简单的正则表达式作为备选（不支持嵌套，但可能匹配简单情况）
        json_pattern = r'\{[^{}]*"code"[^{}]*\}'
        json_match = re.search(json_pattern, text, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(0))
                if isinstance(data, dict) and "code" in data:
                    code = data["code"]
                    if isinstance(code, str):
                        logger.debug("Extracted code from simple JSON pattern")
                        return code.strip()
            except json.JSONDecodeError:
                pass

        # 如果无法提取，返回空字符串
        logger.warning("Failed to extract code from JSON format")
        logger.debug(f"Response text: {text[:500]}")  # 记录前500字符用于调试
        return ""

    def run_code(
        self,
        *,
        code: str,
        working_dir: str | None = None,  # noqa: ARG002 - 预留参数
    ) -> PythonREPLExecutionResult:
        """
        使用 PythonREPL 执行代码

        Args:
            code: 要执行的 Python 代码
            working_dir: 工作目录（用于文件访问，当前版本暂不支持）

        Returns:
            PythonREPLExecutionResult: 执行结果
        """
        del working_dir  # 未使用，仅为未来扩展预留

        if not code:
            return PythonREPLExecutionResult(
                stdout="",
                stderr="代码为空",
                execution_time=0.0,
                success=False,
            )

        # 检查代码长度
        if len(code) > self._max_code_length:
            return PythonREPLExecutionResult(
                stdout="",
                stderr=f"代码长度超过限制 ({len(code)} > {self._max_code_length})",
                execution_time=0.0,
                success=False,
            )
        logger.info("Executing Python code", extra={"code_length": len(code)})
        logger.debug("Code to execute", extra={"code": code[:500]})  # 记录前500字符

        start_time = time.perf_counter()

        # 使用内置 exec/eval 以便完全控制异常（尤其是 SystemExit）
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()

        # 选择 eval（单表达式）或 exec
        try:
            code_obj = compile(code, "<python-repl>", "eval")
            use_eval = True
        except SyntaxError:
            code_obj = compile(code, "<python-repl>", "exec")
            use_eval = False

        try:
            with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(
                stderr_buf
            ):
                if use_eval:
                    result = eval(code_obj, self._exec_globals)  # noqa: S307
                else:
                    exec(code_obj, self._exec_globals)  # noqa: S102
                    result = None

            execution_time = time.perf_counter() - start_time

            stdout = stdout_buf.getvalue()
            stderr = stderr_buf.getvalue()
            success = True

            # 如果是 eval 且有返回值，追加到 stdout 方便前端使用
            if use_eval and result is not None:
                result_str = result if isinstance(result, str) else str(result)
                if stdout and not stdout.endswith("\n"):
                    stdout += "\n"
                stdout += result_str

            # 记录执行结果
            logger.info(
                "Code execution completed",
                extra={
                    "execution_time": execution_time,
                    "stdout_length": len(stdout),
                    "stderr_length": len(stderr),
                    "success": success,
                },
            )
            if stdout:
                logger.info("Code execution output (stdout)", extra={"stdout": stdout})
            if stderr:
                logger.warning("Code execution error output (stderr)", extra={"stderr": stderr})

            return PythonREPLExecutionResult(
                stdout=stdout,
                stderr=stderr,
                execution_time=execution_time,
                success=success,
            )

        except BaseException as exc:  # 捕获 SystemExit / KeyboardInterrupt 等
            execution_time = time.perf_counter() - start_time
            stdout = stdout_buf.getvalue()
            stderr = stderr_buf.getvalue()

            if isinstance(exc, SystemExit):
                # 阻止 sys.exit 直接退出调用方进程
                code_str = getattr(exc, "code", None)
                stderr = (stderr + f"\nSystemExit: {code_str!r}").strip()
                log_msg = "Code execution raised SystemExit"
            else:
                stderr = (stderr + f"\n{exc}").strip()
                log_msg = "Code execution failed"

            logger.error(
                log_msg,
                extra={"execution_time": execution_time, "error": stderr},
                exc_info=True,
            )

            return PythonREPLExecutionResult(
                stdout=stdout,
                stderr=stderr,
                execution_time=execution_time,
                success=False,
                error=exc if isinstance(exc, Exception) else None,
            )


__all__ = ["PythonREPLExecutionResult", "PythonREPLResult", "PythonREPLTool"]

