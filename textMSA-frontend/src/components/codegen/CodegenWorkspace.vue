<template>
  <div class="codegen-workspace">
    <div class="left-pane">
      <div class="pane-header">
        <div class="title">{{ t('codegen.templates.title') }}</div>
        <button class="button button-secondary" @click="refreshTemplates" :disabled="loading.templates">{{ t('common.refresh') }}</button>
      </div>
      <div class="template-list">
        <div 
          v-for="tpl in templates" 
          :key="tpl.template_id" 
          class="template-item"
          :class="{ active: tpl.template_id === currentTemplateId }"
          @click="selectTemplate(tpl.template_id)"
        >
          <div class="template-name">{{ tpl.user_requirement || t('codegen.templates.unnamed') }}</div>
          <div class="template-meta">
            <span>{{ tpl.code_language?.toUpperCase() || 'LANG' }}</span>
            <span class="dot">·</span>
            <span>{{ tpl.status }}</span>
          </div>
          <div class="template-actions">
            <button class="action" :title="t('common.edit')" @click.stop="startEditTemplate(tpl)">✎</button>
            <button class="action danger" :title="t('common.delete')" @click.stop="deleteTemplateLocally(tpl.template_id)">🗑</button>
          </div>
        </div>
        <div v-if="templates.length === 0" class="empty">{{ t('codegen.templates.empty') }}</div>
      </div>
    </div>

    <div class="center-pane">
      <div class="pane-header">
        <div class="title">{{ t('codegen.conversation.title') }}</div>
        <div class="spacer"></div>
        <button class="button button-primary" @click="handleGenerate" :disabled="loading.generate">
          {{ t('codegen.actions.generate') }}
        </button>
        <button class="button button-secondary" @click="handleConfirm" :disabled="!currentTemplateId || loading.confirm">
          {{ t('codegen.actions.confirm') }}
        </button>
        <button class="button button-secondary" @click="handleExecute" :disabled="!currentTemplateId || loading.execute">
          {{ t('codegen.actions.execute') }}
        </button>
      </div>

      <div class="chat-area">
        <div class="chat-messages">
          <div v-for="(m, idx) in messages" :key="idx" class="msg" :class="m.role">
            <div class="role">{{ m.role === 'user' ? t('app.user') : 'Agent' }}</div>
            <div class="content">{{ m.content }}</div>
          </div>
        </div>
        <div class="chat-input">
          <input v-model="draft.user_requirement" type="text" :placeholder="t('codegen.form.requirementPlaceholder')" />
          <input v-model="draft.user_question" type="text" :placeholder="t('codegen.form.questionPlaceholder')" />
          <div class="row">
            <input v-model="draft.input_file_id" type="text" :placeholder="t('codegen.form.inputFilePlaceholder')" />
            <select v-model="draft.code_language">
              <option value="python">python</option>
              <option value="r">r</option>
              <option value="julia">julia</option>
              <option value="bash">bash</option>
            </select>
            <input v-model="draft.conda_env" type="text" :placeholder="t('codegen.form.envPlaceholder')" />
          </div>
          <textarea v-model="paramsText" rows="4" :placeholder="t('codegen.form.paramsPlaceholder')"></textarea>
          <div class="actions">
            <button class="button button-primary" @click="handleGenerate" :disabled="loading.generate">{{ t('codegen.actions.submit') }}</button>
          </div>
        </div>
      </div>
    </div>

    <div class="right-pane">
      <div class="pane-header">
        <div class="title">{{ t('codegen.preview.title') }}</div>
      </div>
      <div class="preview">
        <div class="section">
          <div class="section-title">{{ t('codegen.preview.code') }}</div>
          <textarea v-model="editableCode" class="code-editor" spellcheck="false"></textarea>
          <div class="section-actions">
            <button class="button button-secondary" @click="saveCodeEdit" :disabled="!currentTemplateId || loading.update">{{ t('codegen.actions.saveEdit') }}</button>
          </div>
        </div>
        <div class="section">
          <div class="section-title">{{ t('codegen.preview.metadata') }}</div>
          <pre class="json-preview">{{ metaPreview }}</pre>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
import { listTemplates, startConversation, continueConversation, confirmTemplate, executeTemplate, updateTemplate, getTemplate, type CodegenTemplate } from '../../api/codegen'

