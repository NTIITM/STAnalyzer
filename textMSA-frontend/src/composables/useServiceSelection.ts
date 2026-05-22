/**
 * 服务选择 Composable
 * 管理服务选择相关的状态和逻辑
 */
import { ref, computed, watch } from 'vue'
import { getServiceList, type Service } from '../api/service'

export interface UseServiceSelectionOptions {
  onModeChange?: () => void
}

export interface UseServiceSelectionReturn {
  // 状态
  serviceMode: ReturnType<typeof ref<'all' | 'whitelist'>>
  selectedServiceIds: ReturnType<typeof ref<string[]>>
  availableServiceList: ReturnType<typeof ref<Service[]>>
  loadingServices: ReturnType<typeof ref<boolean>>
  serviceError: ReturnType<typeof ref<string>>
  searchServiceKeyword: ReturnType<typeof ref<string>>
  
  // 计算属性
  filteredServiceList: ReturnType<typeof computed<Service[]>>
  
  // 方法
  loadServiceList: () => Promise<void>
  toggleService: (serviceId: string) => void
  removeService: (serviceId: string) => void
  getServiceName: (serviceId: string) => string
  handleServiceModeChange: () => Promise<void>
}

export function useServiceSelection(
  options: UseServiceSelectionOptions = {}
): UseServiceSelectionReturn {
  const { onModeChange } = options

  // ==================== 状态 ====================
  const serviceMode = ref<'all' | 'whitelist'>('all')
  const selectedServiceIds = ref<string[]>([])
  const availableServiceList = ref<Service[]>([])
  const loadingServices = ref(false)
  const serviceError = ref('')
  const searchServiceKeyword = ref('')

  // ==================== 计算属性 ====================

  /**
   * 筛选服务列表（根据搜索关键词）
   */
  const filteredServiceList = computed(() => {
    const keyword = searchServiceKeyword.value.trim().toLowerCase()
    if (!keyword) {
      return availableServiceList.value
    }
    
    return availableServiceList.value.filter(service => {
      const name = (service.name || '').toLowerCase()
      const description = (service.description || '').toLowerCase()
      const serviceId = (service.service_id || '').toLowerCase()
      const version = (service.version || '').toLowerCase()
      
      return name.includes(keyword) || 
             description.includes(keyword) ||
             serviceId.includes(keyword) ||
             version.includes(keyword)
    })
  })

  // ==================== 方法 ====================

  /**
   * 加载服务列表
   */
  async function loadServiceList() {
    try {
      loadingServices.value = true
      serviceError.value = ''
      const result = await getServiceList(undefined, undefined, 0, 100)
      availableServiceList.value = result.services || []
    } catch (err: any) {
      console.error('加载服务列表失败:', err)
      serviceError.value = err.message || '加载服务列表失败'
    } finally {
      loadingServices.value = false
    }
  }

  /**
   * 切换服务选择状态
   */
  function toggleService(serviceId: string) {
    const index = selectedServiceIds.value.indexOf(serviceId)
    if (index > -1) {
      selectedServiceIds.value.splice(index, 1)
    } else {
      selectedServiceIds.value.push(serviceId)
    }
  }

  /**
   * 移除已选服务
   */
  function removeService(serviceId: string) {
    const index = selectedServiceIds.value.indexOf(serviceId)
    if (index > -1) {
      selectedServiceIds.value.splice(index, 1)
    }
  }

  /**
   * 根据ID获取服务名称
   */
  function getServiceName(serviceId: string): string {
    const service = availableServiceList.value.find(s => s.service_id === serviceId)
    return service?.name || serviceId
  }

  /**
   * 处理服务模式变化
   */
  async function handleServiceModeChange() {
    if (serviceMode.value === 'whitelist' && availableServiceList.value.length === 0) {
      await loadServiceList()
    }
    if (onModeChange) {
      onModeChange()
    }
  }

  return {
    // 状态
    serviceMode,
    selectedServiceIds,
    availableServiceList,
    loadingServices,
    serviceError,
    searchServiceKeyword,
    
    // 计算属性
    filteredServiceList,
    
    // 方法
    loadServiceList,
    toggleService,
    removeService,
    getServiceName,
    handleServiceModeChange
  }
}

