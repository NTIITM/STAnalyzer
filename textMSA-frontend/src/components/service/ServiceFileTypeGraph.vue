<template>
  <div class="service-filetype-graph-container">
    <!-- 顶部工具栏 -->
    <div class="graph-toolbar">
      <div class="toolbar-left">
        <el-button @click="goBack" type="default">
          <Icon name="arrow-left" size="sm" />
          <span>{{ t('common.back') }}</span>
        </el-button>
        <div class="project-select">
          <span class="select-label">{{ t('fileTypeGraph.toolbar.project') }}:</span>
          <el-select
            v-model="selectedProjectId"
            filterable
            clearable
            :placeholder="t('fileTypeGraph.toolbar.selectProject')"
            style="width: 250px;"
            @change="handleProjectChange"
            :loading="projectsLoading"
          >
            <el-option
              v-for="project in projects"
              :key="project.project_id"
              :label="project.name"
              :value="project.project_id"
            >
              <div class="project-option">
                <span class="project-option-name">{{ project.name }}</span>
                <span v-if="project.description" class="project-option-desc">{{ project.description }}</span>
              </div>
            </el-option>
          </el-select>
        </div>
        <div class="file-type-search">
          <span class="search-label">{{ t('fileTypeGraph.toolbar.fileType') }}:</span>
          <el-select
            v-model="fileTypeFilterValue"
            filterable
            clearable
            :placeholder="t('fileTypeGraph.toolbar.searchFileType')"
            style="width: 300px;"
            :loading="fileTypesLoading"
          >
            <el-option
              v-for="fileType in fileTypes"
              :key="fileType.id"
              :label="fileType.display_name || fileType.name"
              :value="fileType.id"
            >
              <div class="file-type-option">
                <span class="file-type-name">{{ fileType.display_name || fileType.name }}</span>
                <span v-if="fileType.description" class="file-type-desc">{{ fileType.description }}</span>
              </div>
            </el-option>
          </el-select>
        </div>
        <span v-if="fileTypeId" class="depth-label">{{ t('fileTypeGraph.toolbar.depthLimit') }}:</span>
        <el-input-number
          v-if="fileTypeId"
          v-model="depthLimit"
          :min="0"
          :max="10"
          :disabled="!fileTypeId"
          :placeholder="t('fileTypeGraph.toolbar.depthLimit')"
          style="width: 120px; margin-right: 10px;"
        />
      </div>
      <div class="toolbar-right">
        <el-button @click="openConfigDialog" type="default">
          <Icon name="settings" size="sm" />
          <span>{{ t('common.config') }}</span>
        </el-button>
        <el-button @click="refreshGraph" type="primary">{{ t('common.refresh') }}</el-button>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading-container">
      <el-skeleton :rows="4" animated />
    </div>

    <!-- 错误状态 -->
    <el-alert
      v-if="error"
      :title="error"
      type="error"
      :closable="true"
      @close="error = ''"
      style="margin: 20px;"
    />

    <!-- Vue Flow 画布 -->
    <div v-if="!loading && !error" class="graph-canvas-wrapper" :class="{ 'has-sidebar': selectedNodeId }">
      <VueFlow
        :nodes="nodes"
        :edges="edges"
        :fit-view-on-init="true"
        :min-zoom="0.2"
        :max-zoom="2"
        :nodes-draggable="false"
        class="graph-canvas"
        @node-click="handleNodeClick"
        @pane-click="handlePaneClick"
      >
        <template #node-fileTypeNode="{ data }">
          <div
            class="custom-filetype-node"
            :class="{
              'is-selected': data.isSelected,
              'is-adjacent': data.isAdjacent,
              'is-dimmed': data.isDimmed
            }"
          >
            <Handle type="target" :position="Position.Left" style="background: #cbd5e1" />
            <div class="node-icon">📄</div>
            <div class="node-content">
              <div class="node-label">{{ data.label }}</div>
              <div v-if="data.description" class="node-description">{{ data.description }}</div>
            </div>
            <Handle type="source" :position="Position.Right" style="background: #cbd5e1" />
          </div>
        </template>
        <template #node-serviceNode="{ data }">
          <div
            class="custom-service-node"
            :class="{
              'is-selected': data.isSelected,
              'is-adjacent': data.isAdjacent,
              'is-dimmed': data.isDimmed
            }"
          >
            <Handle type="target" :position="Position.Left" style="background: #d1d5db" />
            <div class="node-icon">⚙️</div>
            <div class="node-content">
              <div class="node-label">{{ data.label }}</div>
              <div v-if="data.description" class="node-description">{{ data.description }}</div>
            </div>
            <Handle type="source" :position="Position.Right" style="background: #d1d5db" />
          </div>
        </template>
      </VueFlow>
    </div>

    <!-- 空状态 -->
    <div v-if="!loading && !error && nodes.length === 0" class="empty-state">
      <div class="empty-icon">📊</div>
      <span>{{ t('common.noData') }}</span>
    </div>

    <!-- 右侧详情面板 -->
    <div v-if="selectedNodeId" class="detail-sidebar">
      <div class="sidebar-header">
        <div class="sidebar-title">
          <span v-if="selectedNodeType === 'service'">{{ t('fileTypeGraph.detail.serviceTitle') }}</span>
          <span v-else-if="selectedNodeType === 'file_type'">{{ t('fileTypeGraph.detail.fileTypeTitle') }}</span>
        </div>
        <button class="sidebar-close" @click.stop="closeSidebar">
          <Icon name="close" size="md" />
        </button>
      </div>
      <div class="sidebar-content">
        <ServiceDetail 
          v-if="selectedNodeType === 'service' && selectedService"
          :service="selectedService"
          @edit="handleServiceEdit"
        />
        <FileTypeDetail 
          v-else-if="selectedNodeType === 'file_type' && selectedFileTypeId"
          :fileTypeId="selectedFileTypeId"
        />
        <div v-else-if="selectedNodeType === 'service' && serviceLoading" class="loading-state">
          <el-skeleton :rows="4" animated />
        </div>
        <div v-else-if="selectedNodeType === 'service' && serviceError" class="error-state">
          <el-alert :title="serviceError" type="error" show-icon :closable="false" />
        </div>
      </div>
    </div>

    <!-- 隐藏文件类型配置对话框 -->
    <el-dialog
      v-model="showConfigDialog"
      :title="t('fileTypeGraph.config.title')"
      width="600px"
      :before-close="handleConfigDialogClose"
    >
      <div class="config-dialog-content">
        <div class="config-description">
          <p>{{ t('fileTypeGraph.config.description') }}</p>
          <p class="config-hint">{{ t('fileTypeGraph.config.hint') }}</p>
        </div>
        <el-input
          v-model="hiddenFileTypesText"
          type="textarea"
          :rows="8"
          placeholder="csv&#10;png&#10;txt&#10;jpg&#10;jpeg"
          class="config-textarea"
        />
        <div class="config-actions">
          <el-button @click="resetToDefault">{{ t('common.reset') }}</el-button>
          <el-button @click="showConfigDialog = false">{{ t('common.cancel') }}</el-button>
          <el-button type="primary" @click="saveHiddenFileTypes">{{ t('common.save') }}</el-button>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
