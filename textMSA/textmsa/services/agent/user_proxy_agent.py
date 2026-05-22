"""
基于内存checkpoint的用户代理Agent
使用interrupt/resume模式实现决策循环，支持收集项目文件信息、执行服务、回答用户问题
"""

from __future__ import annotations

import json
from typing import Any, TypedDict, Union
from typing_extensions import NotRequired

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command, interrupt

from textmsa.logging_config import get_logger
from textmsa.services.agent.langgraph.state import StateUpdate
from textmsa.services.agent.agent_utils import (
    get_llm_client_instance,
    extract_json_from_response,
    format_file_tree,
    get_context_files_tree_list,
)
from textmsa.services.agent.llm_client import LLMRequest

logger = get_logger(__name__)


def _count_files_in_tree(files_tree_list: list[dict[str, Any]]) -> int:
    """
    递归统计文件树中的文件总数
    
    Args:
        files_tree_list: 文件树列表
        
    Returns:
        文件总数
    """
    count = 0
    
    def traverse(node: dict[str, Any]) -> None:
        nonlocal count
        count += 1
        children = node.get("children", [])
        if children:
            for child in children:
                traverse(child)
    
    for root_node in files_tree_list:
        traverse(root_node)
    
    return count


class DecisionHistoryItem(TypedDict):
    """决策历史项"""
    action: str
    parameter: NotRequired[dict[str, Any]]  # 动作参数，answer_question 动作没有 parameter
    reasoning: str  # 决策理由
    result: NotRequired[str]  # 动作执行结果


# Action response TypedDict definitions
class ExecuteServiceParameter(TypedDict):
    """execute_service 动作的参数"""
    file_ids: list[str]
    query: str


class ReadFilesParameter(TypedDict):
    """read_files 动作的参数"""
    file_ids: list[str]
    recursive: bool
    query: str


class QueryKnowledgeParameter(TypedDict):
    """query_knowledge 动作的参数"""
    query: str


class ExecuteServiceResponse(TypedDict):
    """execute_service 动作的响应"""
    action: str  # "execute_service"
    parameter: ExecuteServiceParameter
    reasoning: str


class ReadFilesResponse(TypedDict):
    """read_files 动作的响应"""
    action: str  # "read_files"
    parameter: ReadFilesParameter
    reasoning: str


class QueryKnowledgeResponse(TypedDict):
    """query_knowledge 动作的响应"""
    action: str  # "query_knowledge"
    parameter: QueryKnowledgeParameter
    reasoning: str


class AnswerQuestionResponse(TypedDict):
    """answer_question 动作的响应"""
    action: str  # "answer_question"
    reasoning: str


# Union type for all action responses
ActionResponse = Union[
    ExecuteServiceResponse,
    ReadFilesResponse,
    QueryKnowledgeResponse,
    AnswerQuestionResponse,
]


class UserProxyState(TypedDict, total=False):
    """用户代理状态，扩展GraphState"""
    # 必需字段（从 GraphState 继承）
    user_id: str
    project_id: str
    # 上下文文件ID列表，由外部传入，每轮决策前据此获取最新的文件树
    context_file_ids: list[str]
    # 此字段用于承载“执行计划”文本，而不是原始用户查询
    user_message: str
    # 原始用户查询/问题，用于最终回答阶段
    original_user_message: str
    conversation_history: list[dict[str, Any]]
    decision_history: list[DecisionHistoryItem]
    language: NotRequired[str]
    # 完成标志和最终答案
    final_answer: NotRequired[str]


