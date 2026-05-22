/**
 * Service API (TypeScript)
 * 服务管理和执行相关 API
 */
import request from './request'

// ==================== 类型定义 ====================

/**
 * Service执行状态
 */
export type ExecutionStatus = 'pending' | 'running' | 'completed' | 'failed'


/**
 * 参数定义Schema
 */
export interface ParameterSchema {
  [paramName: string]: {
    type: 'string' | 'number' | 'integer' | 'boolean' | 'array' | 'object' | 'enum' | 'continuous' | 'discrete'
    default?: any
    default_value?: any
    enum?: any[]
    enum_values?: any[]
    min?: number
    max?: number
    min_value?: number
    max_value?: number
    description?: string
    items?: ParameterSchema
  }
}

/**
 * Service信息
 */
/**
 * 输出结果项类型
 */
export type ServiceOutputItemType = 'file' | 'text'

/**
 * 接受的文件类型配置
 * 定义单个文件名的文件类型要求
 */
export interface AcceptedFileConfig {
  /** 文件类型ID列表（支持多个类型） */
  file_type_ids: string[]
  /** 文件描述 */
  description: string
}

/**
 * 接受的文件类型映射
 * key: 文件名（如 "input_data.h5ad"）
 * value: 该文件名的文件类型配置
 */
export interface AcceptedFiles {
  [filename: string]: AcceptedFileConfig
}

/**
 * 文件输出项
 */
export interface FileOutputItem {
  type: 'file'
  filename: string
  description: string
  /** 文件类型ID（必需字段） */
  file_type_id: string
}

/**
 * 文本信息输出项
 */
export interface TextOutputItem {
  type: 'text'
  filename: string
  description: string
}

/**
 * 输出结果配置
 */
export interface ServiceOutputConfig {
  items: Array<FileOutputItem | TextOutputItem>
  collection_description?: string
}

/**
 * Service信息
 */
export interface Service {
  service_id: string
  name: string
  description?: string
  version: string
  baseurl: string
  service_suffix: string
  download_suffix?: string
  parameter_template: Record<string, any>
  parameter_schema?: ParameterSchema
  output_template?: Record<string, any>
  accepted_files?: AcceptedFiles
  output_config?: ServiceOutputConfig
  visibility?: 'private' | 'public' | 'system'
  created_at?: string
  updated_at?: string
  created_by?: string
}

/**
 * Service列表响应
 */
export interface ServiceListResponse {
  services: Service[]
  total: number
}

/**
 * 创建Service请求
 */
export interface ServiceCreateRequest {
  name: string
  description?: string
  version?: string
  baseurl: string
  service_suffix: string
  download_suffix?: string
  parameter_template?: Record<string, any>
  parameter_schema?: ParameterSchema
  accepted_files?: AcceptedFiles
  output_config?: ServiceOutputConfig
  visibility?: 'private' | 'public' | 'system'
}

/**
 * 请求配置（用于向后兼容，保留原有字段）
 */
export type RequestConfig = Record<string, any>

/**
 * 更新Service请求
 */
export interface ServiceUpdateRequest {
  name?: string
  description?: string
  version?: string
  baseurl?: string
  service_suffix?: string
  download_suffix?: string
  visibility?: 'private' | 'public'
  request_config?: RequestConfig
  parameter_template?: Record<string, any>
  parameter_schema?: ParameterSchema
  output_template?: Record<string, any>
  accepted_files?: AcceptedFiles
  output_config?: ServiceOutputConfig
}

/**
 * Service执行请求（与后端对齐）
 */
export interface ServiceExecuteRequest {
  input_file_ids: string[]
  parameters?: Record<string, any>
  project_id?: string
}

/**
 * Service执行响应
 */
export interface ServiceExecution {
  execution_id: string
  service_id: string
  service_name?: string
  user_id: string
  input_file_ids: string[]
  output_file_ids?: string[]
  status: ExecutionStatus
  parameters: Record<string, any>
  response_data?: Record<string, any>
  error_message?: string
  created_at?: string
  started_at?: string
  completed_at?: string
  duration_seconds?: number
}