import { ElButton, ElInputNumber, ElAlert, ElSkeleton, ElMessage, ElSelect, ElOption, ElDialog, ElInput } from 'element-plus'
import { VueFlow, Handle, Position, MarkerType } from '@vue-flow/core'
import type { Node, Edge } from '@vue-flow/core'
import { getProjectServiceFileTypeGraph, getProject, getProjectList, type GraphNode, type Project } from '../../api/project'
import { getFileTypes } from '../../api/file'
import { getService, type Service } from '../../api/service'
import type { FileType } from '../../types/file'
import Icon from '../common/Icon.vue'
import ServiceDetail from './ServiceDetail.vue'
import FileTypeDetail from './FileTypeDetail.vue'
import '@vue-flow/core/dist/style.css'

const defaultEdgeStyle = {
  stroke: '#94a3b8',
  strokeWidth: 2
} as const

const activeEdgeStyle = {
  ...defaultEdgeStyle,
  stroke: '#ef4444',
  strokeWidth: 4,
  opacity: 0.98
} as const

const router = useRouter()
const route = useRoute()

// Props from route
const projectId = computed(() => route.query.projectId as string | undefined)
const fileTypeId = computed(() => route.query.fileTypeId as string | undefined)

// 文件类型筛选框的值（绑定到路由参数）
const fileTypeFilterValue = computed({
  get: () => fileTypeId.value || null,
  set: (value: string | null) => {
    handleFileTypeChange(value)
  }
})

