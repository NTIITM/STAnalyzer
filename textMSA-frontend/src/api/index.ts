/**
 * API 统一导出 (TypeScript)
 * 方便在组件中统一导入使用
 */
export { default as request } from './request'
export { tokenManager, ApiError, type ApiResponse, type UserInfo } from './request'
export * from './user'
export * from './file'
export * from './analysis'
export * from './service'
export * from './knowledge'
export * from './project'
export * from './codegen'
export * from './agent'

// 命名空间导出（可选，方便使用）
import * as userApi from './user'
import * as fileApi from './file'
import * as analysisApi from './analysis'
import * as serviceApi from './service'
import * as knowledgeApi from './knowledge'
import * as projectApi from './project'
import * as codegenApi from './codegen'
import * as agentApi from './agent'

export const api = {
  user: userApi,
  file: fileApi,
  analysis: analysisApi,
  service: serviceApi,
  knowledge: knowledgeApi,
  project: projectApi,
  codegen: codegenApi,
  agent: agentApi
}
