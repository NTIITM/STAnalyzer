<template>
  <div class="data-analysis-page">
    <el-card class="toolbar-card" shadow="never">
      <div class="toolbar-content">
        <div class="toolbar-left">
          <div class="field">
            <span class="field-label">{{ t('dataAnalysis.toolbar.projectLabel') }}</span>
            <el-select
              v-model="activeProjectId"
              :placeholder="t('dataAnalysis.toolbar.projectPlaceholder')"
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
            :loading="filesLoading"
            @click="loadFiles"
          >
            {{ t('dataAnalysis.toolbar.refreshFiles') }}
          </el-button>
        </div>
        <div class="toolbar-right">
          <el-button
            type="primary"
            plain
            :loading="projectLoading"
            @click="loadProjects"
          >
            {{ t('dataAnalysis.toolbar.refreshProjects') }}
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

    <el-row :gutter="12" class="content-row">
      <el-col :span="6">
        <el-card class="panel-card" shadow="never">
          <template #header>
            <el-tabs v-model="activeView" class="view-tabs" @tab-change="handleViewChange">
              <el-tab-pane :label="t('dataAnalysis.tabs.fileList')" name="file">
                <template #label>
                  <span>{{ t('dataAnalysis.tabs.fileList') }}</span>
                  <el-tag v-if="files.length" effect="plain" class="ml-4">{{ files.length }}</el-tag>
                </template>
              </el-tab-pane>
              <el-tab-pane :label="t('dataAnalysis.tabs.executionList')" name="execution">
                <template #label>
                  <span>{{ t('dataAnalysis.tabs.executionList') }}</span>
                  <el-tag v-if="completedExecutions.length" effect="plain" class="ml-4">{{ completedExecutions.length }}</el-tag>
                </template>
              </el-tab-pane>
            </el-tabs>
          </template>

          <!-- 文件列表 -->
          <div v-if="activeView === 'file'">
            <div v-if="filesLoading" class="panel-body">
              <el-skeleton animated :rows="6" />
            </div>
            <div v-else-if="filesError" class="panel-body">
              <el-alert
                type="error"
                :closable="false"
                :title="filesError"
                show-icon
              />
              <div class="mt-12">
                <el-button @click="loadFiles">{{ t('common.retry') }}</el-button>
              </div>
            </div>
            <div v-else-if="!files.length" class="panel-body">
              <el-empty :description="t('dataAnalysis.lists.fileEmpty')" />
            </div>
            <div v-else class="file-list">
              <el-scrollbar height="calc(100vh - 260px)">
                <el-menu
                  class="file-menu"
                  :default-active="activeFileId || ''"
                  @select="handleSelectFile"
                >
                  <el-menu-item
                    v-for="item in files"
                    :key="item.id"
                    :index="item.id"
                  >
                    <div class="file-item" :title="item.name">
                      <span class="file-name">{{ item.name }}</span>
                    </div>
                  </el-menu-item>
                </el-menu>
              </el-scrollbar>
            </div>
          </div>

          <!-- 执行列表 -->
          <div v-else-if="activeView === 'execution'">
            <div v-if="executionsLoading" class="panel-body">
              <el-skeleton animated :rows="6" />
            </div>
            <div v-else-if="executionsError" class="panel-body">
              <el-alert
                type="error"
                :closable="false"
                :title="executionsError"
                show-icon
              />
              <div class="mt-12">
                <el-button @click="loadExecutions">{{ t('common.retry') }}</el-button>
              </div>
            </div>
            <div v-else-if="!completedExecutions.length" class="panel-body">
              <el-empty :description="t('dataAnalysis.lists.executionEmpty')" />
            </div>
            <div v-else class="execution-list">
              <el-scrollbar>
                <el-menu
                  class="execution-menu"
                  :default-active="activeExecutionId || ''"
                  @select="handleSelectExecution"
                >
                  <el-menu-item
                    v-for="exec in completedExecutions"
                    :key="exec.execution_id"
                    :index="exec.execution_id"
                  >
                    <div class="execution-item" :title="exec.execution_id">
                      <span class="execution-id">{{ exec.execution_id }}</span>
                    </div>
                  </el-menu-item>
                </el-menu>
              </el-scrollbar>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="9">
        <el-card class="panel-card" shadow="never">
          <template #header>
            <div class="card-header">
              <span>{{ activeView === 'file' ? t('dataAnalysis.preview.fileTitle') : t('dataAnalysis.preview.executionTitle') }}</span>
              <span class="subtext" v-if="activeView === 'file' && activeFile?.name">{{ activeFile?.name }}</span>
              <span class="subtext" v-else-if="activeView === 'execution' && activeExecution?.execution_id">
                ID: {{ activeExecution.execution_id }}
              </span>
              <!-- h5ad 文件视图切换 (因服务器负荷问题暂时注释掉) -->
              <!--
              <el-radio-group 
                v-if="activeView === 'file' && isCurrentFileH5ad" 
                v-model="previewMode" 
                class="preview-mode-switch"
              >
              <el-radio-button label="text">{{ t('dataAnalysis.preview.textMode') }}</el-radio-button>
              <el-radio-button label="visualization">{{ t('dataAnalysis.preview.visualizationMode') }}</el-radio-button>
              </el-radio-group>
              -->
            </div>
          </template>

          <div class="panel-body preview-body">
            <!-- 文件预览 -->
            <template v-if="activeView === 'file'">
              <el-empty v-if="!activeFile" :description="t('dataAnalysis.preview.selectFile')" />
              <div v-else class="preview-wrapper">
                <!-- h5ad 文件可视化模式 (因服务器负荷问题暂时注释掉) -->
                <!--
                <SpatialVisualization
                  v-if="isCurrentFileH5ad && previewMode === 'visualization'"
                  :key="`spatial-${activeFile.id}`"
                  :file-id="activeFile.id"
                />
                -->
                <!-- 其他文件类型或文本预览模式 -->
                <component
                  v-if="previewComponent"
                  :is="previewComponent"
                  :key="activeFile.id"
                  :file-id="activeFile.id"
                  :file-name="activeFile.name"
                />
                <div v-else class="fallback-preview">
                  <el-alert
                    :title="t('dataAnalysis.preview.unsupported')"
                    type="info"
                    :closable="false"
                    show-icon
                  />
                </div>
              </div>
            </template>
            <!-- 执行预览 -->
            <template v-else-if="activeView === 'execution'">
              <el-empty v-if="!activeExecution" :description="t('dataAnalysis.preview.selectExecution')" />
              <ExecutionPreview v-else :execution="activeExecution" :files="files" />
            </template>
          </div>
        </el-card>
      </el-col>

      <el-col :span="9">
        <el-card class="panel-card" shadow="never">
          <template #header>
            <div class="card-header">
              <span>{{ activeView === 'file' ? t('dataAnalysis.analysis.fileTitle') : t('dataAnalysis.analysis.executionTitle') }}</span>
              <span class="subtext" v-if="activeView === 'file' && activeFile?.id">ID: {{ activeFile?.id }}</span>
              <span class="subtext" v-else-if="activeView === 'execution' && activeExecution?.execution_id">
                ID: {{ activeExecution.execution_id }}
              </span>
            </div>
          </template>

          <div class="panel-body analysis-body">
            <!-- 文件分析 -->
            <template v-if="activeView === 'file'">
              <el-alert
                v-if="!activeFile"
                :title="t('dataAnalysis.analysis.selectFileTip')"
                type="info"
                :closable="false"
                show-icon
                class="mb-12"
              />

              <el-form label-position="top" class="analysis-form">
                <el-form-item :label="t('dataAnalysis.analysis.questionLabel')" required>
                  <el-input
                    v-model="query"
                    type="textarea"
                    :rows="4"
                    maxlength="500"
                    show-word-limit
                    :placeholder="t('dataAnalysis.analysis.questionPlaceholder')"
                    :disabled="analysisLoading || !activeFile"
                  />
                </el-form-item>
                <div class="action-row">
                  <el-button
                    type="primary"
                    :loading="analysisLoading"
                    :disabled="!activeFile || !canSubmit"
                    @click="handleAnalyze"
                  >
                    {{ t('dataAnalysis.analysis.send') }}
                  </el-button>
                  <el-button
                    :disabled="!analysisResult"
                    @click="copyResult"
                  >
                    {{ t('dataAnalysis.analysis.copy') }}
                  </el-button>
                </div>
              </el-form>
            </template>
            <!-- 执行分析 -->
            <template v-else-if="activeView === 'execution'">
              <el-alert
                v-if="!activeExecution"
                :title="t('dataAnalysis.analysis.selectExecutionTip')"
                type="info"
                :closable="false"
                show-icon
                class="mb-12"
              />

              <el-form label-position="top" class="analysis-form" v-if="activeExecution">
                <el-form-item :label="t('dataAnalysis.analysis.questionLabel')" required>
                  <el-input
                    v-model="query"
                    type="textarea"
                    :rows="4"
                    maxlength="500"
                    show-word-limit
                    :placeholder="t('dataAnalysis.analysis.questionPlaceholder')"
                    :disabled="analysisLoading || !activeExecution"
                  />
                </el-form-item>
                <div class="action-row">
                  <el-button
                    type="primary"
                    :loading="analysisLoading"
                    :disabled="!activeExecution || !canSubmit"
                    @click="handleAnalyzeExecution"
                  >
                    {{ t('dataAnalysis.analysis.send') }}
                  </el-button>
                  <el-button
                    :disabled="!analysisResult"
                    @click="copyResult"
                  >
                    {{ t('dataAnalysis.analysis.copy') }}
                  </el-button>
                </div>
              </el-form>
            </template>

            <div class="result-section">
              <div class="result-header">
                <span>{{ t('dataAnalysis.analysis.resultTitle') }}</span>
                <el-tag v-if="analysisLoading" type="info">{{ t('dataAnalysis.analysis.statusLoading') }}</el-tag>
                <el-tag v-else-if="analysisError" type="danger" effect="plain">{{ t('dataAnalysis.analysis.statusError') }}</el-tag>
                <el-tag v-else-if="analysisResult" type="success" effect="plain">{{ t('dataAnalysis.analysis.statusSuccess') }}</el-tag>
              </div>
              <div class="result-box">
                <div v-if="analysisState === 'error' && (analysisError || finalError)" class="result-error">
                  <el-alert
                    type="error"
                    :title="analysisError || finalError"
                    :closable="false"
                    show-icon
                  />
                </div>

                <div v-else-if="!analysisMessages.length && !analysisLoading" class="state-card">
                  <div class="state-title">{{ t('dataAnalysis.analysis.emptyResult') }}</div>
                </div>

                <div v-else class="message-stack">
                  <div
                    class="message-list"
                    ref="messageListRef"
                    @scroll="handleMessageListScroll"
                  >
                    <div
                      v-for="message in analysisMessages"
                      :key="message.key"
                      class="message-card"
                      :data-role="message.role"
                    >
                      <div class="message-meta">
                        <span class="badge" :data-role="message.role">{{ roleLabel(message.role) }}</span>
                        <span class="timestamp">{{ message.time }}</span>
                      </div>
                      <AgentMessageContent
                        :message="message.content"
                        :extra="message.extra as any"
                      />
                    </div>

                    <div
                      v-if="analysisLoading"
                      class="message-card typing-indicator-card"
                      data-role="assistant"
                    >
                      <div class="message-meta">
                        <span class="badge" data-role="assistant">{{ t('app.agent') }}</span>
                        <span class="timestamp"></span>
                      </div>
                      <div class="typing-indicator">
                        <span class="dot" />
                        <span class="dot" />
                        <span class="dot" />
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import TextPreview from '../components/file-preview/TextPreview.vue'
import ImagePreview from '../components/file-preview/ImagePreview.vue'
import ExecutionPreview from '../components/execution/ExecutionPreview.vue'
// import SpatialVisualization from '../components/analysis/SpatialVisualization.vue'
import AgentMessageContent from '../components/agent/AgentMessageContent.vue'
import { getProjectList, type Project } from '../api/project'
import { getFileList, type FileInfo } from '../api/file'
import { type ExecutionInfo } from '../api/analysis'
import { getExecutionList } from '../api/service'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { tokenManager } from '../api/request'
import { isH5adFile, isHiddenSystemFile } from '../utils/fileType'

