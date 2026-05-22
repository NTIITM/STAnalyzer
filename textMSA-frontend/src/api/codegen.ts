/**
 * Codegen API (TypeScript)
 * 代码生成模板、会话和执行相关 API
 * 
 * 覆盖所有生命周期和会话端点，符合需求 R1-R7：
 * - R1: Template Discovery & Context (listTemplates, getTemplate)
 * - R2: Conversation-Driven Template Creation (startConversation, continueConversation, getConversation)
 * - R3: Template Review & Editing (getTemplate, updateTemplate)
 * - R4: Lifecycle Actions (confirmTemplate, generateCode, finalizeTemplate)
 * - R5: Execution Management (executeTemplate, listTemplateExecutions, getTemplateExecution)
 * - R6: Feedback & Error Handling (handled by shared request helper)
 * - R7: Persistence & Navigation (projectId/serviceId support throughout)
 */
import request from './request'
import type {
  CodegenTemplate,
  CodegenTemplateList,
  CodegenTemplateListParams,
  CodegenTemplateUpdatePayload,
  CodegenExecutePayload,
  CodegenExecuteResponse,
  CodegenExecution,
  CodegenExecutionList,
  CodegenExecutionListParams,
  CodegenConversationStartPayload,
  CodegenConversationStartResponse,
  CodegenConversationContinuePayload,
  CodegenConversationContinueResponse,
  CodegenConversationHistoryResponse
} from '../types/codegen'

// ==================== Template API ====================

/**
 * 获取模板列表
 * @overload
 * @param params - 查询参数对象（projectId, serviceId, status, skip, limit）
 * @returns 模板列表对象（包含 templates 和 total）
 */
export async function listTemplates(
  params?: CodegenTemplateListParams
): Promise<CodegenTemplateList>


/**
 * 获取模板列表（实现）
 */
export async function listTemplates(
  paramsOrSkip?: CodegenTemplateListParams | number,
  limit?: number
): Promise<CodegenTemplateList | CodegenTemplate[]> {
  let queryParams: Record<string, any> = {}
  
  // 兼容旧版调用方式：listTemplates(skip, limit)
  if (typeof paramsOrSkip === 'number' && typeof limit === 'number') {
    queryParams = { skip: paramsOrSkip, limit }
    const response = await request({
      url: '/codegen/templates',
      method: 'GET',
      params: queryParams
    }) as CodegenTemplateList
    // 返回数组以保持向后兼容
    return response.templates
  }
  
  // 新版调用方式：listTemplates(params)
  const params = paramsOrSkip as CodegenTemplateListParams | undefined
  if (params?.skip !== undefined) {
    queryParams.skip = params.skip
  }
  if (params?.limit !== undefined) {
    queryParams.limit = params.limit
  }
  if (params?.projectId) {
    queryParams.project_id = params.projectId
  }
  if (params?.serviceId) {
    queryParams.service_id = params.serviceId
  }
  if (params?.status) {
    if (Array.isArray(params.status)) {
      queryParams.status = params.status.join(',')
    } else {
      queryParams.status = params.status
    }
  }

  return request({
    url: '/codegen/templates',
    method: 'GET',
    params: queryParams
  }) as Promise<CodegenTemplateList>
}

/**
 * 获取模板详情 (R3)
 * @param templateId - 模板ID
 * @returns 模板详情对象
 */
export async function getTemplate(templateId: string): Promise<CodegenTemplate> {
  return request({
    url: `/codegen/templates/${templateId}`,
    method: 'GET'
  }) as Promise<CodegenTemplate>
}

/**
 * 更新模板 (R3)
 * @param templateId - 模板ID
 * @param payload - 更新数据（支持更新代码、参数和状态）
 * @returns 更新后的模板对象
 */
export async function updateTemplate(
  templateId: string,
  payload: CodegenTemplateUpdatePayload
): Promise<CodegenTemplate> {
  return request({
    url: `/codegen/templates/${templateId}`,
    method: 'PUT',
    data: payload
  }) as Promise<CodegenTemplate>
}

/**
 * 确认模板 (R4)
 * @param templateId - 模板ID
 * @returns 确认后的模板对象（状态变为 template_confirmed）
 */
export async function confirmTemplate(templateId: string): Promise<CodegenTemplate> {
  return request({
    url: `/codegen/templates/${templateId}/confirm`,
    method: 'POST'
  }) as Promise<CodegenTemplate>
}

/**
 * 生成代码 (R4)
 * @param templateId - 模板ID（必须处于 template_confirmed 状态）
 * @returns 生成代码后的模板对象（状态变为 code_generated）
 */
export async function generateCode(templateId: string): Promise<CodegenTemplate> {
  return request({
    url: `/codegen/templates/${templateId}/generate-code`,
    method: 'POST'
  }) as Promise<CodegenTemplate>
}

/**
 * 完成模板（最终化）(R4)
 * @param templateId - 模板ID（必须已成功执行）
 * @returns 最终化后的模板对象
 */
