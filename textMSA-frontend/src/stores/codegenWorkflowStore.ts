import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import {
  confirmTemplate as confirmTemplateRequest,
  continueConversation as continueConversationRequest,
  executeTemplate as executeTemplateRequest,
  finalizeTemplate as finalizeTemplateRequest,
  generateCode as generateCodeRequest,
  getConversation as getConversationRequest,
  getTemplateExecution as getTemplateExecutionRequest,
  getTemplate as getTemplateRequest,
  listTemplateExecutions as listTemplateExecutionsRequest,
  listTemplates as listTemplatesRequest,
  startConversation as startConversationRequest,
  updateTemplate as updateTemplateRequest,
  type CodegenConversationContinuePayload,
  type CodegenConversationContinueResponse,
  type CodegenConversationHistoryResponse,
  type CodegenConversationStartPayload,
  type CodegenConversationStartResponse,
  type CodegenExecutePayload,
  type CodegenExecuteResponse,
  type CodegenExecution,
  type CodegenExecutionList,
  type CodegenExecutionListParams,
  type CodegenTemplate,
  type CodegenTemplateList,
  type CodegenTemplateListParams,
  type CodegenTemplateUpdatePayload
} from '../api/codegen'

type AsyncError = string | null

interface LoadTemplateOptions {
  force?: boolean
  fetchConversation?: boolean
  fetchExecutions?: boolean
}

interface FetchConversationOptions {
  force?: boolean
}

interface FetchExecutionsOptions {
  force?: boolean
}

export type LifecycleAction =
  | 'confirm'
  | 'generateCode'
  | 'execute'
  | 'finalize'

const DEFAULT_FETCH_PARAMS: Required<Pick<CodegenTemplateListParams, 'skip' | 'limit'>> = {
  skip: 0,
  limit: 50
}

