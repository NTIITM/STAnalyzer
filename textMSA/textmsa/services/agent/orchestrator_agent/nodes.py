"""
Orchestrator Agent 节点实现
"""

from __future__ import annotations

import json
import re
from typing import Any

from langgraph.types import interrupt

from textmsa.logging_config import get_logger
from textmsa.services.agent.agent_utils import (
    extract_json_from_response,
    format_file_tree,
    get_context_files_tree_list,
    get_llm_client_instance,
)
from textmsa.services.agent.langgraph.state import StateUpdate
from textmsa.services.agent.llm_client import LLMRequest
from .prompts import (
    build_answer_prompt,
    build_decision_prompt,
    ORCHESTRATOR_INTENT_PARSING_PROMPT,
)
from .state import DecisionHistoryItem, OrchestratorAgentState

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


def _detect_language_from_query(user_query: str) -> str:
    """根据用户查询内容简单检测语言（中文 / 英文）。"""
    for ch in user_query:
        # 简单判断 CJK 统一表意字符范围
        if "\u4e00" <= ch <= "\u9fff":
            return "zh"
    return "en"


def parse_intent_and_generate_plan_for_orchestrator(
    user_query: str,
    context_file_ids: list[str],
    user_id: str,
    project_id: str | None = None,
    language: str | None = None,
) -> dict[str, Any]:
    """
    为 Orchestrator Agent 解析用户意图并生成执行计划
    
    Args:
        user_query: 用户查询
        context_file_ids: 上下文文件ID列表
        user_id: 用户ID
        project_id: 项目ID（可选）
        language: 语言（"zh" 或 "en"），默认为根据 user_query 自动检测
    
    Returns:
        包含意图解析结果和执行计划的字典：
        {
            "intent": str,      # 用户意图描述
            "plan": str,        # 整体执行计划的详细描述（字符串）
            "reasoning": str,   # 生成此计划的思考过程
            "language": str     # 检测到的语言
        }
    """
    # 如果未显式传入 language，则根据用户查询自动检测
    if language is None:
        language = _detect_language_from_query(user_query)
    lang = _normalize_language(language)
    
    logger.info(
        "Starting orchestrator intent parsing",
        extra={
            "user_id": user_id,
            "project_id": project_id,
            "context_file_ids_count": len(context_file_ids),
            "language": lang,
        },
    )
    
    # 获取文件树结构
    files_tree_list: list[dict[str, Any]] = get_context_files_tree_list(
        user_id=user_id,
        project_id=project_id,
        context_file_ids=context_file_ids,
        recursive=True,
    )
    
    # 格式化文件树
    files_tree_string = format_file_tree(files_tree_list, language=lang)
    if not files_tree_string:
        files_tree_string = "（暂无文件）" if lang == "zh" else "(No files)"
    
    # 构建 prompt
    prompt_template = ORCHESTRATOR_INTENT_PARSING_PROMPT.get(
        lang, ORCHESTRATOR_INTENT_PARSING_PROMPT["zh"]
    )
    prompt = prompt_template.format(
        user_query=user_query,
        files_tree_string=files_tree_string,
    )
    
    # 调用大模型生成计划
    llm_client = get_llm_client_instance()
    request = LLMRequest(
        messages=[
            {
                "role": "system",
                "content": (
                    "你是一个专业的意图解析助手，负责分析用户需求并生成详细的执行计划。请严格按照JSON格式返回结果。"
                    if lang == "zh"
                    else "You are a professional intent parsing assistant responsible for analyzing user requirements and generating detailed execution plans. Please return results strictly in JSON format."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,
        max_tokens=32000,
    )
    
    try:
        response = llm_client.chat(request)
        result = extract_json_from_response(response.content)
        
        # 确保 plan 是字符串格式
        plan = result.get("plan", "")
        if not isinstance(plan, str):
            plan = str(plan)
        
        intent = result.get("intent", "")
        reasoning = result.get("reasoning", "")
        
        logger.info(
            "Orchestrator intent parsing completed",
            extra={
                "intent": intent,
                "plan_length": len(plan),
                "language": lang,
            },
        )
        
        return {
            "intent": intent,
            "plan": plan,
            "reasoning": reasoning,
            "language": lang,
        }
    except Exception as e:
        logger.error(
            "Failed to parse intent and generate plan",
            extra={"error": str(e)},
            exc_info=True,
        )
        # 返回默认计划
        default_plan = (
            "分析用户查询，根据需要执行服务或查询知识库，然后生成回答。"
            if lang == "zh"
            else "Analyze user query, execute services or query knowledge base as needed, then generate answer."
        )
        return {
            "intent": user_query[:100],
            "plan": default_plan,
            "reasoning": f"Failed to generate plan: {str(e)}",
            "language": lang,
        }


def intent_plan_node(state: OrchestratorAgentState) -> StateUpdate:
    """
    意图解析和计划生成节点
    
    调用 parse_intent_and_generate_plan 生成意图和计划
    """
    user_query = state.get("user_query", "")
    context_file_ids = state.get("context_file_ids", [])
    user_id = state.get("user_id", "")
    project_id = state.get("project_id", "")
    language = state.get("language", "zh")
    
    logger.info(
        "Starting intent parsing and plan generation",
        extra={
            "user_id": user_id,
            "project_id": project_id,
            "context_file_ids_count": len(context_file_ids),
        },
    )
    
    # 调用 orchestrator 专用的意图解析器
    intent_plan_result = parse_intent_and_generate_plan_for_orchestrator(
        user_query,
        context_file_ids,
        user_id,
        project_id,
        language,
    )
    
    intent = intent_plan_result.get("intent", "")
    plan = intent_plan_result.get("plan", "")
    detected_language = intent_plan_result.get("language", language)
    
    logger.info(
        "Intent parsing completed",
        extra={
            "intent": intent,
            "plan_length": len(plan),
            "detected_language": detected_language,
        },
    )
    
    return {
        "intent": intent,
        "plan": plan,
        "language": detected_language,
    }


def decision_node(state: OrchestratorAgentState) -> StateUpdate:
    """
    决策节点：基于执行计划、历史信息和文件上下文，决定下一步动作
    
    在 while True 循环中决策：
    - 如果是 execute_service 或 query_knowledge，则 interrupt 出去
    - 如果是 answer_question，则生成回答并返回结果（不 interrupt，标记完成）
    
    可能的动作：
    - execute_service: 执行服务
    - query_knowledge: 查询知识库
    - answer_question: 回答用户问题（当信息足够时）
    """
    user_id = state.get("user_id", "")
    project_id = state.get("project_id", "")
    context_file_ids = state.get("context_file_ids", [])
    user_query = state.get("user_query", "")
    plan = state.get("plan", "")
    decision_history = state.get("decision_history", [])
    language = state.get("language", "zh")
    execution_feedback = state.get("execution_feedback")
    knowledge_feedback = state.get("knowledge_feedback")
    
    count = 0
    while True:
        count += 1
        if count > 10:
            logger.warning("Decision loop exceeded max iterations, forcing answer_question")
            break
        
        # 每轮决策前，从最后一个决策历史项中提取反馈信息
        current_execution_feedback = execution_feedback
        current_knowledge_feedback = knowledge_feedback
        if decision_history:
            last_decision = decision_history[-1]
            last_action = last_decision.get("action", "")
            last_result = last_decision.get("result", "")
            
            if last_action == "execute_service" and last_result:
                # 解析执行反馈（格式：__EXECUTION_FEEDBACK_START__{feedback}__EXECUTION_FEEDBACK_END__）
                match = re.search(
                    r"__EXECUTION_FEEDBACK_START__(.*?)__EXECUTION_FEEDBACK_END__",
                    last_result,
                    re.DOTALL,
                )
                if match:
                    current_execution_feedback = match.group(1)
                else:
                    # 如果没有特殊标记，使用整个 result（向后兼容）
                    current_execution_feedback = last_result
            elif last_action == "query_knowledge" and last_result:
                # 解析知识查询反馈（格式：__KNOWLEDGE_FEEDBACK_START__{feedback}__KNOWLEDGE_FEEDBACK_END__）
                match = re.search(
                    r"__KNOWLEDGE_FEEDBACK_START__(.*?)__KNOWLEDGE_FEEDBACK_END__",
                    last_result,
                    re.DOTALL,
                )
                if match:
                    current_knowledge_feedback = match.group(1)
                else:
                    # 如果没有特殊标记，使用整个 result（向后兼容）
                    current_knowledge_feedback = last_result
        
        # 每轮决策前，根据 context_file_ids 获取最新文件树
        files_tree_list: list[dict[str, Any]] = get_context_files_tree_list(
            user_id=user_id,
            project_id=project_id,
            context_file_ids=context_file_ids,
            recursive=True,
        )
        
        # 构建决策提示
        decision_prompt = build_decision_prompt(
            plan=plan,
            user_query=user_query,
            files_tree_list=files_tree_list,
            decision_history=decision_history,
            execution_feedback=current_execution_feedback,
            knowledge_feedback=current_knowledge_feedback,
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
            max_tokens=32000,
        )
        response = llm_client.chat(request)
        action_data = extract_json_from_response(response.content)
        action = action_data.get("action", "")
        
        # 简单去重：如果最近几次已多次执行相同 action+parameter，则强制切换为 answer_question
        if action in {"execute_service", "query_knowledge"}:
            try:
                raw_param = action_data.get("parameter") or {}
                new_key = (
                    action,
                    json.dumps(raw_param, sort_keys=True, ensure_ascii=False),
                )
                max_repeat = 5
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
            except Exception as e:  # noqa: BLE001
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
            elif action == "query_knowledge":
                parameter = action_data.get("parameter", {})
                interrupt_data["parameter"] = {
                    "query": parameter.get("query", ""),
                }
            
            # 添加 reasoning 到 interrupt_data
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
    )
    
    answer_prompt = build_answer_prompt(
        user_query=user_query,
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
    
    llm_client = get_llm_client_instance()
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
    
    # 返回结果，标记完成（不 interrupt）
    return {
        "final_answer": answer,
    }