// State
const loading = ref(false)
const error = ref('')
const depthLimit = ref<number | undefined>(undefined)
const graphData = ref<GraphNode[]>([])

// Vue Flow data
const nodes = ref<Node[]>([])
const edges = ref<Edge[]>([])

// 项目相关
const projects = ref<Project[]>([])
const projectsLoading = ref(false)
const selectedProjectId = ref<string | null>(null)
const projectInfo = ref<Project | null>(null)
const projectLoading = ref(false)

// 文件类型相关
const fileTypes = ref<FileType[]>([])
const fileTypesLoading = ref(false)
const selectedFileTypeId = ref<string | null>(null)

// 节点选择相关
const selectedNodeId = ref<string | null>(null)
const selectedNodeType = ref<'service' | 'file_type' | null>(null)
const selectedServiceId = ref<string | null>(null)
const selectedService = ref<Service | null>(null)
const serviceLoading = ref(false)
const serviceError = ref('')

// 隐藏文件类型配置
const STORAGE_KEY = 'serviceFileTypeGraph_hiddenFileTypes'
const defaultHiddenFileTypes = ['csv', 'png', 'txt', 'jpg', 'jpeg', 'gif', 'svg', 'webp', 'bmp', 'ico', 'xlsx', 'xls', 'tsv', 'md', 'log', 'json']

// 从 localStorage 加载隐藏文件类型配置
function loadHiddenFileTypes(): string[] {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored) {
      const parsed = JSON.parse(stored)
      if (Array.isArray(parsed) && parsed.every(item => typeof item === 'string')) {
        return parsed.map(item => item.toLowerCase().trim()).filter(Boolean)
      }
    }
  } catch (err) {
    console.warn('Failed to load hidden file types from localStorage:', err)
  }
  return [...defaultHiddenFileTypes]
}

// 保存隐藏文件类型配置到 localStorage
function saveHiddenFileTypesToStorage(types: string[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(types))
  } catch (err) {
    console.warn('Failed to save hidden file types to localStorage:', err)
  }
}

// 隐藏的文件类型列表（响应式）
const hiddenFileTypes = ref<string[]>(loadHiddenFileTypes())

// 配置对话框
const showConfigDialog = ref(false)
const hiddenFileTypesText = ref('')

/**
 * 检查文件类型是否应该被隐藏
 */
function shouldHideFileType(nodeName: string): boolean {
  if (!nodeName) return false
  const nameLower = nodeName.toLowerCase().trim()
  // 检查是否匹配配置的隐藏类型
  return hiddenFileTypes.value.some(type => nameLower.includes(`${type}`))
}

/**
 * 将后端返回的树状结构转换为 vue-flow 的 nodes 和 edges
 * 优化：改进布局算法，提升性能
 */
