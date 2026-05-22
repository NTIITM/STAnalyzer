import { computed, getCurrentInstance, onUnmounted, ref, unref, watch, type Ref } from 'vue'
import { getAgentJobs, getAgentProjectSession, sendAgentMessage, stopAgentJob } from '../api/agent'
import type {
  AgentConversationMessage,
  AgentConversationMessageUI,
  AgentJobsResponse,
  AgentJobStatus,
  AgentJobSummary,
  AgentMessageRequestPayload,
  AgentProjectSessionPayload
} from '../types/agent'

export interface AgentContextFile {
  fileId: string
  fileName: string
}

export interface UseAgentSessionOptions {
  projectId: Ref<string | null> | string | null
  pollingIntervalMs?: number
}

export function useAgentSession(options: UseAgentSessionOptions) {
  const projectIdRef = computed(() => unref(options.projectId))
  const pollingIntervalMs = options.pollingIntervalMs ?? 5000

  const conversationId = ref<string | null>(null)
  const messages = ref<AgentConversationMessageUI[]>([])
  const messageDraft = ref('')
  const contextFiles = ref<AgentContextFile[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const sending = ref(false)
  const sendError = ref<string | null>(null)
  const composerLocked = ref(false)

  const activeJob = ref<AgentJobSummary | null>(null)
  const jobsLoading = ref(false)
  const jobsError = ref<string | null>(null)
  const pollingStatus = ref<'idle' | 'running' | 'stopped'>('idle')
  const lastPolledAt = ref<string | null>(null)
  const stopJobState = ref<'idle' | 'loading' | 'error' | 'success'>('idle')
  const stopJobError = ref<string | null>(null)

  let loadRequestId = 0
  let activeLoadController: AbortController | null = null
  let pollingTimer: number | null = null

  const hasProject = computed(() => Boolean(projectIdRef.value))

  function resetConversationState() {
    conversationId.value = null
    messages.value = []
    sending.value = false
    sendError.value = null
    messageDraft.value = ''
    error.value = null
    contextFiles.value = []
  }

  function resetJobState() {
    activeJob.value = null
    jobsLoading.value = false
    jobsError.value = null
    composerLocked.value = false
    stopJobState.value = 'idle'
    stopJobError.value = null
    stopPolling()
  }

  function cancelActiveLoad() {
    activeLoadController?.abort()
    activeLoadController = null
  }

  async function loadProjectSession(projectId: string | null, requestId: number) {
    cancelActiveLoad()
    resetConversationState()
    resetJobState()
    if (!projectId) {
      loading.value = false
      return
    }

    const controller = new AbortController()
    activeLoadController = controller
    loading.value = true
    error.value = null

    try {
      const response = await getAgentProjectSession(projectId, { signal: controller.signal })
      if (requestId !== loadRequestId) {
        return
      }
      hydrateSession(response)
    } catch (err) {
      if (controller.signal.aborted || requestId !== loadRequestId) {
        return
      }
      error.value =
        (err as { message?: string })?.message ||
        (err as Error)?.toString() ||
        'Failed to load project session'
      hydrateConversationFromHistory({ messages: [] })
    } finally {
      if (requestId === loadRequestId) {
        loading.value = false
        if (activeLoadController === controller) {
          activeLoadController = null
        }
      }
    }
  }

  function hydrateSession(payload: AgentProjectSessionPayload) {
    hydrateConversationFromHistory(payload.conversation)
    const hasPendingJob = Boolean(payload.job_id)
    setJobStateFromPayload({
      active: null,
      locked: hasPendingJob
    })
    if (hasPendingJob) {
      void refreshJobs({ silent: true })
    }
  }

  function hydrateConversationFromHistory(conversation: {
    messages?: AgentConversationMessage[]
    conversation_id?: string
  }) {
    conversationId.value = conversation.conversation_id ?? null
    messages.value = (conversation.messages ?? []).map(mapHistoryMessage)
  }

  function setJobStateFromPayload({ active, locked }: { active: AgentJobSummary | null; locked: boolean }) {
    activeJob.value = active
    composerLocked.value = locked
    if (active && isJobActive(active.status)) {
      startPolling()
    } else if (!locked) {
      stopPolling()
    }
  }

  function mapHistoryMessage(message: AgentConversationMessage): AgentConversationMessageUI {
    const timestamp = message.timestamp ? new Date(message.timestamp) : new Date()
    return {
      id: message.message_id || generateMessageId('history'),
      role: message.role === 'assistant' ? 'agent' : (message.role as AgentConversationMessageUI['role']),
      content: message.message ?? message.content ?? '',
      time: formatTime(timestamp),
      timestamp: message.timestamp,
      metadata: (message.metadata as unknown as Record<string, unknown>) ?? null,
      origin: 'history',
      status: message.metadata?.status === 'failed' ? 'failed' : 'completed',
      jobId: message.metadata?.job_id
    }
  }

  function generateMessageId(prefix: string) {
    return `${prefix}_${Math.random().toString(36).slice(2, 11)}`
  }

  function formatTime(date: Date) {
    return `${date.getHours().toString().padStart(2, '0')}:${date.getMinutes()
      .toString()
      .padStart(2, '0')}`
  }

  function setMessageDraft(value: string) {
    messageDraft.value = value
  }

  function addContextFile(fileId: string, fileName: string) {
    contextFiles.value = [{ fileId, fileName }]
  }

  function removeContextFile(fileId: string) {
    contextFiles.value = contextFiles.value.filter((file) => file.fileId !== fileId)
  }

  async function sendMessage() {
    if (!hasProject.value) {
      sendError.value = 'Project not selected'
      return
    }
    if (sending.value || composerLocked.value) {
      return
    }
    const trimmed = messageDraft.value.trim()
    if (!trimmed) {
      return
    }

    sending.value = true
    sendError.value = null
    composerLocked.value = true
    messageDraft.value = ''
    const currentProjectId = projectIdRef.value
    if (!currentProjectId) {
      sending.value = false
      composerLocked.value = false
      return
    }

    const payload: AgentMessageRequestPayload = {
      project_id: currentProjectId,
      conversation_id: conversationId.value,
      message: trimmed,
      metadata:
        contextFiles.value.length > 0
          ? {
              context_files: contextFiles.value.map((file) => file.fileId)
            }
          : null
    }

    try {
      const response: AgentProjectSessionPayload = await sendAgentMessage(payload)
      hydrateSession(response)
    } catch (err) {
      sendError.value =
        (err as { message?: string })?.message ||
        (err as Error)?.toString() ||
        'Agent request failed'
    } finally {
      sending.value = false
      composerLocked.value = false
    }
  }

  async function refreshJobs(options?: { silent?: boolean }) {
    const projectId = projectIdRef.value
    if (!projectId) {
      return
    }
    if (!options?.silent) {
      jobsLoading.value = true
      jobsError.value = null
    }
    try {
      const response = await getAgentJobs(projectId)
      applyJobsResponse(response)
    } catch (err) {
      if (!options?.silent) {
        jobsError.value =
          (err as { message?: string })?.message ||
          (err as Error)?.toString() ||
          'Failed to refresh jobs'
      }
    } finally {
      if (!options?.silent) {
        jobsLoading.value = false
      }
    }
  }

  function applyJobsResponse(response: AgentJobsResponse) {
    activeJob.value = response.job
    // 只要存在未完成的 job，就锁定输入并保持轮询
    const jobIsActive = response.job && isJobActive(response.job.status)
    composerLocked.value = Boolean(jobIsActive)
    lastPolledAt.value = new Date().toISOString()

    if (jobIsActive) {
      startPolling()
    } else {
      stopPolling()
      // 如果job已完成（completed/failed/cancelled），确保解锁输入
      if (response.job && !isJobActive(response.job.status)) {
        composerLocked.value = false
      }
    }
  }

  function isJobActive(status: AgentJobStatus | null | undefined) {
    // Only 'running' status is considered active
    return status === 'running'
  }

  function startPolling() {
    if (pollingTimer || !activeJob.value || !isJobActive(activeJob.value.status)) {
      return
    }
    pollingStatus.value = 'running'
    void refreshJobs({ silent: true })
    pollingTimer = window.setInterval(() => {
      void refreshJobs({ silent: true })
    }, pollingIntervalMs)
  }

  function stopPolling() {
    if (pollingTimer) {
      clearInterval(pollingTimer)
      pollingTimer = null
    }
    if (pollingStatus.value !== 'idle') {
      pollingStatus.value = 'stopped'
    }
  }

  // 页面可见性感知：后台标签页暂停轮询，前台恢复
  function handleVisibilityChange() {
    if (document.hidden) {
      stopPolling()
    } else if (activeJob.value && isJobActive(activeJob.value.status)) {
      // 切回前台时立即刷新一次，再恢复轮询
      void refreshJobs({ silent: true })
      startPolling()
    }
  }

  document.addEventListener('visibilitychange', handleVisibilityChange)

  async function requestStop(jobId?: string) {
    if (!jobId) {
      return
    }
    stopJobState.value = 'loading'
    stopJobError.value = null
    try {
      await stopAgentJob(jobId)
      stopJobState.value = 'success'
      // Refresh jobs to get updated status (may be 'cancelling' or 'cancelled')
      await refreshJobs()
      // Don't unlock composer immediately - let the polling detect the final status
    } catch (err) {
      stopJobState.value = 'error'
      stopJobError.value =
        (err as { message?: string })?.message || (err as Error)?.toString() || 'Failed to stop job'
    }
  }

  function retryLoad() {
    loadRequestId += 1
    void loadProjectSession(projectIdRef.value, loadRequestId)
  }

  watch(
    projectIdRef,
    (projectId) => {
      loadRequestId += 1
      const requestId = loadRequestId
      if (!projectId) {
        cancelActiveLoad()
        resetConversationState()
        resetJobState()
        return
      }
      void loadProjectSession(projectId, requestId)
    },
    { immediate: true }
  )

  if (getCurrentInstance()) {
    onUnmounted(() => {
      cancelActiveLoad()
      stopPolling()
      sending.value = false
      document.removeEventListener('visibilitychange', handleVisibilityChange)
    })
  }

  return {
    // state
    hasProject,
    conversationId,
    messages,
    loading,
    error,
    sending,
    sendError,
    composerLocked,
    messageDraft,
    activeJob,
    jobsLoading,
    jobsError,
    pollingStatus,
    lastPolledAt,
    stopJobState,
    stopJobError,
    contextFiles,
    addContextFile,
    removeContextFile,
    // actions
    setMessageDraft,
    sendMessage,
    retryLoad,
    refreshJobs,
    requestStop,
    startPolling,
    stopPolling
  }
}
