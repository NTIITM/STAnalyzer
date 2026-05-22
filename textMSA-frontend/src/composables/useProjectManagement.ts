/**
 * 项目管理 Composable
 * 提取自 AnalysisPanel.vue 的项目管理逻辑
 */
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { getProjectList, getProject, updateProjectServiceConfig as updateProjectServiceConfigAPI, getProjectFilesRelations, type Project, type ProjectServiceConfig } from '../api/project'
import { Status, type FileNode } from '../api/analysis'
import { useCancelableRequest } from './useCancelableRequest'
import { fetchProjectServices, type ProjectServicesResult, type ProjectService } from '../stores/servicesCache'

/**
 * 判断是否为 AbortError
 */
function isAbortError(error: unknown): boolean {
  if (!error) {
    return false
  }
  if (typeof DOMException !== 'undefined' && error instanceof DOMException && error.name === 'AbortError') {
    return true
  }
  if (typeof error === 'object') {
    const anyError = error as { name?: string; code?: string; message?: string; __CANCEL__?: boolean }
    if (anyError.name === 'CanceledError' || anyError.code === 'ERR_CANCELED' || anyError.__CANCEL__) {
      return true
    }
    if (typeof anyError.message === 'string' && anyError.message.toLowerCase() === 'canceled') {
      return true
    }
  }
  return false
}

export interface UseProjectManagementOptions {
  /**
   * Agent 消息添加回调函数
   */
  onAgentMessage?: (role: string, content: string) => void
  /**
   * DAG 数据更新回调函数
   */
  onDagDataUpdate?: (data: {
    nodes: any[]
    edges: any[]
    files: Record<string, any> | any[]
    executions: any[]
  }) => void
  /**
   * DAG 加载状态更新回调函数
   */
  onDagLoadingChange?: (loading: boolean, error: string) => void
}

export interface UseProjectManagementReturn {
  // state
  projectList: ReturnType<typeof ref<Project[]>>
  currentProjectId: ReturnType<typeof ref<string | null>>
  currentProject: ReturnType<typeof ref<Project | null>>
  projectServices: ReturnType<typeof ref<ProjectService[]>>
  currentServiceId: ReturnType<typeof ref<string | null>>
  
  // methods
  loadProjectList: () => Promise<void>
  selectProject: (projectId: string, skipRouteUpdate?: boolean) => Promise<void>
  backToProjects: () => void
  loadProjectDAGData: (projectId: string | null) => Promise<void>
  loadProjectServices: (projectId: string) => Promise<void>
  selectService: (serviceId: string) => void
  findProjectServiceById: (serviceId: string | null) => ProjectService | undefined
  updateProjectServiceConfig: (service: ProjectService, config: ProjectServiceConfig) => Promise<void>
  removeService: (service: ProjectService) => Promise<void>
}

