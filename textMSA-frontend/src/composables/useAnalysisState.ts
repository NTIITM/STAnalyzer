import { ref, computed } from 'vue'
import type { DagNode, DagEdge } from '../types/dag'
import type { FileNode } from '../api/analysis'
import { Status as AnalysisStatus } from '../api/analysis'
import { isHiddenSystemFile, isAnalysisResultFile } from '../utils/fileType'

/**
 * 分析面板状态管理
 * 统一管理 DAG 数据、文件列表、选中状态等
 */
export function useAnalysisState() {

  // ==================== DAG 数据 ====================
  const dagNodes = ref<DagNode[]>([])
  const dagEdges = ref<DagEdge[]>([])
  const dagFiles = ref<FileNode[]>([])
  const isLoading = ref(false)
  const loadError = ref('')

  const hasDagData = computed(() => dagNodes.value.length > 0)

  // ==================== 文件数据 ====================
  interface DataItem {
    id: string
    name: string
    uploadTime: string
    fileId?: string | null
    description?: string
    fileTypeId?: string | null
  }

  /**
   * 将 dagFiles 转换为 DataItem 格式
   */
  const fileDataList = computed<DataItem[]>(() => {
    const seen = new Set<string>()
    const result: DataItem[] = []

    dagFiles.value.forEach((file: FileNode) => {
      const fileId = (file as any).file_id || (file as any).id || (file as any).fileId
      if (!fileId) return

      // 跳过未完成的文件
      const status = (file as any).status || (file as any).node_status
      if (status && status !== AnalysisStatus.COMPLETED) return

      // 去重
      if (seen.has(fileId)) return
      seen.add(fileId)

      const fileName = file.filename || `File ${fileId}`
      const rawType = (file as any).file_type
      const normalizedType =
        (file as any).file_type_id ||
        (file as any).fileTypeId ||
        (typeof rawType === 'string' ? rawType : rawType?.id) ||
        null

      result.push({
        id: `data_${fileId}`,
        name: fileName,
        uploadTime: new Date().toLocaleString('zh-CN'),
        fileId: fileId,
        description: undefined,
        fileTypeId: normalizedType
      })
    })

    return result
  })

  /**
   * 过滤后的文件列表（只显示可交互的文件）
   */
  const filteredFileDataList = computed<DataItem[]>(() => {
    return fileDataList.value.filter(item => {
      // 过滤掉隐藏文件 (如 gen- 开头)
      if (isHiddenSystemFile(item.name)) return false
      // 仅保留可交互的可视化结果文件
      return isAnalysisResultFile(item.name, item.fileTypeId)
    })
  })

  /**
   * 文件字典（用于快速查找）
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

  // ==================== 选中状态 ====================
  const currentDataId = ref<string | null>(null)
  const currentFileId = ref<string | null>(null)

  // ==================== 方法 ====================
  /**
   * 更新 DAG 数据
   */
  function updateDagData(data: { nodes: DagNode[]; edges: DagEdge[]; files: FileNode[] }) {
    dagNodes.value = data.nodes
    dagEdges.value = data.edges
    dagFiles.value = Array.isArray(data.files) ? data.files : []
  }

  /**
   * 重置 DAG 状态
   */
  function resetDagState() {
    dagNodes.value = []
    dagEdges.value = []
    dagFiles.value = []
    currentDataId.value = null
    currentFileId.value = null
  }

  /**
   * 设置加载状态
   */
  function setLoadingState(loading: boolean, error = '') {
    isLoading.value = loading
    loadError.value = error
  }

  /**
   * 删除文件后更新状态
   */
  function removeFile(fileId: string) {
    dagNodes.value = dagNodes.value.filter(node => node?.id !== fileId)
    dagEdges.value = dagEdges.value.filter(
      edge => edge?.source !== fileId && edge?.target !== fileId
    )
    dagFiles.value = dagFiles.value.filter((file: FileNode) => {
      const fileIdToCheck = file?.file_id
      return fileIdToCheck !== fileId
    })
  }

  return {
    // 状态
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
    // 方法
    updateDagData,
    resetDagState,
    setLoadingState,
    removeFile
  }
}
