<template>
  <div class="analysis-workflow-container" :class="{ 'left-panel-collapsed': isLeftPanelCollapsed, 'no-agent-panel': !isProjectSelected }">
    <!-- 左侧面板折叠按钮 -->
    <button 
      class="left-panel-toggle-btn" 
      @click="toggleLeftPanel"
      :title="isLeftPanelCollapsed ? (t('analysis.expandLeftPanel') || 'Expand') : (t('analysis.collapseLeftPanel') || 'Collapse')"
    >
      <span class="toggle-icon">{{ isLeftPanelCollapsed ? '▶' : '◀' }}</span>
    </button>
    
    <!-- 左侧：项目列表和服务列表 -->
    <div class="left-panel" v-show="!isLeftPanelCollapsed">
      <ProjectListPanel
        v-if="!isProjectSelected"
        :project-list="projectList ?? null"
        :current-project-id="previewProjectId ?? null"
        @select-project="selectProjectWithExtras"
        @delete-project="handleDeleteProjectClick"
      />
      <FileListPanel
        v-else
        :files="filteredFileDataList"
        :current-file-id="currentDataId"
        @add-data="showAddDataDialog = true"
        @back-to-projects="backToProjectsWithExtras"
        @select-file="selectData"
        @toggle-action-menu="toggleActionMenu"
      />
    </div>
    
    <!-- 中间：分析内容区域 -->
    <div class="center-panel">
      <div class="panel-content">
        <div v-if="isLoading" class="panel-status panel-status-loading">
          <el-skeleton :rows="4" animated />
        </div>
        <div v-else-if="loadError" class="panel-status panel-status-error">
          <el-alert
            :title="loadError"
            type="error"
            show-icon
            :closable="false"
          />
        </div>
        <div v-else-if="!hasDagData && !activeComponent" class="panel-status panel-status-empty">
          <el-empty :description="$t('app.noAnalysisData')" />
        </div>
        <div v-else class="content-area">
          <!-- 动态组件：显示DAG或子组件 -->
          <component 
            v-if="activeComponent" 
            :is="activeComponent" 
            :fileId="currentFileId"
          />
          <DAGVisualization 
            v-else 
            :nodes="dagNodes" 
            :edges="dagEdges" 
            :files="dagFiles" 
            @file-deleted="handleDagFileDeleted"
            @refresh-dag="handleDagRefresh"
          />
        </div>
      </div>
    </div>
    
    <!-- 右侧：Agent对话区（仅在选择项目后显示） -->
    <div class="right-panel" v-if="isProjectSelected">
      <ProjectAgentPane
        ref="projectAgentPaneRef"
        :project-id="currentProjectId ?? null"
        :project-name="currentProject?.name ?? null"
      />
    </div>

    <!-- 添加数据对话框 -->
    <UploadFileDialog
      v-model="showAddDataDialog"
      ref="uploadDialogRef"
      @upload="handleUploadWithInfo"
    />

    <!-- 编辑文件信息对话框（项目模式下通过 DAG 节点菜单触发） -->
    <EditFileDialog
      v-model="showEditDialog"
      ref="editDialogRef"
      :file-info="editTargetFileInfo"
      :file-name="editTarget?.name"
      @save="handleUpdateFile"
    />

    <!-- 删除确认对话框（项目模式下通过 DAG 节点菜单触发） -->
    <DeleteFileDialog
      v-model="showDeleteDialog"
      ref="deleteDialogRef"
      :file-name="deleteTarget?.name"
      @confirm="handleDeleteFile"
    />

    <!-- 删除项目确认对话框 -->
    <DeleteProjectDialog
      v-model="showDeleteProjectDialog"
      ref="deleteProjectDialogRef"
      :project-name="deleteProjectTarget?.name"
      @confirm="handleDeleteProject"
    />

    
    <!-- 文件项操作菜单 -->
    <div 
      v-if="activeActionMenuId && actionMenuPosition" 
      class="action-menu" 
      :style="actionMenuStyle"
      @click.stop
    >
      <div 
        class="action-menu-item" 
        @click="() => {
          const fileData = fileDataList.find(f => f.id === activeActionMenuId);
          if (fileData && fileData.fileId) showEditDialogHandler(fileData.fileId);
          activeActionMenuId = null;
        }"
      >
        <span class="icon">✏️</span> {{ t('common.edit') }}
      </div>
      <div 
        class="action-menu-item action-menu-item-danger" 
        @click="() => {
          const fileData = fileDataList.find(f => f.id === activeActionMenuId);
          if (fileData) {
            deleteTarget = fileData;
            showDeleteDialog = true;
          }
          activeActionMenuId = null;
        }"
      >
        <span class="icon">🗑️</span> {{ t('common.delete') }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, shallowRef, markRaw, computed, provide } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElAlert, ElButton, ElEmpty, ElSkeleton, ElTooltip } from 'element-plus'
