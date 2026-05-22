<template>
  <div v-if="visible" class="modal-overlay" @click.self="handleClose" role="dialog" aria-modal="true" aria-labelledby="modal-title">
    <div class="modal-content new-template-modal">
      <div class="modal-header">
        <h3 id="modal-title">{{ t('codegen.modal.createTitle') }}</h3>
        <button class="modal-close" @click="handleClose" :aria-label="t('common.close')">
          <Icon name="close" size="md" />
        </button>
      </div>
      
      <div class="modal-body">
        <!-- Loading service metadata -->
        <div v-if="loadingService" class="loading-state">
          <div class="loading-spinner">{{ t('codegen.modal.loadingService') }}</div>
        </div>
        
        <!-- Service metadata error -->
        <div v-else-if="serviceError" class="error-banner">
          <Icon name="exclamation-triangle" size="sm" />
          <span>{{ serviceError }}</span>
        </div>
        
        <!-- Form -->
        <form v-else @submit.prevent="handleSubmit" class="modal-form">
          <!-- User requirement -->
          <div class="form-group">
            <label for="requirement">
              {{ t('codegen.form.requirement') }} <span class="required">*</span>
            </label>
            <textarea
              id="requirement"
              v-model="form.user_requirement"
              class="form-textarea"
              rows="4"
              :placeholder="t('codegen.form.requirementPlaceholder')"
              required
              :disabled="submitting"
              @blur="validateRequirement"
            />
            <small v-if="errors.user_requirement" class="form-error">
              {{ errors.user_requirement }}
            </small>
            <small v-else class="form-hint">
              {{ t('codegen.form.requirementHint') }}
            </small>
          </div>
          
          <!-- Target files selection (if service has output_config) -->
          <div v-if="service && service.output_config && service.output_config.items && service.output_config.items.length > 0" class="form-group">
            <label>
              {{ t('codegen.form.outputs') }}
            </label>
            <div v-if="service.output_config.collection_description" class="output-description">
              {{ service.output_config.collection_description }}
            </div>
            <div class="checkbox-list">
              <label
                v-for="(item, index) in service.output_config.items"
                :key="index"
                class="checkbox-item"
              >
                <input
                  type="checkbox"
                  :value="item.filename"
                  v-model="form.selectedOutputs"
                  :disabled="submitting"
                />
                <div class="checkbox-content">
                  <div class="checkbox-header">
                    <span class="file-name">{{ item.filename }}</span>
                    <span class="file-type-badge" :class="`type-${item.type}`">
                      {{ item.type === 'file' ? t('codegen.form.fileType') : t('codegen.form.textType') }}
                    </span>
                  </div>
                  <div v-if="item.description" class="file-description">
                    {{ item.description }}
                  </div>
                </div>
              </label>
            </div>
            <small class="form-hint">
              {{ t('codegen.form.outputsHint') }}
            </small>
          </div>
          
          <!-- Additional context -->
          <div class="form-group">
            <label for="context">
              {{ t('codegen.form.context') }}
            </label>
            <textarea
              id="context"
              v-model="form.context"
              class="form-textarea"
              rows="2"
              :placeholder="t('codegen.form.contextPlaceholder')"
              :disabled="submitting"
            />
            <small class="form-hint">
              {{ t('codegen.form.contextHint') }}
            </small>
          </div>
          
          <!-- Form error -->
          <div v-if="formError" class="error-banner">
            <Icon name="exclamation-triangle" size="sm" />
            <span>{{ formError }}</span>
          </div>
          
          <!-- Form actions -->
          <div class="modal-footer">
            <button
              type="button"
              class="button button-secondary"
              @click="handleClose"
              :disabled="submitting"
            >
              {{ t('common.cancel') }}
            </button>
            <button
              type="submit"
              class="button button-primary"
              :disabled="!isFormValid || submitting"
            >
              <span v-if="submitting" class="button-loading">
                <span class="spinner"></span>
                {{ t('codegen.modal.creating') }}
              </span>
              <span v-else>{{ t('codegen.modal.create') }}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import Icon from '../common/Icon.vue'
