# H5AD Agent 实现计划

## 一、概述

H5AD Agent 是一个专门用于查询和分析 H5AD（AnnData）文件的智能代理。它能够：
- 理解用户对 H5AD 数据的查询意图
- 自动生成 Python 代码（使用 anndata/scanpy）
- 在安全环境中执行代码
- 解析执行结果并生成结构化答案
- 支持错误修正循环

## 二、技术架构

### 2.1 核心技术栈

| 组件 | 技术选型 | 说明 |
|------|---------|------|
| 工作流编排 | LangGraph | 构建状态机工作流，支持循环和条件分支 |
| LLM 调用 | LLMClient | 复用现有的 LLM 客户端 |
| 代码执行 | PythonREPLTool | 复用现有的 Python 代码执行工具 |
| 日志系统 | Python logging | 使用项目统一的日志配置 |

### 2.2 可复用的工具

- **PythonREPLTool**: 用于执行 Python 代码，支持代码生成和执行
- **LLMClient**: 用于调用大语言模型
- **FileReaderTool**: 用于读取文件信息（可选）

## 三、文件结构

```
textmsa/services/agent/h5ad_agent/
├── __init__.py              # 导出主要接口（build_h5ad_agent_graph, H5ADAgent 等）
├── plan.md                  # 本计划文档
├── state.py                 # H5AD Agent 状态定义（H5ADAgentState, 状态构建函数）
├── workflow.py              # LangGraph 工作流定义（build_h5ad_agent_graph）
├── nodes.py                 # 所有节点函数实现（5个节点函数）
└── prompts.py               # 所有 Prompt 模板定义（3个 Prompt 模板）
```

### 3.1 文件职责说明

| 文件 | 职责 | 主要内容 |
|------|------|---------|
| `state.py` | 状态定义和管理 | `H5ADAgentState` TypedDict、状态构建函数、状态更新工具函数 |
| `prompts.py` | Prompt 模板 | 查询解析 Prompt、代码生成 Prompt、结果合成 Prompt，以及格式化函数 |
| `nodes.py` | 节点函数实现 | 5个节点函数：parse_query_node, generate_code_node, execute_code_node, check_result_node, synthesize_result_node |
| `workflow.py` | 工作流构建 | LangGraph 图构建、条件路由、入口出口设置 |
| `__init__.py` | 接口导出 | 导出主要函数和类，供外部调用 |

### 3.2 三个核心文件的详细说明

#### state.py
**职责**: 定义和管理 H5AD Agent 的状态结构

**必须包含**:
- `H5ADAgentState` TypedDict 定义（所有状态字段）
- `build_initial_state(payload: dict) -> H5ADAgentState` 函数（从输入构建初始状态）
- 状态更新工具函数（如需要）

**不应包含**:
- 节点逻辑
- Prompt 模板
- 工作流构建代码

#### prompts.py
**职责**: 定义所有 Prompt 模板和格式化函数

**必须包含**:
- `QUERY_PARSE_PROMPT`: 查询解析 Prompt 模板字符串
- `CODE_GENERATION_PROMPT`: 代码生成 Prompt 模板字符串
- `RESULT_SYNTHESIS_PROMPT`: 结果合成 Prompt 模板字符串
- `format_query_parse_prompt(...) -> str`: 格式化查询解析 Prompt
- `format_code_generation_prompt(...) -> str`: 格式化代码生成 Prompt
- `format_result_synthesis_prompt(...) -> str`: 格式化结果合成 Prompt

**不应包含**:
- 状态定义
- 节点逻辑
- LLM 调用代码（节点函数中调用）

#### nodes.py
**职责**: 实现所有节点函数

**必须包含**:
- `parse_query_node(state: H5ADAgentState) -> H5ADAgentState`: 解析查询节点
- `generate_code_node(state: H5ADAgentState) -> H5ADAgentState`: 生成代码节点
- `execute_code_node(state: H5ADAgentState) -> H5ADAgentState`: 执行代码节点
- `check_result_node(state: H5ADAgentState) -> H5ADAgentState`: 检查结果节点
- `synthesize_result_node(state: H5ADAgentState) -> H5ADAgentState`: 合成结果节点

**每个节点函数应该**:
- 从 `state.py` 导入 `H5ADAgentState`
- 从 `prompts.py` 导入相应的 Prompt 格式化函数
- 使用 LLMClient 调用 LLM（如需要）
- 使用 PythonREPLTool 执行代码（如需要）
- 添加详细的日志记录
- 返回更新后的状态