/**
 * Service执行列表响应
 */
export interface ServiceExecutionListResponse {
  executions: ServiceExecution[]
  total: number
}

// ==================== 类型守卫函数 ====================

/**
 * 检查文件输出项是否包含 file_type_id
 */
export function isFileOutputItemComplete(item: FileOutputItem | TextOutputItem): item is FileOutputItem {
  if (item.type === 'file') {
    return 'file_type_id' in item && typeof item.file_type_id === 'string' && item.file_type_id.length > 0
  }
  return false
}

/**
 * 检查服务是否有 accepted_files 配置
 */
export function hasAcceptedFiles(service: Service): boolean {
  return service.accepted_files !== undefined && 
         service.accepted_files !== null && 
         Object.keys(service.accepted_files).length > 0
}

// ==================== API 函数 ====================

// 服务列表缓存（30秒 TTL）
const SERVICE_LIST_CACHE_TTL = 30000
const serviceListCache = new Map<string, { data: ServiceListResponse; fetchedAt: number }>()

function serviceListCacheKey(visibility?: string, projectId?: string, skip?: number, limit?: number): string {
  return `${visibility || ''}|${projectId || ''}|${skip || 0}|${limit || 100}`
}

/**
 * 获取Service列表（带缓存）
 * @param visibility - 可见性过滤（可选）
 * @param projectId - 项目ID（可选）
 * @param skip - 跳过数量（默认0）
 * @param limit - 返回数量（默认100）
 * @param force - 强制刷新（默认false）
 */
export async function getServiceList(
  visibility?: 'private' | 'public' | 'system',
  projectId?: string,
  skip: number = 0,
  limit: number = 100,
  force: boolean = false
): Promise<ServiceListResponse> {
  const cacheKey = serviceListCacheKey(visibility, projectId, skip, limit)

  if (!force) {
    const cached = serviceListCache.get(cacheKey)
    if (cached && (Date.now() - cached.fetchedAt) < SERVICE_LIST_CACHE_TTL) {
      return cached.data
    }
  }

  const params: any = { skip, limit }
  if (visibility) params.visibility = visibility
  if (projectId) params.project_id = projectId
  
  const result = await request({
    url: '/service/',
    method: 'GET',
    params
  }) as ServiceListResponse

  serviceListCache.set(cacheKey, { data: result, fetchedAt: Date.now() })
  return result
}

/**
 * 清除服务列表缓存
 */
export function clearServiceListCache() {
  serviceListCache.clear()
}

/**
 * 获取Service详情
 * @param serviceId - Service ID
 * 
 * @returns Service对象，包含以下新字段：
 * - accepted_files: 服务接受的输入文件类型（如果配置）
 * - output_config.items 中的文件项包含 file_type_id 字段
 * 
 * @remarks
 * 如果服务是旧数据（没有新字段），响应中可能不包含这些字段。
 * 前端应该优雅处理这种情况。
 */
export async function getService(serviceId: string): Promise<Service> {
  return request({
    url: `/service/${serviceId}`,
    method: 'GET'
  }) as Promise<Service>
}

/**
 * 获取Service详情（别名，用于兼容）
 */
export const getServiceDetail = getService

/**
 * 创建Service
 * @param serviceData - Service创建数据
 * 
 * @remarks
 * 新字段说明：
 * - accepted_files: 可选，定义服务接受的输入文件类型
 * - output_config.items 中的文件项必须包含 file_type_id 字段
 * 
 * @example
 * ```typescript
 * const service = await createService({
 *   name: "服务名称",
 *   baseurl: "https://api.example.com",
 *   service_suffix: "/api/service",
 *   accepted_files: {
 *     "input_data.h5ad": {
 *       file_type_ids: ["preprocessed_single_cell_data"],
 *       description: "输入的单细胞数据文件"
 *     }
 *   },
 *   output_config: {
 *     items: [
 *       {
 *         type: "file",
 *         filename: "output.h5ad",
 *         description: "输出文件",
 *         file_type_id: "preprocessed_single_cell_data"
 *       }
 *     ]
 *   }
 * })
 * ```
 */
