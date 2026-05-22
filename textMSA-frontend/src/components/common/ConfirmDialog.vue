<template>
  <Teleport to="body">
    <Transition name="dialog-fade">
      <div v-if="visible" class="confirm-dialog-overlay" @click="handleOverlayClick">
        <div class="confirm-dialog" @click.stop>
          <div class="confirm-dialog-header">
            <span class="confirm-dialog-icon">⚠️</span>
            <h3 class="confirm-dialog-title">{{ title }}</h3>
          </div>
          <div class="confirm-dialog-body">
            <p class="confirm-dialog-message">{{ message }}</p>
            <p v-if="detail" class="confirm-dialog-detail">{{ detail }}</p>
          </div>
          <div class="confirm-dialog-footer">
            <button class="confirm-dialog-btn cancel" @click="handleCancel">
              {{ cancelText }}
            </button>
            <button class="confirm-dialog-btn confirm" @click="handleConfirm">
              {{ confirmText }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref } from 'vue'

interface Props {
  title?: string
  message: string
  detail?: string
  confirmText?: string
  cancelText?: string
  closeOnClickOutside?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  title: '确认',
  confirmText: '确认',
  cancelText: '取消',
  closeOnClickOutside: true
})

const emit = defineEmits<{
  confirm: []
  cancel: []
}>()

const visible = ref(false)

function show() {
  visible.value = true
}

function hide() {
  visible.value = false
}

function handleConfirm() {
  emit('confirm')
  hide()
}

function handleCancel() {
  emit('cancel')
  hide()
}

function handleOverlayClick() {
  if (props.closeOnClickOutside) {
    handleCancel()
  }
}

defineExpose({
  show,
  hide
})
</script>

<style scoped>
.confirm-dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  backdrop-filter: blur(2px);
}

.confirm-dialog {
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 12px 48px rgba(0, 0, 0, 0.2);
  min-width: 400px;
  max-width: 500px;
  overflow: hidden;
  animation: dialog-bounce 0.3s ease-out;
}

@keyframes dialog-bounce {
  0% {
    transform: scale(0.9);
    opacity: 0;
  }
  50% {
    transform: scale(1.02);
  }
  100% {
    transform: scale(1);
    opacity: 1;
  }
}

.confirm-dialog-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 20px 24px 16px;
  border-bottom: 1px solid #f0f0f0;
}

.confirm-dialog-icon {
  font-size: 24px;
  line-height: 1;
}

.confirm-dialog-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #1f2937;
}

.confirm-dialog-body {
  padding: 20px 24px;
}

.confirm-dialog-message {
  margin: 0 0 12px 0;
  font-size: 15px;
  font-weight: 500;
  color: #374151;
  line-height: 1.6;
}

.confirm-dialog-detail {
  margin: 0;
  font-size: 13px;
  color: #6b7280;
  line-height: 1.5;
  padding: 12px;
  background: #f9fafb;
  border-radius: 6px;
  border-left: 3px solid #fbbf24;
}

.confirm-dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 24px 20px;
  border-top: 1px solid #f0f0f0;
}

.confirm-dialog-btn {
  padding: 8px 20px;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  border: none;
  outline: none;
}

.confirm-dialog-btn.cancel {
  background: #f3f4f6;
  color: #374151;
}

.confirm-dialog-btn.cancel:hover {
  background: #e5e7eb;
}

.confirm-dialog-btn.confirm {
  background: #3b82f6;
  color: #fff;
}

.confirm-dialog-btn.confirm:hover {
  background: #2563eb;
}

.dialog-fade-enter-active,
.dialog-fade-leave-active {
  transition: opacity 0.2s ease;
}

.dialog-fade-enter-from,
.dialog-fade-leave-to {
  opacity: 0;
}
</style>
