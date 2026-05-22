<template>
  <div class="execution-preview">
    <div v-if="!execution" class="empty-state">
      <el-empty :description="t('execution.detail.selectExecution')" />
    </div>
    <div v-else class="preview-content">
      <el-scrollbar>
        <div class="preview-sections">
          <!-- 基本信息 -->
          <div class="preview-section">
            <h3 class="section-title">{{ t('execution.detail.basic') }}</h3>
            <el-descriptions :column="1" size="small" border>
              <el-descriptions-item :label="t('execution.detail.executionId')">
                <code class="mono">{{ execution.execution_id }}</code>
              </el-descriptions-item>
              <el-descriptions-item :label="t('execution.columns.status')">
                <el-tag :type="statusTagType(execution.status)" effect="light" size="small">
                  {{ statusLabel(execution.status) }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item :label="t('execution.detail.projectId')">
                {{ execution.project_id }}
              </el-descriptions-item>
              <el-descriptions-item :label="t('execution.detail.createdAt')">
                {{ formatDate(execution.created_at) }}
              </el-descriptions-item>
              <el-descriptions-item :label="t('execution.detail.startedAt')">
                {{ formatDate(execution.started_at) }}
              </el-descriptions-item>
              <el-descriptions-item :label="t('execution.detail.completedAt')">
                {{ formatDate(execution.completed_at) }}
              </el-descriptions-item>
              <el-descriptions-item :label="t('execution.columns.duration')">
                {{ formatDuration(execution) }}
              </el-descriptions-item>
            </el-descriptions>
          </div>

          <!-- 输入文件 -->
          <div class="preview-section">
            <h3 class="section-title">{{ t('execution.detail.inputFiles') }}</h3>
            <div v-if="execution.input_file_ids?.length" class="file-list">
              <el-tag
                v-for="fileId in execution.input_file_ids"
                :key="fileId"
                size="small"
                class="file-tag"
              >
                {{ getFileName(fileId) }}
              </el-tag>
            </div>
            <div v-else class="empty-text">{{ t('execution.detail.noInputFiles') }}</div>
          </div>

          <!-- 输出文件 -->
          <div class="preview-section">
            <h3 class="section-title">{{ t('execution.detail.outputFiles') }}</h3>
            <div v-if="execution.output_file_ids?.length" class="file-list">
              <el-tag
                v-for="fileId in execution.output_file_ids"
                :key="fileId"
                size="small"
                class="file-tag"
              >
                {{ getFileName(fileId) }}
              </el-tag>
            </div>
            <div v-else class="empty-text">{{ t('execution.detail.noOutputFiles') }}</div>
          </div>

          <!-- 执行参数 -->
          <div class="preview-section">
            <h3 class="section-title">{{ t('execution.detail.params') }}</h3>
            <div v-if="hasContent(execution.parameters)" class="code-block">
              <pre>{{ formatJson(execution.parameters) }}</pre>
            </div>
            <div v-else class="empty-text">{{ t('execution.detail.noParams') }}</div>
          </div>

          <!-- 响应数据 -->
          <div class="preview-section">
            <h3 class="section-title">{{ t('execution.detail.response') }}</h3>
            <div v-if="hasContent((execution as any).response_data)" class="code-block">
              <pre>{{ formatJson((execution as any).response_data) }}</pre>
            </div>
            <div v-else class="empty-text">{{ t('execution.detail.noResponse') }}</div>
          </div>

          <!-- 错误信息 -->
          <div v-if="execution.error_message" class="preview-section">
            <h3 class="section-title">{{ t('execution.detail.error') }}</h3>
            <div class="error-block">
              {{ execution.error_message }}
            </div>
          </div>
        </div>
      </el-scrollbar>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { type ExecutionInfo } from '../../api/analysis'

interface NormalizedFile {
  id: string
  name: string
}

const props = defineProps<{
  execution: ExecutionInfo | null
  files?: NormalizedFile[]
}>()

const { t } = useI18n()

function statusTagType(status: string) {
  switch (status?.toLowerCase()) {
    case 'running': return 'info'
    case 'completed': return 'success'
    case 'failed': return 'danger'
    case 'error': return 'danger'
    default: return 'default'
  }
}

function statusLabel(status: string) {
  const statusMap: Record<string, string> = {
    pending: t('execution.status.pending'),
    running: t('execution.status.running'),
    completed: t('execution.status.completed'),
    failed: t('execution.status.failed')
  }
  return statusMap[status?.toLowerCase()] || status || '—'
}

function formatDate(date?: string) {
  if (!date) return '—'
  return new Date(date).toLocaleString()
}

function formatDuration(execution: ExecutionInfo) {
  if (execution.duration_seconds !== undefined && execution.duration_seconds !== null) {
    return secondsToText(execution.duration_seconds)
  }
  if (execution.started_at && execution.completed_at) {
    const diff = (new Date(execution.completed_at).getTime() - new Date(execution.started_at).getTime()) / 1000
    return secondsToText(diff)
  }
  if (execution.started_at) {
    const diff = (Date.now() - new Date(execution.started_at).getTime()) / 1000
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

function getFileName(fileId: string): string {
  if (!props.files || !fileId) return fileId
  const file = props.files.find(f => f.id === fileId)
  return file?.name || fileId
}
</script>

<style scoped>
.execution-preview {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}

.preview-content {
  height: 100%;
  padding: 12px;
  display: flex;
  flex-direction: column;
}

.preview-content :deep(.el-scrollbar) {
  flex: 1;
}

.preview-content :deep(.el-scrollbar__wrap) {
  overflow-x: hidden;
}

.preview-sections {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.preview-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.section-title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.file-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.file-tag {
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 12px;
}

.empty-text {
  color: #909399;
  font-size: 13px;
}

.code-block {
  background: #f5f7fa;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  padding: 12px;
  overflow-x: auto;
}

.code-block pre {
  margin: 0;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.6;
  color: #303133;
  white-space: pre-wrap;
  word-break: break-word;
}

.error-block {
  background: #fef0f0;
  border: 1px solid #fde2e2;
  border-radius: 4px;
  padding: 12px;
  color: #f56c6c;
  font-size: 13px;
  line-height: 1.6;
}

.mono {
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 12px;
  background: #f5f7fa;
  padding: 2px 6px;
  border-radius: 3px;
}
</style>