interface NormalizedFile {
  id: string
  name: string
  status?: string
  raw: any
}

interface ExtraFile {
  fileName: string
  description?: string
  filePath: string
}

interface ExtraParts {
  str?: string
  json?: string
  code?: string
  raw?: string
  files?: ExtraFile[]
}

interface QueuedSseEvent {
  eventType: string
  dataStr: string
  streamId: number
}

interface AnalysisMessage {
  key: string
  role: 'user' | 'assistant'
  content: string
  extra?: import('../components/agent/AgentMessageContent.vue').MessageExtra | null
  time: string
}

const MIN_EVENT_RENDER_DELAY = 1500
let lastEventDisplayedAt = 0
let processingEventQueue = false
let activeStreamId = 0
const sseEventQueue: QueuedSseEvent[] = []

const route = useRoute()
const { t } = useI18n()

type EnrichmentRecord = {
  geneSet: string
  term: string
  overlap: string
  pValue: number
  adjP: number
  oldP?: number
  oldAdjP?: number
  oddsRatio?: number
  combinedScore?: number
  genes: string[]
}

const enrichmentSampleData: EnrichmentRecord[] = [
  {
    geneSet: 'MSigDB_Hallmark',
    term: 'Interferon Gamma Response',
    overlap: '15/200',
    pValue: 1.2e-6,
    adjP: 3.5e-5,
    oldP: 2.1e-6,
    oldAdjP: 5.2e-5,
    oddsRatio: 4.2,
    combinedScore: 38.6,
    genes: ['STAT1', 'IRF1', 'CXCL10', 'GBP1', 'IFI44L', 'IFIT1', 'IFIT3', 'ISG15', 'OAS1', 'OAS2', 'OAS3', 'MX1', 'RSAD2', 'GBP4', 'CXCL9']
  },
  {
    geneSet: 'MSigDB_Hallmark',
    term: 'TNFα Signaling via NF-κB',
    overlap: '12/180',
    pValue: 2.8e-5,
    adjP: 7.3e-4,
    oldP: 3.2e-5,
    oldAdjP: 9.1e-4,
    oddsRatio: 3.7,
    combinedScore: 29.4,
    genes: ['NFKBIA', 'NFKB1', 'RELA', 'TNFAIP3', 'BCL3', 'CXCL8', 'CCL20', 'ICAM1', 'JUNB', 'ZC3H12A', 'PTGS2', 'IL6']
  },
  {
    geneSet: 'KEGG',
    term: 'Chemokine Signaling Pathway',
    overlap: '10/150',
    pValue: 7.1e-5,
    adjP: 0.0018,
    oddsRatio: 3.1,
    combinedScore: 21.7,
    genes: ['CXCL10', 'CXCL9', 'CXCL8', 'CCL20', 'CCR7', 'CCR5', 'CXCR3', 'GNAI2', 'JAK1', 'STAT1']
  },
  {
    geneSet: 'Reactome',
    term: 'Antigen Presentation: Folding/Assembly',
    overlap: '8/120',
    pValue: 1.9e-4,
    adjP: 0.0032,
    oddsRatio: 3.9,
    combinedScore: 18.5,
    genes: ['HLA-A', 'HLA-B', 'HLA-C', 'B2M', 'TAP1', 'TAP2', 'PSMB8', 'PSMB9']
  },
  {
    geneSet: 'GO_BP',
    term: 'Response to Virus',
    overlap: '14/210',
    pValue: 2.3e-6,
    adjP: 6.0e-5,
    oddsRatio: 4.5,
    combinedScore: 36.2,
    genes: ['MX1', 'OAS1', 'OAS2', 'OAS3', 'RSAD2', 'IFI44L', 'IFIT1', 'IFIT3', 'ISG15', 'DDX58', 'IFIH1', 'IRF7', 'IRF9', 'STAT1']
  },
  {
    geneSet: 'GO_BP',
    term: 'Leukocyte Migration',
    overlap: '11/190',
    pValue: 4.2e-5,
    adjP: 0.0011,
    oddsRatio: 2.9,
    combinedScore: 24.9,
    genes: ['CXCL8', 'CXCL9', 'CXCL10', 'CCL20', 'ICAM1', 'VCAM1', 'SELE', 'SELPLG', 'CCR7', 'CXCR3', 'ITGB2']
  }
]