export async function createService(serviceData: ServiceCreateRequest): Promise<Service> {
  return request({
    url: '/service/',
    method: 'POST',
    data: serviceData
  }) as Promise<Service>
}

/**
 * 更新Service
 * @param serviceId - Service ID
 * @param updateData - 更新数据
 * 
 * @remarks
 * 可以更新以下新字段：
 * - accepted_files: 更新服务接受的输入文件类型
 * - output_config: 更新输出配置（文件项必须包含 file_type_id）
 * 
 * @example
 * ```typescript
 * await updateService(serviceId, {
 *   accepted_files: {
 *     "input_data.h5ad": {
 *       file_type_ids: ["preprocessed_single_cell_data"],
 *       description: "输入的单细胞数据文件"
 *     }
 *   }
 * })
 * ```
 */
export async function updateService(
  serviceId: string,
  updateData: ServiceUpdateRequest
): Promise<Service> {
  return request({
    url: `/service/${serviceId}`,
    method: 'PUT',
    data: updateData
  }) as Promise<Service>
}

/**
 * 删除Service
 * @param serviceId - Service ID
 */
export async function deleteService(serviceId: string): Promise<{ service_id: string }> {
  return request({
    url: `/service/${serviceId}`,
    method: 'DELETE'
  }) as Promise<{ service_id: string }>
}

/**
 * 执行Service
 * @param serviceId - Service ID
 * @param executeData - 执行数据
 * 
 * @remarks
 * 后端会验证输入文件的 file_type_id 是否符合服务的 accepted_files 要求。
 * 如果文件类型不匹配，会返回 400 错误。
 * 
 * @throws {Error} 如果文件类型不匹配，错误信息会明确指出哪个文件的类型不匹配
 * 
 * @example
 * ```typescript
 * try {
 *   const execution = await executeService(serviceId, {
 *     input_file_ids: ["file_id_1", "file_id_2"],
 *     parameters: { ... }
 *   })
 * } catch (error) {
 *   // 处理文件类型不匹配错误
 *   if (error.message.includes("文件类型")) {
 *     // 显示用户友好的错误提示
 *   }
 * }
 * ```
 */
export async function executeService(
  serviceId: string,
  executeData: ServiceExecuteRequest
): Promise<ServiceExecution> {
  return request({
    url: `/service/${serviceId}/execute`,
    method: 'POST',
    data: executeData
  }) as Promise<ServiceExecution>
}

/**
 * 获取执行记录详情
 * @param executionId - 执行ID
 */
export async function getExecution(executionId: string): Promise<ServiceExecution> {
  return request({
    url: `/service/executions/${executionId}`,
    method: 'GET'
  }) as Promise<ServiceExecution>
}

/**
 * 获取执行记录列表
 * @param serviceId - Service ID过滤（可选）
 * @param userId - 用户ID过滤（可选）
 * @param status - 状态过滤（可选）
 * @param skip - 跳过数量（可选，默认0）
 * @param limit - 返回数量（可选，默认100）
 */
export async function getExecutionList(
  serviceId?: string,
  userId?: string,
  status?: ExecutionStatus,
  project?: string,
  skip: number = 0,
  limit: number = 100
): Promise<ServiceExecutionListResponse> {
  const params: any = { skip, limit }
  if (serviceId) params.service_id = serviceId
  if (userId) params.user_id = userId
  if (status) params.status = status
  if (project) params.project = project
  
  return request({
    url: '/service/executions/',
    method: 'GET',
    params
  }) as Promise<ServiceExecutionListResponse>
}
