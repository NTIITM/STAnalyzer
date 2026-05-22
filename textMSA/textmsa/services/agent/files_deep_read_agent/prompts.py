"""
Files Deep Read Agent Prompt 模板
"""

from __future__ import annotations

from ast import List
import json
from textmsa.logging_config import get_logger

from .state import FileTreeNode, GeneratedFileEntry, PlanHistory

logger = get_logger(__name__)

# -----------------------------------------------------------------------------
# Prompt 模板（支持中英文）
# -----------------------------------------------------------------------------

def _normalize_language(language: str | None) -> str:
    """Normalize language input; default to English."""
    if not language:
        return "en"
    lower = language.lower()
    if lower.startswith("zh"):
        return "zh"
    if lower.startswith("en"):
        return "en"
    return "en"


def _get_prompt(prompt_map: dict[str, str], language: str | None) -> str:
    """Select prompt by language with English fallback."""
    lang = _normalize_language(language)
    return prompt_map.get(lang, prompt_map["en"])


PLAN_DECISION_PROMPT = {
    "en": """
You are a file deep-read planning assistant. Based on the user question and the file tree, decide whether an analysis plan or a reading plan is required.

User question:
{user_query}

File tree (may include a virtual root; nodes contain file_id, filename, file_path, description, children):
{file_tree_list}

Existing generated file summaries:
{generated_files_summary}

**IMPORTANT CONSTRAINTS:**
1. **Reading plan STRICTLY LIMITED to:**
   - Text files only (e.g., .txt, .md, .py, .js, .json config files, README, notes, documentation)
   - Image files only (e.g., .png, .jpg, .jpeg, .gif, .bmp, .svg)
   - Reading plan CANNOT be used for data files like CSV, h5ad, HDF5, Parquet, Excel, or any structured data files

2. **Analysis plan MUST be used for:**
   - CSV, JSON (data files), h5ad, HDF5, Parquet, Excel, or other structured data files
   - Any file that requires data interpretation, statistics, computation, or numerical analysis
   - The analysis plan will read and interpret these data files, then generate text summaries/interpretations
   - Even if the user only asks to "read" or "understand" a CSV/h5ad file, you MUST use analysis plan

**Examples:**
Example 1 (Use reading plan):
- User question: "Please read the README.md file and tell me the main features of the project"
- Files: README.md (text file)
- Correct decision: Use "read" plan, directly read text content and answer

Example 2 (Use analysis plan):
- User question: "Please help me understand the content of this CSV file"
- Files: data.csv (data file)
- Correct decision: Use "analysis" plan, read CSV data, generate statistical summary and text interpretation, then answer based on the interpretation

Decision rules:
1. Analysis plan fits when:
   - Need to handle CSV, JSON (data files), h5ad, HDF5, Parquet, Excel, or other structured data files
   - Need statistics, computation, sampling, or data subset extraction
   - The user asks for numerical analysis, data exploration, or feature extraction
   - Need to interpret or understand data files (analysis plan will generate text interpretations)
   - Large data preprocessing is needed before answering
   - User asks to "read" or "understand" data files (must use analysis plan, not reading plan)

2. Reading plan fits when:
   - Files are ONLY text files (e.g., .txt, .md, .py, .js, config files, README, notes, documentation)
   - Files are ONLY image files (e.g., .png, .jpg, .jpeg, .gif, .bmp, .svg)
   - Need to understand text documents and extract key information
   - Need to analyze or describe image content
   - Analysis results already exist (as text files) and we need to synthesize across files

3. Priority:
   - If ANY data files (CSV, h5ad, etc.) exist, MUST use analysis plan
   - Use reading plan ONLY when ALL files are text or image files
   - Never use reading plan for data files

Return JSON:
{{
  "decision": "analysis" or "read",
  "reasoning": "Brief reasoning based on file type, user needs, and constraints above"
}}
""",
    "zh": """
你是文件深度阅读与规划助手。根据用户问题和文件树，判断需要进行分析计划还是阅读计划。

用户问题：
{user_query}

文件树（可能包含虚拟root，节点含 file_id, filename, file_path, description, children）：
{file_tree_list}

已有生成文件概要：
{generated_files_summary}

**重要约束条件：**
1. **阅读计划严格限制于：**
   - 仅限文本文件（如 .txt, .md, .py, .js, 配置文件, README, 笔记, 文档等）
   - 仅限图像文件（如 .png, .jpg, .jpeg, .gif, .bmp, .svg 等）
   - 阅读计划绝对不能用于数据文件，如 CSV、h5ad、HDF5、Parquet、Excel 等结构化数据文件

2. **分析计划必须用于：**
   - CSV、JSON（数据文件）、h5ad、HDF5、Parquet、Excel 等结构化数据文件
   - 任何需要数据解读、统计、计算或数值分析的文件
   - 分析计划会读取并解读这些数据文件，然后生成文本摘要/解读信息
   - 即使用户只是要求"阅读"或"理解"CSV/h5ad文件，也必须使用分析计划，产生对应的文本文件形式的统计结果，用于阅读计划处理。

**示例说明：**
示例1（使用阅读计划）：
- 用户问题："请阅读 README.md 文件，告诉我项目的主要功能"
- 文件：README.md（文本文件）
- 正确决策：使用"read"计划，直接读取文本内容并回答

示例2（使用分析计划）：
- 用户问题："请帮我理解这个CSV文件的内容"
- 文件：data.csv（数据文件）
- 正确决策：使用"analysis"计划，读取CSV数据，生成统计摘要和文本解读，然后基于解读结果回答用户

**判断逻辑：**
1. **分析计划适合以下情况：**
   - 需要处理CSV、JSON（数据文件）、h5ad、HDF5、Parquet、Excel等结构化数据文件
   - 需要统计、计算、抽样或提取数据子集
   - 用户问题要求数值分析、数据探索或特征提取
   - 需要解读或理解数据文件（分析计划会生成文本解读信息）
   - 需要对大数据文件进行预处理才能回答用户问题
   - 用户要求"阅读"或"理解"数据文件（必须使用分析计划，不能使用阅读计划）

2. **阅读计划适合以下情况：**
   - 文件仅包含文本文件（如 .txt, .md, .py, .js, 配置文件, README, 笔记, 文档等）
   - 文件仅包含图像文件（如 .png, .jpg, .jpeg, .gif, .bmp, .svg 等）
   - 需要理解文本文档内容、提取关键信息
   - 需要分析或描述图像内容
   - 已有分析结果（以文本文件形式存在），需要综合多个文件内容回答用户问题

3. **优先级：**
   - 如果存在任何数据文件（CSV、h5ad等），必须使用分析计划
   - 仅当所有文件都是文本或图像文件时，才使用阅读计划
   - 不能对数据文件使用阅读计划

请返回JSON：
{{
  "decision": "analysis" 或 "read",
  "reasoning": "详细的决策理由，基于文件类型、用户问题需求和上述约束条件判断"
}}
""",
}

