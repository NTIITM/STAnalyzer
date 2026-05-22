"""
Orchestrator Agent Prompt 模板
"""

from textmsa.services.agent.agent_utils import format_file_tree


ORCHESTRATOR_INTENT_PARSING_PROMPT = {
    "zh": """
你是一个智能意图解析助手，负责分析用户查询并生成整体执行计划。

用户查询：{user_query}

项目文件结构：
{files_tree_string}

请根据用户查询和项目文件结构，生成一个详细的整体执行计划。

在规划执行步骤时，你只能使用以下两类基础动作来构建计划：
1. **execute_service（服务执行）**：调用现有的数据分析或处理服务，并基于已有或中间产生的数据执行这些服务以获得结果
2. **query_knowledge（文献与知识查询）**：对于需要科研文献或外部知识支撑的内容，从外部知识库中检索并获取相关信息

计划应该包括以下方面的考虑：
1. **服务执行**：什么时候调用哪些服务，使用哪些文件作为输入，需要执行什么样的分析或处理
2. **文献与知识查询**：在什么情况下需要查询与用户问题或数据分析结果相关的科研文献或知识，以及需要重点了解哪些内容
3. **结果处理**：如何处理和整合各个步骤的输出结果，以形成对用户有帮助的结论或回答

重要约束：
1. 必须仔细分析用户意图，确定完整的执行流程
2. 文件要从项目文件结构中选择，不要引用不存在或未列出的文件
3. **计划中绝对不要包含具体的文件ID、文件路径等未来信息**。计划应该描述"使用哪些类型的文件"或"处理哪些数据"，而不是具体的文件标识符或路径，因为这些信息只有在实际执行时才能确定
4. 计划应该是一个清晰的、连贯的整体流程描述
5. 在保证能够满足用户需求和逻辑完整的前提下，遵循"最小可行"原则：只保留实现目标所必需的关键步骤，避免不必要的拆分和冗余环节
6. 计划中的每一个具体步骤都必须能够清晰归类为"服务执行"或"文献与知识查询"两类基础动作之一

请严格按照以下 JSON 格式返回：

{{
  "intent": "用户意图的简要描述",
  "plan": "整体执行计划的详细描述，包括服务执行、知识查询等各个步骤的规划（不包含具体的文件ID或路径）",
  "reasoning": "生成此计划的思考过程"
}}

请返回 JSON：
""",
    "en": """
You are an intelligent intent parsing assistant responsible for analyzing user queries and generating overall execution plans.

User query:
{user_query}

Project file structure:
{files_tree_string}

Please generate a detailed overall execution plan based on the user query and project file structure.

When designing the execution steps, you may only use the following two basic actions to construct the plan:
1. **execute_service (Service Execution)**: Call existing data analysis or processing services, and execute them based on existing or intermediate data to obtain results
2. **query_knowledge (Literature and Knowledge Query)**: For content that requires support from research literature or external knowledge, query external knowledge bases to retrieve relevant information

The plan should consider the following aspects:
1. **Service Execution**: When to call which services, which files to use as inputs, and what kind of analysis or processing needs to be performed
2. **Literature and Knowledge Query**: When it is necessary to query research literature or domain knowledge related to the user question or data analysis results, and what key points should be focused on
3. **Result Processing**: How to process and integrate outputs from various steps to form conclusions or answers that are helpful to the user

Important constraints:
1. Carefully analyze user intent to determine the complete execution flow
2. Files must be selected from the project file structure only; do not reference files that do not exist or are not listed
3. **The plan must absolutely not contain specific file IDs, file paths, or other future information**. The plan should describe "which types of files to use" or "which data to process", not specific file identifiers or paths, as this information can only be determined during actual execution
4. The plan should be a clear, coherent overall process description
5. While ensuring that the user's needs are met and the logic is complete, follow a "minimum viable" principle: keep only the key steps necessary to achieve the goal, and avoid unnecessary fragmentation or redundant steps
6. Every concrete step in the plan must be clearly classifiable as one of the two basic actions: "Service Execution" or "Literature and Knowledge Query"

Return strictly in JSON format:

{{
  "intent": "Brief description of user intent",
  "plan": "Detailed description of the overall execution plan, including planning for service execution, literature and knowledge queries, and other steps (without specific file IDs or paths)",
  "reasoning": "Reasoning process for generating this plan"
}}

Return JSON:
""",
}


