<template>
  <div 
    class="analysis-workflow-container" 
    :class="{ 
      'left-panel-collapsed': isLeftPanelCollapsed,
      'right-panel-collapsed': isRightPanelCollapsed,
      'no-agent-panel': !isProjectSelected 
    }"
    :style="analysisContainerStyle"
  >
    <!-- 左侧面板折叠按钮 -->
    <button 
      class="left-panel-toggle-btn" 
      @click="toggleLeftPanel"
      :title="isLeftPanelCollapsed ? t('analysis.expandLeftPanel') : t('analysis.collapseLeftPanel')"
    >
      <span class="toggle-icon">{{ isLeftPanelCollapsed ? '▶' : '◀' }}</span>
    </button>
    
    <!-- 左侧：项目列表或文件列表 -->
    <div class="left-panel" v-show="!isLeftPanelCollapsed">
      <ProjectListPanel
        v-if="!isProjectSelected"
        :project-list="projectList"
        :current-project-id="previewProjectId"
        @select-project="handleSelectProject"
        @delete-project="handleDeleteProjectClick"
      />
      <FileListPanel
        v-else
        :files="filteredFileDataList"
        :current-file-id="currentDataId"
        @add-data="showAddDataDialog = true"
        @back-to-projects="handleBackToProjects"
        @select-file="handleSelectFile"
        @toggle-action-menu="handleToggleActionMenu"
      />
    </div>
    
    <!-- 中间：分析内容区域 -->
    <div class="center-panel">
      <div class="panel-content">
        <!-- 加载状态 -->
        <div v-if="isLoading" class="panel-status panel-status-loading">
          <el-skeleton :rows="4" animated />
        </div>
        
        <!-- 错误状态 -->
        <div v-else-if="loadError" class="panel-status panel-status-error">
          <el-alert :title="loadError" type="error" show-icon :closable="false" />
        </div>
        
        <!-- 空状态 -->
        <div v-else-if="!hasDagData && !activeComponent" class="panel-status panel-status-empty">
          <el-empty :description="t('app.noAnalysisData')" />
        </div>
        
        <!-- 内容区域 -->
        <div v-else class="content-area">
          <!-- 动态组件：显示可视化组件或 DAG -->
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
            @file-deleted="handleFileDeleted"
            @refresh-dag="handleRefreshDag"
          />
        </div>
      </div>
    </div>
    
    <!-- 右侧：Agent 对话区（仅在选择项目后显示） -->
    <div class="right-panel" v-if="isProjectSelected" v-show="!isRightPanelCollapsed">
      <div
        class="right-panel-resize-handle"
        :class="{ 'is-resizing': isResizingRightPanel }"
        @mousedown.prevent="onRightResizeMouseDown"
      ></div>
      <ProjectAgentPane
        ref="projectAgentPaneRef"
        :project-id="currentProjectId"
        :project-name="currentProject?.name || null"
        @dag-refresh-files="handleRefreshDagOnce"
      />
    </div>

    <!-- 右侧面板折叠按钮 -->
    <button 
      v-if="isProjectSelected"
      class="right-panel-toggle-btn" 
      @click="toggleRightPanel"
      :title="isRightPanelCollapsed ? t('analysis.expandRightPanel') : t('analysis.collapseRightPanel')"
    >
      <span class="toggle-icon">{{ isRightPanelCollapsed ? '◀' : '▶' }}</span>
    </button>

    <!-- 对话框组件 -->
    <UploadFileDialog
      v-model="showAddDataDialog"
      ref="uploadDialogRef"
      @upload="handleUpload"
    />

    <EditFileDialog
      v-model="showEditDialog"
      ref="editDialogRef"
      :file-info="editTargetFileInfo"
      :file-name="editTarget?.name"
      @save="handleUpdateFile"
    />

    <DeleteFileDialog
      v-model="showDeleteDialog"
      ref="deleteDialogRef"
      :file-name="deleteTarget?.name"
      @confirm="handleDeleteFile"
    />

    <DeleteProjectDialog
      v-model="showDeleteProjectDialog"
      ref="deleteProjectDialogRef"
      :project-name="deleteProjectTarget?.name"
      @confirm="handleDeleteProject"
    />

    <!-- 文件操作菜单 -->
    <div 
      v-if="activeActionMenuId && actionMenuPosition" 
      class="action-menu" 
      :style="actionMenuStyle"
      @click.stop
    >
      <div class="action-menu-item" @click="handleEditFile">
        <span class="icon">✏️</span> {{ t('common.edit') }}
      </div>
      <div class="action-menu-item action-menu-item-danger" @click="handleDeleteFileClick">
        <span class="icon">🗑️</span> {{ t('common.delete') }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, provide } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElAlert, ElEmpty, ElSkeleton } from 'element-plus'