ANALYSIS_PLAN_PROMPT = {
    "en": """
You are a file analysis planning assistant. Based on the user question and file tree, create analysis plans for large data files that need processing.

User question:
{user_query}

File tree (may include a virtual root; nodes contain file_id, filename, file_path, description, children):
{file_tree_list}

Existing generated file summaries:
{generated_files_summary}

Analysis plan rules:
1. Only pick files that need analysis:
   - Focus on CSV, JSON, h5ad, or other potentially large data files
   - Do not include image files in analysis_plans
   - Do not include small text files or config files in analysis_plans
2. Give each file a clear analysis goal:
   - Explicitly state what to analyze (statistics, sampling, feature extraction, etc.)
   - Goals should directly support answering the user question
   - Avoid vague analysis requests
3. Consider downstream integration:
   - Think about how analysis results will be used later
   - If analyzing multiple files, consider their relationships
4. Instruction requirements:
   - Even if pandas or similar tools already generate a data file (e.g., CSV), also produce an additional formatted, human-readable text result file (e.g., .txt) that directly answers the user question or supports later steps.
   - The text result file should clearly describe the analysis content, e.g., "top 10 differential expression genes of xxxx.csv", and list the concrete results inside.
   - Keep outputs clear and structured so they are easy to consume or further interact with.

Return JSON:
{{
  "analysis_plans": [
    {{
      "file_ids": "List of file_id values to analyze",
      "instruction": "Concrete analysis goal (e.g., row/col counts, missing rate, numeric distribution; sample 1% to new file; extract top 500 HVGs, etc.). Also output a question-focused formatted text result file (e.g., top_10_de_genes.txt) even if a pandas-generated data file already exists."
    }}
  ],
  "reasoning": "Reasoning for the analysis plan, based on file types, user needs, and file size"
}}
""",
    "zh": """
你是文件分析规划助手。根据用户问题和文件树，为需要分析的大数据文件制定分析计划。

用户问题：
{user_query}

文件树（可能包含虚拟root，节点含 file_id, filename, file_path, description, children）：
{file_tree_list}

已有生成文件概要：
{generated_files_summary}

**分析计划制定规则：**
1. **只选择需要分析的文件**：
   - 针对CSV、JSON、h5ad等可能包含大量数据的文件
   - 图像文件不要放入analysis_plans
   - 小文本文件、配置文件不要放入analysis_plans

2. **为每个文件指定明确的分析目标**：
   - 具体说明要分析什么（统计、抽样、特征提取等）
   - 分析目标应直接支持回答用户问题
   - 避免模糊的分析请求

3. **考虑后续整合**：
   - 考虑分析结果如何被后续步骤使用
   - 如果分析多个文件，考虑它们之间的关联性

4. **instruction生成要求**  
   - 即使已使用 pandas 等工具生成了对应的数据文件（如 CSV），仍需额外生成一个格式化的、易于阅读的文本结果文件（例如 .txt 格式），用于直接回答用户问题或支持后续分析。
   - 文本结果文件应明确描述分析内容，例如：“文件xxxx.csv的前10个差异表达基因.txt”，并在文件中列出具体结果。
   - 确保输出结果清晰、结构化，便于用户直接使用或进一步交互。

请返回JSON：
{{
  "analysis_plans": [
    {{
      "file_ids": "需要分析的 file_id 列表",
      "instruction": "针对该文件的具体分析目标（例如：统计行列数、缺失率、数值列分布；抽样 1% 生成样本文件；提取 top500 高变基因等），并额外输出面向问题的格式化文本结果文件（如：文件xxxx.csv的前10个差异表达基因.txt），即使已生成数据文件也要提供。"
    }}
  ],
  "reasoning": "分析计划制定理由，基于文件类型、用户问题需求和文件大小判断"
}}

""",
}

