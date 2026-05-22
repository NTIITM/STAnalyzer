"""
Plan Agent Prompt 模板和格式化函数

定义所有 Prompt 模板字符串和格式化函数。
"""

import json
from typing import Any

from textmsa.logging_config import get_logger
from textmsa.services.data.mongodb_models import FileInfo

logger = get_logger(__name__)


def _normalize_language(language: str | None) -> str:
    """归一化语言输入，默认中文。"""
    if not language:
        return "zh"
    lower = str(language).lower()
    if lower.startswith("en"):
        return "en"
    if lower.startswith("zh"):
        return "zh"
    return "zh"


def _get_prompt(prompt_map: dict[str, str], language: str | None) -> str:
    """根据语言获取 Prompt，默认中文。"""
    lang = _normalize_language(language)
    return prompt_map.get(lang, prompt_map.get("zh", next(iter(prompt_map.values()))))


# ----------------------------------------------------------------------------
# 工具函数
# ----------------------------------------------------------------------------


def _fmt_json(data: object) -> str:
    """安全格式化 JSON 字符串，保持非 ASCII 字符。"""
    try:
        return json.dumps(data, ensure_ascii=False, indent=2)
    except TypeError:
        return json.dumps({}, ensure_ascii=False, indent=2)


# ============================================================================
# Prompt 模板
# ============================================================================

PLAN_PROMPT = {
    "zh": """
根据现有文件信息和用户查询，生成执行计划、接受反馈、修改执行计划，若不需要下一步执行则返回 next_plan 为 null

用户查询：{user_query}

可用服务信息：
{service_info_string}

现有文件信息：
{context_files_info_string}

执行的历史信息：
{execution_history_string}

上一段执行反馈：
{execution_feedback_string}

请根据用户查询和可用服务信息，生成下一步执行计划。如果任务已完成或无法继续，请将 next_plan 设置为 null。

重要约束：
1. next_plan 必须是一个对象（字典），不能是数组（列表）
2. 如果不需要执行，next_plan 必须为 null，不能是空数组 [] 或空对象 {{}}
3. 如果需要执行，next_plan 必须包含 service_id 字段
4. 如果现有服务无法解决问题，可以设置 service_id 为 "codegen" 来使用自生成代码进行处理，同时在expect_output中详细描述处理过程以及对于输出文件的期望，且不应该超过5个。
5. **重要**：选择服务时，必须确保 input_file_ids 中的文件类型与服务的输入文件类型配置（accepted_files）完全匹配
   - 必须根据现有文件的文件类型ID，选择能够接受这些文件类型的服务
   - 如果文件类型不匹配，服务执行会失败，请避免选择不匹配的服务
   - 文件要从上下文文件列表中选择，不要选择其他文件
   - **如果文件类型不匹配无法通过 codegen 修复（例如已经尝试过但失败），应该返回 next_plan: null**
6. **重要**：如果上一次执行的结果是成功执行（status 为 "success" 或类似成功状态），不要再次执行相同的服务（相同的 service_id）
   - 请检查执行历史信息，避免重复执行已经成功完成的服务
   - 如果任务需要继续，应选择其他服务或使用 codegen 来处理
7. **重要**：仔细检查执行历史，避免重复尝试已经失败的服务
   - 如果执行历史中显示某个服务已经失败多次（特别是因为文件类型不匹配、参数错误等相同原因），不要再次尝试该服务
   - 如果执行历史显示已经尝试过 codegen 但无法解决文件类型不匹配问题，应该返回 next_plan: null
   - 如果执行历史长度已经很长（接近5步），且任务无法继续推进，应该返回 next_plan: null

请严格按照以下 JSON 格式返回：

示例1（需要执行，使用现有服务）：
{{
  "next_plan": {{
    "service_id": "service_123",
    "input_file_ids": ["file_id_1", "file_id_2"],
    "expect_output": "期望输出描述"
  }},
  "reasoning": "思考过程"
}}

示例2（需要执行，使用自生成代码）：
{{
  "next_plan": {{
    "service_id": "codegen",
    "input_file_ids": ["file_id_1", "file_id_2"],
    "expect_output": "期望输出描述（描述需要执行的分析任务）"
  }},
  "reasoning": "现有服务无法满足需求，需要使用自生成代码处理"
}}

示例3（不需要执行）：
{{
  "next_plan": null,
  "reasoning": "任务已完成，无需进一步执行"
}}

请返回 JSON：
""",
    "en": """
Based on existing file information and the user query, create an execution plan, accept feedback, and adjust the plan. If no further step is needed, return next_plan as null.

User query:
{user_query}

Available services:
{service_info_string}

Context files:
{context_files_info_string}

Execution history:
{execution_history_string}

Latest execution feedback:
{execution_feedback_string}

Generate the next step execution plan. If the task is completed or cannot continue, set next_plan to null.

Important constraints:
1. next_plan must be an object (dict), not an array (list)
2. If no execution is needed, next_plan must be null, not [] or {{}}
3. If execution is needed, next_plan must include service_id
4. If existing services cannot solve the problem, set service_id to "codegen" to use self-generated code. Describe the processing steps and expected output files in expect_output (no more than 5).
5. **Important**: when choosing a service, ensure the file types in input_file_ids exactly match the service accepted_files configuration
   - Use file type IDs from the context files
   - Avoid selecting services whose accepted file types do not match
   - Files must be selected from the context file list only
   - **If file types do not match and cannot be fixed via codegen (e.g., already tried but failed), return next_plan: null**
6. **Important**: if the last execution was successful (status is "success" or similar success status), do not execute the same service (same service_id) again
   - Check the execution history to avoid repeating services that have already completed successfully
   - If the task needs to continue, select a different service or use codegen
7. **Important**: carefully check the execution history to avoid repeating failed services
   - If the execution history shows a service has failed multiple times (especially due to the same reason like file type mismatch, parameter errors, etc.), do not try that service again
   - If the execution history shows codegen has been tried but cannot resolve file type mismatch issues, return next_plan: null
   - If the execution history is already very long (close to 5 steps) and the task cannot progress, return next_plan: null

Return strictly in JSON:

Example 1 (needs execution, use existing service):
{{
  "next_plan": {{
    "service_id": "service_123",
    "input_file_ids": ["file_id_1", "file_id_2"],
    "expect_output": "Expected output description"
  }},
  "reasoning": "Reasoning process"
}}

Example 2 (needs execution, use self-generated code):
{{
  "next_plan": {{
    "service_id": "codegen",
    "input_file_ids": ["file_id_1", "file_id_2"],
    "expect_output": "Expected output description (describe the analysis task)"
  }},
  "reasoning": "Existing services cannot meet the requirement; need self-generated code"
}}

Example 3 (no further execution):
{{
  "next_plan": null,
  "reasoning": "Task completed, no further execution needed"
}}

Return JSON:
""",
}

