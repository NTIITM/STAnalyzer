"""
Knowledge Agent Prompt 模板
"""

from __future__ import annotations

import json
from typing import Any

from textmsa.logging_config import get_logger

logger = get_logger(__name__)


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


INTENT_PROMPT = {
    "en": """
You are an intent understanding assistant for literature search. Given a user's question, extract the concrete research intent to help rewrite the query for higher-recall scientific search.

User question:
{user_query}

Identify the user's intent with these requirements:
- Keep all mentioned genes, pathways, diseases, cell types, time windows, and regulatory relationships.
- Keep constraints such as stage, condition, or species if implied.
- Produce a concise rewritten query that can be used directly for literature search (this is the most important field).

Return JSON:
{{
  "rewritten_query": "Concise search query preserving key entities/constraints",
  "intent_summary": "1-2 sentence summary of what the user wants to find"
}}
""",
    "zh": """
你是一个用于文献检索的意图理解助手。给定用户问题，提取清晰的研究意图，以便重写查询、提升科学文献检索的召回。

用户问题：
{user_query}

请识别用户意图，遵循：
- 若提及阶段、条件、物种等限制，请明确保留。
- 生成可直接用于文献检索的简洁重写查询（这是最重要的字段）。

请返回 JSON：
{{
  "rewritten_query": "保留关键实体/限制条件的简洁检索式",
  "intent_summary": "1-2 句描述用户想要找什么"
}}
""",
}


PLAN_PROMPT = {
    "en": """
You are a knowledge reading planning assistant. Based on the user question and the list of retrieved documents, create a reading plan that specifies what content to extract from each document.

User question:
{user_query}

Retrieved documents:
{documents_list}

**Planning Rules:**
1. **Select relevant documents (limit to at most 5 documents):**
   - Only include documents that are relevant to answering the user question
   - Select **no more than 5 documents** in total for the reading plan
   - For each selected document, specify what content should be extracted based on the query

2. **Plan structure:**
   - Each plan item should specify: document_id, title, snippet, plan_detail
   - document_id can be the title or DOI of the document
   - plan_detail should describe what content needs to be extracted from this document based on the user query (e.g., "Extract information about X", "Find details about Y", "Summarize the key findings related to Z")

3. **No sequential ordering required:**
   - Documents can be read independently
   - No need to consider reading order or dependencies between documents

Return JSON:
{{
  "plans": [
    {{
      "document_id": "title or doi of the document",
      "title": "document title",
      "snippet": "document snippet/abstract",
      "plan_detail": "Description of what content to extract from this document based on the user query"
    }}
  ]
}}
""",
    "zh": """
你是知识阅读规划助手。根据用户问题和检索到的文档列表，制定阅读计划，指定从每个文档中提取什么内容。

用户问题：
{user_query}

检索到的文档：
{documents_list}

**规划规则：**
1. **选择相关文献（最多选择 5 篇文献）：**
   - 只包含与回答用户问题相关的文献
   - 整个阅读计划中**最多选择 5 篇文献**
   - 对于每一篇被选择的文献，根据查询指定应该提取什么内容

2. **计划结构：**
   - 每个计划项应指定：document_id, title, snippet, plan_detail
   - document_id 可以是文档的标题或 DOI
   - plan_detail 应描述根据用户查询需要从该文档中提取什么内容（例如："提取关于 X 的信息"、"查找关于 Y 的详细信息"、"总结与 Z 相关的关键发现"）

3. **不需要顺序：**
   - 文档可以独立读取
   - 不需要考虑阅读顺序或文档之间的依赖关系

请返回JSON：
{{
  "plans": [
    {{
      "document_id": "文档的标题或doi",
      "title": "文档标题",
      "snippet": "文档摘要片段",
      "plan_detail": "根据用户查询需要从该文档中提取什么内容的描述"
    }}
  ]
}}
""",
}


READ_PROMPT = {
    "en": """
You are a document analysis assistant. Analyze the following document snippet and extract relevant content based on the user query and plan detail.

User query:
{user_query}

Plan detail:
{plan_detail}

Document information:
- Title: {title}
- Snippet: {snippet}
- URL: {url}
- DOI: {doi}

**Answer Requirements:**
- Your answer must strictly adhere to the plan detail and only report what is found in the document snippet
- Use natural narrative text, not lists or structured formats
- Do NOT include any suggestions, recommendations, or advice beyond what is in the document content
- Do NOT provide any recommendations or suggestions that go beyond the scope of the document content

Please provide a clear and concise answer based on the document snippet.
""",
    "zh": """
你是文档分析助手。请分析以下文档片段，并根据用户查询和计划详情提取相关内容。

用户查询：
{user_query}

计划详情：
{plan_detail}

文档信息：
- 标题：{title}
- 摘要：{snippet}
- 链接：{url}
- DOI：{doi}

**回答要求：**
- 你的回答必须严格忠于计划详情，只报告文档片段中发现的内容
- 使用自然的叙述性文字，不要使用列表或结构化格式
- 不包含任何建议、推荐或超出文档内容范围的建议
- 不要提供任何超出文档内容范围的推荐或建议

请基于文档片段提供简洁明了的回答。
""",
}


