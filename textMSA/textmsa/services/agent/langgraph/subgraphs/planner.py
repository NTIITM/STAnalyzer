"""
Planner 子图
负责将用户请求拆解为 Knowledge / Analyst 任务，并在多阶段流程中同步状态。
"""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence, NoReturn

from langgraph.graph import END, StateGraph

from textmsa.logging_config import get_logger
from textmsa.services.agent.llm_client import LLMClient, LLMRequest, get_llm_client
from textmsa.services.agent.langgraph import jobs
from textmsa.services.agent.langgraph.state import (
    GraphState,
    PlannerTodo,
    StateUpdate,
)
from textmsa.services.agent.langgraph.subgraphs.utils import (
    fail_job_and_raise,
    format_log_extra,
    parse_json_from_llm_response,
)
from textmsa.services.agent.tools import FileReaderTool
from textmsa.services.data.mongodb_models import AgentJobStepStatus
from textmsa.services.file.file_service import get_file_info

logger = get_logger(__name__)


def _fail_planner(
    job_id: str,
    *,
    message: str,
    code: str = "unexpected_state",
    details: Mapping[str, Any] | None = None,
) -> NoReturn:
    fail_job_and_raise(
        job_id=job_id,
        role="planner",
        message=message,
        code=code,
        details=details,
        log_extra=details,
    )


# ============= Planner 节点配置 =============