REPORT_PROMPT = {
    "zh": """
根据历史执行记录，总结服务执行情况，并说明当前任务是否完成及可能的错误/中止原因。

用户查询：{user_query}

整体执行状态：{final_status}
错误或中止原因（如果有）：{final_error_or_stop_reason}

历史执行信息：
{execution_history_string}

请根据用户查询和历史执行信息，生成执行总结报告，明确：
1. 当前任务是否已经完成，或者在什么阶段中止
2. 各个服务步骤的执行结果和关键输出
3. 如果存在错误或达到最大规划轮数等情况，请在报告中明确指出原因，并给出后续建议

请以 JSON 格式返回：
{{
  "execution_summary": "对于用户查询，结合最终状态和历史执行记录的总结（包含是否完成、错误/中止原因、后续建议）"
}}
""",
    "en": """
Summarize the service execution based on the execution history, and describe whether the task has completed and any error/abort reasons.

User query:
{user_query}

Overall execution status: {final_status}
Error or abort reason (if any): {final_error_or_stop_reason}

Execution history:
{execution_history_string}

Generate an execution summary for the user query, clearly stating:
1. Whether the task has completed or at which stage it stopped
2. The results and key outputs of each service step
3. If there were errors or the maximum planning loop count was reached, explicitly mention the reason and provide follow-up suggestions

Return JSON:
{{
  "execution_summary": "Summary of the execution history for the user query, including completion status, error/abort reasons, and suggestions"
}}
""",
}

