# Files Deep Read Agent 实现计划（state / node / prompt）

基于 `files_deep_read_agent_design.md` 与 `file_analysis_agent` 现有实现，调整点：
- `route_decision` 不再存储在 state，路由依赖状态字段的“隐性”判定。
- `need_script` 内嵌在 `read_plan`。
- `integration_history`、`sub_agent_return` 仅在节点内部使用，不进入持久 state。

## 状态设计（TypedDict 风格）
| 字段 | 类型 | 说明 |
| --- | --- | --- |
| user_query | str | 用户原始问题 |
| file_tree | dict | 输入/维护的文件树（含虚拟 root） |
| analysis_plans | list[dict] | `{file_id, user_query, result?}`，计划与结果 |
| read_plan | dict | `{file_ids: list[str], integration_plan: str, report_plan: str, need_script: bool}` |
| generated_files | list[dict] | `{file_id, file_name, file_path, description, from_agent?}` |
| messages | list[dict] | 对话/日志消息 |
| work_dir_path | str | 子 Agent 与集成代码的工作目录 |
| current_plan_idx | int | 当前分析计划指针 |
| integration_code | str \| None | 最新集成代码（成功或待迭代版本） |
| read_results | dict | `{file_id, file_name, preview, file_path?}` 供下游子 agent 使用 |
| final_answer | str \| None | 最终输出 |

> 说明：路由开关由上述字段组合判断；不存储 route_decision。`integration_history`、`sub_agent_return` 等只在节点内使用。

## 节点与路由
- plan_node
  - 输入：user_query + file_tree (+ generated_files/上一轮计划以及结果 摘要)。
  - 产出：analysis_plans（或更新）、read_plan（含 need_script）、可能的 direct_answer。
  - 路由判定（隐性）：若 direct_answer 可读 → read_node；若存在待完成 analysis_plans → analyze_node；若 read_plan.need_script=True 且无待分析 → integrate_node；否则 → read_node。

- analyze_node
  - 取 `analysis_plans[current_plan_idx]` 的 file_id，整理 `read_results`，调用 `file_analysis_agent`（传入 work_dir_path）。
  - 局部接收 sub agent 返回（final_answer、generated_files_info），更新：analysis_plans[i].result、generated_files、file_tree（新增子文件节点）。
  - 推进 current_plan_idx，若全部完成返回 plan_node 重新判定；失败重试可在本节点循环。

- integrate_node
  - 使用 `read_plan.integration_plan` + 相关 file_ids 的 file_info 构造 prompt → codegen → 执行，写入文件至 work_dir_path。
  - 更新 integration_code（成功或迭代版本），写入的文件加入 generated_files/file_tree。
  - 失败时记录局部 integration_history 并重试；成功后 → read_node。

- read_node
  - 读取 `read_plan.file_ids`（含新生成文件），结合 analysis_plans.result / integration 结果，按 `report_plan` + user_query 生成 final_answer。
  - 输出 final_answer → END。

## Prompt 规划
- plan_node_prompt：输入 user_query、file_tree（压缩 JSON）、generated_files 摘要、analysis_results；产出 analysis_plans、read_plan（含 need_script）、可选 direct_answer。
- analyze_node：复用 `file_analysis_agent` 的三类 prompt（info/code/return），调用前整理 read_results/work_dir_path。
- integrate_node_prompt：输入 user_query、integration_plan、目标 file_ids 的 {file_id,name,path,description/preview}、当前 integration_code；约束：读文件用真实路径、写到 work_dir_path、生成所有期望文件，可多轮迭代。
- read_node_prompt：输入 user_query、read_plan、文件全文/摘要、analysis_plans.result、generated_files 摘要，生成结构化 final_answer（含引用文件/生成物）。

## 依赖与调用
- 子 agent：直接调用现有 `file_analysis_agent`（复用其 workflow/状态初始化）。
- 执行层：保持 LangGraph 流程，路由逻辑由 router 函数基于 state 自动判定（不存 route_decision）。

