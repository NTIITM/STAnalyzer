<template>
  <div class="service-execute">
    <div v-if="!props.hideHeader" class="execute-header">
      <h3>{{ $t('service.execute.title') }}</h3>
      <span class="service-name">
        <template v-if="currentService">{{ currentService.name }}</template>
        <template v-else-if="serviceLoading">{{ $t('common.loading') || 'Loading service...' }}</template>
        <template v-else>{{ serviceError || '-' }}</template>
      </span>
    </div>

    <div v-if="serviceLoading" class="info-message">
      <span>{{ $t('common.loading') || 'Loading service...' }}</span>
    </div>
    <div v-else-if="serviceError" class="form-error">
      {{ serviceError }}
    </div>
    <div v-else-if="!currentService" class="info-message">
      <span>{{ $t('service.execute.noService') || 'Service not found' }}</span>
    </div>

    <div v-else class="form-section">
      <div v-if="!props.hideFileInput" class="form-group">
        <label>{{ $t('service.execute.inputFileId') }} <span class="required">{{ $t('common.required') }}</span></label>
        <!-- 当前显示单个输入框（向后兼容），未来可扩展为支持多个文件ID -->
        <input 
          v-model="inputFileIds[0]"
          type="text"
          class="form-input"
          :class="{ 'input-error': fileValidationError }"
          :placeholder="$t('service.execute.inputFileId')"
          required
          @blur="validateFileType"
        />
        <small class="form-hint">{{ $t('service.execute.inputFileIdHint') }}</small>
        <!-- 文件类型验证提示 -->
        <div v-if="fileValidationError" class="file-validation-error">
          <span class="error-icon">⚠</span>
          <span>{{ fileValidationError }}</span>
        </div>
        <div v-else-if="fileValidationSuccess" class="file-validation-success">
          <span class="success-icon">✓</span>
          <span>{{ fileValidationSuccess }}</span>
        </div>
        <!-- 未来扩展：可以在这里添加"添加更多文件"按钮，显示多个输入框 -->
      </div>

      <div v-if="hasParameters" class="form-section">
        <h4>{{ $t('service.execute.parameters') }}</h4>
        <div v-for="(paramDef, paramName) in parameterSchema" :key="paramName" class="form-group">
          <label>
            {{ paramName }}
            <span v-if="!isOptional(paramDef)" class="required">*</span>
            <span v-if="paramDef.description" class="param-description">（{{ paramDef.description }}）</span>
          </label>
          
          <!-- 枚举类型（优先检查，支持 type='enum' 和 enum_values 字段） -->
          <select 
            v-if="paramDef.type === 'enum' && (paramDef.enum_values || paramDef.enum)"
            v-model="formData.parameters![paramName]"
            class="form-input"
          >
            <option 
              v-for="enumValue in (paramDef.enum_values || paramDef.enum || [])" 
              :key="enumValue" 
              :value="enumValue"
            >
              {{ enumValue }}
            </option>
          </select>
          
          <!-- 字符串类型 -->
          <input 
            v-else-if="paramDef.type === 'string' && !paramDef.enum && !paramDef.enum_values"
            v-model="formData.parameters![paramName]"
            type="text"
            class="form-input"
            :placeholder="`${$t('service.execute.defaultValue')}: ${getDefaultValue(paramDef)}`"
          />
          
          <!-- 字符串枚举类型（向后兼容：type='string' 且包含 enum 字段） -->
          <select 
            v-else-if="paramDef.type === 'string' && (paramDef.enum || paramDef.enum_values)"
            v-model="formData.parameters![paramName]"
            class="form-input"
          >
            <option 
              v-for="enumValue in (paramDef.enum_values || paramDef.enum || [])" 
              :key="enumValue" 
              :value="enumValue"
            >
              {{ enumValue }}
            </option>
          </select>
          
          <!-- 数字类型（支持 continuous 和 discrete 类型，以及 min_value/max_value 字段） -->
          <input 
            v-else-if="paramDef.type === 'number' || paramDef.type === 'integer' || paramDef.type === 'continuous' || paramDef.type === 'discrete'"
            v-model.number="formData.parameters![paramName]"
            type="number"
            class="form-input"
            :min="paramDef.min ?? paramDef.min_value"
            :max="paramDef.max ?? paramDef.max_value"
            :step="paramDef.type === 'integer' || paramDef.type === 'discrete' ? 1 : 0.1"
            :placeholder="`${$t('service.execute.defaultValue')}: ${getDefaultValue(paramDef)}`"
          />
          
          <!-- 布尔类型 -->
          <select 
            v-else-if="paramDef.type === 'boolean'"
            v-model="formData.parameters![paramName]"
            class="form-input"
          >
            <option :value="undefined">{{ $t('service.execute.useDefault') }}（{{ paramDef.default ?? paramDef.default_value ?? false }}）</option>
            <option :value="true">{{ $t('service.execute.yes') }}</option>
            <option :value="false">{{ $t('service.execute.no') }}</option>
          </select>
          
          <!-- 数组类型 -->
          <textarea 
            v-else-if="paramDef.type === 'array'"
            v-model="arrayParams[String(paramName)]"
            class="form-textarea"
            rows="3"
            :placeholder="$t('service.execute.onePerLine')"
            @blur="updateArrayParam(String(paramName))"
          />
          
          <!-- 对象类型 -->
          <textarea 
            v-else-if="paramDef.type === 'object'"
            v-model="objectParams[String(paramName)]"
            class="form-textarea"
            rows="5"
            placeholder='{"key": "value"}'
            @blur="updateObjectParam(String(paramName))"
          />
          
          <!-- 默认文本输入 -->
          <input 
            v-else
            v-model="formData.parameters![paramName]"
            type="text"
            class="form-input"
            :placeholder="`${$t('service.execute.defaultValue')}: ${getDefaultValue(paramDef)}`"
          />
          
          <!-- 枚举类型：显示可选值 -->
          <small v-if="paramDef.type === 'enum' || (paramDef.type === 'string' && (paramDef.enum || paramDef.enum_values))" class="form-hint">
            {{ $t('service.execute.availableValues') }}: {{ (paramDef.enum_values || paramDef.enum || []).join(', ') }}
          </small>
          
          <!-- 布尔类型：显示可选值 -->
          <small v-else-if="paramDef.type === 'boolean'" class="form-hint">
            {{ $t('service.execute.availableValues') }}: true, false
          </small>
          
          <!-- 数字类型：显示范围（仅当有 min/max 限制时） -->
          <small v-else-if="(paramDef.type === 'number' || paramDef.type === 'integer' || paramDef.type === 'continuous' || paramDef.type === 'discrete') && (paramDef.min !== undefined || paramDef.max !== undefined || paramDef.min_value !== undefined || paramDef.max_value !== undefined)" class="form-hint">
            {{ $t('service.execute.range') }}: {{ paramDef.min ?? paramDef.min_value ?? $t('service.execute.unlimited') }} ~ {{ paramDef.max ?? paramDef.max_value ?? $t('service.execute.unlimited') }}
          </small>
        </div>
      </div>

      <div v-else class="info-message">
        <span>{{ $t('service.execute.noParameters') }}</span>
      </div>

      <div v-if="!props.hideExecuteActions && executeError" class="form-error">
        {{ executeError }}
      </div>

      <div v-if="!props.hideExecuteActions && executing" class="executing-state">
        <div class="spinner"></div>
        <span>{{ $t('service.execute.executing') }}</span>
      </div>

      <div v-if="!props.hideExecuteActions && executionResult" class="execution-result">
        <h4>{{ $t('service.execute.result') }}</h4>
        <div class="result-item">
          <span class="result-label">{{ $t('service.execute.executionId') }}:</span>
          <span class="result-value">{{ executionResult.execution_id }}</span>
        </div>
        <div v-if="executionResult.output_file_ids && executionResult.output_file_ids.length > 0" class="result-item">
          <span class="result-label">{{ $t('service.execute.outputFileId') }}:</span>
          <span class="result-value">{{ executionResult.output_file_ids.join(', ') }}</span>
        </div>
        <div class="result-item">
          <span class="result-label">{{ $t('service.execute.status') }}:</span>
          <span class="result-value status-badge" :class="`status-${executionResult.status}`">
            {{ getStatusLabel(executionResult.status) }}
          </span>
        </div>
        <!-- 轮询中显示倒计时和手动刷新 -->
        <div v-if="isPollingActive" class="poll-status">
          <span class="elapsed-time">⏱ {{ formatElapsedTime(elapsedSeconds) }}</span>
          <span class="countdown-hint">{{ nextPollCountdown > 0 ? `${nextPollCountdown}s` : '...' }}</span>
          <el-button size="small" @click="manualRefreshExecution" :loading="manualRefreshing">
            ↻ {{ $t('common.refresh') || '刷新' }}
          </el-button>
        </div>
        <div v-if="executionResult.error_message" class="result-error">
          <span class="error-label">{{ $t('service.execute.error') }}:</span>
          <span class="error-message">{{ executionResult.error_message }}</span>
        </div>
      </div>

      <div v-if="!props.hideExecuteActions" class="execute-actions">
        <el-button
          type="primary"
          @click="handleExecute"
          :disabled="executing || !isFormValid || !!executionResult"
          :loading="executing"
        >
          {{ executing ? $t('service.execute.executing') : $t('service.execute.execute') }}
        </el-button>
        <el-button
          v-if="executionResult"
          @click="resetForm"
        >
          {{ $t('service.execute.reExecute') }}
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, withDefaults } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElButton } from 'element-plus'
import { executeService, getExecution, getService, type Service, type ServiceExecuteRequest, type ServiceExecution, type ParameterSchema } from '../../api/service'
import { getFileList, type FileInfo } from '../../api/file'