function convertGraphToFlowData(roots: GraphNode[]): {
  nodes: Node[]
  edges: Edge[]
} {
  const flowNodes: Node[] = []
  const flowEdges: Edge[] = []
  let nodeIdCounter = 0
  const nodeIdMap = new Map<string, string>() // 映射原始ID到flow节点ID
  const nodeMap = new Map<string, Node>() // 节点ID到节点对象的映射

  // 第一遍遍历：收集所有节点和边
  function collectNodes(
    node: GraphNode,
    parentId: string | undefined
  ): string | null {
    // 如果是文件类型节点且应该被隐藏，跳过该节点及其子节点
    if (node.node_type === 'file_type' && shouldHideFileType(node.name)) {
      return null
    }
    
    const originalId = node.node_type === 'file_type' 
      ? node.file_type_id 
      : node.service_id
    
    let nodeId: string
    if (originalId) {
      const key = `${node.node_type}-${originalId}`
      if (nodeIdMap.has(key)) {
        nodeId = nodeIdMap.get(key)!
        // 如果已存在，仍然需要处理边的关系
        if (parentId) {
          flowEdges.push({
            id: `edge-${parentId}-${nodeId}`,
            source: parentId,
            target: nodeId,
            type: 'smoothstep',
            animated: false,
            markerEnd: MarkerType.ArrowClosed,
            style: { ...defaultEdgeStyle },
            data: { isActive: false },
            class: ''
          })
        }
        return nodeId
      } else {
        nodeId = node.node_type === 'file_type' 
          ? `filetype-${originalId}`
          : `service-${originalId}`
        nodeIdMap.set(key, nodeId)
      }
    } else {
      nodeId = node.node_type === 'file_type' 
        ? `filetype-${nodeIdCounter++}`
        : `service-${nodeIdCounter++}`
    }
    
    // 如果节点已存在，跳过创建
    if (nodeMap.has(nodeId)) {
      if (parentId) {
        flowEdges.push({
          id: `edge-${parentId}-${nodeId}`,
          source: parentId,
          target: nodeId,
          type: 'smoothstep',
          animated: false,
          markerEnd: MarkerType.ArrowClosed,
          style: { ...defaultEdgeStyle },
          data: { isActive: false },
          class: ''
        })
      }
      return nodeId
    }
    
    // 创建节点（位置稍后计算）
    const flowNode: Node = {
      id: nodeId,
      type: node.node_type === 'file_type' ? 'fileTypeNode' : 'serviceNode',
      position: { x: 0, y: 0 },
      data: {
        label: node.name || '未命名',
        description: node.description || '',
        nodeType: node.node_type,
        originalId: originalId,
        isSelected: false,
        isAdjacent: false,
        isDimmed: false
      }
    }
    
    flowNodes.push(flowNode)
    nodeMap.set(nodeId, flowNode)
    
    // 如果有父节点，创建有向边（带箭头）
    if (parentId) {
      flowEdges.push({
        id: `edge-${parentId}-${nodeId}`,
        source: parentId,
        target: nodeId,
        type: 'smoothstep',
        animated: false,
        markerEnd: MarkerType.ArrowClosed,
        style: { ...defaultEdgeStyle },
        data: { isActive: false },
        class: ''
      })
    }
    
    // 递归处理子节点
    if (node.children && node.children.length > 0) {
      node.children.forEach(child => {
        collectNodes(child, nodeId)
      })
    }
    
    return nodeId
  }

  // 收集所有节点和边
  roots.forEach(root => {
    collectNodes(root, undefined)
  })

  // 第二遍：使用拓扑排序计算节点层级，确保所有边从左到右
  // 构建图的邻接表（出边）
  const outEdges = new Map<string, string[]>()
  const inEdges = new Map<string, string[]>()
  
  flowNodes.forEach(node => {
    outEdges.set(node.id, [])
    inEdges.set(node.id, [])
  })
  
  flowEdges.forEach(edge => {
    const source = edge.source
    const target = edge.target
    outEdges.get(source)!.push(target)
    inEdges.get(target)!.push(source)
  })
  
  // 拓扑排序计算层级
  const nodeLevelMap = new Map<string, number>()
  const visited = new Set<string>()
  const processing = new Set<string>()
  
  // 计算每个节点的层级（使用DFS，确保所有边的源节点层级 < 目标节点层级）
  function calculateLevel(nodeId: string): number {
    if (nodeLevelMap.has(nodeId)) {
      return nodeLevelMap.get(nodeId)!
    }
    
    // 检查是否有循环依赖（虽然理论上不应该有）
    if (processing.has(nodeId)) {
      return 0
    }
    
    processing.add(nodeId)
    
    // 找到所有指向该节点的节点，取最大层级+1
    const predecessors = inEdges.get(nodeId) || []
    let maxLevel = -1
    
    if (predecessors.length === 0) {
      // 没有前驱节点，层级为0（最左侧）
      maxLevel = 0
    } else {
      // 有前驱节点，层级为所有前驱节点最大层级+1
      predecessors.forEach(predId => {
        const predLevel = calculateLevel(predId)
        maxLevel = Math.max(maxLevel, predLevel)
      })
      maxLevel += 1
    }
    
    processing.delete(nodeId)
    visited.add(nodeId)
    nodeLevelMap.set(nodeId, maxLevel)
    
    return maxLevel
  }
  
  // 为所有节点计算层级
  flowNodes.forEach(node => {
    if (!visited.has(node.id)) {
      calculateLevel(node.id)
    }
  })
  
  // 按层级分组节点
  const nodesByLevel = new Map<number, Node[]>()
  flowNodes.forEach(node => {
    const level = nodeLevelMap.get(node.id) || 0
    if (!nodesByLevel.has(level)) {
      nodesByLevel.set(level, [])
    }
    nodesByLevel.get(level)!.push(node)
  })

  // 布局参数 - 增加间距让布局更展开
  const horizontalSpacing = 400 // 水平间距（从左到右）
  const verticalSpacing = 150 // 垂直间距

  // 为每层节点分配位置
  nodesByLevel.forEach((levelNodes, level) => {
    // 按节点ID排序，确保布局稳定
    levelNodes.sort((a, b) => a.id.localeCompare(b.id))
    
    const totalHeight = (levelNodes.length - 1) * verticalSpacing
    const startY = -totalHeight / 2
    
    levelNodes.forEach((node, index) => {
      node.position.x = level * horizontalSpacing
      node.position.y = startY + index * verticalSpacing
    })
  })

  return { nodes: flowNodes, edges: flowEdges }
}