READ_PLAN_PROMPT = {
    "en": """
You are a file reading planning assistant. Based on the user question and file tree, create a reading plan that will produce the final report.

User question:
{user_query}

File tree (may include a virtual root; nodes contain file_id, filename, file_path, description, children):
{file_tree_list}

Existing generated file summaries:
{generated_files_summary}

Reading plan rules:
1. Choose appropriate files:
   - Avoid large data files (CSV, JSON, etc.); those should first go through analysis plans
   - Select text files, config files, documents, image files, etc.
   - Prefer files referenced by generated outputs
2. Make the report plan explicit:
   - Describe concrete steps to produce the report
   - Explain how the file contents will answer the user question

Return JSON:
{{
  "read_plan": {{
    "file_ids": "List of file_id values to read",  # should be a list
    "report_plan": "Concrete steps/key points for the final report and how file content answers the question",  # string
  }},
  "reasoning": "Brief reasoning based on file type, user needs, and file size"
}}
""",
    "zh": """
你是文件阅读规划助手。根据用户问题和文件树，制定阅读计划以生成最终报告。

用户问题：
{user_query}

文件树（可能包含虚拟root，节点含 file_id, filename, file_path, description, children）：
{file_tree_list}

已有生成文件概要：
{generated_files_summary}

**阅读计划制定规则：**
1. **选择合适的文件**：
   - 避免包含大数据量文件（CSV、JSON等），这些应该先通过分析计划处理
   - 选择文本文件、配置文件、文档、图像文件等
   - 优先选择生成文件中所涉及的文件

2. **明确报告计划**：
   - 具体说明生成报告的步骤
   - 说明如何利用阅读的文件内容回答用户问题

请返回JSON：
{{
  "read_plan": {{
    "file_ids": "需要分析的 file_id 列表", # 应该为list形式
    "report_plan": "生成最终报告的具体步骤/要点，说明如何利用文件内容回答用户问题", # 应该为字符串形式
  }}
  "reasoning": "简短的决策理由，基于文件类型、用户问题需求和文件大小判断"
}}
""",
}

