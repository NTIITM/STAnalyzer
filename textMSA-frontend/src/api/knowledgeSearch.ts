/**
 * 知识检索 API (TypeScript)
 * 知识检索和文档字典管理相关 API
 */
import request from './request'

// ==================== 类型定义 ====================

/**
 * 知识文档字典
 */
export interface KnowledgeDocumentDict {
  title: string                    // 文档标题（主键）
  query: string                   // 查询字符串
  project_id: string              // 项目ID
  source: string                   // 数据源标识
  snippet?: string                 // 摘要或内容片段
  url?: string                     // 文献链接
  doi?: string                     // DOI
  published_at?: string            // 发表时间
  authors?: string[]               // 作者列表
  journal?: string                 // 期刊或会议
  publisher?: string               // 出版商
  source_type?: string             // 文献类型
  score?: number                   // 相关性评分
  metadata?: Record<string, any>   // 附加元数据
}

/**
 * 按 query 分组的文档字典
 */
export interface KnowledgeDocumentDictGrouped {
  query: string                          // 查询字符串
  documents: KnowledgeDocumentDict[]     // 该查询下的文档列表
}

/**
 * 知识检索请求
 */
export interface KnowledgeSearchRequest {
  query: string                    // 用户查询原文（必填，min_length=1）
  projectId: string                // 项目ID（必填，别名：projectId）
  topK?: number                    // 返回文献数量上限（默认20，范围1-100，别名：topK）
  rewrite?: boolean                // 是否启用查询改写（默认true）
  sources?: string[]               // 指定数据源列表（可选）
  trace?: boolean                  // 是否返回调试信息（默认false）
}

/**
 * 知识文档（检索结果）
 */
export interface KnowledgeDocument {
  source: string                    // 数据源标识（如 pubmed/arxiv/crossref）
  title: string                     // 文献标题
  snippet: string                   // 摘要或内容片段
  url?: string                      // 文献链接
  doi?: string                      // DOI
  published_at?: string            // 发表时间（ISO字符串或年份）
  authors: string[]                 // 作者列表
  journal?: string                  // 期刊或会议
  publisher?: string                // 出版商
  source_type?: string              // 文献类型
  score?: number                    // 相关性评分
  metadata?: Record<string, any>   // 附加元数据
}

/**
 * 知识检索响应数据
 */
export interface KnowledgeSearchResponseData {
  rewrite_query: string           // 最终用于检索的查询
  datasources_used: string[]       // 本次使用的数据源
  documents: KnowledgeDocument[]   // 检索到的文献列表
  usage?: object                   // LLM/请求消耗信息
  errors: object[]                 // 各数据源错误信息
}

/**
 * 知识检索响应
 */
export interface KnowledgeSearchResponse {
  code: number                     // 业务状态码（200表示成功）
  message: string                 // 提示信息
  data: KnowledgeSearchResponseData
}

/**
 * 创建文档字典请求
 */
export interface KnowledgeDocumentDictCreateRequest {
  title: string                   // 文档标题（必填，作为主键）
  query: string                   // 查询字符串（必填）
  project_id: string              // 项目ID（必填）
  source: string                  // 数据源标识（必填）
  snippet?: string                // 摘要或内容片段（可选）
  url?: string                    // 文献链接（可选）
  doi?: string                    // DOI（可选）
  published_at?: string           // 发表时间（可选）
  authors?: string[]              // 作者列表（可选）
  journal?: string                // 期刊或会议（可选）
  publisher?: string              // 出版商（可选）
  source_type?: string            // 文献类型（可选）
  score?: number                  // 相关性评分（可选）
  metadata?: object               // 附加元数据（可选）
}

// ==================== API 函数 ====================

/**
 * 规范化文档对象，处理 metadata 字段映射
 */
function normalizeDocument(doc: any): KnowledgeDocumentDict {
  // 从 metadata 中提取 publisher（如果存在）
  if (doc.metadata && doc.metadata.publisher && !doc.publisher) {
    doc.publisher = doc.metadata.publisher
  }
  
  return doc as KnowledgeDocumentDict
}

/**
 * 获取项目文档列表（按 query 分组）
 * @param projectId - 项目ID
 * @returns 按 query 分组的文档列表
 */
export async function getDocumentDictsByProject(
  projectId: string
): Promise<KnowledgeDocumentDictGrouped[]> {
  const response = await request({
    url: `/knowledge/document-dict/project/${projectId}`,
    method: 'GET'
  }) as any
  
  // API 返回格式: { project_id, groups, total_queries, total_documents }
  // 需要提取 groups 数组并规范化文档对象
  if (response && Array.isArray(response.groups)) {
    return response.groups.map((group: any) => ({
      query: group.query,
      documents: group.documents.map(normalizeDocument)
    }))
  }
  
  // 兼容直接返回数组的情况
  if (Array.isArray(response)) {
    return response.map((group: any) => ({
      query: group.query,
      documents: Array.isArray(group.documents) 
        ? group.documents.map(normalizeDocument)
        : []
    }))
  }
  
  return []
}

/**
 * 知识检索
 * @param payload - 检索请求参数
 * @returns 检索响应数据（request 拦截器已提取 data 字段）
 */
export async function searchKnowledge(
  payload: KnowledgeSearchRequest
): Promise<KnowledgeSearchResponseData> {
  return request({
    url: '/knowledge/search',
    method: 'POST',
    data: {
      query: payload.query,
      projectId: payload.projectId,
      topK: payload.topK ?? 20,
      rewrite: payload.rewrite ?? true,
      sources: payload.sources,
      trace: payload.trace ?? false
    }
  }) as Promise<KnowledgeSearchResponseData>
}

/**
 * 保存文档到字典
 * @param payload - 文档创建请求
 * @returns void
 */
export async function saveDocument(
  payload: KnowledgeDocumentDictCreateRequest
): Promise<void> {
  await request({
    url: '/knowledge/document-dict',
    method: 'POST',
    data: payload
  })
}

/**
 * 删除文档
 * @param title - 文档标题（主键）
 * @returns void
 */
export async function deleteDocument(title: string): Promise<void> {
  await request({
    url: `/knowledge/document-dict/${encodeURIComponent(title)}`,
    method: 'DELETE'
  })
}

