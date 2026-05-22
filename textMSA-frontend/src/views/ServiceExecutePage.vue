<template>
  <div class="service-execute-page">
    <header class="page-header">
      <div class="header-left">
        <button class="back-btn" @click="handleBack">
          ← {{ $t('common.back') || 'Back' }}
        </button>
        <div class="title">
          <h2>{{ currentService?.name || $t('service.execute.title') }}</h2>
          <p v-if="currentService?.description" class="subtitle">{{ currentService.description }}</p>
        </div>
      </div>
      <div v-if="isMultiFile" class="header-right">
        <span class="badge">Multi-file mode</span>
      </div>
    </header>

    <div class="page-body">
      <aside class="info-panel" v-if="currentService">
        <div class="info-block">
          <h3>{{ $t('service.detail.acceptedFiles', 'Required Files') }}</h3>
          <p class="muted small">{{ $t('service.execute.multiFileHint', 'This service requires multiple input files. Please select or upload a file for each slot.') }}</p>
        </div>

        <!-- 为每个文件槽位创建独立的选择区域 -->
        <div 
          v-for="slot in acceptedFileSlots" 
          :key="slot.name"
          class="file-slot-section"
        >
          <div class="slot-header">
            <h4 class="slot-title">{{ slot.name }}</h4>
            <span class="required-badge" v-if="slot.required">*Required</span>
          </div>
          <p v-if="slot.description" class="slot-description muted small">{{ slot.description }}</p>
          <p class="slot-types muted small">
            <strong>Accepted Types:</strong> {{ slot.file_type_ids.map(renderFileTypeName).join(', ') }}
          </p>

          <!-- 文件类型选择器 -->
          <div class="field">
            <label class="field-label">{{ $t('service.execute.fileType', 'File Type') }}</label>
            <select v-model="slotFileTypes[slot.name]" class="field-select">
              <option v-for="typeId in slot.file_type_ids" :key="typeId" :value="typeId">
                {{ renderFileTypeName(typeId) }}
              </option>
            </select>
          </div>

          <!-- 已有文件选择 -->
          <div class="field">
            <label class="field-label">{{ $t('service.execute.existFile', 'Select Existing File') }}</label>
            <div class="field-row">
              <select v-model="selectedFiles[slot.name]" class="field-select">
                <option value="">{{ $t('service.execute.chooseFile', 'Please select a file') }}</option>
                <option
                  v-for="file in getFilteredFilesForSlot(slot)"
                  :key="file.fileId"
                  :value="file.fileId"
                >
                  {{ file.name || file.fileId }} ({{ renderFileTypeName(file.file_type_id) }})
                </option>
              </select>
              <button 
                class="ghost-btn" 
                type="button" 
                @click="reloadFiles" 
                :disabled="loadingFiles"
                title="Refresh list"
              >
                ↻
              </button>
            </div>
          </div>

          <!-- 上传新文件 -->
          <div class="field">
            <label class="field-label">{{ $t('service.execute.uploadNew', 'Or Upload New File') }}</label>
            <div class="upload-box compact">
              <input 
                type="file" 
                :disabled="uploadingSlots[slot.name]" 
                @change="(e) => handleSlotUpload(e, slot.name)" 
              />
              <span class="upload-text">Select File</span>
            </div>
            <div v-if="uploadMessages[slot.name]" class="info-pill success" v-text="uploadMessages[slot.name]" />
            <div v-if="uploadErrors[slot.name]" class="info-pill error" v-text="uploadErrors[slot.name]" />
          </div>

          <!-- 已选文件信息 -->
          <div v-if="selectedFiles[slot.name]" class="selected-file-info">
            <span class="file-icon">📄</span>
            <div class="file-details">
              <strong>{{ getFileNameById(selectedFiles[slot.name]) }}</strong>
              <small class="muted">ID: {{ selectedFiles[slot.name] }}</small>
            </div>
          </div>
        </div>

        <!-- 全局刷新按钮 -->
        <div class="info-block">
          <button 
            class="refresh-all-btn" 
            @click="reloadFiles" 
            :disabled="loadingFiles"
          >
            {{ loadingFiles ? 'Loading...' : 'Refresh All File Lists' }}
          </button>
        </div>
      </aside>

      <section class="execute-panel">
        <div v-if="serviceError" class="error-message">{{ serviceError }}</div>
        <div v-else-if="serviceLoading" class="loading">{{ $t('common.loading') || 'Loading...' }}</div>
        <div v-else-if="!currentService" class="error-message">
          {{ $t('service.execute.noService') || 'Service not found' }}
        </div>
        <div v-else>
          <ServiceExecute
            :service="currentService"
            :service-id="currentService.service_id"
            :selected-files="selectedFiles"
            :project-id="projectId || undefined"
            :hide-file-input="isMultiFile"
            :hide-header="isMultiFile"
          />
          <div v-if="isMultiFile" class="multi-file-hint">
            {{ $t('service.execute.multiFileHintBottom', 'This service requires multiple input files. Selection and upload options for each slot are provided above.') }}
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ServiceExecute from '../components/service/ServiceExecute.vue'
import { getService, type Service } from '../api/service'
import { getFileList, getFileTypes, uploadFile, type FileInfo } from '../api/file'
import type { FileType } from '../types/file'
import { ElMessage } from 'element-plus'