def decision_node(state: UserProxyState) -> StateUpdate:
    """
    决策节点：基于执行计划、历史信息和文件上下文，决定下一步动作
    
    在while true循环中决策：
    - 如果是其他决策（非answer），则interrupt出去
    - 如果是answer决策，则生成回答并返回结果（不interrupt，标记完成）
    
    可能的动作：
    - execute_service: 执行服务
    - read_files: 读取文件
    - query_knowledge: 查询知识库
    - answer_question: 回答用户问题（当信息足够时）
    
    Args:
        state: 当前状态，包含执行计划、历史信息等
        
    Returns:
        StateUpdate: 包含决策历史和完成状态的更新
    """
    # 基本状态字段
    user_id = state.get("user_id", "")
    project_id = state.get("project_id", "")
    context_file_ids = state.get("context_file_ids", [])
    # 此处的 user_message 实际上是“执行计划”文本
    user_message = state.get("user_message", "")
    # original_user_message 为原始用户问题；为了兼容旧状态，缺失时回退到 user_message
    original_user_message = state.get("original_user_message") or user_message
    conversation_history = state.get("conversation_history", [])
    decision_history = state.get("decision_history", [])
    language = state.get("language", "zh")
    
    count = 0
    while True:
        count += 1
        if count > 15:
            break
        # 每轮决策前，根据 context_file_ids 获取最新文件树
        files_tree_list: list[dict[str, Any]] = get_context_files_tree_list(
            user_id=user_id,
            project_id=project_id,
            context_file_ids=context_file_ids,
            recursive=True,
        )

        # 构建决策提示
        decision_prompt = _build_decision_prompt(
            user_message=user_message,
            conversation_history=conversation_history,
            files_tree_list=files_tree_list,
            decision_history=decision_history,
            language=language,
        )
        llm_client = get_llm_client_instance()
        # 根据语言选择 system 提示
        lang = "en" if str(language).lower().startswith("en") else "zh"
        if lang == "en":
            system_content = (
                "You are a decision assistant. Analyze the user's needs and the current "
                "execution status, and decide the next action. You must strictly return JSON."
            )
        else:
            system_content = (
                "你是一个决策助手，负责分析用户需求并决定下一步动作。请严格按照JSON格式返回结果。"
            )
        request = LLMRequest(
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": decision_prompt},
            ],
            temperature=0.3,
            max_tokens=500,
        )
        response = llm_client.chat(request)
        action_data = extract_json_from_response(response.content)
        action = action_data.get("action", "")

        # 简单去重：如果最近几次已多次执行相同 action+parameter，则强制切换为 answer_question
        if action in {"execute_service", "read_files", "query_knowledge"}:
            try:
                raw_param = action_data.get("parameter") or {}
                new_key = (
                    action,
                    json.dumps(raw_param, sort_keys=True, ensure_ascii=False),
                )
                max_repeat = 3
                recent = decision_history[-max_repeat:]
                same_count = 0
                for d in recent:
                    if d.get("action") != action:
                        continue
                    prev_param = d.get("parameter") or {}
                    prev_key = (
                        action,
                        json.dumps(prev_param, sort_keys=True, ensure_ascii=False),
                    )
                    if prev_key == new_key:
                        same_count += 1
                if same_count >= max_repeat:
                    logger.info(
                        "重复动作过多，强制切换为 answer_question",
                        extra={
                            "action": action,
                            "parameter": raw_param,
                            "repeat_count": same_count,
                        },
                    )
                    action = "answer_question"
            except Exception as e:  # noqa: BLE001 - 去重异常不影响主流程
                logger.warning("决策去重逻辑异常，已忽略: %s", e, exc_info=True)

        if action == "answer_question":
            break
        else:
            # 构建 interrupt 数据，包含 action 和 parameter
            interrupt_data: dict[str, Any] = {
                "action": action,
            }
            
            # 根据不同的 action 添加相应的 parameter
            if action == "execute_service":
                parameter = action_data.get("parameter", {})
                interrupt_data["parameter"] = {
                    "file_ids": parameter.get("file_ids", []),
                    "query": parameter.get("query", ""),
                }
            elif action == "read_files":
                parameter = action_data.get("parameter", {})
                interrupt_data["parameter"] = {
                    "file_ids": parameter.get("file_ids", []),
                    "recursive": parameter.get("recursive", False),
                    "query": parameter.get("query", ""),
                }
            elif action == "query_knowledge":
                parameter = action_data.get("parameter", {})
                interrupt_data["parameter"] = {
                    "query": parameter.get("query", ""),
                }
            
            # 添加 reasoning 到 interrupt_data 和决策历史
            reasoning = action_data.get("reasoning", "")
            interrupt_data["reasoning"] = reasoning
            
            result = interrupt(interrupt_data)
            
            # 保存决策历史
            decision_history_item: DecisionHistoryItem = {
                "action": action,
                "parameter": interrupt_data.get("parameter"),
                "reasoning": reasoning,
                "result": result,
            }
            decision_history.append(decision_history_item)

    # 生成最终回答前，再次根据 context_file_ids 获取最新文件树
    files_tree_list: list[dict[str, Any]] = get_context_files_tree_list(
        user_id=user_id,
        project_id=project_id,
        context_file_ids=context_file_ids,
        recursive=True,
        phase="answer",
    )

    answer_prompt = _build_answer_prompt(
        # 这里传入原始的用户问题，而非执行计划
        user_message=original_user_message,
        conversation_history=conversation_history,
        files_tree_list=files_tree_list,
        decision_history=decision_history,
        language=language,
    )
    # 根据语言选择回答阶段的 system 提示
    lang = "en" if str(language).lower().startswith("en") else "zh"
    if lang == "en":
        answer_system_content = (
            "You are a professional AI assistant. Based on the provided information, "
            "generate a clear, accurate, and comprehensive answer for the user."
        )
    else:
        answer_system_content = (
            "你是一个专业的AI助手，负责回答用户问题。请根据提供的信息生成清晰、准确、完整的回答。"
        )
    answer_request = LLMRequest(
        messages=[
            {"role": "system", "content": answer_system_content},
            {"role": "user", "content": answer_prompt},
        ],
        temperature=0.3,
        max_tokens=32000,
    )
    answer_response = llm_client.chat(answer_request)
    answer_data = extract_json_from_response(answer_response.content)
    answer = answer_data.get("final_answer", "")
    
    # 返回结果，标记完成（不interrupt）
    return {
        "final_answer": answer,
    }
    

