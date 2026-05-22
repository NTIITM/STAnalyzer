import { storeToRefs } from 'pinia'
import {
  computed,
  getCurrentInstance,
  onBeforeUnmount,
  unref,
  watch,
  type ComputedRef,
  type Ref
} from 'vue'
import type {
  CodegenConversationContinuePayload,
  CodegenConversationStartPayload,
  CodegenExecutePayload,
  CodegenExecution,
  CodegenTemplateListParams
} from '../../types/codegen'
import {
  useCodegenWorkflowStore,
  type LifecycleAction
} from '../../stores/codegenWorkflowStore'
import { useExecutionPolling } from './useExecutionPolling'

type MaybeRef<T> = T | Ref<T> | ComputedRef<T>

export interface UseCodegenWorkflowOptions {
  autoFetch?: boolean
  projectId?: MaybeRef<string | null | undefined>
  serviceId?: MaybeRef<string | null | undefined>
  templateListParams?: Pick<CodegenTemplateListParams, 'skip' | 'limit' | 'status'>
  pollingIntervalMs?: number
}

export interface StartWorkflowConversationPayload extends CodegenConversationStartPayload {
  draftMessage?: string
}

export function useCodegenWorkflow(options: UseCodegenWorkflowOptions = {}) {
  const store = useCodegenWorkflowStore()
  const {
    templates,
    templatesTotal,
    templatesLoading,
    templatesLoaded,
    templatesError,
    currentTemplate,
    currentConversation,
    currentExecutions,
    selectedTemplateId,
    conversationDrafts,
    conversationLoading,
    conversationError,
    startingConversation,
    continuingConversation,
    executionsLoading,
    executionsTotals,
    executionsError,
    hasPendingExecution,
    hasSuccessfulExecution,
    canConfirm,
    canGenerateCode,
    canExecute,
    canFinalize,
    updatingTemplate,
    confirmingTemplate,
    generatingCode,
    executingTemplate,
    finalizingTemplate,
    lastError
  } = storeToRefs(store)

  const resolvedProjectId = computed<string | null>(() => {
    const value = options.projectId !== undefined ? unref(options.projectId) : undefined
    if (value === undefined || value === null || value === '') {
      return null
    }
    return value
  })

  const resolvedServiceId = computed<string | null>(() => {
    const value = options.serviceId !== undefined ? unref(options.serviceId) : undefined
    if (value === undefined || value === null || value === '') {
      return null
    }
    return value
  })

  const listParams = computed<CodegenTemplateListParams>(() => ({
    skip: options.templateListParams?.skip,
    limit: options.templateListParams?.limit,
    status: options.templateListParams?.status,
    projectId: resolvedProjectId.value ?? undefined,
    serviceId: resolvedServiceId.value ?? undefined
  }))

  const isBusy = computed(
    () =>
      templatesLoading.value ||
      conversationLoading.value ||
      executionsLoading.value ||
      updatingTemplate.value ||
      startingConversation.value ||
      continuingConversation.value ||
      confirmingTemplate.value ||
      generatingCode.value ||
      executingTemplate.value ||
      finalizingTemplate.value
  )

  const workflowError = computed(() => lastError.value ?? templatesError.value ?? conversationError.value ?? executionsError.value)

  const autoFetch = options.autoFetch !== false
  const pollingInterval = options.pollingIntervalMs ?? 3000

  // Use the new execution polling composable for per-execution tracking
  const executionPolling = useExecutionPolling(selectedTemplateId, {
    pollingIntervalMs: pollingInterval,
    autoStart: true,
    pollDetails: true
  })

  /**
   * Show error toast notification
   */
  function showErrorToast(message: string): void {
    if (typeof window !== 'undefined' && window.showMessage) {
      window.showMessage.error(message)
    } else {
      console.error('Codegen error:', message)
    }
  }

  /**
   * Show success toast notification
   */
  function showSuccessToast(message: string): void {
    if (typeof window !== 'undefined' && window.showMessage) {
      window.showMessage.success(message)
    }
  }

  /**
   * Handle errors with toast notifications
   */
  async function handleError(error: unknown, fallbackMessage: string): Promise<void> {
    const message =
      (error as { message?: string })?.message ??
      (error as { toString?: () => string })?.toString?.() ??
      fallbackMessage
    showErrorToast(message)
    throw error
  }

  async function initialize(force = false): Promise<void> {
    if (!force && templatesLoaded.value) {
      return
    }
    await store.fetchTemplates(listParams.value)
  }

  async function refreshTemplates(): Promise<void> {
    await store.fetchTemplates(listParams.value)
  }

  async function selectTemplate(templateId: string): Promise<void> {
    await store.loadTemplate(templateId, {
      fetchConversation: true,
      fetchExecutions: true
    })
  }

  async function startNewTemplateConversation(
    payload: StartWorkflowConversationPayload
  ) {
    try {
      const startPayload: StartWorkflowConversationPayload = {
        ...payload,
        project_id: payload.project_id ?? payload.projectId ?? resolvedProjectId.value ?? undefined,
        service_id: payload.service_id ?? resolvedServiceId.value ?? undefined
      }
      const response = await store.startConversation(startPayload)
      await store.fetchConversation(response.template.template_id, { force: true })
      await store.fetchExecutions(response.template.template_id, { force: true })
      // Start polling for any pending executions
      executionPolling.startPollingAll()
      return response
    } catch (error) {
      await handleError(error, '启动会话失败')
      throw error
    }
  }

  async function sendConversationMessage(payload: CodegenConversationContinuePayload) {
    const templateId = selectedTemplateId.value
    if (!templateId) {
      const error = new Error('请先选择模板')
      await handleError(error, '请先选择模板')
      throw error
    }

    try {
      const response = await store.continueConversation(templateId, payload)
      await store.fetchConversation(templateId, { force: true })
      return response
    } catch (error) {
      await handleError(error, '发送消息失败')
      throw error
    }
  }

  async function updateTemplateDraft(
    templateId: string,
    payload: Parameters<typeof store.updateTemplate>[1]
  ) {
    return store.updateTemplate(templateId, payload)
  }

  async function runLifecycleAction(
    action: LifecycleAction,
    executePayload?: CodegenExecutePayload
  ) {
    try {
      const result = await store.performLifecycleAction(
        action,
        selectedTemplateId.value ?? undefined,
        executePayload
      )

      // If execution was triggered, start polling
      if (action === 'execute') {
        executionPolling.startPollingAll()
        showSuccessToast('执行已启动，正在监控进度...')
      } else {
        // Show success messages for other actions
        const actionMessages: Record<LifecycleAction, string> = {
          confirm: '模板已确认',
          generateCode: '代码生成已启动',
          execute: '执行已启动',
          finalize: '模板已归档'
        }
        showSuccessToast(actionMessages[action])
      }

      return result
    } catch (error) {
      await handleError(error, '操作失败')
      throw error
    }
  }

  async function fetchExecutionDetail(
    executionId: string,
    options: { force?: boolean } = {}
  ): Promise<CodegenExecution> {
    return store.fetchExecutionDetail(executionId, options)
  }

  function setConversationDraft(value: string) {
    const templateId = selectedTemplateId.value
    if (!templateId) {
      return
    }
    store.setConversationDraft(templateId, value)
  }

  function clearError() {
    store.clearError()
  }

  /**
   * @deprecated Use executionPolling methods instead
   */
  function stopExecutionPolling() {
    executionPolling.stopAllPolling()
  }

  /**
   * @deprecated Use executionPolling.refreshExecutions() instead
   */
  async function pollExecutionsOnce(templateId?: string) {
    const targetTemplateId = templateId ?? selectedTemplateId.value
    if (!targetTemplateId) {
      return
    }
    try {
      await executionPolling.refreshExecutions()
    } catch (error) {
      await handleError(error, '刷新执行记录失败')
    }
  }

  /**
   * @deprecated Use executionPolling.startPollingAll() instead
   */
  function startExecutionPolling() {
    executionPolling.startPollingAll()
  }

  /**
   * Manually refresh executions (with error handling)
   */
  async function refreshExecutions(): Promise<void> {
    try {
      await executionPolling.refreshExecutions()
    } catch (error) {
      await handleError(error, '刷新执行记录失败')
      throw error
    }
  }

  /**
   * Manually refresh a specific execution (with error handling)
   */
  async function refreshExecution(executionId: string): Promise<void> {
    try {
      await executionPolling.refreshExecution(executionId)
    } catch (error) {
      await handleError(error, '刷新执行详情失败')
      throw error
    }
  }

  watch(
    () => [resolvedProjectId.value, resolvedServiceId.value],
    () => {
      if (!autoFetch) {
        return
      }
      void store.fetchTemplates(listParams.value)
    },
    { immediate: autoFetch }
  )

  watch(
    () => selectedTemplateId.value,
    (templateId) => {
      if (!templateId) {
        executionPolling.stopAllPolling()
        return
      }
      void store.fetchConversation(templateId)
      void store.fetchExecutions(templateId)
      // Polling will start automatically via useExecutionPolling watchers
    },
    { immediate: true }
  )

  // Watch for errors and surface them
  watch(
    workflowError,
    (error) => {
      if (error) {
        showErrorToast(error)
      }
    }
  )

  if (getCurrentInstance()) {
    onBeforeUnmount(() => {
      executionPolling.stopAllPolling()
    })
  }

  return {
    store,
    templates,
    templatesTotal,
    templatesLoading,
    templatesError,
    templatesLoaded,
    currentTemplate,
    currentConversation,
    currentExecutions,
    conversationDrafts,
    conversationLoading,
    conversationError,
    executionsLoading,
    executionsTotals,
    executionsError,
    hasPendingExecution,
    hasSuccessfulExecution,
    canConfirm,
    canGenerateCode,
    canExecute,
    canFinalize,
    updatingTemplate,
    confirmingTemplate,
    generatingCode,
    executingTemplate,
    finalizingTemplate,
    workflowError,
    isBusy,
    initialize,
    refreshTemplates,
    selectTemplate,
    startNewTemplateConversation,
    sendConversationMessage,
    updateTemplateDraft,
    runLifecycleAction,
    fetchExecutionDetail,
    // Execution polling
    executionPolling,
    refreshExecutions,
    refreshExecution,
    // Deprecated polling methods (kept for backward compatibility)
    startExecutionPolling,
    stopExecutionPolling,
    pollExecutionsOnce,
    // Utilities
    setConversationDraft,
    clearError,
    showErrorToast,
    showSuccessToast,
    resolvedProjectId,
    resolvedServiceId
  }
}

