<template>
  <div class="execution-page">
    <div class="page-header">
      <div class="header-left">
        <Icon name="timeline" size="lg" />
        <div class="titles">
          <h2>{{ $t('execution.title') }}</h2>
          <p class="subtitle">{{ $t('execution.subtitle') }}</p>
        </div>
      </div>
      <div class="header-actions">
        <el-button :icon="Refresh" @click="refresh" :loading="loading">
          {{ $t('execution.refresh') }}
        </el-button>
      </div>
    </div>

    <el-card class="filter-card" shadow="never">
      <div class="filter-bar">
        <el-select
          v-model="filters.project"
          clearable
          filterable
          :placeholder="$t('execution.filters.project')"
          @change="onFiltersChange"
          class="filter-item"
        >
          <el-option
            v-for="project in projectOptions"
            :key="project.project_id"
            :label="project.name || project.project_id"
            :value="project.project_id"
          />
        </el-select>

        <el-select
          v-model="filters.serviceId"
          clearable
          filterable
          :placeholder="$t('execution.filters.service')"
          @change="onFiltersChange"
          class="filter-item"
        >
          <el-option
            v-for="service in serviceOptions"
            :key="service.service_id"
            :label="service.name || service.service_id"
            :value="service.service_id"
          />
        </el-select>

        <el-select
          v-model="filters.status"
          clearable
          :placeholder="$t('execution.filters.status')"
          @change="onFiltersChange"
          class="filter-item"
        >
          <el-option
            v-for="option in statusOptions"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
      </div>
    </el-card>

    <el-card class="table-card" shadow="never">
      <template #default>
        <div v-if="error" class="state-block">
          <el-alert
            type="error"
            :title="error"
            show-icon
            :closable="false"
          />
        </div>
        <div v-else-if="!loading && executions.length === 0" class="state-block">
          <el-empty :description="$t('execution.empty')" />
        </div>
        <el-table
          v-else
          :data="executions"
          row-key="execution_id"
          v-loading="loading"
          border
          header-cell-class-name="table-header"
          style="width: 100%"
        >
          <el-table-column type="expand">
            <template #default="{ row }">
              <div class="expand-block">
                <div class="expand-columns">
                  <div class="expand-col">
                    <h4>{{ $t('execution.detail.basic') }}</h4>
                    <el-descriptions :column="1" size="small">
                      <el-descriptions-item :label="$t('execution.detail.serviceId')">
                        {{ row.service_id }}
                      </el-descriptions-item>
                      <el-descriptions-item :label="$t('execution.detail.userId')">
                        {{ row.user_id }}
                      </el-descriptions-item>
                      <el-descriptions-item :label="$t('execution.detail.createdAt')">
                        {{ formatDate(row.created_at) }}
                      </el-descriptions-item>
                      <el-descriptions-item :label="$t('execution.detail.startedAt')">
                        {{ formatDate(row.started_at) }}
                      </el-descriptions-item>
                      <el-descriptions-item :label="$t('execution.detail.completedAt')">
                        {{ formatDate(row.completed_at) }}
                      </el-descriptions-item>
                    </el-descriptions>
                  </div>

                  <div class="expand-col">
                    <h4>{{ $t('execution.detail.params') }}</h4>
                    <div class="code-block" v-if="hasContent(row.parameters)">
                      <pre>{{ formatJson(row.parameters) }}</pre>
                    </div>
                    <div class="muted" v-else>{{ $t('execution.detail.empty') }}</div>
                  </div>

                  <div class="expand-col">
                    <h4>{{ $t('execution.detail.response') }}</h4>
                    <div class="code-block" v-if="hasContent(row.response_data)">
                      <pre>{{ formatJson(row.response_data) }}</pre>
                    </div>
                    <div class="muted" v-else>{{ $t('execution.detail.empty') }}</div>
                  </div>
                </div>

                <div class="expand-columns">
                  <div class="expand-col">
                    <h4>{{ $t('execution.detail.inputFiles') }}</h4>
                    <ul class="list" v-if="row.input_file_ids?.length">
                      <li v-for="file in row.input_file_ids" :key="file">{{ file }}</li>
                    </ul>
                    <div class="muted" v-else>{{ $t('execution.detail.empty') }}</div>
                  </div>

                  <div class="expand-col">
                    <h4>{{ $t('execution.detail.outputFiles') }}</h4>
                    <ul class="list" v-if="row.output_file_ids?.length">
                      <li v-for="file in row.output_file_ids" :key="file">{{ file }}</li>
                    </ul>
                    <div class="muted" v-else>{{ $t('execution.detail.empty') }}</div>
                  </div>

                  <div class="expand-col">
                    <h4>{{ $t('execution.detail.error') }}</h4>
                    <div class="error-block" v-if="row.error_message">
                      {{ row.error_message }}
                    </div>
                    <div class="muted" v-else>{{ $t('execution.detail.noError') }}</div>
                  </div>
                </div>
              </div>
            </template>
          </el-table-column>

          <el-table-column
            prop="service_name"
            :label="$t('execution.columns.service')"
            min-width="160"
          >
            <template #default="{ row }">
              <div class="cell-title">
                <span class="service-name">{{ row.service_name || row.service_id }}</span>
                <span class="muted-id">{{ row.service_id }}</span>
              </div>
            </template>
          </el-table-column>

          <el-table-column
            prop="status"
            :label="$t('execution.columns.status')"
            width="150"
          >
            <template #default="{ row }">
              <el-tag :type="statusTagType(row.status)" effect="light">
                {{ statusLabel(row.status) }}
              </el-tag>
            </template>
          </el-table-column>

          <el-table-column
            prop="execution_id"
            :label="$t('execution.columns.executionId')"
            min-width="200"
          >
            <template #default="{ row }">
              <code class="mono">{{ row.execution_id }}</code>
            </template>
          </el-table-column>

          <el-table-column
            prop="created_at"
            :label="$t('execution.columns.createdAt')"
            width="180"
          >
            <template #default="{ row }">
              {{ formatDate(row.created_at) }}
            </template>
          </el-table-column>

          <el-table-column
            prop="started_at"
            :label="$t('execution.columns.startedAt')"
            width="180"
          >
            <template #default="{ row }">
              {{ formatDate(row.started_at) }}
            </template>
          </el-table-column>

          <el-table-column
            prop="completed_at"
            :label="$t('execution.columns.completedAt')"
            width="180"
          >
            <template #default="{ row }">
              {{ formatDate(row.completed_at) }}
            </template>
          </el-table-column>

          <el-table-column
            prop="duration_seconds"
            :label="$t('execution.columns.duration')"
            width="140"
          >
            <template #default="{ row }">
              {{ formatDuration(row) }}
            </template>
          </el-table-column>
        </el-table>

        <div class="pagination" v-if="total > pagination.pageSize">
          <el-pagination
            layout="prev, pager, next, jumper"
            :total="total"
            :page-size="pagination.pageSize"
            :current-page="pagination.page"
            @current-change="onPageChange"
          />
        </div>
      </template>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Refresh } from '@element-plus/icons-vue'
