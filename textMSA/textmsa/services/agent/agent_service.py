"""
RAG工作流服务
封装工作流调用，对接API层
"""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

from fastapi import HTTPException, status

from textmsa.logging_config import get_logger
from textmsa.services.data.user_data_manager_mongodb import (
    UserDataManagerMongoDB,
    get_user_data_manager,
)
from textmsa.services.agent.memory import MemoryController, SimpleMemoryController
from textmsa.services.knowledge_service import get_knowledge_search_service
from textmsa.services.agent.agent_utils import (
    get_llm_client_instance,
    extract_json_from_response,
)
from textmsa.services.agent.llm_client import LLMRequest

logger = get_logger(__name__)

# 默认错误消息
DEFAULT_ERROR_MESSAGE = "抱歉，处理您的消息时出现错误，请稍后再试。"

# ==================== 意图配置字典 ====================
INTENT_CONFIG = {
    "complex_query": {
        "description": "复合查询：需要执行多步骤生信分析过程的复杂情况.",
        "description_en": "Complex query: Complex processes requiring multi-step bioinformatics analysis.",
        "handler": "_handle_complex_query",
    },
    "query_knowledge": {
        "description": "查询知识库：用户想要查询科研文献",
        "description_en": "Query knowledge base: User wants to query research literature",
        "handler": "_handle_query_knowledge",
    },
    "read_files": {
        "description": "读取文件：用户想要读取、分析或理解文件内容，包括对数据进行统计分析的工作内容（如提取数据中前10的高可变基因、计算统计指标、数据筛选等）",
        "description_en": "Read files: User wants to read, analyze, or understand file content, including statistical analysis tasks on data (such as extracting top 10 highly variable genes, calculating statistical metrics, data filtering, etc.)",
        "handler": "_handle_read_files",
    },
    "read_files_and_query_knowledge": {
        "description": "读取文件并查询文献：用户想要读取文件后，根据文件解读内容检索相关科研文献",
        "description_en": "Read files and query knowledge: User wants to read files and then retrieve relevant research literature based on the file analysis content",
        "handler": "_handle_read_files_and_query_knowledge",
    },
    "execute_service": {
        "description": "执行服务：用户想要执行生信相关的分析过程，例如数据预处理、质量控制、归一化、聚类、差异表达分析、细胞类型注释、轨迹推断、空间结构域识别、配体-受体分析、通路富集分析等，并解读分析结果",
        "description_en": "Execute service: User wants to execute bioinformatics analysis processes, such as data preprocessing, quality control, normalization, clustering, differential expression analysis, cell type annotation, trajectory inference, spatial domain identification, ligand-receptor analysis, pathway enrichment analysis, etc., and interpret analysis results",
        "handler": "_handle_execute_service",
    },
    "general_chat": {
        "description": "通用对话：其他类型的对话或问题",
        "description_en": "General conversation: Other types of conversations or questions",
        "handler": "_handle_general_chat",
    },
}

