<template>
  <div class="dag-container" ref="dagContainer">
    <div class="dag-header">
      <div class="dag-header-left">
        <h3>{{ t('analysis.title') }}</h3>
        <p class="dag-subtitle">{{ t('analysis.subtitle') }}</p>
      </div>
    </div>
    <div id="dag-canvas" ref="dagCanvas"></div>

    <!-- 节点操作菜单 -->
    <Teleport to="body">
      <div 
        v-if="showNodeActionMenu"
        class="node-action-menu"
        :style="nodeActionMenuStyle"
        @click.stop
      >
        <div class="node-action-menu-header">
          <div class="node-action-menu-title">
            <span class="menu-icon">{{ getCurrentFileInfo()?.icon || '📄' }}</span>
            <span class="menu-file-name">{{ getCurrentFileInfo()?.filename || t('analysis.nodeMenu.unknownFile') }}</span>
          </div>
          <button class="menu-close-btn" @click="closeNodeActionMenu">×</button>
        </div>
        <div class="node-action-menu-divider"></div>
        <div class="node-action-menu-body">
          <!-- 文件操作栏 -->
          <div v-if="actionGroups.fileOperations.length > 0" class="menu-section">
            <div class="menu-section-title">{{ t('analysis.nodeMenu.fileOperations') }}</div>
            <div 
              v-for="option in actionGroups.fileOperations"
              :key="option.id"
              class="node-action-menu-item"
              :class="{ 
                'menu-item-danger': option.danger,
                'menu-item-disabled': option.disabled && option.disabled(getCurrentFileInfo())
              }"
              @click="handleNodeAction(option)"
            >
              <span class="menu-item-icon">{{ option.icon || '○' }}</span>
              <span class="menu-item-label">{{ option.label }}</span>
            </div>
          </div>
          
          <!-- 文件分析栏 -->
          <div v-if="actionGroups.fileAnalysis.length > 0" class="menu-section">
            <div class="menu-section-title">{{ t('analysis.nodeMenu.fileAnalysis') }}</div>
            <div 
              v-for="option in actionGroups.fileAnalysis"
              :key="option.id"
              class="node-action-menu-item"
              :class="{ 
                'menu-item-danger': option.danger,
                'menu-item-disabled': option.disabled && option.disabled(getCurrentFileInfo())
              }"
              @click="handleNodeAction(option)"
            >
              <span class="menu-item-icon">{{ option.icon || '○' }}</span>
              <span class="menu-item-label">{{ option.label }}</span>
            </div>
          </div>
          
          <!-- 进一步分析栏 -->
          <div v-if="showAnalysisSection" class="menu-section">
            <div class="menu-section-title">{{ t('analysis.nodeMenu.furtherAnalysis') }}</div>
            <div 
              v-for="option in actionGroups.analysisOperations"
              :key="option.id"
              class="node-action-menu-item"
              :class="{ 
                'menu-item-danger': option.danger,
                'menu-item-disabled': option.disabled && option.disabled(getCurrentFileInfo())
              }"
              @click="handleNodeAction(option)"
            >
              <span class="menu-item-icon">{{ option.icon || '○' }}</span>
              <span class="menu-item-label">{{ option.label }}</span>
            </div>
            <div v-if="serviceMenuNotice" class="node-action-menu-hint">
              {{ serviceMenuNotice }}
            </div>
          </div>
        </div>
      </div>
    </Teleport>
    
    <!-- Service执行对话框 -->
    <Teleport to="body">
      <div 
        v-if="showServiceExecuteDialog"
        class="service-execute-dialog-overlay"
        @click.self="closeServiceExecuteDialog"
      >
        <div class="service-execute-dialog">
          <div class="dialog-header">
            <h3>{{ t('service.execute.title') }}</h3>
            <button class="dialog-close-btn" @click="closeServiceExecuteDialog">×</button>
          </div>
          <div class="dialog-content">
            <ServiceExecute 
              v-if="selectedService"
              :service="selectedService"
              :initial-file-id="currentFileId"
              :file-info="currentFileInfo"
              :project-id="typeof route.query.projectId === 'string' ? route.query.projectId : null"
              @executed="handleServiceExecuted"
            />
          </div>
        </div>
      </div>
    </Teleport>
    
    <!-- 文件预览对话框 -->
    <FilePreviewDialog
      v-if="showFilePreviewDialog && previewFileInfo"
      :file-id="previewFileInfo.fileId"
      :file-name="previewFileInfo.fileName"
      :file-type="previewFileInfo.fileType"
      :visible="showFilePreviewDialog"
      @close="closeFilePreviewDialog"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, computed, inject, provide, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { Graph } from '@antv/g6'
import { ElMessageBox } from 'element-plus'
import { getNodeActionOptions, type NodeActionGroups } from '../../types/nodeActions'
import { deleteFile, deleteFileChildren } from '../../api/file'
import FilePreviewDialog from '../file-preview/FilePreviewDialog.vue'
import ServiceExecute from '../service/ServiceExecute.vue'
import {
  fetchProjectServices,
  getCachedProjectServices,
  type ProjectService
} from '../../stores/servicesCache'
import { notifyError, notifySuccess } from '../../utils/notify'
import { detectFileType, type FileCategory } from '../../utils/fileType'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

