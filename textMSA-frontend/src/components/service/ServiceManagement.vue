<template>
  <div class="service-management-container">
    <div class="page-header">
      <div class="page-header-left">
        <div>
          <h1>{{ $t('service.management') }}</h1>
        </div>
      </div>
      <div class="page-header-right">
        <el-button type="default" @click="showGraph">
          <Icon name="diagram" size="sm" />
          <span>{{ $t('service.graph') }}</span>
        </el-button>
        <el-button type="primary" @click="showCreateService">
          <Icon name="plus" size="sm" />
          <span>{{ $t('service.create') }}</span>
        </el-button>
      </div>
    </div>

    <!-- 筛选栏 -->
    <div class="service-filters">
      <div class="scope-tabs">
        <button 
          class="scope-tab"
          :class="{ active: visibilityFilter === 'private' }"
          @click="setVisibility('private')"
        >
          <!-- lock icon -->
          <svg xmlns="http://www.w3.org/2000/svg" class="icon icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 1 0-9 0v3.75m-.75 11.25h10.5A2.25 2.25 0 0 0 19.5 19.5v-6.75A2.25 2.25 0 0 0 17.25 10.5H6.75A2.25 2.25 0 0 0 4.5 12.75V19.5a2.25 2.25 0 0 0 2.25 2.25Z" />
          </svg>
          <span>{{ $t('service.visibility.private') }}</span>
          <span class="tab-count">{{ visibilityCounts.private }}</span>
        </button>
        <button 
          class="scope-tab"
          :class="{ active: visibilityFilter === 'public' }"
          @click="setVisibility('public')"
        >
          <!-- globe icon -->
          <svg xmlns="http://www.w3.org/2000/svg" class="icon icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 21a9.004 9.004 0 0 0 8.716-6.747M12 21a9.004 9.004 0 0 1-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 0 1 7.843 4.582M12 3a8.997 8.997 0 0 0-7.843 4.582m15.686 0A11.953 11.953 0 0 1 12 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0 1 21 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0 1 12 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 0 1 3 12c0-1.605.42-3.113 1.157-4.418" />
          </svg>
          <span>{{ $t('service.visibility.public') }}</span>
          <span class="tab-count">{{ visibilityCounts.public }}</span>
        </button>
        <button 
          class="scope-tab"
          :class="{ active: visibilityFilter === 'system' }"
          @click="setVisibility('system')"
        >
          <!-- shield/check icon -->
          <svg xmlns="http://www.w3.org/2000/svg" class="icon icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75 11.25 15 15 9.75m-3-7.036A11.959 11.959 0 0 1 3.598 6 11.99 11.99 0 0 0 3 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285Z" />
          </svg>
          <span>{{ $t('service.visibility.system') }}</span>
          <span class="tab-count">{{ visibilityCounts.system }}</span>
        </button>
      </div>
      <el-button @click="loadServices">{{ $t('common.refresh') }}</el-button>
    </div>

    <!-- Service列表 -->
    <div v-if="loading" class="loading-state">
      <el-skeleton :rows="4" animated />
    </div>
    <div v-else-if="error" class="error-state">
      <el-alert :title="error" type="error" show-icon :closable="false" />
      <el-button class="retry-btn" @click="loadServices">{{ $t('common.retry') }}</el-button>
    </div>
    <div v-else-if="services.length === 0" class="empty-state">
      <span>{{ $t('service.noServices') }}</span>
      <el-button type="primary" @click="showCreateService">{{ $t('service.createFirst') }}</el-button>
    </div>
    <div v-else class="service-list" :class="{ 'has-sidebar': selectedServiceId }">
      <div 
        v-for="service in services" 
        :key="service.service_id"
        class="service-card"
        :class="{ active: selectedServiceId === service.service_id }"
        @click="selectService(service.service_id)"
      >
        <div class="service-card-header">
          <div class="service-title">
            <span class="service-icon">{{ getVisibilityIcon(service.visibility) }}</span>
            <span class="service-name">{{ service.name }}</span>
            <span class="service-visibility-badge" :class="`visibility-${service.visibility || 'private'}`">
              {{ getVisibilityLabel(service.visibility) }}
            </span>
          </div>
          <div class="service-actions" @click.stop>
            <button 
              class="action-btn" 
              @click="showEditService(service)"
              :disabled="isEditDisabled(service)"
              :title="$t('common.edit')"
            >
              <Icon name="edit" size="sm" />
            </button>
            <button 
              class="action-btn" 
              @click="showExecuteService(service)"
              :title="$t('service.execute')"
            >
              <Icon name="execute" size="sm" />
            </button>
            <button 
              v-if="service.visibility !== 'system'"
              class="action-btn"
              :class="service.visibility === 'public' ? 'action-btn-warning' : 'action-btn-success'"
              @click="toggleVisibility(service)"
              :title="service.visibility === 'public' ? $t('service.actions.unpublish', '下架') : $t('service.actions.publish', '公开分享')"
            >
              <span v-if="service.visibility === 'public'" style="font-size: 14px;">🔒</span>
              <span v-else style="font-size: 14px;">🌐</span>
            </button>
            <button 
              class="action-btn action-btn-danger" 
              @click="confirmDeleteService(service)"
              :disabled="isDeleteDisabled(service)"
              :title="$t('common.delete')"
            >
              <Icon name="delete" size="sm" />
            </button>
          </div>
        </div>
        <div class="service-card-body">
          <div class="service-info-item">
            <span class="info-label">ID:</span>
            <span class="info-value">{{ service.service_id }}</span>
          </div>
          <div v-if="service.description" class="service-info-item">
            <span class="info-label">{{ $t('service.form.description') }}:</span>
            <span class="info-value">{{ service.description }}</span>
          </div>
          <div class="service-info-item">
            <span class="info-label">{{ $t('service.form.version') }}:</span>
            <span class="info-value">{{ service.version }}</span>
          </div>
          <div class="service-info-item">
            <span class="info-label">URL:</span>
            <span class="info-value info-value-url">{{ service.baseurl }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Service详情/执行/执行记录面板 -->
    <div v-if="selectedServiceId" class="service-sidebar">
      <div class="sidebar-header">
        <div class="sidebar-tabs">
          <button 
            class="tab-btn"
            :class="{ active: activeTab === 'detail' }"
            @click="activeTab = 'detail'"
          >
            {{ $t('service.detail.basicInfo') }}
          </button>
          <button 
            class="tab-btn"
            :class="{ active: activeTab === 'execute' }"
            @click="activeTab = 'execute'"
          >
            {{ $t('service.execute.title') }}
          </button>
          <button 
            class="tab-btn"
            :class="{ active: activeTab === 'executions' }"
            @click="activeTab = 'executions'"
          >
            {{ $t('service.execution.list') }}
          </button>
        </div>
        <button class="sidebar-close" @click="closeSidebar">
          <Icon name="close" size="md" />
        </button>
      </div>
      <div class="sidebar-content">
        <ServiceDetail 
          v-if="activeTab === 'detail' && selectedService"
          :service="selectedService"
          @edit="showEditService"
        />
        <ServiceExecute 
          v-if="activeTab === 'execute' && selectedService && !requiresMultiFile(selectedService)"
          :service="selectedService"
          @executed="handleServiceExecuted"
        />
        <div 
          v-else-if="activeTab === 'execute' && selectedService"
          class="execute-redirect"
        >
          <p class="execute-redirect__title">
            {{ $t('service.execute.title') }}（多文件模式）
          </p>
          <p class="execute-redirect__desc">
            {{ $t('service.execute.multiFileHint') || '此服务需要多个输入，请在独立页面完成执行。' }}
          </p>
          <el-button type="primary" @click="goServiceExecutePage(selectedService)">
            {{ $t('service.execute.openStandalone') || '前往执行页面' }}
          </el-button>
        </div>
        <ExecutionList 
          v-if="activeTab === 'executions'"
          :serviceId="selectedServiceId"
          @refresh="loadServices"
        />
      </div>
    </div>

  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElAlert, ElButton, ElSkeleton, ElMessage, ElMessageBox } from 'element-plus'
