<template>
  <div class="page-header">
    <div class="page-header-left">
      <button class="back-btn" @click="$emit('back')">
        <Icon name="chevron-down" size="md" class="back-icon" />
        <span>{{ $t('common.cancel') }}</span>
      </button>
      <h1>{{ isEditMode ? $t('project.config') : $t('project.create') }}</h1>
    </div>
    <div class="page-header-right">
      <el-button 
        type="primary"
        :loading="saving"
        @click="$emit('save')" 
        :disabled="saving || !(isFormValid ?? false)"
      >
        <span>{{ saving ? $t('common.saving') : $t('common.save') }}</span>
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import Icon from '../common/Icon.vue'
import { ElButton } from 'element-plus'

defineProps<{
  isEditMode: boolean
  saving: boolean
  isFormValid: boolean | undefined
}>()

defineEmits<{
  back: []
  save: []
}>()
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-xl);
  background: var(--bg-primary);
  border-bottom: 1px solid var(--border-color);
  box-shadow: var(--shadow-sm);
}

.page-header-left {
  display: flex;
  align-items: center;
  gap: var(--spacing-lg);
}

.back-btn {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 8px 16px;
  border: none;
  background: transparent;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  color: var(--text-secondary);
  transition: all 0.2s ease;
}

.back-btn:hover {
  background: var(--bg-tertiary);
  color: var(--text-primary);
}

.back-icon {
  transform: rotate(90deg);
}

.page-header h1 {
  margin: 0;
  font-size: 20px;
  font-weight: 500;
  line-height: 1.4;
  color: rgba(0, 0, 0, 0.85);
}

.page-header-right {
  display: flex;
  gap: var(--spacing-md);
}

.button {
  padding: 8px 16px;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}

.button-primary {
  background: var(--accent-primary);
  color: white;
}

.button-primary:hover:not(:disabled) {
  background: #1890ff;
}

.button-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.button-saving {
  position: relative;
}

.save-spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