// ==================== Props & Emits ====================
const props = defineProps<{
  nodes: any[]
  edges: any[]
  files: any[]
}>()

const emit = defineEmits<{
  'file-deleted': [fileId: string]
  'refresh-dag': []
}>()

// ==================== Inject ====================
const triggerAnalysisComponent = inject<(componentId: string, fileId: string) => void>('triggerAnalysisComponent')
const showEditFileDialog = inject<(dataItem: any) => void>('showEditFileDialog')
const addFileToContext = inject<(fileId: string, fileName: string) => void>('addFileToContext')

// ==================== State ====================
const dagContainer = ref<HTMLElement | null>(null)
const dagCanvas = ref<HTMLElement | null>(null)
let graph: InstanceType<typeof Graph> | null = null
let tooltip: HTMLElement | null = null

const showServiceExecuteDialog = ref(false)
const showFilePreviewDialog = ref(false)
const selectedService = ref<any>(null)
const currentFileId = ref<string | string[] | null>(null)

const showNodeActionMenu = ref(false)
const currentNodeInfo = ref<string | null>(null)
const nodeActionMenuPosition = ref<{ x: number; y: number } | null>(null)
const actionGroups = ref<NodeActionGroups>({ fileOperations: [], fileAnalysis: [], analysisOperations: [] })

function localizeActionGroups(groups: NodeActionGroups): NodeActionGroups {
  const localizeLabel = (optionId: string, fallback: string) => {
    switch (optionId) {
      case 'preview-file':
        return t('analysis.nodeMenu.previewFile')
      case 'download':
        return t('analysis.nodeMenu.downloadFile')
      case 'edit-file':
        return t('analysis.nodeMenu.editFile')
      case 'add-to-context':
        return t('analysis.nodeMenu.addToContext')
      case 'delete-file':
        return t('analysis.nodeMenu.deleteFile')
      case 'delete-file-children':
        return t('analysis.nodeMenu.deleteFileChildren')
      default:
        return fallback
    }
  }

  const mapGroup = (items: NodeActionGroups['fileOperations']) =>
    items.map((option) => ({
      ...option,
      label: localizeLabel(option.id, option.label)
    }))

  return {
    fileOperations: mapGroup(groups.fileOperations),
    fileAnalysis: mapGroup(groups.fileAnalysis),
    analysisOperations: mapGroup(groups.analysisOperations)
  }
}

const previewFileInfo = ref<{
  fileId: string
  fileName: string
  fileType: FileCategory
} | null>(null)

// Service相关
const services = ref<ProjectService[]>([])
const loadingServices = ref(false)
const serviceLoadError = ref('')
const servicesAbort = ref<AbortController | null>(null)

// ==================== Computed ====================
const propNodes = computed(() => props.nodes || [])
const propEdges = computed(() => props.edges || [])

const filesDict = computed(() => {
  const dict: Record<string, any> = {}
  const files = Array.isArray(props.files) ? props.files : []
  files.forEach(file => {
    if (!file) return
    const fileId = file.file_id || file.id
    if (fileId) {
      dict[fileId] = file
    }
  })
  return dict
})

const currentFileInfo = computed(() => {
  if (!currentFileId.value) return null
  const fileId = Array.isArray(currentFileId.value) ? currentFileId.value[0] : currentFileId.value
  if (!fileId) return null
  return filesDict.value[fileId] || null
})

const serviceMenuNotice = computed(() => {
  if (loadingServices.value) return t('app.serviceMenuLoading')
  if (serviceLoadError.value) return serviceLoadError.value
  if (services.value.length === 0) return t('app.serviceMenuEmpty')
  return ''
})

const showAnalysisSection = computed(() =>
  actionGroups.value.analysisOperations.length > 0 || Boolean(serviceMenuNotice.value)
)

// ==================== Graph Functions ====================
const getNodeColor = (): string => '#52c41a'

const getNodeType = (filename: string | undefined): 'circle' | 'rect' => {
  if (!filename) return 'circle'
  return filename.toLowerCase().endsWith('.txt') ? 'rect' : 'circle'
}

const getEdgeColor = (): string => '#bfbfbf'

function darkenColor(color: string, amount: number): string {
  const num = parseInt(color.replace('#', ''), 16)
  const r = Math.max(0, (num >> 16) - Math.round(255 * amount))
  const g = Math.max(0, ((num >> 8) & 0x00FF) - Math.round(255 * amount))
  const b = Math.max(0, (num & 0x0000FF) - Math.round(255 * amount))
  return `#${((r << 16) | (g << 8) | b).toString(16).padStart(6, '0')}`
}

