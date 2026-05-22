<template>
  <el-dialog
    :model-value="modelValue"
    :title="$t('app.addData')"
    width="520px"
    :close-on-click-modal="true"
    :close-on-press-escape="true"
    @close="closeDialog"
  >
    <el-form label-position="top" class="upload-form">
      <el-form-item :label="$t('app.selectFile')">
        <input
          type="file"
          ref="fileInput"
          style="display: none"
          @change="handleFileSelect"
        />
        <div class="file-picker">
          <el-button @click="triggerFileUpload">
            {{ selectedFile ? selectedFile.name : $t('app.selectFile') }}
          </el-button>
          <span v-if="fileExtension" class="file-extensions">
            {{ $t('analysis.upload.selectedFileExtension', { ext: fileExtension }) }}
          </span>
        </div>
        <div v-if="selectedFile && !fileExtension" class="form-hint warning">
          {{ $t('analysis.upload.noFileExtension') }}
        </div>
      </el-form-item>

      <el-form-item
        :label="$t('analysis.upload.fileTypeLabel')"
        :error="!form.fileTypeId && (typeTouched || uploadAttempted) ? $t('analysis.upload.fileTypeRequired') : ''"
      >
        <el-select
          v-model="form.fileTypeId"
          filterable
          clearable
          class="file-type-select"
          :placeholder="selectedFile ? $t('analysis.upload.fileTypePlaceholder') : $t('analysis.upload.selectFileFirst')"
          :disabled="fileTypesLoading || !hasFileTypes || !selectedFile || filteredFileTypes.length === 0"
          @change="handleManualTypeSelect"
        >
          <el-option
            v-for="type in filteredFileTypes"
            :key="type.id"
            :label="formatFileTypeLabel(type)"
            :value="type.id"
          />
        </el-select>
        <div v-if="!selectedFile" class="form-hint">
          {{ $t('analysis.upload.selectFileFirstHint') }}
        </div>
        <div v-else-if="!hasFileTypes && !fileTypesLoading" class="empty-hint">
          {{ $t('analysis.upload.fileTypesEmpty') }}
        </div>
        <div v-else-if="selectedFile && filteredFileTypes.length === 0" class="form-hint warning">
          {{ $t('analysis.upload.noMatchingFileType', { ext: fileExtension || '' }) }}
        </div>
        <div v-if="fileTypesError" class="form-hint error">
          {{ fileTypesError }}
        </div>
        <div
          v-if="autoDetectedTypeLabel"
          class="form-hint info"
          :class="{ success: autoDetectionMatchesSelection }"
        >
          {{ $t('analysis.upload.fileTypeAutoDetected', { type: autoDetectedTypeLabel }) }}
          <span v-if="!autoDetectionMatchesSelection">
            {{ $t('analysis.upload.fileTypeAutoDetectedMismatch') }}
          </span>
        </div>
      </el-form-item>

      <el-form-item :label="$t('app.fileName')">
        <el-input
          v-model="form.name"
          :placeholder="$t('app.fileNamePlaceholder')"
        />
        <div class="form-hint">
          {{ $t('app.fileNameHint') }}
        </div>
      </el-form-item>

      <el-form-item :label="$t('app.description')">
        <el-input
          v-model="form.description"
          type="textarea"
          :rows="3"
          :placeholder="$t('app.descriptionPlaceholder')"
        />
      </el-form-item>

      <el-form-item v-if="extensionWarning">
        <el-alert
          :title="extensionWarning"
          type="warning"
          show-icon
          :closable="false"
        />
      </el-form-item>

      <el-form-item v-if="statusMessage">
        <el-alert
          :title="statusMessage"
          :type="statusIsError ? 'error' : 'info'"
          show-icon
          :closable="false"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="closeDialog">
          {{ $t('common.cancel') }}
        </el-button>
        <el-button
          type="primary"
          :disabled="isUploadDisabled"
          @click="handleUpload"
        >
          {{ uploading ? $t('app.uploading') : $t('app.upload') }}
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useFileTypes } from '../../composables/useFileTypes'
import type { FileType } from '../../types/file'

