import request from './request'
import { tokenManager } from './request'
import type {
  AgentConversationResponse,
  AgentJobsResponse,
  AgentMessageRequestPayload,
  AgentProjectSessionPayload,
  AgentStopJobResponse
} from '../types/agent'

export interface AgentProjectSessionOptions {
  signal?: AbortSignal
}

export async function getAgentProjectSession(
  projectId: string,
  options: AgentProjectSessionOptions = {}
): Promise<AgentProjectSessionPayload> {
  return request({
    url: `/agent/session/${projectId}`,
    method: 'GET',
    signal: options.signal
  }) as Promise<AgentProjectSessionPayload>
}

export interface AgentJobsOptions {
  signal?: AbortSignal
}

export async function getAgentJobs(
  projectId: string,
  options: AgentJobsOptions = {}
): Promise<AgentJobsResponse> {
  return request({
    url: `/agent/jobs/${projectId}`,
    method: 'GET',
    signal: options.signal
  }) as Promise<AgentJobsResponse>
}

export async function stopAgentJob(jobId: string): Promise<AgentStopJobResponse> {
  return request({
    url: `/agent/jobs/${jobId}/stop`,
    method: 'POST'
  }) as Promise<AgentStopJobResponse>
}
/**
 * 发送对话消息（后端返回更新后的会话 + 作业快照）
 */
export async function sendAgentMessage(
  payload: AgentMessageRequestPayload
): Promise<AgentProjectSessionPayload> {
  return request({
    url: '/agent/message',
    method: 'POST',
    data: payload
  }) as Promise<AgentProjectSessionPayload>
}

export async function getAgentConversation(projectId: string): Promise<AgentConversationResponse> {
  return request({
    url: `/agent/conversation/${projectId}`,
    method: 'GET'
  }) as Promise<AgentConversationResponse>
}

export async function clearAgentConversation(projectId: string): Promise<{ success: boolean }> {
  return request({
    url: `/agent/conversation/${projectId}`,
    method: 'DELETE'
  }) as Promise<{ success: boolean }>
}

export async function createConversationStream(options: {
  projectId: string
  message: string
  contextFiles?: string[] | null
  onMessage: (payload: { message?: string; extra?: Record<string, unknown> | null }) => void
  onError: (error: Error) => void
  onComplete: () => void
}) {
  const url = new URL(`/STAnalyzer/api/agent/conversation/${options.projectId}/stream`, window.location.origin)
  url.searchParams.set('message', options.message)
  if (options.contextFiles?.length) {
    options.contextFiles.forEach((fileId) => {
      if (fileId) {
        url.searchParams.append('context_files', fileId)
      }
    })
  }

  const controller = new AbortController()

  // 获取 token（使用 tokenManager 保持一致性）
  const token = tokenManager.getToken()

  const headers: Record<string, string> = {
    Accept: 'text/event-stream',
    // 禁用缓存，确保实时流式传输
    'Cache-Control': 'no-cache, no-transform',
    // 提示代理不要缓冲（某些代理会识别此头）
    'X-Accel-Buffering': 'no'
  }
  
  // 添加 token 到请求头（支持多种方式）
  if (token) {
    // 方式1: Authorization Bearer 头（优先）
    headers.Authorization = `Bearer ${token}`
    // 方式2: token 头
    headers.token = token
  }
  
  // 方式3: 查询参数（后端也支持这种方式）
  if (token) {
    url.searchParams.set('token', token)
    // 也支持 access_token 参数
    url.searchParams.set('access_token', token)
  }

  let completed = false

  try {
    const response = await fetch(url.toString(), {
      method: 'POST',
      headers,
      signal: controller.signal
    })

    if (!response.ok || !response.body) {
      throw new Error(`请求失败: ${response.status}`)
    }


    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''

    // 解析 SSE 事件
    const parseSseChunk = (rawChunk: string) => {
      const lines = rawChunk.split('\n')
      let eventType = 'message'
      const dataLines: string[] = []

      lines.forEach((line) => {
        if (line.startsWith('event:')) {
          eventType = line.slice(6).trim()
        } else if (line.startsWith('data:')) {
          dataLines.push(line.slice(5).trim())
        }
      })

      const dataStr = dataLines.join('\n')
      if (!dataStr && eventType !== 'end') return

      console.log(`[Agent] 收到事件 [${eventType}]:`, dataStr)

      if (eventType === 'progress') {
        try {
          const data = JSON.parse(dataStr)
          // 直接透传后端数据，避免丢失 extra/metadata 等字段
          options.onMessage({
            message: data.message || data.partial_answer || '',
            extra: data.extra ?? null,
            ...data
          })
        } catch (e) {
          console.error('[Agent] 解析进度数据失败:', e)
        }
      } else if (eventType === 'result') {
        try {
          const data = JSON.parse(dataStr)
          options.onMessage({
            message: data.final_answer || data.message || '',
            extra: data.extra ?? {
              evidence_sources: data.evidence_sources,
              conversation_id: data.conversation_id
            },
            ...data
          })
          if (!completed) {
            completed = true
            options.onComplete()
          }
        } catch (e) {
          console.error('[Agent] 解析结果数据失败:', e)
        }
      } else if (eventType === 'error') {
        try {
          const errorData = JSON.parse(dataStr)
          console.error('[Agent] 错误详情:', errorData)
          options.onMessage({
            message: `错误: ${errorData.message || errorData.error || '未知错误'}`
          })
        } catch (e) {
          console.error('[Agent] 解析错误数据失败:', e)
        }
      } else if (eventType === 'end') {
        console.log('[Agent] SSE 流结束')
        if (!completed) {
          completed = true
          options.onComplete()
        }
      }
    }

    // 读取流
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })

      let splitIndex = buffer.indexOf('\n\n')
      while (splitIndex !== -1) {
        const rawEvent = buffer.slice(0, splitIndex)
        buffer = buffer.slice(splitIndex + 2)
        if (rawEvent.trim()) {
          parseSseChunk(rawEvent)
        }
        splitIndex = buffer.indexOf('\n\n')
      }
    }

    if (buffer.trim()) {
      parseSseChunk(buffer)
    }

    if (!completed) {
      completed = true
      options.onComplete()
    }
  } catch (err: any) {
    if (controller.signal.aborted) return
    console.error('[Agent] SSE 错误:', err)
    options.onError(err)
    if (!completed) {
      completed = true
      options.onComplete()
    }
  }

  return controller
}