def _count_files_in_tree(files_tree_list: list[dict]) -> int:
    """递归统计文件树中的文件总数"""
    count = 0
    
    def traverse(node: dict) -> None:
        nonlocal count
        count += 1
        children = node.get("children", [])
        if children:
            for child in children:
                traverse(child)
    
    for root_node in files_tree_list:
        traverse(root_node)
    
    return count


def build_decision_prompt(
    plan: str,
    user_query: str,
    files_tree_list: list[dict],
    decision_history: list[dict],
    execution_feedback: str | None = None,
    knowledge_feedback: str | None = None,
    language: str = "zh",
) -> str:
    """构建决策提示"""
    lang = "en" if str(language).lower().startswith("en") else "zh"
    
    # 文件列表信息（包含 parent_file_id 等关键信息）
    files_summary = ""
    if files_tree_list:
        total_files = _count_files_in_tree(files_tree_list)
        tree_str = format_file_tree(files_tree_list, language=lang)
        files_summary = (
            f"\nProject file list (total {total_files} files):\n{tree_str}"
            if lang == "en"
            else f"\n项目文件列表（共 {total_files} 个文件）：\n{tree_str}"
        )
    
    # 决策历史
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
                elif action == "query_knowledge":
                    query = parameter.get("query", "")
                    param_str = f"query={query[:50]}..." if len(query) > 50 else f"query={query}"
            
            decision_line = f"\n  {idx}. {action}"
            if param_str:
                decision_line += f" ({param_str})"
            decision_line += f": {reasoning}"
            if result:
                result_label = "Result" if lang == "en" else "结果"
                result_str = str(result)
                # 截断过长的结果
                if len(result_str) > 500:
                    result_str = result_str[:500] + "..."
                decision_line += f"\n    {result_label}: {result_str}"
            decision_history_summary += decision_line
    
    # 执行反馈
    execution_feedback_section = ""
    if execution_feedback:
        execution_feedback_section = (
            f"\n\nRecent execution feedback:\n{execution_feedback}"
            if lang == "en"
            else f"\n\n最近的执行反馈：\n{execution_feedback}"
        )
    
    # 知识查询反馈
    knowledge_feedback_section = ""
    if knowledge_feedback:
        knowledge_feedback_section = (
            f"\n\nRecent knowledge query feedback:\n{knowledge_feedback}"
            if lang == "en"
            else f"\n\n最近的知识查询反馈：\n{knowledge_feedback}"
        )
    
    if lang == "en":
        prompt = f"""
Decide the next action based on the following information.
You MUST carefully review the previous decisions and their execution results,
avoid repeating the same failing or ineffective action without new information,
and adjust your next action according to the latest outcomes:

User query:
{user_query}

Execution plan:
{plan}

{files_summary}

{decision_history_summary}{execution_feedback_section}{knowledge_feedback_section}

Choose the next action. Available actions:
1. execute_service - run a service to analyze
2. query_knowledge - query the knowledge base
3. answer_question - information is enough to answer now

Return JSON according to the action chosen:

When choosing an action, you MUST:
1. Explicitly consider the latest execution result(s) in the decision history and feedback.
2. Avoid looping on the same failing configuration; instead, change parameters or choose another action.
3. Only choose execute_service again if you have a clear new hypothesis or different parameters.
4. **When executing services, focus on the task itself rather than specifying concrete methods**: In the query parameter of execute_service, describe the analysis task or processing objective that needs to be completed, rather than specifying which specific analysis method, algorithm, or tool to use. For example, describe "analyze gene expression differences" rather than "use t-test for differential analysis".

For execute_service:
{{
    "action": "execute_service",
    "parameter": {{
        "file_ids": ["file_id1", "file_id2", ...],
        "query": "analysis query or task description (should focus on the task itself, describing the analysis objective or processing requirement, rather than specifying concrete analysis methods, algorithms, or tools)"
    }},
    "reasoning": "brief explanation of why this action is chosen"
}}

For query_knowledge:
{{
    "action": "query_knowledge",
    "parameter": {{
        "query": "knowledge base query that MUST explicitly specify the biological subject (e.g. gene, pathway, cell type) and its relationship to a context, for example: 'What is the role of the gene PDCD1 in T-cell exhaustion and how is it related to the tumor microenvironment?'"
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
来调整下一步的动作选择：

用户问题：
{user_query}

执行计划：
{plan}

{files_summary}

{decision_history_summary}{execution_feedback_section}{knowledge_feedback_section}

请决定**当前这一步**的基础动作类型。你只能在以下三类基础动作中进行选择：
1. **execute_service（服务执行）**：调用现有的数据分析或处理服务，并基于已有或中间产生的数据执行这些服务以获得结果
2. **query_knowledge（文献与知识查询）**：对于需要科研文献或外部知识支撑的内容，从外部知识库中检索并获取相关信息
3. **answer_question（回答问题）**：当前信息已经足够，可以直接给出对用户问题的完整回答，而无需再执行新的服务或查询知识

在选择动作时，你必须同时满足以下约束：
1. 必须明确参考最近一次及历史执行结果，再做决策，保证动作选择与当前进度和已有结果一致；
2. 在参数完全相同且没有新信息的情况下，避免重复执行已经失败或明显无效的动作；
3. 只有在你有新的假设、不同的参数设置或新增的文件/知识来源时，才再次选择 execute_service；
4. 如果现有的信息和结果已经足以形成对用户问题的清晰回答，应优先选择 answer_question，而不是继续追加新的执行步骤；
5. **在执行服务时，不应包含具体的指定方法或技术细节，仅需要专注于任务本身**：在 execute_service 的 query 参数中，应描述需要完成的分析任务或处理目标，而不是指定使用哪种具体的分析方法、算法或工具。例如，应描述"分析基因表达差异"而不是"使用 t-test 进行差异分析"。

请根据选择的动作返回对应的JSON格式：

对于 execute_service：
{{
    "action": "execute_service",
    "parameter": {{
        "file_ids": ["文件id1", "文件id2", ...],
        "query": "分析查询或任务描述（应专注于任务本身，描述需要完成的分析目标或处理需求，而不是指定具体的分析方法、算法或工具）"
    }},
    "reasoning": "选择此动作的简要说明"
}}

对于 query_knowledge：
{{
    "action": "query_knowledge",
    "parameter": {{
        "query": "必须明确说明生物学查询主体（例如基因、通路、细胞类型）以及它与特定情境之间关系的知识库查询，例如：'What is the role of the gene PDCD1 in T-cell exhaustion and how is it related to the tumor microenvironment?'"
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


def build_answer_prompt(
    user_query: str,
    files_tree_list: list[dict],
    decision_history: list[dict],
    language: str = "zh",
) -> str:
    """构建回答提示"""
    lang = "en" if str(language).lower().startswith("en") else "zh"
    
    # 文件信息
    files_info = ""
    if files_tree_list:
        total_files = _count_files_in_tree(files_tree_list)
        tree_str = format_file_tree(files_tree_list, language=lang)
        files_info = (
            f"\nProject file tree (total {total_files} files/dirs):\n{tree_str}"
            if lang == "en"
            else f"\n项目文件树结构（共 {total_files} 个文件/目录）：\n{tree_str}"
        )
    
    # 决策历史
    decision_info = ""
    if decision_history:
        decision_info = "\nDecision history:\n" if lang == "en" else "\n决策历史：\n"
        for idx, decision in enumerate(decision_history, 1):
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
                    param_str = f"file_ids={file_ids}, query={query}"
                elif action == "query_knowledge":
                    query = parameter.get("query", "")
                    param_str = f"query={query}"
            
            decision_info += f"\n{idx}. {action}" + (f" ({param_str})" if param_str else "") + f": {reasoning}\n"
            if result:
                result_label = "Result" if lang == "en" else "结果"
                decision_info += f"    {result_label}: {str(result)[:500]}\n"
    
    # 普通回答
    if lang == "en":
        prompt = f"""
Answer the user's requirement based on the original user query and collected information:

User query:
{user_query}

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
{user_query}

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

