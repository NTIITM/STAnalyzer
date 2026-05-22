# File Read Agent 设计文档

## 一、概述

File Read Agent 是一个基于 LangGraph 的智能文件分析执行系统，接收已读取的文件预览信息，生成并执行子Agent代码来分析文件内容，最终返回分析结果。

### 核心职责
- 根据文件预览信息生成子Agent的prompt和期望输出
- 生成Python代码来执行文件分析任务
- 安全执行生成的代码并捕获结果
- 反思执行结果，决定是否重新生成代码或返回结果

### 与 files_deep_read_agent 的关系
- `files_deep_read_agent` 负责文件树构建和文件读取，当需要分析时调用 `file_analysis_agent`
- `file_analysis_agent` 接收 `read_results`（已读取的文件预览信息），执行分析任务
- 两个Agent通过状态传递进行交互

## 二、状态定义 (State)

### FileAnalysisAgentState

```python
class GeneratedFileInfo(TypedDict, total=False):
    """生成的文件信息"""
    file_name: str                   # 文件名
    description: str                 # 文件描述（说明文件包含什么内容、用途等）

class SubAgentInfo(TypedDict, total=False):
    """子Agent信息定义（单个元素，非list）"""
    name: str                        # 子Agent的名称（用于标识和追踪）
    prompt: str                      # 子Agent的完整prompt
    expected_output: str             # 期望的输出结果描述
    expected_files: list[GeneratedFileInfo]  # 期望生成的文件列表（文件名和描述）

class FileAnalysisAgentState(TypedDict, total=False):
    """File Read Agent 的状态定义"""
    
    # 必需字段（从 files_deep_read_agent 传入）
    user_query: str                  # 用户原始查询
    read_results: dict               # 已读取的文件预览结果（单个元素）
    # 格式：
    # {
    #     "file_id": str,
    #     "file_name": str,
    #     "preview": str,  # 文件预览信息（字符串格式）
    # }
    work_dir_path: str               # 工作目录路径，用于保存子Agent生成的文件
    
    # 子Agent相关
    sub_agent_info: NotRequired[SubAgentInfo]      # 子Agent信息定义（单个元素，非list）
    sub_agent_code: NotRequired[str]               # 子Agent生成的代码（字符串）
    sub_agent_feedback: NotRequired[str]           # 子Agent执行反馈
    # 格式：
    # - 执行失败：f"生成代码{code}，执行失败{reason}"
    # - 执行成功：f"按照预期生成文件xxxxx" 或返回的生成的结果文本
    
    # 生成的文件信息（返回结果属性）
    generated_files_info: NotRequired[list[GeneratedFileInfo]]  # 已生成的文件信息列表
    # 每个元素格式：
    # {
    #     "file_name": str,
    #     "description": str,
    # }
    
    # 执行历史（区分两种）
    sub_agent_execution_history: NotRequired[list[dict]]  # 子Agent代码执行历史（代码和错误信息）
    # 每个元素格式：
    # {
    #     "code": str,        # 生成的代码
    #     "error": str | None,  # 错误信息（如果有）
    # }
    # 注意：执行成功则清空此历史
    sub_agent_info_execution_history: NotRequired[list[dict]]  # 子Agent信息生成历史（子Agent信息和执行反馈）
    # 每个元素格式：
    # {
    #     "sub_agent_info": SubAgentInfo,  # 生成的子Agent信息
    #     "feedback": str,                  # 执行结果反馈
    # }
    
    # 反思相关
    reflection_result: NotRequired[str]  # 反思结果（"regenerate_code" 或 "return_result"）
    reflection_reason: NotRequired[str]  # 反思原因说明
    
    # 任务完成判断
    task_completed: NotRequired[bool]    # 任务是否完成（由 return_result_node 判断）
    task_completion_reason: NotRequired[str]  # 任务完成/未完成的原因说明
    
    # 最终答案
    final_answer: NotRequired[str]       # 最终分析结果
    
    # 消息列表（用于实时对话）
    messages: NotRequired[list[MessageDict]]  # 消息列表
```

## 三、节点设计

### 3.1 `generate_sub_agent_info_node` - 生成子Agent信息节点

**功能**：
- 根据已读取的文件预览信息、用户查询，生成子Agent的信息
- 为子Agent创建唯一的名称（用于标识和追踪）
- 定义期望的输出结果格式和内容
- **定义期望生成的文件列表（文件名和描述）**