import DAGVisualization from './analysis/DAGVisualization.vue'
import SpatialTranscriptomics from './analysis/SpatialTranscriptomics.vue'
import SpatialVisualization from './analysis/SpatialVisualization.vue'
import DGEResultsVisualization from './analysis/DGEResultsVisualization.vue'
import CellCommunicationVisualization from './analysis/CellCommunicationVisualization.vue'
import ProjectAgentPane from './analysis/ProjectAgentPane.vue'
import ProjectListPanel from './analysis/ProjectListPanel.vue'
import FileListPanel from './analysis/FileListPanel.vue'
import UploadFileDialog from './analysis/UploadFileDialog.vue'
import EditFileDialog from './analysis/EditFileDialog.vue'
import DeleteFileDialog from './analysis/DeleteFileDialog.vue'
import DeleteProjectDialog from './analysis/DeleteProjectDialog.vue'
import { uploadFile, updateFileInfo, deleteFile, type FileInfo } from '../api/file'
import { deleteProject, type Project } from '../api/project'
// getFileList, getProject: 已废弃，项目模式下统一使用 dagFiles，不再需要单独加载文件列表
import { useProjectManagement } from '../composables/useProjectManagement'
import { notifyError, notifySuccess } from '../utils/notify'
import type { DagNode, DagEdge, AnalysisComponent } from '../types/dag'
import type { FileNode } from '../api/analysis'
import { Status as AnalysisStatus } from '../api/analysis'
import { FALLBACK_FILE_TYPE_ID, getConfiguredFileTypeId } from '../constants/fileTypes'
import { useFileTypes } from '../composables/useFileTypes'

const router = useRouter()
const route = useRoute()
const { t } = useI18n()

// ==================== 左侧面板折叠状态 ====================
const isLeftPanelCollapsed = ref(false)

function toggleLeftPanel() {
  isLeftPanelCollapsed.value = !isLeftPanelCollapsed.value
  // 保存折叠状态到 localStorage
  localStorage.setItem('analysisLeftPanelCollapsed', String(isLeftPanelCollapsed.value))
}

// ==================== 项目选择状态 ====================
// 用于区分“预览模式”和“选择模式”
const isProjectSelected = ref(false) // 是否明确选择了项目
const previewProjectId = ref<string | null>(null) // 预览模式下的项目 ID

// ==================== 类型定义 ====================
interface DataItem {
  id: string
  name: string
  uploadTime: string
  fileId?: string | null
  description?: string
  fileTypeId?: string | null
  fileInfo?: FileInfo // 可选的文件信息对象
}

interface UploadPayload {
  file: File
  name: string
  description: string
  fileTypeId: string
}

// ==================== 数据管理 ====================
const currentDataId = ref<string | null>(null)
const currentFileId = ref<string | null>(null)

/**
 * 从 dagFiles 转换为 DataItem[] 格式
 */
function convertDagFilesToDataItems(files: FileNode[]): DataItem[] {
  return files.map((file: FileNode) => {
    const fileId = (file as any).file_id || (file as any).id || (file as any).fileId || null
    if (!fileId) return null
    const status = (file as any).status || (file as any).node_status
    if (status && status !== AnalysisStatus.COMPLETED) return null
    const fileName = file.filename || t('analysis.defaultFileName', { id: fileId })
    const rawType = (file as any).file_type
    const normalizedType =
      (file as any).file_type_id ||
      (file as any).fileTypeId ||
      (typeof rawType === 'string' ? rawType : rawType?.id) ||
      null
    return {
      id: `data_${fileId}`,
      name: fileName,
      uploadTime: new Date().toLocaleString('zh-CN'),
      fileId: fileId,
      description: undefined,
      fileTypeId: normalizedType
    }
  }).filter((item): item is DataItem => !!item)
}

/**
 * 文件数据列表（从 dagFiles 转换）
 */