const { t } = useI18n()

const props = withDefaults(defineProps<{
  /** 可以直接传入 Service 对象，或仅提供 serviceId 由组件自行加载 */
  service?: Service | null
  serviceId?: string
  initialFileId?: string | string[] | null
  projectId?: string | null
  /** 可选的文件信息，如果提供则优先使用，避免调用 getFileList API */
  fileInfo?: FileInfo | any | null
  /** 多文件模式下从父组件传入的已选文件（槽位名 -> fileId） */
  selectedFiles?: Record<string, string> | null
  /** 隐藏头部（用于多文件模式展示参数） */
  hideHeader?: boolean
  /** 隐藏文件输入（用于多文件模式展示参数） */
  hideFileInput?: boolean
  /** 隐藏执行按钮与结果（用于多文件模式展示参数） */
  hideExecuteActions?: boolean
}>(), {
  hideHeader: false,
  hideFileInput: false,
  hideExecuteActions: false
})

const emit = defineEmits<{
  executed: [result: ServiceExecution]
}>()

const currentService = ref<Service | null>(props.service || null)
const serviceLoading = ref(false)
const serviceError = ref('')

// 内部使用数组存储文件ID，便于扩展支持多个文件
const inputFileIds = ref<string[]>([''])

const formData = ref<ServiceExecuteRequest>({
  input_file_ids: [],
  parameters: {}
})

