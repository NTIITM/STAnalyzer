<template>
  <section class="prompt-config-card">
    <div class="prompt-header">
      <div>
        <p class="panel-eyebrow">{{ $t('knowledge.prompt.badge') }}</p>
        <h4>{{ $t('knowledge.prompt.title') }}</h4>
        <p class="prompt-subtitle">{{ $t('knowledge.prompt.subtitle') }}</p>
      </div>
      <div class="prompt-actions">
        <el-select 
          v-model="localConfig.templateId" 
          @change="handleTemplateChange"
          :placeholder="$t('knowledge.prompt.selectTemplate')"
        >
          <el-option 
            v-for="tpl in templates" 
            :key="tpl.id" 
            :label="tpl.label"
            :value="tpl.id"
          />
        </el-select>
        <el-button @click="handleReset">
          <Icon name="refresh" size="sm" />
          <span>{{ $t('knowledge.prompt.reset') }}</span>
        </el-button>
        <el-button type="danger" @click="handleDelete" :disabled="!localConfig.templateId">
          <Icon name="delete" size="sm" />
          <span>{{ $t('knowledge.prompt.delete') }}</span>
        </el-button>
        <el-button type="primary" @click="handleSave" :disabled="!dirty">
          <Icon name="save" size="sm" />
          <span>{{ $t('knowledge.prompt.save') }}</span>
        </el-button>
      </div>
    </div>
    <div class="prompt-grid">
      <label class="form-group">
        <span>{{ $t('knowledge.prompt.entityLabel') }}</span>
        <textarea
          v-model="localConfig.entityText"
          rows="6"
          class="form-textarea"
          :placeholder="$t('knowledge.prompt.entityPlaceholder')"
        />
        <small>{{ $t('knowledge.prompt.textHint') }}</small>
      </label>
      <label class="form-group">
        <span>{{ $t('knowledge.prompt.relationLabel') }}</span>
        <textarea
          v-model="localConfig.relationText"
          rows="6"
          class="form-textarea"
          :placeholder="$t('knowledge.prompt.relationPlaceholder')"
        />
        <small>{{ $t('knowledge.prompt.textHint') }}</small>
      </label>
    </div>
    <div class="prompt-footer">
      <p v-if="savedAt">
        {{ $t('knowledge.prompt.lastSaved', { time: formatDate(savedAt) }) }}
      </p>
      <p v-else class="prompt-hint">
        {{ $t('knowledge.prompt.hint') }}
      </p>
      <span v-if="dirty" class="unsaved-dot">{{ $t('knowledge.prompt.unsaved') }}</span>
    </div>
  </section>
</template>

