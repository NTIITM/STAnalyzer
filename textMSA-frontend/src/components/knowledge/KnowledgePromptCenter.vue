<template>
  <div class="prompt-center">
    <div class="page-header">
      <div class="page-header-left">
        <button class="back-btn" @click="goBack">
          <Icon name="chevron-left" size="md" />
          <span>{{ $t('common.cancel') }}</span>
        </button>
        <div>
          <h1>{{ $t('knowledge.promptCenter.title') }}</h1>
          <p class="header-subtitle">{{ $t('knowledge.promptCenter.subtitle') }}</p>
        </div>
      </div>
      <div class="page-header-right">
        <button class="button button-primary" @click="refreshData" :disabled="loading">
          <Icon :name="loading ? 'loading' : 'refresh'" size="sm" />
          <span>{{ $t('knowledge.promptCenter.refresh') }}</span>
        </button>
      </div>
    </div>

    <div class="prompt-layout">
      <section class="prompt-section">
        <div class="section-header">
          <div>
            <h2>{{ $t('knowledge.promptCenter.configTitle') }}</h2>
            <p>{{ $t('knowledge.promptCenter.configDesc') }}</p>
          </div>
        </div>
        <KnowledgePrompt
          :templates="promptTemplates"
          :config="promptConfig"
          @update:config="promptConfig = $event"
          @save="handleSavePrompt"
          @delete-template="handleDeleteTemplate"
        />
      </section>

      <section class="prompt-section">
        <div class="section-header">
          <div>
            <h2>{{ $t('knowledge.promptCenter.generatorTitle') }}</h2>
            <p>{{ $t('knowledge.promptCenter.generatorDesc') }}</p>
          </div>
        </div>
        <form class="prompt-form" @submit.prevent="handleGenerate">
          <label class="form-group">
            <span>{{ $t('knowledge.workflow.promptQuery') }}</span>
            <input
              v-model="promptForm.query"
              type="text"
              class="form-input"
              :placeholder="$t('knowledge.workflow.promptPlaceholder')"
            />
          </label>
          <label class="form-group">
            <span>{{ $t('knowledge.workflow.promptDescription') }}</span>
            <textarea
              v-model="promptForm.description"
              rows="3"
              class="form-textarea"
              :placeholder="$t('knowledge.workflow.promptDescriptionPlaceholder')"
            />
          </label>
          <button class="button button-primary" :disabled="isGenerating || !promptForm.query.trim()">
            <Icon :name="isGenerating ? 'loading' : 'sparkles'" size="sm" />
            <span>{{ isGenerating ? $t('knowledge.promptCenter.generating') : $t('knowledge.promptCenter.generate') }}</span>
          </button>
        </form>

        <KnowledgeExtractionResults
          :mode="pendingPrompt ? 'prompt' : null"
          :triplets="[]"
          :pending-prompt="pendingPrompt"
          :literature-result="null"
          :importing="false"
          :approving="isApproving"
          @approve-prompt="handleApprove"
        />
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import Icon from '../common/Icon.vue'
import KnowledgePrompt from './KnowledgePrompt.vue'
import KnowledgeExtractionResults from './KnowledgeExtractionResults.vue'
import {
  approveGeneratedPrompt,
  generateKnowledgePrompt,
  getKnowledgePromptConfig,
  getKnowledgePromptTemplates,
  saveKnowledgePromptConfig,
  deleteKnowledgePromptTemplate,
  type PendingPrompt,
  type PromptConfigPayload,
  type PromptTemplate
} from '../../api/knowledge'

const router = useRouter()
const { t } = useI18n()

const promptTemplates = ref<PromptTemplate[]>([])
const promptConfig = ref<PromptConfigPayload>({
  templateId: undefined,
  entityPrompt: {},
  relationPrompt: {},
  constraints: ''
})
const pendingPrompt = ref<PendingPrompt | null>(null)
const loading = ref(false)
const isGenerating = ref(false)
const isApproving = ref(false)

const promptForm = ref({
  query: '',
  description: ''
})

function goBack() {
  router.push('/knowledge')
}