**输入**：
- `user_query`: 用户查询
- `read_results`: 已读取的文件预览结果（单个元素，包含 file_id、file_name、preview）
- `sub_agent_info_execution_history`: 子Agent信息生成历史（如果存在，包含之前生成的子Agent信息和执行反馈）
- `work_dir_path`: 工作目录路径

**输出**：
- `sub_agent_info`: 子Agent信息定义（包含name、prompt、expected_output、expected_files）
- 路由决策：`"generate_code"` 或 `"return_result"`

**实现要点**：
1. **记录日志**：记录节点开始执行、输入参数等信息
2. 格式化已读取的文件预览信息（read_results.preview 是字符串）
3. 读取过往子agent执行回馈（如果有，从 `sub_agent_info_execution_history`）
4. 调用 LLM 生成子Agent信息或判断任务是否完成：
   - **首先判断是否需要生成新的子Agent**（基于文件预览信息、用户查询、过往执行反馈）
   - 如果需要生成子Agent：
     - 为子Agent生成一个描述性的名称（如 "数据清洗子Agent"、"统计分析子Agent" 等）
     - 分析文件预览信息
     - 根据用户查询确定分析任务
     - 如果存在 `sub_agent_info_execution_history`，读取过往子Agent执行反馈，用于改进新的子Agent信息生成
     - 定义期望的输出结果格式和内容（**强调输出应该是文件，而不是stdout**）
     - **定义期望生成的文件列表，包括每个文件的文件名和描述（说明文件包含什么内容、用途等）**
     - 提供代码生成指导（**强调代码应该将结果保存到 work_dir_path 目录下的文件**）
   - 如果不需要生成子Agent（任务已完成或可以直接返回结果），LLM 应返回 `sub_agent_info: null`
5. **记录日志**：记录 LLM 调用结果、生成的子Agent信息或判断结果
6. 解析 LLM 响应，提取 `sub_agent_info`（如果为 `null` 表示不需要生成子Agent）
7. **路由决策**：
   - 如果 `sub_agent_info` 不为 `null`，返回 `"generate_code"` → 前往 `generate_sub_agent_code`
   - 如果 `sub_agent_info` 为 `null`（任务已完成或可以直接返回结果），返回 `"return_result"` → 前往 `return_result`
8. **记录日志**：记录路由决策结果

**Prompt 模板**：
```
根据用户查询和已读取的文件预览信息，判断是否需要生成新的子Agent，如果需要则生成子Agent的prompt和期望输出。

用户查询：{user_query}

已读取的文件预览信息：
文件ID：{read_results.file_id}
文件名：{read_results.file_name}
预览内容：{read_results.preview}

过往子Agent执行反馈（如果存在）：
{sub_agent_info_execution_history_string}

**重要：首先判断是否需要生成新的子Agent**
- 如果任务已经完成（基于文件预览信息可以直接回答用户查询，或者已有足够的执行结果），则返回空集合（`sub_agent_info` 为 `null`）
- 如果需要生成新的子Agent来完成分析任务，则生成完整的子Agent信息

如果需要生成子Agent，请生成以下信息：
1. 子Agent名称（一个描述性的名称，用于标识这个子Agent的任务，如 "数据清洗子Agent"、"统计分析子Agent" 等）
2. 任务描述（基于文件预览信息，明确要分析什么）
3. 期望的输出结果格式和内容（**重要：输出应该是文件，而不是stdout。详细说明输出文件应该包含哪些信息、文件格式、文件路径等**）
4. **期望生成的文件列表**（**重要：必须明确列出期望生成的所有文件，包括每个文件的文件名和描述**）：
   - 文件名：应该生成的文件名（如 "cleaned_data.csv", "analysis_result.json" 等）
   - 描述：每个文件应该包含什么内容、用途是什么（如 "清洗后的数据，包含去重和缺失值处理后的结果"）
5. 代码生成指导（如何组织代码、使用哪些库、注意事项等，**强调代码必须将结果保存到 work_dir_path 目录下的文件**）

工作目录路径：{work_dir_path}

请以 JSON 格式返回：
- **如果需要生成子Agent**：
{
  "sub_agent_info": {
    "name": "子Agent名称",
    "prompt": "完整的子Agent prompt，包含任务描述、文件信息、期望输出等",
    "expected_output": "期望的输出结果描述（格式、内容、示例等，强调输出应该是文件）",
    "expected_files": [
      {
        "file_name": "文件名（如 cleaned_data.csv）",
        "description": "文件描述（说明文件来源，包含什么内容、用途等）"
      },
      ...
    ]
  }
}

- **如果不需要生成子Agent（任务已完成或可以直接返回结果）**：
{
  "sub_agent_info": null
}
```