const isEnrichmentView = computed(() => route.query.view === 'enrichment')

const projects = ref<Project[]>([])
const projectLoading = ref(false)
const projectError = ref('')
const activeProjectId = ref<string | null>(null)

const files = ref<NormalizedFile[]>([])
const filesLoading = ref(false)
const filesError = ref('')
const activeFileId = ref<string | null>(null)

const executions = ref<ExecutionInfo[]>([])
const executionsLoading = ref(false)
const executionsError = ref('')
const activeExecutionId = ref<string | null>(null)

const activeView = ref<'file' | 'execution'>('file')

const query = ref('')
const analysisLoading = ref(false)
const analysisResult = ref('')
const analysisError = ref('')
const analysisState = ref<'idle' | 'loading' | 'ready' | 'error'>('idle')
const finalMessage = ref('')
const finalExtra = ref<ExtraParts | null>(null)
const finalError = ref('')
const analysisMessages = ref<AnalysisMessage[]>([])
const messageListRef = ref<HTMLElement | null>(null)
const userLockedScroll = ref(false)
let currentStreamController: AbortController | null = null

const activeFile = computed(() => files.value.find(item => item.id === activeFileId.value) || null)

// 当前文件是否为 h5ad
const isCurrentFileH5ad = computed(() => {
  return activeFile.value ? isH5adFile(activeFile.value.name) : false
})