import { getService, type Service } from '../../api/service'

interface Props {
  visible: boolean
  projectId?: string | null
  serviceId?: string | null
}

interface FormData {
  user_requirement: string
  selectedOutputs: string[]
  context: string
}

interface FormErrors {
  user_requirement?: string
}

const props = withDefaults(defineProps<Props>(), {
  projectId: null,
  serviceId: null
})

const emit = defineEmits<{
  close: []
  submit: [payload: {
    user_requirement: string
    project_id?: string
    service_id?: string
    context?: string
    output_config?: Record<string, any> | null
  }]
}>()

const service = ref<Service | null>(null)
const loadingService = ref(false)
const serviceError = ref<string | null>(null)
const submitting = ref(false)
const formError = ref<string | null>(null)
const { t } = useI18n()

const form = ref<FormData>({
  user_requirement: '',
  selectedOutputs: [],
  context: ''
})

const errors = ref<FormErrors>({})

const isFormValid = computed(() => {
  return !!form.value.user_requirement.trim() && !errors.value.user_requirement
})

// Watch for modal visibility to fetch service metadata
watch(
  () => [props.visible, props.serviceId],
  async ([visible, serviceId]) => {
    if (visible && serviceId && !service.value) {
      await fetchServiceMetadata(serviceId)
    } else if (!visible) {
      // Reset form when modal closes
      resetForm()
    }
  },
  { immediate: true }
)

async function fetchServiceMetadata(serviceId: string) {
  if (!serviceId) {
    return
  }
  
  loadingService.value = true
  serviceError.value = null
  
  try {
    service.value = await getService(serviceId)
  } catch (err: any) {
    console.error('Failed to fetch service metadata:', err)
    serviceError.value = err.message || t('codegen.errors.loadServiceFailed')
  } finally {
    loadingService.value = false
  }
}

function validateRequirement() {
  const requirement = form.value.user_requirement.trim()
  if (!requirement) {
    errors.value.user_requirement = t('codegen.form.requirementEmpty')
  } else if (requirement.length < 10) {
    errors.value.user_requirement = t('codegen.form.requirementTooShort')
  } else {
    errors.value.user_requirement = undefined
  }
  formError.value = null
}

function resetForm() {
  form.value = {
    user_requirement: '',
    selectedOutputs: [],
    context: ''
  }
  errors.value = {}
  formError.value = null
  serviceError.value = null
  service.value = null
}

function handleClose() {
  if (submitting.value) {
    return
  }
  emit('close')
}