### 3.2 `generate_sub_agent_code_node` - 生成子Agent代码节点

**功能**：
- 根据子Agent prompt和期望输出，生成Python代码
- 代码应该能够分析已读取的文件并返回期望的结果

**输入**：
- `sub_agent_info`: 子Agent信息定义
- `read_results`: 已读取的文件预览结果（单个元素）
- `work_dir_path`: 工作目录路径
- `sub_agent_execution_history`: 子Agent代码执行历史（如果存在，包含过去的代码和错误信息，用于改进代码生成）

**输出**：
- `sub_agent_code`: 生成的Python代码（字符串）

**实现要点**：
1. **记录日志**：记录节点开始执行、子Agent信息、期望输出等信息
2. 构建代码生成prompt：
   - 包含子Agent的prompt和名称
   - 包含期望的输出结果（**强调输出应该是文件**）
   - **包含期望生成的文件列表（文件名和描述），确保代码生成这些文件**
   - 包含已读取的文件信息（read_results.preview 是字符串）
   - 包含 `work_dir_path`（**强调代码必须将结果保存到此目录下的文件**）
   - 如果存在 `sub_agent_execution_history`，包含之前的代码和错误信息（用于改进）
3. 调用 LLM 生成Python代码
4. **记录日志**：记录 LLM 调用结果、生成的代码片段（前几行）等信息
5. 解析 LLM 响应，提取代码（直接返回字符串，不需要 description）
6. 验证代码格式（可选，检查基本语法）
7. **验证代码是否包含文件写入操作（确保代码会生成文件，而不是只返回stdout）**
8. 将代码和错误信息（如果有）记录到 `sub_agent_execution_history`（执行成功则清空）
9. **记录日志**：记录代码验证结果、最终生成的代码信息

**Prompt 模板**：
```
根据子Agent信息和期望输出，生成Python代码。

子Agent信息：
{sub_agent_info}

期望输出：
{expected_output}

期望生成的文件列表：
{expected_files_string}

已读取的文件信息：
文件ID：{read_results.file_id}
文件名：{read_results.file_name}
预览内容：{read_results.preview}

过往代码执行历史（如果存在，包含之前的代码和错误）：
{sub_agent_execution_history_string}

请生成Python代码，代码应该：
1. 能够访问已读取的文件数据（通过 read_results）
2. 执行分析任务（根据 prompt 中的任务描述）
3. **将结果保存到文件（保存到 work_dir_path 目录下），而不是通过stdout返回**
4. **必须生成期望的文件列表中的所有文件，文件名和内容必须符合描述**
5. 文件路径应该使用 work_dir_path 变量（已提供在上下文中）

工作目录路径：{work_dir_path}

注意事项：
- **代码必须将结果保存到文件，文件路径使用 work_dir_path**
- **代码必须生成期望的文件列表中的所有文件，文件名必须与期望的文件名一致**
- 代码应该处理可能的异常情况
- 代码应该包含必要的注释
- 生成的文件应该有明确的文件名和扩展名（如 result.csv, analysis.json 等）

请直接返回Python代码字符串（不需要JSON格式，只需要代码本身）。
```

### 3.3 `execute_sub_agent_node` - 执行子Agent节点

**功能**：
- 执行子Agent生成的Python代码
- 捕获执行结果和错误
- **检查生成的文件（在 work_dir_path 目录下）**

**输入**：
- `sub_agent_code`: 子Agent生成的代码（字符串）
- `read_results`: 已读取的文件信息（单个元素，用于代码执行环境）
- `sub_agent_info`: 子Agent信息（用于获取期望的文件列表）
- `work_dir_path`: 工作目录路径

**输出**：
- `sub_agent_feedback`: 执行反馈（字符串）
- `sub_agent_execution_history`: 更新代码执行历史（执行成功则清空，失败则添加错误信息）
- 路由决策：`"success"` 或 `"failure"`