PLANNER_SYSTEM_PROMPT = """你是一个经验丰富的研究规划助手，负责制定科学严谨的执行计划。
你的核心职责是：

1. 理解用户需求：分析用户问题、对话历史和上下文文件信息，识别核心目标和期望产出。

2. 评估执行状态：评估上一轮任务的执行结果，判断是否需要创建新任务、修改现有任务或继续执行。

3. 制定执行计划：将复杂问题拆解为清晰、可执行的 todo 列表，为每个 todo 指定合适的负责人（knowledge 或 analyst），明确任务目标和预期产出。

4. 任务协调与决策：综合判断任务完成情况，动态调整任务计划，确保研究流程的逻辑性和完整性。

5. 质量把控：确保计划的可执行性和合理性，避免冗余任务和循环依赖。


========== 任务分配原则 ==========

重要：任务分配原则

- knowledge：仅负责从知识库检索相关信息并生成回答
  * 不负责数据操作（如检查数据格式、验证数据完整性等）
  * 不负责数据分析（如执行统计检验、生成图表等）
  * 不参与服务调用决策，不决定需要调用哪些服务
  * 只负责检索和整合知识库中的信息

- analyst：负责所有数据分析和操作
  * 执行数据分析任务（如差异表达分析、聚类分析等）
  * 处理所有数据操作（如数据格式检查、数据预处理、数据转换等）
  * 根据任务描述自动匹配和调用相应的服务，服务调用细节完全由 analyst 决定
  * 注意：能够读取到的数据一定是完整的，不需要检查数据完整性
  * 调用analyst一定是用于对于生物数据进行数据分析的，若上下文文件中不存在生物数据，则不应该调用analyst。

========== 输出格式要求 ==========

你的输出必须是 JSON 格式，每个 todo 必须包含以下字段：
- goal: 任务目标描述（必需）
- assignee: 任务负责人，必须是 "knowledge" 或 "analyst"（必需）
- status: 任务状态，必须是 "pending"、"running" 或 "completed"（必需，新任务默认为 "pending"）
- metadata: 任务元数据（可选）

示例：

{
  "todos": [
    {
      "goal": "对选定的文件进行数据预处理、差异表达分析以及结果可视化，调用可用服务直至返回预期结果",
      "assignee": "analyst",
      "status": "pending",
      "metadata": {}
    },
    {
      "goal": "从知识库检索 BRCA1 在乳腺癌中的差异表达相关文献和证据",
      "assignee": "knowledge",
      "status": "pending",
      "metadata": {"query": "BRCA1 expression breast cancer"}
    }
  ]
}

重要：每个 todo 必须包含 status 字段，新创建的任务应该设置为 "pending"。


========== 错误示例（不要这样做）==========

- 不要将数据检查、数据格式验证等任务分配给 knowledge
  * 例如：{"assignee": "knowledge", "goal": "检查数据格式和完整性", "status": "pending"} ❌ 这是错误的
  * 应该分配给 analyst：{"assignee": "analyst", "goal": "检查数据格式", "status": "pending"} ✅

- 不要让 knowledge 决定调用什么服务或参与数据处理操作
  * 例如：{"assignee": "knowledge", "goal": "查找相关的差异表达基因服务", "status": "pending"} ❌ 这是错误的
  * 应该分配给 analyst：{"assignee": "analyst", "goal": "执行差异表达分析", "status": "pending"} ✅
  * analyst 会根据任务描述自动匹配和调用相应的服务，不需要 knowledge 参与

- 不要在 metadata 中指定具体的服务ID或服务调用细节
  * 例如：{"assignee": "analyst", "status": "pending", "metadata": {"service_id": "xxx", "method": "yyy"}} ❌ 这是错误的
  * 应该只描述任务目标：{"assignee": "analyst", "goal": "进行差异表达分析", "status": "pending", "metadata": {}} ✅

- knowledge 不应该决定调用哪些服务
  * 例如：{"assignee": "knowledge", "goal": "调用数据分析服务", "status": "pending"} ❌ 这是错误的
  * knowledge 只能检索知识：{"assignee": "knowledge", "goal": "检索相关文献", "status": "pending", "metadata": {"query": "..."}} ✅

- 不要在 metadata 中指定服务调用细节，analyst 会自动处理
  * 例如：{"status": "pending", "metadata": {"service": "diff_expr", "description": "需要调用差异表达分析服务"}} ❌ 这是错误的
  * 应该简化为：{"status": "pending", "metadata": {}} ✅ analyst 会根据 goal 自动匹配服务

- 不要为 analyst 的任务指定服务调用细节，analyst 会自动处理
  * 例如：{"assignee": "analyst", "status": "pending", "metadata": {"service_id": "xxx", "method": "yyy"}} ❌ 这是错误的
  * 应该只描述任务目标：{"assignee": "analyst", "goal": "执行差异表达分析", "status": "pending", "metadata": {}} ✅

- 不要连续生成多个相同 assignee 的 todo
  * 错误示例：
    {
      "todos": [
        {"assignee": "analyst", "goal": "对数据进行预处理", "status": "pending"},
        {"assignee": "analyst", "goal": "对数据进行聚类", "status": "pending"},
        {"assignee": "analyst", "goal": "分析差异表达基因", "status": "pending"}
      ]
    } ❌ 这是错误的，连续三个 analyst todo
  * 正确示例：
    {
      "todos": [
        {"assignee": "analyst", "goal": "对数据进行预处理、聚类以及差异表达基因分析，调用可用服务直至返回预期结果", "status": "pending"}
      ]
    } ✅ 合并为一个完整的 analyst todo

- 不要将 analyst 任务拆分成多个步骤
  * 错误示例：
    {
      "todos": [
        {"assignee": "analyst", "goal": "1. 应该对数据进行预处理", "status": "pending"},
        {"assignee": "analyst", "goal": "2. 对其聚类", "status": "pending"},
        {"assignee": "analyst", "goal": "3. 分析差异表达基因", "status": "pending"}
      ]
    } ❌ 这是错误的，不应该拆分成多个步骤
  * 正确示例：
    {
      "todos": [
        {"assignee": "analyst", "goal": "对于数据进行预处理、聚类以及差异表达基因分析，调用可用服务直至返回预期结果", "status": "pending"}
      ]
    } ✅ 应该是一个完整的任务描述，让 analyst 自动完成整个流程

如果任何步骤无法判定，返回空列表。"""

