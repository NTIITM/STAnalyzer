/**
 * DAG 可视化相关类型定义
 */
import type { Component } from 'vue'
import type { FileNode, ExecutionInfo, Status } from '../api/analysis'
import type { FileType } from './file'

/**
 * DAG 节点（用于 G6 图库可视化）
 */
export interface DagNode {
  /** 节点ID（文件ID） */
  id: string
  /** 文件名 */
  filename?: string
  /** 文件类型 */
  file_type: string | FileType | null
  /** 节点状态 */
  status: string
  /** 节点颜色 */
  color: string
  /** 节点样式 */
  style: {
    fill: string
    stroke: string
    lineWidth?: number
    cursor?: string
  }
}

/**
 * DAG 边（用于 G6 图库可视化）
 */
export interface DagEdge {
  /** 源节点ID */
  source: string
  /** 目标节点ID */
  target: string
  /** 边的状态 */
  status: string
  /** 边的颜色 */
  color: string
  /** 执行信息（可选） */
  execution: ExecutionInfo | null
  /** 执行ID（可选） */
  execution_id: string | null
  /** 边样式 */
  style: {
    stroke: string
    lineWidth?: number
    endArrow?: boolean
    endArrowType?: 'triangle' | 'circle' | 'diamond'
    endArrowSize?: number
  }
  /** 兼容字段：from（向后兼容） */
  from?: string
  /** 兼容字段：to（向后兼容） */
  to?: string
}

/**
 * 原始边数据（从 API 返回的格式）
 */
export interface DagEdgeRaw {
  /** 源节点ID */
  from: string
  /** 目标节点ID */
  to: string
  /** 执行信息（可选） */
  execution?: ExecutionInfo
  /** 状态（可选） */
  status?: Status
}

/**
 * 分析组件类型
 */
export type AnalysisComponent = Component | null

/**
 * 文件节点类型（用于组件间传递）
 */
export type FileNodeType = FileNode

