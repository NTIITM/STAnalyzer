import { ref } from 'vue'
import { useAbortController, type UseAbortControllerResult } from '../hooks/useAbortController'

export interface CancelableRequestOptions {
  /**
   * Abort any in-flight request before starting the new one.
   * Defaults to true.
   */
  abortExisting?: boolean
}

export interface CancelableRequestResult<T> {
  execute: (factory: (signal: AbortSignal) => Promise<T>, options?: CancelableRequestOptions) => Promise<T>
  cancel: () => void
  isPending: () => boolean
}

/**
 * Provide a simple wrapper for handling cancelable async requests backed by AbortController.
 * Each instance maintains a single in-flight request; starting a new one aborts the previous by default.
 */
export function useCancelableRequest<T = unknown>(): CancelableRequestResult<T> {
  const abortController: UseAbortControllerResult = useAbortController()
  const pendingRef = ref(false)

  async function execute(
    factory: (signal: AbortSignal) => Promise<T>,
    options: CancelableRequestOptions = {}
  ): Promise<T> {
    const { abortExisting = true } = options
    const controller = abortController.create({ abortExisting })
    const signal = controller.signal
    pendingRef.value = true

    try {
      return await factory(signal)
    } finally {
      if (abortController.signal() === signal) {
        pendingRef.value = false
      }
    }
  }

  function cancel(): void {
    abortController.abort()
    pendingRef.value = false
  }

  function isPending(): boolean {
    return pendingRef.value
  }

  return {
    execute,
    cancel,
    isPending
  }
}