// 组件
import DAGVisualization from './analysis/DAGVisualization.vue'
import ProjectAgentPane from './analysis/ProjectAgentPane.vue'
import ProjectListPanel from './analysis/ProjectListPanel.vue'
import FileListPanel from './analysis/FileListPanel.vue'
import UploadFileDialog from './analysis/UploadFileDialog.vue'
import EditFileDialog from './analysis/EditFileDialog.vue'
import DeleteFileDialog from './analysis/DeleteFileDialog.vue'
import DeleteProjectDialog from './analysis/DeleteProjectDialog.vue'

// API
import { uploadFile, updateFileInfo, deleteFile, type FileInfo } from '../api/file'
import { deleteProject, type Project } from '../api/project'

// Composables
import { useProjectManagement } from '../composables/useProjectManagement'
import { useAnalysisState } from '../composables/useAnalysisState'
import { useVisualizationRouter } from '../composables/useVisualizationRouter'
import { useFileTypes } from '../composables/useFileTypes'

// Utils
import { notifyError, notifySuccess } from '../utils/notify'
import { FALLBACK_FILE_TYPE_ID, getConfiguredFileTypeId } from '../constants/fileTypes'

const router = useRouter()
const route = useRoute()
const { t } = useI18n()

// ==================== 状态管理 ====================
const { fileTypeMap: globalFileTypeMap, ensureLoaded: ensureGlobalFileTypes } = useFileTypes()

// 分析状态
const {
  dagNodes,
  dagEdges,
  dagFiles,
  isLoading,
  loadError,
  hasDagData,
  fileDataList,
  filteredFileDataList,
  filesDict,
  currentDataId,
  currentFileId,
  updateDagData,
  resetDagState,
  setLoadingState,
  removeFile
} = useAnalysisState()

// 可视化路由
const {
  activeComponent,
  currentFileId: vizCurrentFileId,
  navigateToVisualization,
  navigateToDAG,
  getVisualizationComponentId
} = useVisualizationRouter()

// 同步 currentFileId
watch(vizCurrentFileId, (newVal) => {
  currentFileId.value = newVal
})

// ==================== 布局与面板尺寸 ====================
const isLeftPanelCollapsed = ref(false)
const isRightPanelCollapsed = ref(false)

const RIGHT_PANEL_MIN_WIDTH = 320
const RIGHT_PANEL_MAX_WIDTH = 640
const DEFAULT_RIGHT_PANEL_WIDTH = 420

const rightPanelWidth = ref<number>(DEFAULT_RIGHT_PANEL_WIDTH)
const isResizingRightPanel = ref(false)
let resizeStartX = 0
let resizeStartWidth = 0

const analysisContainerStyle = computed(() => {
  if (!isProjectSelected.value) {
    return {}
  }

  if (isRightPanelCollapsed.value) {
    return {
      gridTemplateColumns: isLeftPanelCollapsed.value
        ? `0 minmax(0, 1fr) 0`
        : `280px minmax(0, 1fr) 0`
    }
  }

  const rightWidth = `${rightPanelWidth.value}px`
  return {
    gridTemplateColumns: isLeftPanelCollapsed.value
      ? `0 minmax(0, 1fr) ${rightWidth}`
      : `280px minmax(0, 1fr) ${rightWidth}`
  }
})

