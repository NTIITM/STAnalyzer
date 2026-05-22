"""
证据融合器
将多源证据整合并生成带溯源的回答
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from textmsa.logging_config import get_logger
from textmsa.services.agent.evidence_types import Evidence
from textmsa.services.agent.llm_client import LLMClient, LLMRequest, get_llm_client

logger = get_logger(__name__)


class EvidenceFusion:
    """证据融合器"""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        """
        初始化证据融合器

        Args:
            llm_client: LLM客户端（可选，默认使用全局实例）
        """
        self.llm_client = llm_client or get_llm_client()

    def fuse_and_generate_answer(
        self,
        user_query: str,
        private_knowledge_evidence: List[Evidence],
        experiment_evidence: List[Evidence],
        literature_evidence: List[Evidence],
    ) -> str:
        """
        融合所有证据并生成最终回答

        Args:
            user_query: 用户查询
            private_knowledge_evidence: 私有知识证据列表
            experiment_evidence: 实验证据列表
            literature_evidence: 文献证据列表

        Returns:
            最终回答（包含来源标注）
        """
        logger.info(
            f"开始融合证据 | 私有知识: {len(private_knowledge_evidence)}, 实验: {len(experiment_evidence)}, 文献: {len(literature_evidence)}"
        )

        # 1. 收集所有证据
        all_evidence = self._collect_all_evidence(
            private_knowledge_evidence,
            experiment_evidence,
            literature_evidence,
        )

        # 如果没有证据，返回默认回答
        if not all_evidence:
            logger.warning("没有可用证据，返回默认回答")
            return "抱歉，未能找到相关的证据来回答您的问题。"

        # 2. 按优先级排序
        sorted_evidence = self._sort_by_priority(all_evidence)

        # 3. 检测冲突
        conflicts = self._detect_conflicts(sorted_evidence)

        # 4. 构建提示词
        system_prompt, user_prompt = self._build_fusion_prompt(
            user_query,
            sorted_evidence,
            conflicts,
        )

        # 5. 生成回答
        try:
            answer = self._generate_answer(system_prompt, user_prompt)
            return answer
        except Exception as e:
            logger.error(f"生成回答失败: {e}", exc_info=True)
            # 降级：返回简单汇总
            return self._generate_fallback_answer(
                user_query, sorted_evidence, conflicts
            )

    def _collect_all_evidence(
        self,
        private_knowledge_evidence: List[Evidence],
        experiment_evidence: List[Evidence],
        literature_evidence: List[Evidence],
    ) -> List[Evidence]:
        """
        收集所有有效证据

        Args:
            private_knowledge_evidence: 私有知识证据列表
            experiment_evidence: 实验证据列表
            literature_evidence: 文献证据列表

        Returns:
            合并后的证据列表（已过滤空证据）
        """
        all_evidence = []

        # 合并所有证据
        all_evidence.extend(private_knowledge_evidence)
        all_evidence.extend(experiment_evidence)
        all_evidence.extend(literature_evidence)

        # 过滤空证据
        valid_evidence = [
            ev for ev in all_evidence if ev.content and ev.content.strip()
        ]

        # 简单去重（基于内容的前100字符）
        seen_contents = set()
        unique_evidence = []
        for ev in valid_evidence:
            content_key = ev.content[:100].strip()
            if content_key not in seen_contents:
                seen_contents.add(content_key)
                unique_evidence.append(ev)

        logger.info(
            f"收集证据完成 | 原始: {len(all_evidence)}, 有效: {len(valid_evidence)}, 去重后: {len(unique_evidence)}"
        )

        return unique_evidence

    def _sort_by_priority(self, evidence_list: List[Evidence]) -> List[Evidence]:
        """
        按优先级排序证据

        优先级规则：
        - 实验证据（priority=3）：最高优先级
        - 私有知识（priority=2）：中等优先级
        - 文献证据（priority=1）：最低优先级

        Args:
            evidence_list: 证据列表

        Returns:
            排序后的证据列表
        """
        # 排序：首先按priority降序，然后按confidence降序
        sorted_list = sorted(
            evidence_list, key=lambda ev: (-ev.priority, -ev.confidence)
        )

        logger.debug(
            f"证据排序完成 | 最高优先级: {sorted_list[0].priority if sorted_list else 'N/A'}"
        )

        return sorted_list

    def _detect_conflicts(self, evidence_list: List[Evidence]) -> List[Dict[str, Any]]:
        """
        检测证据之间的冲突

        Args:
            evidence_list: 证据列表（已排序）

        Returns:
            冲突列表，每个冲突包含 evidence1, evidence2, conflict_description
        """
        conflicts = []

        # 如果证据数量少于2，无法检测冲突
        if len(evidence_list) < 2:
            return conflicts

        # 使用LLM检测冲突（可选，如果失败则跳过）
        try:
            # 构建证据对列表（只检查前10条证据，避免过多LLM调用）
            evidence_pairs = []
            for i in range(min(10, len(evidence_list))):
                for j in range(i + 1, min(10, len(evidence_list))):
                    evidence_pairs.append((evidence_list[i], evidence_list[j]))

            # 如果证据对太多，只检查前5对
            if len(evidence_pairs) > 5:
                evidence_pairs = evidence_pairs[:5]

            for ev1, ev2 in evidence_pairs:
                # 使用LLM判断是否冲突
                conflict = self._check_pair_conflict(ev1, ev2)
                if conflict:
                    conflicts.append(conflict)

        except Exception as e:
            logger.warning(f"冲突检测失败: {e}，跳过冲突检测")
            # 冲突检测失败不影响主流程

        logger.info(f"冲突检测完成 | 发现 {len(conflicts)} 个冲突")

        return conflicts

    def _check_pair_conflict(
        self, ev1: Evidence, ev2: Evidence
    ) -> Optional[Dict[str, Any]]:
        """
        检查一对证据是否冲突

        Args:
            ev1: 证据1
            ev2: 证据2

        Returns:
            如果冲突，返回冲突描述字典；否则返回None
        """
        try:
            prompt = f"""请判断以下两条证据是否在相同主题上给出相反或矛盾的结论。