const props = defineProps<{
  modelValue: boolean
  category?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  upload: [
    payload: {
      file: File
      name: string
      description: string
      fileTypeId: string
    }
  ]
}>()

const { t } = useI18n()

const fileInput = ref<HTMLInputElement | null>(null)
const selectedFile = ref<File | null>(null)
const form = ref({
  name: '',
  description: '',
  fileTypeId: ''
})
const statusMessage = ref('')
const statusIsError = ref(false)
const uploading = ref(false)
const typeTouched = ref(false)
const uploadAttempted = ref(false)
const autoDetectedTypeId = ref<string | null>(null)
const manualTypeSelection = ref(false)
const {
  fileTypes,
  loading: fileTypesLoadingRef,
  error: fileTypesErrorRef,
  ensureLoaded,
  setCategory,
  detectTypeByFile,
  fileTypeMap
} = useFileTypes(props.category)

const fileTypesLoading = computed(() => fileTypesLoadingRef.value)
const fileTypesError = computed(() => fileTypesErrorRef.value)
const hasFileTypes = computed(() => fileTypes.value.length > 0)

function formatExtensions(list?: string[]) {
  if (!list || !list.length) return ''
  return list
    .map(ext => normalizeExtension(ext) || '')
    .filter(Boolean)
    .join(', ')
}

function formatFileTypeLabel(type: FileType) {
  if (!type.extensions?.length) return type.display_name
  return `${type.display_name} (${formatExtensions(type.extensions)})`
}

const autoDetectedTypeLabel = computed(() => {
  if (!autoDetectedTypeId.value) return ''
  return fileTypeMap.value[autoDetectedTypeId.value]?.display_name || ''
})

const selectedFileType = computed<FileType | null>(() => {
  if (!form.value.fileTypeId) return null
  return fileTypeMap.value[form.value.fileTypeId] || null
})

const autoDetectionMatchesSelection = computed(() => {
  if (!autoDetectedTypeId.value) return false
  return autoDetectedTypeId.value === form.value.fileTypeId
})

const fileExtension = computed(() => {
  if (!selectedFile.value?.name) return null
  const filename = selectedFile.value.name.toLowerCase()
  const dotIndex = filename.lastIndexOf('.')
  if (dotIndex === -1) return null
  return filename.slice(dotIndex)
})

// 根据选择的文件扩展名过滤文件类型
const filteredFileTypes = computed(() => {
  if (!selectedFile.value || !fileExtension.value) {
    return []
  }
  
  const normalizedExt = fileExtension.value
  return fileTypes.value.filter(type => {
    if (!type.extensions || type.extensions.length === 0) {
      return false // 没有扩展名的类型不显示
    }
    return type.extensions.some(ext => {
      const normalized = normalizeExtension(ext)
      return normalized === normalizedExt
    })
  })
})

const extensionWarning = computed(() => {
  if (!selectedFile.value || !selectedFileType.value) return ''
  const extensions = selectedFileType.value.extensions || []
  if (!extensions.length || !fileExtension.value) return ''
  const normalized = extensions.map(ext => normalizeExtension(ext))
  if (normalized.includes(fileExtension.value)) return ''
  return t('analysis.upload.fileTypeMismatch', {
    type: selectedFileType.value.display_name,
    ext: fileExtension.value
  })
})

const isUploadDisabled = computed(() => {
  if (uploading.value) return true
  if (!selectedFile.value) return true
  return !form.value.fileTypeId
})

watch(
  () => props.category,
  category => {
    setCategory(category)
  }
)

watch(
  () => props.modelValue,
  async isOpen => {
    if (isOpen) {
      try {
        await ensureLoaded()
      } catch (error) {
        console.warn('加载文件类型失败', error)
      }
    } else {
      resetState()
    }
  }
)

function normalizeExtension(ext?: string | null) {
  if (!ext) return ''
  const trimmed = ext.trim().toLowerCase()
  if (!trimmed) return ''
  return trimmed.startsWith('.') ? trimmed : `.${trimmed}`
}

function closeDialog() {
  emit('update:modelValue', false)
}

function triggerFileUpload() {
  fileInput.value?.click()
}