const arrayParams = ref<Record<string, string>>({})
const objectParams = ref<Record<string, string>>({})
const executing = ref(false)
const executeError = ref('')
const executionResult = ref<ServiceExecution | null>(null)
const fileValidationError = ref('')
const fileValidationSuccess = ref('')
const validatingFile = ref(false)

const parameterSchema = computed(() => {
  return (currentService.value?.parameter_schema || {}) as ParameterSchema
})

const hasParameters = computed(() => {
  return Object.keys(parameterSchema.value).length > 0
})

async function loadServiceIfNeeded() {
  if (currentService.value || !props.serviceId) return
  try {
    serviceLoading.value = true
    serviceError.value = ''
    const service = await getService(props.serviceId)
    currentService.value = service
  } catch (err: any) {
    console.error('加载 Service 失败:', err)
    serviceError.value = err?.message || err?.data?.message || t('service.loadFailed')
  } finally {
    serviceLoading.value = false
  }
}

watch(() => props.service, (service) => {
  if (service) {
    currentService.value = service
  }
})

watch(() => props.serviceId, () => {
  loadServiceIfNeeded()
}, { immediate: true })

// 监听 selectedFiles（多文件模式）变化，更新 inputFileIds
watch(() => props.selectedFiles, (files) => {
  if (files && props.hideFileInput) {
    const ids = Object.values(files).filter(id => id && id.trim().length > 0)
    inputFileIds.value = ids.length > 0 ? ids : ['']
  }
}, { immediate: true, deep: true })

onMounted(() => {
  loadServiceIfNeeded()
})

const isFormValid = computed(() => {
  // 多文件模式：如果隐藏文件输入，使用 selectedFiles 校验
  if (props.hideFileInput && props.selectedFiles) {
    return Object.values(props.selectedFiles).some(id => id && id.trim().length > 0)
  }
  // 默认：验证至少有一个非空的文件ID
  return inputFileIds.value.some(id => id.trim().length > 0)
})