import { getServiceList, deleteService, updateService, type Service } from '../../api/service'
import ServiceDetail from './ServiceDetail.vue'
import ServiceExecute from './ServiceExecute.vue'
import ExecutionList from './ExecutionList.vue'
import Icon from '../common/Icon.vue'

const router = useRouter()
const route = useRoute()
const { t } = useI18n()

const services = ref<Service[]>([])
const allServices = ref<Service[]>([])  // unfiltered, used for tab counts
const loading = ref(false)
const error = ref('')
const selectedServiceId = ref<string | null>(null)
const activeTab = ref<'detail' | 'execute' | 'executions'>('detail')
const visibilityFilter = ref<'private' | 'public' | 'system' | ''>('')
const visibilityCounts = computed(() => {
  const counts = { private: 0, public: 0, system: 0 }
  for (const s of allServices.value) {
    if (s.visibility === 'public') counts.public += 1
    else if (s.visibility === 'system') counts.system += 1
    else counts.private += 1
  }
  return counts
})

const selectedService = computed(() => {
  return services.value.find(s => s.service_id === selectedServiceId.value) || null
})

function requiresMultiFile(service: Service) {
  const accepted = (service as any).accepted_files
  if (!accepted) return false
  return Object.keys(accepted).length > 1
}

function goServiceExecutePage(service: Service) {
  router.push({
    name: 'ServiceExecutePage',
    params: { serviceId: service.service_id },
    query: { origin: 'service' }
  })
}