**不应包含**:
- 状态定义（从 state.py 导入）
- Prompt 模板（从 prompts.py 导入）
- 工作流构建代码

## 四、状态定义 (state.py)

### 4.1 H5ADAgentState

**文件位置**: `state.py`

```python
from typing import TypedDict, NotRequired

class H5ADAgentState(TypedDict, total=False):
    """H5AD Agent 的状态定义"""
    
    # 必需字段
    user_query: str              # 用户原始查询
    h5ad_file_path: str         # H5AD 文件路径（必需）
    
    # 查询解析结果
    parsed_intent: NotRequired[str]      # 解析出的查询意图
    parsed_params: NotRequired[dict]      # 解析出的参数（如基因名、细胞类型等）
    
    # 代码生成和执行
    generated_code: NotRequired[str]      # LLM 生成的 Python 代码
    code_execution_result: NotRequired[dict]  # 代码执行结果 {"stdout": str, "stderr": str}
    execution_attempts: NotRequired[int]  # 执行尝试次数（用于限制重试，初始为 0）
    
    # 结果处理
    raw_result: NotRequired[str]         # 原始执行输出
    structured_result: NotRequired[dict] # 结构化结果
    final_answer: NotRequired[str]       # 最终答案
    
    # 工作流控制
    should_retry: NotRequired[bool]      # 是否需要重试代码生成
    is_complete: NotRequired[bool]       # 是否完成
    
    # 错误信息
    error_message: NotRequired[str]      # 错误信息
```

### 4.2 状态构建函数

**文件位置**: `state.py`

```python
def build_initial_state(user_query: str, h5ad_file_path: str) -> H5ADAgentState:
    """
    构建初始状态
    
    Args:
        user_query: 用户查询
        h5ad_file_path: H5AD 文件路径
    
    Returns:
        初始化的 H5ADAgentState
    """
    return {
        "user_query": user_query,
        "h5ad_file_path": h5ad_file_path,
        "execution_attempts": 0,
    }
```

## 五、工作流设计（workflow.py）

### 5.1 工作流图结构

```
START
  |
  v
[parse_query_node]  # 解析用户查询（nodes.py）
  |
  v
[generate_code_node]  # 生成 Python 代码（nodes.py）
  |
  v
[execute_code_node]  # 执行代码（nodes.py）
  |
  v
[check_result_node]  # 检查执行结果（nodes.py）
  |
  |--成功--> [synthesize_result_node]  # 合成最终答案（nodes.py）
  |                                           |
  |--失败且可重试--> [generate_code_node] (重试) |
  |                                           |
  |--失败且不可重试--> [END]                  |
  |                                           v
  |                                      [END]
  |
  v
[END]
```

### 5.2 工作流实现要点

**文件位置**: `workflow.py`

1. **导入节点函数**：从 `nodes.py` 导入所有 5 个节点函数
2. **构建 StateGraph**：使用 `H5ADAgentState`（从 `state.py` 导入）
3. **添加节点**：将所有节点添加到图中
4. **设置边**：
   - `START` → `parse_query_node`
   - `parse_query_node` → `generate_code_node`
   - `generate_code_node` → `execute_code_node`
   - `execute_code_node` → `check_result_node`
   - `check_result_node` → 条件路由（见下方）
   - `synthesize_result_node` → `END`
5. **条件路由函数**（`_check_result_router`）：
   ```python
   def _check_result_router(state: H5ADAgentState) -> str:
       if state.get("is_complete"):
           return "synthesize_result"
       elif state.get("should_retry") and state.get("execution_attempts", 0) < 3:
           return "generate_code"
       else:
           return END
   ```

### 5.2 节点详细设计

#### 节点 1: parse_query_node
**功能**: 解析用户查询，提取意图和参数

**文件位置**: `nodes.py`

**输入**: `user_query`, `h5ad_file_path`

**处理逻辑**:
1. 从 `prompts.py` 导入 `format_query_parse_prompt`
2. 格式化 Prompt
3. 调用 LLMClient 解析查询
4. 解析 LLM 返回的 JSON，提取 `intent` 和 `params`
5. 更新状态：`parsed_intent`, `parsed_params`
6. 记录日志

**输出**: 状态更新（`parsed_intent`, `parsed_params`）

**日志**:
- 开始解析查询
- 解析结果（意图、参数）
- 解析耗时

#### 节点 2: generate_code_node
**功能**: 根据解析结果生成 Python 代码

