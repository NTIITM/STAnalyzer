/**
 * Knowledge API (TypeScript)
 * 知识管理 / 提取 / Prompt 配置
 */
import request from './request'

// ==================== 类型定义 ====================

export type KnowledgeScope = 'private' | 'public' | 'system'

export interface KnowledgeRelationSummary {
  fromEntity: string
  relation: string
  endEntity: string
}

export interface KnowledgeRecord {
  id: string
  title: string
  description: string
  relationSummary?: KnowledgeRelationSummary
  tags: string[]
  scope: KnowledgeScope
  editedByUser?: boolean
  source?: string
  ownerId?: string
  createdAt?: string
  lastModified?: string
  sharedAt?: string
  metadata?: Record<string, any> | null
}

export interface KnowledgeListQuery {
  scope?: KnowledgeScope
  keyword?: string
  editedOnly?: boolean
  page?: number
  pageSize?: number
  sort?: 'latest' | 'oldest'
  projectId?: string
}

export interface KnowledgeListResponse {
  items: KnowledgeRecord[]
  total: number
  page: number
  pageSize: number
}

export interface KnowledgeMutationPayload {
  title: string
  description: string
  relationSummary: KnowledgeRelationSummary
  tags?: string[]
  scope?: Exclude<KnowledgeScope, 'system'>
  metadata?: Record<string, any>
}

export interface TextExtractionTriplet {
  fromEntity: string
  relation: string
  endEntity: string
  description: string
  source?: string
  confidence: number
}

export interface LiteratureExtractionResult {
  query: string
  expandedKeywords: string[]
  pubmedQuery: string
  articles: Array<Record<string, any>>
  triplets: TextExtractionTriplet[]
  summary?: string
}

export interface PendingPrompt {
  pendingPromptId: string
  query: string
  context: string
  entityPrompt: Record<string, string>
  relationPrompt: Record<string, string>
  description?: string
  createdAt: string
}

export interface KnowledgeExtractTextPayload {
  text: string
  templateId?: string
  source?: string
}

export interface KnowledgeExtractLiteraturePayload {
  query: string
  templateId?: string
  maxResults?: number
}

export interface KnowledgeExtractPromptPayload {
  query: string
  description?: string
}

export interface KnowledgePromptApprovePayload {
  pendingPromptId: string
  templateId?: string
  name?: string
  isDefault?: boolean
}

export interface ShareKnowledgePayload {
  visibility: 'public'
  note?: string
}

export interface PromptTemplate {
  id: string
  label: string
  name?: string
  description?: string
  entityPrompt: Record<string, string>
  relationPrompt: Record<string, string>
  constraints?: string
  isDefault?: boolean
  updatedAt?: string
}

export interface PromptConfigPayload {
  templateId?: string
  name?: string
  description?: string
  entityPrompt: Record<string, string>
  relationPrompt: Record<string, string>
  constraints?: string
  isDefault?: boolean
  createdAt?: string
  updatedAt?: string
}

// ==================== 知识 CRUD ====================

export async function getKnowledgeList(params: KnowledgeListQuery = {}) {
  const data = await request.get<KnowledgeListResponseRaw>('/knowledge', { params: toListQuery(params) })
  return mapKnowledgeListResponse(data)
}

export async function getKnowledgeDetail(id: string) {
  const data = await request.get<KnowledgeRecordRaw>(`/knowledge/${id}`)
  return mapKnowledgeRecord(data)
}

export async function createKnowledge(payload: KnowledgeMutationPayload) {
  const data = await request.post<KnowledgeRecordRaw>('/knowledge', serializeMutationPayload(payload))
  return mapKnowledgeRecord(data)
}

export async function updateKnowledge(id: string, payload: Partial<KnowledgeMutationPayload>) {
  const data = await request.put<KnowledgeRecordRaw>(`/knowledge/${id}`, serializeMutationPayload(payload))
  return mapKnowledgeRecord(data)
}

export async function deleteKnowledge(id: string) {
  return request.delete<{ deleted: boolean }>(`/knowledge/${id}`)
}

export async function shareKnowledge(id: string, payload: ShareKnowledgePayload = { visibility: 'public' }) {
  const data = await request.post<KnowledgeRecordRaw>(`/knowledge/${id}/share`, payload)
  return mapKnowledgeRecord(data)
}

// ==================== 提取与 Prompt 生成 ====================

export async function extractKnowledgeFromText(payload: KnowledgeExtractTextPayload) {
  const data = await request.post<TextExtractionTripletRaw[]>('/knowledge/extract/text', {
    text: payload.text,
    template_id: payload.templateId,
    source: payload.source
  })
  return data.map(mapTriplet)
}