// 初始化参数值（使用默认值）
watch(currentService, (service) => {
  if (!service) {
    formData.value.parameters = {}
    arrayParams.value = {}
    objectParams.value = {}
    return
  }
  if (service.parameter_template) {
    formData.value.parameters = { ...service.parameter_template }
  } else {
    formData.value.parameters = {}
  }
  
  // 初始化数组和对象的文本表示
  if (service.parameter_schema && formData.value.parameters) {
    Object.entries(service.parameter_schema).forEach(([paramName, paramDef]) => {
      if (paramDef.type === 'array') {
        const defaultValue = formData.value.parameters![paramName] || paramDef.default
        arrayParams.value[paramName] = Array.isArray(defaultValue) 
          ? defaultValue.join('\n') 
          : ''
      } else if (paramDef.type === 'object') {
        const defaultValue = formData.value.parameters![paramName] || paramDef.default
        objectParams.value[paramName] = defaultValue 
          ? JSON.stringify(defaultValue, null, 2)
          : ''
      }
    })
  }
}, { immediate: true })

// 监听 initialFileId 变化，更新 inputFileIds
watch(() => props.initialFileId, (fileId) => {
  if (fileId) {
    // 如果是数组，取第一个；如果是字符串，直接使用
    const id = Array.isArray(fileId) ? fileId[0] : fileId
    if (id && id.trim()) {
      inputFileIds.value[0] = id
    }
  } else {
    // 如果 fileId 为空，清空输入
    inputFileIds.value[0] = ''
  }
}, { immediate: true })


// 监听inputFileIds变化，同步到formData
watch(inputFileIds, (ids) => {
  const validIds = ids.filter(id => id.trim().length > 0)
  // input_file_ids 始终是数组
    formData.value.input_file_ids = validIds
}, { deep: true })

function normalizeFileInfo(source: any, expectedId: string): FileInfo | null {
  if (!source) return null
  const fileId = source.fileId || source.file_id || source.id || expectedId
  if (fileId !== expectedId) return null
  const fileType = source.file_type || source.fileType
  const fileTypeId =
    source.file_type_id ||
    (fileType && typeof fileType === 'object'
      ? (fileType as any).id || (fileType as any).file_type_id || (fileType as any).fileTypeId
      : undefined)
  return {
    fileId,
    name: source.name || source.filename || source.file_name || expectedId,
    size: source.size || 0,
    status: source.status || 'unknown',
    time: source.time || '',
    description: source.description,
    file_type: fileType,
    fileType,
    file_type_id: fileTypeId
  }
}

/**
 * 获取参数的默认值
 */
function getDefaultValue(paramDef: any): string {
  const defaultValue = paramDef.default ?? paramDef.default_value
  return defaultValue !== undefined && defaultValue !== null ? String(defaultValue) : ''
}

/**
 * 检查参数是否可选
 */
function isOptional(paramDef: any): boolean {
  return paramDef.default !== undefined || paramDef.default_value !== undefined
}

/**
 * 更新数组参数
 */
function updateArrayParam(paramName: string) {
  const text = arrayParams.value[paramName]
  if (text && text.trim() && formData.value.parameters) {
    formData.value.parameters[paramName] = text
      .split('\n')
      .map(line => line.trim())
      .filter(line => line.length > 0)
  }
}

/**
 * 更新对象参数
 */
function updateObjectParam(paramName: string) {
  const text = objectParams.value[paramName]
  if (text && text.trim() && formData.value.parameters) {
    try {
      formData.value.parameters[paramName] = JSON.parse(text)
    } catch (err) {
      executeError.value = t('service.execute.jsonInvalid', { param: String(paramName) })
      setTimeout(() => {
        executeError.value = ''
      }, 3000)
    }
  }
}

/**
 * 验证文件类型
 */
