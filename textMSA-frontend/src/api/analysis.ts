/**
 * 文件分析流程 API (TypeScript)
 * 节点：文件（显示文件名）
 * 边：算法（显示方法名，包含执行状态和关键参数）
 */
import request from './request'

// ==================== 类型定义 ====================

/**
 * 枚举状态（文件、执行）
 */
export enum NodeType {
  FILE = 'file',
  KNOWLEDGE = 'knowledge'
}
export enum Status {
  PENDING = 'pending',
  RUNNING = 'running',
  COMPLETED = 'completed',
  FAILED = 'failed',
  SKIPPED = 'skipped'
}
/**
 * 文件节点（树形结构中的节点）
 */
export interface FileNode {
  /** 文件ID */
  file_id: string
  /** 文件显示名称（优先使用，用于节点标签显示） */
  filename?: string
  /** 文件类型ID（用于服务筛选） */
  file_type_id?: string
  /** 文件显示名称（优先使用，用于节点标签显示） */
  status: Status

}


/**
 * 分析流程 DAG 结构（从树形结构转换而来，用于可视化）
 */
export interface AnalysisDAG {

  /** 文件节点列表（扁平化） */
  nodes: FileNode[]
  /** 算法边列表（扁平化） */
  edges: Array<{
    from: string
    to: string
    execution?: ExecutionInfo  // 完整的执行信息
  }>
  // /** 执行顺序（拓扑排序后的节点ID列表） */
  // executionOrder?: string[]
  // /** DAG创建时间 */
  // createdAt?: string
  // /** DAG更新时间 */
  // updatedAt?: string
  // /** 当前执行状态 */
  // status?: 'idle' | 'running' | 'completed' | 'failed'
  // /** 总体进度（0-100） */
  // progress?: number
  // /** 总节点数 */
  // totalNodes?: number
  // /** 已完成节点数 */
  // completedNodes?: number
}

/**
 * 简化的树节点（只包含 id, type, children）
 */
export interface SimpleTreeNode {
  /** 节点ID */
  id: string
  /** 节点类型（project 或 file） */
  type: 'project' | 'file' | 'knowledge'
  /** 子节点列表 */
  children?: SimpleTreeNode[]
  /** 状态 */
  status: Status
}

/**
 * 执行记录信息
 */
export interface ExecutionInfo {
  /** 执行ID */
  execution_id: string
  /** 输入文件ID */
  input_file_ids: string[]
  /** 输出文件ID */
  output_file_ids: string[]
  /** 项目ID */
  project_id: string
  /** 状态 */
  status: string
  /** 参数 */
  parameters?: Record<string, any>

  /** 错误信息 */
  error_message?: string
  /** 创建时间 */
  created_at?: string
  /** 开始时间 */
  started_at?: string
  /** 完成时间 */
  completed_at?: string
  /** 持续时间（秒） */
  duration_seconds?: number
}

/**
 * 文件分析响应
 */
export interface FileAnalysisResponsePayload {
  file_id: string
  query: string
  result: string
  success: boolean
  error_message?: string | null
}

export interface AnalyzeFileParams {
  fileId: string
  query: string
}

export interface AnalyzeExecutionParams {
  executionId: string
  query: string
}

/**
 * 统计信息
 */
export interface AnalysisStatistics {
  /** 总文件数 */
  total_files: number
  /** 总执行数 */
  total_executions: number
  /** 已完成文件数 */
  completed_files: number
  /** 已完成执行数 */
  completed_executions: number
  /** 失败执行数 */
  failed_executions: number
  /** 运行中执行数 */
  running_executions: number
}

/**
 * 项目分析流程树形结构（合并多个文件的分析树）
 * 新格式：简化的树结构 + 扁平化的详细信息
 */
export interface ProjectAnalysisTree {
  /** 项目ID */
  project_id: string
  // /** 项目名称 */
  // project_name?: string
  // /** 项目描述 */
  // project_description?: string
  /** 文件ID（项目级别为null） */
  // file_id: string | null
  /** 根节点（简化的树结构，只包含 id, type, children） */
  root: SimpleTreeNode
  /** 文件列表（扁平化，包含完整信息） */
  files: FileNode[]
  /** 执行列表（扁平化，包含完整信息） */
  executions: ExecutionInfo[]
  // /** 统计信息 */
  // statistics: AnalysisStatistics
  // /** 创建时间 */
  // created_at?: string
  // /** 更新时间 */
  // updated_at?: string
  // /** 项目整体状态 */
  // status?: string
  // /** 总节点数 */
  // total_nodes?: number
  // /** 已完成节点数 */
  // completed_nodes?: number
}