const fileDataList = computed<DataItem[]>(() => {
  const seen = new Set<string>()
  const result: DataItem[] = []
  convertDagFilesToDataItems(dagFiles.value).forEach(item => {
    if (item.fileId && seen.has(item.fileId)) return
    if (item.fileId) seen.add(item.fileId)
    result.push(item)
  })
  return result
})

// 基于文件名后缀的简单过滤（规则：文件名以 .h5ad 结尾，默认生效）
const filteredFileDataList = computed<DataItem[]>(() => {
  return fileDataList.value.filter(item => {
    const name = (item.name || '').trim().toLowerCase()
    const isH5ad = name.endsWith('.h5ad')
    const isDgeCsv =
      item.fileTypeId === 'dge_results_csv' ||
      (name.endsWith('.csv') && name.includes('dge'))
    const isLigrec = item.fileTypeId === 'ligrec_interactions_csv'
    return isH5ad || isDgeCsv || isLigrec
  })
})

/**
 * 将 dagFiles 转换为以 file_id 为 key 的字典（O(1) 查找性能）
 * 用于快速通过 fileId 获取完整文件信息
 */
const filesDict = computed(() => {
  const dict: Record<string, FileNode> = {}
  dagFiles.value.forEach(file => {
    if (file?.file_id) {
      dict[file.file_id] = file
    }
  })
  return dict
})


// ==================== 项目管理 ====================
// 路由更新标志：用于跟踪路由更新来源，避免循环更新
const isUpdatingFromRoute = ref(false)

// ==================== DAG相关 ====================
const dagNodes = ref<DagNode[]>([])
const dagEdges = ref<DagEdge[]>([])
const dagFiles = ref<FileNode[]>([])
const hasDagData = computed(() => dagNodes.value.length > 0)
const isLoading = ref(false)
const loadError = ref('')
const activeComponent = shallowRef<AnalysisComponent>(null)

// 组件映射
// 注意：quality-control 不是一个可视化组件，它应该通过服务执行来完成
// 因此不在此映射中，点击 quality-control 节点将保持在 DAG 视图
const componentMap = {
  'spatial-transcriptomics': markRaw(SpatialTranscriptomics),
  'spatial-visualization': markRaw(SpatialVisualization),
  'dge-results-visualization': markRaw(DGEResultsVisualization),
  'cell-communication-visualization': markRaw(CellCommunicationVisualization)
}

// ==================== Agent 对话相关系统提示（改为 toast） ====================
function pushAgentInfoToast(message: string) {
  notifySuccess({ message })
}

// ==================== UI状态 ====================
const showAddDataDialog = ref<boolean>(false)
const uploadDialogRef = ref<InstanceType<typeof UploadFileDialog> | null>(null)
const projectAgentPaneRef = ref<InstanceType<typeof ProjectAgentPane> | null>(null)
const { fileTypeMap: globalFileTypeMap, ensureLoaded: ensureGlobalFileTypes } = useFileTypes()

const activeActionMenuId = ref<string | null>(null)
const actionMenuPosition = ref<{ top: number; left: number } | null>(null)

const showEditDialog = ref<boolean>(false)
const editDialogRef = ref<InstanceType<typeof EditFileDialog> | null>(null)
const editTarget = ref<DataItem | null>(null)
const editTargetFileInfo = computed<FileInfo | null>(() => {
  if (!editTarget.value) return null
  const targetData = editTarget.value as any
  return (targetData.fileInfo as FileInfo | undefined) || null
})

const showDeleteDialog = ref<boolean>(false)
const deleteDialogRef = ref<InstanceType<typeof DeleteFileDialog> | null>(null)
const deleteTarget = ref<DataItem | null>(null)

const showDeleteProjectDialog = ref<boolean>(false)
const deleteProjectDialogRef = ref<InstanceType<typeof DeleteProjectDialog> | null>(null)
const deleteProjectTarget = ref<Project | null>(null)



// ==================== 函数 ====================
/**
 * 触发分析组件导航
 */
function triggerAnalysisComponent(componentId: string, fileId: string) {
  activeComponent.value = componentMap[componentId as keyof typeof componentMap] || null
  currentFileId.value = fileId || null
}

/**
 * 返回DAG视图
 */
function goHome() {
  activeComponent.value = null
  currentFileId.value = null
  currentDataId.value = null
}

/**
 * 重置 DAG 状态
 */
function resetDagState() {
  dagNodes.value = []
  dagEdges.value = []
  dagFiles.value = []
}

