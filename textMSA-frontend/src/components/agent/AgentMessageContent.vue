<template>
  <div class="agent-message-content">
    <!-- 主消息内容 -->
        <div v-if="message" class="message-text">
      <MarkdownRenderer :content="message" />
    </div>

    <!-- Extra 内容渲染 -->
    <div v-if="extra && hasExtraContent" class="extra-container">
      <!-- txt: 纯文本内容 -->
      <div v-if="extra.txt" class="extra-section extra-txt">
        <div class="extra-header">
          <span class="extra-icon">📄</span>
          <span class="extra-title">{{ t('agentMessage.extra.textContent') }}</span>
        </div>
        <div class="extra-body">
          <p class="text-content">{{ extra.txt }}</p>
        </div>
      </div>

      <!-- json: JSON 数据展示 -->
      <div v-if="extra.json" class="extra-section extra-json">
        <div class="extra-header">
          <span class="extra-icon">📊</span>
          <span class="extra-title">{{ t('agentMessage.extra.data') }}</span>
          <button 
            class="copy-btn" 
            @click="copyToClipboard(formatJson(extra.json), 'JSON')"
            :title="t('agentMessage.extra.copyJson')"
          >
            <span v-if="!copied.json">📋</span>
            <span v-else class="copied-icon">✓</span>
          </button>
        </div>
        <div class="extra-body">
          <pre class="json-content"><code>{{ formatJson(extra.json) }}</code></pre>
        </div>
      </div>

      <div v-if="extra.code" class="extra-section extra-code">
        <div class="extra-header">
          <span class="extra-icon">💻</span>
          <span class="extra-title">{{ t('agentMessage.extra.code') }}</span>
          <button 
            class="copy-btn" 
            @click="copyToClipboard(extra.code, '代码')"
            :title="t('agentMessage.extra.copyCode')"
          >
            <span v-if="!copied.code">📋</span>
            <span v-else class="copied-icon">✓</span>
          </button>
        </div>
        <div class="extra-body">
          <pre class="code-content"><code>{{ extra.code }}</code></pre>
        </div>
      </div>

      <div
        v-if="extra.type === 'literature' && Array.isArray(extra.literatures) && extra.literatures.length > 0"
        class="extra-section extra-literature"
      >
        <div class="extra-header">
          <span class="extra-icon">📚</span>
          <span class="extra-title">{{ t('agentMessage.extra.literatureHeader') }} ({{ extra.literatures.length }})</span>
        </div>
        <div class="extra-body">
          <ul class="literature-list">
            <li
              v-for="(lit, index) in extra.literatures"
              :key="lit.doi || lit.url || index"
              class="literature-item"
            >
              <div class="literature-title">
                <a v-if="lit.url" :href="lit.url" target="_blank" rel="noopener noreferrer">
                  {{ lit.title }}
                </a>
                <span v-else>{{ lit.title }}</span>
              </div>
              <div v-if="lit.snippet" class="literature-snippet">
                {{ lit.snippet }}
              </div>
              <div v-if="lit.doi || lit.url" class="literature-meta">
                <span v-if="lit.doi" class="literature-doi">{{ t('agentMessage.extra.doiLabel') }}: {{ lit.doi }}</span>
                <a
                  v-if="lit.url"
                  :href="lit.url"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="literature-link"
                >
                  {{ t('agentMessage.extra.link') }}
                </a>
              </div>
            </li>
          </ul>
        </div>
      </div>

      <!-- files: 文件列表与下载 -->
      <div v-if="extra.files && Array.isArray(extra.files) && extra.files.length > 0" class="extra-section extra-files">
        <div class="extra-header">
          <span class="extra-icon">📁</span>
          <span class="extra-title">{{ t('agentMessage.extra.relatedFiles') }} ({{ extra.files.length }})</span>
        </div>
        <div class="extra-body">
          <ul class="file-list">
            <li 
              v-for="(file, index) in extra.files" 
              :key="file.file_id || index"
              class="file-item"
            >
              <div class="file-info">
                <span class="file-icon">📎</span>
                <span class="file-name">{{ file.name || file.filename || file.file_id || `${t('agentMessage.extra.file')} ${index + 1}` }}</span>
                <span v-if="file.size" class="file-size">{{ formatFileSize(file.size) }}</span>
              </div>
              <button 
                v-if="file.file_id"
                class="download-btn"
                :disabled="downloading[file.file_id]"
                @click="handleDownload(file)"
                :title="t('agentMessage.extra.downloadFile')"
              >
                <span v-if="!downloading[file.file_id]">⬇️ {{ t('agentMessage.extra.download') }}</span>
                <span v-else>⏳ {{ t('agentMessage.extra.downloading') }}</span>
              </button>
            </li>
          </ul>
        </div>
      </div>

      <!-- execution: 执行详情展示（文件仅展示元信息，不可下载） -->
      <div v-if="extra.execution" class="extra-section extra-execution">
        <div class="extra-header">
          <span class="extra-icon">🧭</span>
          <span class="extra-title">{{ t('agentMessage.extra.executionDetails') }}</span>
          <span class="status-pill" :data-status="extra.execution.status || 'unknown'">
            {{ extra.execution.status || 'unknown' }}
          </span>
        </div>
        <div class="extra-body execution-body">
          <div class="execution-meta">
            <div class="meta-title">{{ t('agentMessage.extra.serviceInfo') }}</div>
            <table class="exec-meta-table">
              <tbody>
                <tr>
                  <th>{{ t('agentMessage.extra.service') }}</th>
                  <td>{{ extra.execution.service_name }}</td>
                </tr>
                <tr>
                  <th>{{ t('agentMessage.extra.serviceId') }}</th>
                  <td class="mono">{{ extra.execution.service_id }}</td>
                </tr>
                <tr v-if="extra.execution.execution_id">
                  <th>{{ t('agentMessage.extra.executionId') }}</th>
                  <td class="mono">{{ extra.execution.execution_id }}</td>
                </tr>
                <tr v-if="extra.execution.duration_seconds">
                  <th>{{ t('agentMessage.extra.duration') }}</th>
                  <td>{{ formatDuration(extra.execution.duration_seconds) }}</td>
                </tr>
                <tr v-if="extra.execution.started_at">
                  <th>{{ t('agentMessage.extra.startTime') }}</th>
                  <td>{{ formatDate(extra.execution.started_at) }}</td>
                </tr>
                <tr v-if="extra.execution.completed_at">
                  <th>{{ t('agentMessage.extra.completionTime') }}</th>
                  <td>{{ formatDate(extra.execution.completed_at) }}</td>
                </tr>
                <tr v-if="extra.execution.service_description">
                  <th>{{ t('agentMessage.extra.description') }}</th>
                  <td class="wrap">{{ extra.execution.service_description }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div class="execution-files" v-if="hasExecutionFiles(extra.execution)">
            <div class="files-section" v-if="extra.execution.input_files?.length">
              <div class="files-title">{{ t('agentMessage.extra.inputFiles') }} ({{ extra.execution.input_files.length }})</div>
              <ul class="exec-file-list">
                <li v-for="f in extra.execution.input_files" :key="f.file_id" class="exec-file-item">
                  <div class="file-main">
                    <span class="file-name">{{ f.filename }}</span>
                    <span class="file-id">ID: {{ f.file_id }}</span>
                  </div>
                  <div v-if="f.description" class="file-desc">{{ f.description }}</div>
                </li>
              </ul>
            </div>

            <div class="files-section" v-if="extra.execution.output_files?.length">
              <div class="files-title">{{ t('agentMessage.extra.outputFiles') }} ({{ extra.execution.output_files.length }})</div>
              <ul class="exec-file-list">
                <li v-for="f in extra.execution.output_files" :key="f.file_id" class="exec-file-item">
                  <div class="file-main">
                    <span class="file-name">{{ f.filename }}</span>
                    <span class="file-id">ID: {{ f.file_id }}</span>
                  </div>
                  <div v-if="f.description" class="file-desc">{{ f.description }}</div>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive } from 'vue'