async function handleSubmit() {
  // Validate form
  validateRequirement()
  
  if (!isFormValid.value) {
    formError.value = t('codegen.form.checkInput')
    return
  }
  
  submitting.value = true
  formError.value = null
  
  try {
    // Build requirement text with context
    let requirementText = form.value.user_requirement.trim()
    
    // Add target files info if selected
    if (form.value.selectedOutputs.length > 0) {
      requirementText += `\\n\\n${t('codegen.form.outputsLabel')}: ${form.value.selectedOutputs.join('、')}`
    }
    
    // Add context if provided
    if (form.value.context.trim()) {
      requirementText += `\\n\\n${t('codegen.form.contextLabel')}: ${form.value.context.trim()}`
    }
    
    // Build payload
    const payload: {
      user_requirement: string
      project_id?: string
      service_id?: string
      output_config?: Record<string, any> | null
    } = {
      user_requirement: requirementText
    }
    
    if (props.projectId) {
      payload.project_id = props.projectId
    }
    
    if (props.serviceId) {
      payload.service_id = props.serviceId
    }
    
    const selectedOutputConfig = buildSelectedOutputConfig()
    if (selectedOutputConfig) {
      payload.output_config = selectedOutputConfig
    }
    
    emit('submit', payload)
    
    // Don't close immediately - let parent handle success/error
    // The parent will close the modal on success
  } catch (err: any) {
    console.error('Failed to submit form:', err)
    formError.value = err.message || t('codegen.errors.submitFailed')
    // Keep form state on error
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.new-template-modal {
  max-width: 600px;
  max-height: 90vh;
  overflow-y: auto;
}

.modal-form {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.form-group label {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
}

.required {
  color: var(--text-error, #ff4d4f);
}

.form-input,
.form-textarea {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  font-size: 14px;
  font-family: inherit;
  background: var(--bg-primary);
  color: var(--text-primary);
  transition: all 0.2s ease;
}

.form-input:focus,
.form-textarea:focus {
  outline: none;
  border-color: var(--accent-primary);
  box-shadow: 0 0 0 2px rgba(24, 144, 255, 0.1);
}

.form-input:disabled,
.form-textarea:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  background: var(--bg-secondary);
}

.form-textarea {
  resize: vertical;
  min-height: 100px;
}

.form-hint {
  font-size: 12px;
  color: var(--text-tertiary);
}

.form-error {
  font-size: 12px;
  color: var(--text-error, #ff4d4f);
}

.output-description {
  font-size: 13px;
  color: var(--text-secondary);
  padding: var(--spacing-sm);
  background: var(--bg-secondary);
  border-radius: var(--radius-sm);
  margin-bottom: var(--spacing-sm);
}

.checkbox-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
  max-height: 200px;
  overflow-y: auto;
  padding: var(--spacing-sm);
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
}

.checkbox-item {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background 0.2s ease;
}

.checkbox-item:hover {
  background: var(--bg-tertiary);
}

.checkbox-item input[type="checkbox"] {
  margin-top: 2px;
  width: 16px;
  height: 16px;
  cursor: pointer;
  flex-shrink: 0;
}

.checkbox-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.checkbox-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-sm);
}

.file-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}

.file-type-badge {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
  text-transform: uppercase;
}

.file-type-badge.type-file {
  background: rgba(24, 144, 255, 0.1);
  color: var(--accent-primary);
}

.file-type-badge.type-text {
  background: rgba(82, 196, 26, 0.1);
  color: #52c41a;
}

.file-description {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
}

.loading-state {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-xl);
  color: var(--text-secondary);
}

.loading-spinner {
  font-size: 14px;
}

.error-banner {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-md);
  background: rgba(255, 77, 79, 0.1);
  border: 1px solid rgba(255, 77, 79, 0.3);
  border-radius: var(--radius-md);
  color: var(--text-error, #ff4d4f);
  font-size: 14px;
}

.modal-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--spacing-md);
  padding-top: var(--spacing-lg);
  border-top: 1px solid var(--border-color);
}

.button {
  padding: 8px 16px;
  border-radius: var(--radius-md);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-xs);
  border: 1px solid transparent;
  min-width: 80px;
}

.button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.button-primary {
  background: var(--accent-primary);
  color: white;
  border-color: var(--accent-primary);
}

.button-primary:hover:not(:disabled) {
  background: var(--accent-hover, #1890ff);
  border-color: var(--accent-hover, #1890ff);
}

.button-secondary {
  background: var(--bg-tertiary);
  color: var(--text-primary);
  border-color: var(--border-color);
}

.button-secondary:hover:not(:disabled) {
  background: var(--bg-secondary);
}

.button-loading {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
}

.spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
<!-- function buildSelectedOutputConfig(): Record<string, any> | null {
  if (!service.value || !service.value.output_config) {
    return null
  }
  if (form.value.selectedOutputs.length === 0) {
    return null
  }
  const selectedItems = service.value.output_config.items?.filter(item =>
    form.value.selectedOutputs.includes(item.filename)
  ) || []

  if (selectedItems.length === 0) {
    return null
  }

  return {
    collection_description: service.value.output_config.collection_description || '用户选择的输出文件',
    items: selectedItems.map(item => ({
      ...item
    }))
  }
} -->
