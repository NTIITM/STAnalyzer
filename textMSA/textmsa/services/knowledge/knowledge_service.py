"""
Knowledge management service: handles CRUD, workflow extraction, prompt config,
and optional Neo4j persistence for imported knowledge.
"""
from __future__ import annotations
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.errors import ConnectionFailure


from textmsa.logging_config import get_logger
from textmsa.settings import get_mongodb_config
from textmsa.services.data.mongodb_models import (
    Knowledge,
    KnowledgePromptConfig,
    KnowledgeRelationSummary,
    KnowledgeScope,
    knowledge_from_dict,
    knowledge_prompt_config_from_dict,
)

logger = get_logger(__name__)


class KnowledgeService:
    """知识管理服务"""

    def __init__(self, connection_string: Optional[str] = None, database_name: Optional[str] = None):
        mongo_config = get_mongodb_config()
        connection_string = connection_string or mongo_config["uri"]
        database_name = database_name or mongo_config["database"]

        try:
            self.client = MongoClient(
                connection_string,
                serverSelectionTimeoutMS=mongo_config["server_selection_timeout_ms"],
                connectTimeoutMS=mongo_config["connect_timeout_ms"],
                socketTimeoutMS=mongo_config["socket_timeout_ms"],
                maxPoolSize=mongo_config["max_pool_size"],
                minPoolSize=mongo_config["min_pool_size"],
            )
            self.client.admin.command("ping")
            logger.info("KnowledgeService: connected to MongoDB")
        except ConnectionFailure as exc:
            logger.error("KnowledgeService: failed to connect MongoDB: %s", exc)
            raise

        self.db = self.client[database_name]
        self.collection = self.db.knowledge
        self.workflow_collection = self.db.knowledge_workflows
        self.prompt_collection = self.db.knowledge_prompt_configs
        self.pending_prompts_collection = self.db.knowledge_pending_prompts
        self._create_indexes()


    # ---------- setup ----------
    def _create_indexes(self) -> None:
        try:
            self.collection.create_index([("knowledge_id", ASCENDING)], unique=True)
            self.collection.create_index([("user_id", ASCENDING)])
            self.collection.create_index([("scope", ASCENDING)])
            self.collection.create_index([("updated_at", DESCENDING)])
            # 支持多个模板：使用 (user_id, template_id) 组合唯一索引
            self.prompt_collection.create_index([("user_id", ASCENDING), ("template_id", ASCENDING)], unique=True)
            self.prompt_collection.create_index([("user_id", ASCENDING), ("is_default", ASCENDING)])
            # 待审批提示索引
            self.pending_prompts_collection.create_index([("pending_prompt_id", ASCENDING)], unique=True)
            self.pending_prompts_collection.create_index([("user_id", ASCENDING)])
            self.pending_prompts_collection.create_index([("created_at", DESCENDING)])
        except Exception as exc:
            logger.warning("KnowledgeService: failed to create indexes (%s)", exc)

    # ---------- helpers ----------
    @staticmethod
    def _now() -> datetime:
        return datetime.utcnow()

    @staticmethod
    def _parse_scope(scope: Optional[str]) -> Optional[KnowledgeScope]:
        if not scope:
            return None
        try:
            return KnowledgeScope(scope)
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"无效的scope: {scope}")

    def _build_scope_query(self, scope: Optional[KnowledgeScope], user_id: Optional[str]) -> Dict[str, Any]:
        if scope == KnowledgeScope.PRIVATE:
            if not user_id:
                return {"user_id": "__unauthorized__"}
            return {"scope": KnowledgeScope.PRIVATE.value, "user_id": user_id}
        if scope == KnowledgeScope.PUBLIC:
            return {"scope": KnowledgeScope.PUBLIC.value}
        if scope == KnowledgeScope.SYSTEM:
            return {"scope": KnowledgeScope.SYSTEM.value}

        query: Dict[str, Any] = {"$or": [{"scope": KnowledgeScope.PUBLIC.value}, {"scope": KnowledgeScope.SYSTEM.value}]}
        if user_id:
            query["$or"].append({"scope": KnowledgeScope.PRIVATE.value, "user_id": user_id})
        return query

    def _apply_keyword_filter(self, base_query: Dict[str, Any], keyword: Optional[str]) -> Dict[str, Any]:
        if not keyword:
            return base_query
        regex = {"$regex": keyword, "$options": "i"}
        keyword_clause = {"description": regex}
        if "$and" not in base_query:
            base_query["$and"] = []
        base_query["$and"].append(keyword_clause)
        return base_query

    def _apply_edited_only_filter(self, base_query: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """
        仅返回当前用户编辑的知识
        """
        # 如果查询已经限定 user_id，直接返回
        if base_query.get("user_id") == user_id:
            return base_query
        clause = {"user_id": user_id}
        if "$and" not in base_query:
            base_query["$and"] = []
        base_query["$and"].append(clause)
        return base_query

    def _apply_project_knowledge_filter(
        self,
        base_query: Dict[str, Any],
        project_id: str,
        user_id: Optional[str]
    ) -> Dict[str, Any]:
        """
        应用项目知识过滤

        Args:
            base_query: 基础查询
            project_id: 项目ID
            user_id: 用户ID（用于获取项目配置）

        Returns:
            应用项目过滤后的查询
        """
        try:
            from textmsa.services.project.project_service import get_project_service

            project_service = get_project_service()
            project = project_service.get_project(project_id=project_id, user_id=user_id)
            config = project.knowledge_config

            # 如果模式是 "all"，不进行过滤
            if config.mode == "all":
                return base_query

            # 如果模式是 "whitelist"，只返回白名单中的知识
            if config.mode == "whitelist":
                if not config.whitelist:
                    return {"knowledge_id": "__no_match__"}
                knowledge_id_filter = {"knowledge_id": {"$in": config.whitelist}}
                if "$and" not in base_query:
                    base_query["$and"] = []
                base_query["$and"].append(knowledge_id_filter)
                return base_query

            # 如果模式是 "blacklist"，排除黑名单中的知识
            if config.mode == "blacklist":
                if config.blacklist:
                    knowledge_id_filter = {"knowledge_id": {"$nin": config.blacklist}}
                    if "$and" not in base_query:
                        base_query["$and"] = []
                    base_query["$and"].append(knowledge_id_filter)
                return base_query

            return base_query

        except Exception as e:
            logger.warning(f"应用项目知识过滤失败: {e}，返回原查询")
            return base_query

    def _enforce_access(self, item: Knowledge, user_id: Optional[str]) -> None:
        if item.scope == KnowledgeScope.PRIVATE and item.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该知识条目")

    def _ensure_mutable(self, item: Knowledge, user_id: Optional[str]) -> None:
        if item.scope == KnowledgeScope.SYSTEM:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="系统知识不可编辑")
        if item.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只能编辑本人知识")

    @staticmethod
    def _to_api_dict(item: Knowledge) -> Dict[str, Any]:
        """将Knowledge模型转换为API响应格式"""
        relation_summary_dict = None
        if item.relation_summary:
            relation_summary_dict = {
                "from_entity": item.relation_summary.from_entity,
                "relation": item.relation_summary.relation,
                "end_entity": item.relation_summary.end_entity,
            }
        return {
            "id": item.knowledge_id,
            "title": item.title,
            "description": item.description,
            "relation_summary": relation_summary_dict,
            "scope": item.scope.value,
            "source": item.source,
            "owner_id": item.user_id,  # API使用owner_id，但模型使用user_id
            "metadata": item.metadata,
            "created_at": item.created_at.isoformat(),
            "last_modified": item.updated_at.isoformat(),
            "shared_at": item.shared_at.isoformat() if item.shared_at else None,
            "share_note": item.share_note,
        }

    # ---------- CRUD ----------
    def list_knowledge(
        self,
        *,
        scope: Optional[str],
        keyword: Optional[str],
        edited_only: bool,
        page: int,
        page_size: int,
        sort: str,
        user_id: Optional[str],
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        page = max(page, 1)
        page_size = max(1, min(page_size, 200))
        scope_enum = self._parse_scope(scope) if scope else None
        query = self._build_scope_query(scope_enum, user_id)
        query = self._apply_keyword_filter(query, keyword)
        if edited_only:
            if not user_id:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录查看已编辑的知识")
            query = self._apply_edited_only_filter(query, user_id)

        # 应用项目过滤
        if project_id:
            query = self._apply_project_knowledge_filter(query, project_id, user_id)

        sort_field = "updated_at" if sort == "latest" else "created_at"
        cursor = (
            self.collection.find(query)
            .sort(sort_field, DESCENDING if sort == "latest" else ASCENDING)
            .skip((page - 1) * page_size)
            .limit(page_size)
        )
        items = [self._to_api_dict(knowledge_from_dict(doc)) for doc in cursor]
        total = self.collection.count_documents(query)
        return {"items": items, "total": total, "page": page, "page_size": page_size}

    def get_knowledge(self, knowledge_id: str, user_id: Optional[str]) -> Dict[str, Any]:
        doc = self.collection.find_one({"knowledge_id": knowledge_id})
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识条目不存在")
        item = knowledge_from_dict(doc)
        self._enforce_access(item, user_id)
        return self._to_api_dict(item)

    # 批量获取知识条目
    # @cache(maxsize=128)
    def get_knowledges(self, knowledge_ids: List[str], user_id: Optional[str]) -> List[Dict[str, Any]]:
        items = [self.get_knowledge(item, user_id) for item in knowledge_ids]
        return items

    def create_knowledge(self, payload: Dict[str, Any], user_id: Optional[str]) -> Dict[str, Any]:
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")
        scope = self._parse_scope(payload.get("scope"))
        if scope and scope not in (KnowledgeScope.PRIVATE, KnowledgeScope.PUBLIC):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="仅支持创建私有或公共知识")

        scope_value = scope or KnowledgeScope.PRIVATE
        if scope_value == KnowledgeScope.PUBLIC:
            # 公共知识仍需审核/分享流程，这里统一创建为私有，再由分享接口处理
            scope_value = KnowledgeScope.PRIVATE

        # 处理relation_summary
        relation_summary_data = payload.get("relation_summary")
        if not relation_summary_data:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="relation_summary不能为空")

        # 支持新旧格式
        if isinstance(relation_summary_data, dict):
            if "from_entity" in relation_summary_data:
                relation_summary = KnowledgeRelationSummary(**relation_summary_data)
            else:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="relation_summary格式无效，必须包含from_entity, relation, end_entity字段")
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="relation_summary必须是字典类型")

        knowledge = Knowledge(
            knowledge_id=str(uuid.uuid4()),
            user_id=user_id,
            title=payload.get("title", payload.get("description", "Untitled")[:100]).strip(),
            description=payload.get("description", "").strip(),
            relation_summary=relation_summary,
            scope=scope_value,
            source=payload.get("source") or "User created",
            metadata=payload.get("metadata") or {},
            created_at=self._now(),
            updated_at=self._now(),
        )
        self.collection.insert_one(knowledge.to_dict())
        return self._to_api_dict(knowledge)

    def create_system_knowledge(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        创建系统知识（内部方法，用于系统初始化）

        Args:
            payload: 知识数据，包含description, relation_summary, source, metadata等

        Returns:
            创建的知识字典
        """
        relation_summary_data = payload.get("relation_summary")
        if not relation_summary_data:
            raise ValueError("relation_summary不能为空")

        if isinstance(relation_summary_data, dict):
            if "from_entity" in relation_summary_data:
                relation_summary = KnowledgeRelationSummary(**relation_summary_data)
            else:
                raise ValueError("relation_summary格式无效")
        else:
            raise ValueError("relation_summary必须是字典类型")

        knowledge = Knowledge(
            knowledge_id=str(uuid.uuid4()),
            user_id=None,
            title=payload.get("title", payload.get("description", "System Knowledge")[:100]).strip(),
            description=payload.get("description", "").strip(),
            relation_summary=relation_summary,
            scope=KnowledgeScope.SYSTEM,
            source=payload.get("source") or "System",
            metadata=payload.get("metadata") or {},
            created_at=self._now(),
            updated_at=self._now(),
        )
        self.collection.insert_one(knowledge.to_dict())
        return {"id": knowledge.knowledge_id, **self._to_api_dict(knowledge)}

    def update_knowledge(self, knowledge_id: str, payload: Dict[str, Any], user_id: Optional[str]) -> Dict[str, Any]:
        doc = self.collection.find_one({"knowledge_id": knowledge_id})
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识条目不存在")
        item = knowledge_from_dict(doc)
        self._ensure_mutable(item, user_id)

        update_fields: Dict[str, Any] = {}
        if "description" in payload:
            if not payload["description"]:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="描述不能为空")
            update_fields["description"] = payload["description"].strip()
        if "relation_summary" in payload:
            relation_summary_data = payload.get("relation_summary")
            if isinstance(relation_summary_data, dict):
                if "from_entity" in relation_summary_data:
                    update_fields["relation_summary"] = relation_summary_data
                else:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="relation_summary格式无效，必须包含from_entity, relation, end_entity字段")
            else:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="relation_summary必须是字典类型")
        if "metadata" in payload:
            update_fields["metadata"] = payload.get("metadata") or {}
        if update_fields:
            update_fields["updated_at"] = self._now()
            self.collection.update_one({"knowledge_id": knowledge_id}, {"$set": update_fields})
        refreshed = knowledge_from_dict(self.collection.find_one({"knowledge_id": knowledge_id}))
        return self._to_api_dict(refreshed)

    def delete_knowledge(self, knowledge_id: str, user_id: Optional[str]) -> None:
        doc = self.collection.find_one({"knowledge_id": knowledge_id})
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识条目不存在")
        item = knowledge_from_dict(doc)
        self._ensure_mutable(item, user_id)
        self.collection.delete_one({"knowledge_id": knowledge_id})

    def share_knowledge(self, knowledge_id: str, note: Optional[str], user_id: Optional[str]) -> Dict[str, Any]:
        doc = self.collection.find_one({"knowledge_id": knowledge_id})
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识条目不存在")
        item = knowledge_from_dict(doc)
        self._ensure_mutable(item, user_id)
        if item.scope != KnowledgeScope.PRIVATE:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="仅私有知识可分享")
        update = {
            "scope": KnowledgeScope.PUBLIC.value,
            "share_note": note,
            "shared_at": self._now(),
            "updated_at": self._now(),
        }
        self.collection.update_one({"knowledge_id": knowledge_id}, {"$set": update})
        refreshed = knowledge_from_dict(self.collection.find_one({"knowledge_id": knowledge_id}))
        return self._to_api_dict(refreshed)

    # ---------- workflow ----------

    def extract_from_text(
        self,
        text: str,
        user_id: Optional[str] = None,
        template_id: Optional[str] = None,
        source: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        从文本中提取知识三元组（entity-relation-entity）
        
        Args:
            text: 待提取的原始文本
            user_id: 用户ID（可选，用于获取用户的prompt配置）
            template_id: 模板ID（可选，用于指定使用的prompt模板）
            source: 来源说明（可选）
        
        Returns:
            提取的知识三元组列表，每个元素包含：
            - from_entity: 头实体
            - relation: 关系类型
            - end_entity: 尾实体
            - description: 描述（从原文中提取的相关句子）
            - source: 来源说明
        
        Raises:
            HTTPException: 当LLM调用失败或文本为空时
        """
        if not text or not text.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="文本不能为空"
            )
        
        logger.info(f"开始从文本提取知识三元组，文本长度: {len(text)}")
        
        try:
            # 获取prompt配置
            prompt_config = None
            if user_id:
                try:
                    prompt_config = self.get_prompt_config(user_id, template_id)
                except Exception as e:
                    logger.warning(f"获取prompt配置失败: {e}，使用默认配置")
            
            # 构建提取提示词
            system_prompt, user_prompt = self._build_extraction_prompts(text, prompt_config)
            
            # 创建LLM实例并调用
            from textmsa.utils.llm import create_llm, call_llm, parse_llm_json_response
            
            try:
                llm = create_llm()
            except Exception as e:
                logger.error(f"创建LLM实例失败: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"LLM服务初始化失败: {str(e)}"
                )
            
            # 调用LLM进行提取
            try:
                response_text = call_llm(llm, system_prompt, user_prompt)
                if not response_text:
                    logger.warning("LLM返回空响应")
                    return []
            except Exception as e:
                logger.error(f"LLM调用失败: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"LLM调用失败: {str(e)}"
                )
            
            # 解析LLM响应
            try:
                response_data = parse_llm_json_response(response_text, default_value=None)
                if not response_data:
                    logger.warning("LLM响应解析失败，返回空结果")
                    return []
            except Exception as e:
                logger.error(f"解析LLM响应失败: {e}")
                logger.debug(f"原始响应: {response_text[:500]}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"解析LLM响应失败: {str(e)}"
                )
            
            # 转换并验证提取结果
            triplets = self._parse_extraction_response(response_data, text, source)
            
            logger.info(f"成功提取 {len(triplets)} 个知识三元组")
            return triplets
            
        except HTTPException:
            # 重新抛出HTTP异常
            raise
        except Exception as e:
            logger.error(f"提取知识三元组时发生未知错误: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"提取知识三元组失败: {str(e)}"
            )
    
    def _build_extraction_prompts(
        self,
        text: str,
        prompt_config: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, str]:
        """
        构建知识提取的提示词
        
        Args:
            text: 待提取的文本
            prompt_config: prompt配置（可选）
        
        Returns:
            (system_prompt, user_prompt) 元组
        """
        # 获取实体和关系提示
        entity_prompt = {}
        relation_prompt = {}
        
        if prompt_config:
            entity_prompt = prompt_config.get("entity_prompt", {})
            relation_prompt = prompt_config.get("relation_prompt", {})
        
        # 如果没有配置，使用默认提示
        if not entity_prompt:
            entity_prompt = {
                "基因/蛋白质": "包括基因名称、蛋白质名称、转录因子等，使用标准命名，识别实体的别名和同义词",
                "疾病": "疾病名称、疾病类型等，使用标准命名",
                "药物": "药物名称、药物类别等，使用标准命名",
                "生物标志物": "诊断标志物、预后标志物、治疗靶点等，使用标准命名"
            }
        
        if not relation_prompt:
            relation_prompt = {
                "activates": "激活关系，明确关系的方向性，提供证据句子，标注置信度",
                "inhibits": "抑制关系，明确关系的方向性，提供证据句子，标注置信度",
                "regulates": "调控关系，明确关系的方向性，提供证据句子，标注置信度",
                "treats": "治疗关系，明确关系的方向性，提供证据句子，标注置信度",
                "is_indicated_for": "适应症关系，明确关系的方向性，提供证据句子，标注置信度",
                "is_associated_with": "关联关系，明确关系的方向性，提供证据句子，标注置信度",
                "correlates_with": "相关性关系，明确关系的方向性，提供证据句子，标注置信度"
            }
        
        # 构建实体提示文本
        entity_prompt_text = "\n".join([
            f"- {entity_type}: {description}"
            for entity_type, description in entity_prompt.items()
        ])
        
        # 构建关系提示文本
        relation_prompt_text = "\n".join([
            f"- {relation_type}: {description}"
            for relation_type, description in relation_prompt.items()
        ])
        
        # 系统提示词
        system_prompt = f"""你是一个专业的知识图谱提取专家，擅长从生物医学文本中提取实体-关系-实体三元组。

你的任务是：
1. 从给定的文本中识别实体（如基因、蛋白质、疾病、药物等）
2. 识别实体之间的关系（如激活、抑制、调控、治疗等）
3. 提取完整的知识三元组（头实体-关系-尾实体）

实体类型要求：
{entity_prompt_text}

关系类型要求：
{relation_prompt_text}

输出要求：
- 返回JSON格式，包含一个"triplets"数组
- 每个三元组包含以下字段：
  - "from_entity": 头实体名称（字符串）
  - "relation": 关系类型（字符串）
  - "end_entity": 尾实体名称（字符串）
  - "description": 描述文本（从原文中提取的相关句子，字符串）
  - "confidence": 置信度（0-1之间的浮点数，可选）

示例输出格式：
{{
  "triplets": [
    {{
      "from_entity": "BRCA1",
      "relation": "regulates",
      "end_entity": "DNA repair",
      "description": "BRCA1 regulates DNA repair pathways.",
      "confidence": 0.9
    }},
    {{
      "from_entity": "Aspirin",
      "relation": "treats",
      "end_entity": "Headache",
      "description": "Aspirin is commonly used to treat headaches.",
      "confidence": 0.85
    }}
  ]
}}

注意：
- 只提取明确存在的关系，不要推测
- 确保实体名称使用标准命名
- 关系类型必须明确且有方向性
- 如果文本中没有找到任何三元组，返回空的triplets数组
"""
        
        # 用户提示词
        user_prompt = f"""请从以下文本中提取知识三元组：

{text}

请按照要求返回JSON格式的提取结果。"""
        
        return system_prompt, user_prompt
    
    def _parse_extraction_response(
        self,
        response_data: Dict[str, Any],
        original_text: str,
        source: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        解析LLM响应并转换为知识三元组格式
        
        Args:
            response_data: LLM返回的JSON数据
            original_text: 原始文本
            source: 来源说明
        
        Returns:
            知识三元组列表
        """
        triplets = []
        
        # 检查响应格式
        if not isinstance(response_data, dict):
            logger.warning(f"LLM响应格式错误，期望dict，得到: {type(response_data)}")
            return []
        
        # 获取triplets数组
        triplets_data = response_data.get("triplets", [])
        if not isinstance(triplets_data, list):
            logger.warning(f"triplets字段格式错误，期望list，得到: {type(triplets_data)}")
            return []
        
        # 处理每个三元组
        for idx, triplet_data in enumerate(triplets_data):
            if not isinstance(triplet_data, dict):
                logger.warning(f"三元组 {idx} 格式错误，跳过")
                continue
            
            try:
                # 提取必需字段
                from_entity = triplet_data.get("from_entity", "").strip()
                relation = triplet_data.get("relation", "").strip()
                end_entity = triplet_data.get("end_entity", "").strip()
                description = triplet_data.get("description", "").strip()
                confidence = triplet_data.get("confidence", 0.8)
                
                # 验证必需字段
                if not from_entity or not relation or not end_entity:
                    logger.warning(f"三元组 {idx} 缺少必需字段，跳过")
                    continue
                
                # 如果没有描述，使用原始文本的前100个字符
                if not description:
                    description = original_text[:100] + "..." if len(original_text) > 100 else original_text
                
                # 构建三元组字典
                triplet = {
                    "from_entity": from_entity,
                    "relation": relation,
                    "end_entity": end_entity,
                    "description": description,
                    "source": source or "Text extraction",
                    "confidence": float(confidence) if isinstance(confidence, (int, float)) else 0.8
                }
                
                triplets.append(triplet)
                
            except Exception as e:
                logger.warning(f"处理三元组 {idx} 时出错: {e}，跳过")
                continue
        
        return triplets

    def extract_from_literature(
        self,
        query: str,
        user_id: Optional[str] = None,
        template_id: Optional[str] = None,
        max_results: int = 10,
        source: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        从文献中提取知识：扩展关键词、重写查询、检索文献、提取知识
        
        Args:
            query: 用户查询（自然语言）
            user_id: 用户ID（可选，用于获取用户的prompt配置）
            template_id: 模板ID（可选，用于指定使用的prompt模板）
            max_results: 最大检索文献数量，默认10
            source: 来源说明（可选）
        
        Returns:
            包含以下字段的字典：
            - query: 原始查询
            - expanded_keywords: 扩展后的关键词列表
            - pubmed_query: 重写后的PubMed查询
            - articles: 检索到的文献列表
            - triplets: 提取的知识三元组列表
            - summary: 提取摘要
        
        Raises:
            HTTPException: 当查询为空、LLM调用失败或PubMed API调用失败时
        """
        if not query or not query.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="查询不能为空"
            )
        
        logger.info(f"开始从文献提取知识，查询: {query[:100]}...")
        
        try:
            # 步骤1: 扩展关键词
            logger.info("步骤1: 扩展关键词...")
            expanded_keywords = self._expand_keywords(query, user_id)
            logger.info(f"扩展后的关键词: {expanded_keywords}")
            
            # 步骤2: 重写为结构化PubMed查询
            logger.info("步骤2: 重写为PubMed查询...")
            pubmed_query = self._rewrite_pubmed_query(query, expanded_keywords, user_id)
            logger.info(f"PubMed查询: {pubmed_query}")
            
            # 步骤3: 检索文献
            logger.info("步骤3: 检索文献...")
            articles = self._retrieve_literature(pubmed_query, max_results=max_results)
            logger.info(f"检索到 {len(articles)} 篇文献")
            
            # 步骤4: 从文献中提取知识
            logger.info("步骤4: 从文献中提取知识...")
            all_triplets = []
            article_sources = []
            
            for idx, article in enumerate(articles):
                article_text = self._format_article_for_extraction(article)
                article_source = f"PubMed: {article.get('pmid', 'unknown')} - {article.get('title', 'Untitled')[:50]}"
                
                try:
                    # 使用现有的extract_from_text方法提取知识
                    triplets = self.extract_from_text(
                        text=article_text,
                        user_id=user_id,
                        template_id=template_id,
                        source=article_source
                    )
                    
                    # 为每个三元组添加文献元数据
                    for triplet in triplets:
                        triplet["article_pmid"] = article.get("pmid")
                        triplet["article_title"] = article.get("title", "")
                        triplet["article_authors"] = article.get("authors", [])
                        triplet["article_pub_date"] = article.get("pub_date", "")
                    
                    all_triplets.extend(triplets)
                    article_sources.append({
                        "pmid": article.get("pmid"),
                        "title": article.get("title", ""),
                        "triplet_count": len(triplets)
                    })
                    
                    logger.info(f"从文献 {idx+1}/{len(articles)} 提取了 {len(triplets)} 个三元组")
                    
                except Exception as e:
                    logger.warning(f"从文献 {idx+1} 提取知识失败: {e}，跳过")
                    continue
            
            logger.info(f"总共提取了 {len(all_triplets)} 个知识三元组")
            
            # 步骤5: 生成摘要
            summary = self._generate_extraction_summary(
                query=query,
                articles_count=len(articles),
                triplets_count=len(all_triplets),
                article_sources=article_sources
            )
            
            return {
                "query": query,
                "expanded_keywords": expanded_keywords,
                "pubmed_query": pubmed_query,
                "articles": articles,
                "triplets": all_triplets,
                "summary": summary,
                "source": source or "Literature extraction"
            }
            
        except HTTPException:
            # 重新抛出HTTP异常
            raise
        except Exception as e:
            logger.error(f"从文献提取知识时发生未知错误: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"从文献提取知识失败: {str(e)}"
            )
    
    def _expand_keywords(
        self,
        query: str,
        user_id: Optional[str] = None
    ) -> List[str]:
        """
        使用LLM扩展查询关键词
        
        Args:
            query: 用户查询
            user_id: 用户ID（可选）
        
        Returns:
            扩展后的关键词列表
        """
        from textmsa.utils.llm import create_llm, call_llm, parse_llm_json_response
        
        try:
            llm = create_llm()
        except Exception as e:
            logger.error(f"创建LLM实例失败: {e}")
            # 如果LLM失败，返回原始查询作为唯一关键词
            return [query.strip()]
        
        system_prompt = """你是一个专业的生物医学文献检索助手。你的任务是根据用户的查询，扩展相关的关键词和同义词，以便更全面地检索相关文献。

输出要求：
- 返回JSON格式，包含一个"keywords"数组
- 每个关键词应该是字符串
- 包括原始查询中的关键词、同义词、相关术语等
- 关键词应该简洁且适合用于文献检索

示例输出格式：
{
  "keywords": ["TP53", "p53", "tumor protein p53", "gene regulation"]
}"""
        
        user_prompt = f"""请为以下查询扩展关键词：

查询: {query}

请返回扩展后的关键词列表（JSON格式）。"""
        
        try:
            response_text = call_llm(llm, system_prompt, user_prompt)
            if not response_text:
                logger.warning("LLM返回空响应，使用原始查询作为关键词")
                return [query.strip()]
            
            response_data = parse_llm_json_response(response_text, default_value=None)
            if not response_data or not isinstance(response_data, dict):
                logger.warning("LLM响应解析失败，使用原始查询作为关键词")
                return [query.strip()]
            
            keywords = response_data.get("keywords", [])
            if not isinstance(keywords, list) or not keywords:
                logger.warning("关键词列表为空，使用原始查询作为关键词")
                return [query.strip()]
            
            # 过滤空字符串并去重
            keywords = list(set([k.strip() for k in keywords if k and k.strip()]))
            if not keywords:
                return [query.strip()]
            
            return keywords
            
        except Exception as e:
            logger.error(f"扩展关键词失败: {e}，使用原始查询作为关键词")
            return [query.strip()]
    
    def _rewrite_pubmed_query(
        self,
        query: str,
        expanded_keywords: List[str],
        user_id: Optional[str] = None
    ) -> str:
        """
        使用LLM将查询重写为结构化的PubMed查询格式
        
        Args:
            query: 原始查询
            expanded_keywords: 扩展后的关键词列表
            user_id: 用户ID（可选）
        
        Returns:
            结构化的PubMed查询字符串
        """
        from textmsa.utils.llm import create_llm, call_llm
        
        try:
            llm = create_llm()
        except Exception as e:
            logger.error(f"创建LLM实例失败: {e}")
            # 如果LLM失败，使用简单的关键词组合
            return " AND ".join(expanded_keywords[:3])
        
        system_prompt = """你是一个专业的PubMed查询构建助手。你的任务是将用户的自然语言查询转换为符合PubMed查询语法的结构化查询。

PubMed查询语法规则：
- 使用 AND, OR, NOT 连接多个术语
- 使用引号包围短语："gene regulation"
- 可以使用字段限定符：[Title/Abstract], [MeSH Terms], [Author] 等
- 支持括号分组：(gene OR protein) AND cancer
- 关键词之间默认使用 AND 连接

输出要求：
- 只返回查询字符串，不要包含其他说明
- 查询应该简洁且有效
- 优先使用 Title/Abstract 字段限定符以提高相关性

示例：
- 输入: "TP53基因调控p21基因"
- 输出: "TP53[Title/Abstract] AND p21[Title/Abstract] AND (regulation OR regulate OR regulatory)"
"""
        
        keywords_text = ", ".join(expanded_keywords[:10])  # 限制关键词数量
        user_prompt = f"""请将以下查询转换为PubMed查询格式：

原始查询: {query}
扩展关键词: {keywords_text}

请返回结构化的PubMed查询字符串（只返回查询，不要其他说明）。"""
        
        try:
            response_text = call_llm(llm, system_prompt, user_prompt)
            if not response_text:
                logger.warning("LLM返回空响应，使用简单关键词组合")
                return " AND ".join(expanded_keywords[:3])
            
            # 清理响应文本（去除可能的引号、换行等）
            pubmed_query = response_text.strip().strip('"').strip("'")
            if not pubmed_query:
                return " AND ".join(expanded_keywords[:3])
            
            return pubmed_query
            
        except Exception as e:
            logger.error(f"重写PubMed查询失败: {e}，使用简单关键词组合")
            return " AND ".join(expanded_keywords[:3])
    
    def _retrieve_literature(
        self,
        pubmed_query: str,
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        从PubMed检索文献
        
        Args:
            pubmed_query: PubMed查询字符串
            max_results: 最大结果数量
        
        Returns:
            文献列表，每个元素包含 pmid, title, abstract, authors, pub_date 等字段
        
        Raises:
            HTTPException: 当PubMed API调用失败时
        """
        try:
            from textmsa.knowledge.pubmed_api import get_pubmed_api
            
            pubmed_api = get_pubmed_api()
            articles = pubmed_api.search_articles(pubmed_query, max_results=max_results)
            
            if not articles:
                logger.warning(f"PubMed查询未返回任何结果: {pubmed_query}")
                return []
            
            return articles
            
        except Exception as e:
            logger.error(f"PubMed API调用失败: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"文献检索失败: {str(e)}"
            )
    
    def _format_article_for_extraction(self, article: Dict[str, Any]) -> str:
        """
        将文献信息格式化为适合提取的文本
        
        Args:
            article: 文献字典，包含 title, abstract, authors 等字段
        
        Returns:
            格式化的文本字符串
        """
        parts = []
        
        # 标题
        title = article.get("title", "")
        if title:
            parts.append(f"Title: {title}")
        
        # 摘要
        abstract = article.get("abstract", "")
        if abstract:
            parts.append(f"Abstract: {abstract}")
        
        # 作者（可选，用于上下文）
        authors = article.get("authors", [])
        if authors:
            authors_text = ", ".join(authors[:5])  # 限制作者数量
            parts.append(f"Authors: {authors_text}")
        
        return "\n\n".join(parts) if parts else ""
    
    def _generate_extraction_summary(
        self,
        query: str,
        articles_count: int,
        triplets_count: int,
        article_sources: List[Dict[str, Any]]
    ) -> str:
        """
        生成提取摘要
        
        Args:
            query: 原始查询
            articles_count: 检索到的文献数量
            triplets_count: 提取的三元组数量
            article_sources: 文献来源列表
        
        Returns:
            摘要文本
        """
        summary_parts = [
            f"查询: {query}",
            f"检索文献数: {articles_count}",
            f"提取三元组数: {triplets_count}",
        ]
        
        if article_sources:
            summary_parts.append("\n文献来源:")
            for source in article_sources[:5]:  # 只显示前5个
                summary_parts.append(
                    f"  - PMID {source.get('pmid', 'unknown')}: "
                    f"{source.get('title', 'Untitled')[:50]} "
                    f"({source.get('triplet_count', 0)} 个三元组)"
                )
            if len(article_sources) > 5:
                summary_parts.append(f"  ... 还有 {len(article_sources) - 5} 篇文献")
        
        return "\n".join(summary_parts)

    def search_literature_for_rag(
        self,
        query: str,
        user_id: Optional[str] = None,
        max_results: int = 5
    ) -> Dict[str, Any]:
        """
        为RAG工作流检索文献：扩展关键词、重写查询、检索文献
        
        这是 extract_from_literature 的简化版本，专门用于RAG工作流。
        只负责检索文献，不进行知识提取（证据摘要在上层 workflow 中以启发式方式生成）。
        
        Args:
            query: 用户查询（自然语言）
            user_id: 用户ID（可选，用于获取用户的prompt配置）
            max_results: 最大检索文献数量，默认5（RAG工作流通常需要更少的结果）
        
        Returns:
            包含以下字段的字典：
            - query: 原始查询
            - expanded_keywords: 扩展后的关键词列表
            - pubmed_query: 重写后的PubMed查询
            - articles: 检索到的文献列表
        
        Raises:
            HTTPException: 当查询为空或PubMed API调用失败时
        """
        if not query or not query.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="查询不能为空"
            )
        
        logger.info(f"RAG工作流：开始检索文献，查询: {query[:100]}...")
        
        try:
            # 步骤1: 扩展关键词
            logger.debug("RAG工作流：扩展关键词...")
            expanded_keywords = self._expand_keywords(query, user_id)
            logger.debug(f"RAG工作流：扩展后的关键词: {expanded_keywords}")
            
            # 步骤2: 重写为结构化PubMed查询
            logger.debug("RAG工作流：重写为PubMed查询...")
            pubmed_query = self._rewrite_pubmed_query(query, expanded_keywords, user_id)
            logger.debug(f"RAG工作流：PubMed查询: {pubmed_query}")
            
            # 步骤3: 检索文献
            logger.debug("RAG工作流：检索文献...")
            articles = self._retrieve_literature(pubmed_query, max_results=max_results)
            logger.info(f"RAG工作流：检索到 {len(articles)} 篇文献")
            
            return {
                "query": query,
                "expanded_keywords": expanded_keywords,
                "pubmed_query": pubmed_query,
                "articles": articles
            }
            
        except HTTPException:
            # 重新抛出HTTP异常
            raise
        except Exception as e:
            logger.error(f"RAG工作流：检索文献时发生未知错误: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"文献检索失败: {str(e)}"
            )

    # ---------- prompt config ----------

    def get_prompt_templates(self) -> List[Dict[str, Any]]:
        """
        获取系统定义的提示词模板列表
        
        Returns:
            系统定义的提示词模板列表，每个模板包含：
            - template_id: 模板ID（系统模板使用特殊ID）
            - name: 模板名称
            - description: 模板描述
            - entity_prompt: 实体提示词定义
            - relation_prompt: 关系提示词定义
        """
        templates = [
            {
                "template_id": "system_biomedical_default",
                "name": "生物医学默认模板",
                "description": "适用于一般生物医学知识抽取的默认模板",
                "entity_prompt": {
                    "基因/蛋白质": "包括基因名称、蛋白质名称、转录因子等，使用标准命名，识别实体的别名和同义词",
                    "疾病": "疾病名称、疾病类型等，使用标准命名",
                    "药物": "药物名称、药物类别等，使用标准命名",
                    "生物标志物": "诊断标志物、预后标志物、治疗靶点等，使用标准命名"
                },
                "relation_prompt": {
                    "activates": "激活关系，明确关系的方向性，提供证据句子，标注置信度",
                    "inhibits": "抑制关系，明确关系的方向性，提供证据句子，标注置信度",
                    "regulates": "调控关系，明确关系的方向性，提供证据句子，标注置信度",
                    "treats": "治疗关系，明确关系的方向性，提供证据句子，标注置信度",
                    "is_indicated_for": "适应症关系，明确关系的方向性，提供证据句子，标注置信度",
                    "is_associated_with": "关联关系，明确关系的方向性，提供证据句子，标注置信度",
                    "correlates_with": "相关性关系，明确关系的方向性，提供证据句子，标注置信度"
                }
            },
            {
                "template_id": "system_gene_regulation",
                "name": "基因调控模板",
                "description": "专门用于基因调控相关研究的模板",
                "entity_prompt": {
                    "转录因子": "调控基因转录的蛋白质，如p53、NF-κB等",
                    "靶基因": "被转录因子调控的基因",
                    "启动子": "基因转录起始区域",
                    "增强子": "增强基因转录的调控元件",
                    "miRNA": "微小RNA，参与转录后调控",
                    "lncRNA": "长链非编码RNA"
                },
                "relation_prompt": {
                    "transcriptionally_regulates": "转录调控关系，转录因子调控靶基因的转录",
                    "binds_to": "结合关系，转录因子结合到DNA序列",
                    "enhances": "增强关系，增强基因表达或功能",
                    "represses": "抑制关系，抑制基因表达或功能",
                    "co_regulates": "共调控关系，多个因子共同调控同一基因"
                }
            },
            {
                "template_id": "system_drug_discovery",
                "name": "药物发现模板",
                "description": "用于药物发现和药物机制研究的模板",
                "entity_prompt": {
                    "药物": "药物化合物名称，包括化学名、商品名等",
                    "靶点": "药物作用的分子靶点，如蛋白质、受体等",
                    "疾病": "药物治疗的疾病",
                    "副作用": "药物可能产生的不良反应",
                    "适应症": "药物的临床应用适应症",
                    "药物类别": "药物的分类，如抗生素、抗肿瘤药等"
                },
                "relation_prompt": {
                    "targets": "靶向关系，药物作用于特定靶点",
                    "treats": "治疗关系，药物用于治疗特定疾病",
                    "causes": "导致关系，药物可能导致的副作用",
                    "is_indicated_for": "适应症关系，药物的临床应用",
                    "inhibits": "抑制关系，药物抑制靶点活性",
                    "activates": "激活关系，药物激活靶点功能"
                }
            },
            {
                "template_id": "system_pathway_analysis",
                "name": "信号通路分析模板",
                "description": "用于信号通路和细胞过程分析的模板",
                "entity_prompt": {
                    "信号分子": "参与信号转导的分子，如激素、细胞因子等",
                    "受体": "接收信号的膜受体或核受体",
                    "激酶": "参与信号转导的激酶，如MAPK、PI3K等",
                    "转录因子": "调控基因表达的转录因子",
                    "通路": "信号转导通路，如MAPK通路、PI3K/AKT通路等",
                    "细胞过程": "细胞生物学过程，如增殖、凋亡、分化等"
                },
                "relation_prompt": {
                    "activates": "激活关系，上游分子激活下游分子",
                    "inhibits": "抑制关系，上游分子抑制下游分子",
                    "phosphorylates": "磷酸化关系，激酶磷酸化底物",
                    "regulates": "调控关系，调控通路或过程",
                    "participates_in": "参与关系，分子参与特定通路或过程",
                    "triggers": "触发关系，触发特定细胞过程"
                }
            }
        ]
        
        return templates

    def list_prompt_configs(self, user_id: Optional[str]) -> List[Dict[str, Any]]:
        """列出用户的所有 prompt 模板"""
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")
        cursor = self.prompt_collection.find({"user_id": user_id}).sort("updated_at", DESCENDING)
        configs = []
        for doc in cursor:
            config = knowledge_prompt_config_from_dict(doc)
            configs.append({
                "template_id": config.template_id,
                "name": config.name,
                "description": config.description,
                "entity_prompt": config.entity_prompt,
                "relation_prompt": config.relation_prompt,
                "constraints": config.constraints,
                "is_default": config.is_default,
                "created_at": config.created_at.isoformat(),
                "updated_at": config.updated_at.isoformat(),
            })
        return configs

    def get_prompt_config(self, user_id: Optional[str], template_id: Optional[str] = None) -> Dict[str, Any]:
        """
        获取 prompt 配置
        
        Args:
            user_id: 用户ID
            template_id: 模板ID，如果为None则返回默认模板或第一个模板
        """
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")
        
        # 如果指定了 template_id，获取指定模板
        if template_id:
            doc = self.prompt_collection.find_one({"user_id": user_id, "template_id": template_id})
            if not doc:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="模板不存在")
            config = knowledge_prompt_config_from_dict(doc)
            return {
                "template_id": config.template_id,
                "name": config.name,
                "description": config.description,
                "entity_prompt": config.entity_prompt,
                "relation_prompt": config.relation_prompt,
                "constraints": config.constraints,
                "is_default": config.is_default,
                "created_at": config.created_at.isoformat(),
                "updated_at": config.updated_at.isoformat(),
            }
        
        # 如果没有指定 template_id，尝试获取默认模板
        doc = self.prompt_collection.find_one({"user_id": user_id, "is_default": True})
        if doc:
            config = knowledge_prompt_config_from_dict(doc)
            return {
                "template_id": config.template_id,
                "name": config.name,
                "description": config.description,
                "entity_prompt": config.entity_prompt,
                "relation_prompt": config.relation_prompt,
                "constraints": config.constraints,
                "is_default": config.is_default,
                "created_at": config.created_at.isoformat(),
                "updated_at": config.updated_at.isoformat(),
            }
        
        # 如果没有默认模板，获取第一个模板
        doc = self.prompt_collection.find_one({"user_id": user_id})
        if doc:
            config = knowledge_prompt_config_from_dict(doc)
            return {
                "template_id": config.template_id,
                "name": config.name,
                "description": config.description,
                "entity_prompt": config.entity_prompt,
                "relation_prompt": config.relation_prompt,
                "constraints": config.constraints,
                "is_default": config.is_default,
                "created_at": config.created_at.isoformat(),
                "updated_at": config.updated_at.isoformat(),
            }

        # 如果没有任何模板，返回默认配置
        default_entity_prompt = {
            "基因/蛋白质": "包括基因名称、蛋白质名称、转录因子等，使用标准命名，识别实体的别名和同义词",
            "疾病": "疾病名称、疾病类型等，使用标准命名",
            "药物": "药物名称、药物类别等，使用标准命名",
            "生物标志物": "诊断标志物、预后标志物、治疗靶点等，使用标准命名"
        }
        default_relation_prompt = {
            "activates": "激活关系，明确关系的方向性，提供证据句子，标注置信度",
            "inhibits": "抑制关系，明确关系的方向性，提供证据句子，标注置信度",
            "regulates": "调控关系，明确关系的方向性，提供证据句子，标注置信度",
            "treats": "治疗关系，明确关系的方向性，提供证据句子，标注置信度",
            "is_indicated_for": "适应症关系，明确关系的方向性，提供证据句子，标注置信度",
            "is_associated_with": "关联关系，明确关系的方向性，提供证据句子，标注置信度",
            "correlates_with": "相关性关系，明确关系的方向性，提供证据句子，标注置信度"
        }
        return {
            "template_id": None,
            "name": None,
            "description": None,
            "entity_prompt": default_entity_prompt,
            "relation_prompt": default_relation_prompt,
            "constraints": None,
            "is_default": False,
            "created_at": self._now().isoformat(),
            "updated_at": self._now().isoformat(),
        }

    def create_prompt_config(self, user_id: Optional[str], payload: Dict[str, Any]) -> Dict[str, Any]:
        """创建新的 prompt 模板"""
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")
        
        entity_prompt = payload.get("entity_prompt")
        relation_prompt = payload.get("relation_prompt")
        if not entity_prompt or not relation_prompt:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="entity_prompt和relation_prompt不能为空")

        # 验证entity_prompt和relation_prompt必须是字典类型，格式为{实体名: 描述}或{关系名: 描述}
        if not isinstance(entity_prompt, dict):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="entity_prompt必须是字典格式：{实体名: 描述, ...}")
        if not isinstance(relation_prompt, dict):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="relation_prompt必须是字典格式：{关系名: 描述, ...}")
        
        # 验证字典的值必须是字符串
        if not all(isinstance(v, str) for v in entity_prompt.values()):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="entity_prompt的值必须是字符串类型")
        if not all(isinstance(v, str) for v in relation_prompt.values()):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="relation_prompt的值必须是字符串类型")

        # 生成 template_id（如果未提供）
        template_id = payload.get("template_id") or str(uuid.uuid4())
        
        # 检查 template_id 是否已存在
        existing = self.prompt_collection.find_one({"user_id": user_id, "template_id": template_id})
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"模板ID {template_id} 已存在")

        # 如果设置为默认模板，取消其他模板的默认状态
        is_default = payload.get("is_default", False)
        if is_default:
            self.prompt_collection.update_many(
                {"user_id": user_id, "is_default": True},
                {"$set": {"is_default": False}}
            )

        config = KnowledgePromptConfig(
            user_id=user_id,
            template_id=template_id,
            name=payload.get("name"),
            description=payload.get("description"),
            entity_prompt=entity_prompt,
            relation_prompt=relation_prompt,
            constraints=payload.get("constraints"),
            is_default=is_default,
            created_at=self._now(),
            updated_at=self._now(),
        )
        self.prompt_collection.insert_one(config.model_dump())
        return self.get_prompt_config(user_id, template_id)

    def update_prompt_config(self, user_id: Optional[str], template_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """更新 prompt 模板"""
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")
        
        doc = self.prompt_collection.find_one({"user_id": user_id, "template_id": template_id})
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="模板不存在")

        update_fields: Dict[str, Any] = {}
        
        if "entity_prompt" in payload:
            entity_prompt = payload["entity_prompt"]
            if not isinstance(entity_prompt, dict):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="entity_prompt必须是字典格式：{实体名: 描述, ...}")
            if not all(isinstance(v, str) for v in entity_prompt.values()):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="entity_prompt的值必须是字符串类型")
            update_fields["entity_prompt"] = entity_prompt

        if "relation_prompt" in payload:
            relation_prompt = payload["relation_prompt"]
            if not isinstance(relation_prompt, dict):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="relation_prompt必须是字典格式：{关系名: 描述, ...}")
            if not all(isinstance(v, str) for v in relation_prompt.values()):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="relation_prompt的值必须是字符串类型")
            update_fields["relation_prompt"] = relation_prompt
        
        if "name" in payload:
            update_fields["name"] = payload["name"]
        if "description" in payload:
            update_fields["description"] = payload["description"]
        if "constraints" in payload:
            update_fields["constraints"] = payload["constraints"]
        
        # 处理 is_default 标志
        if "is_default" in payload:
            is_default = payload["is_default"]
            if is_default:
                # 取消其他模板的默认状态
                self.prompt_collection.update_many(
                    {"user_id": user_id, "is_default": True, "template_id": {"$ne": template_id}},
                    {"$set": {"is_default": False}}
                )
            update_fields["is_default"] = is_default
        
        if update_fields:
            update_fields["updated_at"] = self._now()
        self.prompt_collection.update_one(
                {"user_id": user_id, "template_id": template_id},
                {"$set": update_fields}
            )
        
        return self.get_prompt_config(user_id, template_id)

    def delete_prompt_config(self, user_id: Optional[str], template_id: str) -> None:
        """删除 prompt 模板"""
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")
        
        doc = self.prompt_collection.find_one({"user_id": user_id, "template_id": template_id})
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="模板不存在")
        
        self.prompt_collection.delete_one({"user_id": user_id, "template_id": template_id})

    def save_prompt_config(self, user_id: Optional[str], payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        保存 prompt 配置（兼容旧接口，如果 template_id 存在则更新，否则创建）
        """
        template_id = payload.get("template_id")
        if template_id:
            # 如果 template_id 存在，尝试更新
            doc = self.prompt_collection.find_one({"user_id": user_id, "template_id": template_id})
            if doc:
                return self.update_prompt_config(user_id, template_id, payload)
        
        # 否则创建新模板
        return self.create_prompt_config(user_id, payload)

    # ---------- prompt generation and approval ----------
    
    def generate_prompt(
        self,
        query: str,
        user_id: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        生成提示词（prompt generation mode）
        
        根据用户查询，使用LLM识别上下文（如生物医学、基因调控等），
        然后生成相应的实体和关系抽取提示词，并存储为待审批状态。
        
        Args:
            query: 用户查询/需求描述
            user_id: 用户ID（可选）
            description: 可选的描述信息
        
        Returns:
            生成的提示词信息，包含：
            - pending_prompt_id: 待审批提示ID
            - query: 原始查询
            - context: 识别的上下文
            - entity_prompt: 生成的实体提示词
            - relation_prompt: 生成的关系提示词
            - description: 描述
            - created_at: 创建时间
        
        Raises:
            HTTPException: 当查询为空或LLM调用失败时
        """
        if not query or not query.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="查询不能为空"
            )
        
        logger.info(f"开始生成提示词，查询: {query[:100]}...")
        
        try:
            # 第一步：使用LLM识别查询上下文
            context = self._identify_query_context(query)
            logger.info(f"识别的上下文: {context}")
            
            # 第二步：使用LLM生成提示词
            entity_prompt, relation_prompt = self._generate_prompts_from_context(query, context)
            logger.info(f"生成的实体提示词数量: {len(entity_prompt)}, 关系提示词数量: {len(relation_prompt)}")
            
            # 第三步：存储为待审批状态
            pending_prompt_id = str(uuid.uuid4())
            pending_prompt = {
                "pending_prompt_id": pending_prompt_id,
                "user_id": user_id,
                "query": query.strip(),
                "context": context,
                "entity_prompt": entity_prompt,
                "relation_prompt": relation_prompt,
                "description": description.strip() if description else None,
                "status": "pending",  # pending, approved, rejected
                "created_at": self._now(),
                "updated_at": self._now(),
            }
            
            self.pending_prompts_collection.insert_one(pending_prompt)
            logger.info(f"提示词已生成并存储，pending_prompt_id: {pending_prompt_id}")
            
            return {
                "pending_prompt_id": pending_prompt_id,
                "query": query.strip(),
                "context": context,
                "entity_prompt": entity_prompt,
                "relation_prompt": relation_prompt,
                "description": description.strip() if description else None,
                "created_at": pending_prompt["created_at"].isoformat(),
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"生成提示词时发生错误: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"生成提示词失败: {str(e)}"
            )
    
    def _identify_query_context(self, query: str) -> str:
        """
        使用LLM识别查询的上下文（如生物医学、基因调控、蛋白质相互作用等）
        
        Args:
            query: 用户查询
        
        Returns:
            识别的上下文描述
        """
        from textmsa.utils.llm import create_llm, call_llm, parse_llm_json_response
        
        system_prompt = """你是一个专业的领域识别专家，擅长分析查询内容并识别其所属的研究领域和上下文。

请分析用户查询，识别其所属的研究领域和上下文。常见的领域包括：
- 生物医学（biomedicine）
- 基因调控（gene regulation）
- 蛋白质相互作用（protein-protein interaction）
- 信号通路（signaling pathway）
- 疾病机制（disease mechanism）
- 药物发现（drug discovery）
- 细胞生物学（cell biology）
- 分子生物学（molecular biology）
- 其他相关领域

请返回JSON格式：
{
    "context": "领域名称（中文）",
    "domain": "领域英文标识",
    "reasoning": "识别理由（简要说明）"
}"""

        user_prompt = f"""请分析以下查询并识别其上下文：

查询：{query}

请返回JSON格式的识别结果。"""

        try:
            llm = create_llm()
            response_text = call_llm(llm, system_prompt, user_prompt)
            
            if not response_text:
                logger.warning("LLM返回空响应，使用默认上下文")
                return "生物医学"
            
            response_data = parse_llm_json_response(response_text, default_value=None)
            if not response_data:
                logger.warning("LLM响应解析失败，使用默认上下文")
                return "生物医学"
            
            context = response_data.get("context") or response_data.get("domain") or "生物医学"
            return context
            
        except Exception as e:
            logger.warning(f"识别上下文失败: {e}，使用默认上下文")
            return "生物医学"
    
    def _generate_prompts_from_context(self, query: str, context: str) -> Tuple[Dict[str, str], Dict[str, str]]:
        """
        根据查询和上下文，使用LLM生成实体和关系抽取提示词
        
        Args:
            query: 用户查询
            context: 识别的上下文
        
        Returns:
            (entity_prompt, relation_prompt) 元组，每个都是字典格式 {名称: 描述}
        """
        from textmsa.utils.llm import create_llm, call_llm, parse_llm_json_response
        
        system_prompt = """你是一个专业的提示词工程专家，擅长为知识图谱抽取任务生成高质量的实体和关系定义提示词。

根据用户查询和研究领域上下文，你需要生成：
1. 实体类型定义（entity_prompt）：定义需要抽取的实体类型及其描述
2. 关系类型定义（relation_prompt）：定义需要抽取的关系类型及其描述

实体和关系应该与研究领域和查询内容高度相关。

请返回JSON格式：
{
    "entity_prompt": {
        "实体类型1": "实体描述1",
        "实体类型2": "实体描述2",
        ...
    },
    "relation_prompt": {
        "关系类型1": "关系描述1",
        "关系类型2": "关系描述2",
        ...
    },
    "reasoning": "生成理由（简要说明为什么选择这些实体和关系）"
}

注意：
- 实体类型应该是名词或名词短语（如"基因"、"蛋白质"、"疾病"）
- 关系类型应该是动词或动词短语（如"调控"、"激活"、"抑制"、"关联"）
- 每个描述应该清晰说明该实体或关系的含义和抽取标准
- 实体和关系的数量应该适中（建议5-15个实体，5-15个关系）"""

        user_prompt = f"""用户查询：{query}

研究领域上下文：{context}

请根据以上信息，生成适合该领域和查询的实体和关系抽取提示词。"""

        try:
            llm = create_llm()
            response_text = call_llm(llm, system_prompt, user_prompt)
            
            if not response_text:
                logger.warning("LLM返回空响应，使用默认提示词")
                return self._get_default_prompts()
            
            response_data = parse_llm_json_response(response_text, default_value=None)
            if not response_data:
                logger.warning("LLM响应解析失败，使用默认提示词")
                return self._get_default_prompts()
            
            entity_prompt = response_data.get("entity_prompt", {})
            relation_prompt = response_data.get("relation_prompt", {})
            
            # 验证格式
            if not isinstance(entity_prompt, dict) or not isinstance(relation_prompt, dict):
                logger.warning("LLM返回的提示词格式不正确，使用默认提示词")
                return self._get_default_prompts()
            
            # 验证值都是字符串
            if not all(isinstance(v, str) for v in entity_prompt.values()):
                logger.warning("实体提示词的值必须是字符串，使用默认提示词")
                return self._get_default_prompts()
            
            if not all(isinstance(v, str) for v in relation_prompt.values()):
                logger.warning("关系提示词的值必须是字符串，使用默认提示词")
                return self._get_default_prompts()
            
            # 如果为空，使用默认值
            if not entity_prompt or not relation_prompt:
                logger.warning("生成的提示词为空，使用默认提示词")
                return self._get_default_prompts()
            
            return entity_prompt, relation_prompt
            
        except Exception as e:
            logger.warning(f"生成提示词失败: {e}，使用默认提示词")
            return self._get_default_prompts()
    
    def _get_default_prompts(self) -> Tuple[Dict[str, str], Dict[str, str]]:
        """
        获取默认的实体和关系提示词
        
        Returns:
            (entity_prompt, relation_prompt) 元组
        """
        default_entity_prompt = {
            "基因": "生物学中的遗传单位，编码蛋白质或RNA分子",
            "蛋白质": "由基因编码的功能分子，执行各种生物学功能",
            "疾病": "影响生物体正常功能的病理状态",
            "药物": "用于治疗、预防或诊断疾病的化学物质",
            "细胞": "生物体的基本结构和功能单位",
        }
        
        default_relation_prompt = {
            "调控": "一个实体对另一个实体的表达或功能进行调控",
            "激活": "一个实体增强另一个实体的活性或表达",
            "抑制": "一个实体降低另一个实体的活性或表达",
            "关联": "两个实体之间存在相关性或共同出现",
            "导致": "一个实体是另一个实体产生的原因",
        }
        
        return default_entity_prompt, default_relation_prompt
    
    def approve_prompt(
        self,
        pending_prompt_id: str,
        user_id: Optional[str] = None,
        template_id: Optional[str] = None,
        name: Optional[str] = None,
        is_default: bool = False,
    ) -> Dict[str, Any]:
        """
        审批并保存生成的提示词到提示词库
        
        将待审批的提示词转换为KnowledgePromptConfig并保存到提示词库中。
        
        Args:
            pending_prompt_id: 待审批提示ID
            user_id: 用户ID（可选）
            template_id: 模板ID（可选，如果不提供则自动生成）
            name: 模板名称（可选）
            is_default: 是否设为默认模板
        
        Returns:
            保存的提示词配置信息
        
        Raises:
            HTTPException: 当待审批提示不存在或已审批时
        """
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="请先登录"
            )
        
        # 查找待审批提示
        doc = self.pending_prompts_collection.find_one({"pending_prompt_id": pending_prompt_id})
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="待审批提示不存在"
            )
        
        # 检查是否已审批
        if doc.get("status") != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"提示已{doc.get('status')}，无法重复审批"
            )
        
        # 检查用户权限（只能审批自己的提示）
        if doc.get("user_id") != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权审批此提示"
            )
        
        # 生成template_id（如果未提供）
        if not template_id:
            template_id = str(uuid.uuid4())
        
        # 检查template_id是否已存在
        existing = self.prompt_collection.find_one({"user_id": user_id, "template_id": template_id})
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"模板ID {template_id} 已存在"
            )
        
        # 如果设为默认，先取消其他默认模板
        if is_default:
            self.prompt_collection.update_many(
                {"user_id": user_id, "is_default": True},
                {"$set": {"is_default": False}}
            )
        
        # 创建KnowledgePromptConfig并保存
        entity_prompt = doc.get("entity_prompt", {})
        relation_prompt = doc.get("relation_prompt", {})
        
        if not entity_prompt or not relation_prompt:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="提示词数据不完整"
            )
        
        config = KnowledgePromptConfig(
            user_id=user_id,
            template_id=template_id,
            name=name or doc.get("description") or f"从查询生成的提示词",
            description=doc.get("description") or f"基于查询 '{doc.get('query', '')[:50]}...' 生成的提示词",
            entity_prompt=entity_prompt,
            relation_prompt=relation_prompt,
            is_default=is_default,
            created_at=self._now(),
            updated_at=self._now(),
        )
        
        self.prompt_collection.insert_one(config.model_dump())
        
        # 更新待审批提示的状态
        self.pending_prompts_collection.update_one(
            {"pending_prompt_id": pending_prompt_id},
            {
                "$set": {
                    "status": "approved",
                    "approved_at": self._now(),
                    "template_id": template_id,
                    "updated_at": self._now(),
                }
            }
        )
        
        logger.info(f"提示词已审批并保存，pending_prompt_id: {pending_prompt_id}, template_id: {template_id}")
        
        return self.get_prompt_config(user_id, template_id)
    
    def list_pending_prompts(
        self,
        user_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        skip: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        列出待审批的提示词
        
        Args:
            user_id: 用户ID（可选，如果提供则只返回该用户的提示）
            status: 状态过滤（pending/approved/rejected，可选）
            limit: 返回数量限制
            skip: 跳过数量
        
        Returns:
            待审批提示词列表
        """
        query: Dict[str, Any] = {}
        if user_id:
            query["user_id"] = user_id
        if status:
            query["status"] = status
        
        cursor = self.pending_prompts_collection.find(query).sort("created_at", DESCENDING).skip(skip).limit(limit)
        
        results = []
        for doc in cursor:
            results.append({
                "pending_prompt_id": doc.get("pending_prompt_id"),
                "query": doc.get("query"),
                "context": doc.get("context"),
                "entity_prompt": doc.get("entity_prompt", {}),
                "relation_prompt": doc.get("relation_prompt", {}),
                "description": doc.get("description"),
                "status": doc.get("status", "pending"),
                "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
                "updated_at": doc.get("updated_at").isoformat() if doc.get("updated_at") else None,
            })
        
        return results


# --------- singleton helper ---------
_knowledge_service: Optional[KnowledgeService] = None


def get_knowledge_service() -> KnowledgeService:
    global _knowledge_service
    if _knowledge_service is None:
        _knowledge_service = KnowledgeService()
    return _knowledge_service
