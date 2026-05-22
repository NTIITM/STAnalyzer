<template>
  <div class="knowledge-workspace">
    <div class="page-header">
      <div class="page-header-left">
        <div>
          <h1>{{ $t('knowledge.title') }}</h1>
          <p class="header-subtitle">{{ $t('knowledge.subtitle') }}</p>
        </div>
      </div>
      <div class="page-header-right">
        <button class="button button-secondary" @click="openPromptCenter">
          <Icon name="sparkles" size="sm" />
          <span>{{ $t('knowledge.actions.promptCenter') }}</span>
        </button>
        <button class="button button-primary" @click="openCreateModal">
          <Icon name="plus" size="sm" />
          <span>{{ $t('knowledge.actions.add') }}</span>
        </button>
      </div>
    </div>

    <div class="scope-tabs">
      <button
        v-for="scope in scopeOptions"
        :key="scope.value"
        class="scope-tab"
        :class="{ active: activeScope === scope.value }"
        @click="switchScope(scope.value)"
      >
        <Icon :name="scope.icon" size="sm" />
        <span>{{ scope.label }}</span>
        <span class="tab-count">{{ scope.count }}</span>
      </button>
      <div class="scope-filters">
        <label class="filter-item">
          <input type="checkbox" :checked="showEditedOnly" @change="toggleShowEditedOnly" />
          <span>{{ $t('knowledge.filters.onlyEdited') }}</span>
        </label>
        <button class="button button-secondary" @click="toggleSort">
          <Icon name="sort" size="sm" />
          <span>
            {{ currentSort === 'latest' ? $t('knowledge.filters.sortRecent') : $t('knowledge.filters.sortOldest') }}
          </span>
        </button>
      </div>
    </div>

    <div class="knowledge-layout">
      <div class="knowledge-main">
        <KnowledgeList
          :items="filteredKnowledge"
          :show-edited-only="showEditedOnly"
          :highlighted-id="highlightedId"
          @search="handleSearch"
          @toggle-edited-only="toggleShowEditedOnly"
          @sort-recent="toggleSort"
          @create="openCreateModal"
          @share="handleShare"
          @edit="openEditModal"
          @delete="handleDelete"
        />
      </div>

      <div class="knowledge-aside">
        <KnowledgeWorkflow
          :templates="promptTemplates"
          @result="handleExtractionResult"
          @error="handleWorkflowError"
        />
        <KnowledgeExtractionResults
          :mode="extractionMode"
          :triplets="extractedTriplets"
          :literature-result="literatureResult"
          :importing="isImportingTriplets"
          @import-triplets="handleImportTriplets"
          @prefill-triplet="handlePrefillTriplet"
        />
        <KnowledgeActivity :items="activityLog" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import Icon from '../common/Icon.vue'
import KnowledgeList from './KnowledgeList.vue'
import KnowledgeWorkflow from './KnowledgeWorkflow.vue'
import KnowledgeExtractionResults from './KnowledgeExtractionResults.vue'
import KnowledgeActivity from './KnowledgeActivity.vue'
import {
  createKnowledge,
  deleteKnowledge,
  getKnowledgeList,
  getKnowledgePromptTemplates,
  shareKnowledge,
  type KnowledgeRecord,
  type KnowledgeScope,
  type LiteratureExtractionResult,
  type PromptTemplate,
  type TextExtractionTriplet
} from '../../api/knowledge'

const router = useRouter()
const { t } = useI18n()

const knowledgeItems = ref<KnowledgeRecord[]>([])
const activeScope = ref<KnowledgeScope>('private')
const keyword = ref('')
const showEditedOnly = ref(false)
const highlightedId = ref<string | null>(null)
const highlightTimer = ref<number>()
const loading = ref(false)
const currentSort = ref<'latest' | 'oldest'>('latest')
const scopeCounts = ref<Record<KnowledgeScope, number>>({ private: 0, public: 0, system: 0 })

const extractionMode = ref<'text' | 'literature' | null>(null)
const extractedTriplets = ref<TextExtractionTriplet[]>([])
const literatureResult = ref<LiteratureExtractionResult | null>(null)
const isImportingTriplets = ref(false)

const promptTemplates = ref<PromptTemplate[]>([])

const activityLog = ref<Array<{ id: string; message: string; timestamp: string }>>([])

const scopeOptions = computed(() => [
  {
    value: 'private' as KnowledgeScope,
    label: t('knowledge.scopes.private'),
    icon: 'lock',
    count: scopeCounts.value.private
  },
  {
    value: 'public' as KnowledgeScope,
    label: t('knowledge.scopes.public'),
    icon: 'globe',
    count: scopeCounts.value.public
  },
  {
    value: 'system' as KnowledgeScope,
    label: t('knowledge.scopes.system'),
    icon: 'shield',
    count: scopeCounts.value.system
  }
])