/**
 * 选择项目（包装函数，添加额外的逻辑）
 * 
 * @param projectId - 项目ID
 * @param skipRouteUpdate - 是否跳过路由更新（已废弃，使用 isUpdatingFromRoute 标志）
 */
async function selectProjectWithExtras(projectId: string, skipRouteUpdate = false) {
  if (!projectId) return
  
  // 标记为明确选择了项目
  isProjectSelected.value = true
  previewProjectId.value = null
  
  // 判断是否应该更新路由：如果不是从路由更新来的，且不是跳过路由更新，则需要更新路由
  const shouldUpdateRoute = !isUpdatingFromRoute.value && !skipRouteUpdate
  
  // 如果已经是当前项目，且不需要更新路由，则跳过
  if (currentProjectId.value === projectId && !shouldUpdateRoute) {
    // 仍然尝试刷新项目DAG数据（包含文件列表）
    try {
      await loadProjectDAGDataFromComposable(projectId)
    } catch {}
    return
  }
  
  currentDataId.value = null
  currentFileId.value = null
  
  try {
    // 调用 composable 的 selectProject，传递路由更新标志
    await selectProjectFromComposable(projectId, !shouldUpdateRoute)
    
    // 加载项目DAG数据（包含文件信息，无需单独加载文件列表）
    if (currentProjectId.value) {
      await loadProjectDAGDataFromComposable(currentProjectId.value)
    }
  } catch (error: unknown) {
    console.error('选择项目失败:', error)
  }
}

/**
 * 返回项目列表（包装函数，添加额外的逻辑）
 */
function backToProjectsWithExtras() {
  // 避免因路由清空 projectId 触发 watch 再次执行，导致弹窗/提示重复
  if (isUpdatingFromRoute.value) return
  isUpdatingFromRoute.value = true

  currentDataId.value = null
  currentFileId.value = null
  isProjectSelected.value = false
  goHome()
  resetDagState()
  
  // 返回项目列表后，重新加载第一个项目的DAG作为预览
  backToProjectsFromComposable()
  
  // 延迟加载预览，确保 projectList 已更新
  setTimeout(async () => {
    if (projectList.value && projectList.value.length > 0) {
      const firstProject = projectList.value[0]
      if (firstProject?.project_id) {
        previewProjectId.value = firstProject.project_id
        try {
          await loadProjectDAGDataFromComposable(firstProject.project_id)
        } catch (error) {
          console.error('加载预览DAG失败:', error)
        }
      }
    }
    // 导航和预览处理完成后再释放路由更新标记
    isUpdatingFromRoute.value = false
  }, 120)
}

/**
 * 处理删除项目点击事件
 */
function handleDeleteProjectClick(project: Project) {
  deleteProjectTarget.value = project
  showDeleteProjectDialog.value = true
}

/**
 * 处理删除项目确认
 */
async function handleDeleteProject() {
  if (!deleteProjectTarget.value) return

  const dialog = deleteProjectDialogRef.value
  if (!dialog) return

  try {
    dialog.setDeleting(true)
    
    const projectId = deleteProjectTarget.value.project_id
    if (!projectId) {
      throw new Error('项目ID不存在')
    }

    await deleteProject(projectId)
    
    // 如果删除的是当前项目，返回项目列表
    if (currentProjectId.value === projectId) {
      backToProjectsWithExtras()
    }
    
    // 刷新项目列表
    await loadProjectList()
    
    // 显示成功消息
    notifySuccess({
      message: t('project.actions.deleteSuccess', {
        name: deleteProjectTarget.value.name
      })
    })
    
    dialog.close()
    deleteProjectTarget.value = null
    showDeleteProjectDialog.value = false
  } catch (error: unknown) {
    console.error('删除项目失败:', error)
    const errorMessage = error instanceof Error ? error.message : t('app.unknownError')
    notifyError({
      message: t('project.actions.deleteFailed', { error: errorMessage })
    })
  } finally {
    dialog.setDeleting(false)
  }
}

// 注意：loadProjectFiles 函数已移除
// 项目模式下统一使用 dagFiles，通过 fileDataList 计算属性访问文件列表
// 文件信息从 DAG 数据中获取，无需单独加载

/**
 * 处理 DAG 组件删除文件事件
 */