import Icon from '../common/Icon.vue'
import {
  getExecutionList,
  getServiceList,
  type ExecutionStatus,
  type ServiceExecution,
  type Service
} from '../../api/service'
import { getProjectList, type Project } from '../../api/project'

interface Filters {
  project: string | undefined
  serviceId: string | undefined
  status: ExecutionStatus | undefined
}

const router = useRouter()
const route = useRoute()
const { t } = useI18n()

const filters = reactive<Filters>({
  project: (route.query.project as string) || undefined,
  serviceId: (route.query.service_id as string) || undefined,
  status: (route.query.status as ExecutionStatus) || undefined
})

const pagination = reactive({
  page: 1,
  pageSize: 20
})

const loading = ref(false)
const error = ref('')
const executions = ref<ServiceExecution[]>([])
const total = ref(0)
let pollTimer: number | null = null

const projectOptions = ref<Project[]>([])
const serviceOptions = ref<Service[]>([])

const statusOptions = computed(() => ([
  { value: 'pending', label: t('execution.status.pending') },
  { value: 'running', label: t('execution.status.running') },
  { value: 'completed', label: t('execution.status.completed') },
  { value: 'failed', label: t('execution.status.failed') }
]))

function statusTagType(status: ExecutionStatus) {
  switch (status) {
    case 'running': return 'info'
    case 'completed': return 'success'
    case 'failed': return 'danger'
    default: return 'default'
  }
}

function statusLabel(status: ExecutionStatus) {
  return t(`execution.status.${status}`)
}

function formatDate(date?: string) {
  if (!date) return '—'
  return new Date(date).toLocaleString()
}

function formatDuration(row: ServiceExecution) {
  if (row.duration_seconds !== undefined && row.duration_seconds !== null) {
    return secondsToText(row.duration_seconds)
  }
  if (row.started_at && row.completed_at) {
    const diff = (new Date(row.completed_at).getTime() - new Date(row.started_at).getTime()) / 1000
    return secondsToText(diff)
  }
  if (row.started_at) {
    const diff = (Date.now() - new Date(row.started_at).getTime()) / 1000
    return secondsToText(diff)
  }
  return '—'
}

function secondsToText(seconds: number) {
  if (seconds < 60) return `${seconds.toFixed(1)}s`
  if (seconds < 3600) {
    const mins = Math.floor(seconds / 60)
    const secs = Math.round(seconds % 60)
    return `${mins}m ${secs}s`
  }
  const hours = Math.floor(seconds / 3600)
  const mins = Math.floor((seconds % 3600) / 60)
  return `${hours}h ${mins}m`
}

function formatJson(obj?: Record<string, any>) {
  return JSON.stringify(obj ?? {}, null, 2)
}

function hasContent(obj?: Record<string, any>) {
  return obj && Object.keys(obj).length > 0
}

async function loadProjects() {
  try {
    const list = await getProjectList(0, 200)
    projectOptions.value = list
  } catch (err) {
    console.warn('加载项目列表失败', err)
  }
}

