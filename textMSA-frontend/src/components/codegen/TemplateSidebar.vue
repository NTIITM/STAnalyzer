<template>
  <div class="template-sidebar">
    <!-- Loading state -->
    <div v-if="loading" class="empty-state">
      <div class="loading-spinner">{{ t('codegen.loading') }}</div>
    </div>

    <!-- Error state -->
    <div v-else-if="error" class="empty-state error">
      <div class="error-icon">⚠️</div>
      <div class="error-text">{{ error }}</div>
    </div>

    <!-- Empty state -->
    <div v-else-if="templates.length === 0" class="empty-state">
      <div class="empty-icon">📝</div>
      <div class="empty-text">{{ t('codegen.templates.empty') }}</div>
      <button class="button button-primary" @click="$emit('create')">{{ t('codegen.templates.createNew') }}</button>
    </div>

    <!-- Template list -->
    <div v-else class="template-list">
      <div
        v-for="template in templates"
        :key="template.template_id"
        class="template-item"
        :class="{ active: template.template_id === selectedTemplateId }"
        @click="$emit('select', template.template_id)"
        role="button"
        tabindex="0"
        @keydown.enter="$emit('select', template.template_id)"
        @keydown.space.prevent="$emit('select', template.template_id)"
      >
        <div class="template-info">
          <div class="template-name">{{ template.user_requirement || t('codegen.templates.untitled') }}</div>
          <div class="template-meta">
            <span class="badge">{{ template.code_language?.toUpperCase() || 'LANG' }}</span>
            <span class="dot">·</span>
            <span class="status">{{ template.status }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { CodegenTemplate } from '../../types/codegen'

interface Props {
  templates: CodegenTemplate[]
  loading: boolean
  selectedTemplateId: string | null
  error?: string | null
}

withDefaults(defineProps<Props>(), {
  error: null
})

const { t } = useI18n()
defineEmits<{
  select: [templateId: string]
  create: []
}>()
</script>

<style scoped>
.template-sidebar {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.template-list {
  padding: var(--spacing-sm);
  overflow-y: auto;
  flex: 1;
}

.template-item {
  background: var(--bg-tertiary);
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  padding: var(--spacing-md);
  margin-bottom: var(--spacing-sm);
  cursor: pointer;
  transition: all 0.2s;
}

.template-item:hover {
  background: var(--bg-secondary);
  border-color: var(--border-color);
}

.template-item:focus {
  outline: 2px solid var(--accent-primary);
  outline-offset: 2px;
}

.template-item.active {
  border-color: var(--accent-primary);
  background: rgba(24, 144, 255, 0.08);
}

.template-info {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.template-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.template-meta {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  font-size: 12px;
  color: var(--text-secondary);
}

.badge {
  padding: 2px 6px;
  background: var(--bg-secondary);
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
}

.dot {
  margin: 0 4px;
}

.status {
  text-transform: capitalize;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-xl);
  text-align: center;
  color: var(--text-tertiary);
  min-height: 200px;
}

.empty-state.error {
  color: var(--text-error, #ff4d4f);
}

.empty-icon,
.error-icon {
  font-size: 48px;
  margin-bottom: var(--spacing-md);
  opacity: 0.5;
}

.empty-text,
.error-text {
  font-size: 14px;
  margin-bottom: var(--spacing-md);
}

.loading-spinner {
  font-size: 14px;
  color: var(--text-secondary);
}

.button {
  padding: 6px 16px;
  border-radius: 6px;
  border: 1px solid var(--border-color);
  background: var(--accent-primary);
  color: #fff;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s;
}

.button-primary:hover {
  filter: brightness(1.05);
}
</style>