**实现要点**：
1. **记录日志**：记录节点开始执行、代码信息、工作目录等信息
2. 准备执行环境：
   - 确保 `work_dir_path` 目录存在（如果不存在则创建）
   - 加载已读取的文件数据到执行环境
   - 设置必要的变量和上下文：
     ```python
     execution_context = {
         "read_results": read_results,  # 单个元素
         "user_query": user_query,
         "work_dir_path": work_dir_path,  # 提供工作目录路径
         # 其他必要的上下文
     }
     ```
   - 设置必要的导入（如 pandas, numpy, os, json 等）
3. **记录日志**：记录执行环境准备完成、代码即将执行等信息
4. 执行Python代码：
   ```python
   # 使用安全的执行环境
   exec_result = execute_python_code(
       code=sub_agent_code,  # 直接是字符串
       context=execution_context,
       timeout=30,  # 执行超时时间（秒）
   )
   ```
5. **记录日志**：记录代码执行结果（成功/失败）、执行时间等信息
6. **执行后检查 work_dir_path 目录下生成的文件**：
   - 列出目录下的所有文件
   - 记录新生成的文件信息（文件名、大小、修改时间等）
   - 读取生成的文件内容（如果文件较小，可以读取；如果文件较大，只记录元信息）
7. **记录日志**：记录生成的文件列表、文件信息等
8. 捕获执行结果和错误
9. **根据执行结果生成 `sub_agent_feedback`**：
   - 如果执行失败：
     ```python
     sub_agent_feedback = f"生成代码{sub_agent_code}，执行失败{error_reason}"
     ```
   - 如果执行成功：
     - 如果生成了期望的文件，列出文件名：
       ```python
       sub_agent_feedback = f"按照预期生成文件{', '.join(generated_file_names)}"
       ```
     - 或者返回生成的结果文本（如果有stdout输出且有意义）
10. **记录日志**：记录生成的反馈信息
11. **更新 `sub_agent_execution_history`**：
   - 如果执行成功：清空 `sub_agent_execution_history`（因为成功执行，不需要保留历史）
   - 如果执行失败：将代码和错误信息添加到 `sub_agent_execution_history`：
     ```python
     sub_agent_execution_history.append({
         "code": sub_agent_code,
         "error": error_reason,
     })
     ```
12. **如果执行成功，将生成的文件信息添加到 `generated_files_info` 中**：
   - 遍历生成的文件列表
   - 从 `sub_agent_info.expected_files` 中匹配文件名，获取对应的描述
   - 如果文件名在期望列表中，使用期望的描述；否则生成默认描述
   - 将文件信息添加到 `generated_files_info` 列表中：
     ```python
     {
         "file_name": str,  # 文件名
         "description": str,  # 文件描述（从 expected_files 中获取或生成）
     }
     ```
13. **记录日志**：记录添加到 `generated_files_info` 的文件信息
14. **将生成的文件信息添加到 `sub_agent_info_execution_history`**（在后续节点中处理，这里只生成反馈）
15. **路由决策**：
   - 如果执行成功，返回 `"success"` → 前往 `generate_sub_agent_info`（继续生成新的子Agent）
   - 如果执行失败，返回 `"failure"` → 前往 `generate_sub_agent_code`（重新生成代码）
16. **记录日志**：记录路由决策结果

**注意**：
- 需要安全的代码执行环境（避免恶意代码）
- 需要处理文件访问（文件ID到实际文件路径的映射）
- 需要处理执行超时
- **不需要使用 try-catch 代码，让异常自然传播，由上层处理**
- **子Agent应该总是生成文件，而不是只返回stdout结果**
- **如果代码执行成功但没有生成文件，应该记录警告日志**
- **执行成功时清空 `sub_agent_execution_history`，失败时添加错误信息**

### 3.5 `return_result_node` - 返回结果节点

**功能**：
- 根据执行历史和子Agent执行结果，生成最终分析报告
- 直接结束工作流，返回结果

**输入**：
- `user_query`: 用户查询
- `sub_agent_info_execution_history`: 子Agent信息生成历史（包含之前生成的子Agent信息和执行反馈）
- `generated_files_info`: 已生成的文件信息列表
- `read_results`: 已读取的文件结果（单个元素）

**输出**：
- `final_answer`: 最终分析报告（包含生成的文件信息等，共同组成结构化报告）

