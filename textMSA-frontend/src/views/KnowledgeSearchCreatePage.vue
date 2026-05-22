<template>
  <div class="knowledge-search-create-page">
    <el-card class="toolbar-card" shadow="never">
      <div class="toolbar-content">
        <div class="toolbar-left">
          <el-button size="small" :icon="ArrowLeft" @click="handleBack">
            {{ $t('knowledgeSearch.common.back') }}
          </el-button>
          <div class="field">
            <span class="field-label">{{ $t('knowledgeSearch.project') }}</span>
            <el-select
              v-model="selectedProjectId"
              :placeholder="$t('knowledgeSearch.selectProject')"
              filterable
              size="small"
              style="width: 240px"
              :loading="projectLoading"
              @change="handleProjectChange"
            >
              <el-option
                v-for="project in projects"
                :key="project.project_id"
                :label="project.name"
                :value="project.project_id"
              />
            </el-select>
          </div>
        </div>
      </div>
      <el-alert
        v-if="projectError"
        :closable="false"
        type="error"
        :title="projectError"
        show-icon
        class="mt-8"
      />
    </el-card>

    <el-row :gutter="16">
      <el-col :span="24">
        <el-card class="form-card" shadow="never">
          <template #header>
            <div class="card-header">
              <span>{{ $t('knowledgeSearch.createSearch') }}</span>
            </div>
          </template>

          <el-form
            ref="formRef"
            :model="form"
            :rules="rules"
            label-width="100px"
            label-position="left"
          >
            <el-form-item
              :label="$t('knowledgeSearch.query')"
              prop="query"
            >
              <el-input
                v-model="form.query"
                :placeholder="$t('knowledgeSearch.queryPlaceholder')"
                maxlength="500"
                show-word-limit
                style="width: 400px"
              />
            </el-form-item>

            <el-form-item
              :label="$t('knowledgeSearch.topK')"
              prop="topK"
            >
              <el-input-number
                v-model="form.topK"
                :min="1"
                :max="100"
                :placeholder="$t('knowledgeSearch.topKPlaceholder')"
                style="width: 200px"
              />
              <span class="form-hint">{{ $t('knowledgeSearch.topKHint') }}</span>
            </el-form-item>

            <el-form-item
              :label="$t('knowledgeSearch.sources')"
              prop="sources"
            >
              <el-checkbox-group v-model="form.sources">
                <el-checkbox label="pubmed">PubMed</el-checkbox>
                <el-checkbox label="arxiv">ArXiv</el-checkbox>
                <el-checkbox label="crossref">CrossRef</el-checkbox>
              </el-checkbox-group>
              <span class="form-hint">{{ $t('knowledgeSearch.sourcesHint') }}</span>
            </el-form-item>

            <el-form-item
              :label="$t('knowledgeSearch.rewrite')"
              prop="rewrite"
            >
              <el-switch v-model="form.rewrite" />
              <span class="form-hint">{{ $t('knowledgeSearch.rewriteHint') }}</span>
            </el-form-item>

            <el-form-item
              :label="$t('knowledgeSearch.trace')"
              prop="trace"
            >
              <el-switch v-model="form.trace" />
              <span class="form-hint">{{ $t('knowledgeSearch.traceHint') }}</span>
            </el-form-item>

            <el-form-item>
              <el-button
                type="primary"
                :loading="searching"
                :disabled="!canSearch"
                @click="handleSearch"
              >
                {{ $t('knowledgeSearch.startSearch') }}
              </el-button>
              <el-button @click="handleReset">{{ $t('knowledgeSearch.common.reset') }}</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
    </el-row>

    <!-- 检索结果 -->
    <el-card
      v-if="searchResult"
      class="result-card"
      shadow="never"
    >
      <template #header>
        <div class="card-header">
          <span>{{ $t('knowledgeSearch.searchResults') }}</span>
        </div>
      </template>

      <div v-if="searchResult" class="result-summary">
        <el-descriptions :column="2" border>
          <el-descriptions-item :label="$t('knowledgeSearch.rewriteQuery')">
            {{ searchResult.rewrite_query || '-' }}
          </el-descriptions-item>
          <el-descriptions-item :label="$t('knowledgeSearch.datasourcesUsed')">
            <template v-if="searchResult.datasources_used && searchResult.datasources_used.length > 0">
              <el-tag
                v-for="source in searchResult.datasources_used"
                :key="source"
                size="small"
                effect="plain"
                class="mr-4"
              >
                {{ source }}
              </el-tag>
            </template>
            <span v-else>-</span>
          </el-descriptions-item>
          <el-descriptions-item :label="$t('knowledgeSearch.totalDocuments')">
            {{ searchResult.documents?.length || 0 }}
          </el-descriptions-item>
        </el-descriptions>
      </div>

      <div v-if="searchResult && (!searchResult.documents || searchResult.documents.length === 0)" class="empty-result">
        <el-empty :description="$t('knowledgeSearch.noResults')" />
      </div>
      <div v-else-if="searchResult?.documents && searchResult.documents.length > 0" class="documents-table-wrapper">
        <el-table
          :data="searchResult.documents"
          style="width: 100%"
          :row-key="(_row: KnowledgeDocument, index: number) => index"
        >
          <el-table-column type="expand">
            <template #default="{ row }">
              <div class="expanded-content">
                <div v-if="row.snippet" class="snippet-section">
                  <div class="snippet-label">{{ $t('knowledgeSearch.snippet') }}:</div>
                  <div class="snippet-text">{{ row.snippet }}</div>
                </div>
                <div v-else class="snippet-section">
                  <div class="snippet-text no-snippet">{{ $t('knowledgeSearch.noSnippet') }}</div>
                </div>
              </div>
            </template>
          </el-table-column>
          <el-table-column :label="$t('knowledgeSearch.title')" min-width="300">
            <template #default="{ row }">
              <div class="title-cell">
                <a
                  v-if="row.url"
                  :href="row.url"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="title-link"
                  @click.stop
                >
                  {{ row.title }}
                </a>
                <span v-else class="title-text">{{ row.title }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column :label="$t('knowledgeSearch.authors')" min-width="200">
            <template #default="{ row }">
              <span v-if="row.authors && row.authors.length">{{ row.authors.join(', ') }}</span>
              <span v-else class="text-muted">-</span>
            </template>
          </el-table-column>
          <el-table-column :label="$t('knowledgeSearch.journal')" min-width="150">
            <template #default="{ row }">
              <span v-if="row.journal" class="journal-text">{{ row.journal }}</span>
              <span v-else class="text-muted">-</span>
            </template>
          </el-table-column>
          <el-table-column :label="$t('knowledgeSearch.publisher')" min-width="150">
            <template #default="{ row }">
              <span v-if="row.publisher">{{ row.publisher }}</span>
              <span v-else class="text-muted">-</span>
            </template>
          </el-table-column>
          <el-table-column :label="$t('knowledgeSearch.publishedAt')" width="120">
            <template #default="{ row }">
              <span v-if="row.published_at">{{ row.published_at }}</span>
              <span v-else class="text-muted">-</span>
            </template>
          </el-table-column>
          <el-table-column :label="$t('knowledgeSearch.source')" width="100">
            <template #default="{ row }">
              <el-tag v-if="row.source" size="small" effect="plain">{{ row.source }}</el-tag>
              <span v-else class="text-muted">-</span>
            </template>
          </el-table-column>
          <el-table-column :label="$t('knowledgeSearch.score')" width="100" align="right">
            <template #default="{ row }">
              <span v-if="row.score !== undefined">{{ row.score.toFixed(3) }}</span>
              <span v-else class="text-muted">-</span>
            </template>
          </el-table-column>
          <el-table-column :label="$t('common.actions')" width="200" fixed="right" align="center">
            <template #default="{ row, $index }">
              <div class="action-buttons">
                <el-button
                  type="primary"
                  size="small"
                  :loading="savingStates[row.title]"
                  :disabled="savedStates[row.title]"
                  @click.stop="handleSaveDocument(row)"
                >
                  {{ savedStates[row.title] ? $t('knowledgeSearch.saved') : $t('knowledgeSearch.saveDocument') }}
                </el-button>
                <el-button
                  type="danger"
                  size="small"
                  @click.stop="handleDeleteDocument($index)"
                >
                  {{ $t('common.delete') }}
                </el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElForm } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'