export async function extractKnowledgeFromLiterature(payload: KnowledgeExtractLiteraturePayload) {
  const data = await request.post<LiteratureExtractionResultRaw>('/knowledge/extract/literature', {
    query: payload.query,
    template_id: payload.templateId,
    max_results: payload.maxResults
  })
  return mapLiteratureResult(data)
}

export async function generateKnowledgePrompt(payload: KnowledgeExtractPromptPayload) {
  const data = await request.post<PendingPromptRaw>('/knowledge/extract/prompt', {
    query: payload.query,
    description: payload.description
  })
  return mapPendingPrompt(data)
}

export async function approveGeneratedPrompt(payload: KnowledgePromptApprovePayload) {
  const data = await request.post<PromptConfigRaw>('/knowledge/prompt/approve', {
    pending_prompt_id: payload.pendingPromptId,
    template_id: payload.templateId,
    name: payload.name,
    is_default: payload.isDefault
  })
  return mapPromptConfig(data)
}

// ==================== Prompt 配置 ====================

export async function getKnowledgePromptTemplates() {
  const data = await request.get<PromptTemplateRaw[]>('/knowledge/prompts/templates')
  return (data || []).map(mapPromptTemplate)
}

export async function getKnowledgePromptConfig(templateId?: string) {
  const data = await request.get<PromptConfigRaw>('/knowledge/prompts/current', {
    params: templateId ? { template_id: templateId } : undefined
  })
  return mapPromptConfig(data)
}

export async function saveKnowledgePromptConfig(payload: PromptConfigPayload) {
  const data = await request.put<PromptConfigRaw>('/knowledge/prompts/current', toPromptConfigRequest(payload))
  return mapPromptConfig(data)
}

export async function deleteKnowledgePromptTemplate(templateId: string) {
  return request.delete(`/knowledge/prompts/configs/${templateId}`)
}

// ==================== 辅助方法 ====================

function serializeMutationPayload(payload: Partial<KnowledgeMutationPayload>) {
  const body: Record<string, any> = {}

  if (payload.title !== undefined) body.title = payload.title
  if (payload.description !== undefined) body.description = payload.description
  if (payload.scope !== undefined) body.scope = payload.scope
  if (payload.tags !== undefined) body.tags = payload.tags
  if (payload.metadata !== undefined) body.metadata = payload.metadata

  if (payload.relationSummary) {
    body.relation_summary = {
      from_entity: payload.relationSummary.fromEntity,
      relation: payload.relationSummary.relation,
      end_entity: payload.relationSummary.endEntity
    }
  }

  return body
}

function toPromptConfigRequest(payload: PromptConfigPayload) {
  return {
    template_id: payload.templateId,
    name: payload.name,
    description: payload.description,
    entity_prompt: payload.entityPrompt,
    relation_prompt: payload.relationPrompt,
    constraints: payload.constraints,
    is_default: payload.isDefault
  }
}

function toListQuery(params: KnowledgeListQuery) {
  const query: Record<string, any> = {}
  if (params.scope) query.scope = params.scope
  if (params.keyword) query.keyword = params.keyword
  if (params.editedOnly !== undefined) query.editedOnly = params.editedOnly
  if (params.page) query.page = params.page
  if (params.pageSize) query.pageSize = params.pageSize
  if (params.sort) query.sort = params.sort
  if (params.projectId) query.projectId = params.projectId
  return query
}

// ==================== 原始类型 & 映射 ====================

interface KnowledgeRelationSummaryRaw {
  from_entity?: string
  fromEntity?: string
  relation?: string
  end_entity?: string
  endEntity?: string
}

interface KnowledgeRecordRaw {
  id: string
  title: string
  description: string
  relation_summary?: KnowledgeRelationSummaryRaw
  relationSummary?: KnowledgeRelationSummaryRaw
  tags?: string[]
  scope: KnowledgeScope
  kind?: string
  edited_by_user?: boolean
  editedByUser?: boolean
  source?: string
  owner_id?: string
  ownerId?: string
  created_at?: string
  createdAt?: string
  last_modified?: string
  lastModified?: string
  shared_at?: string
  sharedAt?: string
  metadata?: Record<string, any> | null
}

interface KnowledgeListResponseRaw {
  items: KnowledgeRecordRaw[]
  total?: number
  page?: number
  page_size?: number
  pageSize?: number
}

interface TextExtractionTripletRaw {
  from_entity: string
  relation: string
  end_entity: string
  description?: string
  source?: string
  confidence?: number
}