function toggleLeftPanel() {
  isLeftPanelCollapsed.value = !isLeftPanelCollapsed.value
  localStorage.setItem('analysisLeftPanelCollapsed', String(isLeftPanelCollapsed.value))
}

function toggleRightPanel() {
  isRightPanelCollapsed.value = !isRightPanelCollapsed.value
  localStorage.setItem('analysisRightPanelCollapsed', String(isRightPanelCollapsed.value))
}

function onRightResizeMouseMove(event: MouseEvent) {
  if (!isResizingRightPanel.value) return
  const deltaX = resizeStartX - event.clientX
  let nextWidth = resizeStartWidth + deltaX
  if (nextWidth < RIGHT_PANEL_MIN_WIDTH) nextWidth = RIGHT_PANEL_MIN_WIDTH
  if (nextWidth > RIGHT_PANEL_MAX_WIDTH) nextWidth = RIGHT_PANEL_MAX_WIDTH
  rightPanelWidth.value = nextWidth
}

function stopRightResize() {
  if (!isResizingRightPanel.value) return
  isResizingRightPanel.value = false
  document.body.style.cursor = ''
  window.removeEventListener('mousemove', onRightResizeMouseMove)
  window.removeEventListener('mouseup', stopRightResize)
  localStorage.setItem('analysisRightPanelWidth', String(rightPanelWidth.value))
}

function onRightResizeMouseDown(event: MouseEvent) {
  if (!isProjectSelected.value || isRightPanelCollapsed.value) return
  isResizingRightPanel.value = true
  resizeStartX = event.clientX
  resizeStartWidth = rightPanelWidth.value
  document.body.style.cursor = 'col-resize'
  window.addEventListener('mousemove', onRightResizeMouseMove)
  window.addEventListener('mouseup', stopRightResize)
}

// ==================== DAG 刷新（Agent 对话期间） ====================
function handleRefreshDagOnce() {
  void handleRefreshDag(false)
}

// ==================== 项目管理 ====================
const isProjectSelected = ref(false)
const previewProjectId = ref<string | null>(null)
const isUpdatingFromRoute = ref(false)

// 初始化项目管理
const projectManagement = useProjectManagement({
  onAgentMessage: (_role, message) => {
    notifySuccess({ message })
  },
  onDagDataUpdate: (data) => {
    updateDagData(data)
  },
  onDagLoadingChange: (loading, error) => {
    setLoadingState(loading, error)
  }
})

const {
  projectList,
  currentProjectId,
  currentProject,
  loadProjectList,
  selectProject: selectProjectFromComposable,
  backToProjects: backToProjectsFromComposable,
  loadProjectDAGData: loadProjectDAGDataFromComposable
} = projectManagement

// ==================== 项目操作 ====================
async function handleSelectProject(projectId: string) {
  if (!projectId) return
  
  isProjectSelected.value = true
  previewProjectId.value = null
  
  // 选择项目时自动展开右侧 Agent 面板
  isRightPanelCollapsed.value = false
  localStorage.setItem('analysisRightPanelCollapsed', 'false')
  
  const shouldUpdateRoute = !isUpdatingFromRoute.value
  
  if (currentProjectId.value === projectId && !shouldUpdateRoute) {
    try {
      await loadProjectDAGDataFromComposable(projectId)
    } catch {}
    return
  }
  
  currentDataId.value = null
  navigateToDAG()
  
  try {
    await selectProjectFromComposable(projectId, !shouldUpdateRoute)
    if (currentProjectId.value) {
      await loadProjectDAGDataFromComposable(currentProjectId.value)
    }
  } catch (error) {
    console.error('选择项目失败:', error)
  }
}

async function handleBackToProjects() {
  if (isUpdatingFromRoute.value) return
  
  isUpdatingFromRoute.value = true
  currentDataId.value = null
  isProjectSelected.value = false
  navigateToDAG()
  resetDagState()
  
  backToProjectsFromComposable()
  
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
    isUpdatingFromRoute.value = false
  }, 120)
}