const props = defineProps<{
  serviceId?: string
  projectId?: string
  initialFileId?: string | string[] | null
  origin?: string
}>()

const route = useRoute()
const router = useRouter()

const currentService = ref<Service | null>(null)
const serviceLoading = ref(false)
const serviceError = ref('')
const loadingFiles = ref(false)
const fileList = ref<FileInfo[]>([])
const fileTypes = ref<FileType[]>([])

// 多文件槽位管理
const selectedFiles = ref<Record<string, string>>({})
const slotFileTypes = ref<Record<string, string>>({})
const uploadingSlots = ref<Record<string, boolean>>({})
const uploadMessages = ref<Record<string, string>>({})
const uploadErrors = ref<Record<string, string>>({})

const acceptedFileSlots = computed(() => {
  if (!currentService.value?.accepted_files) return []
  return Object.entries(currentService.value.accepted_files).map(([name, cfg]) => ({
    name,
    file_type_ids: (cfg as any).file_type_ids || [],
    description: (cfg as any).description || '',
    required: (cfg as any).required !== false // 默认为必需
  }))
})

const isMultiFile = computed(() => acceptedFileSlots.value.length > 1)

const acceptedFileTypeIds = computed(() => {
  const ids = new Set<string>()
  acceptedFileSlots.value.forEach(slot => {
    slot.file_type_ids.forEach((id: string) => ids.add(String(id)))
  })
  return Array.from(ids)
})

// 为每个槽位过滤文件
function getFilteredFilesForSlot(slot: { name: string; file_type_ids: string[] }) {
  if (!slot.file_type_ids.length) {
    console.log(`[Slot ${slot.name}] No file types specified, returning all files`)
    return fileList.value
  }
  
  const filtered = fileList.value.filter(item => {
    const typeId = item.file_type_id || (item.fileType as any)?.id || (item.fileType as any)?.file_type_id
    const matches = typeId ? slot.file_type_ids.includes(String(typeId)) : false
    if (typeId) {
      console.log(`[Slot ${slot.name}] File ${item.name || item.fileId}: typeId=${typeId}, accepted=${slot.file_type_ids.join(',')}, matches=${matches}`)
    }
    return matches
  })
  
  console.log(`[Slot ${slot.name}] Filter results: ${filtered.length}/${fileList.value.length} files`)
  return filtered
}

// 根据文件ID获取文件名
function getFileNameById(fileId: string) {
  const file = fileList.value.find(f => f.fileId === fileId)
  return file?.name || fileId
}

// 计算所有已选文件的信息
const selectedFileInfo = computed(() => {
  const firstSlot = acceptedFileSlots.value[0]
  if (!firstSlot) return null
  const fileId = selectedFiles.value[firstSlot.name]
  if (!fileId) return null
  return fileList.value.find(f => f.fileId === fileId) || null
})

async function loadService() {
  const serviceId = props.serviceId || (route.params.serviceId as string | undefined)
  if (!serviceId) {
    serviceError.value = 'No serviceId specified'
    return
  }
  try {
    serviceLoading.value = true
    serviceError.value = ''
    currentService.value = await getService(serviceId)
  } catch (err: any) {
    console.error('Failed to load service', err)
    serviceError.value = err?.message || 'Failed to load service'
  } finally {
    serviceLoading.value = false
  }
}

async function loadFileTypes() {
  try {
    const list = await getFileTypes()
    fileTypes.value = list
  } catch (err) {
    console.warn('Failed to load file types', err)
  }
}

function renderFileTypeName(id?: string | null) {
  if (!id) return id || '-'
  const hit = fileTypes.value.find(item => item.id === id)
  return hit?.display_name || hit?.name || id
}

