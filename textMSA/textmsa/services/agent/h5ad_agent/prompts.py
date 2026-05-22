"""
H5AD Agent Prompt 模板和格式化函数

定义所有 Prompt 模板字符串和格式化函数。
"""

import json
from typing import Any

from textmsa.logging_config import get_logger

logger = get_logger(__name__)


# ============================================================================
# Prompt 模板
# ============================================================================

QUERY_PARSE_PROMPT = """
你是一个 H5AD 数据分析专家。请解析用户查询，提取查询意图和关键参数。

用户查询：{user_query}

H5AD 文件路径：{h5ad_file_path}

{file_preview_section}

请以 JSON 格式返回解析结果：
{{
  "intent": "查询意图描述（如：查询基因表达、统计细胞数量、筛选特定细胞等）",
  "params": {{}},
  "description": "查询的详细描述"
}}

只返回 JSON，不要其他内容。
"""


CODE_GENERATION_PROMPT = """
你是一个 H5AD 数据查询专家，专门生成用于查询 AnnData 对象的 Python 代码。

任务描述：
- 用户查询：{user_query}
- 查询意图：{parsed_intent}
- 关键参数：{parsed_params}

H5AD 文件信息：
- 文件路径：{h5ad_file_path}
- 数据对象已加载为变量：adata

{file_preview_section}

重要约束：
1. H5AD 文件已经加载为变量 `adata`，无需再次读取
2. 必须使用 anndata 和 scanpy 库进行数据操作
3. **禁止画图**：**绝对禁止**使用任何可视化库（如 matplotlib、seaborn、plotly 等）或 scanpy.pl.* 等可视化函数进行画图操作，**禁止**生成任何图表、图像文件或可视化输出
4. 使用 print() 函数输出所有结果
5. 如果查询基因表达，使用 adata[:, '基因名'].X 或 adata.var_names
6. 如果查询细胞信息，使用 adata.obs
7. 如果需要进行统计，使用 numpy 或 pandas
8. 代码必须可以直接执行，不要包含注释或说明

{retry_context}

请以 JSON 格式返回代码：
{{
  "code": "你的 Python 代码（多行字符串）"
}}

只返回 JSON，不要其他内容。
"""


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


# ============================================================================
# 格式化函数
# ============================================================================

def format_query_parse_prompt(
    user_query: str,
    h5ad_file_path: str,
    file_preview: dict | None = None,
) -> str:
    """
    格式化查询解析 Prompt
    
    Args:
        user_query: 用户查询
        h5ad_file_path: H5AD 文件路径
        file_preview: H5AD 文件预览信息（可选）
    
    Returns:
        格式化后的 Prompt 字符串
    """
    logger.debug(
        "Formatting query parse prompt",
        extra={
            "user_query_length": len(user_query),
            "h5ad_file_path": h5ad_file_path,
            "has_file_preview": file_preview is not None,
        },
    )
    
    # 格式化文件预览信息
    file_preview_section = ""
    if file_preview:
        preview_lines = ["文件预览信息："]
        if file_preview.get("n_spots") is not None:
            preview_lines.append(f"- 细胞/spot 数量：{file_preview['n_spots']}")
        if file_preview.get("n_genes") is not None:
            preview_lines.append(f"- 基因数量：{file_preview['n_genes']}")
        if file_preview.get("has_spatial") is not None:
            preview_lines.append(f"- 是否包含空间信息：{'是' if file_preview['has_spatial'] else '否'}")
        if file_preview.get("size") is not None:
            size_mb = file_preview["size"] / (1024 * 1024)
            preview_lines.append(f"- 文件大小：{size_mb:.2f} MB")
        
        # 添加 obs（细胞/spot）的属性列
        obs_columns = file_preview.get("obs_columns", [])
        if obs_columns:
            # 限制显示前20个列，避免信息过长
            display_cols = obs_columns[:5]
            cols_str = ", ".join(display_cols)
            if len(obs_columns) > 5:
                cols_str += f" ... (共{len(obs_columns)}列)"
            preview_lines.append(f"- obs（细胞/spot）属性列：{cols_str}")
        
        # 添加 var（基因）的属性列
        var_columns = file_preview.get("var_columns", [])
        if var_columns:
            display_cols = var_columns[:20]
            cols_str = ", ".join(display_cols)
            if len(var_columns) > 20:
                cols_str += f" ... (共{len(var_columns)}列)"
            preview_lines.append(f"- var（基因）属性列：{cols_str}")
        
        # 添加 obsm（多维数组）的键
        obsm_keys = file_preview.get("obsm_keys", [])
        if obsm_keys:
            keys_str = ", ".join(str(k) for k in obsm_keys)
            preview_lines.append(f"- obsm（多维数组）键：{keys_str}")
        
        # 添加 uns（非结构化注释）的键（只显示前10个）
        uns_keys = file_preview.get("uns_keys", [])
        if uns_keys:
            display_keys = uns_keys[:10]
            keys_str = ", ".join(str(k) for k in display_keys)
            if len(uns_keys) > 10:
                keys_str += f" ... (共{len(uns_keys)}个键)"
            preview_lines.append(f"- uns（非结构化注释）键：{keys_str}")
        
        file_preview_section = "\n".join(preview_lines) + "\n"
    
    prompt = QUERY_PARSE_PROMPT.format(
        user_query=user_query,
        h5ad_file_path=h5ad_file_path,
        file_preview_section=file_preview_section,
    )
    
    logger.debug(
        "Query parse prompt formatted",
        extra={"prompt_length": len(prompt)},
    )
    
    return prompt