INTEGRATION_PROMPT = {
    "en": """
You are a code generation assistant. Generate or iteratively integrate code according to the given instruction.

Instruction:
{instruction}

Input file info:
{file_infos}

{history_errors_block}

Working directory: {work_dir_path}

**Python Library Guidelines for Structured Data Files:**
- **CSV files**: Use `pandas.read_csv()` or `csv` module for reading. Use `pandas.DataFrame.to_csv()` for writing.
- **JSON data files**: Use `json.load()` / `json.dump()` or `pandas.read_json()` for reading. Use `json.dump()` / `json.dumps()` or `pandas.DataFrame.to_json()` for writing.
- **h5ad files (AnnData)**: Use `scanpy.read_h5ad()` or `anndata.read_h5ad()` for reading. Use `adata.write_h5ad()` for writing.
- **HDF5 files**: Use `h5py.File()` or `pandas.read_hdf()` for reading. Use `h5py.File().create_dataset()` or `pandas.DataFrame.to_hdf()` for writing.
- **Parquet files**: Use `pandas.read_parquet()` or `pyarrow.parquet.read_table()` for reading. Use `pandas.DataFrame.to_parquet()` or `pyarrow.parquet.write_table()` for writing.
- **Excel files**: Use `pandas.read_excel()` (requires `openpyxl` or `xlrd` engine) for reading. Use `pandas.DataFrame.to_excel()` for writing.
- **Other structured data**: Choose appropriate libraries based on file format (e.g., `pickle`, `numpy`, `scipy.io`).

**Output Requirements:**
- Read files using the provided real paths.
- Input files may be outside the working directory; read them from their provided paths without relocating.
- Write all output files into the working directory (no outputs outside the working directory).
- Follow the output filename if specified in the instruction; otherwise clearly name the output file in the working directory.
- **NO PLOTTING**: **ABSOLUTELY FORBIDDEN** to use any visualization libraries (e.g., matplotlib, seaborn, plotly, scanpy.pl.*, etc.) for plotting during code generation. **DO NOT** generate any plots, images, or visualization outputs.
- Do not fabricate data or use example data.
- When errors occur, surface detailed error information (stack trace and contextual details) so failures are easy to debug.
- **CRITICAL - Error Handling Rules:**
  - **NEVER** use try-except blocks that silently swallow exceptions without re-raising them or printing detailed error information
  - If you use try-except, you MUST either:
    (1) Re-raise the exception after logging/printing it, OR
    (2) Print the full error details (including traceback) to stderr using `traceback.print_exc()` or `sys.stderr.write()`
  - **DO NOT** catch exceptions and only print a simple error message without the full traceback
  - **DO NOT** catch exceptions and continue execution silently - this makes debugging impossible
  - If error handling is needed, prefer letting exceptions propagate naturally, or use proper error handling that preserves error information

Error handling example (emit to stderr; adapt as needed):
{{
  "code": "import sys\\nimport traceback\\n\\ntry:\\n    # your main logic here\\n    pass\\nexcept Exception:\\n    sys.stderr.write(traceback.format_exc())\\n    raise",
  "expected_files": []
}}

**Return Format:**
You MUST return a JSON object (not markdown code block) with the following structure:
{{
  "code": "The Python code as a string (no markdown code block, just raw code)",
  "expected_files": [
    {{
      "file_name": "output_file.csv",
      "description": "Detailed description of the file structure and content. For CSV files, describe columns and their meanings. For h5ad files, describe attributes, keys, and their meanings. For other formats, describe the structure appropriately."
    }}
  ]
}}

Example for CSV (input may be outside the working directory; output is saved in the working directory):
{{
  "code": "import os\\nimport pandas as pd\\nwork_dir = '{work_dir_path}'\\ninput_path = '/abs/or/relative/path/to/input.csv'  # provided real path, can be outside work_dir\\noutput_path = os.path.join(work_dir, 'output.csv')\\ndf = pd.read_csv(input_path)\\ndf.to_csv(output_path, index=False)",
  "expected_files": [
    {{
      "file_name": "output.csv",
      "description": "CSV file containing differential gene expression results. Columns: 'gene_id' (gene identifier), 'log2fc' (log2 fold change), 'pvalue' (statistical p-value), 'padj' (adjusted p-value), 'significant' (boolean indicating significance)"
    }}
  ]
}}

Example for h5ad (input may be outside the working directory; output is saved in the working directory):
{{
  "code": "import os\\nimport scanpy as sc\\nwork_dir = '{work_dir_path}'\\ninput_path = '/abs/or/relative/path/to/input.h5ad'  # provided real path, can be outside work_dir\\noutput_path = os.path.join(work_dir, 'output.h5ad')\\nadata = sc.read_h5ad(input_path)\\nadata.write(output_path)",
  "expected_files": [
    {{
      "file_name": "output.h5ad",
      "description": "AnnData object (h5ad format) containing single-cell RNA-seq data. Attributes: 'X' (count matrix, cells x genes), 'var' (gene metadata with 'gene_ids' and 'gene_names'), 'obs' (cell metadata with 'cell_type' and 'sample_id'), 'obsm' (cell embeddings in 'X_pca' and 'X_umap'), 'uns' (unsupervised annotations including 'pca' and 'umap' parameters)"
    }}
  ]
}}
""",
    "zh": """
你是代码生成助手，需要根据 instruction 生成或迭代整合代码。

指导方案：
{instruction}

输入文件信息：
{file_infos}

{history_errors_block}

工作目录：{work_dir_path}

**结构化数据文件的 Python 库使用指南：**
- **CSV 文件**：使用 `pandas.read_csv()` 或 `csv` 模块读取。使用 `pandas.DataFrame.to_csv()` 写入。
- **JSON 数据文件**：使用 `json.load()` / `json.dump()` 或 `pandas.read_json()` 读取。使用 `json.dump()` / `json.dumps()` 或 `pandas.DataFrame.to_json()` 写入。
- **h5ad 文件（AnnData）**：使用 `scanpy.read_h5ad()` 或 `anndata.read_h5ad()` 读取。使用 `adata.write_h5ad()` 写入。
- **HDF5 文件**：使用 `h5py.File()` 或 `pandas.read_hdf()` 读取。使用 `h5py.File().create_dataset()` 或 `pandas.DataFrame.to_hdf()` 写入。
- **Parquet 文件**：使用 `pandas.read_parquet()` 或 `pyarrow.parquet.read_table()` 读取。使用 `pandas.DataFrame.to_parquet()` 或 `pyarrow.parquet.write_table()` 写入。
- **Excel 文件**：使用 `pandas.read_excel()`（需要 `openpyxl` 或 `xlrd` 引擎）读取。使用 `pandas.DataFrame.to_excel()` 写入。
- **其他结构化数据**：根据文件格式选择适当的库（如 `pickle`、`numpy`、`scipy.io` 等）。

**输出要求：**
- 读取文件时使用提供的真实路径。
- 输入文件可能不在工作目录中，请直接使用提供的路径读取，不要搬移。
- 将所有输出文件写入工作目录（不要写到工作目录以外）。
- **禁止画图**：代码生成过程中**绝对禁止**使用任何可视化库（如 matplotlib、seaborn、plotly、scanpy.pl.* 等）进行画图操作，**禁止**生成任何图表、图像文件或可视化输出。
- 不要伪造数据或使用示例数据。
- 发生错误时需要输出详细的错误信息（包含堆栈与关键上下文），方便定位问题。
- **关键 - 错误处理规则：**
  - **绝对禁止**使用会静默吞掉异常而不重新抛出或打印详细错误信息的 try-except 代码块
  - 如果使用 try-except，你必须：
    (1) 在记录/打印后重新抛出异常，或者
    (2) 使用 `traceback.print_exc()` 或 `sys.stderr.write()` 将完整错误详情（包括堆栈跟踪）打印到 stderr
  - **不要**捕获异常后只打印简单错误信息而不包含完整堆栈跟踪
  - **不要**捕获异常后静默继续执行 - 这会使调试变得不可能
  - 如果需要错误处理，优先让异常自然传播，或使用能保留错误信息的正确错误处理方式

错误处理示例（输出到 stderr，可按需调整代码结构）：
{{
  "code": "import sys\\nimport traceback\\n\\ntry:\\n    # 主体逻辑\\n    pass\\nexcept Exception:\\n    sys.stderr.write(traceback.format_exc())\\n    raise",
  "expected_files": []
}}

**返回格式：**
你必须返回一个 JSON 对象（不要使用 markdown 代码块），格式如下：
{{
  "code": "Python 代码字符串（不要使用 markdown 代码块，直接返回原始代码）",
  "expected_files": [
    {{
      "file_name": "output_file.csv",
      "description": "文件的详细描述，包括结构和内容。对于 CSV 文件，描述列及其含义。对于 h5ad 文件，描述属性、键及其含义。对于其他格式，适当描述结构。"
    }}
  ]
}}

CSV 文件示例（输入可在工作目录外，输出保存到工作目录）：
{{
  "code": "import os\\nimport pandas as pd\\nwork_dir = '{work_dir_path}'\\ninput_path = '/abs/or/relative/path/to/input.csv'  # 提供的真实路径，可在工作目录外\\noutput_path = os.path.join(work_dir, 'output.csv')\\ndf = pd.read_csv(input_path)\\ndf.to_csv(output_path, index=False)",
  "expected_files": [
    {{
      "file_name": "output.csv",
      "description": "包含差异基因表达结果的 CSV 文件。列包括：'gene_id'（基因标识符）、'log2fc'（log2 倍数变化）、'pvalue'（统计 p 值）、'padj'（调整后的 p 值）、'significant'（表示是否显著的布尔值）"
    }}
  ]
}}

h5ad 文件示例（输入可在工作目录外，输出保存到工作目录）：
{{
  "code": "import os\\nimport scanpy as sc\\nwork_dir = '{work_dir_path}'\\ninput_path = '/abs/or/relative/path/to/input.h5ad'  # 提供的真实路径，可在工作目录外\\noutput_path = os.path.join(work_dir, 'output.h5ad')\\nadata = sc.read_h5ad(input_path)\\nadata.write(output_path)",
  "expected_files": [
    {{
      "file_name": "output.h5ad",
      "description": "包含单细胞 RNA-seq 数据的 AnnData 对象（h5ad 格式）。属性包括：'X'（计数矩阵，细胞 x 基因）、'var'（基因元数据，包含 'gene_ids' 和 'gene_names'）、'obs'（细胞元数据，包含 'cell_type' 和 'sample_id'）、'obsm'（细胞嵌入，包含 'X_pca' 和 'X_umap'）、'uns'（无监督注释，包括 'pca' 和 'umap' 参数）"
    }}
  ]
}}
""",
}


