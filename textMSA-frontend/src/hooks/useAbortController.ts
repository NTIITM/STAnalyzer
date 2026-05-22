import { onBeforeUnmount, ref } from 'vue'

export interface CreateAbortControllerOptions {
  /**
   * Abort any existing controller before creating a new one.
   * Defaults to true to mimic single-flight behaviour.
   */
  abortExisting?: boolean
}

export interface UseAbortControllerResult {
  /**
   * Create (or replace) the managed AbortController.
   */
  create: (options?: CreateAbortControllerOptions) => AbortController
  /**
   * Return the currently managed AbortSignal, if any.
   */
  signal: () => AbortSignal | undefined
  /**
   * Abort the current controller, if present.
   */
  abort: () => void
}

/**
 * Lightweight utility to manage a single AbortController lifecycle per component/composable.
 * Automatically aborts the active controller when the scope is unmounted.
 */
export function useAbortController(): UseAbortControllerResult {
  const controllerRef = ref<AbortController | null>(null)

  function abort(): void {
    controllerRef.value?.abort()
    controllerRef.value = null
  }

  function create(options: CreateAbortControllerOptions = {}): AbortController {
    const { abortExisting = true } = options
    if (abortExisting && controllerRef.value) {
      controllerRef.value.abort()
    }
    const controller = new AbortController()
    controllerRef.value = controller
    return controller
  }

  function signal(): AbortSignal | undefined {
    return controllerRef.value?.signal
  }

  onBeforeUnmount(() => {
    abort()
  })

  return {
    create,
    signal,
    abort
  }
}