async function handleDagFileDeleted(fileId: string) {
  if (!fileId) return

  dagNodes.value = dagNodes.value.filter(node => node?.id !== fileId)
  dagEdges.value = dagEdges.value.filter(edge => edge?.source !== fileId && edge?.target !== fileId)
  // 从数组中删除文件
  dagFiles.value = dagFiles.value.filter((file: FileNode) => {
    const fileIdToCheck = file?.file_id
    return fileIdToCheck !== fileId
  })
  
  // 重新加载 DAG 数据以保持同步
  if (currentProjectId.value) {
    try {
      await loadProjectDAGDataFromComposable(currentProjectId.value)
    } catch (error) {
      console.error('刷新项目数据失败:', error)
    }
  }
}

/**
 * 处理DAG刷新事件
 */
async function handleDagRefresh() {
  if (currentProjectId.value) {
    try {
      await loadProjectDAGDataFromComposable(currentProjectId.value)
    } catch (error) {
      console.error('刷新DAG数据失败:', error)
    }
  }
}

/**
 * 选择数据
 */
function selectData(dataId: string) {
  activeActionMenuId.value = null
  actionMenuPosition.value = null

  if (!currentProjectId.value) {
    notifyError({ message: t('app.selectProjectFirst') })
    return
  }

  const data = fileDataList.value.find(d => d.id === dataId)
  if (!data) return

  const normalizedName = (data.name || '').toLowerCase()
  const isDge =
    data.fileTypeId === 'dge_results_csv' ||
    (normalizedName.endsWith('.csv') && normalizedName.includes('dge'))
  const isLigrec = data.fileTypeId === 'ligrec_interactions_csv'
  const targetComponentId = isLigrec
    ? 'cell-communication-visualization'
    : isDge
      ? 'dge-results-visualization'
      : 'spatial-visualization'

  // 点击同一个文件且已经在可视化视图时，返回 DAG
  if (dataId === currentDataId.value && activeComponent.value === componentMap[targetComponentId]) {
    goHome()
    return
  }

  currentDataId.value = data.id
  currentFileId.value = data.fileId || null
  // 默认进入可视化视图
  activeComponent.value = componentMap[targetComponentId]

  router.push({
    path: '/analysis',
    query: { projectId: currentProjectId.value}
  })

  pushAgentInfoToast(t('app.dataSwitched', { name: data.name }))
}

/**
 * 文件上传相关
 */
const defaultFileTypeId = getConfiguredFileTypeId() ?? FALLBACK_FILE_TYPE_ID

async function handleUploadWithInfo(payload: UploadPayload) {
  const { file, name, description, fileTypeId: providedFileTypeId } = payload
  if (!file) return

  const dialog = uploadDialogRef.value
  if (!dialog) return

  const fileTypeId = providedFileTypeId || defaultFileTypeId
  if (!fileTypeId) {
    dialog.setStatus(t('analysis.upload.fileTypeRequired'), true)
    return
  }

  try {
    dialog.setUploading(true)
    dialog.setStatus(t('app.preparingUpload'), false)
    
    // 如果有项目ID，上传时关联到项目
    const result = await uploadFile({
      file,
      fileTypeId,
      projectId: currentProjectId.value || undefined,
      onProgress: (progress) => {
        dialog.setStatus(t('app.uploadingProgress', { progress }), false)
      }
    })
    
    // 兼容处理：支持 fileId 和 file_id 两种字段名
    const fileId = result.fileId || (result as { file_id?: string }).file_id
    if (!fileId) {
      throw new Error('文件上传成功但未返回文件ID')
    }
    
    if (name.trim() || description.trim()) {
      try {
        await updateFileInfo(fileId, {
          name: name.trim() || undefined,
          description: description.trim() || undefined
        })
      } catch (error: unknown) {
        console.warn('更新文件信息失败，但文件已上传:', error)
      }
    }
    
    // 如果当前在项目模式下，重新加载DAG数据（包含文件信息）
    // 注意：如果上传时已经提供了 project_id，后端会自动添加文件到项目
    // 项目模式下统一使用 dagFiles，无需单独加载文件列表
    if (currentProjectId.value) {
      try {
        // 刷新DAG数据以显示新上传的文件节点
        await loadProjectDAGDataFromComposable(currentProjectId.value)
      } catch (error: unknown) {
        console.warn('重新加载项目DAG数据失败:', error)
      }
    }
        
    const finalName = name.trim() || file.name
    const responseFileType = (result.file_type || result.fileType) as FileInfo['file_type']
    const responseDisplayName =
      typeof responseFileType === 'object'
        ? responseFileType?.display_name || responseFileType?.name
        : null
    const fallbackType = globalFileTypeMap.value[fileTypeId]
    const displayName = responseDisplayName || fallbackType?.display_name || ''
    
    const successMessage = displayName
      ? `${t('app.uploadSuccess', { name: finalName })} (${displayName})`
      : t('app.uploadSuccess', { name: finalName })
    pushAgentInfoToast(successMessage)
    dialog.setStatus(t('app.uploadSuccessMessage'), false)
    dialog.close()
  } catch (err: unknown) {
    console.error('上传失败:', err)
    const errorMessage = err instanceof Error ? err.message : t('app.unknownError')
    dialog.setStatus(t('app.uploadFailed', { error: errorMessage }), true)
  } finally {
    dialog.setUploading(false)
  }
}

