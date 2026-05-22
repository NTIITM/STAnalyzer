<template>
  <div class="text-preview-container">
    <div v-if="loading" class="loading-container">
      <div class="loading-spinner"></div>
      <p>{{ t('filePreview.loading') }}</p>
    </div>
    <div v-else-if="error" class="error-container">
      <p class="error-message">{{ error }}</p>
      <button @click="loadFile" class="retry-btn">{{ t('common.retry') }}</button>
    </div>
    <div v-else class="text-content-wrapper">
      <div class="text-content" ref="textContentRef">
        <pre>{{ textContent }}</pre>
      </div>
      <div v-if="textContent" class="text-info">
        <span>{{ t('filePreview.charCount', { count: textContent.length }) }}</span>
        <span v-if="textContent.includes('\n')">{{ t('filePreview.lineCount', { count: textContent.split('\n').length }) }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { previewFileById } from '../../api/file'

const props = defineProps<{
  fileId: string
  fileName: string
}>()

const { t } = useI18n()
const loading = ref(false)
const error = ref<string | null>(null)
const textContent = ref('')
const textContentRef = ref<HTMLElement | null>(null)

// 最大文件大小限制（10MB）
const MAX_FILE_SIZE = 10 * 1024 * 1024

const loadFile = async () => {
  loading.value = true
  error.value = null
  
  try {
    // 使用 previewFileById 替代 downloadFileById，可以限制文件大小
    const blob = await previewFileById(props.fileId, { maxSize: MAX_FILE_SIZE })
    
    // 检查文件大小
    if (blob.size > MAX_FILE_SIZE) {
      throw new Error(t('filePreview.tooLarge', { size: Math.floor(MAX_FILE_SIZE / 1024 / 1024) }))
    }
    
    // 读取文本内容
    const text = await blob.text()
    textContent.value = text
    
    // 如果文件为空
    if (!text || text.trim().length === 0) {
      textContent.value = `(${t('filePreview.empty')})`
    }
  } catch (err: any) {
    console.error('Failed to load text file:', err)
    error.value = err.message || t('filePreview.loadFailed')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadFile()
})

onUnmounted(() => {
  // 清理资源
  textContent.value = ''
})
</script>

<style scoped>
.text-preview-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 400px;
  max-height: calc(90vh - 120px);
}

.loading-container,
.error-container {
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

.text-content-wrapper {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.text-content {
  flex: 1;
  overflow: auto;
  padding: 1.5rem;
  background: var(--bg-primary, white);
  border: 1px solid var(--border-color, rgba(200, 200, 210, 0.3));
  border-radius: 8px;
  margin: 1rem;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 0.875rem;
  line-height: 1.6;
  color: var(--text-primary, rgba(60, 60, 70, 0.9));
}

.text-content pre {
  margin: 0;
  white-space: pre-wrap;
  word-wrap: break-word;
  overflow-wrap: break-word;
}

.text-info {
  display: flex;
  gap: 1.5rem;
  padding: 0.75rem 1.5rem;
  background: var(--bg-secondary, rgba(245, 247, 250, 0.95));
  border-top: 1px solid var(--border-color, rgba(200, 200, 210, 0.3));
  font-size: 0.75rem;
  color: var(--text-secondary, rgba(100, 100, 110, 0.7));
}

/* 滚动条样式 */
.text-content::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

.text-content::-webkit-scrollbar-track {
  background: var(--bg-secondary, rgba(245, 247, 250, 0.5));
  border-radius: 4px;
}

.text-content::-webkit-scrollbar-thumb {
  background: var(--border-color, rgba(200, 200, 210, 0.5));
  border-radius: 4px;
}

.text-content::-webkit-scrollbar-thumb:hover {
  background: var(--border-color, rgba(200, 200, 210, 0.7));
}
</style>
