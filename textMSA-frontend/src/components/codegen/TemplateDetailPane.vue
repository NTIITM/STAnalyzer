<template>
  <div class="template-detail-pane">
    <!-- Empty state -->
    <div v-if="!template" class="empty-state">
      <div class="empty-icon">📄</div>
      <div class="empty-text">{{ t('codegen.detail.empty') }}</div>
      <div class="empty-hint">{{ t('codegen.detail.hint') }}</div>
    </div>

    <!-- Template detail -->
    <div v-else class="detail-content">
      <!-- Code section -->
      <div class="section">
        <div class="section-header">
          <h3 class="section-title">{{ t('codegen.detail.code') }}</h3>
        </div>
        <textarea
          v-model="localCode"
          class="code-editor"
          spellcheck="false"
          :readonly="!canEdit"
        />
        <div class="section-actions">
          <button
            class="button button-secondary"
            :disabled="!canEdit || updating"
            @click="handleUpdateCode"
          >
            {{ t('common.save') }}
          </button>
        </div>
      </div>

      <!-- Metadata section -->
      <div class="section">
        <div class="section-header">
          <h3 class="section-title">{{ t('codegen.detail.meta') }}</h3>
        </div>
        <pre class="json-preview">{{ metaPreview }}</pre>
      </div>

      <!-- Lifecycle actions -->
      <div class="section">
        <div class="section-header">
          <h3 class="section-title">{{ t('codegen.detail.lifecycle') }}</h3>
        </div>
        <div class="action-buttons">
          <button
            class="button button-primary"
            :disabled="!canConfirm || confirming"
            @click="$emit('confirm')"
          >
            {{ confirming ? t('codegen.detail.confirming') : t('codegen.detail.confirm') }}
          </button>
          <button
            class="button button-primary"
            :disabled="!canGenerateCode || generatingCode"
            @click="$emit('generate-code')"
          >
            {{ generatingCode ? t('codegen.detail.generating') : t('codegen.detail.generate') }}
          </button>
          <button
            class="button button-primary"
            :disabled="!canExecute || executing"
            @click="$emit('execute')"
          >
            {{ executing ? t('codegen.detail.executing') : t('codegen.detail.execute') }}
          </button>
          <button
            class="button button-primary"
            :disabled="!canFinalize || finalizing"
            @click="$emit('finalize')"
          >
            {{ finalizing ? t('codegen.detail.finalizing') : t('codegen.detail.finalize') }}
          </button>
        </div>
      </div>

      <!-- Executions section -->
      <div class="section">
        <div class="section-header">
          <h3 class="section-title">{{ t('codegen.detail.executions') }}</h3>
          <button
            v-if="executions.length > 0"
            class="button-refresh"
            :disabled="executionsLoading"
            :title="isPolling ? t('codegen.detail.autoRefreshing') : t('codegen.detail.refresh')"
            @click="$emit('refresh-executions')"
          >
            <span v-if="isPolling" class="polling-indicator">⟳</span>
            <span v-else>↻</span>
          </button>
        </div>
        <div v-if="executionsLoading" class="loading-state">{{ t('common.loading') }}</div>
        <div v-else-if="executionsError" class="error-state">{{ executionsError }}</div>
        <div v-else-if="executions.length === 0" class="empty-state-small">{{ t('codegen.detail.noExecutions') }}</div>
        <div v-else class="execution-list">
          <div
            v-for="execution in executions"
            :key="execution.execution_id"
            class="execution-item"
            @click="$emit('open-execution', execution.execution_id)"
          >
            <div class="execution-id">{{ execution.execution_id.slice(0, 8) }}...</div>
            <div class="execution-status" :class="`status-${execution.status}`">
              {{ execution.status }}
            </div>
            <div class="execution-time">{{ formatTime(execution.created_at) }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import type { CodegenTemplate, CodegenExecution } from '../../types/codegen'

interface Props {
  template: CodegenTemplate | null
  executions: CodegenExecution[]
  executionsLoading: boolean
  executionsError?: string | null
  canConfirm: boolean
  canGenerateCode: boolean
  canExecute: boolean
  canFinalize: boolean
  confirming: boolean
  generatingCode: boolean
  executing: boolean
  finalizing: boolean
  isPolling?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  executionsError: null,
  isPolling: false
})
const { t } = useI18n()

const emit = defineEmits<{
  update: [payload: { generated_code: string }]
  confirm: []
  'generate-code': []
  execute: []
  finalize: []
  'open-execution': [executionId: string]
  'refresh-executions': []
}>()