import { useI18n } from 'vue-i18n'
import MarkdownRenderer from '../common/MarkdownRenderer.vue'
import { downloadFileById } from '../../api/file'

export interface FileInfo {
  file_id: string
  name?: string
  filename?: string
  size?: number
  type?: string
  description?: string
}

export interface ExecutionAttachmentFile {
  file_id: string
  filename: string
  description?: string
}

export interface ExecutionAttachment {
  execution_id: string
  service_id: string
  service_name: string
  service_description?: string
  status?: string
  project_id?: string
  created_at?: string
  started_at?: string
  completed_at?: string
  duration_seconds?: number
  input_files?: ExecutionAttachmentFile[]
  output_files?: ExecutionAttachmentFile[]
}

export interface LiteratureItem {
  title: string
  snippet?: string
  url?: string
  doi?: string
}

export interface MessageExtra {
  txt?: string
  json?: Record<string, unknown> | unknown[]
  code?: string
  files?: FileInfo[]
  execution?: ExecutionAttachment
  type?: string
  literatures?: LiteratureItem[]
}

interface Props {
  message?: string
  extra?: MessageExtra | null
}

const props = defineProps<Props>()

const { t } = useI18n()

const downloading = reactive<Record<string, boolean>>({})
const copied = reactive<Record<string, boolean>>({})