const filteredKnowledge = computed(() => {
  const term = keyword.value.toLowerCase()
  if (!term) return knowledgeItems.value
  return knowledgeItems.value.filter(item => {
    const summaryText = formatRelationSummary(item).toLowerCase()
    return (
      item.title.toLowerCase().includes(term) ||
      item.description.toLowerCase().includes(term) ||
      summaryText.includes(term) ||
      (item.tags || []).some(tag => tag.toLowerCase().includes(term))
    )
  })
})

watch(activeScope, () => {
  loadKnowledge()
})

async function loadKnowledge() {
  loading.value = true
  try {
    const response = await getKnowledgeList({
      scope: activeScope.value,
      keyword: keyword.value || undefined,
      editedOnly: showEditedOnly.value || undefined,
      sort: currentSort.value
    })
    knowledgeItems.value = response.items
    scopeCounts.value = {
      ...scopeCounts.value,
      [activeScope.value]: response.total
    }
  } catch (err: any) {
    if (window.showMessage) {
      window.showMessage.error(err.message || t('common.loadError'))
    }
  } finally {
    loading.value = false
  }
}

function handleSearch(value: string) {
  keyword.value = value
  loadKnowledge()
}

function toggleShowEditedOnly() {
  showEditedOnly.value = !showEditedOnly.value
  loadKnowledge()
}

function toggleSort() {
  currentSort.value = currentSort.value === 'latest' ? 'oldest' : 'latest'
  loadKnowledge()
}

function switchScope(scope: KnowledgeScope) {
  if (activeScope.value === scope) return
  activeScope.value = scope
}

function openCreateModal() {
  router.push('/knowledge/create')
}

function openEditModal(item: KnowledgeRecord) {
  if (item.scope === 'system') {
    if (window.showMessage) window.showMessage.error(t('knowledge.messages.systemLocked'))
    return
  }
  router.push(`/knowledge/edit/${item.id}`)
}

async function handleDelete(item: KnowledgeRecord) {
  if (item.scope === 'system') {
    if (window.showMessage) window.showMessage.error(t('knowledge.messages.systemLocked'))
    return
  }
  if (!window.confirm(t('knowledge.messages.confirmDelete', { title: item.title }))) return
  try {
    await deleteKnowledge(item.id)
    pushActivity(t('knowledge.messages.activityDeleted', { title: item.title }), 'delete')
    await loadKnowledge()
    if (window.showMessage) window.showMessage.success(t('knowledge.messages.deleted'))
  } catch (err: any) {
    if (window.showMessage) window.showMessage.error(err.message || t('common.deleteError'))
  }
}

async function handleShare(item: KnowledgeRecord) {
  if (item.scope !== 'private') return
  try {
    const updated = await shareKnowledge(item.id, { visibility: 'public' })
    pushActivity(t('knowledge.messages.activityShared', { title: updated.title }), 'share')
    await loadKnowledge()
    flashCard(updated.id)
    if (window.showMessage) window.showMessage.success(t('knowledge.messages.shared'))
  } catch (err: any) {
    if (window.showMessage) window.showMessage.error(err.message || t('common.shareError'))
  }
}

function handleExtractionResult(payload: { mode: 'text' | 'literature'; triplets?: TextExtractionTriplet[]; literature?: LiteratureExtractionResult }) {
  extractionMode.value = payload.mode
  if (payload.mode === 'text') {
    extractedTriplets.value = payload.triplets || []
    literatureResult.value = null
    pushActivity(t('knowledge.messages.activityTextExtracted', { count: extractedTriplets.value.length }), 'workflow')
  } else if (payload.mode === 'literature') {
    literatureResult.value = payload.literature || null
    extractedTriplets.value = payload.literature?.triplets || []
    pushActivity(t('knowledge.messages.activityLiteratureExtracted', { count: extractedTriplets.value.length }), 'workflow')
  }
}

function handleWorkflowError(message: string) {
  pushActivity(message, 'error')
}

async function handleImportTriplets(selected: TextExtractionTriplet[]) {
  if (!selected.length) return
  isImportingTriplets.value = true
  const createdIds: string[] = []
  try {
    for (const triplet of selected) {
      try {
        const payload = buildPayloadFromTriplet(triplet)
        const created = await createKnowledge(payload)
        createdIds.push(created.id)
      } catch (err: any) {
        if (window.showMessage) window.showMessage.error(err.message || t('knowledge.messages.importSingleError'))
      }
    }
    if (createdIds.length) {
      await loadKnowledge()
      createdIds.forEach(id => flashCard(id))
      pushActivity(t('knowledge.messages.activityImported', { count: createdIds.length }), 'workflow')
      if (window.showMessage) window.showMessage.success(t('knowledge.messages.imported', { count: createdIds.length }))
    }
  } finally {
    isImportingTriplets.value = false
  }
}