interface LiteratureExtractionResultRaw {
  query: string
  expanded_keywords?: string[]
  pubmed_query: string
  articles?: Array<Record<string, any>>
  triplets?: TextExtractionTripletRaw[]
  summary?: string
}

interface PendingPromptRaw {
  pending_prompt_id: string
  query: string
  context: string
  entity_prompt?: Record<string, string>
  relation_prompt?: Record<string, string>
  description?: string
  created_at: string
}

interface PromptTemplateRaw {
  id?: string
  template_id?: string
  name?: string
  label?: string
  description?: string
  entity_prompt?: Record<string, string>
  relation_prompt?: Record<string, string>
  constraints?: string
  is_default?: boolean
  updated_at?: string
}

interface PromptConfigRaw extends PromptTemplateRaw {
  created_at?: string
}

function mapKnowledgeListResponse(raw: KnowledgeListResponseRaw): KnowledgeListResponse {
  return {
    items: (raw.items || []).map(mapKnowledgeRecord),
    total: raw.total ?? raw.items.length,
    page: raw.page ?? 1,
    pageSize: raw.page_size ?? raw.pageSize ?? raw.items.length
  }
}

function mapKnowledgeRecord(raw: KnowledgeRecordRaw): KnowledgeRecord {
  const relationSummary = normalizeRelationSummary(raw.relation_summary ?? raw.relationSummary)
  const metadata = raw.metadata ?? null
  const tags = raw.tags ?? (metadata && Array.isArray(metadata.tags) ? metadata.tags : [])

  return {
    id: raw.id,
    title: raw.title,
    description: raw.description,
    relationSummary,
    tags,
    scope: raw.scope,
    editedByUser: raw.edited_by_user ?? raw.editedByUser ?? false,
    source: raw.source,
    ownerId: raw.owner_id ?? raw.ownerId,
    createdAt: raw.created_at ?? raw.createdAt,
    lastModified: raw.last_modified ?? raw.lastModified,
    sharedAt: raw.shared_at ?? raw.sharedAt,
    metadata
  }
}

function normalizeRelationSummary(raw?: KnowledgeRelationSummaryRaw): KnowledgeRelationSummary | undefined {
  if (!raw) return undefined
  const fromEntity = raw.from_entity ?? raw.fromEntity
  const relation = raw.relation
  const endEntity = raw.end_entity ?? raw.endEntity
  if (!fromEntity || !relation || !endEntity) {
    return undefined
  }
  return {
    fromEntity: fromEntity.trim(),
    relation: relation.trim(),
    endEntity: endEntity.trim()
  }
}

function mapTriplet(raw: TextExtractionTripletRaw): TextExtractionTriplet {
  return {
    fromEntity: raw.from_entity,
    relation: raw.relation,
    endEntity: raw.end_entity,
    description: raw.description || '',
    source: raw.source,
    confidence: typeof raw.confidence === 'number' ? raw.confidence : 0.85
  }
}

function mapLiteratureResult(raw: LiteratureExtractionResultRaw): LiteratureExtractionResult {
  return {
    query: raw.query,
    expandedKeywords: raw.expanded_keywords || [],
    pubmedQuery: raw.pubmed_query,
    articles: raw.articles || [],
    triplets: (raw.triplets || []).map(mapTriplet),
    summary: raw.summary
  }
}

function mapPendingPrompt(raw: PendingPromptRaw): PendingPrompt {
  return {
    pendingPromptId: raw.pending_prompt_id,
    query: raw.query,
    context: raw.context,
    entityPrompt: raw.entity_prompt || {},
    relationPrompt: raw.relation_prompt || {},
    description: raw.description,
    createdAt: raw.created_at
  }
}

function mapPromptTemplate(raw: PromptTemplateRaw): PromptTemplate {
  const fallbackId = raw.template_id ?? raw.id ?? `template-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
  return {
    id: fallbackId,
    label: raw.label || raw.name || raw.template_id || 'template',
    name: raw.name,
    description: raw.description,
    entityPrompt: raw.entity_prompt || {},
    relationPrompt: raw.relation_prompt || {},
    constraints: raw.constraints,
    isDefault: raw.is_default,
    updatedAt: raw.updated_at
  }
}

function mapPromptConfig(raw: PromptConfigRaw): PromptConfigPayload {
  return {
    templateId: raw.template_id ?? raw.id,
    name: raw.name,
    description: raw.description,
    entityPrompt: raw.entity_prompt || {},
    relationPrompt: raw.relation_prompt || {},
    constraints: raw.constraints,
    isDefault: raw.is_default,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at
  }
}