CODE_GENERATION_PROMPT = {
    "zh": """
你是代码生成助手。根据给定的指令和文件信息，生成 Python 代码来执行生信分析或数据处理任务。

指令：
{instruction}

文件信息：
{file_info}

**重要：文件信息属性说明**
- 文件信息对象仅包含以下属性：file_id, file_name, file_path, description
- **description 字段包含了文件的所有特殊属性说明**，文件不会有 description 中未提到的其他属性
- **必须仔细阅读 description 字段**，它详细说明了文件的结构、列名、数据格式等所有重要信息
- 生成代码时，只能基于 description 中明确说明的属性来操作文件，不要假设或尝试访问 description 中未提到的属性
- **示例**：一个 CSV 文件的 description 可能是："CSV file containing functional enrichment analysis results from gseapy Enrichr. Columns: 'Term' (pathway/term name), 'Overlap' (overlap between input genes and term genes, e.g., '50/200'), 'P-value' (statistical p-value for enrichment), 'Adjusted P-value' (adjusted p-value using multiple testing correction), 'Odds Ratio' (odds ratio for enrichment), 'Combined Score' (combined score combining p-value and odds ratio), 'Genes' (comma-separated list of overlapping genes), 'gene_count' (number of overlapping genes), 'total_genes' (total genes in the term)"
  - 在这个例子中，该文件只包含上述列，不会有其他列（如 file_type, metadata, created_at 等）
  - 读取和处理该文件时，只能使用 description 中明确列出的列名和属性

执行历史：
{execution_history_string}

**生信分析和数据处理的常用 Python 库：**

1. **数据处理库：**
   - **pandas**: 用于数据框操作，读取/写入 CSV、Excel、Parquet 等格式
     - `pandas.read_csv()`, `pandas.read_excel()`, `pandas.read_parquet()`
     - `df.to_csv()`, `df.to_excel()`, `df.to_parquet()`
   - **numpy**: 用于数值计算和数组操作
     - `numpy.array()`, `numpy.mean()`, `numpy.std()`, `numpy.percentile()`
   - **scipy**: 用于科学计算和统计分析
     - `scipy.stats` 用于统计检验，`scipy.cluster` 用于聚类分析

2. **生信分析专用库：**
   - **scanpy**: 用于单细胞 RNA 测序数据分析
     - `scanpy.read_h5ad()` 读取 h5ad 文件
     - `scanpy.pp.filter_cells()`, `scanpy.pp.filter_genes()` 数据过滤
     - `scanpy.pp.normalize_total()`, `scanpy.pp.log1p()` 标准化
     - `scanpy.pp.highly_variable_genes()` 高变基因筛选
     - `scanpy.pp.scale()` 缩放
     - `scanpy.tl.pca()`, `scanpy.tl.umap()`, `scanpy.tl.leiden()` 降维和聚类
     - `scanpy.pl.*` 可视化函数（如 scanpy.pl.umap(), scanpy.pl.dotplot() 等），使用前需配置 matplotlib 字体为系统默认字体
     - `adata.write_h5ad()` 保存结果
   - **anndata**: AnnData 数据结构
     - `anndata.read_h5ad()` 读取
     - `anndata.AnnData()` 创建对象
   - **biopython**: 用于生物信息学分析
     - `Bio.SeqIO` 序列处理
     - `Bio.Align` 序列比对

3. **可视化库：**
   - **matplotlib**: 用于数据可视化
     - 使用 matplotlib.pyplot 进行绘图
     - **重要 - 字体设置**：画图时必须使用系统默认字体，避免字体警告
     - 在代码开头添加字体配置：`import matplotlib.pyplot as plt` 和 `plt.rcParams['font.family'] = 'sans-serif'` 或 `plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'Liberation Sans']` 等系统默认字体
     - 示例：`import matplotlib; matplotlib.rcParams['font.family'] = 'sans-serif'` 或 `plt.rcParams['font.sans-serif'] = ['DejaVu Sans']`
   - **seaborn**: 用于统计可视化（基于 matplotlib）
     - 使用 seaborn 时同样需要设置 matplotlib 的字体配置
   - **plotly**: 用于交互式可视化
   - **scanpy.pl.***: scanpy 的可视化函数（如 scanpy.pl.umap(), scanpy.pl.dotplot() 等）
     - 使用 scanpy.pl.* 时，需要先配置 matplotlib 的字体设置

4. **其他常用库：**
   - **json**: JSON 文件读写
   - **h5py**: HDF5 文件读写
   - **pyarrow**: Parquet 文件处理

**输出要求：**
- 读取文件时使用提供的真实路径（从 input_file_ids 对应的文件信息中获取）
- 输入文件可能不在工作目录中，请直接使用提供的路径读取，不要搬移
- **重要**：如果任务需要生成输出文件，必须将所有输出文件保存到工作目录（work_dir_path）
- 工作目录路径通过 `work_dir_path` 变量提供，代码中应使用该变量构建输出文件路径
- 例如：`output_path = os.path.join(work_dir_path, "result.csv")` 或 `output_path = f"{{work_dir_path}}/result.csv"`
- **重要**：将分析结果打印到 stdout，以便可以捕获。使用 print() 语句输出关键发现、统计信息、摘要等
- 如果生成了文件，请在代码中明确说明生成了哪些文件及其用途
- 不要伪造数据或使用示例数据
- 发生错误时需要输出详细的错误信息（包含堆栈与关键上下文），方便定位问题
- **关键 - 错误处理规则：**
  - **绝对禁止**使用会静默吞掉异常而不重新抛出或打印详细错误信息的 try-except 代码块
  - 如果使用 try-except，你必须：
    (1) 在记录/打印后重新抛出异常，或者
    (2) 使用 `traceback.print_exc()` 或 `sys.stderr.write()` 将完整错误详情（包括堆栈跟踪）打印到 stderr
  - **不要**捕获异常后只打印简单错误信息而不包含完整堆栈跟踪
  - **不要**捕获异常后静默继续执行 - 这会使调试变得不可能
  - 如果需要错误处理，优先让异常自然传播，或使用能保留错误信息的正确错误处理方式
- 考虑执行历史，避免重复执行相同的分析

**返回格式：**
你必须返回一个 JSON 对象（不要使用 markdown 代码块），格式如下：
{{
  "code": "Python 代码字符串（不要使用 markdown 代码块，直接返回原始代码）",
  "expected_output": "将打印到 stdout 的内容描述"
}}
""",
    "en": """
You are a code generation assistant. Generate Python code to perform bioinformatics analysis or data processing according to the given instruction and file information.

Instruction:
{instruction}

File information:
{file_info}

**Important: File information attributes**
- File information objects only contain the following attributes: file_id, file_name, file_path, description
- **The description field contains all special attribute descriptions for the file**; the file will not have other attributes not mentioned in the description
- **You must carefully read the description field**, which details all important information about the file structure, column names, data formats, etc.
- When generating code, only operate on file attributes explicitly described in the description. Do not assume or attempt to access attributes not mentioned in the description
- **Example**: A CSV file's description might be: "CSV file containing functional enrichment analysis results from gseapy Enrichr. Columns: 'Term' (pathway/term name), 'Overlap' (overlap between input genes and term genes, e.g., '50/200'), 'P-value' (statistical p-value for enrichment), 'Adjusted P-value' (adjusted p-value using multiple testing correction), 'Odds Ratio' (odds ratio for enrichment), 'Combined Score' (combined score combining p-value and odds ratio), 'Genes' (comma-separated list of overlapping genes), 'gene_count' (number of overlapping genes), 'total_genes' (total genes in the term)"
  - In this example, the file only contains the columns listed above, and will not have other columns (such as file_type, metadata, created_at, etc.)
  - When reading and processing this file, only use the column names and attributes explicitly listed in the description

Execution history:
{execution_history_string}

**Common Python libraries for bioinformatics and data processing:**

1. **Data processing:**
   - **pandas**: data frame operations; read/write CSV, Excel, Parquet
   - **numpy**: numerical computation and arrays
   - **scipy**: scientific computing and statistics

2. **Bioinformatics:**
   - **scanpy**: single-cell RNA-seq analysis
     - Use scanpy.pp.* for preprocessing, scanpy.tl.* for analysis
     - Use scanpy.pl.* visualization functions (e.g., scanpy.pl.umap(), scanpy.pl.dotplot(), etc.), but configure matplotlib font to system default fonts first
   - **anndata**: AnnData data structure utilities
   - **biopython**: sequence processing and alignment

3. **Visualization:**
   - **matplotlib**: for data visualization
     - Use matplotlib.pyplot for plotting
     - **IMPORTANT - Font Configuration**: When plotting, you MUST use system default fonts to avoid font warnings
     - Add font configuration at the beginning of code: `import matplotlib.pyplot as plt` and `plt.rcParams['font.family'] = 'sans-serif'` or `plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'Liberation Sans']` or other system default fonts
     - Example: `import matplotlib; matplotlib.rcParams['font.family'] = 'sans-serif'` or `plt.rcParams['font.sans-serif'] = ['DejaVu Sans']`
   - **seaborn**: for statistical visualization (based on matplotlib)
     - When using seaborn, also configure matplotlib font settings
   - **plotly**: for interactive visualization
   - **scanpy.pl.***: scanpy visualization functions (e.g., scanpy.pl.umap(), scanpy.pl.dotplot(), etc.)
     - When using scanpy.pl.*, configure matplotlib font settings first

4. **Others:**
   - **json**, **h5py**, **pyarrow**

**Output requirements:**
- Use the provided real file paths (from input_file_ids) when reading files.
- Input files may be outside the working directory; read them directly without moving.
- **Important**: if the task generates output files, all outputs must be saved to the working directory (work_dir_path).
- The working directory path is provided via `work_dir_path`; build output paths with this variable (e.g., `os.path.join(work_dir_path, "result.csv")`).
- **Important**: print analysis results to stdout with print() for key findings, statistics, and summaries.
- If files are generated, explicitly state which files are produced and their purpose.
- Do not fabricate data or use sample data.
- When errors occur, output detailed error information (stack trace and key context) for debugging.
- **CRITICAL - Error Handling Rules:**
  - **NEVER** use try-except blocks that silently swallow exceptions without re-raising them or printing detailed error information
  - If you use try-except, you MUST either:
    (1) Re-raise the exception after logging/printing it, OR
    (2) Print the full error details (including traceback) to stderr using `traceback.print_exc()` or `sys.stderr.write()`
  - **DO NOT** catch exceptions and only print a simple error message without the full traceback
  - **DO NOT** catch exceptions and continue execution silently - this makes debugging impossible
  - If error handling is needed, prefer letting exceptions propagate naturally, or use proper error handling that preserves error information
- Consider execution history to avoid repeating the same analysis.

**Return format:**
You must return a JSON object (no markdown code block):
{{
  "code": "Python code string (no markdown code block, raw code)",
  "expected_output": "Description of what will be printed to stdout"
}}
""",
}