// 预览模式：文本预览或可视化
const previewMode = ref<'text' | 'visualization'>('text')

// 只显示状态为 completed 的执行记录
const completedExecutions = computed(() => {
  return executions.value.filter(exec => exec.status?.toLowerCase() === 'completed')
})

// 从 completedExecutions 中查找当前选中的执行记录
const activeExecution = computed(() => {
  if (!activeExecutionId.value) return null
  return completedExecutions.value.find(item => item.execution_id === activeExecutionId.value) || null
})

const canSubmit = computed(() => {
  if (activeView.value === 'file') {
    return !!query.value.trim() && !!activeFile.value && !analysisLoading.value
  }
  return !!query.value.trim() && !!activeExecution.value && !analysisLoading.value
})

const previewComponent = computed(() => {
  if (!activeFile.value) return null
  // 如果是 h5ad 文件且选择可视化模式，返回 null（由模板中的 SpatialVisualization 组件处理）
  // (可视化功能已屏蔽，以下逻辑保留但不生效，因为 previewMode 只能是 text)
  if (isCurrentFileH5ad.value && previewMode.value === 'visualization') {
    return null
  }
  const ext = getExtension(activeFile.value.name)
  if (isImageExt(ext)) return ImagePreview
  return TextPreview
})

function getExtension(name?: string): string {
  if (!name) return ''
  const parts = name.split('.')
  if (parts.length <= 1) return ''
  return parts.pop()?.toLowerCase() || ''
}

function isImageExt(ext: string): boolean {
  return ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'svg'].includes(ext)
}

function normalizeFile(record: FileInfo | Record<string, any>): NormalizedFile | null {
  const rawId = (record as any).fileId || (record as any).file_id || (record as any).id
  if (!rawId) return null
  const id = String(rawId)
  const name =
    (record as any).name ||
    (record as any).filename ||
    (record as any).file_name ||
    t('dataAnalysis.preview.fallbackFileName', { id })
  return {
    id,
    name,
    status: (record as any).status,
    raw: record
  }
}

// 执行记录相关状态
const executionTotal = ref(0)

async function loadProjects() {
  projectLoading.value = true
  projectError.value = ''
  try {
    const list = await getProjectList()
    projects.value = list
    if (!activeProjectId.value && list.length) {
      activeProjectId.value = list[0].project_id
    }
    await Promise.all([loadFiles(), loadExecutions()])
  } catch (err: any) {
    projectError.value = err?.message || t('dataAnalysis.errors.loadProjects')
  } finally {
    projectLoading.value = false
  }
}

async function loadExecutions() {
  if (!activeProjectId.value) {
    executions.value = []
    executionsLoading.value = false
    executionsError.value = ''
    executionTotal.value = 0
    return
  }
  
  executionsLoading.value = true
  executionsError.value = ''
  try {
    const { executions: items, total: totalCount } = await getExecutionList(
      undefined, // serviceId
      undefined, // userId
      undefined, // status - 不过滤状态，显示所有执行记录
      activeProjectId.value, // project
      0, // skip
      100 // limit
    )
    executions.value = (items || []) as any[]
    executionTotal.value = totalCount || 0
    
    // 如果当前选中的执行记录不在 completedExecutions 中，清空选中状态
    if (activeExecutionId.value && activeView.value === 'execution') {
      const found = completedExecutions.value.find(
        exec => exec.execution_id === activeExecutionId.value
      )
      if (!found) {
        activeExecutionId.value = null
      }
    }
  } catch (err: any) {
    console.error('加载执行记录失败:', err)
    executionsError.value = err?.message || t('dataAnalysis.errors.loadExecutions')
    executions.value = []
    executionTotal.value = 0
  } finally {
    executionsLoading.value = false
  }
}

async function loadFiles() {
  filesLoading.value = true
  filesError.value = ''
  files.value = []
  activeFileId.value = null
  try {
    const list = await getFileList(
      activeProjectId.value ? { projectId: activeProjectId.value } : undefined
    )
    const normalized = list
      .map(item => normalizeFile(item))
      .filter((item): item is NormalizedFile => !!item)
      // 过滤掉隐藏系统文件 (如 gen- 开头)
      .filter(item => !isHiddenSystemFile(item.name))
      // 去掉h5ad显示逻辑
      .filter(item => !isH5adFile(item.name))
    files.value = normalized
    if (normalized.length) {
      activeFileId.value = normalized[0].id
    }
  } catch (err: any) {
    filesError.value = err?.message || t('dataAnalysis.errors.loadFiles')
  } finally {
    filesLoading.value = false
  }
}

async function handleAnalyze() {
  if (!activeFile.value) {
    ElMessage.warning(t('dataAnalysis.analysis.selectFileWarning'))
    return
  }
  if (!query.value.trim()) {
    ElMessage.warning(t('dataAnalysis.analysis.enterQueryWarning'))
    return
  }
  
  const question = query.value.trim()
  // 添加用户消息
  addUserMessage(question)
  await nextTick()
  scrollToBottom(true)
  
  // 每次点击发送时清除旧的结果状态
  finalMessage.value = ''
  finalExtra.value = null
  
  await startFileAnalysisStream(activeFile.value.id, question)
}

async function handleAnalyzeExecution() {
  if (!activeExecution.value) {
    ElMessage.warning(t('dataAnalysis.analysis.selectExecutionWarning'))
    return
  }
  if (!query.value.trim()) {
    ElMessage.warning(t('dataAnalysis.analysis.enterQueryWarning'))
    return
  }
  
  const question = query.value.trim()
  // 添加用户消息
  addUserMessage(question)
  await nextTick()
  scrollToBottom(true)
  
  // 每次点击发送时清除旧的结果状态
  finalMessage.value = ''
  finalExtra.value = null
  
  // Use the first output file ID if available, otherwise use execution_id
  // The backend endpoint expects file_id, so we'll use output_file_ids[0] if it exists
  await startExecutionAnalysisStream(query.value.trim(), activeExecution.value.execution_id)
}

