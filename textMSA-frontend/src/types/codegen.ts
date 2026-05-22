export type CodegenLanguage = 'python' | 'r' | 'julia' | 'bash'

export type CodegenTemplateStatus =
  | 'template_generated'
  | 'template_confirmed'
  | 'code_generated'


export type CodegenExecutionStatus = 'pending' | 'running' | 'completed' | 'failed' 

export interface CodegenTemplate {
  template_id: string
  name?: string
  description?: string | null
  user_requirement: string
  input_file_name?: string
  input_file_description?: string | null
  parameter_template: Record<string, any>
  parameter_schema?: Record<string, any> | null
  output_config: Record<string, any> | null
  generated_code: string | null
  code_language: CodegenLanguage | string
  status: CodegenTemplateStatus | string
  created_at?: string
  created_by?: string
  service_id: string | null
  project_id: string | null
  error_message?: string | null
  metadata?: Record<string, any>
}

export interface CodegenTemplateList {
  templates: CodegenTemplate[]
  total: number
}

export interface CodegenTemplateListParams {
  skip?: number
  limit?: number
  projectId?: string
  serviceId?: string
  status?: CodegenTemplateStatus | CodegenTemplateStatus[]
}

export interface CodegenTemplateUpdatePayload {
  generated_code?: string
  status?: CodegenTemplateStatus | string
  parameters?: Record<string, any>
}

export interface CodegenExecutePayload {
  template_id: string
  parameters?: Record<string, any>
}

export interface CodegenExecuteResponse {
  execution_id: string
  template_id: string
  status: string
  created_at: string
}

export interface CodegenExecution {
  execution_id: string
  template_id: string
  user_id: string
  code: string
  language: CodegenLanguage | string
  parameters: Record<string, any>
  status: CodegenExecutionStatus | string
  input_file_id?: string
  output_file_id?: string | null
  output_config?: Record<string, any> | null
  error_message?: string | null
  execution_log?: string | null
  created_at?: string
  started_at?: string | null
  completed_at?: string | null
  duration_seconds?: number | null
}

export interface CodegenExecutionList {
  executions: CodegenExecution[]
  total: number
}

export interface CodegenExecutionListParams {
  templateId?: string
  projectId?: string
  serviceId?: string
  status?: CodegenExecutionStatus | CodegenExecutionStatus[]
  skip?: number
  limit?: number
}

export interface CodegenConversationMessage {
  role: 'user' | 'agent' | 'system'
  text: string
  time: string
  requires_action?: boolean
}

export interface CodegenConversation {
  template_id: string
  messages: CodegenConversationMessage[]
}

export interface CodegenConversationStartPayload {
  user_requirement: string
  project_id?: string
  service_id?: string
  projectId?: string
  input_filename?: string
  input_file_description?: string | null
  context?: string
  output_config?: Record<string, any> | null
}

export interface CodegenConversationStartResponse {
  template_id: string
  conversation_id: string
  template: CodegenTemplate
  agent_message: string
}

export interface CodegenConversationContinuePayload {
  message: string
}

export interface CodegenConversationContinueResponse {
  template: CodegenTemplate
  agent_message: string
  requires_action?: boolean
  conversation_ended?: boolean
}

export interface CodegenConversationHistoryResponse {
  template_id: string
  messages: CodegenConversationMessage[]
}