CODE_RETRY_PROMPT = {
    "zh": """
你是代码生成助手。之前的代码执行失败了。请根据错误信息修复代码并重试。

原始指令：
{instruction}

文件信息：
{file_info}

**重要：文件信息属性说明**
- 文件信息对象仅包含以下属性：file_id, file_name, file_path, description
- **description 字段包含了文件的所有特殊属性说明**，文件不会有 description 中未提到的其他属性
- **必须仔细阅读 description 字段**，它详细说明了文件的结构、列名、数据格式等所有重要信息
- 生成代码时，只能基于 description 中明确说明的属性来操作文件，不要假设或尝试访问 description 中未提到的属性
- **示例**：一个 CSV 文件的 description 可能是："CSV file containing functional enrichment analysis results from gseapy Enrichr. Columns: 'Term' (pathway/term name), 'Overlap' (overlap between input genes and term genes, e.g., '50/200'), 'P-value' (statistical p-value for enrichment), 'Adjusted P-value' (adjusted p-value using multiple testing correction), 'Odds Ratio' (odds ratio for enrichment), 'Combined Score' (combined score combining p-value and odds ratio), 'Genes' (comma-separated list of overlapping genes), 'gene_count' (number of overlapping genes), 'total_genes' (total genes in the term)"
  - 在这个例子中，该文件只包含上述列，不会有其他列（如 file_type, metadata, created_at 等）
  - 读取和处理该文件时，只能使用 description 中明确列出的列名和属性

执行历史：
{execution_history_string}

之前的代码：
{previous_code}

错误信息（stderr）：
{error_message}

请分析错误，修复代码，并返回修正后的版本。确保使用生信分析和数据处理的常用库（pandas, numpy, scanpy, anndata, matplotlib, seaborn 等）。

**重要 - 可视化字体设置：**
- 如果代码中使用 matplotlib、seaborn 或 scanpy.pl.* 等可视化库，必须在代码开头配置使用系统默认字体
- 添加字体配置：`import matplotlib; matplotlib.rcParams['font.family'] = 'sans-serif'` 或 `plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'Liberation Sans']` 等系统默认字体
- 这样可以避免字体警告问题

**返回格式：**
你必须返回一个 JSON 对象（不要使用 markdown 代码块），格式如下：
{{
  "code": "修正后的 Python 代码字符串（不要使用 markdown 代码块，直接返回原始代码）",
  "expected_output": "将打印到 stdout 的内容描述"
}}
""",
    "en": """
You are a code generation assistant. The previous code execution failed. Fix the code based on the error message and try again.

Original instruction:
{instruction}

File information:
{file_info}

**Important: File information attributes**
- File information objects only contain the following attributes: file_id, file_name, file_path, description
- **The description field contains all special attribute descriptions for the file**; the file will not have other attributes not mentioned in the description
- **You must carefully read the description field**, which details all important information about the file structure, column names, data formats, etc.
- When generating code, only operate on file attributes explicitly described in the description. Do not assume or attempt to access attributes not mentioned in the description
- **Example**: A CSV file's description might be: "CSV file containing functional enrichment analysis results from gseapy Enrichr. Columns: 'Term' (pathway/term name), 'Overlap' (overlap between input genes and term genes, e.g., '50/200'), 'P-value' (statistical p-value for enrichment), 'Adjusted P-value' (adjusted p-value using multiple testing correction), 'Odds Ratio' (odds ratio for enrichment), 'Combined Score' (combined score combining p-value and odds ratio), 'Genes' (comma-separated list of overlapping genes), 'gene_count' (number of overlapping genes), 'total_genes' (total genes in the term)"
  - In this example, the file only contains the columns listed above, and will not have other columns (such as file_type, metadata, created_at, etc.)
  - When reading and processing this file, only use the column names and attributes explicitly listed in the description

Execution history:
{execution_history_string}

Previous code:
{previous_code}

Error message (stderr):
{error_message}

Analyze the error, fix the code, and return the corrected version. Use common bioinformatics/data-processing libraries (pandas, numpy, scanpy, anndata, matplotlib, seaborn, etc.).

**IMPORTANT - Visualization Font Configuration:**
- If the code uses visualization libraries such as matplotlib, seaborn, or scanpy.pl.*, you MUST configure system default fonts at the beginning of the code
- Add font configuration: `import matplotlib; matplotlib.rcParams['font.family'] = 'sans-serif'` or `plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'Liberation Sans']` or other system default fonts
- This will avoid font warning issues

**Return format:**
You must return a JSON object (no markdown code block):
{{
  "code": "Corrected Python code string (no markdown code block, raw code)",
  "expected_output": "Description of what will be printed to stdout"
}}
""",
}


