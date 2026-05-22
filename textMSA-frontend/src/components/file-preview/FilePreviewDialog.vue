<template>
  <Teleport to="body">
    <div 
      v-if="visible"
      class="file-preview-dialog-overlay"
      @click.self="handleClose"
    >
      <div class="file-preview-dialog">
        <div class="dialog-header">
          <h3>{{ fileName }}</h3>
          <button class="dialog-close-btn" @click="handleClose">×</button>
        </div>
        <div class="dialog-content">
          <div v-if="loading" class="loading-container">
            <div class="loading-spinner"></div>
          <p>{{ t('filePreview.loading') }}</p>
          </div>
          <div v-else-if="error" class="error-container">
            <p class="error-message">{{ error }}</p>
            <button @click="loadFile" class="retry-btn">{{ t('common.retry') }}</button>
          </div>
          <SpreadsheetPreview
            v-else-if="fileType === 'spreadsheet'"
            :file-id="fileId"
            :file-name="fileName"
          />
          <ImagePreview
            v-else-if="fileType === 'image'"
            :file-id="fileId"
            :file-name="fileName"
          />
          <TextPreview
            v-else-if="fileType === 'text'"
            :file-id="fileId"
            :file-name="fileName"
          />
          <div v-else class="unsupported-container">
            <p>{{ t('filePreview.unsupported', { ext: fileType }) }}</p>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import SpreadsheetPreview from './SpreadsheetPreview.vue'
import ImagePreview from './ImagePreview.vue'
import TextPreview from './TextPreview.vue'
import type { FileCategory } from '../../utils/fileType'

const props = defineProps<{
  fileId: string
  fileName: string
  fileType: FileCategory
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const loading = ref(false)
const error = ref<string | null>(null)
const { t } = useI18n()

const handleClose = () => {
  emit('close')
}

const loadFile = () => {
  // 文件加载由子组件处理
  error.value = null
}

watch(() => props.visible, (newVal) => {
  if (newVal) {
    error.value = null
    loading.value = false
  }
})
</script>

<style scoped>
.file-preview-dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10000;
  animation: fadeIn 0.2s ease;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.file-preview-dialog {
  background: var(--bg-primary, white);
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
  width: 90%;
  max-width: 1200px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  animation: slideUp 0.3s ease;
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.5rem;
  border-bottom: 1px solid var(--border-color, rgba(200, 200, 210, 0.5));
  background: var(--bg-secondary, rgba(245, 247, 250, 0.95));
}

.dialog-header h3 {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 600;
  color: var(--text-primary, rgba(60, 60, 70, 0.9));
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  min-width: 0;
}

.dialog-close-btn {
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  font-size: 1.5rem;
  color: var(--text-secondary, rgba(100, 100, 110, 0.7));
  cursor: pointer;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
  flex-shrink: 0;
  margin-left: 1rem;
}

.dialog-close-btn:hover {
  background: var(--bg-tertiary, rgba(245, 247, 250, 0.95));
  color: var(--text-primary, rgba(60, 60, 70, 0.9));
}

.dialog-content {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.loading-container,
.error-container,
.unsupported-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem;
  min-height: 300px;
}

.loading-spinner {
  width: 40px;
  height: 40px;
  border: 4px solid var(--border-color, rgba(200, 200, 210, 0.3));
  border-top-color: var(--accent-primary, #1890ff);
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 1rem;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.error-message {
  color: var(--text-danger, #ff4d4f);
  margin-bottom: 1rem;
  text-align: center;
}

.retry-btn {
  padding: 0.5rem 1rem;
  background: var(--accent-primary, #1890ff);
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.875rem;
  transition: background 0.2s ease;
}

.retry-btn:hover {
  background: var(--accent-hover, #40a9ff);
}

.unsupported-container p {
  color: var(--text-secondary, rgba(100, 100, 110, 0.7));
  font-size: 1rem;
}
</style>
