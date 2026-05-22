<template>
  <div class="codegen-workspace-layout" :class="{ 'has-error': workflowError }">
    <!-- Error banner -->
    <div v-if="workflowError" class="error-banner" role="alert">
      <span class="error-icon">⚠️</span>
      <span class="error-message">{{ workflowError }}</span>
      <button class="error-dismiss" @click="clearError" aria-label="Dismiss error">×</button>
    </div>

    <!-- Three-pane grid layout -->
    <div class="workspace-grid">
      <!-- Left pane: Template Sidebar -->
      <aside class="pane pane-left" aria-label="Template list">
        <div class="pane-header">
          <h2 class="pane-title">{{ t('codegen.panes.templates') }}</h2>
          <button
            class="button button-secondary"
            @click="refreshTemplates"
            :disabled="templatesLoading"
            aria-label="Refresh templates"
          >
            {{ t('common.refresh') }}
          </button>
        </div>
        <div class="pane-content">
          <TemplateSidebar
            :templates="templates"
            :loading="templatesLoading"
            :selected-template-id="selectedTemplateId"
            :error="templatesError"
            @select="handleTemplateSelect"
            @create="handleCreateTemplate"
          />
        </div>
      </aside>

      <!-- Center pane: Conversation -->
      <main class="pane pane-center" aria-label="Conversation">
        <div class="pane-header">
          <h2 class="pane-title">{{ t('codegen.panes.conversation') }}</h2>
        </div>
        <div class="pane-content">
          <ConversationPane
            :conversation="currentConversation"
            :pending-turn="startingConversation || continuingConversation"
            :draft="currentDraft"
            :loading="conversationLoading"
            :error="conversationError"
            :template-id="selectedTemplateId"
            @send="handleSendMessage"
            @update-draft="handleUpdateDraft"
          />
        </div>
      </main>

      <!-- Right pane: Template Detail -->
      <aside class="pane pane-right" aria-label="Template details">
        <div class="pane-header">
          <h2 class="pane-title">{{ t('codegen.panes.preview') }}</h2>
        </div>
        <div class="pane-content">
          <TemplateDetailPane
            :template="currentTemplate"
            :executions="currentExecutions"
            :executions-loading="executionsLoading"
            :executions-error="executionsError"
            :can-confirm="canConfirm"
            :can-generate-code="canGenerateCode"
            :can-execute="canExecute"
            :can-finalize="canFinalize"
            :confirming="confirmingTemplate"
            :generating-code="generatingCode"
            :executing="executingTemplate"
            :finalizing="finalizingTemplate"
            :is-polling="executionPolling?.isPolling?.value ?? false"
            @update="handleUpdateTemplate"
            @confirm="handleConfirm"
            @generate-code="handleGenerateCode"
            @execute="handleExecute"
            @finalize="handleFinalize"
            @open-execution="handleOpenExecution"
            @refresh-executions="handleRefreshExecutions"
          />
        </div>
      </aside>
    </div>
    
    <!-- New Template Modal -->
    <NewTemplateModal
      :visible="showNewTemplateModal"
      :project-id="projectId"
      :service-id="serviceId"
      @close="handleCloseModal"
      @submit="handleModalSubmit"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useCodegenWorkflow } from '../../modules/codegen/useCodegenWorkflow'
import { useWorkspaceRouting } from '../../modules/codegen/useWorkspaceRouting'
import TemplateSidebar from './TemplateSidebar.vue'
import ConversationPane from './ConversationPane.vue'
import TemplateDetailPane from './TemplateDetailPane.vue'
import NewTemplateModal from './NewTemplateModal.vue'
import type { CodegenExecutePayload, CodegenTemplateUpdatePayload } from '../../types/codegen'

interface Props {
  projectId?: string | null
  serviceId?: string | null
}

const props = withDefaults(defineProps<Props>(), {
  projectId: null,
  serviceId: null
})

const emit = defineEmits<{
  error: [message: string]
}>()
const { t } = useI18n()

// Initialize workflow composable with project/service context
const workflow = useCodegenWorkflow({
  projectId: computed(() => props.projectId),
  serviceId: computed(() => props.serviceId),
  autoFetch: true
})

// Initialize routing helper
const routing = useWorkspaceRouting()

// Extract reactive state from workflow
const {
  templates,
  templatesLoading,
  templatesError,
  selectedTemplateId,
  currentTemplate,
  currentConversation,
  currentExecutions,
  conversationDrafts,
  conversationLoading,
  conversationError,
  executionsLoading,
  executionsError,
  startingConversation,
  continuingConversation,
  canConfirm,
  canGenerateCode,
  canExecute,
  canFinalize,
  confirmingTemplate,
  generatingCode,
  executingTemplate,
  finalizingTemplate,
  workflowError,
  refreshTemplates,
  selectTemplate,
  startNewTemplateConversation,
  sendConversationMessage,
  updateTemplateDraft,
  runLifecycleAction,
  setConversationDraft,
  clearError,
  executionPolling,
  refreshExecutions
} = workflow

// Get current draft for selected template
const currentDraft = computed(() => {
  if (!selectedTemplateId || !selectedTemplateId.value) return ''
  const templateId = selectedTemplateId.value
  if (!conversationDrafts || !conversationDrafts.value) return ''
  return conversationDrafts.value[templateId] || ''
})

// Modal state
const showNewTemplateModal = ref(false)

// Handle template selection
async function handleTemplateSelect(templateId: string) {
  try {
    await selectTemplate(templateId)
  } catch (error: any) {
    emit('error', error?.message || t('codegen.errors.selectTemplateFailed'))
  }
}