// 初始化项目管理 composable
const projectManagement = useProjectManagement({
  onAgentMessage: (_role, message) => {
    // 将来自 projectManagement 的 Agent 提示统一转换为 toast
    pushAgentInfoToast(message)
  },
  onDagDataUpdate: (data) => {
    dagNodes.value = data.nodes
    dagEdges.value = data.edges
    dagFiles.value = Array.isArray(data.files) ? data.files : []
  },
  onDagLoadingChange: (loading, error) => {
    isLoading.value = loading
    loadError.value = error
  }
})

// 从 composable 中解构状态和方法
const {
  projectList,
  currentProjectId,
  currentProject,
  loadProjectList,
  selectProject: selectProjectFromComposable,
  backToProjects: backToProjectsFromComposable,
  loadProjectDAGData: loadProjectDAGDataFromComposable,
} = projectManagement


async function handleDeleteFile() {
  if (!deleteTarget.value) return

  const dialog = deleteDialogRef.value
  if (!dialog) return

  try {
    dialog.setDeleting(true)
    
    const fileId = deleteTarget.value.fileId
    if (!fileId) {
      throw new Error('文件ID不存在')
    }

    await deleteFile(fileId)

    if (currentDataId.value === deleteTarget.value.id) {
      if (fileDataList.value.length > 0) {
        selectData(fileDataList.value[0].id)
      } else {
        selectData(null)
      }
    }
    pushAgentInfoToast(t('app.fileDeleted', { name: deleteTarget.value.name }))
    dialog.close()
    deleteTarget.value = null
  } catch (error: unknown) {
    console.error('删除文件失败:', error)
    const errorMessage = error instanceof Error ? error.message : t('app.unknownError')
    notifyError({
      message: t('app.deleteFailed', { error: errorMessage })
    })
  } finally {
    dialog.setDeleting(false)
  }
}

/**
 * 显示编辑文件对话框
 * @param fileIdOrData - 文件ID（字符串）或包含 fileId 的数据对象（向后兼容）
 */
function showEditDialogHandler(fileIdOrData: string | DataItem | any) {
  // 如果传入的是字符串（fileId），从 filesDict 获取完整信息
  if (typeof fileIdOrData === 'string') {
    const fileId = fileIdOrData
    const fileInfo = filesDict.value[fileId]
    if (!fileInfo) {
      console.warn(`文件信息未找到: ${fileId}`)
      notifyError({ message: t('app.fileIdMissing') })
      return
    }
    
    // 构建 DataItem 对象
    const fileName = fileInfo.filename || t('analysis.defaultFileName', { id: fileId })
    // 注意：FileNode 类型可能不包含所有字段，使用类型断言或可选链
    const fileInfoAny = fileInfo as any
    editTarget.value = {
      id: `data_${fileId}`,
      name: fileName,
      uploadTime: new Date().toLocaleString('zh-CN'),
      fileId: fileId,
      description: fileInfoAny.description,
      fileInfo: {
        fileId: fileId,
        name: fileName,
        size: fileInfoAny.size || 0,
        status: fileInfo.status || 'ready',
        time: fileInfoAny.time || new Date().toISOString(),
        description: fileInfoAny.description || ''
      } as FileInfo
    }
  } else {
    throw new Error('传入的参数不是字符串或DataItem对象')
  }
  showEditDialog.value = true
}