const hasExtraContent = computed(() => {
  if (!props.extra) return false
  return !!(
    props.extra.txt ||
    props.extra.json ||
    props.extra.code ||
    props.extra.execution ||
    (props.extra.literatures && props.extra.literatures.length > 0) ||
    (props.extra.files && props.extra.files.length > 0)
  )
})

function formatJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`
}

function formatDate(value?: string) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return `${date.getFullYear()}-${(date.getMonth() + 1).toString().padStart(2, '0')}-${date
    .getDate()
    .toString()
    .padStart(2, '0')} ${date.getHours().toString().padStart(2, '0')}:${date
    .getMinutes()
    .toString()
    .padStart(2, '0')}:${date.getSeconds().toString().padStart(2, '0')}`
}

function formatDuration(seconds?: number) {
  if (!seconds && seconds !== 0) return ''
  if (seconds < 60) return `${seconds.toFixed(1)} ${t('agentMessage.extra.seconds')}`
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins} ${t('agentMessage.extra.minutes')} ${secs.toFixed(0)} ${t('agentMessage.extra.seconds')}`
}

function hasExecutionFiles(exe: ExecutionAttachment) {
  return (exe.input_files && exe.input_files.length > 0) || (exe.output_files && exe.output_files.length > 0)
}

async function handleDownload(file: FileInfo) {
  if (!file.file_id || downloading[file.file_id]) return
  
  try {
    downloading[file.file_id] = true
    const blob = await downloadFileById(file.file_id)
    
    // 创建下载链接
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = file.name || file.file_id
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  } catch (error) {
    console.error('文件下载失败:', error)
    alert(`${t('agentMessage.extra.fileDownloadFailed')}: ${(error as Error).message || t('agentMessage.extra.unknownError')}`)
  } finally {
    downloading[file.file_id] = false
  }
}

async function copyToClipboard(text: string, label: string) {
  try {
    await navigator.clipboard.writeText(text)
    const key = label === 'JSON' ? 'json' : 'code'
    copied[key] = true
    setTimeout(() => {
      copied[key] = false
    }, 2000)
  } catch (error) {
    console.error('复制失败:', error)
    alert(t('agentMessage.extra.copyFailed'))
  }
}
</script>

<style scoped>
.agent-message-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.message-text {
  color: #111827;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  margin-top: 8px;
}

.extra-container {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 8px;
}

.extra-section {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
  background: linear-gradient(180deg, #f9fafb 0%, #ffffff 100%);
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.05);
}

.extra-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: #f3f4f6;
  border-bottom: 1px solid #e5e7eb;
  font-weight: 600;
  font-size: 13px;
  color: #374151;
}

.extra-icon {
  font-size: 16px;
  line-height: 1;
}

.extra-title {
  flex: 1;
}

.copy-btn {
  padding: 4px 8px;
  border: 1px solid #d1d5db;
  border-radius: 4px;
  background: #fff;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s ease;
}

.copy-btn:hover:not(:disabled) {
  border-color: #9ca3af;
  background: #f9fafb;
}

.copy-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.copied-icon {
  color: #10b981;
  font-weight: bold;
}

.extra-body {
  padding: 12px;
  background: #fff;
}

/* txt 样式 */
.extra-txt .text-content {
  margin: 0;
  color: #1f2937;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

/* json 样式 */
.extra-json .json-content {
  margin: 0;
  padding: 12px;
  background: #1e293b;
  color: #e2e8f0;
  border-radius: 6px;
  overflow-x: auto;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', 'Consolas', monospace;
  font-size: 13px;
  line-height: 1.5;
}

.extra-json .json-content code {
  color: inherit;
  background: none;
}

/* code 样式 */
.extra-code .code-content {
  margin: 0;
  padding: 12px;
  background: #0f172a;
  color: #cbd5e1;
  border-radius: 6px;
  overflow-x: auto;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', 'Consolas', monospace;
  font-size: 13px;
  line-height: 1.5;
}

.extra-code .code-content code {
  color: inherit;
  background: none;
}

/* files 样式 */
.file-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.file-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  transition: all 0.2s ease;
}