import { getProjectList, type Project } from '../api/project'
import {
  searchKnowledge,
  saveDocument,
  type KnowledgeSearchRequest,
  type KnowledgeSearchResponseData,
  type KnowledgeDocument
} from '../api/knowledgeSearch'

interface Props {
  projectId?: string
}

const props = defineProps<Props>()

const router = useRouter()
const route = useRoute()
const { t } = useI18n()

// 状态
const projects = ref<Project[]>([])
const projectLoading = ref(false)
const projectError = ref('')
const selectedProjectId = ref<string | null>(null)

const formRef = ref<InstanceType<typeof ElForm> | null>(null)
const form = ref<KnowledgeSearchRequest>({
  query: '',
  projectId: '',
  topK: 20,
  rewrite: true,
  sources: ['pubmed', 'arxiv', 'crossref'],
  trace: false
})

const rules = {
  query: [
    { required: true, message: t('knowledgeSearch.queryRequired'), trigger: 'blur' },
    { min: 1, message: t('knowledgeSearch.queryMinLength'), trigger: 'blur' }
  ],
  projectId: [
    { required: true, message: t('knowledgeSearch.projectRequired'), trigger: 'change' }
  ]
}

const searching = ref(false)
const searchResult = ref<KnowledgeSearchResponseData | null>(null)
const savingStates = ref<Record<string, boolean>>({})
const savedStates = ref<Record<string, boolean>>({})