// ==================== 文件操作 ====================
function handleSelectFile(dataId: string) {
  activeActionMenuId.value = null
  actionMenuPosition.value = null

  if (!currentProjectId.value) {
    notifyError({ message: t('app.selectProjectFirst') })
    return
  }

  const data = fileDataList.value.find(d => d.id === dataId)
  if (!data) return

  // 点击左侧文件后，自动折叠右侧 Agent 对话框以腾出更大空间给可视化
  isRightPanelCollapsed.value = true
  localStorage.setItem('analysisRightPanelCollapsed', 'true')

  const componentId = getVisualizationComponentId(data.name, data.fileTypeId)

  // 点击同一个文件且已经在可视化视图时，返回 DAG
  if (dataId === currentDataId.value && activeComponent.value) {
    navigateToDAG()
    currentDataId.value = null
    return
  }

  currentDataId.value = data.id
  navigateToVisualization(componentId, data.fileId || '')

  router.push({
    path: '/analysis',
    query: { projectId: currentProjectId.value }
  })

  notifySuccess({ message: t('app.dataSwitched', { name: data.name }) })
}

async function handleFileDeleted(fileId: string) {
  if (!fileId) return

  removeFile(fileId)
  
  if (currentProjectId.value) {
    try {
      await loadProjectDAGDataFromComposable(currentProjectId.value)
    } catch (error) {
      console.error('刷新项目数据失败:', error)
    }
  }
}

async function handleRefreshDag(silent = false) {
  if (currentProjectId.value) {
    try {
      await loadProjectDAGDataFromComposable(currentProjectId.value)
    } catch (error) {
      console.error('刷新DAG数据失败:', error)
    }
  }
}

// ==================== 文件上传 ====================
interface UploadPayload {
  file: File
  name: string
  description: string
  fileTypeId: string
}

const showAddDataDialog = ref(false)
const uploadDialogRef = ref<InstanceType<typeof UploadFileDialog> | null>(null)
const defaultFileTypeId = getConfiguredFileTypeId() ?? FALLBACK_FILE_TYPE_ID

async function handleUpload(payload: UploadPayload) {
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
    
    const result = await uploadFile({
      file,
      fileTypeId,
      projectId: currentProjectId.value || undefined,
      onProgress: (progress) => {
        dialog.setStatus(t('app.uploadingProgress', { progress }), false)
      }
    })
    
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
      } catch (error) {
        console.warn('更新文件信息失败，但文件已上传:', error)
      }
    }
    
    if (currentProjectId.value) {
      try {
        await loadProjectDAGDataFromComposable(currentProjectId.value)
      } catch (error) {
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
    
    notifySuccess({ message: successMessage })
    dialog.setStatus(t('app.uploadSuccessMessage'), false)
    dialog.close()
  } catch (err) {
    console.error('上传失败:', err)
    const errorMessage = err instanceof Error ? err.message : t('app.unknownError')
    dialog.setStatus(t('app.uploadFailed', { error: errorMessage }), true)
  } finally {
    dialog.setUploading(false)
  }
}

// ==================== 文件编辑/删除 ====================
interface DataItem {
  id: string
  name: string
  uploadTime: string
  fileId?: string | null
  description?: string
  fileTypeId?: string | null
  fileInfo?: FileInfo
}

const showEditDialog = ref(false)
const editDialogRef = ref<InstanceType<typeof EditFileDialog> | null>(null)
const editTarget = ref<DataItem | null>(null)
const editTargetFileInfo = computed<FileInfo | null>(() => {
  if (!editTarget.value) return null
  const targetData = editTarget.value as any
  return (targetData.fileInfo as FileInfo | undefined) || null
})

const showDeleteDialog = ref(false)
const deleteDialogRef = ref<InstanceType<typeof DeleteFileDialog> | null>(null)
const deleteTarget = ref<DataItem | null>(null)