function lightenColor(color: string, amount: number): string {
  const num = parseInt(color.replace('#', ''), 16)
  const r = Math.min(255, (num >> 16) + Math.round(255 * amount))
  const g = Math.min(255, ((num >> 8) & 0x00FF) + Math.round(255 * amount))
  const b = Math.min(255, (num & 0x0000FF) + Math.round(255 * amount))
  return `#${((r << 16) | (g << 8) | b).toString(16).padStart(6, '0')}`
}

function initGraph() {
  if (!dagCanvas.value) {
    console.warn(t('analysis.messages.dagCanvasNotReady'))
    return
  }
  
  const nodes = propNodes.value.map(fileNode => {
    const nodeColor = getNodeColor()
    return {
      id: fileNode.file_id,
      filename: fileNode.filename,
      file_type: fileNode.file_type,
      color: nodeColor,
      style: {
        fill: nodeColor,
        stroke: darkenColor(nodeColor, 0.2),
        lineWidth: 2,
        cursor: 'pointer'
      }
    }
  })
  
  const nodeIds = new Set(nodes.map(n => n.id))
  
  const edges = propEdges.value
    .filter(edge => nodeIds.has(edge.from) && nodeIds.has(edge.to))
    .map(edge => {
      const edgeColor = getEdgeColor()
      return {
        source: edge.from,
        target: edge.to,
        color: edgeColor,
        style: {
          stroke: edgeColor,
          lineWidth: 2,
          endArrow: true,
          endArrowType: 'triangle',
          endArrowSize: 8
        }
      }
    })
  
  const data = { nodes, edges }
  
  if (graph) {
    try {
      graph.destroy()
    } catch (e) {
      console.warn(t('analysis.messages.destroyGraphInstanceError'), e)
    }
  }
  
  try {
    graph = new Graph({
      container: dagCanvas.value,
      autoFit: 'view',
      data,
      behaviors: ['zoom-canvas', 'drag-canvas'],
      layout: {
        type: 'dagre',
        rankdir: 'LR',
        nodesep: 100,
        ranksep: 150
      },
      node: {
        type: (d: any) => getNodeType(d.filename),
        size: (d: any) => {
          const nodeType = getNodeType(d.filename)
          const baseSize = d.size || 80
          return nodeType === 'rect' ? [baseSize, baseSize] : baseSize
        },
        style: (d: any) => {
          const nodeColor = d.color || d.style?.fill || '#91d5ff'
          const nodeType = getNodeType(d.filename)
          return {
            fill: nodeColor as string,
            stroke: darkenColor(nodeColor, 0.2),
            lineWidth: 2,
            cursor: 'pointer' as const,
            ...(nodeType === 'rect' ? { radius: 4 } : {}),
            labelText: d.filename || d.id,
            labelFill: '#2c3e50',
            labelFontSize: 12,
            labelFontWeight: 500,
            labelPlacement: 'bottom' as const,
            labelOffsetY: 20,
            labelBackground: true,
            labelBackgroundFill: 'rgba(255, 255, 255, 0.95)',
            labelBackgroundPadding: [4, 8],
            labelBackgroundRadius: 4,
            labelBackgroundStroke: 'rgba(200, 200, 210, 0.3)',
            labelBackgroundLineWidth: 1
          }
        },
        animation: false
      },
      edge: {
        type: 'polyline',
        style: (d: any) => {
          const edgeColor = d.color || '#bfbfbf'
          return {
            stroke: edgeColor as string,
            lineWidth: 2,
            endArrow: true,
            endArrowType: 'triangle' as const,
            endArrowSize: 8
          }
        },
        animation: false
      }
    })
    
    graph.render()
    bindEvents()
  } catch (error) {
    console.error(t('analysis.messages.createGraphInstanceFailed'), error)
    graph = null
  }
}

function updateGraph() {
  if (!graph || !dagCanvas.value) {
    initGraph()
    return
  }
  
  const nodes = propNodes.value.map(fileNode => {
    const nodeColor = getNodeColor()
    return {
      id: fileNode.file_id,
      filename: fileNode.filename,
      file_type: fileNode.file_type,
      color: nodeColor,
      style: {
        fill: nodeColor,
        stroke: darkenColor(nodeColor, 0.2),
        lineWidth: 2,
        cursor: 'pointer'
      }
    }
  })
  
  const nodeIds = new Set(nodes.map(n => n.id))
  
  const edges = propEdges.value
    .filter(edge => nodeIds.has(edge.from) && nodeIds.has(edge.to))
    .map(edge => {
      const edgeColor = getEdgeColor()
      return {
        source: edge.from,
        target: edge.to,
        color: edgeColor,
        style: {
          stroke: edgeColor,
          lineWidth: 2,
          endArrow: true,
          endArrowType: 'triangle',
          endArrowSize: 8
        }
      }
    })
  
  try {
    if (typeof graph.updateData === 'function') {
      graph.updateData({ nodes, edges })
      if (typeof graph.render === 'function') {
        graph.render()
      }
      if (typeof graph.layout === 'function') {
        graph.layout()
      }
    } else {
      graph.destroy()
      initGraph()
    }
  } catch (error) {
    console.error(t('analysis.messages.updateGraphDataFailed'), error)
    try {
      graph.destroy()
    } catch (e) {
      console.warn(t('analysis.messages.destroyGraphInstanceFailed'), e)
    }
    initGraph()
  }
}

