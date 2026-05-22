# Files Analyze Agent 设计文档

## 一、概述

Files deep read Agent 是一个基于 LangGraph 的智能文件分析系统，根据用户查询和上下文文件，自动构建文件树、生成读取计划、执行文件读取、生成子Agent代码，并最终生成分析结果。

1. plan_node: 其首先读取一个文件树，假设给定的为一个树形结构（如果给定的是一个List，则自动将它们加入一个虚拟root的根节点,构建为文件树）、读取树结构以及用户query，判断能否回答用户问题，如果不能，选择文件树中的顶点并制定分析计划，生成分析计划，前往1；如果能，生成阅读计划，如果need_script为true，前往3，否则前往4。(请注意对于csv等大数据文件尽可能的进行分析计划，而去读取分析产生的子文件)
树结构如下{
  file_tree:{
    file_id_1_:{
      filename_
      file_description:
      file_path:
      relation_with_parent: xxxx(如果是构建的虚拟节点)
    }
    children:[
      file_id_2:xxx
      file_id_3:xxx
    ]
  }
}

分析计划 analysis_plans:[
  {
    file_id:file_id_1
    user_query: 希望对其进行的分析服务
    result: 子agent分析执行结果
  }
]

阅读计划 
   read_plan:{
    file_ids: [file_id_1, ..., file_id_n],
    integration_plan:  指导如何通过代码联合分析这些文件得到可用的结果
    report_plan: 如何读取这些文件，以进行最终报告,

  }

2. analyze_node 对于文件树中节点选择确认分析计划后，逐个调用/home/common/hwluo/project/textMSA/textmsa/services/agent/file_analysis_agent生成子agent（传入work_dir），用以保存并生成文件，同时将返回的生成文件加入到对应file_id节点的children中。更新generated_files并更新保存file_tree，同时记录每一个子agent传回的final_answer,传入对应analysis_plan的result中。全部完成后转向节点1。

3. integrate_node进行一个多轮代码生成的循环，输入integration_plan以及对应从file_ids获得的file_info(name\path\description), work_dir,构建prompt, 由codegen_llm生成代码并执行，将文件加入file_ids，文件树、generated_files之后将进入4

4. 读取read_plan的file_ids总所有文件（全部读取），根据用户问题生成结果