function showEditDialogHandler(fileIdOrData: string | DataItem | any) {
  if (typeof fileIdOrData === 'string') {
    const fileId = fileIdOrData
    const fileInfo = filesDict.value[fileId]
    if (!fileInfo) {
      console.warn(`文件信息未找到: ${fileId}`)
      notifyError({ message: t('app.fileIdMissing') })
      return
    }
    
    const fileName = fileInfo.filename || t('analysis.defaultFileName', { id: fileId })
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

    if (currentProjectId.value) {
      try {
        await loadProjectDAGDataFromComposable(currentProjectId.value)
      } catch (error) {
        console.error('刷新项目数据失败:', error)
      }
    }

    if (currentDataId.value === editTarget.value.id) {
      handleSelectFile(editTarget.value.id)
    }
    
    notifySuccess({ message: t('app.fileUpdated', { name: updateParams.name || originalName }) })
    dialog.close()
    editTarget.value = null
  } catch (error) {
    console.error('更新文件信息失败:', error)
    const errorMessage = error instanceof Error ? error.message : t('app.unknownError')
    notifyError({ 
      message: t('app.updateFailed', { error: errorMessage }) 
    })
  } finally {
    dialog.setUpdating(false)
  }
}

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
        handleSelectFile(fileDataList.value[0].id)
      } else {
        currentDataId.value = null
        navigateToDAG()
      }
    }
    
    notifySuccess({ message: t('app.fileDeleted', { name: deleteTarget.value.name }) })
    dialog.close()
    deleteTarget.value = null
  } catch (error) {
    console.error('删除文件失败:', error)
    const errorMessage = error instanceof Error ? error.message : t('app.unknownError')
    notifyError({
      message: t('app.deleteFailed', { error: errorMessage })
    })
  } finally {
    dialog.setDeleting(false)
  }
}

// ==================== 项目删除 ====================
const showDeleteProjectDialog = ref(false)
const deleteProjectDialogRef = ref<InstanceType<typeof DeleteProjectDialog> | null>(null)
const deleteProjectTarget = ref<Project | null>(null)

function handleDeleteProjectClick(project: Project) {
  deleteProjectTarget.value = project
  showDeleteProjectDialog.value = true
}

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
    
    if (currentProjectId.value === projectId) {
      handleBackToProjects()
    }
    
    await loadProjectList()
    
    notifySuccess({
      message: t('project.actions.deleteSuccess', {
        name: deleteProjectTarget.value.name
      })
    })
    
    dialog.close()
    deleteProjectTarget.value = null
    showDeleteProjectDialog.value = false
  } catch (error) {
    console.error('删除项目失败:', error)
    const errorMessage = error instanceof Error ? error.message : t('app.unknownError')
    notifyError({
      message: t('project.actions.deleteFailed', { error: errorMessage })
    })
  } finally {
    dialog.setDeleting(false)
  }
}

// ==================== 操作菜单 ====================
const activeActionMenuId = ref<string | null>(null)
const actionMenuPosition = ref<{ top: number; left: number } | null>(null)

const actionMenuStyle = computed(() => {
  if (!actionMenuPosition.value) {
    return {}
  }
  return {
    top: `${actionMenuPosition.value.top}px`,
    left: `${actionMenuPosition.value.left}px`
  }
})

