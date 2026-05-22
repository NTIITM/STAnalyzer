import i18n from '../i18n'
import { ElNotification } from 'element-plus'

type NotifyType = 'success' | 'error' | 'warning' | 'info'

export interface NotifyMessageOptions {
  message?: string
  translationKey?: string
  values?: Record<string, unknown>
  fallback?: string
  details?: string | string[]
  duration?: number
}

type NotifyInput = string | NotifyMessageOptions

function resolveMessage(input: NotifyInput): { text: string; duration?: number } {
  if (typeof input === 'string') {
    return { text: input }
  }

  const {
    message,
    translationKey,
    values,
    fallback,
    details,
    duration
  } = input

  let text = message?.trim()

  if (!text && translationKey) {
    const translated = i18n.global.t(translationKey, values ?? {})
    text = translated === translationKey ? undefined : translated
  }

  if (!text && fallback) {
    text = fallback
  }

  if (!text) {
    text = i18n.global.t('app.unknownError')
  }

  if (text && details) {
    const detailText = Array.isArray(details)
      ? details.filter(Boolean).join('; ')
      : details
    if (detailText && detailText.trim().length > 0) {
      text = `${text} (${detailText.trim()})`
    }
  }

  return { text, duration }
}

function emitNotification(type: NotifyType, input: NotifyInput) {
  const { text, duration } = resolveMessage(input)
  const resolvedDuration =
    duration ?? (type === 'error' ? 6000 : type === 'warning' ? 5000 : 3000)

  if (!text) {
    return
  }

  // 使用 Element Plus Notification，右下角类似“toast”样式
  ElNotification({
    message: text,
    type,
    duration: resolvedDuration,
    position: 'top-right',
    showClose: false
  })
}

export function notifySuccess(input: NotifyInput) {
  emitNotification('success', input)
}

export function notifyError(input: NotifyInput) {
  emitNotification('error', input)
}

export function notifyWarning(input: NotifyInput) {
  emitNotification('warning', input)
}

export function notifyInfo(input: NotifyInput) {
  emitNotification('info', input)
}
