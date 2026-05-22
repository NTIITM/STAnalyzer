/**
 * Agent (项目智能助手) 相关类型定义
 */

export type AgentMessageRole = 'user' | 'assistant' | 'system'

export interface EvidenceSource {
  source_type?: string
  source_id?: string
  content?: string
  relevance_score?: number
  [key: string]: unknown
}

export interface AgentMessageMetadata {
  evidence_sources?: EvidenceSource[]
  execution_time?: number
  status?: string
  job_id?: string
  [key: string]: unknown
}

export interface AgentConversationMessage {
  message_id?: string
  role: AgentMessageRole
  /**
   * 统一的主文案字段
   */
  message: string
  /**
   * 兼容旧字段（仅作为回退，不建议继续使用）
   */
  content?: string
  timestamp?: string
  metadata?: AgentMessageMetadata | null
  /**
   * Agent 可能附带的扩展数据（前端用于渲染 txt/json/code/files 等）
   */
  extra?: Record<string, unknown> | null
}

export interface AgentConversationMessageUI {
  id: string
  role: 'user' | 'agent' | 'system'
  content: string
  time: string
  timestamp?: string
  metadata?: Record<string, unknown> | null
  origin: 'history' | 'local'
  jobId?: string
  status?: 'buffer' | 'streaming' | 'completed' | 'failed'
}

export interface AgentConversationResponse {
  conversation_id: string
  project_id: string
  updated_at?: string | null
  messages: AgentConversationMessage[]
}

export interface AgentMessageRequestPayload {
  project_id: string
  message: string
  conversation_id?: string | null
  message_limit?: number | null
  metadata?: Record<string, unknown> | null
}

export type AgentJobStatus = 'running' | 'completed' | 'failed' | 'cancelled' | 'cancelling'

export type AgentJobStepStatus = 'running' | 'completed'

export interface AgentJobStep {
  name: string
  status: AgentJobStepStatus
  started_at?: string | null
  finished_at?: string | null
  output?: string | null
  message?: string | null
}

export interface AgentJobSummary {
  job_id: string
  status: AgentJobStatus
  steps: AgentJobStep[]
}

export interface AgentProjectSessionPayload {
  conversation: AgentConversationResponse
  /**
   * 若存在未完成的 job，则返回对应的 job_id；否则为 null 或省略
   */
  job_id?: string | null
}

export interface AgentJobsResponse {
  /**
   * 当前未完成的 job 详情（包含执行步骤）；若无未完成 job，则为 null
   */
  job: AgentJobSummary | null
}

export interface AgentStopJobResponse {
  job_id: string
  status: AgentJobStatus | 'cancelling'
  message?: string
}