async function refreshData(preferredTemplateId?: string) {
  loading.value = true
  try {
    const [templates, currentConfig] = await Promise.all([
      getKnowledgePromptTemplates(),
      getKnowledgePromptConfig().catch(() => null)
    ])
    promptTemplates.value = templates
    const targetId = preferredTemplateId || currentConfig?.templateId || promptConfig.value.templateId || templates[0]?.id
    applyTemplateById(targetId)
  } finally {
    loading.value = false
  }
}

function applyTemplateById(templateId?: string) {
  const template = templateId ? promptTemplates.value.find(t => t.id === templateId) : undefined
  if (template) {
    promptConfig.value = {
      templateId: template.id,
      name: template.name,
      description: template.description,
      entityPrompt: template.entityPrompt,
      relationPrompt: template.relationPrompt,
      constraints: template.constraints,
      isDefault: template.isDefault,
      updatedAt: template.updatedAt
    }
  } else if (promptTemplates.value.length) {
    applyTemplateById(promptTemplates.value[0].id)
  } else {
    promptConfig.value = {
      templateId: undefined,
      entityPrompt: {},
      relationPrompt: {},
      constraints: ''
    }
  }
}

async function handleSavePrompt(config: PromptConfigPayload) {
  try {
    await saveKnowledgePromptConfig(config)
    await refreshData(config.templateId)
    if (window.showMessage) window.showMessage.success(t('knowledge.messages.promptSaved'))
  } catch (err: any) {
    if (window.showMessage) window.showMessage.error(err.message || t('knowledge.form.saveFailed'))
  }
}

async function handleDeleteTemplate(templateId: string) {
  const template = promptTemplates.value.find(t => t.id === templateId)
  if (!template) return
  if (isSystemTemplate(template.id)) {
    if (window.showMessage) window.showMessage.error(t('knowledge.promptCenter.deleteBlocked'))
    return
  }
  if (!window.confirm(t('knowledge.promptCenter.deleteConfirm', { name: template.label || template.name || template.id }))) {
    return
  }
  try {
    await deleteKnowledgePromptTemplate(templateId)
    if (window.showMessage) window.showMessage.success(t('knowledge.promptCenter.deleteSuccess'))
    await refreshData()
  } catch (err: any) {
    if (window.showMessage) window.showMessage.error(err.message || t('knowledge.promptCenter.deleteError'))
  }
}

function findTemplate(id?: string) {
  if (!id) return undefined
  return promptTemplates.value.find(t => t.id === id)
}

function isSystemTemplate(id?: string) {
  if (!id) return false
  return id.startsWith('system_')
}

async function handleGenerate() {
  if (!promptForm.value.query.trim()) return
  isGenerating.value = true
  try {
    pendingPrompt.value = await generateKnowledgePrompt({
      query: promptForm.value.query.trim(),
      description: promptForm.value.description || undefined
    })
    if (window.showMessage) window.showMessage.success(t('knowledge.promptCenter.generated'))
  } catch (err: any) {
    if (window.showMessage) window.showMessage.error(err.message || t('knowledge.promptCenter.generateError'))
  } finally {
    isGenerating.value = false
  }
}

async function handleApprove(options: { name?: string; isDefault?: boolean }) {
  if (!pendingPrompt.value) return
  isApproving.value = true
  try {
    await approveGeneratedPrompt({
      pendingPromptId: pendingPrompt.value.pendingPromptId,
      name: options.name,
      isDefault: options.isDefault
    })
    pendingPrompt.value = null
    await refreshData()
    if (window.showMessage) window.showMessage.success(t('knowledge.messages.promptApproved'))
  } catch (err: any) {
    if (window.showMessage) window.showMessage.error(err.message || t('knowledge.messages.promptApproveError'))
  } finally {
    isApproving.value = false
  }
}

onMounted(() => {
  refreshData()
})
</script>

<style scoped>
.prompt-center {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-secondary);
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-lg) var(--spacing-xl);
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-primary);
}

.page-header-left {
  display: flex;
  align-items: center;
  gap: var(--spacing-lg);
}

.header-subtitle {
  margin: 0;
  color: rgba(0, 0, 0, 0.65);
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

.prompt-layout {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-xl);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xl);
}

.prompt-section {
  background: var(--bg-primary);
  border-radius: var(--radius-lg);
  padding: var(--spacing-xl);
  border: 1px solid var(--border-color);
}

.section-header {
  margin-bottom: var(--spacing-lg);
}

.prompt-form {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-lg);
}
</style>