class AgentService:
    """工作流服务"""
    
    def __init__(
        self,
        *,
        user_data_manager: UserDataManagerMongoDB | None = None,
        memory_controller: MemoryController | None = None,
        langgraph_runner: Callable[[dict[str, Any]], Any] | None = None,
    ) -> None:
        """
        初始化服务
        
        Args:
            user_data_manager: 用户数据管理器（可选，默认使用全局实例）
            memory_controller: 记忆控制器（可选，默认使用 SimpleMemoryController）
        """
        self.user_data_manager = user_data_manager or get_user_data_manager()
        self.memory_controller = memory_controller or SimpleMemoryController()
    
    def _build_execution_extra(self, execution_id: str) -> dict[str, Any]:
        """
        根据 execution_id 构建执行相关的结构化信息。
        
        包含：
        - 服务名、服务描述、服务状态
        - 输入/输出文件 ID 与文件名
        """
        from textmsa.services.service.service_service import get_service_service
        from textmsa.services.file.file_service import get_file_service

        execution_extra: dict[str, Any] = {"execution_id": execution_id}

        try:
            service_service = get_service_service()
            execution = service_service.get_execution(execution_id)
        except Exception as e:  # noqa: BLE001 - 这里仅做兜底日志
            logger.warning("获取执行记录失败: %s", e, exc_info=True)
            execution_extra["error"] = "execution_not_found"
            return execution_extra

        # 基础执行信息
        execution_extra.update(
            {
                "service_id": execution.get("service_id"),
                "service_name": execution.get("service_name"),
                "service_description": execution.get("service_description"),
                "status": execution.get("status"),
                "project_id": execution.get("project_id"),
                "created_at": execution.get("created_at"),
                "started_at": execution.get("started_at"),
                "completed_at": execution.get("completed_at"),
                "duration_seconds": execution.get("duration_seconds"),
            }
        )

        # 文件信息（仅暴露文件 ID + 文件名 + 描述，避免泄露过多内部字段）
        user_id = execution.get("user_id")
        input_file_ids: list[str] = execution.get("input_file_ids") or []
        output_file_ids: list[str] = execution.get("output_file_ids") or []

        input_files: list[dict[str, Any]] = []
        output_files: list[dict[str, Any]] = []

        if user_id:
            file_service = get_file_service()

            for fid in input_file_ids:
                try:
                    info = file_service.get_file_info(fid, user_id)
                except Exception:
                    logger.warning("获取输入文件信息失败: file_id=%s, execution_id=%s", fid, execution_id)
                    continue
                if not info:
                    continue
                input_files.append(
                    {
                        "file_id": info.get("file_id"),
                        "filename": info.get("filename"),
                        "description": info.get("description"),
                    }
                )

            for fid in output_file_ids:
                try:
                    info = file_service.get_file_info(fid, user_id)
                except Exception:
                    logger.warning("获取输出文件信息失败: file_id=%s, execution_id=%s", fid, execution_id)
                    continue
                if not info:
                    continue
                output_files.append(
                    {
                        "file_id": info.get("file_id"),
                        "filename": info.get("filename"),
                        "description": info.get("description"),
                    }
                )

        execution_extra["input_files"] = input_files
        execution_extra["output_files"] = output_files

        return execution_extra

    def build_message(
        self,
        *,
        message: str,
        role: str = "assistant",
        extra: Optional[dict[str, Any]] = None,
        message_id: Optional[str] = None,
        timestamp: Optional[float | datetime] = None,
    ) -> dict[str, Any]:
        """
        快速生成符合前端约定的消息结构（不持久化）。
        
        Args:
            role: user/assistant/system 等角色名称
            message: 文本内容
            extra: 附加结构化信息，默认空字典
            message_id: 可选自定义消息ID，默认自动生成
            timestamp: 时间戳（秒）或 datetime，默认当前时间
        
        Returns:
            dict: {message_id, role, message, time, extra}
        """
        if isinstance(timestamp, (int, float)):
            dt = datetime.utcfromtimestamp(timestamp)
        elif isinstance(timestamp, datetime):
            dt = timestamp
        else:
            dt = datetime.utcnow()

        merged_extra: dict[str, Any] = extra.copy() if extra else {}

        return {
            "message_id": message_id or str(uuid.uuid4()),
            "role": role,
            "message": message,
            "time": dt.isoformat(),
            "extra": merged_extra,
        }

    def build_text_message(
        self,
        *,
        role: str = "assistant",
        message: str,
        message_id: Optional[str] = None,
        timestamp: Optional[float | datetime] = None,
        extra: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        生成普通文本消息。
        """
        merged_extra = {"type": "text"}
        if extra:
            merged_extra.update(extra)
        return self.build_message(
            role=role,
            message=message,
            extra=merged_extra,
            message_id=message_id,
            timestamp=timestamp,
        )

    def build_message_with_execution(
        self,
        *,
        role: str = "assistant",
        message: str,
        execution_id: str,
        message_id: Optional[str] = None,
        timestamp: Optional[float | datetime] = None,
        extra: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        生成携带 Service 执行信息的消息。
        
        会将 execution 结构挂载到 extra["execution"]，避免与现有字段冲突。
        """
        merged_extra: dict[str, Any] = extra.copy() if extra else {}

        try:
            execution_extra = self._build_execution_extra(execution_id)
            merged_extra.setdefault("execution", execution_extra)
        except Exception as e:  # noqa: BLE001 - 仅记录日志，不影响主流程
            logger.warning("构建 execution extra 失败: %s", e, exc_info=True)

        return self.build_message(
            role=role,
            message=message,
            extra=merged_extra,
            message_id=message_id,
            timestamp=timestamp,
        )

    def build_code_message(
        self,
        *,
        role: str = "assistant",
        message: str,
        code: str,
        language: str = "python",
        message_id: Optional[str] = None,
        timestamp: Optional[float | datetime] = None,
        extra: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        生成包含代码片段的消息。
        """
        merged_extra = {
            "type": "code",
            "code": code,
            "language": language,
        }
        if extra:
            merged_extra.update(extra)
        return self.build_message(
            role=role,
            message=message,
            extra=merged_extra,
            message_id=message_id,
            timestamp=timestamp,
        )

    def build_files_message(
        self,
        *,
        role: str = "assistant",
        message: str,
        file_ids: list[str],
        user_id: Optional[str] = None,
        message_id: Optional[str] = None,
        timestamp: Optional[float | datetime] = None,
        extra: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        生成携带文件引用的消息。
        """
        files_info: list[dict[str, Any]] = []
        if user_id:
            for fid in file_ids:
                info = self.user_data_manager.get_file_info(user_id, fid)
                if not info:
                    continue
                files_info.append(
                    {
                        "file_id": info.get("file_id"),
                        "filename": info.get("filename"),
                        "description": info.get("description"),
                    }
                )

        merged_extra = {
            "type": "files",
        }
        if files_info:
            merged_extra["files"] = files_info
        if extra:
            merged_extra.update(extra)
        return self.build_message(
            role=role,
            message=message,
            extra=merged_extra,
            message_id=message_id,
            timestamp=timestamp,
        )

    def build_execution_message(
        self,
        *,
        role: str = "assistant",
        message: str,
        execution_id: str,
        message_id: Optional[str] = None,
        timestamp: Optional[float | datetime] = None,
        extra: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        生成携带 Service 执行信息的消息。

        extra 中会包含：
        - type: "execution"
        - execution: { execution_id, service_name, service_description, status, input_files, output_files, ... }
        """
        merged_extra = {"type": "execution"}
        if extra:
            merged_extra.update(extra)
        return self.build_message_with_execution(
            role=role,
            message=message,
            execution_id=execution_id,
            message_id=message_id,
            timestamp=timestamp,
            extra=merged_extra,
        )

    def build_literature_message(
        self,
        *,
        role: str = "assistant",
        message: str,
        literatures: list[dict[str, Any]],
        message_id: Optional[str] = None,
        timestamp: Optional[float | datetime] = None,
        extra: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        生成携带文献信息的消息。

        Args:
            role: user/assistant/system 等角色名称
            message: 文本内容
            literatures: 文献列表，每个文献对象应包含 title, snippet 等属性
                        可选属性：url, doi
            message_id: 可选自定义消息ID，默认自动生成
            timestamp: 时间戳（秒）或 datetime，默认当前时间
            extra: 附加结构化信息，默认空字典

        Returns:
            dict: {message_id, role, message, time, extra}
            
        extra 中会包含：
        - type: "literature"
        - literatures: [{title, snippet, url, doi}, ...]
        """
        # 构建文献信息列表
        literatures_info: list[dict[str, Any]] = []
        for lit in literatures:
            lit_info: dict[str, Any] = {}
            # 必需字段
            if "title" in lit:
                lit_info["title"] = lit["title"]
            if "snippet" in lit:
                lit_info["snippet"] = lit["snippet"]
            # 可选字段：只保留 url 和 doi
            if "url" in lit:
                lit_info["url"] = lit["url"]
            if "doi" in lit:
                lit_info["doi"] = lit["doi"]
            
            if lit_info:  # 只添加非空的文献信息
                literatures_info.append(lit_info)

        merged_extra = {
            "type": "literature",
        }
        if literatures_info:
            merged_extra["literatures"] = literatures_info
        if extra:
            merged_extra.update(extra)
        
        return self.build_message(
            role=role,
            message=message,
            extra=merged_extra,
            message_id=message_id,
            timestamp=timestamp,
        )

    def _build_evidence_sources(self, state: dict[str, Any]) -> list[dict[str, Any]]:
        """
        从工作流状态中提取证据来源信息
        
        Args:
            state: 工作流最终状态
        
        Returns:
            证据来源列表
        """
        sources = []
        
        # 私有知识来源
        for evidence in state.get("private_knowledge_evidence", []):
            sources.append(
                {
                "type": "private_knowledge",
                "source_id": evidence.source_id,
                "priority": evidence.priority,
                "confidence": evidence.confidence,
                }
            )
        
        # 实验来源
        experiment_tool_name = state.get("experiment_tool_name")
        for evidence in state.get("experiment_evidence", []):
            sources.append(
                {
                "type": "experiment",
                "source_id": evidence.source_id,
                "tool_name": experiment_tool_name,
                "priority": evidence.priority,
                "confidence": evidence.confidence,
                }
            )
        
        # 文献来源
        for evidence in state.get("literature_evidence", []):
            sources.append(
                {
                "type": "literature",
                "source_id": evidence.source_id,  # PMID
                "priority": evidence.priority,
                "confidence": evidence.confidence,
                }
            )
        
        return sources
    
    async def _ensure_conversation(
        self,
        user_id: str,
        project_id: str,
    ) -> str:
        """
        确保对话存在，如果不存在则创建

        Args:
            user_id: 用户ID
            project_id: 项目ID

        Returns:
            对话ID

        Raises:
            HTTPException: 如果无法创建或获取对话
        """
        try:
            # 使用数据层便捷接口（统一命名）
            conversation = self.user_data_manager.create_conversation(
                user_id=user_id,
                project_id=project_id,
            )
            return conversation.get("conversation_id", "")
        except Exception as e:
            logger.error(f"确保对话存在失败: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="无法创建或获取对话",
            )

    async def _get_conversation_history(
        self,
        user_id: str,
        project_id: str,
    ) -> list[dict[str, Any]]:
        """
        获取对话历史消息

        Args:
            user_id: 用户ID
            project_id: 项目ID

        Returns:
            消息列表，格式为 [{"role": "user|assistant", "content": "..."}, ...]
        """
        try:
            # 使用统一命名的便捷接口
            conversation = self.user_data_manager.get_conversation(project_id)
            if not conversation:
                return []

            messages = []
            for msg in conversation.get("messages", []):
                messages.append(
                    {
                        "role": msg.get("role", "user"),
                        "content": msg.get("message", ""),
                    }
                )
            return messages
        except Exception as e:
            logger.warning(f"获取对话历史失败: {e}", exc_info=True)
            return []

    async def _save_final_result(
        self,
        user_id: str,
        project_id: str,
        final_state: dict[str, Any],
    ) -> None:
        """
        保存工作流最终结果到数据库

        Args:
            user_id: 用户ID
            project_id: 项目ID
            final_state: 工作流最终状态，包含 final_answer 和 evidence_sources
        """
        try:
            answer = final_state.get("final_answer") or "抱歉，生成回答时出现错误。"
            execution_time = final_state.get("execution_time", 0.0)

            # 构建证据来源列表
            evidence_sources = self._build_evidence_sources(final_state)

            # 保存助手回复
            self.user_data_manager.add_agent_message(
                user_id=user_id,
                project_id=project_id,
                role="assistant",
                message=answer,
                extra={
                    "evidence_sources": evidence_sources,
                    "execution_time": execution_time,
                },
            )

            logger.info(
                f"保存最终结果成功 | 耗时: {execution_time:.2f}秒 | 证据数量: {len(evidence_sources)}"
            )
        except Exception as e:
            logger.warning(f"保存最终结果失败: {e}", exc_info=True)
            # 不中断流程，只记录警告

    def run_with_langgraph(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Execute the new LangGraph pipeline end-to-end.

        TODO: Replace legacy workflow invocation with this method once
        planner/knowledge/analyst subgraphs are ready.
        """

        return self.langgraph_runner(payload)

    def get_conversation(
        self,
        user_id: str,
        project_id: str,
    ) -> dict[str, Any]:
        """
        获取对话历史
        
        Args:
            user_id: 用户ID
            project_id: 项目ID
        
        Returns:
            对话信息，包含消息列表
        
        Raises:
            HTTPException: 如果项目不存在或用户无权限
        """
        try:
            # 优先获取现有会话
            conversation = self.user_data_manager.get_conversation(project_id)

            if not conversation:
                # 如果不存在，创建一个空的
                conversation = self.user_data_manager.create_conversation(
                    user_id=user_id,
                    project_id=project_id,
                )

            return conversation

        except Exception as e:
            logger.error(f"获取对话失败: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="获取对话失败"
            )
    
    def list_project_knowledge(
        self,
        user_id: str,
        project_id: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """
        列出项目的知识条目
        
        Args:
            user_id: 用户ID
            project_id: 项目ID
            limit: 返回的最大条目数（默认20）
        
        Returns:
            知识条目列表
        
        Raises:
            HTTPException: 如果项目不存在或用户无权限
        """
        project = self.user_data_manager.get_project(user_id, project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在"
            )
        
        knowledge_ids = project.get("knowledge_ids", [])
        items: list[dict[str, Any]] = []
        
        for knowledge_id in knowledge_ids[-limit:]:
            try:
                knowledge = self.user_data_manager.get_knowledge(user_id, knowledge_id)
            except Exception as exc:
                logger.warning("获取知识条目失败: %s", exc)
                continue
            if knowledge:
                items.append(knowledge)
        
        return items
    
    def clear_conversation(
        self,
        user_id: str,
        project_id: str,
    ) -> bool:
        """
        清空项目的对话内容
        
        Args:
            user_id: 用户ID
            project_id: 项目ID
        
        Returns:
            是否成功清空
        
        Raises:
            HTTPException: 如果项目不存在或用户无权限
        """
        try:
            # 验证项目存在
            project = self.user_data_manager.get_project(user_id, project_id)
            if not project:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在"
                )
            # 清空对话内容（统一命名便捷接口）
            success = self.user_data_manager.clear_conversation(
                user_id=user_id,
                project_id=project_id,
            )
            
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="清空对话内容失败"
                )
            
            return success
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"清空对话内容失败: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="清空对话内容失败"
            )

    async def save_conversation_message(
        self,
        *,
        user_id: str,
        project_id: str,
        role: str,
        content: str,
        extra: Optional[dict[str, Any]] = None,
        message_id: Optional[str] = None,
        time: Optional[datetime] = None,
        max_messages: Optional[int] = None,
    ) -> Optional[dict[str, Any]]:
        """
        将对话消息持久化到存储层。

        Notes:
            user_data_manager 使用阻塞 I/O，这里通过 asyncio.to_thread
            防止阻塞事件循环。
        """
        try:
            return await asyncio.to_thread(
                self.user_data_manager.add_agent_message,
                user_id,
                project_id,
                role,
                content,
                extra=extra,
                time=time,
                max_messages=max_messages,
                message_id=message_id,
            )
        except Exception as exc:  # noqa: BLE001 - 持久化失败不影响主流程
            logger.warning(
                "保存对话消息失败: %s",
                exc,
                exc_info=True,
                extra={
                    "user_id": user_id,
                    "project_id": project_id,
                    "role": role,
                },
            )
            return None

    def _build_intent_parsing_prompt(
        self,
        user_query: str,
        context_files: list[str] | None = None,
        language: str = "zh",
    ) -> str:
        """
        动态构建意图解析 Prompt，从 INTENT_CONFIG 自动生成
        
        Args:
            user_query: 用户查询
            context_files: 上下文文件ID列表（可选）
            language: 语言（"zh" 或 "en"）
        
        Returns:
            构建好的 Prompt 字符串
        """
        lang = "zh" if language.startswith("zh") else "en"
        desc_key = "description" if lang == "zh" else "description_en"
        
        # 构建可用意图类型列表
        intent_list = []
        for idx, (intent_key, config) in enumerate(INTENT_CONFIG.items(), 1):
            description = config.get(desc_key, config.get("description", ""))
            intent_list.append(f"{idx}. {intent_key} - {description}")
        
        intent_types_text = "\n".join(intent_list)
        
        # 构建上下文文件信息（如果有）
        context_info = ""
        if context_files:
            context_files_text = ", ".join(context_files)
            if lang == "zh":
                context_info = f"\n上下文文件ID: {context_files_text}"
            else:
                context_info = f"\nContext file IDs: {context_files_text}"
        
        # 构建 Prompt
        if lang == "zh":
            prompt = f"""你是一个智能意图解析助手，负责分析用户查询并识别用户的真实意图。

用户查询：{user_query}{context_info}

可用意图类型：
{intent_types_text}

请根据用户查询，识别最匹配的意图类型。

请严格按照以下 JSON 格式返回：
{{
  "intent": "意图类型（{"/".join(INTENT_CONFIG.keys())}）",
  "confidence": 0.95,  // 置信度 0-1
  "reasoning": "选择此意图的原因"
}}

请返回 JSON："""
        else:
            prompt = f"""You are an intelligent intent parsing assistant responsible for analyzing user queries and identifying user intent.

User query: {user_query}{context_info}

Available intent types:
{intent_types_text}

Please identify the most matching intent type based on the user query.

Return strictly in JSON format:
{{
  "intent": "Intent type ({"/".join(INTENT_CONFIG.keys())})",
  "confidence": 0.95,  // Confidence 0-1
  "reasoning": "Reason for choosing this intent"
}}

Return JSON:"""
        
        return prompt

    async def _parse_intent(
        self,
        user_query: str,
        context_files: list[str] | None = None,
        language: str = "zh",
    ) -> dict[str, Any]:
        """
        解析用户意图（仅做意图分类，不提取参数）
        
        Args:
            user_query: 用户查询
            context_files: 上下文文件ID列表（可选）
            language: 语言（"zh" 或 "en"）
        
        Returns:
            意图解析结果：
            {
                "intent": str,           # 意图类型
                "confidence": float,     # 置信度
                "reasoning": str         # 推理过程
            }
        """
        # 动态构建 Prompt（从 INTENT_CONFIG 自动生成）
        prompt = self._build_intent_parsing_prompt(
            user_query=user_query,
            context_files=context_files,
            language=language,
        )
        
        llm_client = get_llm_client_instance()
        request = LLMRequest(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,  # 降低温度以提高稳定性
            max_tokens=500,  # 只需要返回意图类型，减少token
        )
        
        try:
            response = llm_client.chat(request)
            result = extract_json_from_response(response.content)
            
            # 验证意图类型是否有效
            intent = result.get("intent", "")
            if intent not in INTENT_CONFIG:
                logger.warning(f"未知的意图类型: {intent}，使用 general_chat 作为兜底")
                intent = "general_chat"
                result["intent"] = intent
            
            logger.info(
                f"意图解析成功: intent={intent}, confidence={result.get('confidence', 0)}"
            )
            
            return {
                "intent": intent,
                "confidence": result.get("confidence", 0.5),
                "reasoning": result.get("reasoning", ""),
            }
        except Exception as e:
            logger.error(f"意图解析失败: {e}", exc_info=True)
            # 返回兜底意图
            return {
                "intent": "general_chat",
                "confidence": 0.0,
                "reasoning": f"解析失败，使用默认意图: {str(e)}",
            }

    async def _extract_recursive_flag(
        self,
        user_query: str,
        language: str = "zh",
    ) -> bool:
        """
        从用户查询中提取是否需要递归读取文件
        
        提取策略：
        1. 先进行关键词匹配（快速且准确）
        2. 如果关键词匹配不到，再使用 LLM + prompt 来提取
        
        Args:
            user_query: 用户查询
            language: 语言（"zh" 或 "en"）
        
        Returns:
            bool: 是否需要递归读取
        """
        # 1. 先进行关键词匹配
        if language == "zh":
            recursive_keywords = ["递归", "子目录", "所有文件", "全部文件", "所有子目录"]
        else:
            recursive_keywords = ["recursive", "subdirectory", "all files", "all subdirectories"]
        
        query_lower = user_query.lower()
        if any(keyword in query_lower for keyword in recursive_keywords):
            logger.info(f"通过关键词匹配检测到需要递归读取: {user_query}")
            return True
        
        # 2. 如果关键词匹配不到，使用 LLM + prompt 来提取
        try:
            llm_client = get_llm_client_instance()
            
            if language == "zh":
                prompt = f"""请分析以下用户查询，判断用户是否想要递归读取子目录中的文件。

用户查询：{user_query}

请只返回 JSON 格式，包含一个字段 "recursive"（布尔值）：
- 如果用户想要读取子目录中的文件，返回 {{"recursive": true}}
- 如果用户只想读取当前目录的文件，返回 {{"recursive": false}}

只返回 JSON，不要其他内容。"""
            else:
                prompt = f"""Please analyze the following user query to determine if the user wants to recursively read files in subdirectories.

User query: {user_query}

Please return only JSON format with one field "recursive" (boolean):
- If the user wants to read files in subdirectories, return {{"recursive": true}}
- If the user only wants to read files in the current directory, return {{"recursive": false}}

Return only JSON, no other content."""
            
            request = LLMRequest(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=100,
            )
            
            response = llm_client.chat(request)
            result = extract_json_from_response(response.content)
            
            recursive = result.get("recursive", False)
            logger.info(f"通过 LLM 提取到 recursive={recursive}: {user_query}")
            return recursive
            
        except Exception as e:
            logger.warning(f"使用 LLM 提取 recursive 参数失败: {e}，默认返回 False")
            return False

    async def _extract_query_from_file_analysis(
        self,
        file_analysis_result: str,
        user_query: str,
        language: str = "zh",
    ) -> str:
        """
        从文件分析结果中提取用于文献检索的查询关键词
        
        Args:
            file_analysis_result: 文件分析结果文本
            user_query: 原始用户查询（可选，用于指导提取）
            language: 语言（"zh" 或 "en"）
        
        Returns:
            str: 提取的查询关键词/查询语句
        """
        try:
            llm_client = get_llm_client_instance()
            
            if language == "zh":
                prompt = f"""请根据文件分析结果，提取用于检索相关科研文献的关键词或查询语句。

原始用户查询：{user_query}

文件分析结果：
{file_analysis_result}  # 限制长度避免token过多

请从文件分析结果中提取：
1. 关键的研究主题、方法、技术或概念
2. 相关的生物学术语、基因、蛋白质、疾病等
3. 研究领域或方向

请只返回 JSON 格式，包含一个字段 "query"（字符串）：
- 提取的关键词或查询语句，应该适合用于检索科研文献
- 如果无法提取，可以使用原始用户查询

只返回 JSON，不要其他内容。"""
            else:
                prompt = f"""Please extract keywords or query statements for retrieving relevant research literature based on the file analysis results.

Original user query: {user_query}

File analysis results:
{file_analysis_result}  # Limit length to avoid too many tokens

Please extract from the file analysis results:
1. Key research topics, methods, techniques, or concepts
2. Relevant biological terms, genes, proteins, diseases, etc.
3. Research fields or directions

Please return only JSON format with one field "query" (string):
- Extracted keywords or query statements suitable for retrieving research literature
- If extraction is not possible, use the original user query

Return only JSON, no other content."""
            
            request = LLMRequest(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=8000,
            )
            
            response = llm_client.chat(request)
            result = extract_json_from_response(response.content)
            
            query = result.get("query", user_query).strip()
            if not query:
                query = user_query.strip()
            
            logger.info(f"从文件分析结果中提取到查询: {query[:100]}...")
            return query
            
        except Exception as e:
            logger.warning(f"使用 LLM 从文件分析结果提取查询失败: {e}，使用原始查询")
            return user_query.strip()

    async def _handle_complex_query(
        self,
        user_id: str,
        project_id: str,
        user_query: str,
        context_files: list[str] | None = None,
        language: str = "zh",
        progress_cb: Optional[Callable[[dict], None]] = None,
    ) -> str:
        """
        处理复合查询意图（使用 Orchestrator Agent）
        
        这是一个复合意图，会执行完整的多步骤流程：
        1. 调用 orchestrator_agent（会触发 interrupt）
        2. 循环处理 interrupt（execute_service、query_knowledge）
        3. 返回最终答案
        
        Args:
            user_id: 用户ID
            project_id: 项目ID
            user_query: 原始用户查询
            context_files: 上下文文件ID列表（可选）
            language: 语言
            progress_cb: 进度回调函数
        
        Returns:
            处理结果（字符串）
        """
        try:
            from textmsa.services.agent.orchestrator_agent import (
                run_orchestrator_agent,
                resume_orchestrator_agent,
            )
            from textmsa.services.agent.report_agent import (
                astream_analysis_and_report_agent,
            )
            
            context_file_ids = context_files or []
            
            # 1. 生成thread_id：user_id + project_id + uuid
            thread_id = f"{user_id}{project_id}{uuid.uuid4().hex}"
            
            # 2. 首次调用 orchestrator_agent（会触发 interrupt）
            result = await asyncio.to_thread(
                run_orchestrator_agent,
                user_query=user_query,
                user_id=user_id,
                project_id=project_id,
                thread_id=thread_id,
                context_file_ids=context_file_ids,
                language=language,
            )
            
            # 从首次调用结果中获取检测到的语言
            detected_language = result.get("language", language)
            
            # 3. 循环处理interrupt，直到完成
            while True:
                if "final_answer" in result:
                    final_answer = result["final_answer"]
                    break
                
                interrupt_data = result["__interrupt__"][0].value
                if interrupt_data is None:
                    break
                
                # 有interrupt，需要处理
                action = interrupt_data.get("action", "")
                parameter = interrupt_data.get("parameter", {})
                reasoning = interrupt_data.get("reasoning", "")
                
                if progress_cb:
                    message = self.build_message(message=reasoning)
                    progress_cb(message)
                
                # 根据action执行相应的操作
                if action == "execute_service":
                    # 使用 parameter 中的 file_ids 和 query
                    file_ids = parameter.get("file_ids", [])
                    query = parameter.get("query") or user_query
                    
                    # 调用 Analysis and Report Agent
                    # 如果 query 为 None，函数会使用默认查询
                    analysis_result = await astream_analysis_and_report_agent(
                        user_id=user_id,
                        project_id=project_id,
                        context_files=file_ids,
                        language=detected_language,
                        user_query=query,
                        on_event=progress_cb,
                    )
                    
                    # 序列化执行反馈信息
                    report_data = analysis_result.get("report_data", {})
                    execution_feedback = self._serialize_execution_feedback(
                        report_data, detected_language
                    )
                    
                    # 将执行反馈和最终答案组合作为 result（使用特殊标记）
                    final_answer_text = analysis_result.get("final_answer", "")
                    result_text = (
                        f"{final_answer_text}\n\n"
                        f"__EXECUTION_FEEDBACK_START__{execution_feedback}__EXECUTION_FEEDBACK_END__"
                    )
                    
                elif action == "query_knowledge":
                    # 使用 parameter 中的 query
                    query = parameter.get("query", user_query)
                    # 调用 Knowledge Agent
                    from textmsa.services.agent.knowledge_agent import astream_knowledge_agent
                    
                    knowledge_result = await astream_knowledge_agent(
                        user_query=query,
                        project_id=project_id,
                        user_id=user_id,
                        language=detected_language,
                        on_event=progress_cb,
                    )
                    knowledge_answer = knowledge_result.get("final_answer", "")
                    # 使用特殊标记包装知识查询反馈
                    result_text = (
                        f"{knowledge_answer}\n\n"
                        f"__KNOWLEDGE_FEEDBACK_START__{knowledge_answer}__KNOWLEDGE_FEEDBACK_END__"
                    )
                else:
                    logger.warning(f"未知的action: {action}")
                    break
                
                # 恢复 orchestrator_agent 执行
                result = await asyncio.to_thread(
                    resume_orchestrator_agent,
                    result=result_text,
                    thread_id=thread_id,
                )
            message = self.build_message(message=final_answer)
            progress_cb(message)
            
            # 返回最终答案
            return final_answer
            
        except Exception as e:
            logger.error(f"处理复合查询意图失败: {e}", exc_info=True)
            error_msg = (
                f"处理复合查询时出现错误: {str(e)}"
                if language == "zh"
                else f"Error processing complex query: {str(e)}"
            )
            return error_msg
    
    def _serialize_execution_feedback(
        self, report_data: dict, language: str = "zh"
    ) -> str:
        """
        序列化执行反馈信息为易读的字符串
        
        Args:
            report_data: 从 astream_analysis_and_report_agent 获取的报告数据
            language: 语言（zh/en）
        
        Returns:
            序列化后的反馈字符串
        """
        lang = "en" if str(language).lower().startswith("en") else "zh"
        
        total_executions = report_data.get("total_executions", 0)
        successful_count = report_data.get("successful_count", 0)
        failed_count = report_data.get("failed_count", 0)
        executions = report_data.get("executions", [])
        
        if lang == "en":
            feedback_lines = [
                f"Execution Summary: {total_executions} total, {successful_count} successful, {failed_count} failed",
            ]
        else:
            feedback_lines = [
                f"执行摘要：共 {total_executions} 个执行，成功 {successful_count} 个，失败 {failed_count} 个",
            ]
        
        for idx, exec_data in enumerate(executions, 1):
            service_name = exec_data.get("service_name", "Unknown")
            status = exec_data.get("status", "")
            analysis = exec_data.get("analysis")
            error = exec_data.get("error")
            
            if lang == "en":
                feedback_lines.append(f"\n{idx}. {service_name} (Status: {status})")
                if analysis:
                    feedback_lines.append(f"   Analysis: {analysis[:300]}...")
                if error:
                    feedback_lines.append(f"   Error: {error}")
            else:
                feedback_lines.append(f"\n{idx}. {service_name}（状态：{status}）")
                if analysis:
                    feedback_lines.append(f"   分析：{analysis[:300]}...")
                if error:
                    feedback_lines.append(f"   错误：{error}")
        
        return "\n".join(feedback_lines)

    async def _handle_query_knowledge(
        self,
        user_id: str,
        project_id: str,
        user_query: str,
        context_files: list[str] | None = None,
        language: str = "zh",
        progress_cb: Optional[Callable[[dict], None]] = None,
    ) -> str:
        """
        处理知识查询意图
        
        Handler 负责从原始输入中提取和处理参数
        
        Args:
            user_id: 用户ID
            project_id: 项目ID
            user_query: 原始用户查询（Handler 从中提取 query 参数）
            context_files: 上下文文件ID列表（可选，Handler 可从中提取 file_ids）
            language: 语言
            progress_cb: 进度回调函数
        
        Returns:
            处理结果（字符串）
        """
        try:
            # Handler 负责参数提取：从 user_query 中提取查询内容
            query = user_query.strip()
            if not query:
                error_msg = (
                    "查询内容不能为空"
                    if language == "zh"
                    else "Query content cannot be empty"
                )
                logger.error(error_msg)
                return error_msg
            
            # 可选：记录关联的文件ID（如果有）
            if context_files:
                logger.info(f"知识查询关联文件: {context_files}")
            
            # 调用 Knowledge Agent
            from textmsa.services.agent.knowledge_agent import astream_knowledge_agent
            
            # 执行知识查询
            result = await astream_knowledge_agent(
                user_query=query,
                project_id=project_id,
                user_id=user_id,
                language=language,
                on_event=progress_cb,
            )
            
            # 提取最终答案
            final_answer = result.get("final_answer", "")
            
            if not final_answer:
                default_msg = (
                    "未能找到相关信息"
                    if language == "zh"
                    else "No relevant information found"
                )
                return default_msg
            
            logger.info(f"知识查询完成: query_length={len(query)}, answer_length={len(final_answer)}")
            return final_answer
            
        except Exception as e:
            logger.error(f"处理知识查询意图失败: {e}", exc_info=True)
            error_msg = (
                f"处理知识查询时出现错误: {str(e)}"
                if language == "zh"
                else f"Error processing knowledge query: {str(e)}"
            )
            return error_msg

    async def _handle_read_files(
        self,
        user_id: str,
        project_id: str,
        user_query: str,
        context_files: list[str] | None = None,
        language: str = "zh",
        progress_cb: Optional[Callable[[dict], None]] = None,
    ) -> str:
        """
        处理文件读取意图
        
        Handler 负责从原始输入中提取和处理参数
        
        Args:
            user_id: 用户ID
            project_id: 项目ID
            user_query: 原始用户查询（Handler 从中提取 query 参数）
            context_files: 上下文文件ID列表（Handler 从中提取 file_ids 和 recursive）
            language: 语言
            progress_cb: 进度回调函数
        
        Returns:
            处理结果（字符串）
        """
        try:
            from textmsa.services.agent.read_agent import astream_read_agent
            from textmsa.services.file.file_service import get_file_service
            
            # Handler 负责参数提取：
            # 1. 从 context_files 中提取 file_ids（如果没有，可能需要从 user_query 中解析）
            file_ids = context_files or []
            
            # 2. 从 user_query 中提取 recursive 参数（先关键词匹配，后 LLM 提取）
            recursive = await self._extract_recursive_flag(user_query, language)
            
            # 3. 构建查询内容（可以从 user_query 中提取或使用默认值）
            if not file_ids:
                error_msg = (
                    "请指定要读取的文件"
                    if language == "zh"
                    else "Please specify files to read"
                )
                logger.error(error_msg)
                return error_msg
            
            # 获取文件服务
            file_service = get_file_service()
            files_tree_list = await asyncio.to_thread(
                file_service.get_project_files_tree_list,
                project_id=project_id,
                user_id=user_id,
                context_files=file_ids,
                recursive=recursive,
                include_preview=True,
                include_path=True,
            )
            
            # 构建查询：使用 user_query 或默认提示
            default_query = (
                "请分析这些文件的内容和结构。"
                if language == "zh"
                else "Please analyze the content and structure of these files."
            )
            query = user_query.strip() or default_query
            
            # 调用 Read Agent
            result = await astream_read_agent(
                user_query=query,
                file_tree_list=files_tree_list,
                user_id=user_id,
                project_id=project_id,
                language=language,
                on_event=progress_cb,
            )
            
            final_answer = result.get("final_answer", "")
            return final_answer or default_query
            
        except Exception as e:
            logger.error(f"处理文件读取意图失败: {e}", exc_info=True)
            error_msg = (
                f"处理文件读取时出现错误: {str(e)}"
                if language == "zh"
                else f"Error processing file read: {str(e)}"
            )
            return error_msg

    async def _handle_read_files_and_query_knowledge(
        self,
        user_id: str,
        project_id: str,
        user_query: str,
        context_files: list[str] | None = None,
        language: str = "zh",
        progress_cb: Optional[Callable[[dict], None]] = None,
    ) -> str:
        """
        处理读取文件并查询文献意图
        
        工作流程：
        1. 读取文件：调用 Read Agent 分析文件内容
        2. 提取查询：从文件分析结果中提取用于文献检索的关键词/查询
        3. 查询文献：调用 Knowledge Agent 检索相关科研文献
        4. 组合结果：将文件分析结果和文献查询结果组合返回
        
        Args:
            user_id: 用户ID
            project_id: 项目ID
            user_query: 原始用户查询
            context_files: 上下文文件ID列表
            language: 语言
            progress_cb: 进度回调函数
        
        Returns:
            处理结果（字符串），包含文件分析结果和文献查询结果
        """
        try:
            from textmsa.services.agent.read_agent import astream_read_agent
            from textmsa.services.agent.knowledge_agent import astream_knowledge_agent
            from textmsa.services.file.file_service import get_file_service
            
            # 1. 读取文件
            file_ids = context_files or []
            if not file_ids:
                error_msg = (
                    "请指定要读取的文件"
                    if language == "zh"
                    else "Please specify files to read"
                )
                logger.error(error_msg)
                return error_msg
            
            # 提取 recursive 参数
            recursive = await self._extract_recursive_flag(user_query, language)
            
            # 获取文件服务
            file_service = get_file_service()
            files_tree_list = await asyncio.to_thread(
                file_service.get_project_files_tree_list,
                project_id=project_id,
                user_id=user_id,
                context_files=file_ids,
                recursive=recursive,
                include_preview=True,
                include_path=True,
            )
            
            # 构建文件读取查询
            default_read_query = (
                "请分析这些文件的内容和结构。"
                if language == "zh"
                else "Please analyze the content and structure of these files."
            )
            read_query = user_query.strip() or default_read_query
            
            # 通知用户开始读取文件
            if progress_cb:
                read_msg = (
                    "正在读取和分析文件..."
                    if language == "zh"
                    else "Reading and analyzing files..."
                )
                progress_cb(self.build_message(message=read_msg))
            
            # 调用 Read Agent
            read_result = await astream_read_agent(
                user_query=read_query,
                file_tree_list=files_tree_list,
                user_id=user_id,
                project_id=project_id,
                language=language,
                on_event=progress_cb,
            )
            
            file_analysis = read_result.get("final_answer", "")
            if not file_analysis:
                file_analysis = default_read_query
            
            # 2. 从文件分析结果中提取查询关键词
            if progress_cb:
                extract_msg = (
                    "正在从文件分析结果中提取文献检索关键词..."
                    if language == "zh"
                    else "Extracting literature search keywords from file analysis..."
                )
                progress_cb(self.build_message(message=extract_msg))
            
            knowledge_query = await self._extract_query_from_file_analysis(
                file_analysis_result=file_analysis,
                user_query=user_query,
                language=language,
            )
            
            # 3. 查询文献
            if progress_cb:
                query_msg = (
                    f"正在检索相关科研文献（查询：{knowledge_query[:50]}...）"
                    if language == "zh"
                    else f"Searching for relevant research literature (query: {knowledge_query[:50]}...)"
                )
                progress_cb(self.build_message(message=query_msg))
            
            # 调用 Knowledge Agent
            knowledge_result = await astream_knowledge_agent(
                user_query=knowledge_query,
                project_id=project_id,
                user_id=user_id,
                language=language,
                on_event=progress_cb,
            )
            
            literature_answer = knowledge_result.get("final_answer", "")
            if not literature_answer:
                literature_answer = (
                    "未能找到相关文献"
                    if language == "zh"
                    else "No relevant literature found"
                )
            
            # 4. 组合结果
            if language == "zh":
                combined_result = f"""## 文件分析结果

{file_analysis}

---

## 相关科研文献检索结果

{literature_answer}"""
            else:
                combined_result = f"""## File Analysis Results

{file_analysis}

---

## Relevant Research Literature Search Results

{literature_answer}"""
            
            logger.info(
                f"读取文件并查询文献完成: "
                f"file_analysis_length={len(file_analysis)}, "
                f"literature_answer_length={len(literature_answer)}"
            )
            
            return combined_result
            
        except Exception as e:
            logger.error(f"处理读取文件并查询文献意图失败: {e}", exc_info=True)
            error_msg = (
                f"处理读取文件并查询文献时出现错误: {str(e)}"
                if language == "zh"
                else f"Error processing read files and query knowledge: {str(e)}"
            )
            return error_msg

    async def _handle_execute_service(
        self,
        user_id: str,
        project_id: str,
        user_query: str,
        context_files: list[str] | None = None,
        language: str = "zh",
        progress_cb: Optional[Callable[[dict], None]] = None,
    ) -> str:
        """
        处理服务执行意图
        
        Handler 负责从原始输入中提取和处理参数
        
        Args:
            user_id: 用户ID
            project_id: 项目ID
            user_query: 原始用户查询（Handler 从中提取 query 参数）
            context_files: 上下文文件ID列表（Handler 从中提取 file_ids）
            language: 语言
            progress_cb: 进度回调函数
        
        Returns:
            处理结果（字符串）
        """
        try:
            from textmsa.services.agent.report_agent import (
                astream_analysis_and_report_agent,
                build_report_generation_prompt,
            )
            
            # Handler 负责参数提取：
            # 1. 从 context_files 中提取 file_ids
            file_ids = context_files or []
            
            # 2. 从 user_query 中提取查询内容
            query = user_query.strip()
            
            # 调用 Analysis and Report Agent
            result = await astream_analysis_and_report_agent(
                user_id=user_id,
                project_id=project_id,
                context_files=file_ids,
                language=language,
                user_query=query if query else None,
                on_event=progress_cb,
            )
            
            report_data = result.get("report_data", {})
            
            # 生成结构化报告
            if report_data and report_data.get("executions"):
                if progress_cb:
                    progress_msg = (
                        "正在生成结构化分析报告..."
                        if language == "zh"
                        else "Generating structured analysis report..."
                    )
                    # progress_cb({"message": progress_msg})
                
                # 构建报告生成提示词
                report_prompt = build_report_generation_prompt(
                    report_data=report_data,
                    language=language,
                )
                
                # 调用 LLM 生成结构化报告
                llm_client = get_llm_client_instance()
                request = LLMRequest(
                    messages=[{"role": "user", "content": report_prompt}],
                    temperature=0.3,
                    max_tokens=32000,
                )
                
                response = llm_client.chat(request)
                structured_report = response.content

                message = self.build_message(message=structured_report)
                progress_cb(message)
                
                return structured_report
            else:
                # 如果没有执行记录，返回提示信息
                if language == "zh":
                    return "未找到执行记录，无法生成分析报告。"
                else:
                    return "No execution records found, unable to generate analysis report."
            
        except Exception as e:
            logger.error(f"处理服务执行意图失败: {e}", exc_info=True)
            error_msg = (
                f"处理服务执行时出现错误: {str(e)}"
                if language == "zh"
                else f"Error processing service execution: {str(e)}"
            )
            return error_msg

    async def _handle_general_chat(
        self,
        user_id: str,
        project_id: str,
        user_query: str,
        context_files: list[str] | None = None,
        language: str = "zh",
        progress_cb: Optional[Callable[[dict], None]] = None,
    ) -> str:
        """
        处理通用对话意图（兜底handler）
        
        Args:
            user_id: 用户ID
            project_id: 项目ID
            user_query: 原始用户查询
            context_files: 上下文文件ID列表（可选）
            language: 语言
            progress_cb: 进度回调函数
        
        Returns:
            处理结果（字符串）
        """
        try:
            # 通用对话可以使用简单的 LLM 回复，或者调用其他通用对话服务
            llm_client = get_llm_client_instance()
            
            prompt = (
                f"请回答以下问题：\n{user_query}"
                if language == "zh"
                else f"Please answer the following question:\n{user_query}"
            )
            
            request = LLMRequest(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=2000,
            )
            
            response = llm_client.chat(request)
            message = self.build_message(
                message=response.content,
                role="assistant",
            )
            progress_cb(message)
            return response.content
            
        except Exception as e:
            logger.error(f"处理通用对话意图失败: {e}", exc_info=True)
            error_msg = (
                f"处理对话时出现错误: {str(e)}"
                if language == "zh"
                else f"Error processing conversation: {str(e)}"
            )
            return error_msg

    async def send_message(
        self,
        user_id: str,
        project_id: str,
        message: str,
        context_files: list[str] = None,
        progress_cb: Optional[Callable[[dict], None]] = None,
    ) -> dict[str, Any]:
        """
        异步发送消息并返回结果，支持进度回调
        
        工作流程：
        1. 意图解析：识别用户意图类型（complex_query、query_knowledge、read_files等）
        2. Handler 路由：根据意图类型调用对应的 handler
        3. 结果返回：返回 handler 处理后的结果
        
        意图类型说明：
        - complex_query: 复合查询，执行完整的多步骤流程（意图解析+计划生成+user_proxy_agent+循环处理interrupt）
        - query_knowledge: 直接查询知识库
        - read_files: 直接读取和分析文件
        - execute_service: 直接执行服务
        - general_chat: 通用对话（兜底）
        """
        try:
            # 检测语言（简单检测：如果包含中文字符则为中文，否则为英文）
            detected_language = "zh"
            for ch in message:
                if "\u4e00" <= ch <= "\u9fff":
                    detected_language = "zh"
                    break
            else:
                detected_language = "en"
            
            # 1. 先进行意图解析（只返回意图类型，不提取参数）
            intent_result = await self._parse_intent(
                user_query=message,
                context_files=context_files or [],
                language=detected_language,
            )
            
            intent = intent_result["intent"]
            confidence = intent_result["confidence"]
            reasoning = intent_result["reasoning"]
            
            # # 2. 记录意图解析结果（可选）
            # if progress_cb:
            #     desc_key = "description" if detected_language == "zh" else "description_en"
            #     intent_desc = INTENT_CONFIG.get(intent, INTENT_CONFIG["general_chat"]).get(desc_key, intent)
            #     intent_msg = self.build_message(
            #         message=f"识别意图: {intent_desc} (置信度: {confidence:.2f})"
            #     )
            #     progress_cb(intent_msg)
            
            # 3. 根据意图类型获取配置
            config = INTENT_CONFIG.get(intent, INTENT_CONFIG["general_chat"])
            handler_name = config["handler"]
            
            # 4. 调用对应的 handler（传递原始 user_query 和 context_files，让 handler 自己提取参数）
            handler = getattr(self, handler_name)
            result = await handler(
                user_id=user_id,
                project_id=project_id,
                user_query=message,  # 传递原始查询
                context_files=context_files or [],  # 传递上下文文件
                language=detected_language,  # 传递检测到的语言
                progress_cb=progress_cb,
            )
            
            # 5. 返回结果
            return {
                "final_answer": result,
                "intent": intent,
                "confidence": confidence,
            }
            
        except Exception as e:
            logger.error(f"发送消息失败: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="发送消息失败"
            )

    # ========== 旧代码（已替换为新的意图处理流程）==========
    # async def send_message(
    #     self,
    #     user_id: str,
    #     project_id: str,
    #     message: str,
    #     context_files: list[str] = None,
    #     progress_cb: Optional[Callable[[dict], None]] = None,
    # ) -> dict[str, Any]:
    #     \"\"\"
    #     异步发送消息并返回结果，支持进度回调
    #     \"\"\"
    #             
    #     try:
    #         from textmsa.services.agent.user_proxy_agent import (
    #             run_user_proxy_agent,
    #             resume_user_proxy_agent,
    #         )
    #         from textmsa.services.agent.read_agent import astream_read_agent
    #         from textmsa.services.file.file_service import get_file_service
    #         from textmsa.services.user.user_service import get_user_service
    #         # conversation_history = await self._get_conversation_history(user_id, project_id)
    #         conversation_history = [] # 暂时禁用对话历史，记忆管理后再使用
    #         # 获取文件服务（用于后续 read_files 动作）
    #         file_service = get_file_service()
    #         try:
    #             files_tree_list_with_path_and_preview = await asyncio.to_thread(
    #                 file_service.get_project_files_tree_list,
    #                 project_id=project_id,
    #                 user_id=user_id,
    #                 context_files=context_files,
    #                 recursive=False,
    #                 include_preview=True,
    #                 include_path=True,
    #             )
    #         except Exception as e:
    #             logger.warning(f"获取项目文件树列表失败: {e}，使用空列表")
    #             files_tree_list_with_path_and_preview = []
    #         
    #         # 先进行意图解析与计划生成（并自动检测用户使用的语言）
    #         context_file_ids = context_files or []
    #         intent_plan_result = await asyncio.to_thread(
    #             parse_intent_and_generate_plan,
    #             message,
    #             context_file_ids,
    #             user_id,
    #             project_id,
    #             None,  # 语言为空，让意图解析模块根据 user_query 自动检测中/英文
    #         )
    #         intent = intent_plan_result.get("intent", "")
    #         plan_text = intent_plan_result.get("plan", "")
    #         # 从意图解析结果中获取检测到的语言，默认为中文
    #         detected_language = intent_plan_result.get("language", "zh")
    #
    #         if progress_cb:
    #             plan_prefix = "生成的执行计划" if detected_language == "zh" else "Generated execution plan"
    #             plan_msg = self.build_message(message=f"{plan_prefix}：\n{plan_text}")
    #             progress_cb(plan_msg)
    #
    #         # 生成thread_id：user_id + project_id + uuid
    #         thread_id = f"{user_id}{project_id}{uuid.uuid4().hex}"
    #
    #         # 首次调用 user_proxy_agent（会触发 interrupt），输入为执行计划和原始用户问题
    #         result = await asyncio.to_thread(
    #             run_user_proxy_agent,
    #             plan_text or message,  # 执行计划
    #             message,               # 原始用户问题
    #             user_id,
    #             project_id,
    #             thread_id,
    #             conversation_history=conversation_history,
    #             context_file_ids=context_files or [],
    #             language=detected_language,  # 将自动检测到的语言传递给 user_proxy_agent
    #         )
    #         
    #         # 循环处理interrupt，直到完成
    #         while True:
    #             # logger.info(f"result: {result}")
    #             if "final_answer" in result:
    #                 final_answer = result["final_answer"]
    #                 break
    #             interrupt_data = result["__interrupt__"][0].value
    #             if interrupt_data is not None:
    #                 # 有interrupt，需要处理
    #                 action = interrupt_data.get("action", "")
    #                 parameter = interrupt_data.get("parameter", {})
    #                 reasoning = interrupt_data.get("reasoning", "")
    #                 message = self.build_message(
    #                     message=reasoning,
    #                 )
    #                 progress_cb(message)
    #
    #                 # 根据action执行相应的操作
    #                 if action == "execute_service":
    #                     # 使用 parameter 中的 file_ids 和 query
    #                     file_ids = parameter.get("file_ids", [])
    #                     # 根据语言选择默认提示
    #                     default_execute_query = (
    #                         "请执行服务分析。"
    #                         if detected_language == "zh"
    #                         else "Please run the service analysis."
    #                     )
    #                     query = parameter.get("query", message or default_execute_query)
    #                     
    #                     # 调用 Plan Agent
    #                     from textmsa.services.agent.plan_agent import astream_plan_agent
    #                     
    #                     result = await astream_plan_agent(
    #                         user_query=query,
    #                         user_id=user_id,
    #                         project_id=project_id,
    #                         context_files=file_ids,
    #                         language=detected_language,
    #                         on_event=progress_cb,
    #                     )
    #                     
    #                 elif action == "read_files":
    #                     # 使用 parameter 中的 file_ids、recursive 和 query
    #                     file_ids = parameter.get("file_ids", [])
    #                     recursive = parameter.get("recursive", False)
    #                     explicit_query = parameter.get("query") or ""
    #                     
    #                     # 根据 file_ids 过滤文件树
    #                     filtered_files_tree_list = files_tree_list_with_path_and_preview
    #                     if file_ids:
    #                         # 使用 file_service 获取过滤后的文件树
    #                         filtered_files_tree_list = await asyncio.to_thread(
    #                             file_service.get_project_files_tree_list,
    #                             project_id=project_id,
    #                             user_id=user_id,
    #                             context_files=file_ids,
    #                             recursive=recursive,
    #                             include_preview=True,
    #                             include_path=True,
    #                         )
    #                     
    #                     # 构建查询：优先使用模型显式给出的 query，其次使用 reasoning 消息
    #                     default_read_query = (
    #                         "请分析这些文件的内容和结构。"
    #                         if detected_language == "zh"
    #                         else "Please analyze the content and structure of these files."
    #                     )
    #                     base_query = explicit_query.strip() or reasoning or default_read_query
    #                     user_query = base_query
    #                     if file_ids:
    #                         user_query = f"{base_query}\n需要分析的文件ID: {file_ids}"
    #                     
    #                     # 调用 Read Agent
    #                     result = await astream_read_agent(
    #                         user_query=user_query,
    #                         file_tree_list=filtered_files_tree_list,
    #                         user_id=user_id,
    #                         project_id=project_id,
    #                         language=detected_language,
    #                         on_event=progress_cb,
    #                     )
    #                     result = result.get("final_answer", "")
    #                 elif action == "query_knowledge":
    #                     # 使用 parameter 中的 query
    #                     query = parameter.get("query", message)
    #                     # 调用 Knowledge Agent 替换原来的 knowledge_service
    #                     from textmsa.services.agent.knowledge_agent import astream_knowledge_agent
    #                     
    #                     result = await astream_knowledge_agent(
    #                         user_query=query,
    #                         project_id=project_id,
    #                         user_id=user_id,
    #                         language=detected_language,
    #                         on_event=progress_cb,
    #                     )
    #                     result = result.get("final_answer", "")
    #                 else:
    #                     logger.warning(f"未知的action: {action}")
    #                     break
    #
    #                 result = await asyncio.to_thread(
    #                     resume_user_proxy_agent,
    #                     result=result,
    #                     thread_id=thread_id,
    #                 )
    #         message = self.build_message(message=final_answer)
    #         progress_cb(message)
    #
    #         return {
    #             "final_answer": final_answer
    #         }
    #     except Exception as e:
    #         logger.error(f"发送消息失败: {e}", exc_info=True)
    #         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="发送消息失败")
    # ========== 旧代码结束 ==========


# 全局服务实例
_agent_service: AgentService | None = None


def get_agent_service() -> AgentService:
    """获取全局Agent服务实例"""
    global _agent_service
    if _agent_service is None:
        _agent_service = AgentService()
    return _agent_service


__all__ = ["AgentService", "get_agent_service"]