**实现要点**：
1. **记录日志**：记录节点开始执行、输入参数等信息
2. 格式化子Agent信息生成历史（`sub_agent_info_execution_history`）
3. 格式化已生成的文件信息列表（`generated_files_info`）
4. 调用 LLM 生成最终分析报告：
   - 读取子Agent生成记录（`sub_agent_info_execution_history`）
   - 评估当前执行结果是否满足用户查询
   - 评估已生成的文件是否满足需求
   - 生成最终分析报告（包含生成的文件信息等，共同组成结构化报告）
5. **记录日志**：记录 LLM 调用结果、生成的报告摘要等信息
6. 解析 LLM 响应，提取最终报告
7. **记录日志**：记录最终报告生成完成、工作流即将结束等信息
8. **直接结束工作流，路由到 `END`**

**Prompt 模板**：
```
根据用户查询和子Agent生成记录，判断任务是否完成。

用户查询：{user_query}

子Agent生成记录（包含子Agent信息和执行反馈）：
{sub_agent_info_execution_history_string}

已生成的文件信息：
{generated_files_info_string}

已读取的文件：
文件ID：{read_results.file_id}
文件名：{read_results.file_name}
预览内容：{read_results.preview}

请生成最终分析报告：
1. 评估当前执行结果是否满足用户查询
2. 总结已生成的文件信息
3. 生成最终分析报告（包含生成的文件信息等，共同组成结构化报告）

请以 JSON 格式返回：
{
  "final_answer": "最终分析报告（结构化报告，包含生成的文件信息等）"
}
```

## 四、工作流设计

### 工作流图

```
START
  ↓
1. generate_sub_agent_info (生成子Agent信息)
   - 读取过往子agent执行回馈（如果有，从 sub_agent_info_execution_history）
   - 生成新的子agent信息
   ↓
   ├─→ 2. generate_sub_agent_code (生成子Agent代码)
   │      - 读取过去代码生成以及执行结果信息（如果有，从 sub_agent_execution_history）
   │      - 根据新的子agent信息，生成代码
   │      ↓
   │   3. execute_sub_agent (执行子Agent)
   │      - 执行代码
   │      - 根据代码执行结果，更新相应信息（执行反馈以及文件信息）
   │      ↓
   │      ├─→ 成功 → 1. generate_sub_agent_info (返回生成新的子Agent信息)
   │      │
   │      └─→ 失败 → 2. generate_sub_agent_code (返回重新生成代码)
   │
   └─→ 4. return_result (返回结果)
         - 读取子agent生成记录（sub_agent_info_execution_history）
         - 生成简要报告，生成文件信息等，共同组成结构化报告
         ↓
         └─→ END (结束)
```

### 工作流说明

1. **入口**：`generate_sub_agent_info` - 生成子Agent信息
   - 读取过往子agent执行回馈（如果有，从 `sub_agent_info_execution_history`）
   - 生成新的子agent信息
   - 路由决策：前往 `generate_sub_agent_code`（生成代码）或 `return_result`（判断任务完成）

2. **代码生成**：`generate_sub_agent_code` - 生成子Agent代码
   - 读取过去代码生成以及执行结果信息（如果有，从 `sub_agent_execution_history`）
   - 根据新的子agent信息，生成代码
   - 前往 `execute_sub_agent`

3. **代码执行**：`execute_sub_agent` - 执行子Agent
   - 执行代码
   - 根据代码执行结果，更新相应信息（执行反馈以及文件信息）
   - 路由决策：
     - 如果成功 → 返回 `generate_sub_agent_info`（继续生成新的子Agent）
     - 如果失败 → 返回 `generate_sub_agent_code`（重新生成代码）

4. **返回结果**：`return_result` - 生成最终分析报告
   - 读取子agent生成记录（`sub_agent_info_execution_history`）
   - 生成简要报告，生成文件信息等，共同组成结构化报告
   - 直接结束工作流，前往 `END`

5. **结束**：`return_result` → `END`

### 工作流代码结构