function bindEvents() {
  if (!graph) return
  
  graph.off('node:click')
  graph.off('node:mouseenter')
  graph.off('node:mouseleave')
  
  graph.on('node:click', (e) => {
    const event = e.event || e.originalEvent || e.nativeEvent
    if (event) {
      event.stopPropagation()
    }
    
    const { target } = e
    if (!target) return
    
    const nodeData = graph.getNodeData(target.id)
    if (!nodeData) return
    
    const projectId = typeof route.query.projectId === 'string' ? route.query.projectId : ''
    if (!projectId) {
      router.push({ name: 'ProjectPage' })
      return
    }
    
    const nodeId = nodeData.id
    showNodeActionMenuForNode(event, nodeId)
  })
  
  graph.on('node:mouseenter', (e) => {
    const node = e.item
    if (!node) return
    
    const model = node.getModel()
    const baseColor = model.color || '#91d5ff'
    const hoveredColor = lightenColor(baseColor, 0.15)
    const nodeType = getNodeType(model.filename)
    
    try {
      graph.updateItem(node, {
        style: {
          fill: hoveredColor,
          stroke: darkenColor(baseColor, 0.3),
          lineWidth: 4
        },
        size: nodeType === 'rect' ? [95, 95] : 95
      })
    } catch (err) {
      console.warn(t('analysis.messages.updateNodeStyleFailed'), err)
    }
    
    showTooltip(node)
  })
  
  graph.on('node:mouseleave', (e) => {
    const node = e.item
    if (!node) return
    
    const model = node.getModel()
    const baseColor = model.color || '#91d5ff'
    const nodeType = getNodeType(model.filename)
    
    try {
      graph.updateItem(node, {
        style: {
          fill: baseColor,
          stroke: darkenColor(baseColor, 0.2),
          lineWidth: 2
        },
        size: nodeType === 'rect' ? [80, 80] : 80
      })
    } catch (err) {
      console.warn(t('analysis.messages.restoreNodeStyleFailed'), err)
    }
    
    hideTooltip()
  })
}

function showTooltip(item: any) {
  if (!item) return
  
  const model = item.getModel()
  const canvasContainer = dagCanvas.value
  if (!canvasContainer) return
  
  if (!tooltip) {
    tooltip = document.createElement('div')
    tooltip.className = 'dag-tooltip'
    document.body.appendChild(tooltip)
  }
  
  const fileId = model.id
  const fileInfo = filesDict.value[fileId]
  if (!fileInfo) {
    hideTooltip()
    return
  }
  
  const filename = fileInfo.filename || fileInfo.file_name || fileInfo.fileName || fileId
  const fileType = detectFileType(filename)
  const fileTypeLabel = fileType === 'text' ? t('analysis.fileType.text') : t('analysis.fileType.unknown')
  
  const html = `
    <div class="tooltip-header">
      <div class="tooltip-title">📄 ${filename}</div>
      <div class="tooltip-type">${fileTypeLabel}</div>
    </div>
    <div class="tooltip-section">
      <div class="tooltip-row"><span>ID:</span><span>${fileId}</span></div>
    </div>
  `

  tooltip.innerHTML = html
  
  const containerRect = canvasContainer.getBoundingClientRect()
  const left = containerRect.left + 20
  const bottom = containerRect.bottom - 20
  
  tooltip.style.left = `${left}px`
  tooltip.style.bottom = `${window.innerHeight - bottom}px`
  tooltip.style.top = 'auto'
  tooltip.style.display = 'block'
}

function hideTooltip() {
  if (tooltip) {
    tooltip.style.display = 'none'
  }
}

function handleResize() {
  if (!graph || !dagCanvas.value) return
  
  try {
    const width = dagCanvas.value.clientWidth
    const height = dagCanvas.value.clientHeight
    if (typeof graph.resize === 'function') {
      graph.resize(width, height)
    }
  } catch (error) {
    console.warn(t('analysis.messages.resizeGraphFailed'), error)
  }
}

// ==================== Node Action Menu ====================
function getCurrentFileInfo() {
  if (!currentNodeInfo.value) return null
  return filesDict.value[currentNodeInfo.value] || null
}

function updateActionGroupsForNode(fileId: string) {
  if (!fileId) {
    actionGroups.value = {
      fileOperations: [],
      fileAnalysis: [],
      analysisOperations: []
    }
    return
  }

  const fileInfo = filesDict.value[fileId]
  if (!fileInfo) {
    console.warn(t('analysis.messages.fileInfoNotFound', { fileId }))
    actionGroups.value = {
      fileOperations: [],
      fileAnalysis: [],
      analysisOperations: []
    }
    return
  }

  const handlers = {
    triggerAnalysisComponent,
    showEditFileDialog,
    deleteFileNode,
    deleteFileChildren: deleteFileChildrenNode,
    showServiceExecuteDialog: showServiceExecuteDialogHandler,
    showFilePreview: showFilePreviewHandler,
    addFileToContext
  }

  actionGroups.value = localizeActionGroups(getNodeActionOptions(fileInfo, handlers, services.value, t))
}

