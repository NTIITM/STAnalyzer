<template>
  <div class="panel-card results-panel">
    <div class="panel-header">
      <div>
        <p class="panel-eyebrow">{{ $t('knowledge.results.badge') }}</p>
        <h4>{{ headerTitle }}</h4>
        <p class="panel-subtitle">{{ subtitle }}</p>
      </div>
      <div v-if="mode !== 'prompt' && displayTriplets.length" class="panel-actions">
        <button class="button button-secondary" @click="selectAll">
          {{ $t('knowledge.results.selectAll') }}
        </button>
        <button
          class="button button-primary"
          :disabled="!selectedTriplets.length || importing"
          @click="emitImport"
        >
          <Icon :name="importing ? 'loading' : 'download'" size="sm" />
          <span>{{ importing ? $t('knowledge.results.importing') : $t('knowledge.results.import') }}</span>
        </button>
      </div>
    </div>

    <div v-if="!mode" class="empty-panel">
      <Icon name="inbox" size="lg" />
      <p>{{ $t('knowledge.results.empty') }}</p>
    </div>

    <div v-else-if="mode === 'prompt'" class="prompt-panel">
      <template v-if="pendingPrompt">
        <div class="prompt-meta">
          <p><strong>{{ $t('knowledge.results.pendingId') }}:</strong> {{ pendingPrompt.pendingPromptId }}</p>
          <p><strong>{{ $t('knowledge.results.query') }}:</strong> {{ pendingPrompt.query }}</p>
          <p v-if="pendingPrompt.description"><strong>{{ $t('knowledge.results.description') }}:</strong> {{ pendingPrompt.description }}</p>
        </div>
        <div class="prompt-columns">
          <div>
            <h5>{{ $t('knowledge.results.entityPrompt') }}</h5>
            <ul>
              <li v-for="(desc, key) in pendingPrompt.entityPrompt" :key="`entity-${key}`">
                <strong>{{ key }}</strong>
                <p>{{ desc }}</p>
              </li>
            </ul>
          </div>
          <div>
            <h5>{{ $t('knowledge.results.relationPrompt') }}</h5>
            <ul>
              <li v-for="(desc, key) in pendingPrompt.relationPrompt" :key="`relation-${key}`">
                <strong>{{ key }}</strong>
                <p>{{ desc }}</p>
              </li>
            </ul>
          </div>
        </div>
        <div class="prompt-approve">
          <label class="form-group">
            <span>{{ $t('knowledge.results.templateName') }}</span>
            <input v-model="approveForm.name" type="text" class="form-input" :placeholder="$t('knowledge.results.templateNamePlaceholder')" />
          </label>
          <label class="checkbox">
            <input v-model="approveForm.isDefault" type="checkbox" />
            <span>{{ $t('knowledge.results.setDefault') }}</span>
          </label>
          <button class="button button-primary" :disabled="approving" @click="emitApprove">
            <Icon :name="approving ? 'loading' : 'check'" size="sm" />
            <span>{{ approving ? $t('knowledge.results.approving') : $t('knowledge.results.approve') }}</span>
          </button>
        </div>
      </template>
      <div v-else class="empty-panel">
        <Icon name="info" size="lg" />
        <p>{{ $t('knowledge.results.noPrompt') }}</p>
      </div>
    </div>

    <div v-else class="triplet-panel">
      <div v-if="mode === 'literature' && literatureResult" class="literature-summary">
        <p><strong>{{ $t('knowledge.results.query') }}:</strong> {{ literatureResult.query }}</p>
        <p v-if="literatureResult.expandedKeywords.length">
          <strong>{{ $t('knowledge.results.expandedKeywords') }}:</strong>
          <span v-for="keyword in literatureResult.expandedKeywords" :key="keyword" class="keyword-chip">{{ keyword }}</span>
        </p>
        <p v-if="literatureResult.summary">
          <strong>{{ $t('knowledge.results.summary') }}:</strong> {{ literatureResult.summary }}
        </p>
      </div>
      <div v-if="displayTriplets.length" class="triplet-list">
        <label
          v-for="(triplet, index) in displayTriplets"
          :key="tripletKey(triplet, index)"
          class="triplet-item"
        >
          <input
            type="checkbox"
            :value="tripletKey(triplet, index)"
            v-model="selectedKeys"
          />
          <div class="triplet-content">
            <p class="triplet-title">
              {{ triplet.fromEntity }}
              <span>{{ triplet.relation }}</span>
              {{ triplet.endEntity }}
            </p>
            <p class="triplet-desc">{{ triplet.description || $t('knowledge.results.noDescription') }}</p>
            <div class="triplet-meta">
              <span v-if="triplet.source">{{ $t('knowledge.results.source') }}: {{ triplet.source }}</span>
              <span>{{ $t('knowledge.results.confidence', { value: formatConfidence(triplet.confidence) }) }}</span>
              <button class="text-link" type="button" @click="prefill(triplet)">
                {{ $t('knowledge.results.toForm') }}
              </button>
            </div>
          </div>
        </label>
      </div>
      <div v-else class="empty-panel">
        <Icon name="info" size="lg" />
        <p>{{ $t('knowledge.results.noTriplets') }}</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import Icon from '../common/Icon.vue'