FAILURE_LOOP_DETECTION_PROMPT = {
    "zh": """
你是一个用于检测“重复失败循环”的助手。

给定一段服务执行历史（仅包含失败记录），请判断是否存在以下情况：
- 同一个 service_id 因为相同或非常相似的原因，已经连续或多次失败
- 这些失败很可能会继续重复下去，导致无限循环

执行历史（仅失败记录，按时间顺序排列）：
{failed_records_json}

请遵循以下要求：
1. 仔细阅读每一条失败记录中的 service_id、status、feedback
2. 判断是否存在“同一服务因为相同或类似原因多次失败”的模式
3. 允许你根据语义判断“类似原因”，例如错误信息中只是在路径、行号等细节不同，但本质错误相同
4. 如果你判断存在明显的重复失败循环，请返回 is_loop_detected 为 true，否则为 false

返回 JSON（不要使用 markdown 代码块）：
{{
  "is_loop_detected": true 或 false,
  "service_id": "如果检测到循环，给出主要相关的 service_id；否则可以留空字符串",
  "reason_summary": "对导致循环的失败原因做一个简短中文概述；如果 is_loop_detected 为 false，可以留空字符串"
}}
""",
    "en": """
You are an assistant for detecting "repeated failure loops".

Given a segment of service execution history (failure records only), determine whether the following holds:
- The same service_id has failed multiple times due to the same or very similar reason
- These failures are likely to continue repeating, causing an infinite loop

Execution history (failure records only, in chronological order):
{failed_records_json}

Please follow these instructions:
1. Carefully read service_id, status, and feedback of each failure record
2. Decide whether there is a pattern where the same service fails multiple times for the same or similar reason
3. You may judge "similar reason" semantically, e.g., error messages differing only in path/line number but essentially the same
4. If you believe there is an obvious repeated failure loop, return is_loop_detected as true; otherwise false

Return JSON (no markdown code block):
{{
  "is_loop_detected": true or false,
  "service_id": "If a loop is detected, the primary related service_id; otherwise an empty string",
  "reason_summary": "A brief English summary of the failure reason that leads to the loop; leave empty if is_loop_detected is false"
}}
""",
}