**文件位置**: `nodes.py`

**输入**: `parsed_intent`, `parsed_params`, `h5ad_file_path`, `code_execution_result`（如果重试）

**处理逻辑**:
1. 从 `prompts.py` 导入 `format_code_generation_prompt`
2. 如果重试，构建 `retry_context`（包含上次执行错误信息）
3. 格式化代码生成 Prompt
4. 调用 LLMClient 生成代码
5. 解析 LLM 返回的 JSON，提取 `code` 字段
6. 验证代码基本格式（可选）
7. 更新状态：`generated_code`, `execution_attempts`（递增）
8. 记录日志

**输出**: 状态更新（`generated_code`, `execution_attempts`）

**日志**:
- 开始生成代码
- 生成的代码预览（前500字符）
- 代码生成耗时

#### 节点 3: execute_code_node
**功能**: 执行生成的 Python 代码

**文件位置**: `nodes.py`

**输入**: `generated_code`, `h5ad_file_path`

**处理逻辑**:
1. 构建完整的执行代码：
   - 导入必要库（anndata, scanpy, numpy, pandas）
   - 加载 H5AD 文件：`adata = anndata.read_h5ad(h5ad_file_path)`
   - 追加生成的代码
2. 使用 PythonREPLTool 执行代码
3. 捕获执行结果（stdout, stderr）
4. 更新状态：`code_execution_result`, `raw_result`
5. 记录执行日志

**输出**: 状态更新（`code_execution_result`, `raw_result`）

**日志**:
- 开始执行代码
- 执行代码预览
- 执行结果（成功/失败）
- 执行耗时
- 标准输出内容
- 错误信息（如果有）

#### 节点 4: check_result_node
**功能**: 检查执行结果，决定下一步

**文件位置**: `nodes.py`

**输入**: `code_execution_result`, `execution_attempts`

**处理逻辑**:
1. 检查是否有错误（`code_execution_result.get("stderr")` 非空）
2. 检查执行尝试次数（限制最大重试次数，如 3 次）
3. 决定是重试还是继续
4. 更新状态：`should_retry`, `is_complete`, `error_message`（如果失败）
5. 记录日志

**输出**: 状态更新（`should_retry`, `is_complete`, `error_message`）

**路由逻辑**（在 `workflow.py` 中实现）:
- 如果成功（无错误） → `synthesize_result`
- 如果失败且未超过重试次数（`execution_attempts < 3`） → `generate_code`（重试）
- 如果失败且超过重试次数 → `END`（返回错误信息）

**日志**:
- 检查结果
- 决定的路由

#### 节点 5: synthesize_result_node
**功能**: 合成最终答案

**文件位置**: `nodes.py`

**输入**: `user_query`, `raw_result`, `parsed_intent`

**处理逻辑**:
1. 从 `prompts.py` 导入 `format_result_synthesis_prompt`
2. 格式化结果合成 Prompt
3. 调用 LLMClient 解析原始结果
4. 解析 LLM 返回的 JSON，提取 `summary`, `structured_data`, `formatted_answer`
5. 更新状态：`structured_result`, `final_answer`, `is_complete=True`
6. 记录日志

**输出**: 状态更新（`structured_result`, `final_answer`, `is_complete=True`）

**日志**:
- 开始合成结果
- 原始结果预览
- 最终答案预览
- 合成耗时

## 六、Prompt 设计（prompts.py）

所有 Prompt 模板都定义在 `prompts.py` 文件中，并提供格式化函数。

### 6.1 查询解析 Prompt

**文件位置**: `prompts.py`

**模板定义**:
```python
QUERY_PARSE_PROMPT = """
你是一个 H5AD 数据分析专家。请解析用户查询，提取查询意图和关键参数。

用户查询：{user_query}

H5AD 文件路径：{h5ad_file_path}

请以 JSON 格式返回解析结果：
{{
  "intent": "查询意图描述（如：查询基因表达、统计细胞数量、筛选特定细胞等）",
  "params": {{
    "genes": ["基因名列表"],
    "cell_types": ["细胞类型列表"],
    "regions": ["区域列表"],
    "filters": {{"过滤条件"}},
    "operations": ["操作类型（如：mean, sum, count等）"]
  }},
  "description": "查询的详细描述"
}}

只返回 JSON，不要其他内容。
"""
```

**格式化函数**:
```python
def format_query_parse_prompt(user_query: str, h5ad_file_path: str) -> str:
    """格式化查询解析 Prompt"""
    return QUERY_PARSE_PROMPT.format(
        user_query=user_query,
        h5ad_file_path=h5ad_file_path,
    )
```