def _build_decision_prompt(
    user_message: str,
    conversation_history: list[dict[str, Any]],
    files_tree_list: list[dict[str, Any]],
    decision_history: list[DecisionHistoryItem],
    language: str = "zh",
) -> str:
    """构建决策提示。
    
    强调：在每一轮决策中，必须综合参考「已有决策历史及其执行结果」，
    避免在没有新信息的情况下重复执行同样的无效动作，应基于上一次执行
    的 outcome 调整下一步动作选择。
    """
    
    lang = "en" if str(language).lower().startswith("en") else "zh"

    history_summary = ""
    if conversation_history:
        recent = conversation_history[-3:]  # 最近3轮对话
        history_summary = "\n".join([
            f"{msg.get('role', 'user')}: {msg.get('content', '')}"
            for msg in recent
        ])
    
    files_summary = ""
    if files_tree_list:
        # 统计文件总数
        total_files = _count_files_in_tree(files_tree_list)
        # 格式化树形结构
        tree_str = format_file_tree(files_tree_list, language=lang)
        files_summary = (
            f"\nProject file tree (total {total_files} files/dirs):\n{tree_str}"
            if lang == "en"
            else f"\n项目文件树结构（共 {total_files} 个文件/目录）：\n{tree_str}"
        )
    
    decision_history_summary = ""
    if decision_history:
        decision_history_summary = "\nDecision history:" if lang == "en" else "\n决策历史："
        for idx, decision in enumerate(decision_history[-5:], 1):
            action = decision.get("action", "unknown")
            parameter = decision.get("parameter")
            reasoning = decision.get("reasoning", "")
            result = decision.get("result")
            # 格式化参数信息
            param_str = ""
            if parameter:
                if action == "execute_service":
                    file_ids = parameter.get("file_ids", [])
                    query = parameter.get("query", "")
                    param_str = f"file_ids={file_ids}, query={query[:50]}..." if len(query) > 50 else f"file_ids={file_ids}, query={query}"
                elif action == "read_files":
                    file_ids = parameter.get("file_ids", [])
                    recursive = parameter.get("recursive", False)
                    query = parameter.get("query", "")
                    base = f"file_ids={file_ids}, recursive={recursive}"
                    if query:
                        param_str = base + (f", query={query[:50]}..." if len(query) > 50 else f", query={query}")
                    else:
                        param_str = base
                elif action == "query_knowledge":
                    query = parameter.get("query", "")
                    param_str = f"query={query[:50]}..." if len(query) > 50 else f"query={query}"
            # 截断长理由
            reasoning_str = reasoning
            # 格式化结果信息
            result_str = ""
            if result:
                # 直接使用完整结果，不截取
                if isinstance(result, str):
                    result_str = result
                else:
                    result_str = str(result)
            
            # 构建决策历史项
            decision_line = f"\n  {idx}. {action}"
            if param_str:
                decision_line += f" ({param_str})"
            decision_line += f": {reasoning_str}"
            if result_str:
                result_label = "Result" if lang == "en" else "结果"
                decision_line += f"\n    {result_label}: {result_str}"
            decision_history_summary += decision_line
    
    if lang == "en":
        prompt = f"""
Decide the next action based on the following information.
You MUST carefully review the previous decisions and their execution results,
avoid repeating the same failing or ineffective action without new information,
and adjust your next action according to the latest outcomes:

Execution plan:
{user_message}

Conversation history:
{history_summary or "None"}

{files_summary}

{decision_history_summary}

Choose the next action. Available actions:
1. execute_service - run a service to analyze
2. read_files - read project files
3. query_knowledge - query the knowledge base
4. answer_question - information is enough to answer now

Return JSON according to the action chosen:

When choosing an action, you MUST:
1. Explicitly consider the latest execution result(s) in the decision history.
2. Avoid looping on the same failing configuration; instead, change parameters or choose another action.
3. Only choose execute_service or read_files again if you have a clear new hypothesis or different parameters.

For execute_service:
{{
    "action": "execute_service",
    "parameter": {{
        "file_ids": ["file_id1", "file_id2", ...],
        "query": "analysis query or description"
    }},
    "reasoning": "brief explanation of why this action is chosen"
}}

For read_files:
{{
    "action": "read_files",
    "parameter": {{
        "file_ids": ["file_id1", "file_id2", ...],
        "recursive": true or false,
        "query": "what you want to read/inspect in these files"
    }},
    "reasoning": "brief explanation of why this action is chosen"
}}

For query_knowledge:
{{
    "action": "query_knowledge",
    "parameter": {{
        "query": "knowledge base query"
    }},
    "reasoning": "brief explanation of why this action is chosen"
}}

For answer_question:
{{
    "action": "answer_question",
    "reasoning": "brief explanation of why information is sufficient to answer now"
}}
""".strip()
    else:
        prompt = f"""
基于以下信息，决定下一步动作。
你必须认真审视「已有的决策历史以及对应的执行结果」，在没有新信息时，
避免再次执行同样的、已经失败或无效的动作，而是要根据最新的执行结果
来调整下一步的动作选择，并遵循与整体执行计划一致的动作类型和顺序约束：

执行计划：
{user_message}

对话历史：
{history_summary or "无"}

{files_summary}

{decision_history_summary}
        
请决定**当前这一步**的基础动作类型。你只能在以下三类基础动作中进行选择，这三类动作在整体执行流程中应当遵循“先服务执行 → 再文件读取与分析 → 最后文献与知识查询”的顺序，不得在已经进入后续阶段后再回到前面的阶段：
1. **execute_service（服务执行）**：调用现有的数据分析或处理服务，并基于已有或中间产生的数据执行这些服务以获得结果
2. **read_files（文件读取与分析）**：对已有文件进行读取、解析和分析，并对其内容和结果进行适当的解读
3. **query_knowledge（文献与知识查询）**：对于需要科研文献或外部知识支撑的内容，从外部知识库中检索并获取相关信息
4. **answer_question（回答问题）**：当前信息已经足够，可以直接给出对用户问题的完整回答，而无需再执行新的服务、读取文件或查询知识
        
在选择动作时，你必须同时满足以下约束：
1. 必须明确参考最近一次及历史执行结果，再做决策，保证动作选择与当前进度和已有结果一致；
2. 在参数完全相同且没有新信息的情况下，避免重复执行已经失败或明显无效的动作；
3. 只有在你有新的假设、不同的参数设置或新增的文件/知识来源时，才再次选择 execute_service 或 read_files；
4. 在整体流程上，已经开始“文献与知识查询”（query_knowledge）后，不得再新增“服务执行”（execute_service）或“文件读取与分析”（read_files）动作；
5. 如果现有的信息和结果已经足以形成对用户问题的清晰回答，应优先选择 answer_question，而不是继续追加新的执行步骤。

请根据选择的动作返回对应的JSON格式：

对于 execute_service：
{{
    "action": "execute_service",
    "parameter": {{
        "file_ids": ["文件id1", "文件id2", ...],
        "query": "分析查询或描述"
    }},
    "reasoning": "选择此动作的简要说明"
}}

对于 read_files：
{{
    "action": "read_files",
    "parameter": {{
        "file_ids": ["文件id1", "文件id2", ...],
        "recursive": true 或 false,
        "query": "你希望在这些文件中阅读或分析的内容"
    }},
    "reasoning": "选择此动作的简要说明"
}}

对于 query_knowledge：
{{
    "action": "query_knowledge",
    "parameter": {{
        "query": "知识库查询"
    }},
    "reasoning": "选择此动作的简要说明"
}}

对于 answer_question：
{{
    "action": "answer_question",
    "reasoning": "说明为什么当前信息足够回答问题的简要说明"
}}
""".strip()
    
    return prompt


