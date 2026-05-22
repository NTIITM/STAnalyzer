import { ref } from 'vue'
import type { Ref } from 'vue'
import type { AgentConversationMessage } from '../types/agent'
import { clearAgentConversation, createConversationStream, getAgentConversation } from '../api/agent'

interface SendMessageOptions {
  projectId: string
  content: string
  contextFiles?: string[]
}

interface UseAgentConversationStream {
  projectId: Ref<string | null>
  messages: Ref<AgentConversationMessage[]>
  sending: Ref<boolean>
  loading: Ref<boolean>
  error: Ref<string | null>
  conversationActive: Ref<boolean>
  loadConversation: (projectId: string | null) => Promise<void>
  sendMessage: (options: SendMessageOptions) => Promise<void>
  clearConversation: (projectId: string | null) => Promise<void>
  stopStream: () => void
}

const projectIdRef = ref<string | null>(null)
const messagesRef = ref<AgentConversationMessage[]>([])
const sendingRef = ref(false)
const loadingRef = ref(false)
const errorRef = ref<string | null>(null)
const conversationActiveRef = ref(false)
let streamController: AbortController | null = null

async function loadConversationInternal(projectId: string | null) {
  if (!projectId) {
    messagesRef.value = []
    sendingRef.value = false
    conversationActiveRef.value = false
    return
  }

  loadingRef.value = true
  errorRef.value = null
  try {
    const response = await getAgentConversation(projectId)
    // 兼容后端返回 { conversation: { messages: [...] } } 或直接返回 messages 数组
    const conversation = (response as any)?.conversation ?? response
    messagesRef.value = conversation?.messages ?? []
  } catch (err) {
    const e = err as { message?: string } | Error
    const msg = (e as { message?: string })?.message || e.toString()
    errorRef.value = msg
  } finally {
    loadingRef.value = false
  }
}

function stopStreamInternal() {
  if (streamController) {
    streamController.abort()
    streamController = null
  }
  sendingRef.value = false
  conversationActiveRef.value = false
}

async function sendMessageInternal(options: SendMessageOptions) {
  if (!options.projectId || !options.content.trim()) {
    return
  }

  stopStreamInternal()
  sendingRef.value = true
  conversationActiveRef.value = true

  const now = new Date()
  const userMessage: AgentConversationMessage = {
    message_id: `local-${now.getTime()}`,
    role: 'user',
    message: options.content.trim(),
    timestamp: now.toISOString()
  }

  messagesRef.value = [userMessage]

  try {
    streamController = await createConversationStream({
      projectId: options.projectId,
      message: options.content.trim(),
      contextFiles: options.contextFiles,
      onMessage: (payload) => {
        const p = payload as any
        const tsRaw =
          p?.timestamp ??
          p?.time ??
          p?.created_at ??
          p?.updated_at ??
          null
        const nowChunk = tsRaw ? new Date(tsRaw) : new Date()
        const agentMsg: AgentConversationMessage = {
          message_id: `chunk-${nowChunk.getTime()}-${Math.random().toString(36).substr(2, 9)}`,
          role: 'assistant',
          message: payload.message || '',
          // 优先保留后端提供的时间戳，缺失时才使用前端当前时间
          timestamp: tsRaw || nowChunk.toISOString(),
          ...(payload.extra !== undefined ? { extra: payload.extra } : {})
        }
        messagesRef.value = [...messagesRef.value, agentMsg]
      },
      onError: () => {
        sendingRef.value = false
        stopStreamInternal()
      },
      onComplete: () => {
        sendingRef.value = false
        stopStreamInternal()
      }
    })
  } catch (err) {
    sendingRef.value = false
    stopStreamInternal()
    const e = err as { message?: string } | Error
    const msg = (e as { message?: string })?.message || e.toString()
    errorRef.value = msg
  }
}

async function clearConversationInternal(projectId: string | null) {
  if (!projectId) return
  try {
    await clearAgentConversation(projectId)
    messagesRef.value = []
    stopStreamInternal()
  } catch (err) {
    const e = err as { message?: string } | Error
    const msg = (e as { message?: string })?.message || e.toString()
    errorRef.value = msg
  }
}

export function useAgentConversationStream(): UseAgentConversationStream {
  const projectId = projectIdRef
  const messages = messagesRef
  const sending = sendingRef
  const loading = loadingRef
  const error = errorRef
  const conversationActive = conversationActiveRef

  return {
    projectId,
    messages,
    sending,
    loading,
    error,
    conversationActive,
    loadConversation: async (pid: string | null) => {
      projectIdRef.value = pid
      await loadConversationInternal(pid)
    },
    sendMessage: async (options: SendMessageOptions) => {
      projectIdRef.value = options.projectId
      await sendMessageInternal(options)
    },
    clearConversation: async (pid: string | null) => {
      await clearConversationInternal(pid)
    },
    stopStream: () => {
      stopStreamInternal()
    }
  }
}