证据1：
{ev1.content}
来源：{ev1.source_type} - {ev1.source_id}

证据2：
{ev2.content}
来源：{ev2.source_type} - {ev2.source_id}

请判断：
1. 这两条证据是否涉及相同主题？
2. 如果涉及相同主题，它们的结论是否相反或矛盾？

请只返回 "conflict" 或 "no_conflict"，不要其他内容。如果返回 "conflict"，请在下一行简要说明冲突点（不超过50字）。"""

            request = LLMRequest(
                messages=[
                    {
                        "role": "system",
                        "content": "你是一个专业的科学证据分析助手，负责检测证据之间的冲突。",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=100,
            )

            response = self.llm_client.chat(request)
            result = response.content.strip().lower()

            if result.startswith("conflict"):
                # 提取冲突描述
                lines = result.split("\n", 1)
                conflict_desc = (
                    lines[1].strip() if len(lines) > 1 else "证据之间存在矛盾"
                )

                return {
                    "evidence1": ev1,
                    "evidence2": ev2,
                    "conflict_description": conflict_desc,
                }

            return None

        except Exception as e:
            logger.debug(f"检查证据冲突失败: {e}")
            return None

    def _build_fusion_prompt(
        self,
        user_query: str,
        evidence_list: List[Evidence],
        conflicts: List[Dict[str, Any]],
    ) -> Tuple[str, str]:
        """
        构建融合提示词

        Args:
            user_query: 用户查询
            evidence_list: 证据列表（已排序）
            conflicts: 冲突列表

        Returns:
            (system_prompt, user_prompt) 元组
        """
        # 构建系统提示词
        system_prompt = """你是一个专业的科学回答生成助手。你的任务是基于多源证据生成准确、全面的回答。

要求：
1. 优先使用高优先级证据（实验 > 私有知识 > 文献）
2. 如果存在冲突，明确说明冲突点
3. 每个证据都要标注来源（格式：来源类型 - 来源ID）
4. 使用Markdown格式，使回答易读
5. 回答应该简洁但完整，直接回答用户问题
6. 如果证据不足，应该说明