def _build_answer_prompt(
    user_message: str,
    conversation_history: list[dict[str, Any]],
    files_tree_list: list[dict[str, Any]],
    decision_history: list[DecisionHistoryItem],
    language: str = "zh",
) -> str:
    """构建结果问答提示（此处的 user_message 为原始用户问题/需求）"""
    
    lang = "en" if str(language).lower().startswith("en") else "zh"

    # 整理文件信息（保持树形结构）
    files_info = ""
    if files_tree_list:
        # 统计文件总数
        total_files = _count_files_in_tree(files_tree_list)
        # 格式化树形结构
        tree_str = format_file_tree(files_tree_list, language=lang)
        files_info = (
            f"\nProject file tree (total {total_files} files/dirs):\n{tree_str}"
            if lang == "en"
            else f"\n项目文件树结构（共 {total_files} 个文件/目录）：\n{tree_str}"
        )
    
    # 整理决策历史
    decision_info = ""
    if decision_history:
        decision_info = "\nDecision history:\n" if lang == "en" else "\n决策历史：\n"
        for idx, decision in enumerate(decision_history, 1):
            action = decision.get("action", "unknown")
            parameter = decision.get("parameter")
            reasoning = decision.get("reasoning", "")
            # 格式化参数信息
            param_str = ""
            if parameter:
                if action == "execute_service":
                    file_ids = parameter.get("file_ids", [])
                    query = parameter.get("query", "")
                    param_str = f"file_ids={file_ids}, query={query}"
                elif action == "read_files":
                    file_ids = parameter.get("file_ids", [])
                    recursive = parameter.get("recursive", False)
                    query = parameter.get("query", "")
                    base = f"file_ids={file_ids}, recursive={recursive}"
                    if query:
                        param_str = base + f", query={query}"
                    else:
                        param_str = base
                elif action == "query_knowledge":
                    query = parameter.get("query", "")
                    param_str = f"query={query}"
            decision_info += f"\n{idx}. {action}" + (f" ({param_str})" if param_str else "") + f": {reasoning}\n"
    
    # 整理对话历史
    history_info = ""
    if conversation_history:
        history_info = "\nConversation history:\n" if lang == "en" else "\n对话历史：\n"
        for msg in conversation_history[-5:]:  # 最近5轮对话
            role = msg.get("role", "user")
            content = msg.get("content", "")
            history_info += f"{role}: {content}\n"
    
    if lang == "en":
        prompt = f"""
Answer the user's requirement based on the original user query and collected information:

User query:
{user_message}

{history_info}

{files_info}

{decision_info}

Please provide a clear, accurate, and complete answer. The answer should:
1. Directly address the question
2. Cite related file info or decision history when helpful
3. Use clear structure for readability

Return JSON:
{{
    "final_answer": "your answer"
}}
""".strip()
    else:
        prompt = f"""
基于以下原始用户问题和收集到的中间结果，为用户生成最终总结性回答：

用户问题：
{user_message}

{history_info}

{files_info}

{decision_info}

请根据以上信息，为用户提供一个清晰、准确、完整的回答。回答应该：
1. 直接回答用户的问题
2. 引用相关的文件信息或决策历史作为依据
3. 使用清晰的结构和格式，便于用户理解

以JSON格式返回回答：
{{
    "final_answer": "回答内容"
}}
""".strip()
    
    return prompt