function refreshActionGroups() {
  if (showNodeActionMenu.value && currentNodeInfo.value) {
    updateActionGroupsForNode(currentNodeInfo.value)
  }
}

watch(services, () => {
  refreshActionGroups()
})

function showNodeActionMenuForNode(event: any, fileId: string) {
  if (!fileId) return
  
  const fileInfo = filesDict.value[fileId]
  if (!fileInfo) {
    console.warn(t('analysis.messages.fileInfoNotFound', { fileId }))
    return
  }
  
  currentNodeInfo.value = fileId
  updateActionGroupsForNode(fileId)
  
  let positionSet = false
  
  if (event && event.canvas && event.canvas.x !== undefined && event.canvas.y !== undefined) {
    const canvasRect = dagCanvas.value?.getBoundingClientRect()
    if (canvasRect) {
      nodeActionMenuPosition.value = {
        x: canvasRect.left + event.canvas.x,
        y: canvasRect.top + event.canvas.y
      }
      positionSet = true
    }
  } else if (event && event.client && event.client.x !== undefined && event.client.y !== undefined) {
    nodeActionMenuPosition.value = {
      x: event.client.x,
      y: event.client.y
    }
    positionSet = true
  } else if (event && event.canvasX !== undefined && event.canvasY !== undefined) {
    const canvasRect = dagCanvas.value?.getBoundingClientRect()
    if (canvasRect) {
      nodeActionMenuPosition.value = {
        x: canvasRect.left + event.canvasX,
        y: canvasRect.top + event.canvasY
      }
      positionSet = true
    }
  } else if (event && event.clientX !== undefined && event.clientY !== undefined) {
    nodeActionMenuPosition.value = {
      x: event.clientX,
      y: event.clientY
    }
    positionSet = true
  }
  
  if (!positionSet) {
    const canvasRect = dagCanvas.value?.getBoundingClientRect()
    if (canvasRect) {
      nodeActionMenuPosition.value = {
        x: canvasRect.left + canvasRect.width / 2,
        y: canvasRect.top + canvasRect.height / 2
      }
    } else {
      nodeActionMenuPosition.value = {
        x: 100,
        y: 100
      }
    }
  }
  
  showNodeActionMenu.value = true
  
  setTimeout(() => {
    document.addEventListener('click', handleClickOutside)
  }, 100)
}

function closeNodeActionMenu() {
  showNodeActionMenu.value = false
  currentNodeInfo.value = null
  nodeActionMenuPosition.value = null
  actionGroups.value = { fileOperations: [], fileAnalysis: [], analysisOperations: [] }
}

async function handleNodeAction(option: any) {
  if (!currentNodeInfo.value) return
  
  const fileInfo = getCurrentFileInfo()
  if (!fileInfo) {
    console.warn(`文件信息未找到: ${currentNodeInfo.value}`)
    return
  }
  
  if (option.disabled && option.disabled(fileInfo)) {
    return
  }
  
  try {
    await option.action(fileInfo)
    closeNodeActionMenu()
  } catch (error) {
    console.error(t('analysis.messages.executeNodeActionFailed'), error)
    closeNodeActionMenu()
  }
}

const nodeActionMenuStyle = computed(() => {
  if (!nodeActionMenuPosition.value) {
    return {}
  }
  
  const menuWidth = 240
  const maxMenuHeight = window.innerHeight * 0.7
  const padding = 10
  
  let left = nodeActionMenuPosition.value.x
  let top = nodeActionMenuPosition.value.y
  
  if (left + menuWidth > window.innerWidth - padding) {
    left = window.innerWidth - menuWidth - padding
  }
  if (left < padding) {
    left = padding
  }
  
  if (top + maxMenuHeight > window.innerHeight - padding) {
    top = window.innerHeight - maxMenuHeight - padding
  }
  if (top < padding) {
    top = padding
  }
  
  return {
    left: `${left}px`,
    top: `${top}px`,
    maxHeight: `${maxMenuHeight}px`
  }
})

function handleClickOutside(event: MouseEvent) {
  if (showNodeActionMenu.value) {
    const target = event.target as HTMLElement
    const menuElement = target.closest('.node-action-menu')
    const dagElement = target.closest('#dag-canvas')
    const dagContainerElement = target.closest('.dag-container')
    
    if (menuElement || dagElement || dagContainerElement) {
      return
    }
    
    closeNodeActionMenu()
  }
}