ANSWER_PROMPT = {
    "en": """
You are a report generation assistant. Based on the user question and all reading results, produce a comprehensive narrative answer.

User question:
{user_query}

{gene_relation_section}

Reading results:
{reading_results}

**Important Rules:**

1. Generate a narrative final answer that:
   - Is a coherent narrative text based primarily on the reading results{gene_relation_instruction}
   - If gene relation information is provided, consider it as supplementary information to enhance your answer
   - References specific documents using their titles and DOIs (with hyperlinks in Markdown format) when mentioning results
   - Provides a comprehensive analysis of all reading results
   - Does NOT include any suggestions, recommendations, or advice beyond what is in the reading results
   - Is based primarily on the interpretation of the reading results, with gene relation information considered when available

2. The answer should be a natural narrative text, not a list or structured format.

Return JSON:
{{
  "final_answer": "The narrative final answer in Markdown format, based primarily on reading results and including DOI hyperlinks for references"
}}
""",
    "zh": """
你是报告生成助手。根据用户问题和所有阅读结果，生成综合性的叙述性最终答案。

用户问题：
{user_query}

{gene_relation_section}

阅读结果：
{reading_results}

**重要规则：**

1. 生成叙述性的最终答案，要求：
   - 是一段连贯的叙述性文字，主要基于阅读结果{gene_relation_instruction}
   - 如果提供了基因关系信息，将其作为补充信息来增强你的答案
   - 在提及结果时，使用文档标题和DOI（以Markdown超链接形式）引用特定文档
   - 对所有阅读结果进行综合分析
   - 不包含任何建议、推荐或超出阅读结果范围的建议
   - 主要基于对阅读结果的解读，如果提供了基因关系信息，也要考虑它

2. 答案应该是自然的叙述性文字，而不是列表或结构化格式。

请返回JSON：    
{{
  "final_answer": "主要基于阅读结果的叙述性最终答案，以Markdown格式给出，并包含引用文档的DOI超链接"
}}
""",
}


# -----------------------------------------------------------------------------
# 辅助格式化函数
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


def format_intent_prompt(
    user_query: str,
    language: str | None = "en",
) -> str:
    """格式化意图识别 prompt"""
    return _get_prompt(INTENT_PROMPT, language).format(
        user_query=user_query,
    )


def format_plan_prompt(
    user_query: str,
    documents_list: list[dict[str, Any]],
    language: str | None = "en",
) -> str:
    """格式化计划生成 prompt"""
    return _get_prompt(PLAN_PROMPT, language).format(
        user_query=user_query,
        documents_list=_fmt_json(documents_list),
    )


def format_read_prompt(
    user_query: str,
    plan_detail: str,
    title: str,
    snippet: str,
    url: str | None = None,
    doi: str | None = None,
    language: str | None = "en",
) -> str:
    """格式化文档阅读 prompt"""
    return _get_prompt(READ_PROMPT, language).format(
        user_query=user_query,
        plan_detail=plan_detail,
        title=title,
        snippet=snippet,
        url=url or "",
        doi=doi or "",
    )


def format_answer_prompt(
    user_query: str,
    reading_results: str,
    language: str | None = "en",
    gene_relation_result: str | None = None,
) -> str:
    """格式化最终答案生成 prompt"""
    # 处理基因关系结果部分
    if gene_relation_result:
        gene_relation_section_en = f"""Gene relation information:
{gene_relation_result}

"""
        gene_relation_section_zh = f"""基因关系信息：
{gene_relation_result}

"""
        gene_relation_section = gene_relation_section_zh if _normalize_language(language) == "zh" else gene_relation_section_en
        gene_relation_instruction_en = " and gene relation information"
        gene_relation_instruction_zh = "和基因关系信息"
        gene_relation_instruction = gene_relation_instruction_zh if _normalize_language(language) == "zh" else gene_relation_instruction_en
    else:
        gene_relation_section = ""
        gene_relation_instruction = ""
    
    return _get_prompt(ANSWER_PROMPT, language).format(
        user_query=user_query,
        gene_relation_section=gene_relation_section,
        gene_relation_instruction=gene_relation_instruction,
        reading_results=reading_results,
    )