/**
 * 加载Service列表
 */
async function loadServices() {
  try {
    loading.value = true
    error.value = ''
    // Load filtered list (for display)
    const result = await getServiceList(
      visibilityFilter.value || undefined
    )
    console.log(result)
    services.value = result.services || []
    // Load all services (unfiltered, for tab counts) - only when no filter applied or always refresh
    if (!visibilityFilter.value) {
      allServices.value = services.value
    } else {
      // Load unfiltered in background for counts
      getServiceList(undefined).then(r => {
        allServices.value = r.services || []
      }).catch(() => {})
    }
  } catch (err: any) {
    console.error('Failed to load service list:', err)
    error.value = err.message || t('service.loadFailed')
  } finally {
    loading.value = false
  }
}

function setVisibility(next: 'private' | 'public' | 'system') {
  if (visibilityFilter.value === next) {
    return
  }
  visibilityFilter.value = next
  loadServices()
}

/**
 * 选择Service
 */
function selectService(serviceId: string) {
  selectedServiceId.value = serviceId
  activeTab.value = 'detail'
}

/**
 * 关闭侧边栏
 */
function closeSidebar() {
  selectedServiceId.value = null
}

/**
 * 显示创建Service对话框
 */
function showCreateService() {
  router.push('/services/create')
}

/**
 * 显示关系图
 */
function showGraph() {
  const projectId = route.query.projectId as string | undefined
  router.push({
    path: '/services/graph',
    query: projectId ? { projectId } : {}
  })
}

/**
 * 显示编辑Service对话框
 */
function showEditService(service: Service) {
  router.push(`/services/edit/${service.service_id}`)
}

/**
 * 显示执行Service
 */
function showExecuteService(service: Service) {
  selectedServiceId.value = service.service_id
  activeTab.value = 'execute'
}


/**
 * 确认删除Service
 */
