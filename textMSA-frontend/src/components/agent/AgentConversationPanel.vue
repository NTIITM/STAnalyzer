<template>
  <div class="agent-conversation-shell">
    <section class="agent-conversation-body">
      <div v-if="!hasProject" class="state-card">
        <div class="state-title">{{ t('app.agentConversationSelectProjectTitle') }}</div>
        <p class="state-subtitle">{{ t('app.agentConversationSelectProjectSubtitle') }}</p>
      </div>

      <div v-else-if="loading" class="state-card">
        <div class="skeleton-line" />
        <div class="skeleton-line short" />
        <div class="skeleton-line" />
      </div>

      <div v-else-if="error" class="state-card error">
        <div class="state-title">{{ t('app.agentConversationLoadFailed') }}</div>
        <p class="state-subtitle">{{ error }}</p>
      </div>

      <div v-else-if="!messages.length" class="state-card">
        <div class="state-title">{{ t('app.noConversation') }}</div>
      </div>

      <div v-else class="message-stack">
        <div
          class="message-list"
          ref="messageListRef"
          @scroll="handleMessageListScroll"
        >
          <div
            v-for="message in normalizedMessages"
            :key="message.key"
            class="message-card"
            :data-role="message.role"
          >
            <div class="message-meta">
              <span class="badge" :data-role="message.role">{{ message.roleLabel }}</span>
              <span class="timestamp">{{ message.time }}</span>
            </div>
            <AgentMessageContent
              :message="message.content"
              :extra="message.extra"
            />
          </div>

          <div
            v-if="sending || conversationActive"
            class="message-card typing-indicator-card"
            data-role="assistant"
          >
            <div class="message-meta">
              <span class="badge" data-role="assistant">{{ t('app.agent') }}</span>
              <span class="timestamp"></span>
            </div>
            <div class="typing-indicator">
              <span class="dot" />
              <span class="dot" />
              <span class="dot" />
            </div>
          </div>
        </div>
      </div>
    </section>

    <footer class="composer">
      <div class="context-bar">
        <div class="context-header">
          <div class="context-label">{{ t('app.agentConversationContextTitle') }}</div>
          <div class="context-actions" v-if="contextFiles.length">
            <span class="context-count">{{ t('app.agentConversationContextCount', { count: contextFiles.length }) }}</span>
            <button class="chip-clear" type="button" @click="clearContextFiles">{{ t('common.clear') }}</button>
          </div>
          <div class="context-hint" v-else>{{ t('app.agentConversationContextHint') }}</div>
        </div>

        <div class="context-chips" v-if="contextFiles.length">
          <span
            v-for="file in contextFiles"
            :key="file.fileId"
            class="context-chip"
            :title="file.fileName"
          >
            <span class="chip-text">{{ file.fileName || file.fileId }}</span>
            <button
              class="chip-remove"
              @click="removeContextFile(file.fileId)"
              :aria-label="t('app.agentConversationContextRemoveFileAria')"
            >
              ×
            </button>
          </span>
        </div>

        <div class="context-toast" v-if="contextToast">{{ contextToast }}</div>
      </div>

      <textarea
        v-model="messageDraft"
        class="composer-input"
        :placeholder="hasProject ? t('app.queryPlaceholder') : t('app.agentConversationSelectProjectHint')"
        :disabled="!hasProject || sending"
        @keydown.enter.exact.prevent="handleSend"
      />
      <div class="composer-actions">
        <button
          type="button"
          class="ax-btn danger"
          :disabled="clearing || !hasProject || !messages.length"
          @click="handleClear"
        >
          {{ clearing ? t('app.agentConversationClearing') : t('app.agentConversationClear') }}
        </button>
        <button
          type="button"
          class="ax-btn"
          :disabled="sendDisabled"
          @click="handleSend"
        >
          {{ sending ? t('app.agentConversationSending') : t('app.send') }}
        </button>
      </div>
    </footer>

    <ConfirmDialog
      ref="confirmDialogRef"
      :title="t('common.warning')"
      :message="t('app.agentConversationNoContextWarning')"
      :detail="t('app.agentConversationNoContextWarningDetail')"
      :confirm-text="t('common.confirm')"
      :cancel-text="t('common.cancel')"
      @confirm="handleConfirmSend"
      @cancel="handleCancelSend"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import type { AgentConversationMessage } from '../../types/agent'