// ==================== File Operations ====================
async function deleteFileNode(fileId: string, fileName?: string) {
  const fileInfo = filesDict.value[fileId]
  const fileDisplayName = fileName || fileInfo?.filename || fileInfo?.file_name || fileInfo?.fileName || fileId

  let observer: MutationObserver | null = null
  const setMessageBoxZIndex = () => {
    const messageBox = document.querySelector('.delete-confirm-message-box') as HTMLElement
    if (!messageBox) {
      const allMessageBoxes = document.querySelectorAll('.el-message-box')
      if (allMessageBoxes.length > 0) {
        const latestMessageBox = allMessageBoxes[allMessageBoxes.length - 1] as HTMLElement
        latestMessageBox.style.zIndex = '20001'
        
        let parent = latestMessageBox.parentElement
        while (parent && parent !== document.body) {
          if (parent.classList.contains('el-overlay')) {
            parent.style.zIndex = '20000'
            break
          }
          parent = parent.parentElement
        }
      }
      return
    }
    
    messageBox.style.zIndex = '20001'
    
    let parent = messageBox.parentElement
    while (parent && parent !== document.body) {
      if (parent.classList.contains('el-overlay')) {
        parent.style.zIndex = '20000'
        const allOverlays = document.querySelectorAll('.el-overlay')
        allOverlays.forEach((overlay) => {
          if (overlay.contains(messageBox)) {
            (overlay as HTMLElement).style.zIndex = '20000'
          }
        })
        break
      }
      parent = parent.parentElement
    }
  }

  try {
    observer = new MutationObserver(() => {
      setMessageBoxZIndex()
    })
    observer.observe(document.body, {
      childList: true,
      subtree: true
    })

    const messageBoxPromise = ElMessageBox.confirm(
      t('app.confirmDeleteText', { name: fileDisplayName }),
      t('app.confirmDelete'),
      {
        confirmButtonText: t('common.confirm'),
        cancelButtonText: t('common.cancel'),
        type: 'warning',
        dangerouslyUseHTMLString: false,
        customClass: 'delete-confirm-message-box'
      }
    )

    await nextTick()
    setMessageBoxZIndex()
    setTimeout(setMessageBoxZIndex, 0)
    setTimeout(setMessageBoxZIndex, 50)

    await messageBoxPromise

    try {
      await deleteFile(fileId)
      emit('file-deleted', fileId)
      notifySuccess({
        message: t('analysis.messages.fileDeleted')
      })
    } catch (error: unknown) {
      console.error(t('analysis.messages.fileDeleteFailed'), error)
      const message = error instanceof Error ? error.message : t('app.unknownError')
      notifyError({
        message: t('analysis.messages.fileDeleteFailed') + ': ' + message
      })
    }
  } catch (error) {
    console.log('User cancelled file deletion')
  } finally {
    if (observer) {
      observer.disconnect()
    }
    observer = null
  }
}

async function deleteFileChildrenNode(fileId: string, fileName?: string) {
  const fileInfo = filesDict.value[fileId]
  const fileDisplayName = fileName || fileInfo?.filename || fileInfo?.file_name || fileInfo?.fileName || fileId
  const projectId = typeof route.query.projectId === 'string' ? route.query.projectId : undefined

  try {
    await ElMessageBox.confirm(
      t('app.confirmDeleteText', { name: `${fileDisplayName} 的子文件` }),
      t('app.confirmDelete'),
      {
        confirmButtonText: t('common.confirm'),
        cancelButtonText: t('common.cancel'),
        type: 'warning',
        customClass: 'delete-children-message-box',
        modalClass: 'delete-children-overlay'
      }
    )

    await deleteFileChildren(fileId, projectId)
    emit('refresh-dag')
    notifySuccess({
      message: t('analysis.messages.fileDeleted')
    })
  } catch (error: unknown) {
    if (error === 'cancel' || (error as any)?.message === 'cancel') return
    console.error(t('analysis.messages.fileDeleteFailed'), error)
    const message = error instanceof Error ? error.message : t('app.unknownError')
    notifyError({
      message: t('analysis.messages.fileDeleteFailed') + ': ' + message
    })
  }
}

// ==================== Service Operations ====================
async function loadServices() {
  const projectId = typeof route.query.projectId === 'string' ? route.query.projectId : ''
  
  if (servicesAbort.value) {
    servicesAbort.value.abort()
    servicesAbort.value = null
  }
  
  if (!projectId) {
    services.value = []
    return
  }

  const cached = getCachedProjectServices(projectId)
  if (cached) {
    services.value = cached.services ?? []
  }

  const controller = new AbortController()
  servicesAbort.value = controller
  loadingServices.value = true
  serviceLoadError.value = ''
  
  try {
    const result = await fetchProjectServices({
      projectId,
      signal: controller.signal
    })
    services.value = result.services ?? []
  } catch (error: unknown) {
    if ((error as any)?.name === 'AbortError') return
    console.error('加载服务列表失败', error)
    serviceLoadError.value =
      (error as any)?.message || (error as Error)?.toString() || t('app.unknownError')
    services.value = []
  } finally {
    if (servicesAbort.value === controller) {
      servicesAbort.value = null
    }
    loadingServices.value = false
  }
}

function requiresMultiFile(service: any) {
  const accepted = service?.accepted_files
  if (!accepted) return false
  return Object.keys(accepted).length > 1
}