function handleProjectChange() {
  Promise.all([loadFiles(), loadExecutions()])
}

function handleViewChange() {
  stopCurrentStream()
  // 切换视图时清空分析结果
  analysisResult.value = ''
  analysisError.value = ''
  finalMessage.value = ''
  finalExtra.value = null
  finalError.value = ''
  analysisState.value = 'idle'
  sseEventQueue.length = 0
  lastEventDisplayedAt = 0
  query.value = ''
  
  // 根据新视图自动选中第一个项目
  if (activeView.value === 'file') {
    activeExecutionId.value = null
    if (files.value.length && !activeFileId.value) {
      activeFileId.value = files.value[0].id
    }
  } else if (activeView.value === 'execution') {
    activeFileId.value = null
    if (completedExecutions.value.length && !activeExecutionId.value) {
      activeExecutionId.value = completedExecutions.value[0].execution_id
    }
  }
}

function handleSelectFile(fileId: string) {
  stopCurrentStream()
  activeFileId.value = fileId
  activeExecutionId.value = null
  analysisResult.value = ''
  analysisError.value = ''
  finalMessage.value = ''
  finalExtra.value = null
  finalError.value = ''
  analysisState.value = 'idle'
  sseEventQueue.length = 0
  lastEventDisplayedAt = 0
  // 如果切换到 h5ad 文件，自动切换到可视化模式
  const selectedFile = files.value.find(item => item.id === fileId)
  if (selectedFile && isH5adFile(selectedFile.name)) {
    previewMode.value = 'visualization'
  } else {
    previewMode.value = 'text'
  }
}

function handleSelectExecution(executionId: string) {
  stopCurrentStream()
  activeExecutionId.value = executionId
  activeFileId.value = null
  analysisResult.value = ''
  analysisError.value = ''
  finalMessage.value = ''
  finalExtra.value = null
  finalError.value = ''
  analysisState.value = 'idle'
  sseEventQueue.length = 0
  lastEventDisplayedAt = 0
}


async function copyResult() {
  if (!analysisResult.value) return
  try {
    await navigator.clipboard.writeText(analysisResult.value)
    ElMessage.success(t('dataAnalysis.analysis.copySuccess'))
  } catch (err) {
    console.error(err)
    ElMessage.error(t('dataAnalysis.analysis.copyFailed'))
  }
}

onMounted(async () => {
  await loadProjects()
})

onUnmounted(() => {
  stopCurrentStream()
})

function stopCurrentStream() {
  if (currentStreamController) {
    currentStreamController.abort()
    currentStreamController = null
  }
  activeStreamId += 1
  sseEventQueue.length = 0
  lastEventDisplayedAt = 0
  processingEventQueue = false
}

function delay(ms: number) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

function formatExtra(extra: unknown): string {
  if (extra === null || extra === undefined) return ''
  if (typeof extra === 'string') return extra
  try {
    return JSON.stringify(extra, null, 2)
  } catch {
    return String(extra)
  }
}

function renderMessage(text: string) {
  if (!text) return ''
  const html = marked.parse(text, { async: false }) as string
  return DOMPurify.sanitize(html)
}

function parseExtraParts(extra: unknown): ExtraParts {
  if (extra === null || extra === undefined) return {}
  if (typeof extra === 'object') {
    const obj = extra as Record<string, unknown>
    if (Object.keys(obj).length === 0) return {}
    const parts: ExtraParts = {}
    if (Array.isArray(obj.files)) {
      const files: ExtraFile[] = []
      obj.files.forEach(item => {
        const fileObj = item as Record<string, unknown>
        const filePath = typeof fileObj.file_path === 'string' ? fileObj.file_path : ''
        if (!filePath) return
        const fileName =
          typeof fileObj.file_name === 'string'
            ? fileObj.file_name
            : filePath.split('/').pop() || filePath
        const description =
          typeof fileObj.description === 'string' ? fileObj.description : undefined
        files.push({
          fileName,
          description,
          filePath
        })
      })
      if (files.length) parts.files = files
    }
    if (typeof obj.str === 'string') parts.str = obj.str
    if (obj.json !== undefined) parts.json = formatExtra(obj.json)
    if (typeof obj.code === 'string') parts.code = obj.code
    if (!parts.str && !parts.json && !parts.code && !parts.files) {
      parts.raw = formatExtra(extra)
    }
    return parts
  }
  return { str: String(extra) }
}

function formatTime(date: Date = new Date()): string {
  return `${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`
}

function addUserMessage(content: string) {
  const now = new Date()
  analysisMessages.value.push({
    key: `user-${Date.now()}-${Math.random()}`,
    role: 'user',
    content: content.trim(),
    extra: null,
    time: formatTime(now)
  })
}

function convertExtraPartsToMessageExtra(extra: ExtraParts | null): import('../components/agent/AgentMessageContent.vue').MessageExtra | null {
  if (!extra) return null
  
  const result: any = {}
  
  // 转换 str 为 txt
  if (extra.str) {
    result.txt = extra.str
  }
  
  // 转换 json 字符串为对象
  if (extra.json) {
    try {
      result.json = typeof extra.json === 'string' ? JSON.parse(extra.json) : extra.json
    } catch {
      result.json = extra.json
    }
  }
  
  // 转换 code
  if (extra.code) {
    result.code = extra.code
  }
  
  // 转换 files
  if (extra.files && Array.isArray(extra.files)) {
    result.files = extra.files.map(file => ({
      file_id: file.filePath || '',
      name: file.fileName,
      filename: file.fileName,
      description: file.description
    }))
  }
  
  return Object.keys(result).length > 0 ? result : null
}