function buildPayloadFromTriplet(triplet: TextExtractionTriplet) {
  const title = `${triplet.fromEntity} ${triplet.relation} ${triplet.endEntity}`.trim()
  return {
    title,
    description: triplet.description || title,
    relationSummary: {
      fromEntity: triplet.fromEntity,
      relation: triplet.relation,
      endEntity: triplet.endEntity
    },
    scope: activeScope.value === 'public' ? 'public' : 'private',
    metadata: {
      source: triplet.source || 'extraction'
    }
  }
}

const TRIPLET_PREFILL_KEY = 'knowledge_triplet_prefill'

function handlePrefillTriplet(triplet: TextExtractionTriplet) {
  const prefill = {
    title: `${triplet.fromEntity} ${triplet.relation} ${triplet.endEntity}`.trim(),
    description: triplet.description || '',
    relationSummary: {
      fromEntity: triplet.fromEntity,
      relation: triplet.relation,
      endEntity: triplet.endEntity
    },
    metadata: {
      source: triplet.source || 'extraction'
    }
  }
  sessionStorage.setItem(TRIPLET_PREFILL_KEY, JSON.stringify(prefill))
  router.push({ path: '/knowledge/create', query: { prefill: '1' } })
}

async function loadPromptTemplates() {
  try {
    promptTemplates.value = await getKnowledgePromptTemplates()
  } catch (err) {
    console.error('加载Prompt模板失败:', err)
  }
}

function openPromptCenter() {
  router.push('/knowledge/prompts')
}

function flashCard(id: string | null) {
  highlightedId.value = id
  if (highlightTimer.value) window.clearTimeout(highlightTimer.value)
  highlightTimer.value = window.setTimeout(() => {
    highlightedId.value = null
  }, 1500)
}

function pushActivity(message: string, type: string) {
  activityLog.value = [
    {
      id: `${type}-${Date.now()}`,
      message,
      timestamp: new Date().toISOString()
    },
    ...activityLog.value
  ].slice(0, 8)
}

function formatRelationSummary(item: KnowledgeRecord): string {
  if (!item.relationSummary) return ''
  const { fromEntity, relation, endEntity } = item.relationSummary
  return `${fromEntity} ${relation} ${endEntity}`.trim()
}

onMounted(async () => {
  await Promise.all([loadKnowledge(), loadPromptTemplates()])
})

onBeforeUnmount(() => {
  if (highlightTimer.value) window.clearTimeout(highlightTimer.value)
})
</script>

<style scoped>
.knowledge-workspace {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100%;
  background: var(--bg-secondary);
  overflow: hidden;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-lg) var(--spacing-xl);
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-primary);
  flex-shrink: 0;
}

.page-header-left h1 {
  margin: 0 0 4px 0;
  font-size: 20px;
  font-weight: 500;
  line-height: 1.4;
  color: rgba(0, 0, 0, 0.85);
}

.header-subtitle {
  margin: 0;
  font-size: 14px;
  color: rgba(0, 0, 0, 0.65);
}

.scope-tabs {
  display: flex;
  gap: var(--spacing-sm);
  padding: var(--spacing-md) var(--spacing-xl);
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-primary);
  flex-shrink: 0;
  flex-wrap: wrap;
  align-items: center;
}

.scope-tab {
  border: 1px solid var(--border-color);
  background: transparent;
  border-radius: 999px;
  padding: 4px 14px;
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  cursor: pointer;
  color: rgba(0, 0, 0, 0.65);
  font-size: 14px;
  transition: all 0.2s ease;
}

.scope-tab.active {
  background: #1890ff;
  color: #fff;
  border-color: #1890ff;
}

.scope-filters {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  margin-left: auto;
}

.filter-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: rgba(0, 0, 0, 0.65);
}

.tab-count {
  background: rgba(255, 255, 255, 0.2);
  padding: 0 8px;
  border-radius: 999px;
  font-size: 12px;
}

.knowledge-layout {
  flex: 1;
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(320px, 1fr);
  gap: var(--spacing-xl);
  padding: var(--spacing-xl);
  overflow: hidden;
  min-height: 0;
}

.knowledge-main {
  overflow-y: auto;
  background: var(--bg-primary);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-color);
  padding: var(--spacing-xl);
}

.knowledge-aside {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
  overflow-y: auto;
}

@media (max-width: 1200px) {
  .knowledge-layout {
    grid-template-columns: 1fr;
  }
}
</style>