// Handle create template - open modal
function handleCreateTemplate() {
  showNewTemplateModal.value = true
}

// Handle modal close
function handleCloseModal() {
  showNewTemplateModal.value = false
}

// Handle modal submit
async function handleModalSubmit(payload: {
  user_requirement: string
  project_id?: string
  service_id?: string
  context?: string
  output_config?: Record<string, any> | null
}) {
  try {
    const response = await startNewTemplateConversation({
      user_requirement: payload.user_requirement,
      project_id: payload.project_id,
      service_id: payload.service_id,
      context: payload.context,
      output_config: payload.output_config || undefined
    })
    
    // Select the newly created template
    if (response.template.template_id) {
      await selectTemplate(response.template.template_id)
    }
    
    // Close modal on success
    showNewTemplateModal.value = false
  } catch (error: any) {
    // Error will be handled by workflow error state
    // Keep modal open so user can retry
    console.error('Failed to create template:', error)
    emit('error', error?.message || t('codegen.errors.createTemplateFailed'))
  }
}

// Handle sending conversation message
async function handleSendMessage(message: string) {
  if (!selectedTemplateId.value) {
    emit('error', t('codegen.errors.selectTemplateFirst'))
    return
  }
  try {
    await sendConversationMessage({ message })
  } catch (error: any) {
    emit('error', error?.message || t('codegen.errors.sendFailed'))
  }
}

// Handle draft update
function handleUpdateDraft(draft: string) {
  setConversationDraft(draft)
}

// Handle template update
async function handleUpdateTemplate(payload: CodegenTemplateUpdatePayload) {
  if (!selectedTemplateId.value) {
    emit('error', t('codegen.errors.selectTemplateFirst'))
    return
  }
  try {
    await updateTemplateDraft(selectedTemplateId.value, payload)
  } catch (error: any) {
    emit('error', error?.message || t('codegen.errors.updateTemplateFailed'))
  }
}

// Handle lifecycle actions
async function handleConfirm() {
  try {
    await runLifecycleAction('confirm')
  } catch (error: any) {
    emit('error', error?.message || t('codegen.errors.confirmTemplateFailed'))
  }
}

async function handleGenerateCode() {
  try {
    await runLifecycleAction('generateCode')
  } catch (error: any) {
    emit('error', error?.message || t('codegen.errors.generateCodeFailed'))
  }
}

async function handleExecute(payload?: CodegenExecutePayload) {
  try {
    await runLifecycleAction('execute', payload)
  } catch (error: any) {
    emit('error', error?.message || t('codegen.errors.executeFailed'))
  }
}

async function handleFinalize() {
  try {
    await runLifecycleAction('finalize')
  } catch (error: any) {
    emit('error', error?.message || t('codegen.errors.finalizeFailed'))
  }
}

// Handle opening execution detail
function handleOpenExecution(executionId: string) {
  // TODO: Open ExecutionDrawer
  console.log('Open execution:', executionId)
}

// Handle manual refresh of executions
async function handleRefreshExecutions() {
  try {
    await refreshExecutions()
  } catch (error: any) {
    emit('error', error?.message || t('codegen.errors.refreshExecutionsFailed'))
  }
}

// Initialize from query params on mount
onMounted(() => {
  routing.initializeFromQuery()
})

// Watch for errors and emit upward
watch(workflowError, (error) => {
  if (error) {
    emit('error', error)
  }
})
</script>

<style scoped>
.codegen-workspace-layout {
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
  overflow: hidden;
}

.error-banner {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-md) var(--spacing-lg);
  background: #fff3cd;
  border-bottom: 1px solid #ffc107;
  color: #856404;
  font-size: 14px;
}

.error-icon {
  font-size: 16px;
}

.error-message {
  flex: 1;
}

.error-dismiss {
  background: transparent;
  border: none;
  font-size: 20px;
  line-height: 1;
  cursor: pointer;
  color: #856404;
  padding: 0;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.error-dismiss:hover {
  background: rgba(0, 0, 0, 0.1);
  border-radius: 4px;
}

.workspace-grid {
  display: grid;
  grid-template-columns: 320px 1fr 420px;
  grid-template-rows: 1fr;
  gap: var(--spacing-lg);
  padding: var(--spacing-lg);
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

/* Responsive breakpoints */
@media (max-width: 1400px) {
  .workspace-grid {
    grid-template-columns: 280px 1fr 380px;
  }
}

@media (max-width: 1200px) {
  .workspace-grid {
    grid-template-columns: 240px 1fr 320px;
  }
}

@media (max-width: 1024px) {
  .workspace-grid {
    grid-template-columns: 1fr;
    grid-template-rows: auto auto auto;
  }
  
  .pane {
    max-height: 50vh;
  }
}

.pane {
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
  justify-content: space-between;
  gap: var(--spacing-md);
  padding: var(--spacing-md) var(--spacing-lg);
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-secondary);
  flex-shrink: 0;
}

.pane-title {
  font-size: 14px;
  font-weight: 500;
  margin: 0;
  color: var(--text-primary);
}

.pane-content {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.button {
  padding: 4px 12px;
  border-radius: 6px;
  border: 1px solid var(--border-color);
  background: var(--bg-primary);
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s;
}

.button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.button-secondary:hover:not(:disabled) {
  filter: brightness(1.02);
  background: var(--bg-tertiary);
}

.button-primary {
  background: var(--accent-primary);
  border-color: var(--accent-primary);
  color: #fff;
}

.button-primary:hover:not(:disabled) {
  filter: brightness(1.05);
}
</style>
