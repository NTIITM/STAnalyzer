<template>
  <Teleport to="body">
    <transition-group name="toast" tag="div" class="message-toast-container">
      <div
        v-for="message in messages"
        :key="message.id"
        class="message-toast"
        :class="`toast-${message.type}`"
      >
        <span class="toast-icon">{{ getIcon(message.type) }}</span>
        <span class="toast-message">{{ message.content }}</span>
        <button class="toast-close" @click="removeMessage(message.id)">×</button>
      </div>
    </transition-group>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

export interface ToastMessage {
  id: number
  type: 'success' | 'error' | 'warning' | 'info'
  content: string
  duration?: number
}

const messages = ref<ToastMessage[]>([])
let messageIdCounter = 0

/**
 * 显示消息
 */
function showMessage(type: ToastMessage['type'], content: string, duration: number = 3000) {
  const message: ToastMessage = {
    id: messageIdCounter++,
    type,
    content,
    duration
  }
  
  messages.value.push(message)
  
  if (duration > 0) {
    setTimeout(() => {
      removeMessage(message.id)
    }, duration)
  }
  
  return message.id
}

/**
 * 移除消息
 */
function removeMessage(id: number) {
  const index = messages.value.findIndex(m => m.id === id)
  if (index !== -1) {
    messages.value.splice(index, 1)
  }
}

/**
 * 获取图标
 */
function getIcon(type: ToastMessage['type']): string {
  switch (type) {
    case 'success': return '✅'
    case 'error': return '❌'
    case 'warning': return '⚠️'
    case 'info': return 'ℹ️'
  }
}

// 全局消息接口
declare global {
  interface Window {
    showMessage?: {
      success: (content: string, duration?: number) => number
      error: (content: string, duration?: number) => number
      warning: (content: string, duration?: number) => number
      info: (content: string, duration?: number) => number
    }
  }
}

/**
 * 导出方法供全局使用
 */
function setupGlobalMessage() {
  window.showMessage = {
    success: (content: string, duration?: number) => showMessage('success', content, duration),
    error: (content: string, duration?: number) => showMessage('error', content, duration || 5000),
    warning: (content: string, duration?: number) => showMessage('warning', content, duration),
    info: (content: string, duration?: number) => showMessage('info', content, duration)
  }
}

onMounted(() => {
  setupGlobalMessage()
})

onUnmounted(() => {
  if (window.showMessage) {
    delete window.showMessage
  }
})

defineExpose({
  showMessage,
  removeMessage
})
</script>

<style scoped>
.message-toast-container {
  position: fixed;
  top: 70px;
  right: 1rem;
  z-index: 10001;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  pointer-events: none;
}

.message-toast {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.875rem 1rem;
  background: var(--bg-secondary);
  backdrop-filter: var(--backdrop-blur);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  box-shadow: var(--shadow-lg);
  min-width: 300px;
  max-width: 500px;
  pointer-events: auto;
  animation: slideInRight 0.3s ease;
}

.toast-success {
  border-left: 4px solid rgba(100, 200, 100, 0.8);
}

.toast-error {
  border-left: 4px solid rgba(220, 100, 100, 0.8);
}

.toast-warning {
  border-left: 4px solid rgba(255, 180, 0, 0.8);
}

.toast-info {
  border-left: 4px solid rgba(100, 150, 220, 0.8);
}

.toast-icon {
  font-size: 1.2rem;
  flex-shrink: 0;
}

.toast-message {
  flex: 1;
  font-size: 0.9rem;
  color: var(--text-primary);
  line-height: 1.4;
}

.toast-close {
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  font-size: 1.25rem;
  color: var(--text-secondary);
  cursor: pointer;
  border-radius: 4px;
  transition: all 0.2s ease;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
}

.toast-close:hover {
  background: var(--bg-tertiary);
  color: var(--text-primary);
}

@keyframes slideInRight {
  from {
    transform: translateX(100%);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}

.toast-enter-active,
.toast-leave-active {
  transition: all 0.3s ease;
}

.toast-enter-from {
  transform: translateX(100%);
  opacity: 0;
}

.toast-leave-to {
  transform: translateX(100%);
  opacity: 0;
}
</style>