const route = useRoute()

const serviceId = ref<string | null>(null)
const projectId = ref<string | null>(null)

const templates = ref<CodegenTemplate[]>([])
const currentTemplateId = ref<string | null>(null)
const editableCode = ref<string>('')

const messages = ref<{ role: 'user' | 'agent', content: string }[]>([])

const draft = ref({
  user_requirement: '',
  user_question: '',
  input_file_id: '',
  code_language: 'python',
  conda_env: 'LG'
})
const paramsText = ref<string>('{}')

const loading = ref({
  templates: false,
  generate: false,
  update: false,
  confirm: false,
  execute: false
})

const currentTemplate = computed(() => templates.value.find(t => t.template_id === currentTemplateId.value) || null)
const metaPreview = computed(() => {
  const t = currentTemplate.value
  if (!t) return '未选择模板'
  return JSON.stringify({
    parameter_template: t.parameter_template,
    parameter_schema: t.parameter_schema,
    output_config: t.output_config,
    status: t.status
  }, null, 2)
})

function pushMsg(role: 'user' | 'agent', content: string) {
  messages.value.push({ role, content })
}

async function refreshTemplates() {
  try {
    loading.value.templates = true
    const list = await listTemplates(0, 100)
    templates.value = list
    if (list.length > 0 && !currentTemplateId.value) {
      selectTemplate(list[0].template_id)
    }
  } catch (e: any) {
    pushMsg('agent', `加载模板失败：${e?.message || '未知错误'}`)
  } finally {
    loading.value.templates = false
  }
}

function selectTemplate(id: string) {
  currentTemplateId.value = id
  loadTemplateCode(id)
}

async function loadTemplateCode(id: string) {
  try {
    const t = await getTemplate(id)
    editableCode.value = t.generated_code || ''
  } catch {}
}

function parseParams(): Record<string, any> {
  try {
    const obj = paramsText.value?.trim() ? JSON.parse(paramsText.value) : {}
    return obj
  } catch {
    pushMsg('agent', '参数JSON解析失败，已忽略参数。')
    return {}
  }
}

async function handleGenerate() {
  try {
    loading.value.generate = true
    if (!draft.value.user_requirement.trim()) {
      pushMsg('agent', '请填写需求描述。')
      return
    }
    messages.value = []
    pushMsg('user', draft.value.user_requirement)

    const startResponse = await startConversation({
      user_requirement: draft.value.user_requirement,
      project_id: projectId.value || undefined,
      service_id: serviceId.value || undefined
    })

    const template = startResponse.template
    if (startResponse.agent_message?.trim()) {
      pushMsg('agent', startResponse.agent_message)
    }
    pushMsg('agent', `已生成模板：${template.template_id}`)

    await refreshTemplates()
    currentTemplateId.value = template.template_id
    editableCode.value = template.generated_code || ''

    if (draft.value.user_question?.trim()) {
      pushMsg('user', draft.value.user_question)
      const continueResponse = await continueConversation(template.template_id, {
        message: draft.value.user_question
      })
      if (continueResponse.agent_message?.trim()) {
        pushMsg('agent', continueResponse.agent_message)
      }
      editableCode.value = continueResponse.template.generated_code || editableCode.value
      await refreshTemplates()
    }
  } catch (e: any) {
    pushMsg('agent', `生成失败：${e?.message || '未知错误'}`)
  } finally {
    loading.value.generate = false
  }
}

async function saveCodeEdit() {
  if (!currentTemplateId.value) return
  try {
    loading.value.update = true
    const updated = await updateTemplate(currentTemplateId.value, {
      generated_code: editableCode.value
    })
    pushMsg('agent', `模板已更新：${updated.template_id}`)
    await refreshTemplates()
  } catch (e: any) {
    pushMsg('agent', `保存失败：${e?.message || '未知错误'}`)
  } finally {
    loading.value.update = false
  }
}

async function handleConfirm() {
  if (!currentTemplateId.value) return
  try {
    loading.value.confirm = true
    await confirmTemplate(currentTemplateId.value)
    pushMsg('agent', '模板已确认')
    await refreshTemplates()
  } catch (e: any) {
    pushMsg('agent', `确认失败：${e?.message || '未知错误'}`)
  } finally {
    loading.value.confirm = false
  }
}