### 6.2 代码生成 Prompt

**文件位置**: `prompts.py`

**模板定义**:
```python
CODE_GENERATION_PROMPT = """
你是一个 H5AD 数据查询专家，专门生成用于查询 AnnData 对象的 Python 代码。

任务描述：
- 用户查询：{user_query}
- 查询意图：{parsed_intent}
- 关键参数：{parsed_params}

H5AD 文件信息：
- 文件路径：{h5ad_file_path}
- 数据对象已加载为变量：adata

重要约束：
1. H5AD 文件已经加载为变量 `adata`，无需再次读取
2. 必须使用 anndata 和 scanpy 库进行数据操作
3. 使用 print() 函数输出所有结果
4. 如果查询基因表达，使用 adata[:, '基因名'].X 或 adata.var_names
5. 如果查询细胞信息，使用 adata.obs
6. 如果需要进行统计，使用 numpy 或 pandas
7. 代码必须可以直接执行，不要包含注释或说明

{retry_context}

请以 JSON 格式返回代码：
{{
  "code": "你的 Python 代码（多行字符串）"
}}

只返回 JSON，不要其他内容。
"""
```

**格式化函数**:
```python
def format_code_generation_prompt(
    user_query: str,
    parsed_intent: str,
    parsed_params: dict,
    h5ad_file_path: str,
    retry_context: str = "",
) -> str:
    """格式化代码生成 Prompt"""
    return CODE_GENERATION_PROMPT.format(
        user_query=user_query,
        parsed_intent=parsed_intent,
        parsed_params=parsed_params,
        h5ad_file_path=h5ad_file_path,
        retry_context=retry_context,
    )
```

### 6.3 结果合成 Prompt

**文件位置**: `prompts.py`

**模板定义**:
```python
RESULT_SYNTHESIS_PROMPT = """
你是一个数据分析结果总结专家。请将代码执行结果转化为清晰、结构化的答案。

原始查询：{user_query}

查询意图：{parsed_intent}

代码执行输出：
{raw_result}

请根据原始查询，将执行结果总结为：
1. 简洁明了的文字描述
2. 如果结果包含数据（如数值、列表、字典），请以结构化格式展示
3. 如果结果适合用表格展示，请使用 Markdown 表格格式
4. 如果结果适合用 JSON 展示，请使用 JSON 格式并用代码块包裹

请以 JSON 格式返回：
{{
  "summary": "简洁的文字总结",
  "structured_data": {{"结构化数据（如果有）"}},
  "formatted_answer": "格式化后的完整答案（Markdown 格式）"
}}

只返回 JSON，不要其他内容。
"""
```

**格式化函数**:
```python
def format_result_synthesis_prompt(
    user_query: str,
    parsed_intent: str,
    raw_result: str,
) -> str:
    """格式化结果合成 Prompt"""
    return RESULT_SYNTHESIS_PROMPT.format(
        user_query=user_query,
        parsed_intent=parsed_intent,
        raw_result=raw_result,
    )
```

## 七、日志设计

### 7.1 日志级别

- **INFO**: 节点开始/结束、关键步骤、执行结果
- **DEBUG**: 详细数据（代码内容、执行输出等）
- **WARNING**: 警告信息（如重试、代码格式问题）
- **ERROR**: 错误信息（执行失败、LLM 调用失败等）

### 7.2 日志内容

每个节点都应记录：

1. **节点开始**
   - 节点名称
   - 输入参数摘要
   - 时间戳

2. **处理过程**
   - 关键步骤
   - 中间结果预览
   - 耗时统计

3. **节点结束**
   - 输出结果摘要
   - 执行状态（成功/失败）
   - 总耗时

### 7.3 日志格式示例

```python
logger.info(
    "H5AD Agent - 节点开始",
    extra={
        "node": "parse_query",
        "user_query_length": len(state["user_query"]),
        "h5ad_file_path": state["h5ad_file_path"],
    }
)

logger.debug(
    "H5AD Agent - 查询解析结果",
    extra={
        "node": "parse_query",
        "parsed_intent": state["parsed_intent"],
        "parsed_params": state["parsed_params"],
    }
)

logger.info(
    "H5AD Agent - 节点完成",
    extra={
        "node": "parse_query",
        "duration_seconds": duration,
        "success": True,
    }
)
```

## 八、错误处理

### 8.1 错误恢复策略