/**
 * 获取项目的分析流程树形结构（合并多个文件的分析树）
 * @param projectId - 项目ID
 * @returns 项目分析流程树形结构
 */
export async function getProjectAnalysisTree(projectId: string): Promise<ProjectAnalysisTree> {
  return request({
    url: `/analysis/project/${projectId}/tree`,
    method: 'GET'
  }) as Promise<ProjectAnalysisTree>
}

/**
 * 将树形结构转换为 DAG 格式（用于可视化）
 * @param treeData - 树形结构数据（FileAnalysisTree 或 ProjectAnalysisTree）
 * @returns DAG 格式数据
 */
export function convertAnalysisTreeToDAG(files: FileNode[], executions: ExecutionInfo[]): AnalysisDAG {
  
  const nodes: FileNode[] = []
  const edges: Array<{ from: string; to: string; status: Status; execution?: ExecutionInfo }> = []
  
  
  const toStatus = (s: any): Status => {
    switch ((s || '').toLowerCase()) {
      case 'running': return Status.RUNNING
      case 'completed': return Status.COMPLETED
      case 'failed': return Status.FAILED
      case 'error': return Status.FAILED
      case 'uploaded': return Status.COMPLETED
      default: return Status.PENDING
    }
  }
  files.forEach((file) => {

    // 创建文件节点，包含完整的文件信息
    const fileNode: FileNode & { id?: string } = {
      // 兼容下游 store（需要 id, fileType/file_type, fileName/file_name）
      id: file.file_id,              // 与 edges from/to 使用同一原始ID
      file_id: file.file_id,
      // 保留后端字段命名，便于 store 读取
      file_type_id: file.file_type_id,      // 提取的 file_type_id
      filename: file.filename,
      status: toStatus(file.status),
    }
    nodes.push(fileNode)
  })
  // 根据 executions 构建边（使用 input_file_ids 和 output_file_id/output_file_ids）
  executions.forEach(exec => {
    // 支持 input_file_ids（数组）
    const inputFileIds: string[] = []
    if (exec.input_file_ids && Array.isArray(exec.input_file_ids)) {
      inputFileIds.push(...exec.input_file_ids)
    } 
    // 支持 output_file_ids（数组）
    const outputFileIds: string[] = []
    if (exec.output_file_ids && Array.isArray(exec.output_file_ids)) {
      outputFileIds.push(...exec.output_file_ids)
    } 
    // 为每个输入文件到每个输出文件创建边 
    inputFileIds.forEach((from_id) => {
      outputFileIds.forEach((to_id) => {
        edges.push({
          from: from_id,
          to: to_id,
          status: toStatus(exec.status),
          // 保存完整的执行信息到边（用于tooltip显示）
          execution: exec
        })
      })
    })
  })
  

  return {
    nodes,
    edges,
  }
}

// TODO: 后续可能需要添加更多接口，比如更新执行状态、更新文件状态等

/**
 * 删除执行记录
 * @param executionId - 执行ID
 * @returns 删除的执行ID
 */
export async function deleteExecution(executionId: string): Promise<string> {
  return request({
    url: `/analysis/execution/${executionId}`,
    method: 'DELETE'
  }) as Promise<string>
}

/**
 * 触发文件分析
 * @param params - fileId/query（query 虽后端可选，前端需保证必填）
 */
export async function analyzeFile(params: AnalyzeFileParams): Promise<FileAnalysisResponsePayload> {
  const { fileId, query } = params
  return request({
    url: '/analysis/analyze',
    method: 'POST',
    params: {
      file_id: fileId,
      query
    }
  }) as Promise<FileAnalysisResponsePayload>
}

/**
 * 触发执行分析
 * @param params - executionId（执行ID）和 query（查询内容）
 */
export async function analyzeExecution(params: AnalyzeExecutionParams): Promise<FileAnalysisResponsePayload> {
  const { executionId, query } = params
  return request({
    url: '/analysis/analyze',
    method: 'POST',
    params: {
      execution_id: executionId,
      query
    }
  }) as Promise<FileAnalysisResponsePayload>
}