/**
 * 加载关系图数据
 */
async function loadGraph() {
  try {
    loading.value = true
    error.value = ''
    
    const depth = fileTypeId.value && depthLimit.value !== undefined 
      ? depthLimit.value 
      : undefined
    
    const response = await getProjectServiceFileTypeGraph(
      projectId.value,
      fileTypeId.value,
      depth
    )
    
    graphData.value = response.roots || []
    
    // 转换为 vue-flow 格式
    const { nodes: flowNodes, edges: flowEdges } = convertGraphToFlowData(graphData.value)
    
    // 使用 nextTick 优化渲染性能
    await nextTick()
    nodes.value = flowNodes
    edges.value = flowEdges
  } catch (err: any) {
    console.error('Failed to load graph:', err)
    error.value = err.message || '加载关系图失败'
    ElMessage.error(error.value)
  } finally {
    loading.value = false
  }
}

/**
 * 刷新关系图
 */
function refreshGraph() {
  loadGraph()
}

/**
 * 返回服务管理页面
 */
function goBack() {
  router.push('/services')
}

/**
 * 处理节点点击事件
 */
function handleNodeClick(event: { node: Node }) {
  const node = event.node
  if (!node || !node.data) return

  const nodeType = node.data.nodeType
  const originalId = node.data.originalId

  if (!nodeType || !originalId) return

  selectedNodeId.value = node.id
  selectedNodeType.value = nodeType

  updateHighlights(node.id)

  if (nodeType === 'service') {
    selectedServiceId.value = originalId
    selectedFileTypeId.value = null
    loadServiceDetail(originalId)
  } else if (nodeType === 'file_type') {
    selectedFileTypeId.value = originalId
    selectedServiceId.value = null
    selectedService.value = null
  }
}

/**
 * 加载服务详情
 */
async function loadServiceDetail(serviceId: string) {
  try {
    serviceLoading.value = true
    serviceError.value = ''
    selectedService.value = await getService(serviceId)
  } catch (err: any) {
    console.error('Failed to load service detail:', err)
    serviceError.value = err.message || '加载服务详情失败'
    selectedService.value = null
  } finally {
    serviceLoading.value = false
  }
}

/**
 * 关闭侧边栏
 */
function closeSidebar() {
  selectedNodeId.value = null
  selectedNodeType.value = null
  selectedServiceId.value = null
  selectedFileTypeId.value = null
  selectedService.value = null
  serviceError.value = ''

  resetHighlights()
}

/**
 * 点击空白画布时关闭侧边栏并清除高亮
 */
function handlePaneClick() {
  closeSidebar()
}

/**
 * 重置所有节点的高亮状态
 */
