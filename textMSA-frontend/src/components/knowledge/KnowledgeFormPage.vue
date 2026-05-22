<template>
  <div class="knowledge-form-page">
    <div class="page-header">
      <div class="page-header-left">
        <button class="back-btn" @click="handleBack">
          <Icon name="chevron-left" size="md" class="back-icon" />
          <span>{{ $t('common.cancel') }}</span>
        </button>
        <h1>{{ isEditMode ? $t('knowledge.modal.editTitle') : $t('knowledge.modal.createTitle') }}</h1>
      </div>
      <div class="page-header-right">
        <button
          class="button button-primary"
          :class="{ 'button-saving': saving }"
          @click="handleSave"
          :disabled="saving || !isFormValid"
        >
          <span v-if="saving" class="save-spinner"></span>
          <span>{{ saving ? $t('common.saving') : $t('common.save') }}</span>
        </button>
      </div>
    </div>

    <div v-if="prefillNotice" class="prefill-banner">
      <Icon name="info" size="sm" />
      <span>{{ prefillNotice }}</span>
      <button class="text-link" type="button" @click="clearPrefill">
        {{ $t('knowledge.form.clearPrefill') }}
      </button>
    </div>

    <div class="form-container">
      <section class="form-section">
        <h2 class="section-title">{{ $t('knowledge.detail.basicInfo') }}</h2>
        <div class="form-group">
          <label>{{ $t('knowledge.modal.fields.title') }} <span class="required">{{ $t('common.required') }}</span></label>
          <input
            v-model="form.title"
            type="text"
            class="form-input"
            :placeholder="$t('knowledge.modal.fields.title')"
          />
        </div>
        <div class="form-group">
          <label>{{ $t('knowledge.modal.fields.description') }} <span class="required">{{ $t('common.required') }}</span></label>
          <textarea
            v-model="form.description"
            rows="4"
            class="form-textarea"
            :placeholder="$t('knowledge.modal.fields.description')"
          />
        </div>
        <div class="form-group relation-grid">
          <label>
            <span>{{ $t('knowledge.modal.fields.relationFrom') }}</span>
            <input v-model="form.relationSummary.fromEntity" type="text" class="form-input" />
          </label>
          <label>
            <span>{{ $t('knowledge.modal.fields.relationType') }}</span>
            <input v-model="form.relationSummary.relation" type="text" class="form-input" />
          </label>
          <label>
            <span>{{ $t('knowledge.modal.fields.relationTo') }}</span>
            <input v-model="form.relationSummary.endEntity" type="text" class="form-input" />
          </label>
        </div>
        <div class="form-group">
          <label>{{ $t('knowledge.modal.fields.tags') }}</label>
          <input
            v-model="form.tagsText"
            type="text"
            class="form-input"
            :placeholder="$t('knowledge.modal.tagsPlaceholder')"
          />
          <small>{{ $t('knowledge.form.tagsHint') }}</small>
        </div>
        <div class="form-group">
          <label>{{ $t('knowledge.modal.fields.scope') }}</label>
          <el-select v-model="form.scope" :placeholder="$t('knowledge.modal.fields.scope')">
            <el-option :label="$t('knowledge.scopes.private')" value="private" />
            <el-option :label="$t('knowledge.scopes.public')" value="public" />
          </el-select>
        </div>
      </section>

      <section class="form-section">
        <h2 class="section-title">{{ $t('knowledge.form.metadataSection') }}</h2>
        <div class="metadata-list">
          <div v-for="(entry, index) in metadataEntries" :key="index" class="metadata-row">
            <input
              v-model="entry.key"
              type="text"
              class="form-input"
              :placeholder="$t('knowledge.form.metadataKey')"
            />
            <input
              v-model="entry.value"
              type="text"
              class="form-input"
              :placeholder="$t('knowledge.form.metadataValue')"
            />
            <button class="action-btn" type="button" @click="removeMetadata(index)" :disabled="metadataEntries.length === 1">
              <Icon name="delete" size="sm" />
            </button>
          </div>
          <button class="button button-secondary" type="button" @click="addMetadata">
            <Icon name="plus" size="sm" />
            <span>{{ $t('knowledge.form.metadataAdd') }}</span>
          </button>
        </div>
      </section>
    </div>

    <div v-if="formError" class="form-error-toast">
      {{ formError }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import Icon from '../common/Icon.vue'
import {
  createKnowledge,
  getKnowledgeDetail,
  updateKnowledge,
  type KnowledgeMutationPayload,
  type KnowledgeRelationSummary,
  type KnowledgeScope
} from '../../api/knowledge'

const router = useRouter()
const route = useRoute()
const { t } = useI18n()

const knowledgeId = computed(() => route.params.id as string | undefined)
const isEditMode = computed(() => !!knowledgeId.value)

const saving = ref(false)
const formError = ref('')
const prefillNotice = ref<string | null>(null)
const PREFILL_KEY = 'knowledge_triplet_prefill'

const form = reactive({
  title: '',
  description: '',
  relationSummary: createRelationSummary(),
  tagsText: '',
  scope: 'private' as Exclude<KnowledgeScope, 'system'>
})

const metadataEntries = ref<Array<{ key: string; value: string }>>([{ key: '', value: '' }])

const isFormValid = computed(() => {
  return Boolean(form.title.trim() && form.description.trim() && isRelationValid(form.relationSummary))
})

onMounted(async () => {
  if (isEditMode.value) {
    await loadKnowledgeData()
  } else {
    applyPrefill()
  }
})

function createRelationSummary(): KnowledgeRelationSummary {
  return {
    fromEntity: '',
    relation: '',
    endEntity: ''
  }
}

function isRelationValid(summary: KnowledgeRelationSummary) {
  return (
    summary.fromEntity.trim() &&
    summary.relation.trim() &&
    summary.endEntity.trim()
  )
}

async function loadKnowledgeData() {
  if (!knowledgeId.value) return
  try {
    const knowledge = await getKnowledgeDetail(knowledgeId.value)
    form.title = knowledge.title
    form.description = knowledge.description
    form.relationSummary = knowledge.relationSummary
      ? { ...knowledge.relationSummary }
      : createRelationSummary()
    form.tagsText = (knowledge.tags || []).join(', ')
    form.scope = knowledge.scope as Exclude<KnowledgeScope, 'system'>
    const metadata = knowledge.metadata || {}
    const entries = Object.entries(metadata)
      .map(([key, value]) => ({ key, value: String(value ?? '') }))
      .filter(entry => entry.key)
    metadataEntries.value = entries.length ? entries : [{ key: '', value: '' }]
  } catch (err: any) {
    formError.value = err.message || t('knowledge.form.loadFailed')
  }
}

function applyPrefill() {
  const raw = sessionStorage.getItem(PREFILL_KEY)
  if (!raw) return
  try {
    const data = JSON.parse(raw)
    if (data.title) form.title = data.title
    if (data.description) form.description = data.description
    if (data.relationSummary) {
      form.relationSummary = {
        fromEntity: data.relationSummary.fromEntity || '',
        relation: data.relationSummary.relation || '',
        endEntity: data.relationSummary.endEntity || ''
      }
    }
    if (data.metadata) {
      const entries = Object.entries(data.metadata)
        .map(([key, value]) => ({ key, value: String(value ?? '') }))
        .filter(entry => entry.key)
      metadataEntries.value = entries.length ? entries : [{ key: '', value: '' }]
    }
    prefillNotice.value = t('knowledge.form.prefillSuccess')
  } catch (err) {
    console.warn('无法解析提取候选填充数据:', err)
  } finally {
    sessionStorage.removeItem(PREFILL_KEY)
  }
}

function clearPrefill() {
  prefillNotice.value = null
}

function addMetadata() {
  metadataEntries.value.push({ key: '', value: '' })
}

function removeMetadata(index: number) {
  if (metadataEntries.value.length === 1) return
  metadataEntries.value.splice(index, 1)
}

function parseTags() {
  return form.tagsText
    .split(',')
    .map(tag => tag.trim())
    .filter(Boolean)
}

function buildMetadata() {
  const entries = metadataEntries.value.filter(entry => entry.key.trim())
  if (!entries.length) return undefined
  return entries.reduce<Record<string, string>>((acc, entry) => {
    acc[entry.key.trim()] = entry.value.trim()
    return acc
  }, {})
}

async function handleSave() {
  if (!isFormValid.value) {
    formError.value = t('knowledge.form.invalidFields')
    return
  }

  saving.value = true
  formError.value = ''

  try {
    const relation = {
      fromEntity: form.relationSummary.fromEntity.trim(),
      relation: form.relationSummary.relation.trim(),
      endEntity: form.relationSummary.endEntity.trim()
    }

    const tags = parseTags()
    const payload: KnowledgeMutationPayload = {
      title: form.title.trim(),
      description: form.description.trim(),
      relationSummary: relation,
      scope: form.scope,
      tags,
      metadata: buildMetadata()
    }

    if (tags.length) {
      payload.metadata = {
        ...(payload.metadata || {}),
        tags
      }
    }

    if (isEditMode.value) {
      await updateKnowledge(knowledgeId.value!, payload)
    } else {
      await createKnowledge(payload)
    }

    if (window.showMessage) {
      window.showMessage.success(
        isEditMode.value ? t('knowledge.messages.updateSuccess') : t('knowledge.messages.createSuccess')
      )
    }

    router.push('/knowledge').catch(() => {})
  } catch (err: any) {
    formError.value = err.message || t('knowledge.form.saveFailed')
  } finally {
    saving.value = false
  }
}

function handleBack() {
  router.push('/knowledge')
}
</script>

<style scoped>
.knowledge-form-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-secondary);
}

