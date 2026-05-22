/**
 * Project API (TypeScript)
 * 项目管理相关 API
 */
import request from './request'

// ==================== 类型定义 ====================

/**
 * 配置模式
 */
export type ConfigMode = 'whitelist' | 'blacklist' | 'all'

/**
 * 知识配置
 */
export interface ProjectKnowledgeConfig {
  mode: ConfigMode
  whitelist: string[]
  blacklist: string[]
}

/**
 * 服务配置
 */
export interface ProjectServiceConfig {
  mode: ConfigMode
  whitelist: string[]
  blacklist: string[]
}

/**
 * 项目信息
 */
export interface Project {
  project_id: string
  user_id: string
  name: string
  description?: string
  knowledge_config: ProjectKnowledgeConfig
  service_config: ProjectServiceConfig
  file_ids: string[]
  created_at: string
  updated_at: string
}

/**
 * 创建项目请求
 */
export interface ProjectCreateRequest {
  name: string
  description?: string
  knowledge_config?: ProjectKnowledgeConfig
  service_config?: ProjectServiceConfig
}

/**
 * 更新项目请求
 */
export interface ProjectUpdateRequest {
  name?: string
  description?: string
  knowledge_config?: ProjectKnowledgeConfig
  service_config?: ProjectServiceConfig
}

/**
 * 添加文件到项目请求
 */
export interface AddFileToProjectRequest {
  file_id: string
}

/**
 * 项目列表响应
 */
export interface ProjectListResponse {
  code: number
  message: string
  data: Project[]
  total: number
}

/**
 * 项目详情响应
 */
export interface ProjectDetailResponse {
  code: number
  message: string
  data: Project
}

/**
 * 项目文件关系详情（新 DAG 数据源）
 */
export interface ProjectFilesRelationsDetail {
  files: any[]
  relations: Array<{
    parent_file_id: string
    child_file_id: string
  }>
}

/**
 * 获取项目文件与关系详情（包含 files 与 relations）
 * @param projectId - 项目ID
 */
export async function getProjectFilesRelations(
  projectId: string
): Promise<ProjectFilesRelationsDetail> {
  return request({
    url: `/project/${projectId}/files-relations`,
    method: 'GET'
  }) as Promise<ProjectFilesRelationsDetail>
}

/**
 * Service-FileType 关系图节点类型
 */
export interface GraphNode {
  node_type: 'file_type' | 'service'
  file_type_id?: string
  service_id?: string
  name: string
  description?: string
  children?: GraphNode[]
}

/**
 * Service-FileType 关系图响应
 */
export interface ServiceFileTypeGraphResponse {
  roots: GraphNode[]
}

// ==================== API 函数 ====================

/**
 * 创建项目
 * @param projectData - 项目数据
 * @returns 创建的项目信息
 */
export async function createProject(
  projectData: ProjectCreateRequest
): Promise<Project> {
  // request 拦截器已经提取了 data 字段，所以直接返回 Project 对象
  return request({
    url: '/project/',
    method: 'POST',
    data: projectData
  }) as Promise<Project>
}

// 项目列表缓存（30秒 TTL）
const PROJECT_LIST_CACHE_TTL = 30000
let projectListCache: { list: Project[]; fetchedAt: number } | null = null

/**
 * 获取项目列表（带缓存）
 * @param skip - 跳过数量（默认0）
 * @param limit - 返回数量限制（默认100）
 * @param force - 强制刷新缓存（默认false）
 * @returns 项目列表
 */
export async function getProjectList(
  skip: number = 0,
  limit: number = 100,
  force: boolean = false
): Promise<Project[]> {
  // 非默认分页参数时跳过缓存
  if (!force && skip === 0 && limit === 100 && projectListCache) {
    const age = Date.now() - projectListCache.fetchedAt
    if (age < PROJECT_LIST_CACHE_TTL) {
      return projectListCache.list
    }
  }

  const result = await request({
    url: '/project/list',
    method: 'GET',
    params: { skip, limit }
  }) as Project[]

  // 仅缓存默认分页参数的结果
  if (skip === 0 && limit === 100) {
    projectListCache = { list: result, fetchedAt: Date.now() }
  }

  return result
}

/**
 * 清除项目列表缓存
 */
export function clearProjectListCache() {
  projectListCache = null
}

/**
 * 获取项目详情
 * @param projectId - 项目ID
 * @returns 项目详情（request 拦截器已提取 data 字段，所以返回的是 Project 对象）
 */