export const useCodegenWorkflowStore = defineStore('codegen-workflow', () => {
  const templates = ref<CodegenTemplate[]>([])
  const templatesTotal = ref(0)
  const templatesLoading = ref(false)
  const templatesLoaded = ref(false)
  const templatesError = ref<AsyncError>(null)

  const templateMap = ref<Record<string, CodegenTemplate>>({})

  const selectedTemplateId = ref<string | null>(null)
  const templateLoading = ref(false)
  const templateError = ref<AsyncError>(null)

  const conversationByTemplate = ref<Record<string, CodegenConversationHistoryResponse['messages']>>({})
  const conversationLoading = ref(false)
  const conversationError = ref<AsyncError>(null)
  const conversationDrafts = ref<Record<string, string>>({})
  const startingConversation = ref(false)
  const continuingConversation = ref(false)

  const executionsByTemplate = ref<Record<string, CodegenExecution[]>>({})
  const executionsTotals = ref<Record<string, number>>({})
  const executionsLoading = ref(false)
  const executionsError = ref<AsyncError>(null)

  const activeExecutionId = ref<string | null>(null)
  const executionDetails = ref<Record<string, CodegenExecution>>({})
  const executionDetailLoading = ref(false)
  const executionDetailError = ref<AsyncError>(null)

  const updatingTemplate = ref(false)
  const confirmingTemplate = ref(false)
  const generatingCode = ref(false)
  const executingTemplate = ref(false)
  const finalizingTemplate = ref(false)

  const lastError = ref<AsyncError>(null)

  let fetchTemplatesPromise: Promise<void> | null = null
  const templateDetailPromises = new Map<string, Promise<CodegenTemplate>>()
  const conversationPromises = new Map<string, Promise<CodegenConversationHistoryResponse['messages']>>()
  const executionListPromises = new Map<string, Promise<CodegenExecution[]>>()
  const executionDetailPromises = new Map<string, Promise<CodegenExecution>>()
  let startConversationPromise: Promise<CodegenConversationStartResponse> | null = null
  let continueConversationPromise: Promise<CodegenConversationContinueResponse> | null = null

  const currentTemplate = computed<CodegenTemplate | null>(() => {
    const id = selectedTemplateId.value
    if (!id) {
      return null
    }
    return templateMap.value[id] ?? null
  })

  const currentConversation = computed(() => {
    const id = selectedTemplateId.value
    if (!id) {
      return []
    }
    return conversationByTemplate.value[id] ?? []
  })

  const currentExecutions = computed(() => {
    const id = selectedTemplateId.value
    if (!id) {
      return []
    }
    return executionsByTemplate.value[id] ?? []
  })

  const hasPendingExecution = computed(() =>
    currentExecutions.value.some((execution) =>
      ['pending', 'running'].includes(String(execution.status))
    )
  )

  const hasSuccessfulExecution = computed(() =>
    currentExecutions.value.some((execution) => String(execution.status) === 'completed')
  )

  const canConfirm = computed(() => currentTemplate.value?.status === 'template_generated')
  const canGenerateCode = computed(() => currentTemplate.value?.status === 'template_confirmed')
  const canExecute = computed(() => currentTemplate.value?.status === 'code_generated')
  const canFinalize = computed(() => canExecute.value && hasSuccessfulExecution.value)

  function clearError() {
    lastError.value = null
  }

  function setLastError(error: unknown, fallbackMessage: string) {
    lastError.value =
      (error as { message?: string })?.message ??
      (error as { toString?: () => string })?.toString?.() ??
      fallbackMessage
  }

  function upsertTemplate(template: CodegenTemplate) {
    const nextMap = { ...templateMap.value, [template.template_id]: template }
    templateMap.value = nextMap

    const existingIndex = templates.value.findIndex(
      (item) => item.template_id === template.template_id
    )

    if (existingIndex === -1) {
      templates.value = [template, ...templates.value]
      templatesTotal.value += 1
      return
    }

    const nextTemplates = templates.value.slice()
    nextTemplates[existingIndex] = { ...nextTemplates[existingIndex], ...template }
    templates.value = nextTemplates
  }

  function replaceTemplateList(list: CodegenTemplate[], total?: number) {
    templates.value = list
    templatesTotal.value = typeof total === 'number' ? total : list.length
    const nextMap: Record<string, CodegenTemplate> = {}
    list.forEach((item) => {
      nextMap[item.template_id] = item
    })
    templateMap.value = nextMap
  }

  function setConversation(templateId: string, messages: CodegenConversationHistoryResponse['messages']) {
    conversationByTemplate.value = {
      ...conversationByTemplate.value,
      [templateId]: messages
    }
  }

  function appendConversationMessage(
    templateId: string,
    message: CodegenConversationHistoryResponse['messages'][number]
  ) {
    const existing = conversationByTemplate.value[templateId] ?? []
    setConversation(templateId, [...existing, message])
  }

  function setExecutions(templateId: string, executions: CodegenExecution[], total?: number) {
    const sorted = executions.slice().sort((a, b) => {
      const aTime = a.created_at ? new Date(a.created_at).getTime() : 0
      const bTime = b.created_at ? new Date(b.created_at).getTime() : 0
      return bTime - aTime
    })

    executionsByTemplate.value = {
      ...executionsByTemplate.value,
      [templateId]: sorted
    }

    executionsTotals.value = {
      ...executionsTotals.value,
      [templateId]: typeof total === 'number' ? total : sorted.length
    }
  }

  function setExecutionDetail(execution: CodegenExecution) {
    executionDetails.value = {
      ...executionDetails.value,
      [execution.execution_id]: execution
    }

    // Also update the execution in the list if it exists
    const templateId = execution.template_id
    const executions = executionsByTemplate.value[templateId]
    if (executions) {
      const index = executions.findIndex((e) => e.execution_id === execution.execution_id)
      if (index !== -1) {
        const updated = executions.slice()
        updated[index] = { ...updated[index], ...execution }
        setExecutions(templateId, updated, executionsTotals.value[templateId])
      }
    }
  }

  function setConversationDraft(templateId: string, value: string) {
    conversationDrafts.value = {
      ...conversationDrafts.value,
      [templateId]: value
    }
  }

  async function fetchTemplates(params: CodegenTemplateListParams = {}): Promise<void> {
    if (templatesLoading.value && fetchTemplatesPromise) {
      return fetchTemplatesPromise
    }

    templatesLoading.value = true
    templatesError.value = null

    const request = listTemplatesRequest({
      skip: params.skip ?? DEFAULT_FETCH_PARAMS.skip,
      limit: params.limit ?? DEFAULT_FETCH_PARAMS.limit,
      projectId: params.projectId,
      serviceId: params.serviceId,
      status: params.status
    }) as Promise<CodegenTemplateList>

    fetchTemplatesPromise = request.then((response) => {
      replaceTemplateList(response.templates, response.total)
      templatesLoaded.value = true
    })

    try {
      await fetchTemplatesPromise
    } catch (error) {
      templatesError.value = (error as { message?: string })?.message ?? '加载模板列表失败'
      setLastError(error, '加载模板列表失败')
      throw error
    } finally {
      templatesLoading.value = false
      fetchTemplatesPromise = null
    }
  }

  async function loadTemplate(
    templateId: string,
    options: LoadTemplateOptions = {}
  ): Promise<CodegenTemplate> {
    if (selectedTemplateId.value !== templateId) {
      selectedTemplateId.value = templateId
    }

    const cached = templateMap.value[templateId]
    if (cached && !options.force && !templateDetailPromises.has(templateId)) {
      if (options.fetchConversation) {
        void fetchConversation(templateId)
      }
      if (options.fetchExecutions) {
        void fetchExecutions(templateId)
      }
      return cached
    }

    if (templateDetailPromises.has(templateId)) {
      const existingPromise = templateDetailPromises.get(templateId)!
      if (options.fetchConversation) {
        void fetchConversation(templateId, { force: options.force })
      }
      if (options.fetchExecutions) {
        void fetchExecutions(templateId, { force: options.force })
      }
      return existingPromise
    }

    templateLoading.value = true
    templateError.value = null

    const request = getTemplateRequest(templateId)
    templateDetailPromises.set(templateId, request)

    try {
      const detail = await request
      upsertTemplate(detail)
      if (options.fetchConversation) {
        void fetchConversation(templateId, { force: options.force })
      }
      if (options.fetchExecutions) {
        void fetchExecutions(templateId, { force: options.force })
      }
      return detail
    } catch (error) {
      templateError.value = (error as { message?: string })?.message ?? '加载模板详情失败'
      setLastError(error, '加载模板详情失败')
      throw error
    } finally {
      if (templateDetailPromises.get(templateId) === request) {
        templateDetailPromises.delete(templateId)
      }
      templateLoading.value = false
    }
  }

  async function fetchConversation(
    templateId: string,
    options: FetchConversationOptions = {}
  ): Promise<CodegenConversationHistoryResponse['messages']> {
    if (!options.force && conversationByTemplate.value[templateId] && !conversationPromises.has(templateId)) {
      return conversationByTemplate.value[templateId]
    }

    if (conversationPromises.has(templateId)) {
      return conversationPromises.get(templateId)!
    }

    conversationLoading.value = true
    conversationError.value = null

    const request = getConversationRequest(templateId).then((response) => response.messages)
    conversationPromises.set(templateId, request)

    try {
      const messages = await request
      setConversation(templateId, messages)
      return messages
    } catch (error) {
      conversationError.value =
        (error as { message?: string })?.message ?? '加载会话历史失败'
      setLastError(error, '加载会话历史失败')
      throw error
    } finally {
      if (conversationPromises.get(templateId) === request) {
        conversationPromises.delete(templateId)
      }
      conversationLoading.value = false
    }
  }

  async function startConversation(
    payload: CodegenConversationStartPayload & { draftMessage?: string }
  ): Promise<CodegenConversationStartResponse> {
    if (startingConversation.value && startConversationPromise) {
      return startConversationPromise
    }

    startingConversation.value = true
    conversationError.value = null
    lastError.value = null

    const requestPayload: CodegenConversationStartPayload = {
      user_requirement: payload.user_requirement,
      project_id: payload.project_id ?? payload.projectId,
      service_id: payload.service_id
    }

    const request = startConversationRequest(requestPayload)
    startConversationPromise = request

    try {
      const response = await request
      const { template } = response
      upsertTemplate(template)
      selectedTemplateId.value = template.template_id

      const nowIso = new Date().toISOString()
      const initialMessages = [
        {
          role: 'user' as const,
          text: payload.draftMessage ?? payload.user_requirement,
          time: nowIso,
          requires_action: false
        },
        {
          role: 'agent' as const,
          text: response.agent_message,
          time: nowIso,
          requires_action: !!response.template?.metadata?.requires_action
        }
      ]

      setConversation(template.template_id, initialMessages)
      setConversationDraft(template.template_id, '')

      return response
    } catch (error) {
      conversationError.value =
        (error as { message?: string })?.message ?? '启动会话失败'
      setLastError(error, '启动会话失败')
      throw error
    } finally {
      startingConversation.value = false
      startConversationPromise = null
    }
  }

  async function continueConversation(
    templateId: string,
    payload: CodegenConversationContinuePayload
  ): Promise<CodegenConversationContinueResponse> {
    if (continuingConversation.value && continueConversationPromise) {
      return continueConversationPromise
    }

    if (!payload.message.trim()) {
      throw new Error('消息内容不能为空')
    }

    continuingConversation.value = true
    conversationError.value = null
    lastError.value = null

    const userMessage = {
      role: 'user' as const,
      text: payload.message,
      time: new Date().toISOString(),
      requires_action: false
    }
    appendConversationMessage(templateId, userMessage)

    const request = continueConversationRequest(templateId, payload)
    continueConversationPromise = request

    try {
      const response = await request
      const agentMessage = {
        role: 'agent' as const,
        text: response.agent_message,
        time: new Date().toISOString(),
        requires_action: !!response.requires_action
      }
      appendConversationMessage(templateId, agentMessage)
      setConversationDraft(templateId, '')
      upsertTemplate(response.template)
      return response
    } catch (error) {
      conversationError.value =
        (error as { message?: string })?.message ?? '继续会话失败'
      setLastError(error, '继续会话失败')
      throw error
    } finally {
      continuingConversation.value = false
      continueConversationPromise = null
    }
  }

  async function refreshTemplate(templateId: string): Promise<CodegenTemplate> {
    return loadTemplate(templateId, { force: true })
  }

  async function updateTemplate(
    templateId: string,
    payload: CodegenTemplateUpdatePayload
  ): Promise<CodegenTemplate> {
    if (updatingTemplate.value) {
      throw new Error('已有模板更新请求进行中')
    }

    updatingTemplate.value = true
    templateError.value = null
    lastError.value = null

    try {
      const updated = await updateTemplateRequest(templateId, payload)
      upsertTemplate(updated)
      return updated
    } catch (error) {
      templateError.value =
        (error as { message?: string })?.message ?? '更新模板失败'
      setLastError(error, '更新模板失败')
      throw error
    } finally {
      updatingTemplate.value = false
    }
  }

  async function performLifecycleAction(
    action: LifecycleAction,
    templateId?: string,
    executePayload?: CodegenExecutePayload
  ): Promise<CodegenTemplate | CodegenExecuteResponse> {
    const targetTemplateId = templateId ?? selectedTemplateId.value
    if (!targetTemplateId) {
      throw new Error('未选择模板')
    }

    const template = templateMap.value[targetTemplateId]
    if (!template) {
      throw new Error('模板不存在或尚未加载')
    }

    try {
      switch (action) {
        case 'confirm': {
          if (!canConfirm.value) {
            throw new Error('模板尚未准备好确认')
          }
          if (confirmingTemplate.value) {
            throw new Error('确认操作正在进行中')
          }
          confirmingTemplate.value = true
          const confirmed = await confirmTemplateRequest(targetTemplateId)
          upsertTemplate(confirmed)
          return confirmed
        }
        case 'generateCode': {
          if (!canGenerateCode.value) {
            throw new Error('模板需要先确认才能生成代码')
          }
          if (generatingCode.value) {
            throw new Error('生成代码操作正在进行中')
          }
          generatingCode.value = true
          const generated = await generateCodeRequest(targetTemplateId)
          upsertTemplate(generated)
          return generated
        }
        case 'execute': {
          if (!canExecute.value) {
            throw new Error('模板需要先生成代码才能执行')
          }
          if (executingTemplate.value) {
            throw new Error('执行操作正在进行中')
          }
          executingTemplate.value = true
          const response = await executeTemplateRequest(targetTemplateId, executePayload ?? {})
          void fetchExecutions(targetTemplateId, { force: true })
          return response
        }
        case 'finalize': {
          if (!canFinalize.value) {
            throw new Error('需要成功执行后才能归档模板')
          }
          if (finalizingTemplate.value) {
            throw new Error('归档操作正在进行中')
          }
          finalizingTemplate.value = true
          const finalized = await finalizeTemplateRequest(targetTemplateId)
          upsertTemplate(finalized)
          return finalized
        }
        default:
          throw new Error(`未知生命周期操作: ${action satisfies never}`)
      }
    } catch (error) {
      setLastError(error, '生命周期操作失败')
      throw error
    } finally {
      if (action === 'confirm') {
        confirmingTemplate.value = false
      } else if (action === 'generateCode') {
        generatingCode.value = false
      } else if (action === 'execute') {
        executingTemplate.value = false
      } else if (action === 'finalize') {
        finalizingTemplate.value = false
      }
    }
  }

  async function fetchExecutions(
    templateId: string,
    options: FetchExecutionsOptions = {}
  ): Promise<CodegenExecution[]> {
    if (!options.force && executionsByTemplate.value[templateId] && !executionListPromises.has(templateId)) {
      return executionsByTemplate.value[templateId]
    }

    if (executionListPromises.has(templateId)) {
      return executionListPromises.get(templateId)!
    }

    executionsLoading.value = true
    executionsError.value = null

    const request = listTemplateExecutionsRequest({
      templateId,
      skip: 0,
      limit: 50
    } as CodegenExecutionListParams) as Promise<CodegenExecutionList>

    const promise = request.then((response) => {
      setExecutions(templateId, response.executions, response.total)
      return response.executions
    })

    executionListPromises.set(templateId, promise)

    try {
      return await promise
    } catch (error) {
      executionsError.value =
        (error as { message?: string })?.message ?? '加载执行记录失败'
      setLastError(error, '加载执行记录失败')
      throw error
    } finally {
      if (executionListPromises.get(templateId) === promise) {
        executionListPromises.delete(templateId)
      }
      executionsLoading.value = false
    }
  }

  async function fetchExecutionDetail(
    executionId: string,
    options: { force?: boolean } = {}
  ): Promise<CodegenExecution> {
    if (!options.force && executionDetails.value[executionId] && !executionDetailPromises.has(executionId)) {
      return executionDetails.value[executionId]
    }

    if (executionDetailPromises.has(executionId)) {
      return executionDetailPromises.get(executionId)!
    }

    executionDetailLoading.value = true
    executionDetailError.value = null

    const request = getTemplateExecutionRequest(executionId)
    executionDetailPromises.set(executionId, request)

    try {
      const detail = await request
      setExecutionDetail(detail)
      return detail
    } catch (error) {
      executionDetailError.value =
        (error as { message?: string })?.message ?? '加载执行详情失败'
      setLastError(error, '加载执行详情失败')
      throw error
    } finally {
      if (executionDetailPromises.get(executionId) === request) {
        executionDetailPromises.delete(executionId)
      }
      executionDetailLoading.value = false
    }
  }

  function setActiveExecution(executionId: string | null) {
    activeExecutionId.value = executionId
  }

  function resetStore() {
    templates.value = []
    templatesTotal.value = 0
    templatesLoaded.value = false
    templatesError.value = null
    templateMap.value = {}

    selectedTemplateId.value = null
    templateLoading.value = false
    templateError.value = null

    conversationByTemplate.value = {}
    conversationLoading.value = false
    conversationError.value = null
    conversationDrafts.value = {}
    startingConversation.value = false
    continuingConversation.value = false

    executionsByTemplate.value = {}
    executionsTotals.value = {}
    executionsLoading.value = false
    executionsError.value = null
    activeExecutionId.value = null
    executionDetails.value = {}
    executionDetailLoading.value = false
    executionDetailError.value = null

    updatingTemplate.value = false
    confirmingTemplate.value = false
    generatingCode.value = false
    executingTemplate.value = false
    finalizingTemplate.value = false

    lastError.value = null
  }

  return {
    // state
    templates,
    templatesTotal,
    templatesLoading,
    templatesLoaded,
    templatesError,
    selectedTemplateId,
    templateLoading,
    templateError,
    conversationLoading,
    conversationError,
    conversationDrafts,
    startingConversation,
    continuingConversation,
    executionsLoading,
    executionsError,
    executionsTotals,
    activeExecutionId,
    executionDetails,
    executionDetailLoading,
    executionDetailError,
    updatingTemplate,
    confirmingTemplate,
    generatingCode,
    executingTemplate,
    finalizingTemplate,
    lastError,

    // computed
    currentTemplate,
    currentConversation,
    currentExecutions,
    hasPendingExecution,
    hasSuccessfulExecution,
    canConfirm,
    canGenerateCode,
    canExecute,
    canFinalize,

    // actions
    clearError,
    setConversationDraft,
    fetchTemplates,
    loadTemplate,
    refreshTemplate,
    fetchConversation,
    startConversation,
    continueConversation,
    updateTemplate,
    performLifecycleAction,
    fetchExecutions,
    fetchExecutionDetail,
    setActiveExecution,
    resetStore
  }
})