async function validateFileType() {
  const fileId = inputFileIds.value[0]?.trim()
  if (!fileId) {
    fileValidationError.value = ''
    fileValidationSuccess.value = ''
    return
  }

  if (!currentService.value) {
    fileValidationError.value = t('service.execute.noService') || 'Service not loaded'
    fileValidationSuccess.value = ''
    return
  }

  // 如果服务没有配置 accepted_files，跳过验证
  if (!currentService.value.accepted_files || Object.keys(currentService.value.accepted_files).length === 0) {
    fileValidationError.value = ''
    fileValidationSuccess.value = ''
    return
  }

  try {
    validatingFile.value = true
    fileValidationError.value = ''
    fileValidationSuccess.value = ''

    // 优先使用传入的 fileInfo，如果没有则调用 API 获取并在前端过滤
    let file: FileInfo | null = null

    if (props.fileInfo) {
      file = normalizeFileInfo(props.fileInfo, fileId)
    }

    if (!file) {
      const list = await getFileList(
        props.projectId ? { projectId: props.projectId } : undefined
      )
      const matched = list.find(item => {
        const candidateId = (item as any).fileId || (item as any).file_id || (item as any).id
        return candidateId === fileId
      })
      file = normalizeFileInfo(matched, fileId)
    }

    if (!file) {
      fileValidationError.value = t('service.execute.fileNotFound', { fileId })
      return
    }

    // 检查文件是否有 file_type_id
    if (!file.file_type_id) {
      fileValidationError.value = t('service.execute.fileTypeIdMissing')
      return
    }

    // 验证文件类型是否符合服务的 accepted_files 要求
    // 由于服务可能接受多个文件名，我们需要检查所有配置
    const acceptedConfigs = Object.values(currentService.value.accepted_files)
    const isAccepted = acceptedConfigs.some(config => 
      file!.file_type_id && config.file_type_ids.includes(file!.file_type_id)
    )

    if (!isAccepted) {
      const acceptedTypes = acceptedConfigs
        .flatMap(config => config.file_type_ids)
        .filter((id, index, arr) => arr.indexOf(id) === index) // 去重
        .join(', ')
      fileValidationError.value = t('service.execute.fileTypeNotAccepted', {
        fileTypeId: file.file_type_id || 'unknown',
        acceptedTypes
      })
      return
    }

    // 验证通过
    fileValidationSuccess.value = t('service.execute.fileTypeValid', {
      fileTypeId: file.file_type_id || 'unknown'
    })
  } catch (err: any) {
    console.error('验证文件类型失败:', err)
    fileValidationError.value = t('service.execute.fileValidationFailed', {
      error: err.message || String(err)
    })
  } finally {
    validatingFile.value = false
  }
}

/**
 * 处理执行
 */
async function handleExecute() {
  if (!isFormValid.value) {
    executeError.value = t('service.execute.fillInputFileId')
    return
  }

  if (!currentService.value) {
    executeError.value = t('service.execute.noService') || 'Service not loaded'
    return
  }

  // 多文件模式：优先使用 selectedFiles；否则使用输入框
  const validFileIds = props.hideFileInput && props.selectedFiles
    ? Object.values(props.selectedFiles).filter(id => id && id.trim().length > 0)
    : inputFileIds.value.filter(id => id.trim().length > 0)
  if (validFileIds.length === 0) {
    executeError.value = t('service.execute.fillInputFileId')
    return
  }

  // 如果服务配置了 accepted_files，先验证文件类型
  if (currentService.value.accepted_files && Object.keys(currentService.value.accepted_files).length > 0) {
    if (fileValidationError.value) {
      executeError.value = fileValidationError.value
      return
    }
    // 如果还没有验证，先验证
    if (!fileValidationSuccess.value && !validatingFile.value) {
      await validateFileType()
      if (fileValidationError.value) {
        executeError.value = fileValidationError.value
        return
      }
    }
  }

  try {
    executing.value = true
    executeError.value = ''
    executionResult.value = null

    // 清理未设置的参数
    const cleanParams: Record<string, any> = {}
    if (formData.value.parameters) {
    Object.entries(formData.value.parameters).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        cleanParams[key] = value
      }
    })
    }

    const executeRequest: ServiceExecuteRequest = {
      input_file_ids: validFileIds,
      parameters: cleanParams
    }
    
    // 如果提供了projectId，添加到请求中
    if (props.projectId) {
      executeRequest.project_id = props.projectId
    }
    
    const result = await executeService(currentService.value.service_id, executeRequest)

    executionResult.value = result

    // 如果状态是pending或running，开始轮询
    if (result.status === 'pending' || result.status === 'running') {
      pollExecutionStatus(result.execution_id)
    } else {
      emit('executed', result)
    }
  } catch (err: any) {
    console.error('执行Service失败:', err)
    // 优先显示详细的错误消息（包括后端返回的 detail 字段）
    const errorMsg = err.message || err.data?.detail || err.data?.message || t('service.execute.executeFailed')
    executeError.value = errorMsg
    // 同时显示全局错误提示
    if (window.showMessage) {
      window.showMessage.error(errorMsg)
    }
  } finally {
    executing.value = false
  }
}