export async function getProject(projectId: string): Promise<Project> {
  // request 拦截器已经提取了 data 字段，所以直接返回 Project 对象
  return request({
    url: `/project/${projectId}`,
    method: 'GET'
  }) as Promise<Project>
}

/**
 * 更新项目信息
 * @param projectId - 项目ID
 * @param projectData - 更新的项目数据
 * @returns 更新后的项目信息
 */
export async function updateProject(
  projectId: string,
  projectData: ProjectUpdateRequest
): Promise<Project> {
  // request 拦截器已经提取了 data 字段，所以直接返回 Project 对象
  return request({
    url: `/project/${projectId}`,
    method: 'PUT',
    data: projectData
  }) as Promise<Project>
}

/**
 * 删除项目
 * @param projectId - 项目ID
 * @returns 删除结果
 */
export async function deleteProject(projectId: string): Promise<{ success: boolean; message: string }> {
  // request 拦截器已经提取了 data 字段，如果后端返回的是 { message }，则直接返回
  // 否则返回默认成功消息
  try {
    const result = await request({
      url: `/project/${projectId}`,
      method: 'DELETE'
    }) as any
    
    return {
      success: true,
      message: result?.message || '项目删除成功'
    }
  } catch (error: any) {
    // 如果删除成功但返回格式不符合预期，仍然返回成功
    return {
      success: true,
      message: error.message || '项目删除成功'
    }
  }
}

/**
 * 向项目添加文件
 * @param projectId - 项目ID
 * @param fileId - 文件ID
 * @returns 更新后的项目信息
 */
export async function addFileToProject(
  projectId: string,
  fileId: string
): Promise<Project> {
  return request({
    url: `/project/${projectId}/file`,
    method: 'POST',
    data: { file_id: fileId }
  }) as Promise<Project>
}

/**
 * 从项目移除文件
 * @param projectId - 项目ID
 * @param fileId - 文件ID
 * @returns 更新后的项目信息
 */
export async function removeFileFromProject(
  projectId: string,
  fileId: string
): Promise<Project> {
  return request({
    url: `/project/${projectId}/file/${fileId}`,
    method: 'DELETE'
  }) as Promise<Project>
}

/**
 * 获取项目的文件列表
 * @param projectId - 项目ID
 * @returns 文件ID列表
 */
export async function getProjectFiles(projectId: string): Promise<string[]> {
  const response = await request({
    url: `/project/${projectId}/files`,
    method: 'GET'
  }) as { code: number; message: string; data: string[] }
  
  return response.data
}

/**
 * 更新项目知识配置
 * @param projectId - 项目ID
 * @param config - 知识配置
 * @returns 更新后的项目信息
 */
export async function updateProjectKnowledgeConfig(
  projectId: string,
  config: ProjectKnowledgeConfig
): Promise<Project> {
  const response = await request({
    url: `/project/${projectId}/knowledge-config`,
    method: 'PUT',
    data: config
  }) as { code: number; message: string; data: Project }
  
  return response.data
}

/**
 * 更新项目服务配置
 * @param projectId - 项目ID
 * @param config - 服务配置
 * @returns 更新后的项目信息
 */
export async function updateProjectServiceConfig(
  projectId: string,
  config: ProjectServiceConfig
): Promise<Project> {
  const response = await request({
    url: `/project/${projectId}/service-config`,
    method: 'PUT',
    data: config
  }) as { code: number; message: string; data: Project }
  
  return response.data
}

/**
 * 获取项目的 Service-FileType 关系图
 * @param projectId - 项目ID（可选）。若提供，则只返回该项目内的服务；若不提供，则返回所有可见服务
 * @param fileTypeId - 文件类型ID（可选），指定起始节点，从该文件类型开始裁剪子图
 * @param depth - 深度限制（可选，仅在提供 file_type_id 时生效）。从起始文件类型出发的最大搜索深度（按节点层级计，0 表示仅包含起点本身）
 * @returns 关系图数据
 */
export async function getProjectServiceFileTypeGraph(
  projectId?: string,
  fileTypeId?: string,
  depth?: number
): Promise<ServiceFileTypeGraphResponse> {
  const params: any = {}
  if (projectId) {
    params.project_id = projectId
  }
  if (fileTypeId) {
    params.file_type_id = fileTypeId
  }
  if (depth !== undefined) {
    params.depth = depth
  }
  
  return request({
    url: '/project/service-filetype-graph',
    method: 'GET',
    params
  }) as Promise<ServiceFileTypeGraphResponse>
}

