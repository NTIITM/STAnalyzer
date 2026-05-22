<template>
  <div class="knowledge-search-page">
    <el-card class="toolbar-card" shadow="never">
      <div class="toolbar-content">
        <div class="toolbar-left">
          <div class="field">
            <span class="field-label">{{ $t('knowledgeSearch.project') }}</span>
            <el-select
              v-model="selectedProjectId"
              :placeholder="$t('knowledgeSearch.selectProject')"
              filterable
              clearable
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
          <el-button
            :loading="documentsLoading"
            @click="loadDocuments"
          >
            {{ $t('common.refresh') }}
          </el-button>
          <el-button
            v-if="selectedProjectId"
            type="primary"
            @click="handleCreateSearch"
          >
            {{ $t('knowledgeSearch.createSearch') }}
          </el-button>
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

    <el-card class="content-card" shadow="never">
      <template #header>
        <div class="card-header">
          <span>{{ $t('knowledgeSearch.title') }}</span>
        </div>
      </template>

      <div v-if="documentsLoading" class="panel-body">
        <el-skeleton animated :rows="6" />
      </div>
      <div v-else-if="documentsError" class="panel-body">
        <el-alert
          type="error"
          :closable="false"
          :title="documentsError"
          show-icon
        />
        <div class="mt-12">
          <el-button @click="loadDocuments">{{ $t('common.retry') }}</el-button>
        </div>
      </div>
      <div v-else-if="!selectedProjectId" class="panel-body">
        <el-empty :description="$t('knowledgeSearch.selectProjectFirst')" />
      </div>
      <div v-else-if="!groupedDocuments.length" class="panel-body">
        <el-empty :description="$t('knowledgeSearch.noDocuments')" />
      </div>
      <div v-else class="documents-list">
        <el-collapse v-model="activeNames" accordion>
          <el-collapse-item
            v-for="(group, groupIndex) in groupedDocuments"
            :key="group.query || `group-${groupIndex}`"
            :name="group.query || `group-${groupIndex}`"
          >
            <template #title>
              <div class="collapse-title">
                <span class="query-text">{{ group.query }}</span>
                <el-tag effect="plain" class="ml-8">
                  {{ group.documents.length }} {{ $t('knowledgeSearch.documents') }}
                </el-tag>
              </div>
            </template>
            <div class="documents-table-wrapper">
              <el-table
                :data="group.documents || []"
                style="width: 100%"
                :row-key="(row: any) => `${group.query || 'unknown'}-${row.title || ''}-${row.source || ''}`"
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
                    <el-tag v-if="row.source" effect="plain">{{ row.source }}</el-tag>
                    <span v-else class="text-muted">-</span>
                  </template>
                </el-table-column>
                <el-table-column :label="$t('knowledgeSearch.score')" width="100" align="right">
                  <template #default="{ row }">
                    <span v-if="row.score != null && typeof row.score === 'number'">{{ row.score.toFixed(3) }}</span>
                    <span v-else class="text-muted">-</span>
                  </template>
                </el-table-column>
                <el-table-column :label="$t('common.actions')" width="120" fixed="right" align="center">
                  <template #default="{ row }">
                    <el-button
                      type="danger"
                      :icon="Delete"
                      @click.stop="handleDeleteDocument(row)"
                    >
                      {{ $t('common.delete') }}
                    </el-button>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </el-collapse-item>
        </el-collapse>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete } from '@element-plus/icons-vue'
import { getProjectList, type Project } from '../api/project'
import {
  getDocumentDictsByProject,
  deleteDocument,
  type KnowledgeDocumentDictGrouped
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

const groupedDocuments = ref<KnowledgeDocumentDictGrouped[]>([])
const documentsLoading = ref(false)
const documentsError = ref('')
const activeNames = ref<string[]>([])

// 初始化项目ID（从 props 或 query 参数）
onMounted(() => {
  if (props.projectId) {
    selectedProjectId.value = props.projectId
  } else if (route.query.projectId) {
    selectedProjectId.value = route.query.projectId as string
  }
  loadProjects()
  if (selectedProjectId.value) {
    loadDocuments()
  }
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
    loadDocuments()
  } else {
    groupedDocuments.value = []
  }
}

/**
 * 加载文档列表
 */
async function loadDocuments() {
  if (!selectedProjectId.value) {
    return
  }

  try {
    documentsLoading.value = true
    documentsError.value = ''
    const result = await getDocumentDictsByProject(selectedProjectId.value)
    // 确保数据结构正确，过滤掉无效的 group
    groupedDocuments.value = (Array.isArray(result) ? result : [])
      .filter(group => group && group.query && Array.isArray(group.documents))
      .map(group => ({
        ...group,
        documents: group.documents.filter(doc => doc && doc.title)
      }))
    // 默认展开第一个
    if (groupedDocuments.value.length > 0 && groupedDocuments.value[0].query) {
      activeNames.value = [groupedDocuments.value[0].query]
    } else {
      activeNames.value = []
    }
  } catch (err: any) {
    console.error('加载文档列表失败:', err)
    documentsError.value = err.message || t('knowledgeSearch.errors.loadDocumentsFailed')
    groupedDocuments.value = []
    activeNames.value = []
  } finally {
    documentsLoading.value = false
  }
}

/**
 * 创建新检索
 */
function handleCreateSearch() {
  if (selectedProjectId.value) {
    router.push({
      path: '/knowledge-search/create',
      query: { projectId: selectedProjectId.value }
    })
  }
}

/**
 * 删除文档
 */
async function handleDeleteDocument(doc: any) {
  try {
    await ElMessageBox.confirm(
      t('knowledgeSearch.confirmDelete', { title: doc.title }),
      t('common.warning'),
      {
        confirmButtonText: t('common.confirm'),
        cancelButtonText: t('common.cancel'),
        type: 'warning'
      }
    )

    await deleteDocument(doc.title)
    ElMessage.success(t('knowledgeSearch.deleteSuccess'))
    await loadDocuments()
  } catch (err: any) {
    if (err !== 'cancel') {
      console.error('删除文档失败:', err)
      ElMessage.error(err.message || t('knowledgeSearch.errors.deleteFailed'))
    }
  }
}
</script>

<style scoped>
.knowledge-search-page {
  padding: 16px;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.toolbar-card {
  margin-bottom: 16px;
  flex-shrink: 0;
}

.toolbar-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.field {
  display: flex;
  align-items: center;
  gap: 8px;
}

.field-label {
  font-size: 14px;
  color: #606266;
  white-space: nowrap;
}

.content-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
}

.panel-body {
  padding: 24px;
  text-align: center;
}

.documents-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.collapse-title {
  display: flex;
  align-items: center;
  width: 100%;
}

.query-text {
  flex: 1;
  font-weight: 500;
  color: #303133;
}

.documents-table-wrapper {
  width: 100%;
  padding: 8px 0;
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

.mt-8 {
  margin-top: 8px;
}

.mt-12 {
  margin-top: 12px;
}

.ml-8 {
  margin-left: 8px;
}
</style>