回答格式：
## 核心观点

[基于高优先级证据的核心观点]

## 证据支撑

1. [证据内容] (来源：实验 - {tool_name})
2. [证据内容] (来源：私有知识 - {document_name})
3. [证据内容] (来源：文献 - PMID:{pmid})

## 冲突说明（如有）

- [冲突点描述]"""

        # 构建用户提示词
        evidence_text = ""
        for i, ev in enumerate(evidence_list[:10], 1):  # 最多使用10条证据
            source_label = self._format_source_label(ev)
            evidence_text += f"{i}. {ev.content} (来源：{source_label})\n"

        conflicts_text = ""
        if conflicts:
            conflicts_text = "\n冲突说明：\n"
            for i, conflict in enumerate(conflicts, 1):
                ev1 = conflict["evidence1"]
                ev2 = conflict["evidence2"]
                desc = conflict["conflict_description"]
                conflicts_text += f"- 冲突{i}：{desc}\n"
                conflicts_text += f"  - 证据1：{ev1.content[:100]}... (来源：{self._format_source_label(ev1)})\n"
                conflicts_text += f"  - 证据2：{ev2.content[:100]}... (来源：{self._format_source_label(ev2)})\n"

        user_prompt = f"""用户问题：
{user_query}

证据列表（按优先级排序）：
{evidence_text}
{conflicts_text}

请基于以上证据生成回答。"""

        return system_prompt, user_prompt

    def _format_source_label(self, evidence: Evidence) -> str:
        """格式化证据来源标签"""
        if evidence.source_type == "experiment":
            return f"实验 - {evidence.source_id}"
        elif evidence.source_type == "private_knowledge":
            return f"私有知识 - {evidence.source_id}"
        elif evidence.source_type == "literature":
            return f"文献 - PMID:{evidence.source_id}"
        else:
            return f"{evidence.source_type} - {evidence.source_id}"

    def _generate_answer(self, system_prompt: str, user_prompt: str) -> str:
        """
        生成最终回答

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词

        Returns:
            最终回答
        """
        request = LLMRequest(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,  # 稍高温度以获得更自然的回答
            max_tokens=2000,
        )

        response = self.llm_client.chat(request)
        answer = response.content.strip()

        logger.info(f"生成回答完成 | 长度: {len(answer)}字符")

        return answer

    def _generate_fallback_answer(
        self,
        user_query: str,
        sorted_evidence: List[Evidence],
        conflicts: List[Dict[str, Any]],
    ) -> str:
        """
        生成降级回答（当LLM调用失败时）

        Args:
            user_query: 用户查询
            sorted_evidence: 排序后的证据列表
            conflicts: 冲突列表

        Returns:
            降级回答
        """
        logger.info("使用降级方案生成回答")

        answer_parts = ["基于检索到的证据，回答如下：\n\n"]

        # 添加核心观点（使用最高优先级证据）
        if sorted_evidence:
            top_evidence = sorted_evidence[0]
            answer_parts.append(f"## 核心观点\n\n{top_evidence.content}\n\n")

        # 添加证据支撑
        answer_parts.append("## 证据支撑\n\n")
        for i, ev in enumerate(sorted_evidence[:5], 1):  # 最多使用5条证据
            source_label = self._format_source_label(ev)
            answer_parts.append(f"{i}. {ev.content} (来源：{source_label})\n")

        # 添加冲突说明
        if conflicts:
            answer_parts.append("\n## 冲突说明\n\n")
            for i, conflict in enumerate(conflicts, 1):
                desc = conflict["conflict_description"]
                answer_parts.append(f"- 冲突{i}：{desc}\n")

        answer_parts.append("\n（注：此回答基于可用证据自动生成，可能不够完善）")

        return "".join(answer_parts)


# 全局实例
_evidence_fusion: Optional[EvidenceFusion] = None


def get_evidence_fusion() -> EvidenceFusion:
    """获取证据融合器实例（单例）"""
    global _evidence_fusion
    if _evidence_fusion is None:
        _evidence_fusion = EvidenceFusion()
    return _evidence_fusion