def format_code_generation_prompt(
    user_query: str,
    parsed_intent: str,
    parsed_params: dict,
    h5ad_file_path: str,
    retry_context: str = "",
    file_preview: dict | None = None,
) -> str:
    """
    格式化代码生成 Prompt
    
    Args:
        user_query: 用户查询
        parsed_intent: 解析出的查询意图
        parsed_params: 解析出的参数
        h5ad_file_path: H5AD 文件路径
        retry_context: 重试上下文（如果重试，包含上次执行错误信息）
        file_preview: H5AD 文件预览信息（可选）
    
    Returns:
        格式化后的 Prompt 字符串
    """
    logger.debug(
        "Formatting code generation prompt",
        extra={
            "user_query_length": len(user_query),
            "parsed_intent": parsed_intent,
            "parsed_params_keys": list(parsed_params.keys()) if parsed_params else [],
            "h5ad_file_path": h5ad_file_path,
            "is_retry": bool(retry_context),
            "has_file_preview": file_preview is not None,
        },
    )
    
    # 如果没有提供重试上下文，使用空字符串
    if not retry_context:
        retry_context = ""
    else:
        retry_context = f"\n上次执行错误信息：\n{retry_context}\n请根据错误信息修正代码。\n"
    
    # 格式化文件预览信息
    file_preview_section = ""
    if file_preview:
        preview_lines = ["文件预览信息："]
        if file_preview.get("n_spots") is not None:
            preview_lines.append(f"- 细胞/spot 数量：{file_preview['n_spots']}")
        if file_preview.get("n_genes") is not None:
            preview_lines.append(f"- 基因数量：{file_preview['n_genes']}")
        if file_preview.get("has_spatial") is not None:
            preview_lines.append(f"- 是否包含空间信息：{'是' if file_preview['has_spatial'] else '否'}")
        if file_preview.get("size") is not None:
            size_mb = file_preview["size"] / (1024 * 1024)
            preview_lines.append(f"- 文件大小：{size_mb:.2f} MB")
        
        # 添加 obs（细胞/spot）的属性列
        obs_columns = file_preview.get("obs_columns", [])
        if obs_columns:
            # 限制显示前20个列，避免信息过长
            display_cols = obs_columns[:20]
            cols_str = ", ".join(display_cols)
            if len(obs_columns) > 20:
                cols_str += f" ... (共{len(obs_columns)}列)"
            preview_lines.append(f"- obs（细胞/spot）属性列：{cols_str}")
        
        # 添加 var（基因）的属性列
        var_columns = file_preview.get("var_columns", [])
        if var_columns:
            display_cols = var_columns[:20]
            cols_str = ", ".join(display_cols)
            if len(var_columns) > 20:
                cols_str += f" ... (共{len(var_columns)}列)"
            preview_lines.append(f"- var（基因）属性列：{cols_str}")
        
        # 添加 obsm（多维数组）的键
        obsm_keys = file_preview.get("obsm_keys", [])
        if obsm_keys:
            keys_str = ", ".join(str(k) for k in obsm_keys)
            preview_lines.append(f"- obsm（多维数组）键：{keys_str}")
        
        # 添加 uns（非结构化注释）的键（只显示前10个）
        uns_keys = file_preview.get("uns_keys", [])
        if uns_keys:
            display_keys = uns_keys[:10]
            keys_str = ", ".join(str(k) for k in display_keys)
            if len(uns_keys) > 10:
                keys_str += f" ... (共{len(uns_keys)}个键)"
            preview_lines.append(f"- uns（非结构化注释）键：{keys_str}")
        
        file_preview_section = "\n".join(preview_lines) + "\n"
    
    prompt = CODE_GENERATION_PROMPT.format(
        user_query=user_query,
        parsed_intent=parsed_intent,
        parsed_params=json.dumps(parsed_params, ensure_ascii=False, indent=2),
        h5ad_file_path=h5ad_file_path,
        retry_context=retry_context,
        file_preview_section=file_preview_section,
    )
    
    logger.debug(
        "Code generation prompt formatted",
        extra={
            "prompt_length": len(prompt),
            "retry_context_length": len(retry_context),
        },
    )
    
    return prompt


def format_result_synthesis_prompt(
    user_query: str,
    parsed_intent: str,
    raw_result: str,
) -> str:
    """
    格式化结果合成 Prompt
    
    Args:
        user_query: 用户查询
        parsed_intent: 解析出的查询意图
        raw_result: 原始执行结果
    
    Returns:
        格式化后的 Prompt 字符串
    """
    logger.debug(
        "Formatting result synthesis prompt",
        extra={
            "user_query_length": len(user_query),
            "parsed_intent": parsed_intent,
            "raw_result_length": len(raw_result),
        },
    )
    
    prompt = RESULT_SYNTHESIS_PROMPT.format(
        user_query=user_query,
        parsed_intent=parsed_intent,
        raw_result=raw_result,
    )
    
    logger.debug(
        "Result synthesis prompt formatted",
        extra={"prompt_length": len(prompt)},
    )
    
    return prompt