# 构建图
builder = StateGraph(UserProxyState)
builder.add_node("decision", decision_node)
builder.add_edge(START, "decision")
builder.add_edge("decision", END)

# 使用内存checkpoint
checkpointer = MemorySaver()
graph = builder.compile(checkpointer=checkpointer)


def run_user_proxy_agent(
    plan: str,
    user_message: str,
    user_id: str,
    project_id: str,
    thread_id: str,
    conversation_history: list[dict[str, Any]] | None = None,
    context_file_ids: list[str] | None = None,
    decision_history: list[DecisionHistoryItem] | None = None,
    language: str | None = None,
) -> dict[str, Any]:
    """
    运行用户代理Agent，根据执行计划进行动作决策和反思
    
    Args:
        plan: 执行计划文本（由意图解析器生成）
        user_message: 原始用户问题/查询
        user_id: 用户ID
        project_id: 项目ID
        thread_id: 线程ID（用于langgraph checkpoint恢复，格式：user_id + project_id + uuid）
        conversation_history: 对话历史
        context_file_ids: 上下文文件ID列表（由外部传入，每轮基于此获取文件树）
        decision_history: 决策历史（可选，显式传入）
        language: 语言代码（"zh" 或 "en"），默认根据上游逻辑决定；不传则默认为中文
        
    Returns:
        包含__interrupt__或最终结果的字典
    """
    config = {"configurable": {"thread_id": thread_id}}
    
    # 构建初始状态（仅包含指定字段）
    initial_state: UserProxyState = {
        "user_id": user_id,
        "project_id": project_id,
        "context_file_ids": context_file_ids or [],
        # 将执行计划文本存入 user_message 字段，供决策提示使用
        "user_message": plan,
        # 保存原始用户问题，供最终回答提示使用
        "original_user_message": user_message,
        "conversation_history": conversation_history or [],
        "decision_history": decision_history or [],
    }
    if language:
        initial_state["language"] = language
    
    # 首次调用，会触发interrupt
    result = graph.invoke(initial_state, config=config)
    return result


def resume_user_proxy_agent(
    result: str,
    thread_id: str,
) -> dict[str, Any]:
    """
    恢复用户代理Agent执行
    
    Args:
        result: 动作执行结果（字符串）
        thread_id: 线程ID（用于langgraph checkpoint恢复，格式：user_id + project_id + uuid）
    Returns:
        包含__interrupt__或最终结果的字典
    """
    config = {"configurable": {"thread_id": thread_id}}
    # 直接基于现有状态恢复执行（文件树在 decision_node 内按需获取）
    return graph.invoke(Command(resume=result), config=config)
    