READ_PROMPT = {
    "en": """
You are a report generation assistant. Based on the user question, reading plan, file content summaries, and analysis results, produce the final summarized answer.

User question:
{user_query}

Reading guidance:
{report_plan}

File contents:
{file_summaries}

Produce the final answer that includes:
- Conclusion/answer
- Main evidence (referencing files or generated artifacts)

If there are no files, answer the user question directly.

Return JSON:
{{
  "final_answer": "The final summarized answer"
}}
""",
    "zh": """
你是报告生成助手。基于用户问题、阅读计划、文件内容摘要和分析结果，生成最终总结性的回答。

用户问题：
{user_query}

阅读指导：
{report_plan}

文件内容：
{file_summaries}

生成最终回答，包含：
- 结论/回答
- 主要依据（引用文件或生成物）

如果没有文件请直接回答用户问题

请以 JSON 格式返回：{{
  "final_answer": "最终总结性的回答"
}}
""",
}


FAILURE_PROMPT = {
    "en": """
You are a failure analysis assistant. The file deep-read agent has exceeded the maximum number of planning attempts (more than 3 plans).

User question:
{user_query}

File tree (may include a virtual root; nodes contain file_id, filename, file_path, description, children):
{file_tree_list}

Planning history:
{history_plans_summary}

Please analyze the failure reasons and generate a final answer that:
1. Explains why the task could not be completed
2. Summarizes what was attempted (based on history_plans)
3. **IMPORTANT**: Analyze whether the failure is due to insufficient file descriptions in the file tree. Check if any files mentioned in the planning history have vague, missing, or inadequate descriptions that prevented proper analysis
4. If file descriptions are insufficient, identify which specific files have problematic descriptions and explain how this contributed to the failure
5. Provides suggestions for what the user could try next (e.g., providing more detailed file descriptions, simplifying the query, etc.)
6. Is clear, helpful, and professional

Return JSON:
{{
  "final_answer": "The final answer explaining the failure and providing suggestions"
}}
""",
    "zh": """
你是一个失败分析助手。文件深度阅读代理已超过最大规划尝试次数（超过 3 次规划）。

用户问题：
{user_query}

文件树（可能包含虚拟根节点；节点包含 file_id、filename、file_path、description、children）：
{file_tree_list}

规划历史：
{history_plans_summary}

请分析失败原因并生成最终回答，要求：
1. 说明为什么任务无法完成
2. 总结已尝试的内容（基于 history_plans）
3. **重要**：分析失败是否因为文件树中文件描述不够详细。检查规划历史中提到的文件是否有模糊、缺失或不足的描述，导致无法进行正确分析
4. 如果文件描述不足，请指出哪些具体文件的描述存在问题，并说明这如何导致了失败
5. 提供用户接下来可以尝试的建议（例如，提供更详细的文件描述、简化查询等）
6. 回答清晰、有帮助且专业

请以 JSON 格式返回：
{{
  "final_answer": "说明失败原因并提供建议的最终回答"
}}
""",
}


