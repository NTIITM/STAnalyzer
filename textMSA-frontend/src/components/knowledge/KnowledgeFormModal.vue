<template>
  <div v-if="visible" class="modal-overlay" @click.self="$emit('close')">
    <div class="modal-content knowledge-modal">
      <div class="modal-header">
        <h3>
          {{ mode === 'create' ? $t('knowledge.modal.createTitle') : $t('knowledge.modal.editTitle') }}
        </h3>
        <button class="modal-close" @click="$emit('close')">
          <Icon name="close" size="md" />
        </button>
      </div>
      <div class="modal-body">
        <form @submit.prevent="handleSubmit" class="modal-form">
          <label class="form-group">
            <span>{{ $t('knowledge.modal.fields.title') }} <span class="required">{{ $t('common.required') }}</span></span>
            <input v-model="form.title" type="text" class="form-input" required />
          </label>
          <label class="form-group">
            <span>{{ $t('knowledge.modal.fields.description') }} <span class="required">{{ $t('common.required') }}</span></span>
            <textarea v-model="form.description" rows="3" class="form-textarea" required />
          </label>
          <div class="form-group relation-grid">
            <label>
              <span>{{ $t('knowledge.modal.fields.relationFrom') }}</span>
              <input v-model="form.relation.fromEntity" type="text" class="form-input" />
            </label>
            <label>
              <span>{{ $t('knowledge.modal.fields.relationType') }}</span>
              <input v-model="form.relation.relation" type="text" class="form-input" />
            </label>
            <label>
              <span>{{ $t('knowledge.modal.fields.relationTo') }}</span>
              <input v-model="form.relation.endEntity" type="text" class="form-input" />
            </label>
          </div>
          <label class="form-group">
            <span>{{ $t('knowledge.modal.fields.tags') }}</span>
            <input
              v-model="form.tagsText"
              type="text"
              class="form-input"
              :placeholder="$t('knowledge.modal.tagsPlaceholder')"
            />
          </label>
          <label class="form-group">
            <span>{{ $t('knowledge.modal.fields.scope') }}</span>
            <el-select v-model="form.scope" :placeholder="$t('knowledge.modal.fields.scope')">
              <el-option :label="$t('knowledge.scopes.private')" value="private" />
              <el-option :label="$t('knowledge.scopes.public')" value="public" />
            </el-select>
          </label>
          <p class="form-hint">
            {{ $t('knowledge.modal.userEditedHint') }}
          </p>
          <div class="modal-footer">
            <button type="button" class="button button-secondary" @click="$emit('close')">
              {{ $t('common.cancel') }}
            </button>
            <button type="submit" class="button button-primary" :disabled="saving">
              <span v-if="saving" class="save-spinner"></span>
              <span>{{ saving ? $t('common.saving') : $t('common.save') }}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import Icon from '../common/Icon.vue'
import type { KnowledgeRecord, KnowledgeScope, KnowledgeRelationSummary } from '../../api/knowledge'

const { t } = useI18n()

const props = defineProps<{
  visible: boolean
  mode: 'create' | 'edit'
  item?: KnowledgeRecord | null
}>()

const emit = defineEmits<{
  close: []
  submit: [data: {
    title: string
    description: string
    relationSummary: KnowledgeRelationSummary
    tags: string[]
    scope: Exclude<KnowledgeScope, 'system'>
  }]
}>()

const saving = ref(false)

const form = reactive({
  title: '',
  description: '',
  relation: createEmptyRelation(),
  tagsText: '',
  scope: 'private' as Exclude<KnowledgeScope, 'system'>
})

watch(() => props.visible, (visible) => {
  if (visible && props.item && props.mode === 'edit') {
    form.title = props.item.title
    form.description = props.item.description
    Object.assign(
      form.relation,
      props.item.relationSummary ? { ...props.item.relationSummary } : createEmptyRelation()
    )
    form.tagsText = (props.item.tags || []).join(', ')
    form.scope = props.item.scope as Exclude<KnowledgeScope, 'system'>
  } else if (visible && props.mode === 'create') {
    form.title = ''
    form.description = ''
    Object.assign(form.relation, createEmptyRelation())
    form.tagsText = ''
    form.scope = 'private'
  }
})

function normalizeTags(input: string) {
  if (!input) return []
  return input
    .split(',')
    .map(tag => tag.trim())
    .filter(Boolean)
}

function createEmptyRelation(): KnowledgeRelationSummary {
  return {
    fromEntity: '',
    relation: '',
    endEntity: ''
  }
}

function normalizeRelation(relation: KnowledgeRelationSummary) {
  const fromEntity = relation.fromEntity.trim()
  const relationType = relation.relation.trim()
  const endEntity = relation.endEntity.trim()
  if (!fromEntity || !relationType || !endEntity) {
    return null
  }
  return {
    fromEntity,
    relation: relationType,
    endEntity
  }
}

function handleSubmit() {
  if (!form.title.trim() || !form.description.trim()) {
    if (window.showMessage) {
      window.showMessage.error(t('knowledge.messages.missingFields'))
    }
    return
  }

  const relation = normalizeRelation(form.relation)
  if (!relation) {
    if (window.showMessage) {
      window.showMessage.error(t('knowledge.messages.missingRelation'))
    }
    return
  }

  saving.value = true
  const tags = normalizeTags(form.tagsText)
  
  emit('submit', {
    title: form.title.trim(),
    description: form.description.trim(),
    relationSummary: relation,
    tags,
    scope: form.scope
  })
  
  setTimeout(() => {
    saving.value = false
  }, 300)
}
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  backdrop-filter: blur(4px);
}

.modal-content {
  background: var(--bg-primary);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xl);
  max-width: 640px;
  width: 90%;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-lg) var(--spacing-xl);
  border-bottom: 1px solid var(--border-color);
}

.modal-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 500;
  line-height: 1.5;
  color: rgba(0, 0, 0, 0.85);
  letter-spacing: 0;
}

.modal-close {
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  color: rgba(0, 0, 0, 0.45);
  transition: all 0.2s cubic-bezier(0.645, 0.045, 0.355, 1);
}

.modal-close:hover {
  background: var(--bg-tertiary);
  color: rgba(0, 0, 0, 0.85);
}

.modal-body {
  padding: var(--spacing-xl);
  overflow-y: auto;
  flex: 1;
}

.modal-form {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
}

.relation-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: var(--spacing-md);
}

.form-hint {
  font-size: 12px;
  font-weight: 400;
  line-height: 1.5715;
  color: rgba(0, 0, 0, 0.45);
  margin: 0;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--spacing-sm);
  margin-top: var(--spacing-md);
}

.required {
  color: rgba(220, 100, 100, 0.9);
}

.save-spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  margin-right: 8px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  vertical-align: middle;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