/**
 * 轮询执行状态（指数退避策略）
 */
let pollTimer: number | null = null
let pollInterval = 30000
const POLL_MAX_INTERVAL = 120000

// 轮询状态可视化
const isPollingActive = ref(false)
const nextPollCountdown = ref(0)
const elapsedSeconds = ref(0)
const manualRefreshing = ref(false)
let countdownTimer: number | null = null
let elapsedTimer: number | null = null
let currentPollingExecutionId: string | null = null

function clearPollTimer() {
  if (pollTimer) {
    clearTimeout(pollTimer)
    pollTimer = null
  }
  clearCountdownTimer()
  clearElapsedTimer()
  isPollingActive.value = false
}

function clearCountdownTimer() {
  if (countdownTimer) {
    clearInterval(countdownTimer)
    countdownTimer = null
  }
  nextPollCountdown.value = 0
}

function clearElapsedTimer() {
  if (elapsedTimer) {
    clearInterval(elapsedTimer)
    elapsedTimer = null
  }
  elapsedSeconds.value = 0
}

function startCountdown(seconds: number) {
  clearCountdownTimer()
  nextPollCountdown.value = Math.ceil(seconds)
  countdownTimer = window.setInterval(() => {
    nextPollCountdown.value = Math.max(0, nextPollCountdown.value - 1)
  }, 1000)
}

function startElapsedTimer() {
  clearElapsedTimer()
  elapsedSeconds.value = 0
  elapsedTimer = window.setInterval(() => {
    elapsedSeconds.value++
  }, 1000)
}