function resetHighlights() {
  nodes.value = nodes.value.map(node => ({
    ...node,
    data: {
      ...node.data,
      isSelected: false,
      isAdjacent: false,
      isDimmed: false
    }
  }))

  edges.value = edges.value.map(edge => ({
    ...edge,
    style: { ...defaultEdgeStyle },
    data: { ...edge.data, isActive: false }
  }))
}

/**
 * 根据选中节点高亮自身与相邻节点
 */
function updateHighlights(activeNodeId: string) {
  const adjacentMap = new Map<string, boolean>()
  edges.value.forEach(edge => {
    if (edge.source === activeNodeId) {
      adjacentMap.set(edge.target, true)
    }
    if (edge.target === activeNodeId) {
      adjacentMap.set(edge.source, true)
    }
  })

  nodes.value = nodes.value.map(node => {
    const isSelected = node.id === activeNodeId
    const isAdjacent = adjacentMap.has(node.id)
    const isDimmed = !isSelected && !isAdjacent
    return {
      ...node,
      data: {
        ...node.data,
        isSelected,
        isAdjacent: !isSelected && isAdjacent,
        isDimmed
      }
    }
  })

  edges.value = edges.value.map(edge => {
    const isActive = edge.source === activeNodeId || edge.target === activeNodeId
    return {
      ...edge,
      style: isActive ? { ...activeEdgeStyle } : { ...defaultEdgeStyle },
      data: { ...edge.data, isActive }
    }
  })
}

/**
 * 处理服务编辑
 */
function handleServiceEdit(service: Service) {
  router.push(`/services/edit/${service.service_id}`)
}

/**
 * 加载项目列表
 */
async function loadProjects() {
  try {
    projectsLoading.value = true
    projects.value = await getProjectList(0, 100)
  } catch (err: any) {
    console.error('Failed to load projects:', err)
    ElMessage.error(err.message || '加载项目列表失败')
  } finally {
    projectsLoading.value = false
  }
}

/**
 * 加载项目信息
 */
async function loadProjectInfo() {
  if (!projectId.value) return
  
  try {
    projectLoading.value = true
    projectInfo.value = await getProject(projectId.value)
  } catch (err: any) {
    console.error('Failed to load project info:', err)
    ElMessage.error(err.message || '加载项目信息失败')
  } finally {
    projectLoading.value = false
  }
}

/**
 * 加载文件类型列表
 */
async function loadFileTypes() {
  try {
    fileTypesLoading.value = true
    fileTypes.value = await getFileTypes({ force: false })
  } catch (err: any) {
    console.error('Failed to load file types:', err)
    ElMessage.error(err.message || '加载文件类型列表失败')
  } finally {
    fileTypesLoading.value = false
  }
}

/**
 * 处理项目选择变化
 */
function handleProjectChange(value: string | null) {
  const query: Record<string, string> = {}
  if (value) {
    query.projectId = value
  }
  if (fileTypeId.value) {
    query.fileTypeId = fileTypeId.value
  }
  
  // 更新路由参数
  router.push({
    path: route.path,
    query
  })
}

/**
 * 处理文件类型选择变化
 */
function handleFileTypeChange(value: string | null) {
  const query: Record<string, string> = {}
  if (projectId.value) {
    query.projectId = projectId.value
  }
  if (value) {
    query.fileTypeId = value
  }
  
  // 更新路由参数
  router.push({
    path: route.path,
    query
  })
}

/**
 * 打开配置对话框
 */
function openConfigDialog() {
  hiddenFileTypesText.value = hiddenFileTypes.value.join('\n')
  showConfigDialog.value = true
}

/**
 * 关闭配置对话框
 */
function handleConfigDialogClose() {
  showConfigDialog.value = false
}

/**
 * 恢复默认配置
 */
function resetToDefault() {
  hiddenFileTypesText.value = defaultHiddenFileTypes.join('\n')
}

/**
 * 保存隐藏文件类型配置
 */
function saveHiddenFileTypes() {
  const lines = hiddenFileTypesText.value
    .split('\n')
    .map(line => line.trim())
    .filter(line => line.length > 0)
    .map(line => line.toLowerCase().replace(/^\.+/, '')) // 移除开头的点号
  
  hiddenFileTypes.value = lines
  saveHiddenFileTypesToStorage(lines)
  showConfigDialog.value = false
  ElMessage.success('配置已保存')
  
  // 重新加载图表以应用新的隐藏配置
  loadGraph()
}