async function handleExecute() {
  if (!currentTemplateId.value) return
  try {
    loading.value.execute = true
    const res = await executeTemplate(currentTemplateId.value, parseParams())
    pushMsg('agent', `已触发执行：${res.execution_id}（状态：${res.status}）`)
  } catch (e: any) {
    pushMsg('agent', `执行失败：${e?.message || '未知错误'}`)
  } finally {
    loading.value.execute = false
  }
}

function startEditTemplate(tpl: CodegenTemplate) {
  currentTemplateId.value = tpl.template_id
  editableCode.value = tpl.generated_code || ''
}

function deleteTemplateLocally(id: string) {
  templates.value = templates.value.filter(t => t.template_id !== id)
  if (currentTemplateId.value === id) {
    currentTemplateId.value = templates.value[0]?.template_id || null
    if (currentTemplateId.value) loadTemplateCode(currentTemplateId.value)
  }
}

onMounted(() => {
  serviceId.value = (route.query.serviceId as string) || null
  projectId.value = (route.query.projectId as string) || null
  refreshTemplates()
})
</script>

<style scoped>
.codegen-workspace {
  display: grid;
  grid-template-columns: 320px 1fr 420px;
  grid-template-rows: 1fr;
  gap: var(--spacing-lg);
  padding: var(--spacing-lg);
  height: 100%;
}
.left-pane, .center-pane, .right-pane {
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.pane-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  padding: var(--spacing-md) var(--spacing-lg);
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-secondary);
}
.pane-header .title {
  font-size: 14px;
  font-weight: 500;
}
.template-list {
  padding: var(--spacing-sm);
  overflow-y: auto;
  min-height: 0;
}
.template-item {
  background: var(--bg-tertiary);
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  padding: var(--spacing-md);
  margin-bottom: var(--spacing-sm);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}
.template-item.active {
  border-color: var(--accent-primary);
  background: rgba(24,144,255,0.08);
}
.template-name {
  flex: 1;
  font-size: 14px;
}
.template-meta {
  font-size: 12px;
  color: var(--text-secondary);
}
.template-meta .dot { margin: 0 6px; }
.template-actions .action {
  margin-left: 8px;
  border: none;
  background: transparent;
  cursor: pointer;
}
.template-actions .danger { color: #ff4d4f; }
.empty {
  padding: var(--spacing-xl);
  text-align: center;
  color: var(--text-tertiary);
}
.chat-area {
  display: grid;
  grid-template-rows: 1fr auto;
  min-height: 0;
  height: 100%;
}
.chat-messages {
  padding: var(--spacing-lg);
  overflow-y: auto;
}
.msg { 
  border: 1px solid var(--border-color);
  background: var(--bg-tertiary);
  border-radius: var(--radius-md);
  padding: var(--spacing-md);
  margin-bottom: var(--spacing-sm);
}
.msg.user { background: var(--accent-primary); color: #fff; border-color: var(--accent-hover); }
.msg .role { font-size: 12px; opacity: 0.75; margin-bottom: 4px; }
.chat-input {
  padding: var(--spacing-lg);
  border-top: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}
.chat-input input, .chat-input select, .chat-input textarea {
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  padding: 6px 10px;
  font-size: 14px;
  background: var(--bg-primary);
}
.chat-input .row {
  display: grid;
  grid-template-columns: 1fr 120px 1fr;
  gap: var(--spacing-sm);
}
.actions { display: flex; gap: var(--spacing-sm); }
.preview {
  padding: var(--spacing-md);
  overflow: auto;
}
.section { margin-bottom: var(--spacing-lg); }
.section-title { font-size: 13px; color: var(--text-secondary); margin-bottom: 6px; }
.code-editor {
  width: 100%;
  min-height: 220px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  padding: 10px;
  background: #0f172a;
  color: #e5e7eb;
}
.json-preview {
  white-space: pre-wrap;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  padding: 10px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
}
.button {
  padding: 4px 12px;
  border-radius: 6px;
  border: 1px solid var(--border-color);
  background: var(--bg-primary);
  cursor: pointer;
}
.button-primary {
  background: var(--accent-primary);
  border-color: var(--accent-primary);
  color: #fff;
}
.button-secondary:hover, .button-primary:hover {
  filter: brightness(1.02);
}
</style>

