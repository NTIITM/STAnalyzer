import { beforeEach, describe, expect, it, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

const fixtures = vi.hoisted(() => {
  const templateFixture = {
    template_id: 'tmpl-1',
    user_requirement: 'Process dataset',
    parameter_template: {},
    parameter_schema: {},
    output_config: {},
    generated_code: null,
    code_language: 'python',
    status: 'template_generated',
    service_id: 'svc-1',
    project_id: 'proj-1'
  }

  const conversationHistory = {
    template_id: templateFixture.template_id,
    messages: [
      { role: 'user', text: 'Hi', time: '2024-01-01T00:00:00Z' },
      { role: 'agent', text: 'Hello', time: '2024-01-01T00:00:01Z' }
    ]
  }

  const executionPending = {
    execution_id: 'exec-1',
    template_id: templateFixture.template_id,
    user_id: 'user-1',
    code: '# code',
    language: 'python',
    parameters: {},
    status: 'pending',
    created_at: '2024-01-01T00:00:00Z'
  }

  const executionCompleted = {
    ...executionPending,
    status: 'completed'
  }

  const confirmedTemplate = { ...templateFixture, status: 'template_confirmed' }
  const codeGeneratedTemplate = { ...templateFixture, status: 'code_generated' }
  const finalizedTemplate = { ...templateFixture, status: 'finalized' }

  return {
    templateFixture,
    conversationHistory,
    executionPending,
    executionCompleted,
    confirmedTemplate,
    codeGeneratedTemplate,
    finalizedTemplate,
    listTemplatesMock: vi.fn(async () => ({
      templates: [templateFixture],
      total: 1
    })),
    getTemplateMock: vi.fn(async () => templateFixture),
    getConversationMock: vi.fn(async () => conversationHistory),
    startConversationMock: vi.fn(async () => ({
      template_id: templateFixture.template_id,
      conversation_id: 'conv-1',
      template: templateFixture,
      agent_message: 'First response'
    })),
    continueConversationMock: vi.fn(async () => ({
      template: templateFixture,
      agent_message: 'Follow up',
      requires_action: false,
      conversation_ended: false
    })),
    listTemplateExecutionsMock: vi.fn(async () => ({
      executions: [executionPending],
      total: 1
    })),
    getTemplateExecutionMock: vi.fn(async () => executionCompleted),
    executeTemplateMock: vi.fn(async () => ({
      execution_id: executionPending.execution_id,
      template_id: templateFixture.template_id,
      status: 'pending',
      created_at: '2024-01-01T00:00:00Z'
    })),
    confirmTemplateMock: vi.fn(async () => confirmedTemplate),
    generateCodeMock: vi.fn(async () => codeGeneratedTemplate),
    finalizeTemplateMock: vi.fn(async () => finalizedTemplate),
    updateTemplateMock: vi.fn(async () => ({
      ...templateFixture,
      generated_code: '# updated'
    }))
  }
})

const {
  templateFixture,
  conversationHistory,
  executionPending,
  executionCompleted,
  confirmedTemplate,
  codeGeneratedTemplate,
  finalizedTemplate,
  listTemplatesMock,
  getTemplateMock,
  getConversationMock,
  startConversationMock,
  continueConversationMock,
  listTemplateExecutionsMock,
  getTemplateExecutionMock,
  executeTemplateMock,
  confirmTemplateMock,
  generateCodeMock,
  finalizeTemplateMock,
  updateTemplateMock
} = fixtures

let useCodegenWorkflowStore: typeof import('../../../src/stores/codegenWorkflowStore').useCodegenWorkflowStore

vi.mock('../../../src/api/codegen', () => ({
  listTemplates: listTemplatesMock,
  getTemplate: getTemplateMock,
  getConversation: getConversationMock,
  startConversation: startConversationMock,
  continueConversation: continueConversationMock,
  listTemplateExecutions: listTemplateExecutionsMock,
  getTemplateExecution: getTemplateExecutionMock,
  executeTemplate: executeTemplateMock,
  confirmTemplate: confirmTemplateMock,
  generateCode: generateCodeMock,
  finalizeTemplate: finalizeTemplateMock,
  updateTemplate: updateTemplateMock
}))

describe('codegenWorkflowStore', () => {
  beforeEach(async () => {
    vi.resetModules()
    vi.clearAllMocks()
    const storeModule = await import('../../../src/stores/codegenWorkflowStore')
    useCodegenWorkflowStore = storeModule.useCodegenWorkflowStore
    setActivePinia(createPinia())
  })

  it('fetchTemplates populates state and avoids duplicate requests while loading', async () => {
    const store = useCodegenWorkflowStore()
    const promiseA = store.fetchTemplates()
    const promiseB = store.fetchTemplates()

    expect(listTemplatesMock).toHaveBeenCalledTimes(1)

    await Promise.all([promiseA, promiseB])

    expect(store.templates).toHaveLength(1)
    expect(store.templatesTotal).toBe(1)
    expect(store.templates[0]).toMatchObject({ template_id: templateFixture.template_id })
  })

  it('startConversation selects template, seeds messages, and clears draft', async () => {
    const store = useCodegenWorkflowStore()
    await store.startConversation({ user_requirement: 'Process dataset', service_id: 'svc-1' })

    expect(startConversationMock).toHaveBeenCalledTimes(1)
    expect(store.selectedTemplateId).toBe(templateFixture.template_id)
    expect(store.currentConversation.length).toBeGreaterThanOrEqual(2)
    expect(store.conversationDrafts[templateFixture.template_id]).toBe('')
  })

  it('continueConversation rejects empty messages', async () => {
    const store = useCodegenWorkflowStore()
    await store.startConversation({ user_requirement: 'Process dataset', service_id: 'svc-1' })

    await expect(
      store.continueConversation(templateFixture.template_id, { message: '   ' })
    ).rejects.toThrow('消息内容不能为空')
  })

  it('performLifecycleAction enforces sequencing', async () => {
    const store = useCodegenWorkflowStore()
    await store.startConversation({ user_requirement: 'Process dataset', service_id: 'svc-1' })

    await store.performLifecycleAction('confirm')
    expect(confirmTemplateMock).toHaveBeenCalledWith(templateFixture.template_id)

    await store.performLifecycleAction('generateCode')
    expect(generateCodeMock).toHaveBeenCalledWith(templateFixture.template_id)

    await store.performLifecycleAction('execute')
    expect(executeTemplateMock).toHaveBeenCalledWith(templateFixture.template_id, {})

    // Simulate successful execution to allow finalize
    await store.fetchExecutions(templateFixture.template_id, { force: true })
    listTemplateExecutionsMock.mockResolvedValueOnce({
      executions: [executionCompleted],
      total: 1
    })
    await store.fetchExecutions(templateFixture.template_id, { force: true })

    await store.performLifecycleAction('finalize')
    expect(finalizeTemplateMock).toHaveBeenCalledWith(templateFixture.template_id)
  })

  it('fetchExecutionDetail caches results', async () => {
    const store = useCodegenWorkflowStore()
    const first = await store.fetchExecutionDetail(executionPending.execution_id, { force: true })
    expect(first.execution_id).toBe(executionPending.execution_id)
    expect(getTemplateExecutionMock).toHaveBeenCalledTimes(1)

    const second = await store.fetchExecutionDetail(executionPending.execution_id)
    expect(second).toEqual(first)
    expect(getTemplateExecutionMock).toHaveBeenCalledTimes(1)
  })
})