import AgentMessageContent from './AgentMessageContent.vue'
import ConfirmDialog from '../common/ConfirmDialog.vue'
import { useAgentConversationStream } from '../../composables/useAgentConversationStream'

const props = defineProps<{
  projectId: string | null
  projectName: string | null
}>()

const emit = defineEmits<{
  (e: 'conversation-start'): void
  (e: 'conversation-stop'): void
  (e: 'dag-refresh-files'): void
}>()

const { t } = useI18n()

const hasProject = computed(() => Boolean(props.projectId))
const clearing = ref(false)
const messageDraft = ref('')
const contextFiles = ref<{ fileId: string; fileName: string }[]>([])
const contextToast = ref('')
const messageListRef = ref<HTMLElement | null>(null)
const userLockedScroll = ref(false)
const confirmDialogRef = ref<InstanceType<typeof ConfirmDialog> | null>(null)
const pendingMessage = ref('')

const {
  projectId: globalProjectId,
  messages,
  sending,
  loading,
  error,
  conversationActive,
  loadConversation,
  sendMessage,
  clearConversation
} = useAgentConversationStream()

function parseExtra(extra: unknown) {
  if (!extra) return null
  let value: unknown = extra

  // 处理多层字符串包裹的 JSON（后端已 json dump，但可能再次作为字符串返回）
  for (let i = 0; i < 2 && typeof value === 'string'; i += 1) {
    try {
      const parsed = JSON.parse(value)
      value = parsed
    } catch {
      // 非合法 JSON 字符串直接退出
      break
    }
  }

  if (value && typeof value === 'object') {
    return value as Record<string, unknown>
  }
  return null
}

const normalizedMessages = computed(() =>
  messages.value.map((message, idx) => {
    // 优先使用后端提供的时间字段，其次才回退到前端当前时间
    const m = message as unknown as {
      timestamp?: string
      time?: string
      created_at?: string
      updated_at?: string
    }
    const tsRaw = m.timestamp ?? m.time ?? m.created_at ?? m.updated_at
    const ts = tsRaw ? new Date(tsRaw) : new Date()
    const body = (message as { message?: string; content?: string }).message ?? message.content ?? ''
    return {
      key: message.message_id ?? `msg-${idx}`,
      role: message.role,
      roleLabel: roleLabel(message.role),
      time: `${ts.getHours().toString().padStart(2, '0')}:${ts.getMinutes().toString().padStart(2, '0')}`,
      content: body,
      extra: parseExtra(message.extra)
    }
  })
)

const sendDisabled = computed(
  () => !hasProject.value || sending.value || !messageDraft.value.trim()
)

async function loadConversationForCurrentProject() {
  if (!props.projectId) {
    await loadConversation(null)
    return
  }

  await loadConversation(props.projectId)
  await nextTick()
  scrollToBottom(true)
}

async function handleSend() {
  if (sendDisabled.value) return
  if (!props.projectId) return
  
  const content = messageDraft.value.trim()
  
  // 检查 context files 是否为空，如果为空则显示确认对话框
  if (contextFiles.value.length === 0) {
    pendingMessage.value = content
    confirmDialogRef.value?.show()
    return
  }
  
  // 直接发送
  await doSendMessage(content)
}

async function handleConfirmSend() {
  // 用户确认发送
  if (pendingMessage.value) {
    await doSendMessage(pendingMessage.value)
    pendingMessage.value = ''
  }
}

function handleCancelSend() {
  // 用户取消发送，不清空输入框
  pendingMessage.value = ''
}

async function doSendMessage(content: string) {
  messageDraft.value = ''
  await nextTick()
  scrollToBottom(true)

  await sendMessage({
    projectId: props.projectId!,
    content,
    contextFiles: contextFiles.value.map((f) => f.fileId)
  })
}