async function confirmDeleteService(service: Service) {
  try {
    await ElMessageBox.confirm(
      t('service.actions.confirmDelete', { name: service.name }),
      t('service.actions.deleteTitle', '删除服务'),
      {
        confirmButtonText: t('app.confirm', '确认'),
        cancelButtonText: t('app.cancel', '取消'),
        type: 'warning',
      }
    )
  } catch {
    return  // user cancelled
  }

  try {
    await deleteService(service.service_id)
    if (selectedServiceId.value === service.service_id) {
      selectedServiceId.value = null
    }
    ElMessage.success(t('service.actions.deleteSuccess', '删除成功'))
    await loadServices()
  } catch (err: any) {
    ElMessage.error(`${t('service.actions.deleteFailed')}: ${err.message || t('app.unknownError')}`)
  }
}

/**
 * 快速切换 visibility（一键公开/下架）
 */
async function toggleVisibility(service: Service) {
  const isPublic = service.visibility === 'public'
  const nextVis = isPublic ? 'private' : 'public'
  const actionLabel = isPublic
    ? t('service.actions.unpublish', '下架')
    : t('service.actions.publish', '公开分享')

  try {
    await ElMessageBox.confirm(
      isPublic
        ? t('service.actions.confirmUnpublish', { name: service.name }, `确认将「${service.name}」从社区下架？`)
        : t('service.actions.confirmPublish', { name: service.name }, `确认将「${service.name}」公开分享到社区？`),
      actionLabel,
      {
        confirmButtonText: t('app.confirm', '确认'),
        cancelButtonText: t('app.cancel', '取消'),
        type: isPublic ? 'warning' : 'info',
      }
    )
  } catch {
    return  // cancelled
  }

  try {
    await updateService(service.service_id, { visibility: nextVis })
    ElMessage.success(
      isPublic
        ? t('service.actions.unpublishSuccess', '已成功下架')
        : t('service.actions.publishSuccess', '已成功公开分享到社区')
    )
    await loadServices()
  } catch (err: any) {
    ElMessage.error(`${actionLabel}${t('app.failed', '失败')}: ${err.message || t('app.unknownError')}`)
  }
}

/**
 * Service执行后处理
 */
function handleServiceExecuted() {
  activeTab.value = 'executions'
  // 执行记录列表会自动刷新
}

/**
 * 基于可见性获取图标
 */
function getVisibilityIcon(visibility?: Service['visibility']): string {
  switch (visibility) {
    case 'system': return '🛠️'
    case 'public': return '🌐'
    case 'private':
    default: return '🔒'
  }
}

/**
 * 可见性标签
 */
function getVisibilityLabel(visibility?: Service['visibility']): string {
  switch (visibility) {
    case 'system': return t('service.visibility.system')
    case 'public': return t('service.visibility.public')
    case 'private':
    default: return t('service.visibility.private')
  }
}

/**
 * 操作权限（基础规则）
 */
function isEditDisabled(service: Service): boolean {
  return service.visibility === 'system'
}

function isDeleteDisabled(service: Service): boolean {
  return service.visibility === 'system'
}

onMounted(() => {
  loadServices()
})
</script>

<style scoped>
.service-management-container {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100%;
  background: var(--bg-secondary);
  overflow: hidden;
  position: relative;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-lg) var(--spacing-xl);
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-primary);
  flex-shrink: 0;
}

.page-header-left h1 {
  margin: 0 0 4px 0;
  font-size: 20px;
  font-weight: 500;
  line-height: 1.4;
  color: rgba(0, 0, 0, 0.85);
  letter-spacing: 0;
}

.page-header-right {
  display: flex;
  gap: var(--spacing-sm);
}

.service-filters {
  display: flex;
  align-items: center;
  gap: var(--spacing-lg);
  padding: var(--spacing-md) var(--spacing-xl);
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-primary);
  flex-shrink: 0;
}

.scope-tabs {
  display: flex;
  gap: 8px;
}

.scope-tab {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: transparent;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s ease;
}

.scope-tab:hover {
  background: var(--bg-tertiary);
  color: var(--text-primary);
}

.scope-tab.active {
  background: var(--accent-primary);
  border-color: var(--accent-primary);
  color: #fff;
}

.scope-tab .icon-sm {
  width: 16px;
  height: 16px;
}