```python
def build_file_analysis_agent_workflow() -> StateGraph[FileAnalysisAgentState]:
    workflow = StateGraph(FileAnalysisAgentState)
    
    # 添加节点
    workflow.add_node("generate_sub_agent_info", generate_sub_agent_info_node)
    workflow.add_node("generate_sub_agent_code", generate_sub_agent_code_node)
    workflow.add_node("execute_sub_agent", execute_sub_agent_node)
    workflow.add_node("return_result", return_result_node)
    
    # 设置入口
    workflow.set_entry_point("generate_sub_agent_info")
    
    # 条件路由：generate_sub_agent_info
    # 读取过往子agent执行回馈（如果有），生成新的子agent信息
    # 路由决策：前往 generate_sub_agent_code 或 return_result
    workflow.add_conditional_edges(
        "generate_sub_agent_info",
        generate_sub_agent_info_node,  # 节点函数返回路由决策
        {
            "generate_code": "generate_sub_agent_code",  # 需要生成代码
            "return_result": "return_result",  # 直接判断任务完成
        },
    )
    
    # 设置边：generate_sub_agent_code -> execute_sub_agent
    workflow.add_edge("generate_sub_agent_code", "execute_sub_agent")
    
    # 条件路由：execute_sub_agent
    # 执行代码，根据代码执行结果，更新相应信息（执行反馈以及文件信息）
    # 路由决策：如果成功前往 generate_sub_agent_info，如果失败前往 generate_sub_agent_code
    workflow.add_conditional_edges(
        "execute_sub_agent",
        execute_sub_agent_node,  # 节点函数返回路由决策
        {
            "success": "generate_sub_agent_info",  # 执行成功，继续生成新的子Agent
            "failure": "generate_sub_agent_code",  # 执行失败，重新生成代码
        },
    )
    
    # 设置边：return_result -> END
    # 读取子agent生成记录生成简要报告，生成文件信息等，共同组成结构化报告
    workflow.add_edge("return_result", END)
    
    return workflow
```

## 五、关键实现细节

### 5.1 文件预览信息处理

- 从 `read_results` 中提取文件预览信息
- 格式化预览信息，使其易于理解（用于prompt）
- 支持多种文件类型（CSV、JSON、TXT、H5AD等）
- **子Agent生成的新文件会被添加到 read_results 中，供后续子Agent使用**

### 5.2 子Agent信息生成

- 基于文件预览信息生成针对性的prompt
- 明确定义期望的输出格式和内容
- **明确定义期望生成的文件列表（文件名和描述）**
- 提供代码生成指导

### 5.3 代码生成

- 基于prompt和期望输出生成Python代码
- 考虑执行历史中的错误，改进代码生成
- 生成结构化的代码（易于执行和调试）
- **代码必须将结果保存到文件（work_dir_path 目录下），而不是只返回stdout**
- 为每个子Agent生成唯一的名称，用于追踪和标识

### 5.4 代码执行安全

- 使用受限的Python执行环境
- 限制文件访问范围（只能访问 read_results 中的文件）
- 设置执行超时（避免无限循环）
- **不需要使用 try-catch 代码，让异常自然传播，由上层处理**

### 5.5 执行反馈机制

- 根据代码执行结果生成反馈字符串
- 执行失败：`"生成代码{code}，执行失败{reason}"`
- 执行成功：`"按照预期生成文件xxxxx"` 或返回的生成的结果文本
- 将子Agent信息和反馈添加到 `sub_agent_info_execution_history` 中

### 5.6 任务完成判断机制

- 评估当前所有执行结果是否完全满足用户查询
- 生成最终分析报告（包含生成的文件信息等，共同组成结构化报告）
- 直接结束工作流，返回结果

### 5.7 日志记录

- **所有节点都应该适当记录日志信息**，包括：
  - 节点开始执行时的输入参数（关键信息）
  - LLM 调用前后的状态（请求内容摘要、响应摘要）
  - 代码执行的关键步骤（执行开始、执行结果、生成的文件等）
  - 路由决策结果
  - 错误和警告信息
- **日志级别**：
  - INFO：正常流程信息（节点执行、路由决策等）
  - DEBUG：详细调试信息（代码片段、文件列表等）
  - WARNING：警告信息（如代码执行成功但未生成文件）
  - ERROR：错误信息（代码执行失败等）
- **日志格式**：使用结构化日志，包含节点名称、时间戳、关键参数等信息

### 5.8 循环控制

- 设置最大迭代次数（防止无限循环）
- 记录执行历史，避免重复错误：
  - `sub_agent_execution_history`：记录代码和错误信息（执行成功则清空）
  - `sub_agent_info_execution_history`：记录子Agent信息和执行反馈
- 在任务完成判断节点中考虑执行次数
- 支持多轮子Agent生成（每个子Agent完成一部分任务，最终完成整个任务）

## 六、文件结构