.file-item:hover {
  background: #f3f4f6;
  border-color: #d1d5db;
}

.file-info {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.file-icon {
  font-size: 16px;
  line-height: 1;
  flex-shrink: 0;
}

.file-name {
  font-weight: 500;
  color: #1f2937;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-size {
  font-size: 12px;
  color: #6b7280;
  flex-shrink: 0;
}

.download-btn {
  padding: 6px 12px;
  border: 1px solid #3b82f6;
  border-radius: 6px;
  background: #3b82f6;
  color: #fff;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  transition: all 0.2s ease;
  white-space: nowrap;
  flex-shrink: 0;
}

.download-btn:hover:not(:disabled) {
  background: #2563eb;
  border-color: #2563eb;
  box-shadow: 0 2px 4px rgba(59, 130, 246, 0.3);
}

.download-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.literature-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.literature-item {
  padding: 10px 12px;
  background: #f9fafb;
  border-radius: 6px;
  border: 1px solid #e5e7eb;
  transition: all 0.2s ease;
}

.literature-item:hover {
  background: #f3f4f6;
  border-color: #d1d5db;
}

.literature-title {
  font-weight: 600;
  color: #111827;
  margin-bottom: 4px;
}

.literature-title a {
  color: #1d4ed8;
  text-decoration: none;
}

.literature-title a:hover {
  text-decoration: underline;
}

.literature-snippet {
  font-size: 13px;
  color: #4b5563;
  line-height: 1.5;
  margin-bottom: 4px;
}

.literature-meta {
  font-size: 12px;
  color: #6b7280;
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.literature-link {
  color: #2563eb;
}

/* execution 样式 */
.extra-execution .execution-body {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.exec-meta-table {
  width: 100%;
  border-collapse: collapse;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  overflow: hidden;
  box-shadow: 0 6px 16px rgba(15, 23, 42, 0.05);
}

.exec-meta-table th,
.exec-meta-table td {
  padding: 10px 12px;
  text-align: left;
  border-bottom: 1px solid #e5e7eb;
  vertical-align: top;
}

.exec-meta-table th {
  width: 110px;
  background: #f8fafc;
  color: #334155;
  font-weight: 600;
  font-size: 13px;
}

.exec-meta-table td {
  color: #1f2937;
  font-size: 13px;
}

.exec-meta-table tr:last-child th,
.exec-meta-table tr:last-child td {
  border-bottom: none;
}

.exec-meta-table .wrap {
  white-space: pre-wrap;
  word-break: break-word;
}

.exec-file-item {
  border: 1px solid #e5e7eb;
  background: #f8fafc;
  border-radius: 8px;
  padding: 10px 12px;
  display: grid;
  gap: 4px;
  transition: all 0.2s ease;
}

.exec-file-item:hover {
  border-color: #cbd5e1;
  background: #eef2ff;
  box-shadow: 0 4px 10px rgba(67, 56, 202, 0.08);
}

.file-id {
  color: #4b5563;
  font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
  font-size: 12px;
  display: block;
  word-break: break-all;
  white-space: normal;
}

.file-desc {
  color: #4b5563;
  font-size: 13px;
  line-height: 1.5;
}

.file-note {
  color: #9ca3af;
  font-size: 12px;
  font-style: italic;
}

.files-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.execution-files {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 12px;
}

.status-pill {
  padding: 4px 10px;
  border-radius: 999px;
  background: #eef2ff;
  color: #4338ca;
  font-size: 12px;
  font-weight: 600;
  text-transform: capitalize;
}

.status-pill[data-status='completed'] {
  background: #ecfdf3;
  color: #166534;
}

.status-pill[data-status='failed'],
.status-pill[data-status='error'] {
  background: #fef2f2;
  color: #dc2626;
}

/* 响应式调整 */
@media (max-width: 768px) {
  .extra-execution .execution-body {
    grid-template-columns: 1fr;
  }
  .file-item {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }

  .download-btn {
    width: 100%;
  }
}
</style>
