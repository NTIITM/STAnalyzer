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
            <span class="menu-file-name">{{ getCurrentFileInfo()?.filename || getCurrentFileInfo()?.fileName || t('analysis.nodeMenu.unknownFile') }}</span>
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
            <h3>{{ $t('service.execute.title') }}</h3>
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
import { ElMessageBox, ElButton } from 'element-plus'
import { getNodeActionOptions, type NodeActionGroups } from '../../types/nodeActions'
import { deleteFile } from '../../api/file'
import FilePreviewDialog from '../file-preview/FilePreviewDialog.vue'
import ServiceExecute from '../service/ServiceExecute.vue'
import {
  fetchProjectServices,
  getCachedProjectServices,
  type ProjectService,
  type ProjectServicesResult
} from '../../stores/servicesCache'
import { notifyError, notifySuccess } from '../../utils/notify'
import { detectFileType, type FileCategory } from '../../utils/fileType'

const route = useRoute()
const router = useRouter()
const { t } = useI18n()

// ==================== Inject from AnalysisPanel ====================
// 从父组件 AnalysisPanel 注入的函数
const triggerAnalysisComponent = inject<(componentId: string, fileId: string) => void>('triggerAnalysisComponent')
const showEditFileDialog = inject<(dataItem: any) => void>('showEditFileDialog')
const addFileToContext = inject<(fileId: string, fileName: string) => void>('addFileToContext')
const previewFileInfo = ref<{
  fileId: string
  fileName: string
  fileType: FileCategory
} | null>(null)

const props = defineProps<{
  nodes: any[]
  edges: any[]
  files: any[]
}>()

const propNodes = computed(() => props.nodes || [])
const propEdges = computed(() => props.edges || [])

// 将 files 列表转换为以 file_id 为 key 的字典（O(1) 查找性能）
const filesDict = computed(() => {
  const dict: Record<string, any> = {}
  const files = Array.isArray(props.files)
    ? props.files
    : props.files
      ? Object.values(props.files)
      : []
  files.forEach(file => {
    if (!file) return
    const fileId = file.file_id || file.id
    if (fileId) {
      dict[fileId] = file
    }
  })
  return dict
})

// 画布和图实例
const dagContainer = ref<HTMLElement | null>(null)
const dagCanvas = ref<HTMLElement | null>(null)
let graph: InstanceType<typeof Graph> | null = null
let tooltip: HTMLElement | null = null

// 对话框和选择状态
const showServiceExecuteDialog = ref(false)
const showFilePreviewDialog = ref(false)
const selectedService = ref<any>(null)
const currentFileId = ref<string | string[] | null>(null)

// 节点操作菜单状态
const showNodeActionMenu = ref(false)
const currentNodeInfo = ref<string | null>(null) // 只存储 fileId
const nodeActionMenuPosition = ref<{ x: number; y: number } | null>(null)
const actionGroups = ref<NodeActionGroups>({ fileOperations: [], fileAnalysis: [], analysisOperations: [] })

// Service相关状态
const services = ref<ProjectService[]>([])
const loadingServices = ref(false)
const serviceLoadError = ref('')
const serviceMeta = ref<{ fromCache: boolean; fetchedAt: number | null }>({
  fromCache: false,
  fetchedAt: null
})
const servicesAbort = ref<AbortController | null>(null)

