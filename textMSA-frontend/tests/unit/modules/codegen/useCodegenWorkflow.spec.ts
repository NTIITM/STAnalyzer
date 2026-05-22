import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { nextTick } from 'vue'

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

  return {
    templateFixture,
    conversationHistory,
    executionPending,
    executionCompleted,
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
    listTemplateExecutionsMock: vi
      .fn()
      .mockImplementation(async () => ({
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
    confirmTemplateMock: vi.fn(async () => ({ ...templateFixture, status: 'template_confirmed' })),
    generateCodeMock: vi.fn(async () => ({ ...templateFixture, status: 'code_generated' })),
    finalizeTemplateMock: vi.fn(async () => ({ ...templateFixture, status: 'finalized' })),
    updateTemplateMock: vi.fn(async () => ({ ...templateFixture, generated_code: '# updated' }))
  }
})

const {
  templateFixture,
  conversationHistory,
  executionPending,
  executionCompleted,
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

let useCodegenWorkflow: typeof import('../../../../src/modules/codegen/useCodegenWorkflow').useCodegenWorkflow
let useCodegenWorkflowStore: typeof import('../../../../src/stores/codegenWorkflowStore').useCodegenWorkflowStore

vi.mock('../../../../src/api/codegen', () => ({
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

describe('useCodegenWorkflow composable', () => {
  beforeEach(async () => {
    vi.resetModules()
    vi.useFakeTimers()
    vi.clearAllMocks()
    const storeModule = await import('../../../../src/stores/codegenWorkflowStore')
    const composableModule = await import('../../../../src/modules/codegen/useCodegenWorkflow')
    useCodegenWorkflowStore = storeModule.useCodegenWorkflowStore
    useCodegenWorkflow = composableModule.useCodegenWorkflow
    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('automatically fetches templates when autoFetch is enabled', async () => {
    useCodegenWorkflow({ projectId: 'proj-1', serviceId: 'svc-1' })

    await vi.waitFor(() => expect(listTemplatesMock).toHaveBeenCalled())

    const params = listTemplatesMock.mock.calls.at(-1)?.[0]
    expect(params.projectId).toBe('proj-1')
    expect(params.serviceId).toBe('svc-1')
  })

  it('startNewTemplateConversation hydrates conversation and executions', async () => {
    const workflow = useCodegenWorkflow({ autoFetch: false, projectId: 'proj-1', serviceId: 'svc-1' })
    const store = useCodegenWorkflowStore()

    await workflow.refreshTemplates()
    await workflow.startNewTemplateConversation({ user_requirement: 'Process dataset' })
    await nextTick()

    expect(store.selectedTemplateId).toBe(templateFixture.template_id)
    expect(getConversationMock).toHaveBeenCalledWith(templateFixture.template_id)
    expect(listTemplateExecutionsMock).toHaveBeenCalled()
  })

  it('sendConversationMessage delegates to store and refreshes history', async () => {
    const workflow = useCodegenWorkflow({ autoFetch: false })
    const store = useCodegenWorkflowStore()
    await workflow.refreshTemplates()
    await workflow.startNewTemplateConversation({ user_requirement: 'Process dataset' })
    await nextTick()

    await workflow.sendConversationMessage({ message: 'New prompt' })

    expect(continueConversationMock).toHaveBeenCalledWith(templateFixture.template_id, {
      message: 'New prompt'
    })
    expect(getConversationMock).toHaveBeenCalledTimes(2)
  })

  it('polls executions until completion and then stops', async () => {
    const workflow = useCodegenWorkflow({ autoFetch: false })
    await workflow.refreshTemplates()

    listTemplateExecutionsMock.mockReset()
    listTemplateExecutionsMock
      .mockImplementationOnce(async () => ({
        executions: [executionPending],
        total: 1
      }))
      .mockImplementationOnce(async () => ({
        executions: [executionCompleted],
        total: 1
      }))
      .mockImplementation(async () => ({
        executions: [executionCompleted],
        total: 1
      }))

    await workflow.selectTemplate(templateFixture.template_id)
    await nextTick()

    expect(listTemplateExecutionsMock).toHaveBeenCalledTimes(1)

    await vi.runOnlyPendingTimersAsync()
    await nextTick()

    expect(listTemplateExecutionsMock).toHaveBeenCalledTimes(2)

    await vi.runOnlyPendingTimersAsync()
    await nextTick()

    expect(listTemplateExecutionsMock).toHaveBeenCalledTimes(2)
  })

  it('runLifecycleAction routes to store lifecycle handler', async () => {
    const workflow = useCodegenWorkflow({ autoFetch: false })
    await workflow.refreshTemplates()
    await workflow.startNewTemplateConversation({ user_requirement: 'Process dataset' })
    await workflow.runLifecycleAction('confirm')

    expect(confirmTemplateMock).toHaveBeenCalledWith(templateFixture.template_id)
  })
})

