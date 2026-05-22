/**
 * 项目配置 Composable
 * 管理项目配置的核心状态和业务逻辑
 */
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { 
  getProject, 
  createProject,
  updateProject, 
  updateProjectServiceConfig,
  type ProjectServiceConfig,
  type ProjectCreateRequest,
  type Project
} from '../api/project'

export interface FormData {
  name: string
  description: string
  serviceIds: string[]
}

export interface UseProjectConfigOptions {
  projectId?: string | null
  isEditMode: boolean
  onLoadComplete?: (project: Project) => void
}

export interface UseProjectConfigReturn {
  // 状态
  loading: ReturnType<typeof ref<boolean>>
  error: ReturnType<typeof ref<string>>
  saving: ReturnType<typeof ref<boolean>>
  formData: ReturnType<typeof ref<FormData>>
  
  // 计算属性
  isFormValid: ReturnType<typeof computed<boolean>>
  
  // 方法
  loadProjectData: () => Promise<void>
  saveProject: (options: {
    serviceMode: 'all' | 'whitelist'
    selectedServiceIds: string[]
  }) => Promise<void>
  resetForm: () => void
}

export function useProjectConfig(
  options: UseProjectConfigOptions
): UseProjectConfigReturn {
  const router = useRouter()
  const { t } = useI18n()
  const { projectId, isEditMode, onLoadComplete } = options

  // ==================== 状态 ====================
  const loading = ref(false)
  const error = ref('')
  const saving = ref(false)

  const formData = ref<FormData>({
    name: '',
    description: '',
    serviceIds: []
  })

  // ==================== 计算属性 ====================

  const isFormValid = computed(() => {
    return formData.value.name.trim().length > 0
  })

  // ==================== 方法 ====================

  /**
   * 加载项目数据
   */
  async function loadProjectData() {
    // 创建模式：不加载数据
    if (!isEditMode) {
      return
    }

    if (!projectId) {
      error.value = '项目ID不存在'
      return
    }

    try {
      loading.value = true
      error.value = ''
      const project = await getProject(projectId)
      
      formData.value = {
        name: project.name || '',
        description: project.description || '',
        serviceIds: (project as any).service_ids || []
      }

      if (onLoadComplete) {
        onLoadComplete(project)
      }
    } catch (err: any) {
      console.error('加载项目数据失败:', err)
      error.value = err.message || '加载失败'
    } finally {
      loading.value = false
    }
  }

  /**
   * 保存项目配置
   */
  async function saveProject(options: {
    serviceMode: 'all' | 'whitelist'
    selectedServiceIds: string[]
  }) {
    if (!isFormValid.value) {
      return
    }

    try {
      saving.value = true

      // 同步已选服务ID列表到 formData
      formData.value.serviceIds = [...options.selectedServiceIds]

      if (isEditMode && projectId) {
        // 编辑模式：更新项目配置
        // 更新基本信息
        await updateProject(projectId, {
          name: formData.value.name,
          description: formData.value.description || undefined
        })

        // 更新服务配置
        const serviceConfig: ProjectServiceConfig = {
          mode: options.serviceMode,
          whitelist: options.serviceMode === 'whitelist' ? options.selectedServiceIds : [],
          blacklist: []
        }
        await updateProjectServiceConfig(projectId, serviceConfig)

        // 显示成功消息并返回
        if (window.showMessage) {
          window.showMessage.success(t('project.actions.saveSuccess'))
        }
        router.push('/analysis')
      } else {
        // 创建模式：创建新项目
        const projectData: ProjectCreateRequest = {
          name: formData.value.name,
          description: formData.value.description || undefined
        }
        const newProject = await createProject(projectData)
        
        // 显示成功消息并跳转到新创建的项目
        if (window.showMessage) {
          window.showMessage.success(t('project.actions.saveSuccess'))
        }
        // 跳转到分析页面并自动选中新创建的项目
        router.push(`/analysis?projectId=${newProject.project_id}`)
      }
    } catch (err: any) {
      console.error('保存项目配置失败:', err)
      const errorMsg = err.detail || err.message || '保存失败'
      if (window.showMessage) {
        window.showMessage.error(`${t('project.actions.saveFailed')}: ${errorMsg}`)
      } else {
        alert(`${t('project.actions.saveFailed')}: ${errorMsg}`)
      }
    } finally {
      saving.value = false
    }
  }

  /**
   * 重置表单
   */
  function resetForm() {
    formData.value = {
      name: '',
      description: '',
      serviceIds: []
    }
    error.value = ''
  }

  return {
    // 状态
    loading,
    error,
    saving,
    formData,
    
    // 计算属性
    isFormValid,
    
    // 方法
    loadProjectData,
    saveProject,
    resetForm
  }
}