# -----------------------------------------------------------------------------
# 辅助格式化
# -----------------------------------------------------------------------------

def _safe_to_jsonable(data: object):
    if isinstance(data, (str, int, float, bool)) or data is None:
        return data
    if isinstance(data, dict):
        return {k: _safe_to_jsonable(v) for k, v in data.items()}
    if isinstance(data, (list, tuple)):
        return [_safe_to_jsonable(v) for v in data]
    return str(data)


def _fmt_json(data: object) -> str:
    if data is None:
        return "null"
    if isinstance(data, str):
        return data
    return json.dumps(_safe_to_jsonable(data), ensure_ascii=False, indent=2)


def _fmt_plans_history_string(
    history_plans: list[PlanHistory] | PlanHistory | None = None,
    language: str | None = "en",
) -> str:
    """Format plan history into a readable string."""
    lang = _normalize_language(language)
    if history_plans is None:
        return ""
    if isinstance(history_plans, list):
        if lang == "zh":
            return "\n".join(
                [
                    f"计划类型：{plan_history.get('plan_type', '')}\n计划：{_fmt_json(plan_history.get('plan', {}))}\n结果：{plan_history.get('result', '')}"
                    for plan_history in history_plans
                ]
            )
        return "\n".join(
            [
                f"Plan type: {plan_history.get('plan_type', '')}\nPlan: {_fmt_json(plan_history.get('plan', {}))}\nResult: {plan_history.get('result', '')}"
                for plan_history in history_plans
            ]
        )
    # single plan record
    plan_history = history_plans
    if lang == "zh":
        return f"计划类型：{plan_history.get('plan_type', '')}\n计划：{_fmt_json(plan_history.get('plan', {}))}\n结果：{plan_history.get('result', '')}"
    return f"Plan type: {plan_history.get('plan_type', '')}\nPlan: {_fmt_json(plan_history.get('plan', {}))}\nResult: {plan_history.get('result', '')}"