FINAL_ANSWER_SYSTEM_PROMPT = """你是一个专业的回答生成助手，负责基于所有任务执行结果生成针对性的最终回答。
你的核心职责：

1. 结果整合：
   - 回顾用户的原始问题
   - 整合所有已完成任务的结果
   - 结合知识检索结果和分析结果

2. 回答生成：
   - 生成针对用户问题的完整、准确的回答
   - 确保回答逻辑清晰、结构完整
   - 引用相关的证据和分析结果

3. 输出要求：
   - 直接输出最终回答文本，无需 JSON 格式
   - 回答应该直接、准确、有针对性"""

MODEL_QUESTION_RESPONSE = (
    "您好，我是由gpt-5.1-codex模型提供支持，作为Cursor IDE的核心功能之一，"
    "可协助完成各类开发任务，只要是编程相关的问题，都可以问我！你现在有什么想做的吗？"
)


# ============= 节点：规划 / 任务反馈 / 最终回答 =============

def node_planner_plan(
    state: GraphState,
) -> StateUpdate:
    """
    规划节点：调用 LLM 生成 todo。

    Args:
        state: LangGraph 全局状态。

    Returns:
        StateUpdate: planner_todos / active_todo 等字段。
    """

    job_id = state.get("job_id", "unknown")
    jobs.check_job_cancelled(job_id)
    logger.info("Planner node started", extra={"job_id": job_id})
    
    llm = get_llm_client()
    user_prompt = _build_planner_prompt(state)
    logger.debug(
        "Planner prompt built",
        extra=format_log_extra({
            "job_id": job_id,
            "prompt_length": len(user_prompt),
            "user_message_length": len(state.get("user_message", "")),
        }),
    )

    raw_response: str | None = None
    decision: Mapping[str, Any] = {}
    error_message: str | None = None

    try:
        request = LLMRequest(
            messages=[
                {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=1500,
            response_format={"type": "json_object"},
        )
        response = llm.chat(request)
        raw_response = response.content.strip()
        decision = parse_json_from_llm_response(raw_response, default={})
    except Exception as exc:  # pragma: no cover - exercised via tests
        error_message = str(exc)
        logger.exception("planner node failed to query LLM", exc_info=True)
        _record_planner_step(
            job_id=job_id,
            raw_response=raw_response,
            decision_summary={"phase": "plan"},
            error=error_message,
        )
        _fail_planner(
            job_id,
            message="Planner LLM call failed",
            code="planning_llm_failure",
            details={"error": error_message},
        )

    planner_todos = _coerce_todos(decision.get("todos"))
    # 如果新生成的 todos 为空，保留旧的 todos；否则使用新的 todos
    update: StateUpdate = {
        "planner_todos": planner_todos if planner_todos else list(state.get("planner_todos") or []),
    }

    # === 在 planner 内部选择下一步要执行的任务类型 ===
    # 初始化默认值
    next_task_type = "done"
    active_todo = None
    
    # 使用 update 中的 todos（可能是新的，也可能是旧的）
    todos_to_check = update["planner_todos"]
    

    logger.info(
        f"Planner decision: todos_count={len(todos_to_check)}, next_task_type={next_task_type}, "
        f"first_todo_status={todos_to_check[0].get('status') if todos_to_check else 'N/A'}, "
        f"first_todo_assignee={todos_to_check[0].get('assignee') if todos_to_check else 'N/A'}",
        extra={"job_id": job_id},
    )

    # 查找第一个 pending 或 running 状态的任务
    # 注意：新创建的任务应该是 "pending"，但如果 LLM 返回 "running" 也应该处理
    if len(todos_to_check) > 0:
        for todo in todos_to_check:
            todo_status = todo.get("status", "").lower() if todo.get("status") else ""
            # 处理 pending 或 running 状态的任务
            if todo_status in ("pending", "running"):
                assignee = todo.get("assignee", "").lower() if todo.get("assignee") else ""
                if assignee == "knowledge":
                    next_task_type = "knowledge"
                    active_todo = todo
                    # 将状态更新为 running（如果还是 pending）
                    if todo_status == "pending":
                        todo["status"] = "running"
                    break
                elif assignee == "analyst":
                    next_task_type = "analyst"
                    active_todo = todo
                    # 将状态更新为 running（如果还是 pending）
                    if todo_status == "pending":
                        todo["status"] = "running"
                    break

    # 写入决策结果；如果没有剩余任务，则 next_task_type 为 "done"
    update["next_task_type"] = next_task_type
    if active_todo is not None:
        update["active_todo"] = active_todo
    
    _record_planner_step(
        job_id=job_id,
        raw_response=raw_response,
        decision_summary={
            "todo_count": len(todos_to_check),
            "next_task_type": next_task_type,
        },
        error=error_message,
    )

    return update


def node_final_answer(
    state: GraphState,
    *,
    llm_client: LLMClient | None = None,
) -> StateUpdate:
    """
    最终回答生成节点：回顾用户问题，整合所有任务结果，生成针对性回答。
    如果检测到模型相关问题，直接返回标准回答。
    
    Args:
        state: LangGraph 全局状态。
        llm_client: 可选的 LLM 客户端，方便测试注入。
    
    Returns:
        StateUpdate: final_answer 字段。
    """
    job_id = state.get("job_id", "unknown")
    logger.info("Final answer node started", extra={"job_id": job_id})
    
    user_message = state.get("user_message", "")
    
    # 检查是否为模型相关问题（直接检查用户消息）
    model_question_keywords = [
        "你是什么", "你是谁", "什么模型", "哪个模型", "什么AI", "哪个AI",
        "什么助手", "哪个助手", "gpt", "claude", "模型名称", "模型版本"
    ]
    is_model_question = any(
        keyword in user_message.lower() for keyword in model_question_keywords
    )
    
    if is_model_question:
        logger.info("Model question detected, returning standard response", extra=format_log_extra({"job_id": job_id}))
        return StateUpdate(final_answer=MODEL_QUESTION_RESPONSE)
    normalized_intent = state.get("normalized_intent") or user_message
    knowledge_results = list(state.get("knowledge_results") or [])
    
    # 构建结果摘要（基于 todos 元数据而不是 completed_tasks）
    # 这里只依赖知识结果；analyst 任务的执行情况已经在 todos.metadata 中反映。
    task_results_summary = _build_task_completion_summary( knowledge_results)
    knowledge_summary = _summarize_knowledge_results(knowledge_results)
    
    llm = llm_client or get_llm_client()
    
    prompt = f"""
用户原始问题：
{user_message}

规范化意图：
{normalized_intent}

任务执行结果摘要：
{task_results_summary}

知识检索结果摘要：
{knowledge_summary}

请基于以上信息，生成一个完整、准确、有针对性的最终回答。
回答应该：
1. 直接回应用户的问题
2. 引用相关的任务执行结果和知识检索结果
3. 逻辑清晰、结构完整
4. 使用专业但易懂的语言

直接输出最终回答文本（无需 JSON 格式）：
""".strip()
    
    final_answer: str = ""
    error_message: str | None = None
    
    try:
        request = LLMRequest(
            messages=[
                {"role": "system", "content": FINAL_ANSWER_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=2000,
        )
        response = llm.chat(request)
        final_answer = response.content.strip()
    except Exception as exc:
        error_message = str(exc)
        logger.exception("Final answer generation failed", exc_info=True)
        _record_planner_step(
            job_id=job_id,
            raw_response=None,
            decision_summary={"phase": "final_answer"},
            error=error_message,
            name="final-answer",
        )
        _fail_planner(
            job_id,
            message="Final answer generation failed",
            code="final_answer_llm_failure",
            details={"error": error_message},
        )
    
    logger.info(
        "Final answer generated",
        extra=format_log_extra({
            "job_id": job_id,
            "answer_length": len(final_answer),
            "has_error": bool(error_message),
        }),
    )
    
    _record_planner_step(
        job_id=job_id,
        raw_response=final_answer[:500] if final_answer else None,
        decision_summary={
            "phase": "final_answer",
            "answer_length": len(final_answer),
        },
        error=error_message,
        name="final-answer",
    )
    
    return StateUpdate(final_answer=final_answer)


# ============= 辅助函数（LLM / 数据规范化） =============

def _build_file_info_section(context_files: Sequence[str], user_id: str) -> str:
    """
    构建 context_files 的文件信息和预览部分。
    
    Args:
        context_files: 上下文文件ID列表（字符串列表）
        user_id: 用户ID，用于读取文件
        
    Returns:
        格式化的文件信息字符串
    """
    if not context_files:
        return "无上下文文件"
    
    file_reader = FileReaderTool(
        max_csv_rows=5,  # 限制 CSV 预览行数
        max_text_bytes=1000,  # 限制文本预览大小
    )
    
    file_info_lines: list[str] = []
    for idx, file_id_str in enumerate(context_files):
        if not file_id_str or not isinstance(file_id_str, str):
            continue
        
        # 尝试获取文件信息和预览
        file_name = file_id_str  # 默认使用 file_id 作为文件名
        file_info_text = f"{idx}. 文件: {file_name} (ID: {file_id_str})"  # 默认值
        
        try:
            # 读取文件基本信息
            info = get_file_info(file_id_str, user_id)
            if info:
                # 如果获取到文件名，使用文件名
                file_name = info.get("file_name") or info.get("filename") or file_id_str
                description = info.get("description") or ""
                if description:
                    file_info_text = f"{idx}. 文件: {file_name} (ID: {file_id_str})\n   - 描述: {description}"
                else:
                    file_info_text = f"{idx}. 文件: {file_name} (ID: {file_id_str})"
            else:
                file_info_text = f"{idx}. 文件: {file_name} (ID: {file_id_str})"
            
            # 尝试读取文件内容预览
            read_result = file_reader.read_file(file_id=file_id_str, user_id=user_id)
            if read_result.success and read_result.preview:
                preview = read_result.preview
                # 格式化预览内容
                if isinstance(preview, dict):
                    preview_str = file_reader.format_preview(preview)
                    if preview_str:
                        file_info_text += f"\n   - 内容预览:\n{preview_str}"
                elif isinstance(preview, str):
                    preview_str = preview[:500]  # 限制预览长度
                    file_info_text += f"\n   - 内容预览: {preview_str}"
        except Exception as exc:
            logger.debug(
                "Failed to read file info/preview for planner prompt",
                extra={"file_id": file_id_str, "error": str(exc)},
            )
            # 即使读取失败，也保留基本信息（使用默认的 file_info_text）
        
        file_info_lines.append(file_info_text)
    
    if not file_info_lines:
        return "无有效的上下文文件"
    
    return "\n\n".join(file_info_lines)


def _build_planner_prompt(state: GraphState) -> str:
    user_message = state.get("user_message", "")
    conversation = _format_conversation(state.get("conversation_history") or [])

    # 构建 context_files 的文件信息和预览
    context_files = state.get("context_files") or []
    file_info_section = _build_file_info_section(context_files, state.get("user_id", ""))
    
    # 检测 active_todo 是否存在
    active_todo = state.get("active_todo")
    active_todo_section = ""
    if active_todo and isinstance(active_todo, Mapping):
        goal = active_todo.get('goal', '')
        assignee = active_todo.get('assignee', '')
        status = active_todo.get('status', 'unknown')
        active_todo_section = f"""
        上一轮执行的任务：
        - goal: {goal}
        - assignee: {assignee}
        - status: {status}
        """
    planner_todos = state.get("planner_todos") or []
    planner_todos_section = ""
    if planner_todos:
        planner_todos_section = f"""
        上一轮 planner 生成的 todos：
        {json.dumps(planner_todos, ensure_ascii=False, indent=2)}
        """


    return f"""
用户原始问题：
{user_message}

最近对话（供参考）：
{conversation}

文件信息：
{file_info_section}

上下文：

{planner_todos_section}

{active_todo_section}

请基于上述上下文信息，分析用户需求，评估执行状态，制定或更新执行计划。
""".strip()



def _coerce_todos(value: Any) -> list[PlannerTodo]:
    todos: list[PlannerTodo] = []
    if not isinstance(value, Sequence):
        return todos

    for item in value:
        if not isinstance(item, Mapping):
            continue
        assignee = str(item.get("assignee") or "analyst").lower()
        todo: PlannerTodo = {
            "goal": item.get("goal") or item.get("description"),
            "assignee": assignee,
            "status": (item.get("status") or "pending").lower(),
        }
        metadata: dict[str, Any] = {}
        raw_metadata = item.get("metadata") or {}
        if isinstance(raw_metadata, Mapping):
            metadata.update(raw_metadata)
        if metadata:
            todo["metadata"] = metadata
        todos.append(todo)
    return todos


def _summarize_knowledge_results(
    results: Sequence[Mapping[str, Any]],
    *,
    fallback: str | None = None,
) -> str:
    if not results:
        return fallback or ""
    snippets: list[str] = []
    for entry in results:
        query = entry.get("query")
        docs = entry.get("documents") or []
        doc_titles = [doc.get("title") for doc in docs if doc.get("title")]
        if query:
            snippets.append(f"查询: {query}\n找到 {len(docs)} 条相关文档，标题: {', '.join(doc_titles[:2]) or '无标题'}")
        elif doc_titles:
            snippets.append(f"找到 {len(docs)} 条相关文档，标题: {', '.join(doc_titles[:2]) or '无标题'}")
    summary = "\n".join(snippets)
    return summary or (fallback or "")


def _record_planner_step(
    *,
    job_id: str,
    raw_response: str | None,
    decision_summary: Mapping[str, Any],
    error: str | None,
    name: str = "plan",
) -> None:
    metadata: dict[str, Any] = {
        "decision": dict(decision_summary),
    }
    if raw_response:
        metadata["llm_response_preview"] = _truncate(raw_response, 800)
    if error:
        metadata["error"] = error

    jobs.append_step(
        jobs.JobStepPayload(
            job_id=job_id,
            role="planner",
            name=name,
            status=AgentJobStepStatus.COMPLETED,
            metadata=metadata,
        )
    )


def _format_conversation(messages: Sequence[Mapping[str, Any]]) -> str:
    if not messages:
        return "无"
    lines: list[str] = []
    for msg in messages[-6:]:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def _truncate(value: str, length: int) -> str:
    if len(value) <= length:
        return value
    return value[: length - 3] + "..."


def _build_task_completion_summary(
    knowledge_results: Sequence[Mapping[str, Any]],
) -> str:
    """
    构建任务完成情况摘要，用于反馈和最终回答生成。
    目前仅基于知识检索结果；analyst 的执行结果已经记录在 todos.metadata 中。
    """
    if not knowledge_results:
        return "暂无已完成的任务"
    
    lines: list[str] = []
    
    if knowledge_results:
        lines.append("知识检索结果：")
        for result in knowledge_results[:3]:
            query = result.get("query", "")
            docs = result.get("documents") or []
            doc_count = len(docs)
            if query:
                lines.append(f"  - 查询: {query}, 找到 {doc_count} 条相关文档")
            elif doc_count > 0:
                lines.append(f"  - 找到 {doc_count} 条相关文档")
    
    return "\n".join(lines) if lines else "暂无结果"


planner_node = node_planner_plan
final_answer_node = node_final_answer


__all__ = [
    "node_planner_plan",
    "node_final_answer",
    "planner_node",
    "final_answer_node",
]