async function reloadFiles() {
  try {
    loadingFiles.value = true
    const list = await getFileList(props.projectId ? { projectId: props.projectId } : undefined)
    // 后端可能返回 file_id / id 字段，统一归一化
    fileList.value = (list || []).map((item: any) => {
      const fileId = item.fileId || item.file_id || item.id || ''
      const fileType =
        item.file_type ||
        item.fileType ||
        (typeof item.type === 'object' ? item.type : undefined)
      const fileTypeId =
        item.file_type_id ||
        (fileType && typeof fileType === 'object'
          ? (fileType as any).id || (fileType as any).file_type_id
          : undefined) ||
        item.type_id
      return {
        ...item,
        fileId,
        file_type_id: fileTypeId,
        fileType: fileType
      } as FileInfo
    })
    console.log(
      `[FileList] Loaded ${fileList.value.length} files:`,
      fileList.value.map(f => ({
        id: f.fileId,
        name: f.name,
        type_id: f.file_type_id,
        fileType: f.fileType
      }))
    )
  } catch (err) {
    console.warn('Failed to load file list', err)
  } finally {
    loadingFiles.value = false
  }
}

// 处理槽位文件上传
async function handleSlotUpload(event: Event, slotName: string) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  
  // 限制文件大小为 512MB
  const MAX_SIZE = 512 * 1024 * 1024
  if (file.size > MAX_SIZE) {
    input.value = ''
    ElMessage.error('文件大小不能超过 512MB')
    return
  }
  
  const fileTypeId = slotFileTypes.value[slotName]
  if (!fileTypeId) {
    uploadErrors.value[slotName] = 'Please select a file type first'
    return
  }
  
  try {
    uploadingSlots.value[slotName] = true
    uploadErrors.value[slotName] = ''
    uploadMessages.value[slotName] = ''
    
    const res = await uploadFile({
      file,
      fileTypeId,
      projectId: props.projectId,
      name: file.name
    })
    
    const newId = res.fileId || res.file_id || ''
    selectedFiles.value[slotName] = newId
    uploadMessages.value[slotName] = 'Upload successful'
    
    // 重新加载文件列表
    await reloadFiles()
    
    // 清空 input
    input.value = ''
  } catch (err: any) {
    console.error(`File upload failed [${slotName}]`, err)
    uploadErrors.value[slotName] = err?.message || 'Upload failed'
  } finally {
    uploadingSlots.value[slotName] = false
  }
}

function handleBack() {
  if (props.origin === 'analysis') {
    router.push({ name: 'Analysis', query: route.query })
    return
  }
  if (props.origin === 'service' || props.origin === 'services') {
    router.push({ name: 'Services' })
    return
  }
  router.back()
}

onMounted(async () => {
  console.log('[Mount] Component mounted, loading data')
  console.log('[Mount] projectId:', props.projectId)
  console.log('[Mount] serviceId:', props.serviceId)
  
  await loadService()
  await loadFileTypes()
  await reloadFiles()
  
  console.log('[Mount] Data loaded successfully')
  console.log('[Mount] fileList:', fileList.value.length, 'files')
  console.log('[Mount] fileTypes:', fileTypes.value.length, 'types')
  console.log('[Mount] acceptedFileSlots:', acceptedFileSlots.value)
})

watch(currentService, (newService) => {
  if (!newService) return
  
  console.log('[Service] Service loaded:', newService.service_id)
  console.log('[Service] accepted_files:', newService.accepted_files)
  console.log('[Service] acceptedFileSlots:', acceptedFileSlots.value)
  
  // 为每个槽位初始化默认文件类型（选择第一个接受的类型）
  // 使用新对象确保响应式更新
  const newSlotFileTypes: Record<string, string> = {}
  acceptedFileSlots.value.forEach(slot => {
    if (slot.file_type_ids.length > 0) {
      newSlotFileTypes[slot.name] = slot.file_type_ids[0]
      console.log(`[Slot ${slot.name}] Initialized file type to: ${slot.file_type_ids[0]}`)
    }
  })
  slotFileTypes.value = newSlotFileTypes
  console.log('[Service] slotFileTypes initialized:', slotFileTypes.value)
}, { immediate: true })

// 监听文件列表变化
watch(fileList, (newList) => {
  console.log('[FileList] File list updated:', newList.length, 'files')
  if (newList.length > 0) {
    console.log('[FileList] File details:', newList.map(f => ({
      id: f.fileId,
      name: f.name,
      type_id: f.file_type_id,
      fileType: f.fileType
    })))
  }
})