const localCode = ref(props.template?.generated_code || '')

// Sync template code to local state
watch(() => props.template?.generated_code, (newCode) => {
  if (newCode !== undefined) {
    localCode.value = newCode || ''
  }
})

const canEdit = computed(() => {
  if (!props.template) return false
  const status = props.template.status
  return status === 'template_generated' || status === 'template_confirmed'
})

const updating = computed(() => props.confirming || props.generatingCode || props.executing || props.finalizing)

const metaPreview = computed(() => {
  if (!props.template) return '{}'
  return JSON.stringify(
    {
      parameter_template: props.template.parameter_template,
      parameter_schema: props.template.parameter_schema,
      output_config: props.template.output_config,
      status: props.template.status
    },
    null,
    2
  )
})

function handleUpdateCode() {
  emit('update', { generated_code: localCode.value })
}

function formatTime(time?: string): string {
  if (!time) return '未知时间'
  try {
    const date = new Date(time)
    return date.toLocaleString('zh-CN', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  } catch {
    return time
  }
}
</script>

<style scoped>
.template-detail-pane {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.detail-content {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-md);
}

.section {
  margin-bottom: var(--spacing-lg);
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--spacing-sm);
}

.section-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  margin: 0;
}

.code-editor {
  width: 100%;
  min-height: 220px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono',
    'Courier New', monospace;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  padding: 10px;
  background: #0f172a;
  color: #e5e7eb;
  font-size: 13px;
  line-height: 1.5;
  resize: vertical;
}

.code-editor:read-only {
  opacity: 0.7;
  cursor: not-allowed;
}

.json-preview {
  white-space: pre-wrap;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  padding: 10px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono',
    'Courier New', monospace;
  font-size: 12px;
  line-height: 1.5;
  max-height: 300px;
  overflow-y: auto;
  color: var(--text-primary);
}

.section-actions {
  margin-top: var(--spacing-sm);
}

.action-buttons {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.execution-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.execution-item {
  padding: var(--spacing-sm);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: var(--bg-tertiary);
  cursor: pointer;
  transition: all 0.2s;
}

.execution-item:hover {
  background: var(--bg-secondary);
  border-color: var(--accent-primary);
}

.execution-id {
  font-size: 12px;
  font-family: ui-monospace;
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.execution-status {
  font-size: 12px;
  font-weight: 500;
  margin-bottom: 2px;
}

.status-pending {
  color: #faad14;
}

.status-running {
  color: #1890ff;
}

.status-completed {
  color: #52c41a;
}

.status-failed {
  color: #ff4d4f;
}

.execution-time {
  font-size: 11px;
  color: var(--text-tertiary);
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-xl);
  text-align: center;
  color: var(--text-tertiary);
  height: 100%;
}

.empty-state-small {
  padding: var(--spacing-md);
  text-align: center;
  color: var(--text-tertiary);
  font-size: 13px;
}

.empty-icon {
  font-size: 48px;
  margin-bottom: var(--spacing-md);
  opacity: 0.5;
}

.empty-text {
  font-size: 16px;
  font-weight: 500;
  margin-bottom: var(--spacing-xs);
}

.empty-hint {
  font-size: 13px;
  opacity: 0.7;
}

.loading-state,
.error-state {
  padding: var(--spacing-md);
  text-align: center;
  font-size: 13px;
}

.error-state {
  color: var(--text-error, #ff4d4f);
}

.button {
  padding: 6px 16px;
  border-radius: 6px;
  border: 1px solid var(--border-color);
  background: var(--bg-primary);
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s;
}

.button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.button-secondary:hover:not(:disabled) {
  filter: brightness(1.02);
  background: var(--bg-tertiary);
}

.button-primary {
  background: var(--accent-primary);
  border-color: var(--accent-primary);
  color: #fff;
}

.button-primary:hover:not(:disabled) {
  filter: brightness(1.05);
}

.button-refresh {
  padding: 4px 8px;
  border: 1px solid var(--border-color);
  border-radius: 4px;
  background: var(--bg-primary);
  cursor: pointer;
  font-size: 14px;
  color: var(--text-secondary);
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 28px;
  height: 28px;
}

.button-refresh:hover:not(:disabled) {
  background: var(--bg-tertiary);
  color: var(--text-primary);
  border-color: var(--accent-primary);
}

.button-refresh:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.polling-indicator {
  display: inline-block;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>