// 初始化选中的项目ID和文件类型ID（从路由参数）
selectedProjectId.value = projectId.value || null
selectedFileTypeId.value = fileTypeId.value || null

// 监听路由参数变化，同步选中的项目并重新加载项目信息和图表
watch(projectId, (newValue) => {
  selectedProjectId.value = newValue || null
  if (newValue) {
    loadProjectInfo()
    loadGraph()
  } else {
    projectInfo.value = null
    nodes.value = []
    edges.value = []
  }
})

// 监听路由参数变化，同步选中的文件类型并重新加载图表
watch(fileTypeId, (newValue) => {
  selectedFileTypeId.value = newValue || null
  // 当 fileTypeId 变化时，重置深度限制并重新加载图表
  if (newValue) {
    depthLimit.value = undefined
  }
  loadGraph()
})

// 监听深度限制变化（添加防抖）
let debounceTimer: ReturnType<typeof setTimeout> | null = null
watch(depthLimit, () => {
  if (fileTypeId.value) {
    if (debounceTimer) {
      clearTimeout(debounceTimer)
    }
    debounceTimer = setTimeout(() => {
      loadGraph()
    }, 500) // 500ms 防抖
  }
})

// 组件挂载时加载数据
onMounted(() => {
  loadProjects()
  if (projectId.value) {
    loadProjectInfo()
  }
  loadFileTypes()
  loadGraph()
})
</script>

<style scoped>
.service-filetype-graph-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  width: 100%;
  background: var(--bg-secondary);
}

.graph-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  background: var(--bg-primary);
  border-bottom: 1px solid var(--border-color);
  box-shadow: var(--shadow-sm);
  z-index: 10;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 16px;
  flex: 1;
}

.project-select {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 12px;
  border-right: 1px solid var(--border-color);
}

.select-label {
  font-size: 14px;
  color: var(--text-secondary);
  font-weight: 500;
  white-space: nowrap;
}

.project-option {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0; /* 关键：允许 flex 容器收缩 */
  flex: 1;
}