function showServiceExecuteDialogHandler(service: any, fileId: string) {
  if (requiresMultiFile(service)) {
    const projectId =
      typeof route.query.projectId === 'string' ? route.query.projectId : undefined
    router.push({
      name: 'ServiceExecutePage',
      params: { serviceId: service?.service_id },
      query: {
        projectId,
        fileId,
        origin: 'analysis'
      }
    })
    closeNodeActionMenu()
    return
  }

  selectedService.value = service
  currentFileId.value = [fileId]
  showServiceExecuteDialog.value = true
  closeNodeActionMenu()
}

function closeServiceExecuteDialog() {
  showServiceExecuteDialog.value = false
  selectedService.value = null
  currentFileId.value = null
}

function handleServiceExecuted(result: any) {
  if (result.status === 'completed') {
    notifySuccess({ message: t('analysis.messages.serviceExecutedSuccess') })
    emit('refresh-dag')
  } else if (result.status === 'failed') {
    const errorMsg = result.error_message || t('analysis.messages.serviceExecutedFailed')
    notifyError({ message: errorMsg })
  }
  closeServiceExecuteDialog()
}

// ==================== File Preview ====================
function showFilePreviewHandler(fileId: string) {
  const fileInfo = filesDict.value[fileId]
  if (!fileInfo) {
    console.warn(t('analysis.messages.fileInfoNotFound', { fileId }))
    return
  }
  
  const fileName = fileInfo.filename || fileInfo.file_name || fileInfo.fileName || fileId
  const fileType = detectFileType(fileInfo).category
  
  previewFileInfo.value = {
    fileId,
    fileName,
    fileType
  }
  showFilePreviewDialog.value = true
  closeNodeActionMenu()
}

function closeFilePreviewDialog() {
  showFilePreviewDialog.value = false
  previewFileInfo.value = null
}

// ==================== Provide ====================
provide('deleteFileNode', deleteFileNode)
provide('showServiceExecuteDialog', showServiceExecuteDialogHandler)
provide('showFilePreview', showFilePreviewHandler)

// ==================== Lifecycle ====================
onMounted(() => {
  loadServices()
  setTimeout(() => {
    if (propNodes.value.length > 0) {
      initGraph()
    }
  }, 100)
  
  watch(
    [propNodes, propEdges],
    () => {
      if (graph && propNodes.value.length > 0) {
        updateGraph()
      } else if (!graph && propNodes.value.length > 0) {
        initGraph()
      }
    },
    { deep: true }
  )
  
  watch(
    () => route.query.projectId,
    () => loadServices(),
    { immediate: false }
  )
  
  window.addEventListener('resize', handleResize)
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  document.removeEventListener('click', handleClickOutside)
  
  if (graph) {
    try {
      graph.destroy()
    } catch (e) {
      console.warn('销毁图实例失败', e)
    }
  }
  
  if (tooltip) {
    document.body.removeChild(tooltip)
    tooltip = null
  }
})
</script>

<style scoped>
.dag-container {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: linear-gradient(135deg, rgba(245, 247, 250, 0.95) 0%, rgba(238, 242, 246, 0.95) 100%);
  border-radius: 8px;
  overflow: hidden;
}

.dag-header {
  padding: 1.5rem 2rem;
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid rgba(200, 200, 210, 0.4);
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.dag-header-left {
  flex: 1;
}

.dag-header h3 {
  margin: 0 0 0.5rem 0;
  font-size: 1.25rem;
  font-weight: 600;
  color: rgba(60, 60, 70, 0.9);
}

.dag-subtitle {
  margin: 0;
  font-size: 0.9rem;
  color: rgba(100, 100, 110, 0.7);
}

#dag-canvas {
  flex: 1;
  position: relative;
}
</style>

<style>
.dag-tooltip {
  position: fixed;
  padding: 16px;
  background: rgba(40, 40, 50, 0.98);
  backdrop-filter: blur(10px);
  color: white;
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
  pointer-events: none;
  z-index: 10000;
  display: none;
  max-width: 320px;
  max-height: 60vh;
  overflow-y: auto;
  animation: tooltipFadeIn 0.2s ease-out;
}

@keyframes tooltipFadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.tooltip-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.2);
}

.tooltip-title {
  font-weight: 600;
  font-size: 1rem;
  color: rgba(255, 255, 255, 0.95);
}

.tooltip-type {
  font-size: 0.75rem;
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 500;
  background: rgba(82, 196, 26, 0.2);
  color: #52c41a;
}