.scope-tab .tab-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  border-radius: 9px;
  font-size: 12px;
  padding: 0 6px;
  background: rgba(0, 0, 0, 0.06);
  color: inherit;
}

.scope-tab.active .tab-count {
  background: rgba(255, 255, 255, 0.22);
}

.filter-group {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.filter-group label {
  font-size: 0.9rem;
  color: var(--text-secondary);
  font-weight: 500;
}

.service-list {
  flex: 1;
  overflow-y: auto;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(420px, 1fr));
  gap: var(--spacing-xl);
  margin-right: 0;
  padding: var(--spacing-xl);
  min-height: 0;
}

.service-list.has-sidebar {
  margin-right: 580px;
}

.service-card {
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: var(--spacing-xl);
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.service-card:hover {
  border-color: var(--accent-primary);
  box-shadow: var(--shadow-lg);
  transform: translateY(-4px);
}

.service-card.active {
  border-color: var(--accent-primary);
  background: var(--bg-primary);
  box-shadow: var(--shadow-md);
  border-width: 2px;
}

.service-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.75rem;
}

.service-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex: 1;
}

.service-icon {
  font-size: 1.2rem;
}

.service-name {
  font-size: 14px;
  font-weight: 400;
  line-height: 1.5715;
  color: rgba(0, 0, 0, 0.85);
  flex: 1;
  letter-spacing: 0;
}

.service-visibility-badge {
  padding: 0 8px;
  border-radius: 2px;
  font-size: 12px;
  font-weight: 400;
  line-height: 1.5715;
  text-transform: none;
  letter-spacing: 0;
}

.visibility-private {
  background: rgba(120, 120, 120, 0.15);
  color: rgba(80, 80, 80, 0.95);
}

.visibility-public {
  background: rgba(40, 140, 240, 0.15);
  color: rgba(20, 100, 200, 0.95);
}

.visibility-system {
  background: rgba(250, 160, 60, 0.18);
  color: rgba(200, 120, 30, 0.95);
}

.service-actions {
  display: flex;
  gap: 0.5rem;
}

.action-btn {
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  border-radius: 4px;
  cursor: pointer;
  font-size: 1rem;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.action-btn:hover {
  background: var(--bg-tertiary);
}

.action-btn-danger:hover {
  background: rgba(220, 100, 100, 0.2);
}

.action-btn-warning:hover {
  background: rgba(230, 162, 60, 0.2);
}

.action-btn-success:hover {
  background: rgba(103, 194, 58, 0.2);
}

.service-card-body {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.service-info-item {
  display: flex;
  gap: 0.5rem;
  font-size: 0.85rem;
}

.info-label {
  color: var(--text-secondary);
  font-weight: 500;
  min-width: 60px;
}

.info-value {
  color: var(--text-primary);
  flex: 1;
  word-break: break-all;
}

.info-value-url {
  font-family: monospace;
  font-size: 0.8rem;
}

.loading-state,
.error-state,
.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  padding: 3rem;
  color: var(--text-secondary);
}

.service-sidebar {
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
}

.sidebar-tabs {
  display: flex;
  gap: 0.5rem;
}

.tab-btn {
  padding: 8px 16px;
  border: none;
  background: transparent;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 400;
  line-height: 1.5715;
  color: rgba(0, 0, 0, 0.65);
  transition: all 0.2s cubic-bezier(0.645, 0.045, 0.355, 1);
  min-height: 32px;
}

.tab-btn:hover {
  background: var(--bg-tertiary);
  color: var(--text-primary);
}

.tab-btn.active {
  background: var(--accent-primary);
  color: white;
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

.execute-redirect {
  border: 1px dashed var(--border-color);
  border-radius: 12px;
  padding: 16px;
  background: var(--bg-tertiary);
}

.execute-redirect__title {
  margin: 0 0 8px;
  font-weight: 600;
}

.execute-redirect__desc {
  margin: 0 0 12px;
  color: var(--text-secondary);
  line-height: 1.6;
}
</style>
