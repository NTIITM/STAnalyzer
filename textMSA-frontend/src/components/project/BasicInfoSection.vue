<template>
  <div class="form-section">
    <h2 class="section-title">{{ $t('project.basicInfo') }}</h2>
    
    <div class="form-group">
      <label>{{ $t('project.name') }} <span class="required">{{ $t('common.required') }}</span></label>
      <input 
        :value="formData.name"
        type="text"
        class="form-input"
        :placeholder="$t('project.name')"
        required
        @input="handleNameInput"
      />
    </div>

    <div class="form-group">
      <label>{{ $t('project.description') }}</label>
      <textarea 
        :value="formData.description"
        class="form-textarea"
        rows="3"
        :placeholder="$t('project.description')"
        @input="handleDescriptionInput"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
export interface BasicInfoFormData {
  name: string
  description: string
}

const props = defineProps<{
  formData: BasicInfoFormData
}>()

const emit = defineEmits<{
  'update:formData': [data: BasicInfoFormData]
}>()

function handleNameInput(event: Event) {
  const target = event.target as HTMLInputElement
  emit('update:formData', {
    ...props.formData,
    name: target.value
  })
}

function handleDescriptionInput(event: Event) {
  const target = event.target as HTMLTextAreaElement
  emit('update:formData', {
    ...props.formData,
    description: target.value
  })
}
</script>

<style scoped>
.form-section {
  background: white;
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 24px;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
  transition: box-shadow 0.3s ease;
}

.form-section:hover {
  box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05), 0 4px 6px -2px rgba(0, 0, 0, 0.025);
}

.section-title {
  margin: 0 0 20px 0;
  font-size: 18px;
  font-weight: 600;
  line-height: 1.4;
  color: var(--text-primary, #1e293b);
  border-bottom: 1px solid var(--border-color, #f1f5f9);
  padding-bottom: 12px;
}

.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary, #334155);
}

.required {
  color: #ef4444;
  margin-left: 4px;
}

.form-input,
.form-textarea {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid var(--border-color, #cbd5e1);
  border-radius: 8px;
  font-size: 14px;
  font-family: inherit;
  background-color: #f8fafc;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  color: var(--text-primary, #0f172a);
}

.form-input:hover,
.form-textarea:hover {
  border-color: #94a3b8;
}

.form-input:focus,
.form-textarea:focus {
  outline: none;
  background-color: white;
  border-color: var(--accent-primary, #3b82f6);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15);
}

.form-textarea {
  resize: vertical;
  min-height: 100px;
  line-height: 1.5;
}
</style>