.tooltip-section {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.tooltip-row {
  display: flex;
  gap: 8px;
  font-size: 0.8rem;
  margin-bottom: 4px;
}

.tooltip-row span:first-child {
  color: rgba(255, 255, 255, 0.7);
}

.tooltip-row span:last-child {
  color: rgba(100, 200, 255, 0.9);
  word-break: break-all;
}

/* ============ 节点操作菜单样式 ============ */
.node-action-menu {
  position: fixed;
  background: var(--bg-secondary, #ffffff);
  backdrop-filter: blur(10px);
  border-radius: 12px;
  border: 1px solid var(--border-color, rgba(200, 200, 210, 0.5));
  border-radius: 12px;
  box-shadow: 0 18px 45px rgba(0, 0, 0, 0.18);
  z-index: 9999;
  min-width: 240px;
  max-width: 320px;
  max-height: 70vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  animation: menuFadeIn 0.2s ease-out;
}

@keyframes menuFadeIn {
  from {
    opacity: 0;
    transform: scale(0.95) translateY(-10px);
  }
  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}

.node-action-menu-header {
  padding: 1rem 1.25rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--border-color, rgba(200, 200, 210, 0.5));
  background: var(--bg-tertiary, rgba(245, 247, 250, 0.95));
}

.node-action-menu-title {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex: 1;
  min-width: 0;
}

.menu-icon {
  font-size: 1.2rem;
  flex-shrink: 0;
}

.menu-file-name {
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--text-primary, rgba(60, 60, 70, 0.9));
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.menu-close-btn {
  background: transparent;
  border: none;
  font-size: 1.5rem;
  color: var(--text-secondary, rgba(100, 100, 110, 0.7));
  cursor: pointer;
  padding: 0;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.menu-close-btn:hover {
  background: var(--bg-secondary, rgba(255, 255, 255, 0.5));
  color: var(--text-primary, rgba(60, 60, 70, 0.9));
}

.node-action-menu-divider {
  height: 1px;
  background: var(--border-color, rgba(200, 200, 210, 0.5));
}

.node-action-menu-body {
  padding: 0.5rem 0;
  overflow-y: auto;
  overflow-x: hidden;
  flex: 1;
  min-height: 0;
  scrollbar-width: thin;
  scrollbar-color: rgba(200, 200, 210, 0.5) transparent;
}

.node-action-menu-body::-webkit-scrollbar {
  width: 6px;
}

.node-action-menu-body::-webkit-scrollbar-track {
  background: transparent;
}

.node-action-menu-body::-webkit-scrollbar-thumb {
  background: rgba(200, 200, 210, 0.5);
  border-radius: 3px;
}

.node-action-menu-body::-webkit-scrollbar-thumb:hover {
  background: rgba(200, 200, 210, 0.7);
}

.menu-section {
  margin-bottom: 0.5rem;
}

.menu-section:last-child {
  margin-bottom: 0;
}

.menu-section-title {
  padding: 0.5rem 1.25rem;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-secondary, rgba(100, 100, 110, 0.7));
  text-transform: uppercase;
  letter-spacing: 0.5px;
  background: var(--bg-tertiary, rgba(245, 247, 250, 0.95));
  border-bottom: 1px solid var(--border-color, rgba(200, 200, 210, 0.3));
}

.node-action-menu-item {
  padding: 0.875rem 1.25rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  transition: all 0.2s ease;
  font-size: 0.9rem;
  color: var(--text-primary, rgba(60, 60, 70, 0.9));
  border-left: 3px solid transparent;
}

.node-action-menu-item:hover:not(.menu-item-disabled) {
  background: var(--bg-tertiary, rgba(245, 247, 250, 0.95));
  border-left-color: var(--accent-primary, rgba(100, 150, 220, 0.9));
}

.node-action-menu-item.menu-item-danger {
  color: rgba(220, 100, 100, 0.9);
}

.node-action-menu-item.menu-item-danger:hover:not(.menu-item-disabled) {
  background: rgba(220, 100, 100, 0.1);
  border-left-color: rgba(220, 100, 100, 0.9);
  color: rgba(220, 100, 100, 1);
}

.node-action-menu-item.menu-item-disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.delete-children-overlay {
  z-index: 20010 !important;
}

.delete-children-message-box {
  z-index: 20011 !important;
}

.node-action-menu-hint {
  padding: 0.75rem 1.25rem;
  font-size: 0.85rem;
  color: var(--text-secondary, rgba(100, 100, 110, 0.7));
  line-height: 1.4;
  border-top: 1px dashed var(--border-color, rgba(200, 200, 210, 0.4));
}

.menu-item-icon {
  font-size: 1rem;
  flex-shrink: 0;
  width: 20px;
  text-align: center;
}

.menu-item-label {
  flex: 1;
  font-weight: 500;
}

/* Service执行对话框样式 */
.service-execute-dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10000;
  backdrop-filter: blur(4px);
}

.service-execute-dialog {
  background: var(--bg-primary, white);
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
  width: 90%;
  max-width: 800px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.5rem;
  border-bottom: 1px solid var(--border-color, rgba(200, 200, 210, 0.5));
  background: var(--bg-secondary, rgba(245, 247, 250, 0.95));
}

.dialog-header h3 {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 600;
  color: var(--text-primary, rgba(60, 60, 70, 0.9));
}

.dialog-close-btn {
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  font-size: 1.5rem;
  color: var(--text-secondary, rgba(100, 100, 110, 0.7));
  cursor: pointer;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.dialog-close-btn:hover {
  background: var(--bg-tertiary, rgba(245, 247, 250, 0.95));
  color: var(--text-primary, rgba(60, 60, 70, 0.9));
}

.dialog-content {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem;
}
</style>
