<template>
  <div class="execution-list">
    <div class="execution-header">
      <h3>{{ $t('service.execution.list') }}</h3>
      <el-button @click="loadExecutions" :disabled="loading" :loading="loading">
        {{ $t('common.refresh') }}
      </el-button>
    </div>

    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
      <span>{{ $t('common.loading') }}</span>
    </div>
    <div v-else-if="error" class="error-state">
      <span>{{ error }}</span>
    </div>
    <div v-else-if="executions.length === 0" class="empty-state">
      <span>{{ $t('service.execution.noRecords') }}</span>
    </div>
    <div v-else class="execution-items">
      <div 
        v-for="execution in executions" 
        :key="execution.execution_id"
        class="execution-item"
        :class="`status-${execution.status}`"
      >
        <div class="execution-header-row">
          <div class="execution-title">
            <span class="execution-icon">{{ getStatusIcon(execution.status) }}</span>
            <span class="execution-id">{{ execution.execution_id }}</span>
            <span class="execution-status-badge" :class="`status-${execution.status}`">
              {{ getStatusLabel(execution.status) }}
            </span>
          </div>
          <div class="execution-time">
            {{ formatDate(execution.created_at) }}
          </div>
        </div>
        <div class="execution-body">
          <div class="execution-info-row">
            <span class="info-label">{{ $t('service.execution.inputFile') }}:</span>
            <span class="info-value">{{ execution.input_file_id }}</span>
          </div>
          <div v-if="execution.output_file_id" class="execution-info-row">
            <span class="info-label">{{ $t('service.execution.outputFile') }}:</span>
            <span class="info-value">{{ execution.output_file_id }}</span>
          </div>
          <div v-if="execution.duration_seconds !== undefined" class="execution-info-row">
            <span class="info-label">{{ $t('service.execution.duration') }}:</span>
            <span class="info-value">{{ formatDuration(execution.duration_seconds) }}</span>
          </div>
          <div v-if="execution.error_message" class="execution-error">
            <span class="error-label">{{ $t('service.execution.error') }}:</span>
            <span class="error-message">{{ execution.error_message }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { getExecutionList, type ServiceExecution, type ExecutionStatus } from '../../api/service'

const { t, locale } = useI18n()

const props = defineProps<{
  serviceId: string
}>()

const executions = ref<ServiceExecution[]>([])
const loading = ref(false)
const error = ref('')
let pollInterval: number | null = null

/**
 * 加载执行记录
 */
async function loadExecutions() {
  try {
    loading.value = true
    error.value = ''
    const result = await getExecutionList(props.serviceId)
    executions.value = result.executions || []
    // 加载后判断是否需要轮询
    const hasRunning = executions.value.some(e => e.status === 'running' || e.status === 'pending')
    if (hasRunning) {
      startPolling()
    } else {
      stopPolling()
    }
  } catch (err: any) {
    console.error('加载执行记录失败:', err)
    error.value = err.message || t('service.execution.loadFailed')
  } finally {
    loading.value = false
  }
}

/**
 * 获取状态图标
 */
function getStatusIcon(status: ExecutionStatus): string {
  switch (status) {
    case 'pending': return '⏳'
    case 'running': return '🔄'
    case 'completed': return '✅'
    case 'failed': return '❌'
    case 'cancelled': return '🚫'
    default: return '📋'
  }
}

/**
 * 获取状态标签
 */
function getStatusLabel(status: ExecutionStatus): string {
  switch (status) {
    case 'pending': return t('service.execution.status.pending')
    case 'running': return t('service.execution.status.running')
    case 'completed': return t('service.execution.status.completed')
    case 'failed': return t('service.execution.status.failed')
    case 'cancelled': return t('service.execution.status.cancelled')
    default: return status
  }
}

/**
 * 格式化日期
 */
function formatDate(date?: string): string {
  if (!date) return '-'
  return new Date(date).toLocaleString(locale.value)
}

/**
 * 格式化耗时
 */
function formatDuration(seconds: number): string {
  if (seconds < 60) {
    return `${seconds.toFixed(1)}${t('service.execution.seconds')}`
  } else if (seconds < 3600) {
    return `${Math.floor(seconds / 60)}${t('service.execution.minutes')}${(seconds % 60).toFixed(0)}${t('service.execution.seconds')}`
  } else {
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    return `${hours}${t('service.execution.hours')}${minutes}${t('service.execution.minutes')}`
  }
}

/**
 * 开始轮询
 */
function startPolling() {
  if (pollInterval) return // 避免重复启动
  // 每5秒轮询一次，仅当有活跃任务时才发请求
  pollInterval = window.setInterval(() => {
    const hasRunning = executions.value.some(e => e.status === 'running' || e.status === 'pending')
    if (hasRunning) {
      loadExecutions()
    } else {
      stopPolling()
    }
  }, 5000)
}

/**
 * 停止轮询
 */
function stopPolling() {
  if (pollInterval) {
    clearInterval(pollInterval)
    pollInterval = null
  }
}

onMounted(() => {
  loadExecutions() // loadExecutions 内部会根据状态决定是否启动轮询
})

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped>
.execution-list {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.execution-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1rem;
}

.execution-header h3 {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
}

.execution-items {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  overflow-y: auto;
}

.execution-item {
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 1rem;
  transition: all 0.2s ease;
}

.execution-item:hover {
  border-color: var(--border-hover);
  box-shadow: var(--shadow-sm);
}

.execution-item.status-running {
  border-color: rgba(100, 150, 220, 0.5);
  background: rgba(100, 150, 220, 0.1);
}

.execution-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.5rem;
}

.execution-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.execution-icon {
  font-size: 1.1rem;
}

.execution-id {
  font-family: monospace;
  font-size: 0.85rem;
  color: var(--text-primary);
}

.execution-status-badge {
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 500;
}

.execution-status-badge.status-pending {
  background: rgba(200, 200, 200, 0.2);
  color: rgba(120, 120, 120, 0.9);
}

.execution-status-badge.status-running {
  background: rgba(100, 150, 220, 0.2);
  color: rgba(60, 100, 160, 0.9);
}

.execution-status-badge.status-completed {
  background: rgba(100, 200, 100, 0.2);
  color: rgba(50, 150, 50, 0.9);
}

.execution-status-badge.status-failed {
  background: rgba(220, 100, 100, 0.2);
  color: rgba(180, 50, 50, 0.9);
}

.execution-status-badge.status-cancelled {
  background: rgba(200, 200, 200, 0.2);
  color: rgba(120, 120, 120, 0.9);
}

.execution-time {
  font-size: 0.85rem;
  color: var(--text-secondary);
}

.execution-body {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.execution-info-row {
  display: flex;
  gap: 0.5rem;
  font-size: 0.85rem;
}

.info-label {
  color: var(--text-secondary);
  font-weight: 500;
  min-width: 80px;
}

.info-value {
  color: var(--text-primary);
  flex: 1;
  word-break: break-all;
  font-family: monospace;
}

.execution-error {
  margin-top: 0.5rem;
  padding: 0.5rem;
  background: rgba(220, 100, 100, 0.1);
  border-radius: 4px;
  font-size: 0.85rem;
}

.error-label {
  color: rgba(180, 50, 50, 0.9);
  font-weight: 500;
  display: block;
  margin-bottom: 0.25rem;
}

.error-message {
  color: rgba(180, 50, 50, 0.9);
  word-break: break-word;
}

.loading-state,
.error-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  padding: 2rem;
  color: var(--text-secondary);
}

.spinner {
  width: 24px;
  height: 24px;
  border: 3px solid var(--border-color);
  border-top-color: var(--accent-primary);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>