def format_plan_decision_prompt(
    user_query: str,
    file_tree_list: list[FileTreeNode] | FileTreeNode,
    generated_files: list[GeneratedFileEntry],
    plan_count: int = 0,
    history_plans: list[PlanHistory] | PlanHistory | None = None,
    read_plan: dict | None = None,
    language: str | None = "en",
) -> str:
    """
    格式化“决策生成分析计划还是阅读计划”的提示词。
    """
    lang = _normalize_language(language)
    history_str = _fmt_plans_history_string(history_plans, lang)
    history_block = (
        f"\n- 计划历史：{history_str}" if lang == "zh" else f"\n- Plan history: {history_str}"
    ) if history_str else ""
    extra_context = (
        ("\n附加参考：" if lang == "zh" else "\nAdditional context:")
        + (f"\n- 已执行计划轮次：{plan_count}" if lang == "zh" else f"\n- Executed plan rounds: {plan_count}")
        + (
            f"\n- 现有阅读计划：{_fmt_json(read_plan or {})}"
            if lang == "zh"
            else f"\n- Existing read plan: {_fmt_json(read_plan or {})}"
        )
        + history_block
    )
    extra_context = (
        "" if plan_count == 0 and (history_plans is None or history_plans == []) else extra_context
    )
    return (
        extra_context
        + _get_prompt(PLAN_DECISION_PROMPT, lang).format(
            user_query=user_query,
            file_tree_list=_fmt_json(file_tree_list),
            generated_files_summary=_fmt_json(generated_files),
        )
    )