.project-option-name {
  font-size: 14px;
  color: var(--text-primary);
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.project-option-desc {
  font-size: 12px;
  color: var(--text-tertiary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-type-search {
  display: flex;
  align-items: center;
  gap: 8px;
}

.search-label {
  font-size: 14px;
  color: var(--text-secondary);
  font-weight: 500;
  white-space: nowrap;
}

.file-type-option {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0; /* 关键：允许 flex 容器收缩 */
  flex: 1;
}

.file-type-name {
  font-size: 14px;
  color: var(--text-primary);
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-type-desc {
  font-size: 12px;
  color: var(--text-tertiary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.depth-label {
  font-size: 14px;
  color: var(--text-secondary);
  margin-right: 4px;
}

.loading-container {
  padding: 40px;
  background: var(--bg-primary);
  margin: 20px;
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}

.graph-canvas-wrapper {
  flex: 1;
  width: 100%;
  min-height: 0;
  background: var(--bg-secondary);
  position: relative;
  transition: margin-right 0.3s ease;
}

.graph-canvas-wrapper.has-sidebar {
  margin-right: 520px;
}

.graph-canvas {
  width: 100%;
  height: 100%;
  background: var(--bg-secondary);
}

/* 自定义节点样式 */
:deep(.custom-filetype-node) {
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 50%;
  padding: 20px;
  width: 140px;
  height: 140px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-sm);
  transition: all 0.2s ease;
  cursor: pointer;
  box-sizing: border-box;
}

:deep(.custom-filetype-node:hover) {
  transform: translateY(-4px);
  box-shadow: var(--shadow-md);
  border-color: var(--accent-primary);
  background: var(--bg-tertiary);
}

:deep(.custom-filetype-node.is-selected) {
  border-color: var(--accent-primary);
  border-width: 2px;
  box-shadow: 0 8px 20px rgba(59, 130, 246, 0.25);
  background: linear-gradient(145deg, #eef2ff, #e0ecff);
}

:deep(.custom-filetype-node.is-adjacent) {
  border-color: #a5b4fc;
  border-width: 2px;
  box-shadow: 0 4px 12px rgba(148, 163, 184, 0.35);
  background: #f8fafc;
}

:deep(.custom-service-node) {
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: 16px 20px;
  width: 280px;
  min-height: 120px;
  box-shadow: var(--shadow-sm);
  transition: all 0.2s ease;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

:deep(.custom-service-node:hover) {
  transform: translateY(-4px);
  box-shadow: var(--shadow-md);
  border-color: var(--accent-primary);
  background: var(--bg-tertiary);
}

:deep(.custom-service-node.is-selected) {
  border-color: var(--accent-primary);
  border-width: 2px;
  box-shadow: 0 12px 28px rgba(59, 130, 246, 0.3);
  background: linear-gradient(145deg, #eef2ff, #e0ecff);
  transform: translateY(-4px);
}

:deep(.custom-service-node.is-adjacent) {
  border-color: #a5b4fc;
  border-width: 2px;
  box-shadow: 0 8px 18px rgba(148, 163, 184, 0.35);
  background: #f8fafc;
}

:deep(.custom-filetype-node .node-icon) {
  font-size: 28px;
  margin-bottom: 6px;
  text-align: center;
}

:deep(.custom-service-node .node-icon) {
  font-size: 32px;
  margin-bottom: 10px;
  text-align: center;
}

:deep(.node-content) {
  text-align: center;
}

:deep(.custom-filetype-node .node-label) {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: 2px;
  word-break: break-word;
  line-height: 1.3;
  text-align: center;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
}

:deep(.custom-service-node .node-label) {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 6px;
  word-break: break-word;
  line-height: 1.4;
  text-align: center;
}

:deep(.custom-filetype-node .node-description) {
  font-size: 11px;
  color: var(--text-tertiary);
  line-height: 1.2;
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 1;
  line-clamp: 1;
  -webkit-box-orient: vertical;
  text-align: center;
}

:deep(.custom-service-node .node-description) {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.4;
  margin-top: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  text-align: center;
}

/* 边的样式优化 */
:deep(.vue-flow__edge-path) {
  stroke-width: 2;
  stroke: var(--border-hover);
}

:deep(.vue-flow__edge.selected .vue-flow__edge-path) {
  stroke: var(--accent-primary);
  stroke-width: 2.5;
}

/* 箭头样式 */
:deep(.vue-flow__edge-marker) {
  fill: var(--border-hover);
}

:deep(.vue-flow__edge.selected .vue-flow__edge-marker) {
  fill: var(--accent-primary);
}

/* Handle 样式 */
:deep(.vue-flow__handle) {
  width: 10px;
  height: 10px;
  border: 2px solid #fff;
  box-shadow: var(--shadow-sm);
  background: var(--accent-primary);
}

.empty-state {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  height: 400px;
  color: var(--text-tertiary);
  font-size: 16px;
  gap: 12px;
}

.empty-icon {
  font-size: 48px;
  opacity: 0.5;
}

/* 配置对话框样式 */
.config-dialog-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.config-description {
  color: var(--text-secondary);
  font-size: 14px;
  line-height: 1.6;
}

.config-description p {
  margin: 0 0 8px 0;
}

.config-hint {
  color: var(--text-tertiary);
  font-size: 12px;
  font-style: italic;
}

.config-textarea {
  width: 100%;
}

.config-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 8px;
}

/* 右侧详情面板样式 */
.detail-sidebar {
  position: absolute;
  right: 0;
  top: 0;
  bottom: 0;
  width: 520px;
  background: var(--bg-primary);
  border-left: 1px solid var(--border-color);
  box-shadow: -2px 0 8px rgba(0, 0, 0, 0.1);
  display: flex;
  flex-direction: column;
  z-index: 100;
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-lg);
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}

.sidebar-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.sidebar-close {
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  font-size: 1.5rem;
  color: var(--text-secondary);
  cursor: pointer;
  border-radius: 4px;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
}

.sidebar-close:hover {
  background: var(--bg-tertiary);
  color: var(--text-primary);
}

.sidebar-content {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-xl);
}

.sidebar-content .loading-state,
.sidebar-content .error-state {
  padding: 2rem;
}
</style>