.page-header {
  display: flex;
  justify-content: space-between;
  padding: var(--spacing-lg) var(--spacing-xl);
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-primary);
}

.page-header-left {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
}

.back-btn {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  border: none;
  background: transparent;
  cursor: pointer;
  color: rgba(0, 0, 0, 0.65);
}

.form-container {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
  gap: var(--spacing-xl);
  padding: var(--spacing-xl);
  overflow-y: auto;
}

.form-section {
  background: var(--bg-primary);
  border-radius: var(--radius-lg);
  padding: var(--spacing-xl);
  border: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
}

.section-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.relation-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: var(--spacing-md);
}

.metadata-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.metadata-row {
  display: grid;
  grid-template-columns: 1fr 1fr auto;
  gap: var(--spacing-sm);
  align-items: center;
}

.action-btn {
  width: 36px;
  height: 36px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  background: var(--bg-secondary);
  cursor: pointer;
}

.prefill-banner {
  margin: var(--spacing-md) var(--spacing-xl) 0;
  background: rgba(24, 144, 255, 0.08);
  border: 1px solid rgba(24, 144, 255, 0.3);
  border-radius: var(--radius-md);
  padding: var(--spacing-md);
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.text-link {
  border: none;
  background: none;
  color: var(--accent-primary);
  cursor: pointer;
}

.form-error-toast {
  margin: var(--spacing-md) var(--spacing-xl);
  padding: var(--spacing-md);
  border-radius: var(--radius-md);
  background: rgba(255, 77, 79, 0.1);
  color: #a8071a;
}
</style>