function addAssistantMessage(content: string, extra?: unknown) {
  const parsedExtra = extra !== undefined ? parseExtraParts(extra) : null
  const convertedExtra = convertExtraPartsToMessageExtra(parsedExtra)
  const now = new Date()
  analysisMessages.value.push({
    key: `assistant-${Date.now()}-${Math.random()}`,
    role: 'assistant',
    content: content || '',
    extra: convertedExtra,
    time: formatTime(now)
  })
  return parsedExtra
}

function setFinalOutput(message: string, extra?: unknown) {
  const parsedExtra = extra !== undefined ? parseExtraParts(extra) : null
  finalMessage.value = message || ''
  finalExtra.value = parsedExtra
  analysisResult.value = finalMessage.value
  
  // 在 loading 状态时，将消息添加到数组中
  if (analysisState.value === 'loading') {
    addAssistantMessage(message || '', extra)
  }
}

async function downloadFileAttachment(file?: ExtraFile) {
  if (!file || !file.filePath) return
  try {
    const headers: Record<string, string> = {}
    const token = tokenManager.getToken()
    if (token) {
      headers.Authorization = `Bearer ${token}`
      headers.token = token
    }
    const response = await fetch(file.filePath, { headers })
    if (!response.ok) {
      throw new Error(t('dataAnalysis.events.downloadFailed'))
    }
    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = file.fileName || file.filePath.split('/').pop() || 'download'
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  } catch (err) {
    console.error(err)
    ElMessage.error(t('dataAnalysis.events.downloadFailed'))
  }
}

async function processEventQueue() {
  if (processingEventQueue) return
  processingEventQueue = true
  while (sseEventQueue.length) {
    const { eventType, dataStr, streamId } = sseEventQueue.shift()!
    if (streamId !== activeStreamId) {
      continue
    }
    const now = Date.now()
    const timeSinceLast = now - lastEventDisplayedAt
    const waitMs = lastEventDisplayedAt ? Math.max(MIN_EVENT_RENDER_DELAY - timeSinceLast, 0) : 0
    if (waitMs > 0) {
      await delay(waitMs)
    }
    processSseEvent(eventType, dataStr)
    lastEventDisplayedAt = Date.now()
  }
  processingEventQueue = false
}

function handleSseEvent(eventType: string, dataStr: string, streamId: number) {
  if (!dataStr && eventType !== 'end') return
  sseEventQueue.push({ eventType, dataStr, streamId })
  void processEventQueue()
}

function processSseEvent(eventType: string, dataStr: string) {
  if (!dataStr && eventType !== 'end') return
  if (eventType === 'error') {
    let errorMessage = t('dataAnalysis.analysis.failed')
    let fallbackResult = ''
    let fallbackExtra: unknown
    try {
      const payload = JSON.parse(dataStr)
      errorMessage = payload?.message || payload?.data?.error_message || errorMessage
      if (payload?.data?.result) {
        fallbackResult = String(payload.data.result)
        fallbackExtra = payload?.data?.extra
      }
    } catch {
      errorMessage = dataStr || errorMessage
    }
    finalError.value = errorMessage
    analysisError.value = errorMessage
    analysisState.value = 'error'
    if (fallbackResult) {
      setFinalOutput(fallbackResult, fallbackExtra)
    } else {
      setFinalOutput('')
    }
    return
  }

  if (eventType === 'end') {
    let endMessage = dataStr || t('dataAnalysis.analysis.complete')
    let endExtra = finalExtra.value || undefined
    
    // 尝试解析 JSON 以提取 extra 信息
    try {
      const payload = JSON.parse(dataStr)
      if (payload?.final_answer) {
        endMessage = String(payload.final_answer)
        endExtra = payload?.extra
      } else if (payload?.message) {
        endMessage = String(payload.message)
        endExtra = payload?.extra || endExtra
      } else if (payload?.extra) {
        endExtra = payload.extra
      }
    } catch {
      // 如果不是 JSON，使用原始字符串
    }
    
    setFinalOutput(endMessage, endExtra)
    analysisState.value = 'ready'
    return
  }

  if (eventType === 'progress') {
    try {
      const payload = JSON.parse(dataStr)
      if (payload?.final_answer) {
        setFinalOutput(String(payload.final_answer), payload?.extra)
      } else {
        const msg = payload?.message ?? dataStr
        setFinalOutput(String(msg), payload?.extra)
      }
    } catch {
      setFinalOutput(dataStr)
    }
    analysisState.value = 'loading'
    return
  }

  setFinalOutput(dataStr)
}

function parseSseChunk(rawChunk: string, streamId: number) {
  const lines = rawChunk.split('\n')
  let eventType = 'message'
  const dataLines: string[] = []
  lines.forEach(line => {
    const trimmed = line.trim()
    if (trimmed.startsWith('event:')) {
      eventType = trimmed.slice(6).trim() || 'message'
    } else if (trimmed.startsWith('data:')) {
      dataLines.push(trimmed.slice(5).trim())
    }
  })
  const dataStr = dataLines.join('\n')
  handleSseEvent(eventType, dataStr, streamId)
}