async function loadServices() {
  try {
    const { services } = await getServiceList(undefined, undefined, 0, 200)
    serviceOptions.value = services
  } catch (err) {
    console.warn('加载服务列表失败', err)
  }
}

async function loadExecutions() {
  loading.value = true
  error.value = ''
  try {
    const skip = (pagination.page - 1) * pagination.pageSize
    const { executions: items, total: totalCount } = await getExecutionList(
      filters.serviceId,
      undefined,
      filters.status,
      filters.project,
      skip,
      pagination.pageSize
    )
    executions.value = items || []
    total.value = totalCount || 0
    refreshPolling()
  } catch (err: any) {
    console.error('加载执行记录失败', err)
    error.value = err?.message || t('execution.error.loadFailed')
  } finally {
    loading.value = false
  }
}

function buildQuery() {
  const query: Record<string, string> = {}
  if (filters.project) query.project = filters.project
  if (filters.serviceId) query.service_id = filters.serviceId
  if (filters.status) query.status = filters.status
  return query
}

function syncRouteQuery() {
  router.replace({
    path: '/executions',
    query: buildQuery()
  })
}

function onFiltersChange() {
  pagination.page = 1
  syncRouteQuery()
  loadExecutions()
}

function onPageChange(page: number) {
  pagination.page = page
  loadExecutions()
}

function refresh() {
  loadExecutions()
}

function refreshPolling() {
  const hasActive = executions.value.some(item => item.status === 'pending' || item.status === 'running')
  if (hasActive) {
    startPolling()
  } else {
    stopPolling()
  }
}

function startPolling() {
  if (pollTimer) return
  pollTimer = window.setInterval(() => {
    // 页面不可见时跳过请求
    if (document.hidden) return
    const hasActive = executions.value.some(item => item.status === 'pending' || item.status === 'running')
    if (hasActive && !loading.value) {
      loadExecutions()
    } else if (!hasActive) {
      stopPolling()
    }
  }, 5000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

// 页面可见性感知：后台暂停轮询，前台恢复
function handleVisibilityChange() {
  if (document.hidden) {
    stopPolling()
  } else {
    // 切回前台时判断是否需要恢复轮询
    refreshPolling()
    if (executions.value.some(item => item.status === 'pending' || item.status === 'running')) {
      loadExecutions() // 立即刷新一次
    }
  }
}

document.addEventListener('visibilitychange', handleVisibilityChange)

function initFromRoute() {
  filters.project = (route.query.project as string) || undefined
  filters.serviceId = (route.query.service_id as string) || undefined
  filters.status = (route.query.status as ExecutionStatus) || undefined
}

watch(() => route.query, () => {
  initFromRoute()
  pagination.page = 1
  loadExecutions()
})

onMounted(async () => {
  await Promise.all([loadProjects(), loadServices()])
  initFromRoute()
  loadExecutions()
})

onUnmounted(() => {
  stopPolling()
  document.removeEventListener('visibilitychange', handleVisibilityChange)
})
</script>

<style scoped>
.execution-page {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
  padding: 16px;
  background: var(--bg-secondary, #f7f8fa);
  overflow: auto;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.titles h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
}

.subtitle {
  margin: 2px 0 0;
  color: var(--text-secondary);
  font-size: 13px;
}

.filter-card {
  padding: 8px 12px;
}

.filter-bar {
  display: flex;
  gap: 12px;
  flex-wrap: nowrap;
  align-items: center;
  justify-content: flex-start;
}

.filter-item {
  min-width: 200px;
  width: auto;
}

.table-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: auto;
}

.state-block {
  padding: 32px 0;
}

.expand-block {
  display: flex;
  flex-direction: column;
  gap: 16px;
  background: var(--bg-tertiary, #fafafa);
  padding: 12px;
  border-radius: 8px;
}

.expand-columns {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.expand-col {
  flex: 1;
  min-width: 240px;
}

.expand-col h4 {
  margin: 0 0 6px;
  font-size: 14px;
  color: var(--text-primary);
}

.code-block {
  background: #0d1117;
  color: #e6edf3;
  border-radius: 6px;
  padding: 8px;
  font-size: 12px;
  line-height: 1.5;
  overflow: auto;
}

.list {
  margin: 0;
  padding-left: 16px;
  color: var(--text-primary);
}

.list li {
  word-break: break-all;
  font-family: var(--mono-font, monospace);
}

.muted {
  color: var(--text-secondary);
  font-size: 13px;
}

.muted-id {
  color: var(--text-secondary);
  font-size: 12px;
  margin-left: 6px;
}

.cell-title {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.service-name {
  font-weight: 600;
  color: var(--text-primary);
}

.mono {
  font-family: var(--mono-font, monospace);
}

.error-block {
  padding: 8px;
  background: rgba(220, 38, 38, 0.08);
  border: 1px solid rgba(220, 38, 38, 0.2);
  border-radius: 6px;
  color: #b91c1c;
  white-space: pre-wrap;
  word-break: break-word;
}

.pagination {
  display: flex;
  justify-content: flex-end;
  padding: 12px 8px 0;
}

.table-header {
  background: var(--bg-tertiary, #fafafa);
  font-weight: 600;
}
</style>

