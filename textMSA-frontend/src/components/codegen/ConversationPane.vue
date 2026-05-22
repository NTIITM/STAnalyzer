<template>
  <div class="conversation-pane">
    <!-- Loading state -->
    <div v-if="loading && conversation.length === 0" class="empty-state">
      <div class="loading-spinner">{{ t('codegen.conversation.loading') }}</div>
    </div>

    <!-- Error state -->
    <div v-else-if="error" class="error-banner">
      <span class="error-icon">⚠️</span>
      <span class="error-text">{{ error }}</span>
    </div>

    <!-- Empty state -->
    <div v-else-if="conversation.length === 0" class="empty-state">
      <div class="empty-icon">💬</div>
      <div class="empty-text">{{ t('codegen.conversation.empty') }}</div>
      <div class="empty-hint">{{ t('codegen.conversation.hint') }}</div>
    </div>

    <!-- Conversation timeline -->
    <div v-else class="conversation-timeline">
      <div
        v-for="(message, idx) in conversation"
        :key="idx"
        class="message"
        :class="message.role"
      >
        <div class="message-role">{{ message.role === 'user' ? t('codegen.conversation.user') : 'Agent' }}</div>
        <div class="message-content">{{ message.text }}</div>
        <div class="message-time">{{ formatTime(message.time) }}</div>
      </div>
    </div>

    <!-- Input area -->
    <div class="conversation-input">
      <textarea
        v-model="localDraft"
        :disabled="!templateId || pendingTurn"
        :placeholder="t('codegen.conversation.placeholder')"
        rows="3"
        @input="handleDraftUpdate"
        @keydown.enter.exact.prevent="handleSend"
        @keydown.enter.shift.exact="handleNewLine"
      />
      <div class="input-actions">
        <button
          class="button button-primary"
          :disabled="!templateId || pendingTurn || !localDraft.trim()"
          @click="handleSend"
        >
          {{ pendingTurn ? t('codegen.conversation.sending') : t('codegen.conversation.send') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import type { CodegenConversationMessage } from '../../types/codegen'

interface Props {
  conversation: CodegenConversationMessage[]
  pendingTurn: boolean
  draft: string
  loading: boolean
  error?: string | null
  templateId: string | null
}

const props = withDefaults(defineProps<Props>(), {
  error: null
})

const emit = defineEmits<{
  send: [message: string]
  'update-draft': [draft: string]
}>()

const { t } = useI18n()
const localDraft = ref(props.draft)

// Sync draft prop to local state
watch(() => props.draft, (newDraft) => {
  localDraft.value = newDraft
})

function handleDraftUpdate() {
  emit('update-draft', localDraft.value)
}

function handleSend() {
  const message = localDraft.value.trim()
  if (!message || props.pendingTurn || !props.templateId) {
    return
  }
  emit('send', message)
  localDraft.value = ''
  emit('update-draft', '')
}

function handleNewLine() {
  // Allow Shift+Enter for new line
}

function formatTime(time: string): string {
  try {
    const date = new Date(time)
    return date.toLocaleString(undefined, {
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
.conversation-pane {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}

.conversation-timeline {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-lg);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.message {
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: var(--spacing-md);
  background: var(--bg-tertiary);
  max-width: 85%;
  align-self: flex-start;
}

.message.user {
  align-self: flex-end;
  background: var(--accent-primary);
  color: #fff;
  border-color: var(--accent-hover);
}

.message-role {
  font-size: 12px;
  opacity: 0.75;
  margin-bottom: 4px;
  font-weight: 500;
}

.message-content {
  font-size: 14px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}

.message-time {
  font-size: 11px;
  opacity: 0.6;
  margin-top: var(--spacing-xs);
}

.conversation-input {
  border-top: 1px solid var(--border-color);
  padding: var(--spacing-md);
  background: var(--bg-secondary);
  flex-shrink: 0;
}

.conversation-input textarea {
  width: 100%;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  padding: var(--spacing-sm);
  font-size: 14px;
  font-family: inherit;
  resize: vertical;
  background: var(--bg-primary);
  color: var(--text-primary);
}

.conversation-input textarea:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.conversation-input textarea:focus {
  outline: 2px solid var(--accent-primary);
  outline-offset: 2px;
}

.input-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: var(--spacing-sm);
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-xl);
  text-align: center;
  color: var(--text-tertiary);
  flex: 1;
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

.loading-spinner {
  font-size: 14px;
  color: var(--text-secondary);
}

.error-banner {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-md);
  background: #fff3cd;
  border-bottom: 1px solid #ffc107;
  color: #856404;
  font-size: 13px;
}

.error-icon {
  font-size: 16px;
}

.error-text {
  flex: 1;
}

.button {
  padding: 6px 16px;
  border-radius: 6px;
  border: 1px solid var(--border-color);
  background: var(--accent-primary);
  color: #fff;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s;
}

.button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.button-primary:hover:not(:disabled) {
  filter: brightness(1.05);
}
</style>