async function handleClear() {
  if (!props.projectId) return
  const confirmed = window.confirm(t('app.agentConversationClearConfirm'))
  if (!confirmed) return
  try {
    clearing.value = true
    await clearConversation(props.projectId)
  } catch (err) {
    error.value =
      (err as { message?: string })?.message ||
      (err as Error)?.toString() ||
      t('app.agentConversationClearFailed')
  } finally {
    clearing.value = false
  }
}

function roleLabel(role: AgentConversationMessage['role']) {
  if (role === 'assistant') return t('app.agent')
  if (role === 'system') return t('app.system')
  return t('app.user')
}

function isNearBottom(el: HTMLElement, threshold = 120) {
  const distance = el.scrollHeight - el.scrollTop - el.clientHeight
  return distance <= threshold
}

function handleMessageListScroll() {
  const el = messageListRef.value
  if (!el) return
  userLockedScroll.value = !isNearBottom(el)
}

function scrollToBottom(force = false) {
  const el = messageListRef.value
  if (!el) return
  if (force || !userLockedScroll.value || isNearBottom(el)) {
    requestAnimationFrame(() => {
      el.scrollTo({
        top: el.scrollHeight,
        behavior: 'smooth'
      })
    })
  }
}

function addFileToContext(fileId: string, fileName: string) {
  if (!fileId) return
  const exists = contextFiles.value.some((f) => f.fileId === fileId)
  if (!exists) {
    contextFiles.value = [...contextFiles.value, { fileId, fileName }]
  }
  contextToast.value = t('app.agentConversationContextAdded', { name: fileName || fileId })
  setTimeout(() => (contextToast.value = ''), 2200)
}

function removeContextFile(fileId: string) {
  contextFiles.value = contextFiles.value.filter((f) => f.fileId !== fileId)
  contextToast.value = ''
}

function clearContextFiles() {
  contextFiles.value = []
  contextToast.value = ''
}

defineExpose({
  addFileToContext,
  removeContextFile,
  clearContextFiles
})

onMounted(() => {
  globalProjectId.value = props.projectId
  void loadConversationForCurrentProject()
})

onUnmounted(() => {
  emit('conversation-stop')
})

watch(
  conversationActive,
  (active, prev) => {
    if (active && !prev) {
      emit('conversation-start')
    } else if (!active && prev) {
      emit('conversation-stop')
    }
  },
  { immediate: true }
)

watch(
  () => props.projectId,
  () => {
    globalProjectId.value = props.projectId
    void loadConversationForCurrentProject()
  }
)

watch(
  () => messages.value.length,
  () => {
    void nextTick().then(() => scrollToBottom(false))

    if (!sending.value) return
    const last = messages.value[messages.value.length - 1]
    if (!last) return
    const extraParsed = parseExtra((last as any).extra)
    if (!extraParsed) return
    const anyExtra = extraParsed as any
    const hasFiles = Array.isArray(anyExtra.files) && anyExtra.files.length > 0
    if (hasFiles) {
      emit('dag-refresh-files')
    }
  }
)

onUnmounted(() => {})
</script>

<style scoped>
.agent-conversation-shell {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
}

.agent-conversation-body {
  flex: 1;
  min-height: 0;
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 12px;
  padding: 16px;
  background: #fff;
}

.state-card {
  border: 1px dashed #e5e7eb;
  border-radius: 12px;
  padding: 24px;
  text-align: center;
  color: #6b7280;
  background: #fafafa;
}

.state-card.error {
  border-color: #ff4d4f;
  color: #b91c1c;
  background: #fff6f5;
}

.state-title {
  font-weight: 600;
  color: #111827;
  margin-bottom: 8px;
}

.state-subtitle {
  margin: 0 0 12px 0;
  font-size: 14px;
}