# ============================================================================
# 格式化函数
# ============================================================================


def format_plan_prompt(
    user_query: str,
    service_info_string: str,
    context_files_info_string: str,
    execution_history_string: str,
    execution_feedback_string: str = "",
    language: str | None = "zh",
) -> str:
    """格式化计划提示词（中英文）。"""
    lang = _normalize_language(language)
    feedback = execution_feedback_string or ("无" if lang == "zh" else "None")
    return _get_prompt(PLAN_PROMPT, lang).format(
        user_query=user_query,
        service_info_string=service_info_string,
        context_files_info_string=context_files_info_string,
        execution_history_string=execution_history_string,
        execution_feedback_string=feedback,
    )


def format_failure_loop_detection_prompt(
    failed_records: list[dict[str, Any]],
    language: str | None = "zh",
) -> str:
    """格式化失败循环检测提示词（中英文）。"""
    lang = _normalize_language(language)
    failed_records_json = _fmt_json(failed_records)
    return _get_prompt(FAILURE_LOOP_DETECTION_PROMPT, lang).format(
        failed_records_json=failed_records_json,
    )


def format_report_prompt(
    user_query: str,
    execution_history_string: str,
    final_status: str = "",
    final_error_or_stop_reason: str = "",
    language: str | None = "zh",
) -> str:
    """格式化报告提示词（中英文）。"""
    lang = _normalize_language(language)
    status = final_status or ("未知" if lang == "zh" else "unknown")
    error_or_reason = final_error_or_stop_reason or ("无" if lang == "zh" else "None")
    return _get_prompt(REPORT_PROMPT, lang).format(
        user_query=user_query,
        execution_history_string=execution_history_string,
        final_status=status,
        final_error_or_stop_reason=error_or_reason,
    )