- 重试机制：代码执行失败时，将错误信息反馈给代码生成节点，最多重试 3 次
- 降级策略：如果 LLM 调用失败，返回原始执行结果
- 超时处理：代码执行设置超时（如 60 秒）

## 九、集成方式

### 9.1 作为独立 Agent 使用

```python
from textmsa.services.agent.h5ad_agent import H5ADAgent

agent = H5ADAgent()
result = agent.execute(
    user_query="查询基因 CCL5 在所有细胞中的平均表达量",
    h5ad_file_path="/path/to/data.h5ad",
)
```

### 9.2 作为子图集成到主工作流

```python
from textmsa.services.agent.h5ad_agent import build_h5ad_agent_graph

# 在主工作流中作为子图使用
h5ad_subgraph = build_h5ad_agent_graph().compile()
```

## 十、实现步骤

### 步骤 1: 创建基础文件结构
- [ ] 创建 `__init__.py`（导出接口）
- [ ] 创建 `state.py`（状态定义）
- [ ] 创建 `prompts.py`（Prompt 模板）
- [ ] 创建 `nodes.py`（节点函数占位）
- [ ] 创建 `workflow.py`（工作流占位）

### 步骤 2: 实现 state.py
- [ ] 定义 `H5ADAgentState` TypedDict
- [ ] 实现状态构建函数 `build_initial_state`
- [ ] 实现状态更新工具函数（如需要）

### 步骤 3: 实现 prompts.py
- [ ] 实现 `QUERY_PARSE_PROMPT` 模板
- [ ] 实现 `CODE_GENERATION_PROMPT` 模板
- [ ] 实现 `RESULT_SYNTHESIS_PROMPT` 模板
- [ ] 实现 Prompt 格式化函数（如 `format_query_parse_prompt`）

### 步骤 4: 实现 nodes.py
- [ ] 实现 `parse_query_node`（使用 prompts.py 中的 QUERY_PARSE_PROMPT）
- [ ] 实现 `generate_code_node`（使用 prompts.py 中的 CODE_GENERATION_PROMPT）
- [ ] 实现 `execute_code_node`（使用 PythonREPLTool）
- [ ] 实现 `check_result_node`（条件路由逻辑）
- [ ] 实现 `synthesize_result_node`（使用 prompts.py 中的 RESULT_SYNTHESIS_PROMPT）
- [ ] 每个节点添加详细日志

### 步骤 5: 构建工作流（workflow.py）
- [ ] 导入所有节点函数（从 nodes.py）
- [ ] 构建 LangGraph StateGraph
- [ ] 添加所有节点到图中
- [ ] 实现条件路由逻辑（check_result 节点）
- [ ] 设置入口点（parse_query）
- [ ] 设置出口点（END）
- [ ] 实现 `build_h5ad_agent_graph` 函数

### 步骤 6: 完善 __init__.py
- [ ] 导出 `build_h5ad_agent_graph`
- [ ] 导出 `H5ADAgentState`（如需要）
- [ ] 导出便捷执行函数（如需要）

### 步骤 7: 测试
- [ ] 单元测试（每个节点函数）
- [ ] 集成测试（完整工作流）
- [ ] 错误场景测试（代码执行失败、LLM 调用失败等）
- [ ] 重试机制测试

### 步骤 8: 文档
- [ ] API 文档
- [ ] 使用示例
- [ ] 错误处理说明

## 十一、注意事项

1. **安全性**
   - 代码执行必须在安全环境中进行
   - 验证文件路径，防止路径遍历攻击
   - 限制代码执行时间和资源使用

2. **性能**
   - LLM 调用可能较慢，考虑添加超时
   - 代码执行可能耗时，设置合理的超时时间
   - 考虑缓存解析结果（如果查询相同）

3. **可扩展性**
   - Prompt 设计要灵活，易于调整
   - 状态定义要预留扩展字段
   - 节点设计要模块化，易于替换

4. **用户体验**
   - 提供清晰的错误信息
   - 支持进度反馈（通过 job service）
   - 返回结构化的结果，便于前端展示

## 十二、后续优化方向

1. **代码优化**
   - 代码生成时考虑历史执行记录，避免重复错误
   - 支持更复杂的查询（多步骤分析）

2. **性能优化**
   - 缓存 H5AD 文件加载（如果文件未变化）
   - 并行处理多个查询

3. **功能扩展**
   - 支持可视化结果生成
   - 支持批量查询
   - 支持查询历史记录