async function loadServices() {
  const projectId = typeof route.query.projectId === 'string' ? route.query.projectId : ''
  // 清理旧请求
  if (servicesAbort.value) {
    servicesAbort.value.abort()
    servicesAbort.value = null
  }
  if (!projectId) {
    services.value = []
    serviceMeta.value = { fromCache: false, fetchedAt: null }
    return
  }

  // 优先使用缓存
  const cached = getCachedProjectServices(projectId)
  if (cached) {
    services.value = cached.services ?? []
    serviceMeta.value = { fromCache: true, fetchedAt: cached.fetchedAt }
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
    serviceMeta.value = { fromCache: result.fromCache, fetchedAt: result.fetchedAt }
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
const serviceMenuNotice = computed(() => {
  if (loadingServices.value) return t('app.serviceMenuLoading')
  if (serviceLoadError.value) return serviceLoadError.value
  if (services.value.length === 0) return t('app.serviceMenuEmpty')
  return ''
})
const showAnalysisSection = computed(
  () =>
    actionGroups.value.analysisOperations.length > 0 ||
    Boolean(serviceMenuNotice.value)
)

// 计算当前文件信息（从 filesDict 中获取）
const currentFileInfo = computed(() => {
  if (!currentFileId.value) return null
  const fileId = Array.isArray(currentFileId.value) ? currentFileId.value[0] : currentFileId.value
  if (!fileId) return null
  return filesDict.value[fileId] || null
})

// 定义节点颜色（统一色，绿色）
const getNodeColor = (): string => '#52c41a'

// 根据文件名判断节点类型
const getNodeType = (filename: string | undefined): 'circle' | 'rect' => {
  if (!filename) return 'circle'
  return filename.toLowerCase().endsWith('.txt') ? 'rect' : 'circle'
}

// 定义边颜色（统一色）
const getEdgeColor = (): string => '#bfbfbf'

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

/**
 * 删除文件节点
 */
async function deleteFileNode(fileId: string, fileName?: string) {
  // 获取文件名，如果没有传入则从 filesDict 获取
  const fileInfo = filesDict.value[fileId]
  const fileDisplayName = fileName || fileInfo?.filename || fileInfo?.file_name || fileInfo?.fileName || fileId

  // 使用 MutationObserver 监听 ElMessageBox 的创建
  let observer: MutationObserver | null = null
  const setMessageBoxZIndex = () => {
    // 查找包含自定义类的消息框
    const messageBox = document.querySelector('.delete-confirm-message-box') as HTMLElement
    if (!messageBox) {
      // 如果找不到，尝试查找最新的 el-message-box
      const allMessageBoxes = document.querySelectorAll('.el-message-box')
      if (allMessageBoxes.length > 0) {
        const latestMessageBox = allMessageBoxes[allMessageBoxes.length - 1] as HTMLElement
        latestMessageBox.style.zIndex = '20001'
        
        // 查找对应的 overlay
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
    
    // 找到消息框，设置其 z-index
    messageBox.style.zIndex = '20001'
    
    // 查找并设置 overlay 的 z-index
    let parent = messageBox.parentElement
    while (parent && parent !== document.body) {
      if (parent.classList.contains('el-overlay')) {
        parent.style.zIndex = '20000'
        // 同时设置所有相关的 overlay
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
    // 创建 MutationObserver 监听 body 的变化
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

    // 立即尝试设置 z-index
    await nextTick()
    setMessageBoxZIndex()
    
    // 延迟再次设置，确保 DOM 完全渲染
    setTimeout(setMessageBoxZIndex, 0)
    setTimeout(setMessageBoxZIndex, 50)

    await messageBoxPromise

    // 用户确认删除
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
    // 用户取消删除，不需要处理
    console.log('User cancelled file deletion')
  } finally {
    // 停止观察
    if (observer) {
      observer.disconnect()
      observer = null
    }
  }
}

function initGraph() {
  if (!dagCanvas.value) {
    console.warn(t('analysis.messages.dagCanvasNotReady'))
    return
  }
  
  // 构建图数据（过滤掉项目节点）
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
  
  // 获取所有节点ID集合（用于过滤边）
  const nodeIds = new Set(nodes.map(n => n.id))
  
  // 过滤边：只保留两端节点都在节点列表中的边（排除与项目节点相关的边）
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
  
  // 如果已有图实例，先销毁
  if (graph) {
    try {
      graph.destroy()
    } catch (e) {
      console.warn(t('analysis.messages.destroyGraphInstanceError'), e)
    }
  }
  
  // 创建图实例（G6 5.x）
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
          // 对于正方形节点，返回 [width, height] 数组
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
            // 对于正方形节点，设置圆角
            ...(nodeType === 'rect' ? { radius: 4 } : {}),
            // 标签配置
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
        animation: {
          update: {
            duration: 200,
            easing: 'easeQuadOut'
          }
        }
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
        labelText: '',
        labelFill: '#666',
        labelFontSize: 11,
        labelFontWeight: 500,
        labelPlacement: 'center',
        labelBackground: true,
        labelBackgroundFill: 'rgba(255, 255, 255, 0.9)',
        labelBackgroundPadding: [2, 6],
        labelBackgroundRadius: 3,
        labelBackgroundStroke: 'rgba(200, 200, 210, 0.3)',
        labelBackgroundLineWidth: 1,
        animation: {
          enter: false
        }
      }
    })
    
    graph.render()
    
    // 绑定事件
    bindEvents()
  } catch (error) {
    console.error(t('analysis.messages.createGraphInstanceFailed'), error)
    graph = null
  }
}

/**
 * 更新图数据（G6 5.x）
 */
function updateGraph() {
  if (!graph || !dagCanvas.value) {
    initGraph()
    return
  }
  
  // 构建节点数据
  let nodes = propNodes.value.map(fileNode => {
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
  
  // 获取所有节点ID集合（用于过滤边）
  const nodeIds = new Set(nodes.map(n => n.id))
  
  // 构建边数据
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
    // G6 5.x 使用 updateData 方法更新数据
    if (typeof graph.updateData === 'function') {
      graph.updateData({
        nodes,
        edges
      })
      // 更新数据后需要重新渲染和布局
      if (typeof graph.render === 'function') {
        graph.render()
      }
      // 如果图有布局方法，也需要重新布局
      if (typeof graph.layout === 'function') {
        graph.layout()
      }
    } else {
      // 降级方案：重新初始化
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

/**
 * 绑定图事件
 */
function bindEvents() {
  if (!graph) return
  
  // 移除旧的事件监听器（避免重复绑定）
  graph.off('node:click')
  graph.off('node:mouseenter')
  graph.off('node:mouseleave')
  
  // 节点点击事件
  graph.on('node:click', (e) => {
    // 阻止事件冒泡
    const event = e.event || e.originalEvent || e.nativeEvent
    if (event) {
      event.stopPropagation()
    }
    
    const { target } = e
    if (!target) return
    
    const nodeData = graph.getNodeData(target.id)
    if (!nodeData) return
    
    // 若项目ID为空，跳转项目页面
    const projectId = typeof route.query.projectId === 'string' ? route.query.projectId : ''
    if (!projectId) {
      router.push({ name: 'ProjectPage' })
      return
    }
    
    // 从 files 字典中获取完整的文件信息（O(1) 查找）
    const nodeId = nodeData.id
    // 只传递 fileId，不传递完整文件信息
    showNodeActionMenuForNode(event, nodeId)
  })
  
  // 节点悬停事件
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
    
    showTooltip(node, 'file')
  })
  
  // 节点离开事件
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

/**
 * 显示工具提示
 */
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
  
  let html = ''
  
  // 文件信息提示
  const fileId = model.id
  const fileInfo = filesDict.value[fileId]
  if (!fileInfo) {
    hideTooltip()
    return
  }
  const filename = fileInfo.filename || fileInfo.file_name || fileInfo.fileName || fileId
  const fileType = detectFileType(filename)
  const fileTypeLabel = fileType === 'text' ? t('analysis.fileType.text') : t('analysis.fileType.unknown')
  html = `
    <div class="tooltip-header">
      <div class="tooltip-title">� ${filename}</div>
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

/**
 * 加深颜色
 */
function darkenColor(color: string, amount: number): string {
  const num = parseInt(color.replace('#', ''), 16)
  const r = Math.max(0, (num >> 16) - Math.round(255 * amount))
  const g = Math.max(0, ((num >> 8) & 0x00FF) - Math.round(255 * amount))
  const b = Math.max(0, (num & 0x0000FF) - Math.round(255 * amount))
  return `#${((r << 16) | (g << 8) | b).toString(16).padStart(6, '0')}`
}

/**
 * 变亮颜色
 */
function lightenColor(color: string, amount: number): string {
  const num = parseInt(color.replace('#', ''), 16)
  const r = Math.min(255, (num >> 16) + Math.round(255 * amount))
  const g = Math.min(255, ((num >> 8) & 0x00FF) + Math.round(255 * amount))
  const b = Math.min(255, (num & 0x0000FF) + Math.round(255 * amount))
  return `#${((r << 16) | (g << 8) | b).toString(16).padStart(6, '0')}`
}

/**
 * 处理窗口大小变化
 */
function handleResize() {
  if (!graph || !dagCanvas.value) return
  
  try {
    const width = dagCanvas.value.clientWidth
    const height = dagCanvas.value.clientHeight
    // G6 5.x 使用 resize 方法
    if (typeof graph.resize === 'function') {
      graph.resize(width, height)
    }
  } catch (error) {
    console.warn(t('analysis.messages.resizeGraphFailed'), error)
  }
}

// ==================== 节点操作菜单 ====================
/**
 * 获取当前文件信息（从 filesDict 中获取）
 */
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

  // 从 filesDict 获取完整的文件信息
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

  // 构建 handlers 对象，使用 inject 的函数
  const handlers = {
    triggerAnalysisComponent,
    showEditFileDialog,
    deleteFileNode,
    showServiceExecuteDialog: showServiceExecuteDialogHandler,
    showFilePreview: showFilePreviewHandler,
    addFileToContext
  }

  actionGroups.value = getNodeActionOptions(fileInfo, handlers, services.value)
}

function refreshActionGroups() {
  if (showNodeActionMenu.value && currentNodeInfo.value) {
    updateActionGroupsForNode(currentNodeInfo.value)
  }
}

watch(services, () => {
  refreshActionGroups()
})

/**
 * 显示节点操作菜单
 * @param event - 事件对象
 * @param fileId - 文件ID（只传递 fileId，不传递完整文件信息）
 */
function showNodeActionMenuForNode(event: any, fileId: string) {
  // 检查 fileId 是否有效
  if (!fileId) {
    return
  }
  
  // 验证文件信息是否存在
  const fileInfo = filesDict.value[fileId]
  if (!fileInfo) {
    console.warn(t('analysis.messages.fileInfoNotFound', { fileId }))
    return
  }
  
  // 只存储 fileId
  currentNodeInfo.value = fileId
  
  // 根据节点信息生成操作选项（传递 fileId，函数内部会从 filesDict 获取完整信息）
  updateActionGroupsForNode(fileId)
  
  // 计算菜单位置（相对于视口）
  let positionSet = false
  
  if (event && event.canvas && event.canvas.x !== undefined && event.canvas.y !== undefined) {
    // G6事件对象包含canvas坐标
    const canvasRect = dagCanvas.value?.getBoundingClientRect()
    if (canvasRect) {
      nodeActionMenuPosition.value = {
        x: canvasRect.left + event.canvas.x,
        y: canvasRect.top + event.canvas.y
      }
      positionSet = true
    }
  } else if (event && event.client && event.client.x !== undefined && event.client.y !== undefined) {
    // 使用client坐标
    nodeActionMenuPosition.value = {
      x: event.client.x,
      y: event.client.y
    }
    positionSet = true
  } else if (event && event.canvasX !== undefined && event.canvasY !== undefined) {
    // 备用：直接使用canvasX/Y
    const canvasRect = dagCanvas.value?.getBoundingClientRect()
    if (canvasRect) {
      nodeActionMenuPosition.value = {
        x: canvasRect.left + event.canvasX,
        y: canvasRect.top + event.canvasY
      }
      positionSet = true
    }
  } else if (event && event.clientX !== undefined && event.clientY !== undefined) {
    // 备用：直接使用clientX/Y
    nodeActionMenuPosition.value = {
      x: event.clientX,
      y: event.clientY
    }
    positionSet = true
  }
  
  if (!positionSet) {
    // 默认位置（节点中心）
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
  
  // 延迟重新添加事件监听器，确保菜单已经显示
  setTimeout(() => {
    document.addEventListener('click', handleClickOutside)
  }, 100)
}

/**
 * 关闭节点操作菜单
 */
function closeNodeActionMenu() {
  showNodeActionMenu.value = false
  currentNodeInfo.value = null
  nodeActionMenuPosition.value = null
  actionGroups.value = { fileOperations: [], fileAnalysis: [], analysisOperations: [] }
}

/**
 * 处理节点操作选项点击
 */
async function handleNodeAction(option: any) {
  if (!currentNodeInfo.value) return
  
  // 从 filesDict 获取完整的文件信息
  const fileInfo = getCurrentFileInfo()
  if (!fileInfo) {
    console.warn(`文件信息未找到: ${currentNodeInfo.value}`)
    return
  }
  
  // 检查是否禁用
  if (option.disabled && option.disabled(fileInfo)) {
    return
  }
  
  try {
    // 执行操作（传递完整的文件信息给 action）
    await option.action(fileInfo)
    // 操作完成后关闭菜单
    closeNodeActionMenu()
  } catch (error) {
    console.error(t('analysis.messages.executeNodeActionFailed'), error)
    // 即使出错也关闭菜单
    closeNodeActionMenu()
  }
}

/**
 * 节点操作菜单样式计算
 */
const nodeActionMenuStyle = computed(() => {
  if (!nodeActionMenuPosition.value) {
    return {}
  }
  
  // 确保菜单不会超出视口
  const menuWidth = 240 // 菜单宽度
  const maxMenuHeight = window.innerHeight * 0.7 // 使用 70vh 作为最大高度
  const padding = 10
  
  let left = nodeActionMenuPosition.value.x
  let top = nodeActionMenuPosition.value.y
  
  // 调整水平位置
  if (left + menuWidth > window.innerWidth - padding) {
    left = window.innerWidth - menuWidth - padding
  }
  if (left < padding) {
    left = padding
  }
  
  // 调整垂直位置 - 确保菜单完全在视口内
  // 如果菜单会超出底部，向上调整
  if (top + maxMenuHeight > window.innerHeight - padding) {
    top = window.innerHeight - maxMenuHeight - padding
  }
  // 如果向上调整后超出顶部，则从顶部开始
  if (top < padding) {
    top = padding
  }
  
  return {
    left: `${left}px`,
    top: `${top}px`,
    maxHeight: `${maxMenuHeight}px`
  }
})

/**
 * 点击其他地方关闭菜单
 */
function handleClickOutside(event: MouseEvent) {
  if (showNodeActionMenu.value) {
    const target = event.target
    // 检查点击是否在菜单内部
    const menuElement = target.closest('.node-action-menu')
    // 检查点击是否在 DAG canvas 上（避免点击节点时关闭菜单）
    const dagElement = target.closest('#dag-canvas')
    const dagContainerElement = target.closest('.dag-container')
    
    // 如果点击在菜单内部或DAG容器内，不关闭菜单
    if (menuElement || dagElement || dagContainerElement) {
      return
    }
    
    closeNodeActionMenu()
  }
}

function requiresMultiFile(service: any) {
  const accepted = service?.accepted_files
  if (!accepted) return false
  return Object.keys(accepted).length > 1
}

/**
 * 显示Service执行对话框
 */
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
  // 直接使用传入的fileId
  currentFileId.value = [fileId]

  showServiceExecuteDialog.value = true
  // 关闭节点操作菜单
  closeNodeActionMenu()
}

/**
 * 显示文件预览对话框
 * @param fileId - 文件ID（只传递 fileId，不传递完整文件信息）
 */
function showFilePreviewHandler(fileId: string) {
  // 从 filesDict 获取完整的文件信息
  const fileInfo = filesDict.value[fileId]
  if (!fileInfo) {
    console.warn(t('analysis.messages.fileInfoNotFound', { fileId }))
    return
  }
  
  // 从文件信息中提取所需字段
  const fileName = fileInfo.filename || fileInfo.file_name || fileInfo.fileName || fileId
  const fileType = detectFileType(fileInfo).category
  
  previewFileInfo.value = {
    fileId,
    fileName,
    fileType
  }
  showFilePreviewDialog.value = true
  // 关闭节点操作菜单
  closeNodeActionMenu()
}

// ==================== Provide ====================
// 提供函数给 nodeActions.ts 使用（通过 inject）
provide('deleteFileNode', deleteFileNode)
provide('showServiceExecuteDialog', showServiceExecuteDialogHandler)
provide('showFilePreview', showFilePreviewHandler)

/**
 * 关闭文件预览对话框
 */
function closeFilePreviewDialog() {
  showFilePreviewDialog.value = false
  previewFileInfo.value = null
}

/**
 * 关闭Service执行对话框
 */
function closeServiceExecuteDialog() {
  showServiceExecuteDialog.value = false
  selectedService.value = null
  currentFileId.value = null
}

/**
 * Service执行完成后的处理
 */
function handleServiceExecuted(result: ServiceExecution) {
  // 根据执行状态显示相应的消息
  if (window.showMessage) {
    if (result.status === 'completed') {
      window.showMessage.success(t('analysis.messages.serviceExecutedSuccess'))
      // 执行成功时，触发刷新DAG数据
      emit('refresh-dag')
    } else if (result.status === 'failed') {
      const errorMsg = result.error_message || t('analysis.messages.serviceExecutedFailed')
      window.showMessage.error(errorMsg)
    } else {
      // 其他状态（如 pending, running）不应该到达这里，但为了安全起见
      window.showMessage.info(t('analysis.messages.serviceExecutedStatus', { status: result.status }))
    }
  }
  // 关闭对话框
  closeServiceExecuteDialog()
}

/**
 * 显示边信息对话框
 */
function showEdgeInfoDialogHandler(event: any, edgeData: any) {
  // 优先使用边数据中已有的 execution
  let execution = edgeData.execution
  
  // 如果没有，尝试通过 execution_id 查找（使用 execution_id 字典）
  if (!execution && edgeData.execution_id) {
    execution = executionsByIdDict.value[edgeData.execution_id]
  }
  
  // 如果还是没有，尝试通过 source 和 target 匹配（使用 output_file_id 字典）
  if (!execution) {
    const source = edgeData.source || edgeData.from
    const target = edgeData.target || edgeData.to
    // 直接通过 target (output_file_id) 从字典中查找
    execution = executionsDict.value[target]
    // 验证是否匹配 source (input_file_ids)
    if (execution) {
      const inputFileIds = execution.input_file_ids || []
      if (!inputFileIds.includes(source)) {
        execution = null
      }
    }
  }
  
  // 使用执行记录信息
  currentEdgeInfo.value = {
    ...execution,
    // 确保关键字段存在
    execution_id: execution?.execution_id || '-',
    service_name: execution?.service_name || '-',
    service_description: execution?.service_description || '-',
    status: execution?.status || 'pending',
    parameters: execution?.parameters || {},
    error_message: execution?.error_message || null
  }
  
  // 计算对话框位置
  let positionSet = false
  if (event && event.canvas && event.canvas.x !== undefined && event.canvas.y !== undefined) {
    const canvasRect = dagCanvas.value?.getBoundingClientRect()
    if (canvasRect) {
      edgeInfoDialogPosition.value = {
        x: canvasRect.left + event.canvas.x,
        y: canvasRect.top + event.canvas.y
      }
      positionSet = true
    }
  } else if (event && event.clientX !== undefined && event.clientY !== undefined) {
    edgeInfoDialogPosition.value = {
      x: event.clientX,
      y: event.clientY
    }
    positionSet = true
  }
  
  if (!positionSet) {
    const canvasRect = dagCanvas.value?.getBoundingClientRect()
    if (canvasRect) {
      edgeInfoDialogPosition.value = {
        x: canvasRect.left + canvasRect.width / 2,
        y: canvasRect.top + canvasRect.height / 2
      }
    } else {
      edgeInfoDialogPosition.value = { x: 100, y: 100 }
    }
  }
  
  showEdgeInfoDialog.value = true
  
  // 延迟添加点击外部关闭事件
  setTimeout(() => {
    document.addEventListener('click', handleClickOutsideEdgeDialog)
  }, 100)
}

/**
 * 关闭边信息对话框
 */
function closeEdgeInfoDialog() {
  showEdgeInfoDialog.value = false
  currentEdgeInfo.value = null
  edgeInfoDialogPosition.value = null
}

/**
 * 删除执行记录
 */
async function handleDeleteExecution() {
  if (!currentEdgeInfo.value?.execution_id) {
    return
  }

  const executionId = currentEdgeInfo.value.execution_id
  const serviceName = currentEdgeInfo.value.service_name || t('analysis.edgeInfo.title')

  // 临时降低详情框的 z-index，确保确认框显示在最顶层
  const dialogElement = document.querySelector('.edge-info-dialog') as HTMLElement
  let originalZIndex: string | null = null
  if (dialogElement) {
    originalZIndex = dialogElement.style.zIndex || ''
    dialogElement.style.zIndex = '1000' // 临时降低，低于 ElMessageBox 的默认 z-index (通常是 2000+)
  }

  // 使用 MutationObserver 监听 ElMessageBox 的创建
  let observer: MutationObserver | null = null
  const setMessageBoxZIndex = () => {
    // 查找包含自定义类的消息框
    const messageBox = document.querySelector('.delete-confirm-message-box') as HTMLElement
    if (!messageBox) {
      // 如果找不到，尝试查找最新的 el-message-box
      const allMessageBoxes = document.querySelectorAll('.el-message-box')
      if (allMessageBoxes.length > 0) {
        const latestMessageBox = allMessageBoxes[allMessageBoxes.length - 1] as HTMLElement
        latestMessageBox.style.zIndex = '20001'
        
        // 查找对应的 overlay
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
    
    // 找到消息框，设置其 z-index
    messageBox.style.zIndex = '20001'
    
    // 查找并设置 overlay 的 z-index
    let parent = messageBox.parentElement
    while (parent && parent !== document.body) {
      if (parent.classList.contains('el-overlay')) {
        parent.style.zIndex = '20000'
        // 同时设置所有相关的 overlay
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
    // 创建 MutationObserver 监听 body 的变化
    observer = new MutationObserver(() => {
      setMessageBoxZIndex()
    })
    observer.observe(document.body, {
      childList: true,
      subtree: true
    })

    const messageBoxPromise = ElMessageBox.confirm(
      t('analysis.edgeInfo.confirmDeleteExecution', { name: serviceName }),
      t('analysis.edgeInfo.confirmDelete'),
      {
        confirmButtonText: t('common.confirm'),
        cancelButtonText: t('common.cancel'),
        type: 'warning',
        dangerouslyUseHTMLString: false,
        customClass: 'delete-confirm-message-box'
      }
    )

    // 立即尝试设置 z-index
    await nextTick()
    setMessageBoxZIndex()
    
    // 延迟再次设置，确保 DOM 完全渲染
    setTimeout(setMessageBoxZIndex, 0)
    setTimeout(setMessageBoxZIndex, 50)

    await messageBoxPromise

    deletingExecution.value = true
    try {
      await deleteExecution(executionId)
      notifySuccess({
        message: t('analysis.edgeInfo.deleteExecutionSuccess')
      })
      // 关闭对话框
      closeEdgeInfoDialog()
      // 刷新 DAG 图
      emit('refresh-dag')
    } catch (error: any) {
      console.error('Delete execution failed:', error)
      notifyError({
        message: t('analysis.edgeInfo.deleteExecutionFailed'),
        details: error?.message || error?.toString()
      })
    } finally {
      deletingExecution.value = false
    }
  } catch (error) {
    // 用户取消删除，不需要处理
    console.log('User cancelled deletion')
  } finally {
    // 停止观察
    if (observer) {
      observer.disconnect()
      observer = null
    }
    // 恢复详情框的 z-index
    if (dialogElement && originalZIndex !== null) {
      if (originalZIndex) {
        dialogElement.style.zIndex = originalZIndex
      } else {
        dialogElement.style.zIndex = '' // 恢复为 CSS 中的值
      }
    }
  }
}

/**
 * 点击外部关闭边信息对话框
 */
function handleClickOutsideEdgeDialog(event: MouseEvent) {
  if (showEdgeInfoDialog.value) {
    const target = event.target
    const dialogElement = target.closest('.edge-info-dialog')
    const dagElement = target.closest('#dag-canvas')
    
    if (!dialogElement && !dagElement) {
      closeEdgeInfoDialog()
    }
  }
}

/**
 * 边信息对话框样式计算
 */
const edgeInfoDialogStyle = computed(() => {
  if (!edgeInfoDialogPosition.value) {
    return {}
  }
  
  const dialogWidth = 500
  const maxDialogHeight = window.innerHeight * 0.8 // 使用 80vh 作为最大高度
  const padding = 10
  
  let left = edgeInfoDialogPosition.value.x
  let top = edgeInfoDialogPosition.value.y
  
  // 调整水平位置
  if (left + dialogWidth > window.innerWidth - padding) {
    left = window.innerWidth - dialogWidth - padding
  }
  if (left < padding) {
    left = padding
  }
  
  // 调整垂直位置 - 确保对话框完全在视口内
  // 如果对话框会超出底部，向上调整
  if (top + maxDialogHeight > window.innerHeight - padding) {
    top = window.innerHeight - maxDialogHeight - padding
  }
  // 如果向上调整后超出顶部，则从顶部开始
  if (top < padding) {
    top = padding
  }
  
  return {
    left: `${left}px`,
    top: `${top}px`,
    maxHeight: `${maxDialogHeight}px`
  }
})

/**
 * 获取状态文本
 */
function getStatusText(status: string): string {
  const statusMap = {
    completed: t('analysis.status.completed'),
    running: t('analysis.status.running'),
    pending: t('analysis.status.pending'),
    failed: t('analysis.status.failed'),
    skipped: t('analysis.status.skipped')
  }
  return statusMap[status] || status || t('analysis.status.pending')
}

/**
 * 格式化日期时间
 */
function formatDateTime(dateTime: string | number | Date): string {
  if (!dateTime) return '-'
  try {
    const date = new Date(dateTime)
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  } catch (e) {
    return dateTime
  }
}

/**
 * 格式化持续时间
 */
function formatDuration(seconds: number): string {
  if (!seconds) return '-'
  if (seconds < 60) {
    return `${seconds}${t('analysis.messages.seconds')}`
  } else if (seconds < 3600) {
    const minutes = Math.floor(seconds / 60)
    const secs = seconds % 60
    return t('analysis.messages.minutes', { minutes, seconds: secs })
  } else {
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    const secs = seconds % 60
    return t('analysis.messages.hours', { hours, minutes, seconds: secs })
  }
}

onUnmounted(() => {
  // 清理图实例
  if (graph) {
    try {
      graph.destroy()
    } catch (e) {
      console.warn(t('analysis.messages.destroyGraphInstanceFailed'), e)
    }
    graph = null
  }

  // 移除事件监听器
  window.removeEventListener('resize', handleResize)

  
  // 清理 tooltip
  if (tooltip) {
    try {
      document.body.removeChild(tooltip)
    } catch (e) {
      console.warn(t('analysis.messages.removeTooltipFailed'), e)
    }
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

.dag-header-right {
  display: flex;
  align-items: center;
  margin-left: 1rem;
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

.dag-header-right {
  display: flex;
  align-items: center;
  margin-left: 1rem;
}

#dag-canvas {
  flex: 1;
  position: relative;
}

.dag-legend {
  position: absolute;
  bottom: 1rem;
  right: 1rem;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(200, 200, 210, 0.5);
  border-radius: 8px;
  padding: 1rem;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  z-index: 100;
  min-width: 140px;
}

.legend-title {
  font-size: 0.875rem;
  font-weight: 600;
  color: rgba(60, 60, 70, 0.9);
  margin-bottom: 0.75rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid rgba(200, 200, 210, 0.3);
}

.legend-items {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.legend-color {
  width: 16px;
  height: 16px;
  border-radius: 3px;
  border: 1px solid rgba(200, 200, 210, 0.5);
  flex-shrink: 0;
}

.legend-label {
  font-size: 0.8rem;
  color: rgba(100, 100, 110, 0.8);
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

.tooltip-status {
  font-size: 0.75rem;
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 500;
}

.tooltip-status.completed {
  background: rgba(82, 196, 26, 0.2);
  color: #52c41a;
}

.tooltip-status.running {
  background: rgba(24, 144, 255, 0.2);
  color: #1890ff;
}

.tooltip-status.pending {
  background: rgba(217, 217, 217, 0.2);
  color: #d9d9d9;
}

.tooltip-status.failed {
  background: rgba(255, 77, 79, 0.2);
  color: #ff4d4f;
}

.tooltip-desc {
  font-size: 0.85rem;
  color: rgba(255, 255, 255, 0.8);
  line-height: 1.5;
  margin-bottom: 12px;
}

.tooltip-section {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
}

.tooltip-section-title {
  font-size: 0.8rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.9);
  margin-bottom: 8px;
}

.tooltip-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 0.8rem;
}

.info-item {
  display: flex;
  gap: 4px;
}

.info-key {
  color: rgba(255, 255, 255, 0.7);
}

.info-value {
  color: rgba(100, 200, 255, 0.9);
  word-break: break-all;
}

.tooltip-config {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 0.8rem;
}

.config-item {
  display: flex;
  gap: 4px;
}

.config-key {
  color: rgba(255, 255, 255, 0.7);
}

.config-value {
  color: rgba(100, 200, 255, 0.9);
  font-family: monospace;
}

.tooltip-summary {
  font-size: 0.8rem;
  color: rgba(255, 255, 255, 0.7);
  line-height: 1.5;
}

.tooltip-error {
  font-size: 0.8rem;
  color: rgba(255, 100, 100, 0.9);
  line-height: 1.5;
  background: rgba(255, 77, 79, 0.1);
  padding: 8px;
  border-radius: 4px;
  border: 1px solid rgba(255, 77, 79, 0.3);
}

/* ============ 节点操作菜单样式 ============ */
.node-action-menu {
  position: fixed;
  background: var(--bg-secondary, #ffffff);
  backdrop-filter: blur(10px);
  border: 1px solid var(--border-color, rgba(200, 200, 210, 0.5));
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
  z-index: 10002 !important;
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
  /* 自定义滚动条样式 */
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

/* ============ 边信息对话框样式 ============ */
.edge-info-dialog {
  position: fixed;
  background: var(--bg-secondary, #ffffff);
  backdrop-filter: blur(10px);
  border: 1px solid var(--border-color, rgba(200, 200, 210, 0.5));
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
  z-index: 10003 !important;
  width: 500px;
  max-width: 90vw;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  animation: dialogFadeIn 0.2s ease-out;
}

@keyframes dialogFadeIn {
  from {
    opacity: 0;
    transform: scale(0.95) translateY(-10px);
  }
  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}

.edge-info-dialog-header {
  padding: 1rem 1.25rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--border-color, rgba(200, 200, 210, 0.5));
  background: var(--bg-tertiary, rgba(245, 247, 250, 0.95));
}

.edge-info-dialog-title {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex: 1;
  min-width: 0;
}

.edge-info-icon {
  font-size: 1.2rem;
  flex-shrink: 0;
}

.edge-info-name {
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--text-primary, rgba(60, 60, 70, 0.9));
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.edge-info-close-btn {
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

.edge-info-close-btn:hover {
  background: var(--bg-secondary, rgba(255, 255, 255, 0.5));
  color: var(--text-primary, rgba(60, 60, 70, 0.9));
}

.edge-info-dialog-divider {
  height: 1px;
  background: var(--border-color, rgba(200, 200, 210, 0.5));
}

.edge-info-dialog-body {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 1rem 1.25rem;
  min-height: 0;
  /* 自定义滚动条样式 */
  scrollbar-width: thin;
  scrollbar-color: rgba(200, 200, 210, 0.5) transparent;
}

.edge-info-dialog-body::-webkit-scrollbar {
  width: 6px;
}

.edge-info-dialog-body::-webkit-scrollbar-track {
  background: transparent;
}

.edge-info-dialog-body::-webkit-scrollbar-thumb {
  background: rgba(200, 200, 210, 0.5);
  border-radius: 3px;
}

.edge-info-dialog-body::-webkit-scrollbar-thumb:hover {
  background: rgba(200, 200, 210, 0.7);
}

.edge-info-content {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.info-section {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.info-section-title {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text-primary, rgba(60, 60, 70, 0.9));
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--border-color, rgba(200, 200, 210, 0.3));
}

.info-item {
  display: flex;
  gap: 0.5rem;
  font-size: 0.875rem;
  padding: 0.25rem 0;
}

.info-key {
  color: var(--text-secondary, rgba(100, 100, 110, 0.7));
  font-weight: 500;
  min-width: 80px;
}

.info-value {
  color: var(--text-primary, rgba(60, 60, 70, 0.9));
  flex: 1;
  word-break: break-word;
}

.info-value.status-completed {
  color: #52c41a;
}

.info-value.status-running {
  color: #1890ff;
}

.info-value.status-pending {
  color: #d9d9d9;
}

.info-value.status-failed {
  color: #ff4d4f;
}

.info-params,
.info-response {
  background: rgba(245, 247, 250, 0.5);
  border: 1px solid rgba(200, 200, 210, 0.3);
  border-radius: 6px;
  padding: 0.75rem;
  font-size: 0.8rem;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  overflow-x: auto;
  max-height: 200px;
  overflow-y: auto;
}

.info-params pre,
.info-response pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
}

/* 删除确认框样式 - 确保显示在最顶层 */
/* 注意：z-index 主要通过 JavaScript 动态设置，这里作为备用 */

.info-error {
  background: rgba(255, 77, 79, 0.1);
  border: 1px solid rgba(255, 77, 79, 0.3);
  border-radius: 6px;
  padding: 0.75rem;
  font-size: 0.875rem;
  color: #ff4d4f;
  word-break: break-word;
}

.edge-info-dialog-footer {
  padding: 1rem;
  border-top: 1px solid var(--border-color, rgba(200, 200, 210, 0.3));
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}
</style>
