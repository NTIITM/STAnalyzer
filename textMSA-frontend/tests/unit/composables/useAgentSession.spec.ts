import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'

const apiMocks = vi.hoisted(() => {
  return {
    getAgentProjectSession: vi.fn(),
    getAgentJobs: vi.fn(),
    stopAgentJob: vi.fn(),
    sendAgentMessage: vi.fn(),
    createAgentSseClient: vi.fn(() => ({
      cancel: vi.fn(),
      getStatus: () => 'open'
    }))
  }
})

vi.mock('../../../src/api/agent', () => ({
  getAgentProjectSession: apiMocks.getAgentProjectSession,
  getAgentJobs: apiMocks.getAgentJobs,
  stopAgentJob: apiMocks.stopAgentJob,
  sendAgentMessage: apiMocks.sendAgentMessage,
  createAgentSseClient: apiMocks.createAgentSseClient
}))

describe('useAgentSession', () => {
  const conversationFixture = {
    conversation_id: 'conv-1',
    project_id: 'proj-1',
    messages: [
      {
        message_id: 'm1',
        role: 'user',
        content: 'Hello',
        timestamp: '2025-01-01T00:00:00Z'
      }
    ]
  }

  const activeJobFixture = {
    job_id: 'job-1',
    status: 'running',
    started_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:05Z',
    locked: true,
    progress: {
      current_step: 'tool_selector',
      step_detail: 'Scoring relevant tools'
    }
  }

  beforeEach(() => {
    vi.resetModules()
    vi.clearAllMocks()
    apiMocks.getAgentProjectSession.mockResolvedValue({
      conversation: conversationFixture,
      job_id: activeJobFixture.job_id
    })
    apiMocks.getAgentJobs.mockResolvedValue({
      job: { ...activeJobFixture }
    })
  })

  it('hydrates conversation and job snapshot when project id is provided', async () => {
    const projectId = ref<string | null>(null)
    const { useAgentSession } = await import('../../../src/composables/useAgentSession')
    const session = useAgentSession({ projectId })

    projectId.value = 'proj-1'

    await vi.waitFor(() => expect(session.messages.value).toHaveLength(1))
    await vi.waitFor(() => expect(apiMocks.getAgentJobs).toHaveBeenCalled())
    expect(session.activeJob.value?.job_id).toBe('job-1')
    expect(session.composerLocked.value).toBe(true)
  })

  it('refreshJobs updates composer lock and polling timestamp', async () => {
    apiMocks.getAgentProjectSession.mockResolvedValueOnce({
      conversation: conversationFixture,
      job_id: null
    })
    const projectId = ref<string | null>('proj-1')
    const { useAgentSession } = await import('../../../src/composables/useAgentSession')
    const session = useAgentSession({ projectId })

    await vi.waitFor(() => expect(apiMocks.getAgentProjectSession).toHaveBeenCalled())
    expect(session.composerLocked.value).toBe(false)

    apiMocks.getAgentJobs.mockResolvedValueOnce({
      job: { ...activeJobFixture, status: 'running' }
    })
    await session.refreshJobs()
    expect(session.activeJob.value?.status).toBe('running')
    expect(session.composerLocked.value).toBe(true)

    apiMocks.getAgentJobs.mockResolvedValueOnce({
      job: { ...activeJobFixture, status: 'completed' }
    })

    await session.refreshJobs()

    expect(session.activeJob.value?.status).toBe('completed')
    expect(session.composerLocked.value).toBe(false)
    expect(session.lastPolledAt.value).toBeTruthy()
  })

  it('requestStop delegates to stop endpoint and refreshes jobs', async () => {
    apiMocks.stopAgentJob.mockResolvedValue({ job_id: 'job-1', status: 'cancelled' })
    const projectId = ref<string | null>('proj-1')
    const { useAgentSession } = await import('../../../src/composables/useAgentSession')
    const session = useAgentSession({ projectId })

    await vi.waitFor(() => expect(apiMocks.getAgentProjectSession).toHaveBeenCalled())

    await session.requestStop('job-1')

    expect(apiMocks.stopAgentJob).toHaveBeenCalledWith('job-1')
    expect(apiMocks.getAgentJobs).toHaveBeenCalled()
  })

  it('sendMessage waits for backend conversation before updating messages', async () => {
    apiMocks.getAgentProjectSession.mockResolvedValueOnce({
      conversation: conversationFixture,
      job_id: null
    })
    const projectId = ref<string | null>('proj-1')
    const { useAgentSession } = await import('../../../src/composables/useAgentSession')
    const session = useAgentSession({ projectId })

    await vi.waitFor(() => expect(apiMocks.getAgentProjectSession).toHaveBeenCalled())
    expect(session.messages.value).toHaveLength(1)

    apiMocks.sendAgentMessage.mockResolvedValueOnce({
      conversation: {
        ...conversationFixture,
        messages: [
          ...conversationFixture.messages,
          {
            message_id: 'm2',
            role: 'assistant',
            content: 'Updated from backend',
            timestamp: '2025-01-01T00:00:02Z'
          }
        ]
      },
      job_id: null
    })

    session.setMessageDraft('New question')
    const sendPromise = session.sendMessage()
    expect(session.messages.value).toHaveLength(1)
    await sendPromise

    expect(apiMocks.sendAgentMessage).toHaveBeenCalled()
    expect(session.messages.value).toHaveLength(2)
    expect(session.messages.value[1].content).toBe('Updated from backend')
  })
})