.skeleton-line {
  height: 14px;
  background: linear-gradient(90deg, #f0f2f5 25%, #e5e7eb 37%, #f0f2f5 63%);
  background-size: 400% 100%;
  animation: shimmer 1.4s ease infinite;
  border-radius: 8px;
  margin-bottom: 10px;
}

.skeleton-line.short {
  width: 60%;
}

.message-stack {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
}

.message-list {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 14px;
  background: #fff;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 360px;
}

.message-card {
  border: 1px solid #eef2f7;
  border-radius: 12px;
  padding: 12px 14px;
  background: #fff;
  box-shadow: 0 2px 6px rgba(17, 24, 39, 0.04);
  min-width: 80%;
  max-width: 95%;
  word-break: break-word;
}

.message-card[data-role='user'] {
  background: #eef2ff;
  border-color: #e0e7ff;
  align-self: flex-end;
}

.message-card[data-role='assistant'] {
  background: #ecfdf3;
  border-color: #d1fae5;
}

.typing-indicator-card {
  max-width: 200px;
}

.typing-indicator {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 6px;
}

.typing-indicator .dot {
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: #4ade80;
  opacity: 0.4;
  animation: typing-bounce 1.2s infinite ease-in-out;
}

.typing-indicator .dot:nth-child(2) {
  animation-delay: 0.15s;
}

.typing-indicator .dot:nth-child(3) {
  animation-delay: 0.3s;
}

.message-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
  color: #6b7280;
  font-size: 12px;
}

.badge {
  padding: 4px 10px;
  border-radius: 999px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.badge[data-role='assistant'] {
  background: #ecfdf3;
  color: #047857;
}

.badge[data-role='user'] {
  background: #e0e7ff;
  color: #3730a3;
}

.badge[data-role='system'] {
  background: #fef3c7;
  color: #b45309;
}

.timestamp {
  font-variant-numeric: tabular-nums;
}

.message-content {
  color: #111827;
  line-height: 1.6;
  white-space: pre-wrap;
}

.context-bar {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
}

.context-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.context-label {
  font-weight: 600;
  font-size: 13px;
  color: #0f172a;
}

.context-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.context-count {
  font-size: 12px;
  color: #64748b;
}

.context-hint {
  font-size: 12px;
  color: #94a3b8;
}

.context-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.context-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  background: #ffffff;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  font-size: 12px;
  color: #0f172a;
  max-width: 200px;
}

.chip-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chip-remove {
  border: none;
  background: transparent;
  color: #475569;
  width: 16px;
  height: 16px;
  cursor: pointer;
  line-height: 1;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  transition: all 0.2s ease;
}

.chip-remove:hover {
  background: #eef2f7;
  color: #0f172a;
}

.chip-clear {
  border: 1px solid #e5e7eb;
  background: #ffffff;
  color: #0f172a;
  border-radius: 8px;
  padding: 6px 10px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.chip-clear:hover {
  background: #f3f4f6;
}

.context-toast {
  font-size: 12px;
  color: #0f172a;
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 6px 10px;
  width: fit-content;
}

.composer {
  display: flex;
  flex-direction: column;
  gap: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 12px;
  background: #fff;
}

.composer-input {
  width: 100%;
  min-height: 96px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 10px 12px;
  resize: vertical;
  font-family: inherit;
  font-size: 14px;
  line-height: 1.5;
}

.composer-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.ax-btn {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 6px 12px;
  background: #ffffff;
  cursor: pointer;
  font-weight: 600;
  color: #111827;
  transition: all 0.2s ease;
}

.ax-btn:hover:not(:disabled) {
  border-color: #4338ca;
  color: #4338ca;
  box-shadow: 0 2px 6px rgba(67, 56, 202, 0.12);
}

.ax-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.ax-btn.ghost {
  background: #f9fafb;
}

.ax-btn.danger {
  color: #b91c1c;
  border-color: #fecdd3;
  background: #fff1f2;
}

.ax-btn.danger:hover:not(:disabled) {
  border-color: #f87171;
  color: #991b1b;
  box-shadow: 0 2px 6px rgba(248, 113, 113, 0.24);
}

@keyframes shimmer {
  0% {
    background-position: 100% 0;
  }
  100% {
    background-position: -100% 0;
  }
}

@keyframes typing-bounce {
  0%,
  60%,
  100% {
    transform: translateY(0);
    opacity: 0.4;
  }
  30% {
    transform: translateY(-3px);
    opacity: 1;
  }
}

@media (max-width: 1200px) {
  .conversation-grid {
    grid-template-columns: 1fr;
  }
  .conversation-list {
    max-height: 240px;
  }
}
</style>