async function handleUpdateFile(name: string, description: string) {
  if (!editTarget.value) return

  const dialog = editDialogRef.value
  if (!dialog) return

  const fileId = editTarget.value.fileId
  if (!fileId) {
    notifyError({ message: t('app.fileIdMissing') })
    return
  }

  // 验证至少有一个字段被修改
  const targetData = editTarget.value as any
  const fileInfo = (targetData.fileInfo as FileInfo | undefined)
  const originalName = fileInfo?.name || editTarget.value.name || ''
  const originalDescription = fileInfo?.description || ''
  
  if (name.trim() === originalName && description.trim() === originalDescription) {
    dialog.close()
    return
  }

  try {
    dialog.setUpdating(true)
    
    const updateParams: { name?: string; description?: string } = {}
    if (name.trim() !== originalName) {
      updateParams.name = name.trim()
    }
    if (description.trim() !== originalDescription) {
      updateParams.description = description.trim()
    }

    await updateFileInfo(fileId, updateParams)

    // 重新加载 DAG 数据以获取最新文件信息
    if (currentProjectId.value) {
      try {
        await loadProjectDAGDataFromComposable(currentProjectId.value)
      } catch (error) {
        console.error('刷新项目数据失败:', error)
      }
    }

    // 如果当前选中的是编辑的文件，更新当前数据
    if (currentDataId.value === editTarget.value.id) {
      selectData(editTarget.value.id)
    }
    pushAgentInfoToast(t('app.fileUpdated', { name: updateParams.name || originalName }))
    dialog.close()
    editTarget.value = null
  } catch (error: unknown) {
    console.error('更新文件信息失败:', error)
    const errorMessage = error instanceof Error ? error.message : t('app.unknownError')
    notifyError({ 
      message: t('app.updateFailed', { error: errorMessage }) 
    })
  } finally {
    dialog.setUpdating(false)
  }
}

function handleClickOutside(event: MouseEvent) {
  if (activeActionMenuId.value) {
    const target = event.target as HTMLElement
    if (!target.closest('.action-menu-wrapper') && !target.closest('.action-menu')) {
      activeActionMenuId.value = null
      actionMenuPosition.value = null
    }
  }
}

function toggleActionMenu(event: MouseEvent, dataId: string) {
  if (activeActionMenuId.value === dataId) {
    activeActionMenuId.value = null
    actionMenuPosition.value = null
  } else {
    activeActionMenuId.value = dataId
    const button = event.currentTarget as HTMLElement
    const rect = button.getBoundingClientRect()
    actionMenuPosition.value = {
      top: rect.bottom + 4,
      left: rect.right - 180
    }
  }
}

const actionMenuStyle = computed(() => {
  if (!actionMenuPosition.value) {
    return {}
  }
  return {
    top: `${actionMenuPosition.value.top}px`,
    left: `${actionMenuPosition.value.left}px`
  }
})

// 将函数暴露到全局，供nodeActions使用
declare global {
  interface Window {
    triggerAnalysisComponent?: (componentId: string, fileId: string) => void
  }
}


// loadProjectList 已从 composable 中获取

// ==================== Provide/Inject ====================
// 使用 provide 提供函数给子组件，替代全局变量
provide('triggerAnalysisComponent', triggerAnalysisComponent)
provide('showEditFileDialog', showEditDialogHandler)

// 加入对话上下文
function addFileToContextHandler(fileId: string, fileName: string) {
  if (projectAgentPaneRef.value?.addFileToContext) {
    projectAgentPaneRef.value.addFileToContext(fileId, fileName)
  }
}
provide('addFileToContext', addFileToContextHandler)

// ==================== 生命周期 ====================
onMounted(async () => {
  // 恢复左侧面板折叠状态
  const savedCollapsedState = localStorage.getItem('analysisLeftPanelCollapsed')
  if (savedCollapsedState === 'true') {
    isLeftPanelCollapsed.value = true
  }
  
  // 预加载文件类型（供上传成功后 toast/映射使用）
  ensureGlobalFileTypes().catch(() => {})

  // 加载项目列表
  await loadProjectList()
  
  // 检查路由参数：使用 projectId
  const projectId = route.query.projectId as string | undefined
  
  if (projectId) {
    // 项目模式：初始化时路由已经包含 projectId，设置路由更新标志
    isUpdatingFromRoute.value = true
    try {
      await selectProjectWithExtras(projectId)
    } finally {
      isUpdatingFromRoute.value = false
    }
  } else if (projectList.value && projectList.value.length > 0) {
    // 如果没有指定项目ID，但有项目列表，加载第一个项目的DAG作为预览
    const firstProject = projectList.value[0]
    if (firstProject?.project_id) {
      previewProjectId.value = firstProject.project_id
      isProjectSelected.value = false
      try {
        await loadProjectDAGDataFromComposable(firstProject.project_id)
      } catch (error) {
        console.error('加载预览DAG失败:', error)
      }
    }
  }
  
  document.addEventListener('click', handleClickOutside)
}
)
  
  // 监听路由变化