def format_analysis_plan_prompt(
    user_query: str,
    file_tree_list: list[FileTreeNode] | FileTreeNode,
    generated_files: list[GeneratedFileEntry],
    history_plans: list[PlanHistory] | PlanHistory | None = None,
    language: str | None = "en",
) -> str:
    """
    格式化分析计划提示词。
    """
    lang = _normalize_language(language)
    extra_context = (
        ""
        if history_plans in (None, [])
        else (
            ("\n附加参考：" if lang == "zh" else "\nAdditional context:")
            + (
                f"\n- 计划历史：{_fmt_plans_history_string(history_plans, lang)}"
                if lang == "zh"
                else f"\n- Plan history: {_fmt_plans_history_string(history_plans, lang)}"
            )
        )
    )
    return (
        extra_context
        + _get_prompt(ANALYSIS_PLAN_PROMPT, lang).format(
            user_query=user_query,
            file_tree_list=_fmt_json(file_tree_list),
            generated_files_summary=_fmt_json(generated_files),
        )
    )


def format_read_plan_prompt(
    user_query: str,
    file_tree_list: list[FileTreeNode] | FileTreeNode,
    generated_files: list[GeneratedFileEntry],
    history_plans: list[PlanHistory] | PlanHistory | None = None,
    language: str | None = "en",
) -> str:
    """
    格式化阅读计划提示词。
    """
    lang = _normalize_language(language)
    extra_context = (
        ""
        if history_plans in (None, [])
        else (
            ("\n附加参考：" if lang == "zh" else "\nAdditional context:")
            + (
                f"\n- 计划历史：{_fmt_plans_history_string(history_plans, lang)}"
                if lang == "zh"
                else f"\n- Plan history: {_fmt_plans_history_string(history_plans, lang)}"
            )
        )
    )
    return extra_context + _get_prompt(READ_PLAN_PROMPT, lang).format(
        user_query=user_query,
        file_tree_list=_fmt_json(file_tree_list),
        generated_files_summary=_fmt_json(generated_files),
    )



def format_integration_prompt(
    instruction: str,
    file_infos: list[dict],
    history_errors: List[str] | None,
    work_dir_path: str,
    language: str | None = "en",
) -> str:

    lang = _normalize_language(language)
    history_errors_block = ""
    if history_errors:
        history_errors_block = (
            "\n历史执行错误：\n" if lang == "zh" else "\nExecution history errors:\n"
        ) + "\n".join([f"- {error}" for error in history_errors])
    
    return _get_prompt(INTEGRATION_PROMPT, language).format(
        instruction=instruction,
        file_infos=_fmt_json(file_infos),
        history_errors_block=history_errors_block,
        work_dir_path=work_dir_path,
    )



def format_read_prompt(
    user_query: str,
    report_plan: str,
    file_summaries: list[dict],
    language: str | None = "en",
) -> str:
    return _get_prompt(READ_PROMPT, language).format(
        user_query=user_query,
        report_plan=report_plan,
        file_summaries=_fmt_json(file_summaries),
    )


def format_failure_prompt(
    user_query: str,
    file_tree_list: list[FileTreeNode] | FileTreeNode,
    history_plans: list[PlanHistory],
    language: str | None = "en",
) -> str:
    """Format failure prompt with file tree and history plans summary."""
    history_plans_summary = _fmt_plans_history_string(history_plans, language)
    return _get_prompt(FAILURE_PROMPT, language).format(
        user_query=user_query,
        file_tree_list=_fmt_json(file_tree_list),
        history_plans_summary=history_plans_summary,
    )