def format_code_generation_prompt(
    instruction: str,
    file_info: dict[str, Any],
    execution_history_string: str = "",
    work_dir_path: str = "",
    analysis_guidance: str = "",
    language: str | None = "zh",
) -> str:
    """格式化代码生成提示词（中英文）。"""
    lang = _normalize_language(language)
    prompt = _get_prompt(CODE_GENERATION_PROMPT, lang).format(
        instruction=instruction,
        file_info=_fmt_json(file_info),
        execution_history_string=execution_history_string or ("无" if lang == "zh" else "None"),
    )
    
    # 如果有分析指导信息，将其追加到提示词中，帮助代码生成
    if analysis_guidance:
        if lang == "zh":
            prompt += f"\n\n[数据预览分析指导]\n{analysis_guidance}"
        else:
            prompt += f"\n\n[Data preview analysis guidance]\n{analysis_guidance}"
    
    if work_dir_path:
        if lang == "zh":
            prompt += f"\n\n工作目录路径：{work_dir_path}\n注意：所有输出文件必须保存到此目录。"
        else:
            prompt += f"\n\nWork directory path: {work_dir_path}\nNote: all output files must be saved to this directory."
    
    return prompt


def format_code_retry_prompt(
    instruction: str,
    file_info: dict[str, Any],
    previous_code: str,
    error_message: str,
    execution_history_string: str = "",
    work_dir_path: str = "",
    analysis_guidance: str = "",
    language: str | None = "zh",
) -> str:
    """格式化代码重试提示词（中英文）。"""
    lang = _normalize_language(language)
    prompt = _get_prompt(CODE_RETRY_PROMPT, lang).format(
        instruction=instruction,
        file_info=_fmt_json(file_info),
        previous_code=previous_code,
        error_message=error_message,
        execution_history_string=execution_history_string or ("无" if lang == "zh" else "None"),
    )
    
    # 重试时同样附带分析指导信息，保持上下文一致
    if analysis_guidance:
        if lang == "zh":
            prompt += f"\n\n[数据预览分析指导]\n{analysis_guidance}"
        else:
            prompt += f"\n\n[Data preview analysis guidance]\n{analysis_guidance}"
    
    if work_dir_path:
        if lang == "zh":
            prompt += f"\n\n工作目录路径：{work_dir_path}\n注意：所有输出文件必须保存到此目录。"
        else:
            prompt += f"\n\nWork directory path: {work_dir_path}\nNote: all output files must be saved to this directory."
    
    return prompt


def format_service_info_for_planning(
    service_info_list: list[dict[str, Any]],
    language: str | None = "zh",
) -> str:
    """格式化服务信息列表（中英文）。"""
    lang = _normalize_language(language)
    if not service_info_list:
        return "暂无可用服务" if lang == "zh" else "No available services"
    
    labels = {
        "header": "可用服务列表：" if lang == "zh" else "Available services:",
        "service_id": "服务ID" if lang == "zh" else "Service ID",
        "service_name": "服务名称" if lang == "zh" else "Service name",
        "service_desc": "服务描述" if lang == "zh" else "Service description",
        "input_config": "输入文件配置" if lang == "zh" else "Input file config",
        "input_type": "输入文件类型" if lang == "zh" else "Input file types",
        "output_type": "输出文件类型" if lang == "zh" else "Output file types",
        "none": "无" if lang == "zh" else "None",
        "no_desc": "无描述" if lang == "zh" else "No description",
    }
    
    lines = [labels["header"]]
    for idx, service in enumerate(service_info_list, 1):
        service_id = service.get("service_id", "")
        name = service.get("name", "")
        description = service.get("description", "") or labels["no_desc"]
        input_file_types = service.get("input_file_types", [])
        accepted_files = service.get("accepted_files", {})
        output_file_types = service.get("output_file_types", [])
        
        lines.append(f"\n{idx}. {labels['service_id']}: {service_id}")
        lines.append(f"   {labels['service_name']}: {name}")
        lines.append(f"   {labels['service_desc']}: {description}")
        
        if accepted_files:
            lines.append(f"   {labels['input_config']}:")
            for filename, file_config in accepted_files.items():
                file_type_ids = file_config.get("file_type_ids", [])
                file_desc = file_config.get("description", "")
                type_str = ", ".join(file_type_ids) if file_type_ids else labels["none"]
                desc_str = f" ({file_desc})" if file_desc else ""
                lines.append(f"     - {filename}: file_type_ids [{type_str}]{desc_str}")
        else:
            types_str = ", ".join(input_file_types) if input_file_types else labels["none"]
            lines.append(f"   {labels['input_type']}: {types_str}")
        
        lines.append(f"   {labels['output_type']}: {', '.join(output_file_types) if output_file_types else labels['none']}")
    
    return "\n".join(lines)