const stopWatchProjectId = watch(
  () => ({
    projectId: route.query.projectId as string | undefined,
    path: route.path,
    name: route.name
  }),
  async (to, from) => {
    const isAnalysisRoute = to.path === '/analysis' || to.name === 'Analysis'

    // 离开分析页时不再处理 projectId，避免导航到其他页面被干扰
    if (!isAnalysisRoute) return

    // 如果已由编程式路由更新触发，避免重复执行
    if (isUpdatingFromRoute.value) return

    // 如果 projectId 没有变化，跳过
    if (to.projectId === from?.projectId) {
      return
    }
    
    if (to.projectId) {
      // 设置路由更新标志，避免循环更新
      isUpdatingFromRoute.value = true
      try {
        await selectProjectWithExtras(to.projectId)
      } finally {
        // 重置标志
        isUpdatingFromRoute.value = false
      }
    } else {
      backToProjectsWithExtras()
    }
  }
) 

onUnmounted(() => {
  // 停止所有 watch
  stopWatchProjectId()
  // 清理事件监听器
  document.removeEventListener('click', handleClickOutside)
})

</script>

<style scoped>
.analysis-workflow-container {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr) clamp(360px, 28vw, 440px);
  grid-template-rows: 1fr;
  gap: var(--spacing-lg);
  padding: var(--spacing-lg);
  background: var(--bg-secondary);
  width: 100%;
  height: 100%;
  position: relative;
  transition: grid-template-columns 0.3s ease;
  overflow: hidden;
}

.analysis-workflow-container.left-panel-collapsed {
  grid-template-columns: 0 minmax(0, 1fr) clamp(440px, 35vw, 600px);
  gap: 0 var(--spacing-lg);
}

/* 无Agent面板时的两栏布局 */
.analysis-workflow-container.no-agent-panel {
  grid-template-columns: 280px minmax(0, 1fr);
}

.analysis-workflow-container.no-agent-panel.left-panel-collapsed {
  grid-template-columns: 0 minmax(0, 1fr);
}

/* 左侧面板折叠按钮 */
.left-panel-toggle-btn {
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  z-index: 100;
  width: 32px;
  height: 48px;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-sm);
  transition: all 0.2s ease;
}

.left-panel-toggle-btn:hover {
  background: var(--bg-secondary);
  box-shadow: var(--shadow-md);
}

.toggle-icon {
  font-size: 12px;
  color: var(--text-secondary);
}

.left-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  transition: opacity 0.2s ease;
}

.center-panel {
  display: flex;
  flex-direction: column;
  background: var(--bg-primary);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--border-color);
  overflow: hidden;
  position: relative;
}

.home-button {
  position: absolute;
  top: 16px;
  right: 16px;
  z-index: 10;
  box-shadow: var(--shadow-sm);
}

.panel-content {
  flex: 1;
  width: 100%;
  height: 100%;
  overflow: hidden;
  position: relative;
}

.panel-status {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.panel-status-loading {
  padding: 40px;
  max-width: 600px;
  margin: 0 auto;
}

.content-area {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.right-panel {
  display: flex;
  flex-direction: column;
  background: var(--bg-primary);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--border-color);
  overflow: hidden;
}

/* 操作菜单样式 */
.action-menu {
  position: fixed;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  z-index: 10001;
  min-width: 120px;
  padding: var(--spacing-xs) 0;
  animation: fadeIn 0.15s ease;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(-4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.action-menu-item {
  padding: var(--spacing-sm) var(--spacing-lg);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  font-size: 14px;
  font-weight: 400;
  line-height: 1.5715;
  color: rgba(0, 0, 0, 0.85);
  transition: all 0.2s ease;
}

.action-menu-item:hover {
  background: var(--bg-tertiary);
}

.action-menu-item-danger {
  color: #ff4d4f;
}

.action-menu-item-danger:hover {
  background: rgba(255, 77, 79, 0.1);
  color: #ff4d4f;
}

.action-menu-item .icon {
  font-size: 16px;
  width: 20px;
  text-align: center;
}
</style>