const canSearch = computed(() => {
  return !!form.value.query.trim() && !!form.value.projectId && !searching.value
})

// 初始化项目ID（从 props 或 query 参数）
onMounted(() => {
  if (props.projectId) {
    selectedProjectId.value = props.projectId
    form.value.projectId = props.projectId
  } else if (route.query.projectId) {
    selectedProjectId.value = route.query.projectId as string
    form.value.projectId = route.query.projectId as string
  }
  loadProjects()
})

/**
 * 加载项目列表
 */
async function loadProjects() {
  try {
    projectLoading.value = true
    projectError.value = ''
    const result = await getProjectList()
    projects.value = Array.isArray(result) ? result : []
  } catch (err: any) {
    console.error('加载项目列表失败:', err)
    projectError.value = err.message || t('knowledgeSearch.errors.loadProjectsFailed')
  } finally {
    projectLoading.value = false
  }
}

/**
 * 项目选择变化
 */
function handleProjectChange() {
  if (selectedProjectId.value) {
    form.value.projectId = selectedProjectId.value
  } else {
    form.value.projectId = ''
  }
}

/**
 * 执行检索
 */
async function handleSearch() {
  if (!formRef.value) return

  try {
    await formRef.value.validate()
  } catch {
    return
  }

  try {
    searching.value = true
    searchResult.value = null
    savedStates.value = {}
    savingStates.value = {}

    const result = await searchKnowledge({
      query: form.value.query,
      projectId: form.value.projectId!,
      topK: form.value.topK,
      rewrite: form.value.rewrite,
      sources: form.value.sources && form.value.sources.length > 0 ? form.value.sources : undefined,
      trace: form.value.trace
    })

    searchResult.value = result
    ElMessage.success(t('knowledgeSearch.searchSuccess'))
  } catch (err: any) {
    console.error('检索失败:', err)
    ElMessage.error(err.message || t('knowledgeSearch.errors.searchFailed'))
  } finally {
    searching.value = false
  }
}

/**
 * 重置表单
 */
function handleReset() {
  form.value = {
    query: '',
    projectId: selectedProjectId.value || '',
    topK: 20,
    rewrite: true,
    sources: ['pubmed', 'arxiv', 'crossref'],
    trace: false
  }
  searchResult.value = null
  savedStates.value = {}
  savingStates.value = {}
  formRef.value?.clearValidate()
}

/**
 * 删除文档（仅前端删除）
 */
function handleDeleteDocument(index: number) {
  if (!searchResult.value || !searchResult.value.documents) return
  
  const doc = searchResult.value.documents[index]
  if (!doc) return

  // 从数组中删除
  searchResult.value.documents.splice(index, 1)
  
  // 清除相关的保存状态
  delete savingStates.value[doc.title]
  delete savedStates.value[doc.title]
  
  ElMessage.success(t('knowledgeSearch.deleteSuccess'))
}

