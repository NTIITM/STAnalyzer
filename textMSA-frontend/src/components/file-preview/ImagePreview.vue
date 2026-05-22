<template>
  <div class="image-preview">
    <div v-if="loading" class="loading-container">
      <div class="loading-spinner"></div>
      <p>{{ t('filePreview.loading') }}</p>
    </div>
    <div v-else-if="error" class="error-container">
      <p class="error-message">{{ error }}</p>
      <button @click="loadFile" class="retry-btn">{{ t('common.retry') }}</button>
    </div>
    <div v-else-if="imageUrl" class="image-container" ref="imageContainerRef">
      <div class="image-toolbar">
        <button @click="resetZoom" class="toolbar-btn" :title="t('imagePreview.resetZoom')">{{ t('imagePreview.reset') }}</button>
        <button @click="zoomIn" class="toolbar-btn" :title="t('imagePreview.zoomIn')">+</button>
        <button @click="zoomOut" class="toolbar-btn" :title="t('imagePreview.zoomOut')">-</button>
        <button @click="toggleFullscreen" class="toolbar-btn" :title="t('imagePreview.fullscreen')">{{ t('imagePreview.fullscreen') }}</button>
        <span class="zoom-info">{{ Math.round(scale * 100) }}%</span>
      </div>
      <div 
        class="image-wrapper"
        :style="{ transform: `scale(${scale}) translate(${translateX}px, ${translateY}px)` }"
        @mousedown="startDrag"
        @mousemove="onDrag"
        @mouseup="endDrag"
        @mouseleave="endDrag"
        @wheel.prevent="onWheel"
      >
        <img 
          :src="imageUrl" 
          :alt="fileName"
          class="preview-image"
          @load="onImageLoad"
        />
      </div>
      <div v-if="imageInfo" class="image-info">
        <span>{{ t('imagePreview.dimensions', { w: imageInfo.width, h: imageInfo.height }) }}</span>
        <span v-if="imageInfo.size">{{ t('imagePreview.size', { value: formatFileSize(imageInfo.size) }) }}</span>
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

const loading = ref(false)
const error = ref<string | null>(null)
const { t } = useI18n()
const imageUrl = ref<string | null>(null)
const scale = ref(1)
const translateX = ref(0)
const translateY = ref(0)
const isDragging = ref(false)
const dragStart = ref({ x: 0, y: 0 })
const imageContainerRef = ref<HTMLElement | null>(null)
const imageInfo = ref<{ width: number; height: number; size?: number } | null>(null)

const loadFile = async () => {
  loading.value = true
  error.value = null
  
  try {
    // 使用 previewFileById 替代 downloadFileById，可以请求优化后的图片
    const blob = await previewFileById(props.fileId, { imageSize: 'medium' })
    
    // 创建 Blob URL
    if (imageUrl.value) {
      URL.revokeObjectURL(imageUrl.value)
    }
    
    imageUrl.value = URL.createObjectURL(blob)
    imageInfo.value = { size: blob.size, width: 0, height: 0 }
  } catch (err: any) {
    console.error('Failed to load image:', err)
    error.value = err.message || t('imagePreview.loadFailed')
  } finally {
    loading.value = false
  }
}

const onImageLoad = (event: Event) => {
  const img = event.target as HTMLImageElement
  if (img) {
    imageInfo.value = {
      width: img.naturalWidth,
      height: img.naturalHeight,
      size: imageInfo.value?.size
    }
    // 自动适应容器
    resetZoom()
  }
}

const resetZoom = () => {
  scale.value = 1
  translateX.value = 0
  translateY.value = 0
}

const zoomIn = () => {
  scale.value = Math.min(scale.value + 0.1, 5)
}

const zoomOut = () => {
  scale.value = Math.max(scale.value - 0.1, 0.1)
}

const onWheel = (event: WheelEvent) => {
  event.preventDefault()
  const delta = event.deltaY > 0 ? -0.1 : 0.1
  scale.value = Math.max(0.1, Math.min(scale.value + delta, 5))
}

const startDrag = (event: MouseEvent) => {
  if (scale.value <= 1) return // 只有在放大时才允许拖拽
  isDragging.value = true
  dragStart.value = { x: event.clientX - translateX.value, y: event.clientY - translateY.value }
}

const onDrag = (event: MouseEvent) => {
  if (!isDragging.value) return
  translateX.value = event.clientX - dragStart.value.x
  translateY.value = event.clientY - dragStart.value.y
}

const endDrag = () => {
  isDragging.value = false
}

const toggleFullscreen = () => {
  if (!imageContainerRef.value) return
  
  if (!document.fullscreenElement) {
    imageContainerRef.value.requestFullscreen().catch((err) => {
      console.error('无法进入全屏模式:', err)
    })
  } else {
    document.exitFullscreen()
  }
}

const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
}

onMounted(() => {
  loadFile()
})

onUnmounted(() => {
  // 清理 Blob URL
  if (imageUrl.value) {
    URL.revokeObjectURL(imageUrl.value)
  }
})
</script>

<style scoped>
.image-preview {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
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

.image-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.image-toolbar {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--border-color, rgba(200, 200, 210, 0.5));
  background: var(--bg-secondary, rgba(245, 247, 250, 0.95));
}

.toolbar-btn {
  padding: 0.375rem 0.75rem;
  background: var(--bg-primary, white);
  border: 1px solid var(--border-color, rgba(200, 200, 210, 0.5));
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.875rem;
  color: var(--text-primary, rgba(60, 60, 70, 0.9));
  transition: all 0.2s ease;
}

.toolbar-btn:hover {
  background: var(--bg-tertiary, rgba(250, 250, 250, 0.5));
  border-color: var(--accent-primary, #1890ff);
}

.zoom-info {
  margin-left: auto;
  font-size: 0.875rem;
  color: var(--text-secondary, rgba(100, 100, 110, 0.7));
}

.image-wrapper {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  cursor: grab;
  transition: transform 0.1s ease-out;
}

.image-wrapper:active {
  cursor: grabbing;
}

.preview-image {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  user-select: none;
  pointer-events: none;
}

.image-info {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  padding: 0.75rem 1rem;
  border-top: 1px solid var(--border-color, rgba(200, 200, 210, 0.5));
  background: var(--bg-secondary, rgba(245, 247, 250, 0.95));
  font-size: 0.875rem;
  color: var(--text-secondary, rgba(100, 100, 110, 0.7));
}

.image-container:fullscreen {
  background: black;
}

.image-container:fullscreen .image-toolbar {
  background: rgba(0, 0, 0, 0.8);
  border-bottom-color: rgba(255, 255, 255, 0.2);
}

.image-container:fullscreen .toolbar-btn {
  background: rgba(255, 255, 255, 0.1);
  border-color: rgba(255, 255, 255, 0.3);
  color: white;
}

.image-container:fullscreen .toolbar-btn:hover {
  background: rgba(255, 255, 255, 0.2);
}

.image-container:fullscreen .zoom-info {
  color: rgba(255, 255, 255, 0.8);
}

.image-container:fullscreen .image-info {
  background: rgba(0, 0, 0, 0.8);
  border-top-color: rgba(255, 255, 255, 0.2);
  color: rgba(255, 255, 255, 0.8);
}
</style>