function formatElapsedTime(seconds: number): string {
  if (seconds < 60) return `${seconds}s`
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins}m ${secs}s`
}

async function manualRefreshExecution() {
  if (!currentPollingExecutionId || manualRefreshing.value) return
  manualRefreshing.value = true
  try {
    const execution = await getExecution(currentPollingExecutionId)
    executionResult.value = execution
    if (execution.status === 'completed' || execution.status === 'failed') {
      clearPollTimer()
      emit('executed', execution)
    }
  } catch (err) {
    console.error('手动刷新失败:', err)
  } finally {
    manualRefreshing.value = false
  }
}

async function pollExecutionStatus(executionId: string) {
  // 停止之前的轮询
  clearPollTimer()
  pollInterval = 30000 // 重置退避间隔
  currentPollingExecutionId = executionId
  isPollingActive.value = true
  startElapsedTimer()

  async function doPoll() {
    try {
      const execution = await getExecution(executionId)
      executionResult.value = execution

      // 如果已完成或失败，停止轮询
      if (execution.status === 'completed' || execution.status === 'failed') {
        clearPollTimer()
        emit('executed', execution)
        return
      }
    } catch (err) {
      console.error('获取执行状态失败:', err)
    }
    // 指数退避：30s → 60s → 120s(上限)
    pollInterval = Math.min(pollInterval * 2, POLL_MAX_INTERVAL)
    startCountdown(pollInterval / 1000)
    pollTimer = window.setTimeout(doPoll, pollInterval)
  }

  // 首次以初始间隔启动
  startCountdown(pollInterval / 1000)
  pollTimer = window.setTimeout(doPoll, pollInterval)
}

// 组件卸载时清理轮询定时器
onUnmounted(() => {
  clearPollTimer()
})

/**
 * 重置表单
 */
function resetForm() {
  executionResult.value = null
  executeError.value = ''
  fileValidationError.value = ''
  fileValidationSuccess.value = ''
  inputFileIds.value = ['']
  formData.value.input_file_ids = []
  formData.value.parameters = { ...currentService.value?.parameter_template || {} }
  
  // 重置数组和对象参数
  Object.keys(arrayParams.value).forEach(key => {
    arrayParams.value[key] = ''
  })
  Object.keys(objectParams.value).forEach(key => {
    objectParams.value[key] = ''
  })
}

/**
 * 获取状态标签
 */
function getStatusLabel(status: string): string {
  switch (status) {
    case 'pending': return t('service.execution.status.pending')
    case 'running': return t('service.execution.status.running')
    case 'completed': return t('service.execution.status.completed')
    case 'failed': return t('service.execution.status.failed')
    case 'cancelled': return t('service.execution.status.cancelled')
    default: return status
  }
}
</script>

<style scoped>
.service-execute {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.execute-header {
  margin-bottom: 1.5rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid var(--border-color);
}

.execute-header h3 {
  margin: 0 0 0.5rem 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
}

.service-name {
  font-size: 0.9rem;
  color: var(--text-secondary);
}

.form-section {
  flex: 1;
  overflow-y: auto;
}

.form-section h4 {
  margin: 1.5rem 0 1rem 0;
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--text-primary);
}

.param-description {
  font-weight: normal;
  color: var(--text-secondary);
  font-size: 0.85rem;
}

.info-message {
  padding: 1rem;
  background: var(--bg-tertiary);
  border-radius: 6px;
  color: var(--text-secondary);
  font-size: 0.9rem;
  margin-bottom: 1rem;
}

.executing-state {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1rem;
  background: rgba(100, 150, 220, 0.1);
  border-radius: 6px;
  margin-bottom: 1rem;
}

.spinner {
  width: 20px;
  height: 20px;
  border: 2px solid var(--border-color);
  border-top-color: var(--accent-primary);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.execution-result {
  padding: 1rem;
  background: var(--bg-tertiary);
  border-radius: 6px;
  margin-bottom: 1rem;
}

.execution-result h4 {
  margin: 0 0 0.75rem 0;
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--text-primary);
}

.result-item {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
  font-size: 0.9rem;
}

.result-label {
  color: var(--text-secondary);
  font-weight: 500;
  min-width: 100px;
}

.result-value {
  color: var(--text-primary);
  flex: 1;
  word-break: break-all;
  font-family: monospace;
}

.status-badge {
  display: inline-block;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.85rem;
  font-weight: 500;
}

.status-pending {
  background: rgba(200, 200, 200, 0.2);
  color: rgba(120, 120, 120, 0.9);
}

.status-running {
  background: rgba(100, 150, 220, 0.2);
  color: rgba(60, 100, 160, 0.9);
}

.status-completed {
  background: rgba(100, 200, 100, 0.2);
  color: rgba(50, 150, 50, 0.9);
}

.status-failed {
  background: rgba(220, 100, 100, 0.2);
  color: rgba(180, 50, 50, 0.9);
}

.poll-status {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-top: 0.75rem;
  padding: 0.5rem 0.75rem;
  background: rgba(100, 150, 220, 0.08);
  border: 1px solid rgba(100, 150, 220, 0.2);
  border-radius: 6px;
  font-size: 0.85rem;
}

.elapsed-time {
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
}

.countdown-hint {
  color: rgba(100, 150, 220, 0.9);
  font-weight: 500;
  font-variant-numeric: tabular-nums;
  min-width: 40px;
  text-align: center;
}

.result-error {
  margin-top: 0.75rem;
  padding: 0.75rem;
  background: rgba(220, 100, 100, 0.1);
  border-radius: 4px;
}

.error-label {
  display: block;
  color: rgba(180, 50, 50, 0.9);
  font-weight: 500;
  margin-bottom: 0.25rem;
  font-size: 0.85rem;
}

.error-message {
  color: rgba(180, 50, 50, 0.9);
  word-break: break-word;
  font-size: 0.85rem;
}

.execute-actions {
  padding-top: 1rem;
  border-top: 1px solid var(--border-color);
  display: flex;
  gap: 0.75rem;
}

/* 文件类型验证样式 */
.input-error {
  border-color: var(--color-error, #f56565) !important;
}

.file-validation-error {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-top: 0.5rem;
  padding: 0.5rem;
  background: rgba(245, 101, 101, 0.1);
  border-radius: 4px;
  color: var(--color-error, #f56565);
  font-size: 0.875rem;
}

.file-validation-success {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-top: 0.5rem;
  padding: 0.5rem;
  background: rgba(100, 200, 100, 0.1);
  border-radius: 4px;
  color: var(--color-success, #48bb78);
  font-size: 0.875rem;
}

.error-icon {
  font-size: 1rem;
  font-weight: bold;
}

.success-icon {
  font-size: 1rem;
  font-weight: bold;
}
</style>