/**
 * 保存文档
 */
async function handleSaveDocument(doc: KnowledgeDocument) {
  if (!form.value.projectId || !form.value.query) {
    ElMessage.warning(t('knowledgeSearch.projectRequired'))
    return
  }

  try {
    savingStates.value[doc.title] = true

    await saveDocument({
      title: doc.title,
      query: form.value.query,
      project_id: form.value.projectId,
      source: doc.source,
      snippet: doc.snippet,
      url: doc.url,
      doi: doc.doi,
      published_at: doc.published_at,
      authors: doc.authors,
      journal: doc.journal,
      publisher: doc.publisher,
      source_type: doc.source_type,
      score: doc.score,
      metadata: doc.metadata
    })

    savedStates.value[doc.title] = true
    ElMessage.success(t('knowledgeSearch.saveSuccess'))
  } catch (err: any) {
    console.error('保存文档失败:', err)
    ElMessage.error(err.message || t('knowledgeSearch.errors.saveFailed'))
  } finally {
    savingStates.value[doc.title] = false
  }
}

/**
 * 返回
 */
function handleBack() {
  router.push({
    path: '/knowledge-search',
    query: selectedProjectId.value ? { projectId: selectedProjectId.value } : {}
  })
}
</script>

<style scoped>
.knowledge-search-create-page {
  padding: 12px;
  min-height: 100%;
  display: flex;
  flex-direction: column;
  overflow-x: hidden;
  overflow-y: visible;
}

.toolbar-card {
  margin-bottom: 12px;
  flex-shrink: 0;
}

.toolbar-card :deep(.el-card__body) {
  padding: 12px 16px;
}

.toolbar-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.field {
  display: flex;
  align-items: center;
  gap: 6px;
}

.field-label {
  font-size: 13px;
  color: #606266;
  white-space: nowrap;
}

.form-card {
  margin-bottom: 12px;
}

.form-card :deep(.el-card__header) {
  padding: 12px 16px;
  border-bottom: 1px solid #ebeef5;
}

.form-card :deep(.el-card__body) {
  padding: 16px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
  font-size: 15px;
}

:deep(.el-form-item) {
  margin-bottom: 16px;
}

:deep(.el-form-item__label) {
  font-size: 13px;
  padding-bottom: 6px;
}

.form-hint {
  margin-left: 10px;
  font-size: 12px;
  color: #909399;
}

.result-card {
  margin-top: 12px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
}

.result-card :deep(.el-card__header) {
  padding: 12px 16px;
  border-bottom: 1px solid #ebeef5;
}

.result-card :deep(.el-card__body) {
  padding: 16px;
  display: flex;
  flex-direction: column;
}

.result-summary {
  margin-bottom: 16px;
}

.result-summary :deep(.el-descriptions) {
  font-size: 13px;
}

.result-summary :deep(.el-descriptions__label) {
  font-size: 13px;
  font-weight: 500;
}

.result-summary :deep(.el-descriptions__content) {
  font-size: 13px;
}

.mr-4 {
  margin-right: 4px;
}

.empty-result {
  padding: 30px;
  text-align: center;
}

.documents-table-wrapper {
  width: 100%;
  flex: 1;
  overflow: auto;
  min-height: 0;
}

.title-cell {
  display: flex;
  align-items: center;
}

.title-link {
  color: #409eff;
  text-decoration: none;
  word-break: break-word;
}

.title-link:hover {
  text-decoration: underline;
}

.title-text {
  word-break: break-word;
  color: #606266;
}

.journal-text {
  font-style: italic;
  color: #606266;
}

.text-muted {
  color: #909399;
}

.expanded-content {
  padding: 16px;
  background-color: #f5f7fa;
}

.snippet-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.snippet-label {
  font-weight: 600;
  font-size: 14px;
  color: #606266;
}

.snippet-text {
  font-size: 14px;
  line-height: 1.6;
  color: #606266;
  white-space: pre-wrap;
  word-break: break-word;
}

.snippet-text.no-snippet {
  color: #909399;
  font-style: italic;
}

.action-buttons {
  display: flex;
  gap: 8px;
  justify-content: center;
  align-items: center;
}

.mt-8 {
  margin-top: 8px;
}
</style>