async function handleFileSelect(event: Event) {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return

  // 限制文件大小为 512MB
  const MAX_SIZE = 512 * 1024 * 1024
  if (file.size > MAX_SIZE) {
    target.value = ''
    ElMessage.error(t('analysis.upload.fileTooLarge', '文件大小不能超过 512MB'))
    return
  }

  selectedFile.value = file
  typeTouched.value = false
  uploadAttempted.value = false
  manualTypeSelection.value = false

  if (!form.value.name) {
    form.value.name = file.name
  }

  try {
    await ensureLoaded()
  } catch {}

  // 文件改变时，清除之前选择的文件类型（因为可能不匹配新文件）
  form.value.fileTypeId = ''
  autoDetectedTypeId.value = null

  // 检测文件类型，如果找到匹配的类型则自动选择
  const detected = detectTypeByFile(file)
  autoDetectedTypeId.value = detected?.id || null
  if (detected && filteredFileTypes.value.some(type => type.id === detected.id)) {
    form.value.fileTypeId = detected.id
  }
}

function handleManualTypeSelect() {
  manualTypeSelection.value = true
  typeTouched.value = true
}

function handleUpload() {
  uploadAttempted.value = true
  typeTouched.value = true

  if (!selectedFile.value || !form.value.fileTypeId) return

  emit('upload', {
    file: selectedFile.value,
    name: form.value.name.trim(),
    description: form.value.description.trim(),
    fileTypeId: form.value.fileTypeId
  })
}

function resetState() {
  selectedFile.value = null
  form.value = { name: '', description: '', fileTypeId: '' }
  statusMessage.value = ''
  statusIsError.value = false
  uploading.value = false
  typeTouched.value = false
  uploadAttempted.value = false
  autoDetectedTypeId.value = null
  manualTypeSelection.value = false
  if (fileInput.value) {
    fileInput.value.value = ''
  }
}

defineExpose({
  setStatus: (message: string, isError = false) => {
    statusMessage.value = message
    statusIsError.value = isError
  },
  setUploading: (value: boolean) => {
    uploading.value = value
  },
  close: () => {
    closeDialog()
  }
})
import { ElAlert, ElButton, ElDialog, ElForm, ElFormItem, ElInput, ElSelect, ElOption, ElMessage } from 'element-plus'
</script>

<style scoped>
.upload-form {
  padding-top: 8px;
}

.file-type-select select {
  width: 100%;
}

.file-picker {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.file-extensions {
  font-size: 12px;
  color: rgba(0, 0, 0, 0.45);
}

.upload-status {
  padding: var(--spacing-sm) var(--spacing-md);
  border-radius: var(--radius-md);
  background: rgba(33, 150, 243, 0.06);
  color: #1565c0;
  border: 1px solid rgba(33, 150, 243, 0.25);
}

.upload-status.error {
  background: rgba(244, 67, 54, 0.06);
  color: #c62828;
  border-color: rgba(244, 67, 54, 0.25);
}

.extension-warning {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  padding: var(--spacing-sm) var(--spacing-md);
  border-radius: var(--radius-md);
  background: rgba(255, 152, 0, 0.08);
  color: #e65100;
  font-size: 13px;
  border: 1px solid rgba(255, 152, 0, 0.35);
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--spacing-sm);
}

.form-hint {
  font-size: 12px;
  color: rgba(0, 0, 0, 0.45);
}

.form-hint.error,
.form-hint.info,
.form-hint.success,
.form-hint.warning {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.form-hint.error {
  color: #d32f2f;
}

.form-hint.info {
  color: #1565c0;
}

.form-hint.success {
  color: #2e7d32;
}

.form-hint.warning {
  color: #e65100;
}

.empty-hint {
  font-size: 13px;
  color: rgba(0, 0, 0, 0.45);
}

.link-button {
  background: none;
  border: none;
  padding: 0;
  margin-left: var(--spacing-xs);
  color: #1565c0;
  cursor: pointer;
  font-size: 12px;
  text-decoration: underline;
}

.option-ext {
  font-size: 12px;
  color: rgba(0, 0, 0, 0.45);
}
</style>