export function useProjectManagement(
  options: UseProjectManagementOptions = {}
): UseProjectManagementReturn {
  const router = useRouter()
  const { t } = useI18n()
  const { onAgentMessage, onDagDataUpdate, onDagLoadingChange } = options

  // ==================== 状态 ====================
  const projectList = ref<Project[]>([])
  const currentProjectId = ref<string | null>(null)
  const currentProject = ref<Project | null>(null)
  const projectServices = ref<ProjectService[]>([])
  const currentServiceId = ref<string | null>(null)
  const projectServicesRequest = useCancelableRequest<ProjectServicesResult>()

  // ==================== 函数 ====================

  /**
   * 加载项目列表
   */
  async function loadProjectList() {
    try {
      const response = await getProjectList()
      projectList.value = Array.isArray(response) ? response : []
    } catch (error: any) {
      console.error('加载项目列表失败:', error)
      projectList.value = []
    }
  }

  /**
   * 加载项目DAG数据
   */
  async function loadProjectDAGData(projectId: string | null) {
    if (!projectId) {
      if (onDagDataUpdate) {
        onDagDataUpdate({
          nodes: [],
          edges: [],
          files: [],
          executions: []
        })
      }
      if (onDagLoadingChange) {
        onDagLoadingChange(false, '')
      }
      return
    }
    
    if (onDagLoadingChange) {
      onDagLoadingChange(true, '')
    }
    
    try {
      const detail = await getProjectFilesRelations(projectId)
      const files: FileNode[] = Array.isArray(detail?.files) ? detail.files : []
      const relations = Array.isArray(detail?.relations) ? detail.relations : []

      // 构建节点：直接使用文件列表
      const nodes: FileNode[] = files.map((file) => ({
        ...file,
        id: (file as any).file_id || (file as any).id,
        status: (file as any).status || Status.COMPLETED
      }))

      // 构建边：根据 relations 映射 parent -> child
      const edges = relations
        .filter(rel => rel?.parent_file_id && rel?.child_file_id)
        .map(rel => ({
          from: rel.parent_file_id,
          to: rel.child_file_id,
          status: Status.PENDING,
          execution: undefined
        }))

      if (onDagDataUpdate) {
        onDagDataUpdate({
          nodes,
          edges,
          files,
          executions: []
        })
      }
    } catch (error: any) {
      console.error('加载项目DAG数据时出错:', error)
      const errorMessage = t('app.loadDAGError')
      if (onDagLoadingChange) {
        onDagLoadingChange(false, errorMessage)
      }
      if (onDagDataUpdate) {
        onDagDataUpdate({
          nodes: [],
          edges: [],
          files: [],
          executions: []
        })
      }
    } finally {
      if (onDagLoadingChange) {
        onDagLoadingChange(false, '')
      }
    }
  }

  /**
   * 加载项目服务列表
   */
  async function loadProjectServices(projectId: string) {
    if (!projectId) {
      projectServicesRequest.cancel()
      projectServices.value = []
      return
    }

    const requestProjectId = projectId

    try {
      const result = await projectServicesRequest.execute((signal) =>
        fetchProjectServices({
          projectId: requestProjectId,
          signal
        })
      )
      if (currentProjectId.value !== requestProjectId) {
        return
      }
      projectServices.value = result.services ?? []
    } catch (error: unknown) {
      if (isAbortError(error)) {
        return
      }
      console.error('加载项目服务失败:', error)
      if (currentProjectId.value === requestProjectId) {
        projectServices.value = []
      }
    }
  }

  /**
   * 查找项目服务
   */
  function findProjectServiceById(serviceId: string | null): ProjectService | undefined {
    if (!serviceId) {
      return undefined
    }
    return projectServices.value.find((service) => service.service_id === serviceId)
  }

  /**
   * 选择服务（仅高亮，暂不触发其他动作）
   */
  function selectService(serviceId: string) {
    currentServiceId.value = serviceId
  }

  /**
   * 选择项目
   * 
   * @param projectId - 项目ID
   * @param skipRouteUpdate - 是否跳过路由更新（true 表示从路由变化触发，避免循环更新）
   */
  async function selectProject(projectId: string, skipRouteUpdate = false) {
    if (!projectId) return
    
    // 如果已经是当前项目，且是从路由变化触发的（不需要更新路由），则跳过
    // 但如果是用户主动选择（skipRouteUpdate=false），即使项目相同也需要刷新服务列表
    if (currentProjectId.value === projectId && skipRouteUpdate) {
      // 仍然尝试刷新项目服务列表
      try {
        await loadProjectServices(projectId)
      } catch {}
      return
    }
    
    currentProjectId.value = projectId
    currentServiceId.value = null
    
    try {
      // 加载项目详情
      const project = await getProject(projectId)
      currentProject.value = project
      
      // 同步加载项目服务列表
      await loadProjectServices(projectId)
      
      // 更新路由：仅在不是从路由变化触发时更新（避免循环更新）
      if (!skipRouteUpdate) {
        router.push({
          path: '/analysis',
          query: { projectId }
        })
      }
    } catch (error: any) {
      console.error('选择项目失败:', error)
      currentProjectId.value = null
      currentProject.value = null
      projectServices.value = []
    }
  }

  /**
   * 返回项目列表
   */
  function backToProjects() {
    currentProjectId.value = null
    currentProject.value = null
    currentServiceId.value = null
    
    router.push('/analysis')
    if (onAgentMessage) {
      onAgentMessage('agent', t('project.backToProjects'))
    }
  }

  /**
   * 更新项目服务配置
   */
  async function updateProjectServiceConfig(service: ProjectService, config: ProjectServiceConfig): Promise<void> {
    if (!currentProjectId.value || !currentProject.value) {
      throw new Error('No project selected')
    }

    const updated = await updateProjectServiceConfigAPI(currentProjectId.value, config)
    currentProject.value = updated
    projectServices.value = projectServices.value.filter(s => s.service_id !== service.service_id)
    
    if (onAgentMessage) {
      onAgentMessage('agent', `已将服务 ${service.name} 移入项目黑名单`)
    }
  }

  /**
   * 移除服务（加入黑名单）
   */
  async function removeService(service: ProjectService): Promise<void> {
    if (!currentProjectId.value || !currentProject.value) {
      throw new Error('No project selected')
    }

    try {
      const prev: ProjectServiceConfig = currentProject.value.service_config || { mode: 'all', whitelist: [], blacklist: [] }
      const next: ProjectServiceConfig = {
        mode: prev.mode || 'all',
        whitelist: Array.isArray(prev.whitelist) ? prev.whitelist : [],
        blacklist: Array.from(new Set([...(Array.isArray(prev.blacklist) ? prev.blacklist : []), service.service_id]))
      }
      const updated = await updateProjectServiceConfigAPI(currentProjectId.value, next)
      currentProject.value = updated
      projectServices.value = projectServices.value.filter(s => s.service_id !== service.service_id)
      
      if (onAgentMessage) {
        onAgentMessage('agent', `已将服务 ${service.name} 移入项目黑名单`)
      }
    } catch (e: any) {
      console.error('移除服务失败:', e)
      if (onAgentMessage) {
        onAgentMessage('agent', `移除服务失败：${e?.message || '未知错误'}`)
      }
      throw e
    }
  }

  return {
    // state
    projectList,
    currentProjectId,
    currentProject,
    projectServices,
    currentServiceId,
    
    // methods
    loadProjectList,
    selectProject,
    backToProjects,
    loadProjectDAGData,
    loadProjectServices,
    selectService,
    findProjectServiceById,
    updateProjectServiceConfig,
    removeService
  }
}

