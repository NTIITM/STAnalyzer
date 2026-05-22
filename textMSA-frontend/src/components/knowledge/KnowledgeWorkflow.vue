<template>
  <div class="panel-card workflow-panel">
    <div class="panel-header">
      <div>
        <p class="panel-eyebrow">{{ $t('knowledge.workflow.badge') }}</p>
        <h4>{{ $t('knowledge.workflow.title') }}</h4>
      </div>
      <Icon name="sparkles" size="md" />
    </div>

    <div class="workflow-tabs">
      <button
        v-for="tab in tabs"
        :key="tab.value"
        class="workflow-tab"
        :class="{ active: activeTab === tab.value }"
        @click="switchTab(tab.value)"
      >
        <Icon :name="tab.icon" size="sm" />
        <span>{{ tab.label }}</span>
      </button>
    </div>

    <form v-if="activeTab === 'text'" class="workflow-form" @submit.prevent="submitText">
      <label class="form-group">
        <span>{{ $t('knowledge.workflow.textLabel') }}</span>
        <textarea
          v-model="textForm.text"
          rows="5"
          class="form-textarea"
          :placeholder="$t('knowledge.workflow.placeholder')"
        />
      </label>
      <label class="form-group">
        <span>{{ $t('knowledge.workflow.templateLabel') }}</span>
        <el-select v-model="textForm.templateId" :placeholder="$t('knowledge.workflow.templateLabel')" clearable>
          <el-option :label="$t('knowledge.workflow.templateAuto')" value="" />
          <el-option 
            v-for="tpl in templates" 
            :key="tpl.id" 
            :label="tpl.label"
            :value="tpl.id"
          />
        </el-select>
      </label>
      <label class="form-group">
        <span>{{ $t('knowledge.workflow.sourceLabel') }}</span>
        <input v-model="textForm.source" type="text" class="form-input" :placeholder="$t('knowledge.workflow.sourcePlaceholder')" />
      </label>
      <el-button type="primary" :disabled="!textForm.text.trim()" :loading="isLoading">
        <Icon name="play" size="sm" />
        <span>{{ $t('knowledge.workflow.run') }}</span>
      </el-button>
    </form>

    <form v-else class="workflow-form" @submit.prevent="submitLiterature">
      <label class="form-group">
        <span>{{ $t('knowledge.workflow.literatureQuery') }}</span>
        <input
          v-model="literatureForm.query"
          type="text"
          class="form-input"
          :placeholder="$t('knowledge.workflow.literaturePlaceholder')"
        />
      </label>
      <label class="form-group">
        <span>{{ $t('knowledge.workflow.templateLabel') }}</span>
        <el-select v-model="literatureForm.templateId" :placeholder="$t('knowledge.workflow.templateLabel')" clearable>
          <el-option :label="$t('knowledge.workflow.templateAuto')" value="" />
          <el-option 
            v-for="tpl in templates" 
            :key="tpl.id" 
            :label="tpl.label"
            :value="tpl.id"
          />
        </el-select>
      </label>
      <label class="form-group">
        <span>{{ $t('knowledge.workflow.maxResults') }}</span>
        <input
          v-model.number="literatureForm.maxResults"
          type="number"
          min="1"
          max="50"
          class="form-input"
        />
      </label>
      <button class="button button-primary" :disabled="isLoading || !literatureForm.query.trim()">
        <Icon :name="isLoading ? 'loading' : 'play'" size="sm" />
        <span>{{ isLoading ? $t('knowledge.workflow.running') : $t('knowledge.workflow.run') }}</span>
      </button>
    </form>

    <div class="workflow-status">
      <p>{{ statusLabel }}</p>
      <small v-if="lastRun">{{ $t('knowledge.workflow.lastRun') }} {{ formatDate(lastRun) }}</small>
    </div>
    <p v-if="errorMessage" class="workflow-error">{{ errorMessage }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import Icon from '../common/Icon.vue'
import {
  extractKnowledgeFromText,
  extractKnowledgeFromLiterature,
  type PromptTemplate,
  type TextExtractionTriplet,
  type LiteratureExtractionResult
} from '../../api/knowledge'

type WorkflowTab = 'text' | 'literature'

interface ExtractionResultPayload {
  mode: WorkflowTab
  triplets?: TextExtractionTriplet[]
  literature?: LiteratureExtractionResult
}

const props = defineProps<{ templates: PromptTemplate[] }>()

const emit = defineEmits<{
  result: [payload: ExtractionResultPayload]
  error: [message: string]
}>()

const { t } = useI18n()

const tabs = [
  { value: 'text' as WorkflowTab, label: t('knowledge.workflow.textTab'), icon: 'document' },
  { value: 'literature' as WorkflowTab, label: t('knowledge.workflow.literatureTab'), icon: 'book' }
]

const activeTab = ref<WorkflowTab>('text')
const isLoading = ref(false)
const lastRun = ref<string | null>(null)
const statusLabel = ref(t('knowledge.workflow.statusIdle'))
const errorMessage = ref('')

const textForm = reactive({
  text: '',
  templateId: '',
  source: ''
})

const literatureForm = reactive({
  query: '',
  templateId: '',
  maxResults: 10
})

watch(
  () => props.templates,
  templates => {
    if (!templates.length) return
    if (!textForm.templateId) {
      textForm.templateId = templates[0].id
    }
    if (!literatureForm.templateId) {
      literatureForm.templateId = templates[0].id
    }
  },
  { immediate: true }
)

function switchTab(tab: WorkflowTab) {
  if (isLoading.value) return
  activeTab.value = tab
  errorMessage.value = ''
}

function formatDate(value: string) {
  return new Date(value).toLocaleString()
}

async function submitText() {
  if (!textForm.text.trim()) return
  await runWithLoading(async () => {
    const triplets = await extractKnowledgeFromText({
      text: textForm.text.trim(),
      templateId: textForm.templateId || undefined,
      source: textForm.source || undefined
    })
    emit('result', { mode: 'text', triplets })
    setStatus('text', triplets.length)
  })
}

async function submitLiterature() {
  if (!literatureForm.query.trim()) return
  await runWithLoading(async () => {
    const result = await extractKnowledgeFromLiterature({
      query: literatureForm.query.trim(),
      templateId: literatureForm.templateId || undefined,
      maxResults: literatureForm.maxResults
    })
    emit('result', { mode: 'literature', literature: result })
    setStatus('literature', result.triplets.length)
  })
}

async function runWithLoading(task: () => Promise<void>) {
  errorMessage.value = ''
  isLoading.value = true
  try {
    await task()
  } catch (err: any) {
    const message = err?.message || t('common.loadError')
    errorMessage.value = message
    emit('error', message)
    if (window.showMessage) {
      window.showMessage.error(message)
    }
  } finally {
    isLoading.value = false
  }
}

function setStatus(mode: WorkflowTab, count: number) {
  if (count > 0) {
    statusLabel.value = t('knowledge.workflow.statusCompleted', { count })
  } else {
    statusLabel.value = t('knowledge.workflow.statusNoResult')
  }
  lastRun.value = new Date().toISOString()
}
</script>

<style scoped>
.workflow-panel {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.workflow-tabs {
  display: flex;
  gap: var(--spacing-xs);
}

.workflow-tab {
  flex: 1;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: transparent;
  padding: 8px 12px;
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  font-size: 13px;
  cursor: pointer;
  transition: 0.2s ease;
}

.workflow-tab.active {
  background: var(--accent-primary);
  color: #fff;
  border-color: var(--accent-primary);
}

.workflow-form {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.workflow-status {
  font-size: 13px;
  color: rgba(0, 0, 0, 0.65);
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.workflow-error {
  color: #ff4d4f;
  font-size: 13px;
  margin: 0;
}
</style>