export async function finalizeTemplate(templateId: string): Promise<CodegenTemplate> {
  return request({
    url: `/codegen/templates/${templateId}/finalize`,
    method: 'POST'
  }) as Promise<CodegenTemplate>
}

/**
 * 执行模板 (R5)
 * @param templateId - 模板ID（必须处于 code_generated 状态）
 * @param payload - 执行参数（可选，包含参数覆盖、projectId、serviceId）
 * @returns 执行响应对象（包含 execution_id）
 */
export async function executeTemplate(
  templateId: string,
  payload?: CodegenExecutePayload
): Promise<CodegenExecuteResponse> {
  const requestPayload: Record<string, any> = {}
  
  if (payload?.parameters) {
    requestPayload.parameters = payload.parameters
  }
  if (payload?.template_id) {
    requestPayload.template_id = payload.template_id
  }

  return request({
    url: `/codegen/templates/${templateId}/execute`,
    method: 'POST',
    data: Object.keys(requestPayload).length > 0 ? requestPayload : undefined
  }) as Promise<CodegenExecuteResponse>
}

// ==================== Conversation API ====================

/**
 * 启动新会话 (R2)
 * @param payload - 会话启动参数（包含用户需求、可选的文件信息、项目/服务上下文）
 * @returns 会话启动响应（包含模板ID、会话ID、初始模板和代理消息）
 */
export async function startConversation(
  payload: CodegenConversationStartPayload
): Promise<CodegenConversationStartResponse> {
  const requestPayload: Record<string, any> = {
    user_requirement: payload.user_requirement
  }
  
  // 支持 project_id 和 projectId 两种格式
  if (payload.project_id) {
    requestPayload.project_id = payload.project_id
  } else if (payload.projectId) {
    requestPayload.project_id = payload.projectId
  }
  
  if (payload.service_id) {
    requestPayload.service_id = payload.service_id
  }
  // 支持 input_filename 和 input_file_description（R2 要求）
  if (payload.input_filename) {
    requestPayload.input_filename = payload.input_filename
  }
  if (payload.input_file_description !== undefined) {
    requestPayload.input_file_description = payload.input_file_description
  }

  // 支持额外上下文和输出配置（可选）
  if (payload.context) {
    requestPayload.context = payload.context
  }
  if (payload.output_config) {
    requestPayload.output_config = payload.output_config
  }

  return request({
    url: '/codegen/conversations/start',
    method: 'POST',
    data: requestPayload
  }) as Promise<CodegenConversationStartResponse>
}

/**
 * 继续会话 (R2)
 * @param templateId - 模板ID
 * @param payload - 继续会话参数（包含用户消息）
 * @returns 继续会话响应（包含更新的模板和代理回复）
 */
export async function continueConversation(
  templateId: string,
  payload: CodegenConversationContinuePayload
): Promise<CodegenConversationContinueResponse> {
  return request({
    url: `/codegen/conversations/${templateId}/continue`,
    method: 'POST',
    data: payload
  }) as Promise<CodegenConversationContinueResponse>
}

/**
 * 获取会话历史 (R2)
 * @param templateId - 模板ID
 * @returns 会话历史响应（包含所有消息列表）
 */
export async function getConversation(
  templateId: string
): Promise<CodegenConversationHistoryResponse> {
  return request({
    url: `/codegen/conversations/${templateId}`,
    method: 'GET'
  }) as Promise<CodegenConversationHistoryResponse>
}

// ==================== Execution API ====================

/**
 * 获取执行记录列表 (R5)
 * @param params - 查询参数（templateId, projectId, serviceId, status, skip, limit）
 * @returns 执行记录列表（按创建时间倒序，最新的在前）
 */
export async function listTemplateExecutions(
  params?: CodegenExecutionListParams
): Promise<CodegenExecutionList> {
  const queryParams: Record<string, any> = {}
  
  if (params?.templateId) {
    queryParams.template_id = params.templateId
  }
  if (params?.projectId) {
    queryParams.project_id = params.projectId
  }
  if (params?.serviceId) {
    queryParams.service_id = params.serviceId
  }
  if (params?.status) {
    if (Array.isArray(params.status)) {
      queryParams.status = params.status.join(',')
    } else {
      queryParams.status = params.status
    }
  }
  if (params?.skip !== undefined) {
    queryParams.skip = params.skip
  }
  if (params?.limit !== undefined) {
    queryParams.limit = params.limit
  }

  return request({
    url: '/codegen/executions',
    method: 'GET',
    params: queryParams
  }) as Promise<CodegenExecutionList>
}

/**
 * 获取执行记录详情 (R5)
 * @param executionId - 执行ID
 * @returns 执行详情对象（包含状态、日志、输出和错误信息）
 */
export async function getTemplateExecution(executionId: string): Promise<CodegenExecution> {
  return request({
    url: `/codegen/executions/${executionId}`,
    method: 'GET'
  }) as Promise<CodegenExecution>
}
