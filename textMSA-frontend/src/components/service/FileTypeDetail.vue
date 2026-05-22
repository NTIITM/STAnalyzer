<template>
  <div class="file-type-detail">
    <div v-if="loading" class="loading-state">
      <el-skeleton :rows="4" animated />
    </div>
    <div v-else-if="error" class="error-state">
      <el-alert :title="error" type="error" show-icon :closable="false" />
    </div>
    <div v-else-if="fileType" class="detail-content">
      <div class="detail-section">
        <h3>基本信息</h3>
        <div class="detail-item">
          <span class="detail-label">文件类型 ID:</span>
          <span class="detail-value">{{ fileType.id }}</span>
        </div>
        <div class="detail-item">
          <span class="detail-label">名称:</span>
          <span class="detail-value">{{ fileType.name }}</span>
        </div>
        <div class="detail-item">
          <span class="detail-label">显示名称:</span>
          <span class="detail-value">{{ fileType.display_name }}</span>
        </div>
        <div v-if="fileType.description" class="detail-item">
          <span class="detail-label">描述:</span>
          <span class="detail-value">{{ fileType.description }}</span>
        </div>
        <div v-if="fileType.category" class="detail-item">
          <span class="detail-label">分类:</span>
          <span class="detail-value">{{ fileType.category }}</span>
        </div>
        <div class="detail-item">
          <span class="detail-label">扩展名:</span>
          <div class="extensions-list">
            <span 
              v-for="ext in fileType.extensions" 
              :key="ext"
              class="extension-badge"
            >
              {{ ext }}
            </span>
            <span v-if="fileType.extensions.length === 0" class="no-extensions">
              无扩展名
            </span>
          </div>
        </div>
        <div v-if="fileType.is_default !== undefined" class="detail-item">
          <span class="detail-label">默认类型:</span>
          <span class="detail-value">
            <el-tag :type="fileType.is_default ? 'success' : 'info'">
              {{ fileType.is_default ? '是' : '否' }}
            </el-tag>
          </span>
        </div>
      </div>
    </div>
    <div v-else class="empty-state">
      <span>未找到文件类型信息</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { ElSkeleton, ElAlert, ElTag } from 'element-plus'
import { getFileTypes } from '../../api/file'
import type { FileType } from '../../types/file'

const props = defineProps<{
  fileTypeId: string
}>()

const fileType = ref<FileType | null>(null)
const loading = ref(false)
const error = ref('')

/**
 * 加载文件类型详情
 */
async function loadFileType() {
  if (!props.fileTypeId) {
    fileType.value = null
    return
  }

  try {
    loading.value = true
    error.value = ''
    
    // 获取所有文件类型，然后根据 ID 查找
    const allFileTypes = await getFileTypes({ force: false })
    const found = allFileTypes.find(ft => ft.id === props.fileTypeId)
    
    if (found) {
      fileType.value = found
    } else {
      error.value = '未找到指定的文件类型'
      fileType.value = null
    }
  } catch (err: any) {
    console.error('Failed to load file type:', err)
    error.value = err.message || '加载文件类型失败'
    fileType.value = null
  } finally {
    loading.value = false
  }
}

// 监听 fileTypeId 变化
watch(() => props.fileTypeId, () => {
  loadFileType()
}, { immediate: true })

onMounted(() => {
  loadFileType()
})
</script>

<style scoped>
.file-type-detail {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.detail-content {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.detail-section {
  border-bottom: 1px solid var(--border-color);
  padding-bottom: 1rem;
}

.detail-section:last-of-type {
  border-bottom: none;
}

.detail-section h3 {
  margin: 0 0 0.75rem 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
}

.detail-item {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
  font-size: 0.9rem;
  align-items: flex-start;
}

.detail-label {
  color: var(--text-secondary);
  font-weight: 500;
  min-width: 100px;
  flex-shrink: 0;
}

.detail-value {
  color: var(--text-primary);
  flex: 1;
  word-break: break-word;
}

.extensions-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  align-items: center;
}

.extension-badge {
  display: inline-flex;
  align-items: center;
  padding: 0.25rem 0.625rem;
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  color: white;
  border-radius: 4px;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', 'Consolas', monospace;
  font-size: 0.8125rem;
  font-weight: 500;
  box-shadow: 0 2px 4px rgba(59, 130, 246, 0.2);
}

.no-extensions {
  color: var(--text-tertiary);
  font-style: italic;
}

.loading-state,
.error-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 2rem;
  color: var(--text-secondary);
}

.empty-state {
  color: var(--text-tertiary);
  font-style: italic;
}
</style>