```
file_analysis_agent/
├── __init__.py              # 主入口函数
├── state.py                 # 状态定义
├── workflow.py              # 工作流定义
├── nodes.py                 # 节点实现
├── prompts.py               # Prompt模板
└── file_analysis_agent_design.md  # 设计文档（本文件）
```

## 七、与 files_deep_read_agent 的交互

### 调用方式

```python
# 在 files_deep_read_agent 中调用 file_analysis_agent
import os
work_dir_path = os.path.join(project_work_dir, "file_analysis_agent_output")  # 创建工作目录
os.makedirs(work_dir_path, exist_ok=True)

file_analysis_agent_state = {
    "user_query": user_query,
    "read_results": read_result,  # 从 files_deep_read_agent 传入（单个元素，包含 file_id、file_name、preview）
    # 格式：{"file_id": str, "file_name": str, "preview": str}
    "work_dir_path": work_dir_path,  # 工作目录路径，用于保存子Agent生成的文件
    "generated_files_info": [],  # 初始化生成的文件信息列表（可选，会自动填充）
    "sub_agent_execution_history": [],  # 初始化子Agent代码执行历史（可选，会自动填充）
    "sub_agent_info_execution_history": [],  # 初始化子Agent信息生成历史（可选，会自动填充）
}

# 执行 file_analysis_agent
result = file_analysis_agent_workflow.invoke(file_analysis_agent_state)

# 获取最终答案和生成的文件信息
final_answer = result.get("final_answer")
generated_files_info = result.get("generated_files_info", [])  # 已生成的文件信息列表
```

### 状态传递

- `files_deep_read_agent` → `file_analysis_agent`：
  - `user_query`, `read_results`, `work_dir_path`
- `file_analysis_agent` → `files_deep_read_agent`：
  - `final_answer`（最终分析结果，结构化报告，包含生成的文件信息等）
  - `generated_files_info`（已生成的文件信息列表，包含文件名和描述）
  - `sub_agent_feedback`（执行反馈，可选）
  - `work_dir_path`（工作目录路径，包含子Agent生成的所有文件）

## 八、注意事项

1. **代码执行安全**：必须使用安全的代码执行环境，防止恶意代码
2. **文件访问控制**：限制代码只能访问 read_results 中的文件和 work_dir_path 目录
3. **执行超时**：设置合理的执行超时时间（如30秒）
4. **异常处理**：**不需要使用 try-catch 代码，让异常自然传播，由上层处理**
5. **日志记录**：**所有节点都应该适当记录日志信息**，包括节点执行、LLM调用、代码执行、路由决策等关键步骤
5. **循环控制**：防止无限循环（设置最大迭代次数，如5-10次，因为可能需要多个子Agent）
6. **资源管理**：及时释放文件资源，避免内存泄漏
7. **执行历史管理**：
   - `sub_agent_execution_history`：记录代码和错误信息，执行成功则清空，失败则添加错误信息
   - `sub_agent_info_execution_history`：记录子Agent信息和执行反馈，用于改进新的子Agent信息生成
8. **文件生成验证**：确保子Agent代码总是生成文件，而不是只返回stdout
9. **工作目录管理**：确保 work_dir_path 目录存在，及时清理临时文件（可选）
10. **子Agent名称**：为每个子Agent生成唯一的、描述性的名称，便于追踪和调试
11. **多轮子Agent生成**：支持多轮子Agent生成，每个子Agent完成一部分任务，最终完成整个任务
12. **文件信息管理**：成功执行代码后，将生成的文件信息（文件名和描述）添加到 `generated_files_info` 中，作为返回结果属性
13. **期望文件定义**：在生成子Agent信息时，必须明确定义期望生成的文件列表（文件名和描述），确保代码生成正确的文件

## 九、后续优化方向

1. **代码缓存**：缓存生成的代码，避免重复生成
2. **代码优化**：自动优化生成的代码（性能、可读性）
3. **结果验证**：自动验证执行结果是否符合期望输出
4. **并行执行**：支持并行执行多个子Agent（如果任务独立）
5. **错误恢复**：更智能的错误恢复机制（自动修复常见错误）
6. **文件管理**：自动管理 work_dir_path 目录，清理临时文件，组织生成的文件
7. **子Agent依赖管理**：管理子Agent之间的依赖关系，确保执行顺序正确
8. **文件类型识别**：自动识别生成的文件类型，提供相应的预览和处理