function handleToggleActionMenu(event: MouseEvent, dataId: string) {
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

function handleEditFile() {
  const fileData = fileDataList.value.find(f => f.id === activeActionMenuId.value)
  if (fileData && fileData.fileId) {
    showEditDialogHandler(fileData.fileId)
  }
  activeActionMenuId.value = null
}

function handleDeleteFileClick() {
  const fileData = fileDataList.value.find(f => f.id === activeActionMenuId.value)
  if (fileData) {
    deleteTarget.value = fileData
    showDeleteDialog.value = true
  }
  activeActionMenuId.value = null
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

// ==================== Provide/Inject ====================
const projectAgentPaneRef = ref<InstanceType<typeof ProjectAgentPane> | null>(null)

provide('triggerAnalysisComponent', (componentId: string, fileId: string) => {
  navigateToVisualization(componentId as any, fileId)
})
provide('showEditFileDialog', showEditDialogHandler)
provide('addFileToContext', (fileId: string, fileName: string) => {
  if (projectAgentPaneRef.value?.addFileToContext) {
    projectAgentPaneRef.value.addFileToContext(fileId, fileName)
  }
})

// ==================== 生命周期 ====================
onMounted(async () => {
  // 恢复左侧面板折叠状态
  const savedCollapsedState = localStorage.getItem('analysisLeftPanelCollapsed')
  if (savedCollapsedState === 'true') {
    isLeftPanelCollapsed.value = true
  }
  
  // 恢复右侧面板折叠状态
  const savedRightCollapsedState = localStorage.getItem('analysisRightPanelCollapsed')
  if (savedRightCollapsedState === 'true') {
    isRightPanelCollapsed.value = true
  }

   const savedRightPanelWidth = localStorage.getItem('analysisRightPanelWidth')
   if (savedRightPanelWidth) {
     const parsed = Number(savedRightPanelWidth)
     if (!Number.isNaN(parsed) && parsed >= RIGHT_PANEL_MIN_WIDTH && parsed <= RIGHT_PANEL_MAX_WIDTH) {
       rightPanelWidth.value = parsed
     }
   }
  
  // 预加载文件类型
  ensureGlobalFileTypes().catch(() => {})

  // 加载项目列表
  await loadProjectList()
  
  // 检查路由参数
  const projectId = route.query.projectId as string | undefined
  
  if (projectId) {
    isUpdatingFromRoute.value = true
    try {
      await handleSelectProject(projectId)
    } finally {
      isUpdatingFromRoute.value = false
    }
  } else if (projectList.value && projectList.value.length > 0) {
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
})

// 监听路由变化
const stopWatchProjectId = watch(
  () => ({
    projectId: route.query.projectId as string | undefined,
    path: route.path,
    name: route.name
  }),
  async (to, from) => {
    const isAnalysisRoute = to.path === '/analysis' || to.name === 'Analysis'

    if (!isAnalysisRoute) return
    if (isUpdatingFromRoute.value) return
    if (to.projectId === from?.projectId) return
    
    if (to.projectId) {
      isUpdatingFromRoute.value = true
      try {
        await handleSelectProject(to.projectId)
      } finally {
        isUpdatingFromRoute.value = false
      }
    } else {
      handleBackToProjects()
    }
  }
)

onUnmounted(() => {
  stopWatchProjectId()
  document.removeEventListener('click', handleClickOutside)
  stopRightResize()
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
  grid-template-columns: 0 minmax(0, 1fr) clamp(360px, 28vw, 440px);
  gap: 0 var(--spacing-lg);
}

.analysis-workflow-container.right-panel-collapsed {
  grid-template-columns: 280px minmax(0, 1fr) 0;
  gap: var(--spacing-lg) 0;
}

.analysis-workflow-container.left-panel-collapsed.right-panel-collapsed {
  grid-template-columns: 0 minmax(0, 1fr) 0;
  gap: 0;
}

.analysis-workflow-container.no-agent-panel {
  grid-template-columns: 280px minmax(0, 1fr);
}

.analysis-workflow-container.no-agent-panel.left-panel-collapsed {
  grid-template-columns: 0 minmax(0, 1fr);
}

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

.right-panel-toggle-btn {
  position: absolute;
  right: 12px;
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

.right-panel-toggle-btn:hover {
  background: var(--bg-secondary);
  box-shadow: var(--shadow-md);
}

.left-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  transition: opacity 0.2s ease;
}

.right-panel {
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
  position: relative;
}

.right-panel-resize-handle {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 8px;
  cursor: col-resize;
  z-index: 10;
  background: transparent;
}

.right-panel-resize-handle:hover,
.right-panel-resize-handle.is-resizing {
  background: rgba(15, 23, 42, 0.06);
}

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