async function startFileAnalysisStream(fileId: string, question: string) {
  stopCurrentStream()
  activeStreamId += 1
  const streamId = activeStreamId
  analysisLoading.value = true
  analysisResult.value = ''
  analysisError.value = ''
  finalMessage.value = ''
  finalExtra.value = null
  finalError.value = ''
  // 不清空消息列表，保留之前的对话历史
  analysisState.value = 'loading'

  const controller = new AbortController()
  currentStreamController = controller

  try {
    const url = new URL('/STAnalyzer/api/analysis/analyze-file/stream/deep', window.location.origin)
    url.searchParams.set('file_id', fileId)
    url.searchParams.set('query', question)

    const headers: Record<string, string> = {
      Accept: 'text/event-stream',
      // 禁用缓存，确保实时流式传输
      'Cache-Control': 'no-cache, no-transform',
      // 提示代理不要缓冲（某些代理会识别此头）
      'X-Accel-Buffering': 'no'
    }
    const token = tokenManager.getToken()
    if (token) {
      headers.Authorization = `Bearer ${token}`
      headers.token = token
      // 也支持查询参数方式
      url.searchParams.set('token', token)
      url.searchParams.set('access_token', token)
    }

    const response = await fetch(url.toString(), {
      method: 'POST',
      headers,
      signal: controller.signal
    })

    if (!response.ok || !response.body) {
      throw new Error(t('dataAnalysis.errors.requestFailed', { status: response.status }))
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      let splitIndex = buffer.indexOf('\n\n')
      while (splitIndex !== -1) {
        const rawEvent = buffer.slice(0, splitIndex)
        buffer = buffer.slice(splitIndex + 2)
        if (rawEvent.trim()) {
          parseSseChunk(rawEvent, streamId)
        }
        splitIndex = buffer.indexOf('\n\n')
      }
    }

    if (buffer.trim()) {
      parseSseChunk(buffer, streamId)
    }
  } catch (err: any) {
    if (controller.signal.aborted) return
    analysisError.value = err?.message || t('dataAnalysis.analysis.failed')
    finalError.value = analysisError.value
    setFinalOutput('')
    analysisState.value = 'error'
  } finally {
    if (currentStreamController === controller) {
      currentStreamController = null
    }
    analysisLoading.value = false
  }
}

async function startExecutionAnalysisStream(question: string, executionId?: string) {
  stopCurrentStream()
  activeStreamId += 1
  const streamId = activeStreamId
  analysisLoading.value = true
  analysisResult.value = ''
  analysisError.value = ''
  finalMessage.value = ''
  finalExtra.value = null
  finalError.value = ''
  analysisState.value = 'loading'

  const controller = new AbortController()
  currentStreamController = controller

  try {
    const url = new URL('/STAnalyzer/api/analysis/analyze-execution/stream/deep', window.location.origin)
    url.searchParams.set('query', question)
    // If execution_id is provided, add it as a parameter (backend may use it for context)
    if (executionId) {
      url.searchParams.set('execution_id', executionId)
    }

    const headers: Record<string, string> = {
      Accept: 'text/event-stream',
      // 禁用缓存，确保实时流式传输
      'Cache-Control': 'no-cache, no-transform',
      // 提示代理不要缓冲（某些代理会识别此头）
      'X-Accel-Buffering': 'no'
    }
    const token = tokenManager.getToken()
    if (token) {
      headers.Authorization = `Bearer ${token}`
      headers.token = token
      // 也支持查询参数方式
      url.searchParams.set('token', token)
      url.searchParams.set('access_token', token)
    }

    const response = await fetch(url.toString(), {
      method: 'POST',
      headers,
      signal: controller.signal
    })

    if (!response.ok || !response.body) {
      throw new Error(t('dataAnalysis.errors.requestFailed', { status: response.status }))
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      let splitIndex = buffer.indexOf('\n\n')
      while (splitIndex !== -1) {
        const rawEvent = buffer.slice(0, splitIndex)
        buffer = buffer.slice(splitIndex + 2)
        if (rawEvent.trim()) {
          parseSseChunk(rawEvent, streamId)
        }
        splitIndex = buffer.indexOf('\n\n')
      }
    }

    if (buffer.trim()) {
      parseSseChunk(buffer, streamId)
    }
  } catch (err: any) {
    if (controller.signal.aborted) return
    analysisError.value = err?.message || t('dataAnalysis.analysis.failed')
    finalError.value = analysisError.value
    setFinalOutput('')
    analysisState.value = 'error'
  } finally {
    if (currentStreamController === controller) {
      currentStreamController = null
    }
    analysisLoading.value = false
  }
}

function roleLabel(role: 'user' | 'assistant') {
  if (role === 'assistant') return t('app.agent')
  return t('app.user')
}

function isNearBottom(el: HTMLElement, threshold = 120) {
  const distance = el.scrollHeight - el.scrollTop - el.clientHeight
  return distance <= threshold
}

function handleMessageListScroll() {
  const el = messageListRef.value
  if (!el) return
  userLockedScroll.value = !isNearBottom(el)
}

function scrollToBottom(force = false) {
  const el = messageListRef.value
  if (!el) return
  if (force || !userLockedScroll.value || isNearBottom(el)) {
    requestAnimationFrame(() => {
      el.scrollTo({
        top: el.scrollHeight,
        behavior: 'smooth'
      })
    })
  }
}

// 监听消息变化，自动滚动到底部
watch(
  () => analysisMessages.value.length,
  () => {
    void nextTick().then(() => scrollToBottom(false))
  }
)
</script>

<style scoped>
.data-analysis-page {
  padding: 12px;
  height: 100%;
  background: #f6f7fb;
}

.toolbar-card {
  margin-bottom: 12px;
}

.toolbar-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.field {
  display: flex;
  align-items: center;
  gap: 8px;
}

.field-label {
  color: #666;
  font-size: 13px;
}

.content-row {
  height: calc(100vh - 150px);
}

.panel-card {
  height: calc(100vh - 150px);
  display: flex;
  flex-direction: column;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  font-weight: 600;
}

.preview-mode-switch {
  margin-left: auto;
}

.subtext {
  color: #909399;
  font-size: 12px;
}