<script setup lang="ts">
import { reactive, ref, watch, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import Icon from '../common/Icon.vue'
import type { PromptConfigPayload, PromptTemplate } from '../../api/knowledge'

const { t } = useI18n()

const props = defineProps<{
  templates: PromptTemplate[]
  config: PromptConfigPayload
}>()

const emit = defineEmits<{
  'update:config': [config: PromptConfigPayload]
  save: [config: PromptConfigPayload]
  'delete-template': [templateId: string]
}>()

const localConfig = reactive({
  templateId: props.config.templateId || props.templates[0]?.id || '',
  entityText: mapToText(props.config.entityPrompt),
  relationText: mapToText(props.config.relationPrompt),
  constraints: props.config.constraints || ''
})

const dirty = ref(false)
const savedAt = ref<string | null>(props.config.updatedAt || null)
const skipSync = ref(false)

const currentTemplate = computed(() => props.templates.find(tpl => tpl.id === localConfig.templateId))

watch(
  () => props.config,
  newConfig => {
    if (skipSync.value) {
      skipSync.value = false
      return
    }
    localConfig.templateId = newConfig.templateId || props.templates[0]?.id || ''
    localConfig.entityText = mapToText(newConfig.entityPrompt)
    localConfig.relationText = mapToText(newConfig.relationPrompt)
    localConfig.constraints = newConfig.constraints || ''
    savedAt.value = newConfig.updatedAt || savedAt.value
    dirty.value = false
  },
  { deep: true }
)

watch(
  () => props.templates,
  templates => {
    if (!localConfig.templateId && templates.length) {
      localConfig.templateId = templates[0].id
    }
  }
)

watch(
  () => [localConfig.templateId, localConfig.entityText, localConfig.relationText, localConfig.constraints],
  () => {
    dirty.value = true
    skipSync.value = true
    emit('update:config', toPayload())
  }
)

function handleTemplateChange() {
  const template = props.templates.find(tpl => tpl.id === localConfig.templateId)
  if (template) {
    localConfig.entityText = mapToText(template.entityPrompt)
    localConfig.relationText = mapToText(template.relationPrompt)
    dirty.value = true
  }
}

function handleReset() {
  const template = props.templates.find(tpl => tpl.id === localConfig.templateId) || props.templates[0]
  if (template) {
    localConfig.entityText = mapToText(template.entityPrompt)
    localConfig.relationText = mapToText(template.relationPrompt)
    localConfig.constraints = template.constraints || ''
    dirty.value = true
  } else {
    localConfig.entityText = ''
    localConfig.relationText = ''
    localConfig.constraints = ''
    dirty.value = true
  }
}

function handleSave() {
  savedAt.value = new Date().toISOString()
  dirty.value = false
  emit('save', toPayload())
}

function handleDelete() {
  if (!localConfig.templateId) return
  emit('delete-template', localConfig.templateId)
}

function toPayload(): PromptConfigPayload {
  return {
    templateId: localConfig.templateId,
    name: currentTemplate.value?.name || currentTemplate.value?.label,
    description: currentTemplate.value?.description,
    entityPrompt: textToMap(localConfig.entityText),
    relationPrompt: textToMap(localConfig.relationText),
    constraints: localConfig.constraints
  }
}

function mapToText(map: Record<string, string> = {}) {
  if (!map) return ''
  return Object.entries(map)
    .map(([key, value]) => `${key}: ${value}`)
    .join('\n')
}

function textToMap(text: string) {
  const trimmed = text?.trim()
  if (!trimmed) return {}
  if (trimmed.startsWith('{')) {
    try {
      const parsed = JSON.parse(trimmed)
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
        return Object.fromEntries(
          Object.entries(parsed).map(([key, value]) => [key, String(value)])
        )
      }
    } catch (err) {
      console.warn('Prompt文本解析失败，已回退到逐行解析:', err)
    }
  }
  const map: Record<string, string> = {}
  trimmed.split('\n').forEach(line => {
    const [rawKey, ...rest] = line.split(':')
    if (!rawKey || !rest.length) return
    map[rawKey.trim()] = rest.join(':').trim()
  })
  return map
}

function formatDate(value: string) {
  if (!value) return '--'
  return new Date(value).toLocaleString()
}
</script>

<style scoped>
.prompt-config-card {
  background: var(--bg-primary);
  border-radius: var(--radius-lg);
  padding: var(--spacing-lg);
  box-shadow: var(--shadow-md);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.prompt-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--spacing-md);
  flex-wrap: wrap;
}

.panel-eyebrow {
  font-size: 12px;
  text-transform: uppercase;
  color: rgba(0, 0, 0, 0.45);
  margin: 0 0 4px 0;
}

.prompt-header h4 {
  margin: 0 0 4px 0;
  font-size: 16px;
  font-weight: 500;
  color: rgba(0, 0, 0, 0.85);
}

.prompt-subtitle {
  margin: 0;
  font-size: 14px;
  color: rgba(0, 0, 0, 0.65);
}

.prompt-actions {
  display: flex;
  gap: var(--spacing-sm);
  flex-wrap: wrap;
}

.prompt-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: var(--spacing-md);
}

.prompt-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  color: rgba(0, 0, 0, 0.65);
}

.prompt-hint {
  margin: 0;
}

.unsaved-dot {
  color: #ff4d4f;
  font-weight: 500;
}
</style>