def format_context_files_info(
    context_files: list[FileInfo],
    language: str | None = "zh",
) -> str:
    """格式化上下文文件信息（中英文）。"""
    lang = _normalize_language(language)
    if not context_files:
        return "暂无上下文文件" if lang == "zh" else "No context files"
    
    labels = {
        "header": "上下文文件列表：" if lang == "zh" else "Context files:",
        "file_id": "文件ID" if lang == "zh" else "File ID",
        "file_name": "文件名" if lang == "zh" else "File name",
        "file_type": "文件类型ID" if lang == "zh" else "File type ID",
        "file_path": "文件路径" if lang == "zh" else "File path",
        "desc": "描述" if lang == "zh" else "Description",
    }
    
    lines = [labels["header"]]
    for idx, file_info in enumerate(context_files, 1):
        file_id = file_info.file_id
        file_name = file_info.filename
        file_type_id = file_info.file_type_id
        file_path = file_info.file_path or ""
        description = file_info.description or ""
        
        lines.append(f"\n{idx}. {labels['file_id']}: {file_id}")
        lines.append(f"   {labels['file_name']}: {file_name}")
        lines.append(f"   {labels['file_type']}: {file_type_id}")
        if file_path:
            lines.append(f"   {labels['file_path']}: {file_path}")
        if description:
            lines.append(f"   {labels['desc']}: {description}")
    
    return "\n".join(lines)


def format_execution_history(
    execution_history: list[dict[str, Any]],
    language: str | None = "zh",
) -> str:
    """格式化执行历史为字符串（中英文）。"""
    lang = _normalize_language(language)
    if not execution_history:
        return "暂无执行历史" if lang == "zh" else "No execution history"
    
    labels = {
        "header": "执行历史：" if lang == "zh" else "Execution history:",
        "step": "步骤" if lang == "zh" else "Step",
        "service_id": "服务ID" if lang == "zh" else "Service ID",
        "service_name": "服务名称" if lang == "zh" else "Service name",
        "service_desc": "服务描述" if lang == "zh" else "Service description",
        "input": "输入文件" if lang == "zh" else "Input files",
        "params": "参数" if lang == "zh" else "Parameters",
        "output": "输出文件" if lang == "zh" else "Output files",
        "status": "状态" if lang == "zh" else "Status",
        "feedback": "反馈" if lang == "zh" else "Feedback",
        "none": "无" if lang == "zh" else "None",
        "no_desc": "无描述" if lang == "zh" else "No description",
    }
    
    lines = [labels["header"]]
    for idx, record in enumerate(execution_history, 1):
        service_id = record.get("service_id", "")
        service_name = record.get("service_name", "")
        service_description = record.get("service_description", "") or labels["no_desc"]
        input_file_ids = record.get("input_file_ids", [])
        parameters = record.get("parameters", {})
        output_file_ids = record.get("output_file_ids", [])
        status = record.get("status", "unknown")
        feedback = record.get("feedback", "")
        
        lines.append(f"\n{labels['step']} {idx}:")
        lines.append(f"  {labels['service_id']}: {service_id}")
        lines.append(f"  {labels['service_name']}: {service_name}")
        lines.append(f"  {labels['service_desc']}: {service_description}")
        lines.append(f"  {labels['input']}: {', '.join(input_file_ids) if input_file_ids else labels['none']}")
        lines.append(f"  {labels['params']}: {_fmt_json(parameters) if parameters else labels['none']}")
        lines.append(f"  {labels['output']}: {', '.join(output_file_ids) if output_file_ids else labels['none']}")
        lines.append(f"  {labels['status']}: {status}")
        if feedback:
            lines.append(f"  {labels['feedback']}: {feedback}")
    
    return "\n".join(lines)