.panel-body {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.file-list {
  height: 100%;
}

.file-menu {
  border: none;
}

.file-item {
  display: flex;
  align-items: center;
  width: 100%;
  height: 34px;
}

.file-name {
  flex: 1;
  font-weight: 600;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.preview-body {
  padding: 0;
  height: 100%;
  overflow: hidden;
}

.preview-wrapper {
  height: 100%;
}

.fallback-preview {
  padding: 12px;
}

.analysis-body {
  padding: 12px;
  gap: 12px;
  overflow-y: auto;
  min-height: 0;
}

.analysis-form {
  margin-bottom: 12px;
}

.action-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.result-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.result-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
}

.result-box {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  background: #fff;
  padding: 16px;
  min-height: 180px;
  display: flex;
  flex-direction: column;
}

.state-card {
  border: 1px dashed #e5e7eb;
  border-radius: 12px;
  padding: 24px;
  text-align: center;
  color: #6b7280;
  background: #fafafa;
}

.state-title {
  font-weight: 600;
  color: #111827;
  margin-bottom: 8px;
}

.message-stack {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
  flex: 1;
  min-height: 0;
}

.message-list {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 14px;
  background: #fff;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 360px;
  max-height: 500px;
}

.message-card {
  border: 1px solid #eef2f7;
  border-radius: 12px;
  padding: 12px 14px;
  background: #fff;
  box-shadow: 0 2px 6px rgba(17, 24, 39, 0.04);
  min-width: 80%;
  max-width: 95%;
  word-break: break-word;
}

.message-card[data-role='user'] {
  background: #eef2ff;
  border-color: #e0e7ff;
  align-self: flex-end;
}

.message-card[data-role='assistant'] {
  background: #ecfdf3;
  border-color: #d1fae5;
}

.typing-indicator-card {
  max-width: 200px;
}

.typing-indicator {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 6px;
}

.typing-indicator .dot {
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: #4ade80;
  opacity: 0.4;
  animation: typing-bounce 1.2s infinite ease-in-out;
}

.typing-indicator .dot:nth-child(2) {
  animation-delay: 0.15s;
}

.typing-indicator .dot:nth-child(3) {
  animation-delay: 0.3s;
}

.message-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
  color: #6b7280;
  font-size: 12px;
}

.badge {
  padding: 4px 10px;
  border-radius: 999px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.badge[data-role='assistant'] {
  background: #ecfdf3;
  color: #047857;
}

.badge[data-role='user'] {
  background: #e0e7ff;
  color: #3730a3;
}

.timestamp {
  font-variant-numeric: tabular-nums;
}

.result-events {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.result-event {
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 10px;
  background: #fafafa;
  transition: background 0.2s ease, border-color 0.2s ease;
}

.result-event.is-expandable {
  cursor: pointer;
}

.result-event.is-expandable:hover {
  border-color: #dcdfe6;
  background: #f5f7fa;
}

.result-event.is-expanded {
  border-color: #409eff;
  background: #f0f7ff;
}

.event-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.event-title {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.event-index {
  font-weight: 600;
  color: #606266;
}

.event-message {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  color: #303133;
  line-height: 1.6;
  word-break: break-word;
}

.event-message :deep(p) {
  margin: 0;
}

.event-extra {
  margin-top: 8px;
  padding: 10px;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  font-family: inherit;
  font-size: 13px;
  color: #303133;
  overflow-x: auto;
}

.event-extra pre {
  margin: 0;
  white-space: pre-wrap;
}

.event-files {
  margin-top: 8px;
  padding: 10px;
  background: #f9fafc;
  border: 1px dashed #e4e7ed;
  border-radius: 6px;
}

.files-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.file-item {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.file-meta {
  flex: 1;
  min-width: 0;
}

.file-name {
  font-weight: 600;
  color: #303133;
  word-break: break-word;
}

.file-desc {
  color: #606266;
  font-size: 13px;
  margin-top: 2px;
  word-break: break-word;
}

.file-path {
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
  word-break: break-all;
}

.extra-block + .extra-block {
  margin-top: 8px;
}

.extra-label {
  font-weight: 600;
  color: #606266;
  margin-bottom: 4px;
  font-size: 12px;
}

.extra-content {
  color: #303133;
  line-height: 1.6;
  font-family: inherit;
  font-size: 13px;
}

.extra-pre {
  margin: 0;
  white-space: pre-wrap;
  background: #f8f9fb;
  padding: 8px;
  border-radius: 4px;
  overflow: auto;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  word-break: break-word;
}

.result-footer-loading {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  color: #409eff;
  font-size: 13px;
}

.loading-icon {
  font-size: 16px;
}

.result-loading,
.result-error {
  padding: 4px;
}

.result-markdown {
  font-size: 13px;
  line-height: 1.6;
  color: #303133;
  word-break: break-word;
}

.result-markdown p {
  margin: 0 0 8px;
}

.result-markdown h1,
.result-markdown h2,
.result-markdown h3,
.result-markdown h4,
.result-markdown h5,
.result-markdown h6 {
  margin: 10px 0 6px;
  font-weight: 700;
}

@keyframes typing-bounce {
  0%,
  60%,
  100% {
    transform: translateY(0);
    opacity: 0.4;
  }
  30% {
    transform: translateY(-3px);
    opacity: 1;
  }
}

.result-markdown ul,
.result-markdown ol {
  padding-left: 18px;
  margin: 6px 0 10px;
}

.result-markdown code {
  background: #f5f5f5;
  padding: 2px 4px;
  border-radius: 4px;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 12px;
}

.result-markdown pre {
  background: #f5f5f5;
  padding: 10px;
  border-radius: 6px;
  overflow: auto;
  margin: 8px 0;
  font-size: 12px;
}

.result-markdown table {
  border-collapse: collapse;
  width: 100%;
  margin: 8px 0;
}

.result-markdown th,
.result-markdown td {
  border: 1px solid #ebeef5;
  padding: 6px 8px;
}

.mt-8 {
  margin-top: 8px;
}

.mt-12 {
  margin-top: 12px;
}

.mb-12 {
  margin-bottom: 12px;
}

.ml-4 {
  margin-left: 4px;
}

.view-tabs {
  margin: -12px -12px 0;
}

.view-tabs :deep(.el-tabs__header) {
  margin: 0;
}

.view-tabs :deep(.el-tabs__nav-wrap) {
  padding: 0 12px;
}

.execution-list {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.execution-list :deep(.el-scrollbar) {
  flex: 1;
}

.execution-list :deep(.el-scrollbar__wrap) {
  overflow-x: hidden;
}

.execution-menu {
  border: none;
}

.execution-item {
  display: flex;
  align-items: center;
  width: 100%;
  height: 34px;
}

.execution-id {
  flex: 1;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 12px;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>

