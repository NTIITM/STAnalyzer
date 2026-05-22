import { ref, shallowRef, markRaw } from 'vue'
import type { Component } from 'vue'
import SpatialTranscriptomics from '../components/analysis/SpatialTranscriptomics.vue'
import SpatialVisualization from '../components/analysis/SpatialVisualization.vue'
import DGEResultsVisualization from '../components/analysis/DGEResultsVisualization.vue'
import CellCommunicationVisualization from '../components/analysis/CellCommunicationVisualization.vue'

export type VisualizationComponentId =
  | 'spatial-transcriptomics'
  | 'spatial-visualization'
  | 'dge-results-visualization'
  | 'cell-communication-visualization'

/**
 * 可视化组件路由管理
 * 负责在 DAG 视图和各种可视化组件之间切换
 */
export function useVisualizationRouter() {
  // 组件映射
  const componentMap: Record<VisualizationComponentId, Component> = {
    'spatial-transcriptomics': markRaw(SpatialTranscriptomics),
    'spatial-visualization': markRaw(SpatialVisualization),
    'dge-results-visualization': markRaw(DGEResultsVisualization),
    'cell-communication-visualization': markRaw(CellCommunicationVisualization)
  }

  const activeComponent = shallowRef<Component | null>(null)
  const currentFileId = ref<string | null>(null)

  /**
   * 导航到指定的可视化组件
   */
  function navigateToVisualization(componentId: VisualizationComponentId, fileId: string) {
    activeComponent.value = componentMap[componentId] || null
    currentFileId.value = fileId || null
  }

  /**
   * 返回 DAG 视图
   */
  function navigateToDAG() {
    activeComponent.value = null
    currentFileId.value = null
  }

  /**
   * 根据文件类型确定要使用的可视化组件
   */
  function getVisualizationComponentId(
    fileName: string,
    fileTypeId?: string | null
  ): VisualizationComponentId {
    const normalizedName = (fileName || '').toLowerCase()
    const isDge =
      fileTypeId === 'dge_results_csv' ||
      (normalizedName.endsWith('.csv') && normalizedName.includes('dge'))
    const isLigrec = fileTypeId === 'ligrec_interactions_csv'

    if (isLigrec) {
      return 'cell-communication-visualization'
    } else if (isDge) {
      return 'dge-results-visualization'
    } else {
      return 'spatial-visualization'
    }
  }

  return {
    activeComponent,
    currentFileId,
    navigateToVisualization,
    navigateToDAG,
    getVisualizationComponentId
  }
}