import type { PendingPrompt, LiteratureExtractionResult, TextExtractionTriplet } from '../../api/knowledge'

type ResultMode = 'text' | 'literature' | 'prompt' | null

const props = defineProps<{
  mode: ResultMode
  triplets: TextExtractionTriplet[]
  literatureResult?: LiteratureExtractionResult | null
  pendingPrompt?: PendingPrompt | null
  importing?: boolean
  approving?: boolean
}>()

const emit = defineEmits<{
  'import-triplets': [triplets: TextExtractionTriplet[]]
  'prefill-triplet': [triplet: TextExtractionTriplet]
  'approve-prompt': [payload: { name?: string; isDefault?: boolean }]
}>()

const { t } = useI18n()

const selectedKeys = ref<string[]>([])
const approveForm = reactive({
  name: '',
  isDefault: false
})

watch(
  () => props.mode,
  () => {
    selectedKeys.value = []
    approveForm.name = ''
    approveForm.isDefault = false
  }
)

watch(
  () => props.pendingPrompt,
  () => {
    approveForm.name = ''
    approveForm.isDefault = false
  }
)

const displayTriplets = computed(() => {
  if (props.mode === 'literature' && props.literatureResult) {
    return props.literatureResult.triplets || []
  }
  if (props.mode === 'text') {
    return props.triplets || []
  }
  return []
})

const selectedTriplets = computed(() => {
  return displayTriplets.value.filter((triplet, index) => selectedKeys.value.includes(tripletKey(triplet, index)))
})

const headerTitle = computed(() => {
  if (!props.mode) return t('knowledge.results.titleIdle')
  if (props.mode === 'prompt') return t('knowledge.results.titlePrompt')
  if (props.mode === 'literature') return t('knowledge.results.titleLiterature')
  return t('knowledge.results.titleText')
})

const subtitle = computed(() => {
  if (!props.mode) return t('knowledge.results.subtitleIdle')
  return t('knowledge.results.subtitleActive')
})

function tripletKey(triplet: TextExtractionTriplet, index: number) {
  return `${triplet.fromEntity}-${triplet.relation}-${triplet.endEntity}-${index}`
}

function selectAll() {
  selectedKeys.value = displayTriplets.value.map((triplet, index) => tripletKey(triplet, index))
}

function formatConfidence(value: number) {
  return `${Math.round((value || 0) * 100)}%`
}

function emitImport() {
  if (!selectedTriplets.value.length) return
  emit('import-triplets', [...selectedTriplets.value])
  selectedKeys.value = []
}

function prefill(triplet: TextExtractionTriplet) {
  emit('prefill-triplet', triplet)
}

function emitApprove() {
  if (!props.pendingPrompt) return
  emit('approve-prompt', {
    name: approveForm.name || undefined,
    isDefault: approveForm.isDefault
  })
}
</script>

<style scoped>
.results-panel {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.panel-actions {
  display: flex;
  gap: var(--spacing-sm);
}

.panel-subtitle {
  margin: 4px 0 0;
  font-size: 13px;
  color: rgba(0, 0, 0, 0.45);
}

.empty-panel {
  border: 1px dashed var(--border-color);
  border-radius: var(--radius-lg);
  padding: var(--spacing-lg);
  text-align: center;
  color: rgba(0, 0, 0, 0.45);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
  align-items: center;
}

.triplet-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
  max-height: 360px;
  overflow-y: auto;
}

.triplet-item {
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: var(--spacing-md);
  display: flex;
  gap: var(--spacing-md);
  align-items: flex-start;
}

.triplet-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.triplet-title {
  margin: 0;
  font-weight: 600;
  color: rgba(0, 0, 0, 0.85);
}

.triplet-title span {
  color: var(--accent-primary);
  font-weight: 500;
  margin: 0 6px;
}

.triplet-desc {
  margin: 0;
  font-size: 13px;
  color: rgba(0, 0, 0, 0.65);
}

.triplet-meta {
  display: flex;
  gap: var(--spacing-sm);
  flex-wrap: wrap;
  font-size: 12px;
  color: rgba(0, 0, 0, 0.45);
  align-items: center;
}

.text-link {
  border: none;
  background: none;
  color: var(--accent-primary);
  cursor: pointer;
  padding: 0;
}

.keyword-chip {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--bg-tertiary);
  margin-right: 6px;
  margin-top: 4px;
}

.prompt-panel ul {
  margin: 0;
  padding-left: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.prompt-panel li {
  font-size: 13px;
  color: rgba(0, 0, 0, 0.75);
}

.prompt-columns {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: var(--spacing-lg);
}

.prompt-approve {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.checkbox {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: rgba(0, 0, 0, 0.65);
}

.literature-summary {
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: var(--spacing-md);
  font-size: 13px;
  color: rgba(0, 0, 0, 0.75);
}
</style>