// 监听槽位文件类型变化
watch(slotFileTypes, (newTypes) => {
  console.log('[SlotFileTypes] Slot file types updated:', newTypes)
}, { deep: true })
</script>

<style scoped>
.service-execute-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px;
  height: 100%;
  box-sizing: border-box;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.title h2 {
  margin: 0;
  font-size: 20px;
}

.subtitle {
  margin: 4px 0 0;
  color: var(--text-secondary);
  font-size: 14px;
}

.back-btn {
  border: 1px solid var(--border-color);
  background: transparent;
  padding: 6px 10px;
  border-radius: 6px;
  cursor: pointer;
}

.badge {
  padding: 6px 10px;
  background: rgba(100, 150, 220, 0.1);
  border-radius: 6px;
  color: #3a6ea5;
  font-size: 12px;
}

.page-body {
  display: grid;
  grid-template-columns: 360px 1fr;
  gap: 16px;
  height: calc(100% - 64px);
}

.info-panel {
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 16px;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.info-block h3 {
  margin: 0 0 8px;
  font-size: 16px;
}

.info-block ul {
  margin: 0;
  padding-left: 18px;
}

.slot-types {
  color: var(--text-secondary);
  margin-left: 6px;
  font-size: 13px;
}

.muted {
  color: var(--text-secondary);
}

.execute-panel {
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 16px;
  overflow: auto;
}

.loading,
.error-message {
  padding: 12px;
  background: var(--bg-tertiary);
  border-radius: 6px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin: 10px 0;
}

.field-label {
  font-weight: 600;
  font-size: 14px;
}

.field-select {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  background: var(--bg-secondary, white);
}

.field-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.ghost-btn {
  border: 1px solid var(--border-color);
  background: transparent;
  border-radius: 6px;
  padding: 8px 12px;
  cursor: pointer;
}

.upload-box {
  border: 1px dashed var(--border-color);
  border-radius: 10px;
  padding: 12px;
  display: flex;
  gap: 12px;
  align-items: center;
}

.upload-hint {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.small {
  font-size: 12px;
}

.info-pill {
  margin-top: 8px;
  padding: 8px 10px;
  border-radius: 6px;
  font-size: 13px;
}

.info-pill.success {
  background: rgba(80, 180, 120, 0.12);
  color: #2c8b5d;
  border: 1px solid rgba(80, 180, 120, 0.3);
}

.info-pill.error {
  background: rgba(230, 110, 110, 0.12);
  color: #b63f3f;
  border: 1px solid rgba(230, 110, 110, 0.3);
}

/* 文件槽位样式 */
.file-slot-section {
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 16px;
  margin: 12px 0;
  background: var(--bg-secondary, #fafafa);
}

.slot-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.slot-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.required-badge {
  background: rgba(230, 110, 110, 0.15);
  color: #b63f3f;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
}

.slot-description {
  margin: 4px 0 8px;
  line-height: 1.4;
}

.slot-types {
  margin: 4px 0 12px;
  padding: 6px 10px;
  background: rgba(100, 150, 220, 0.08);
  border-radius: 6px;
  font-size: 12px;
}

.upload-box.compact {
  padding: 8px;
  position: relative;
}

.upload-box.compact input[type="file"] {
  position: absolute;
  width: 100%;
  height: 100%;
  opacity: 0;
  cursor: pointer;
}

.upload-text {
  font-size: 13px;
  color: var(--text-secondary);
}

.selected-file-info {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px;
  background: rgba(80, 180, 120, 0.08);
  border: 1px solid rgba(80, 180, 120, 0.2);
  border-radius: 6px;
  margin-top: 8px;
}

.file-icon {
  font-size: 20px;
}

.file-details {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
}

.file-details strong {
  font-size: 13px;
  color: var(--text-primary);
}

.file-details small {
  font-size: 11px;
}

.refresh-all-btn {
  width: 100%;
  padding: 10px;
  border: 1px solid var(--border-color);
  background: var(--bg-primary, white);
  border-radius: 6px;
  cursor: pointer;
  font-weight: 500;
  transition: all 0.2s;
}

.refresh-all-btn:hover:not(:disabled) {
  background: var(--bg-secondary, #f5f5f5);
}

.refresh-all-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  border: 1px solid rgba(230, 110, 110, 0.3);
}

.info-block.compact {
  margin-top: 6px;
  padding: 10px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
}

.compact-title {
  margin: 0 0 4px;
}
</style>

