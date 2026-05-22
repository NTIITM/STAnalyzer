/**
 * Execution polling composable for codegen executions.
 * Implements requirements R4, R5, R6 for execution monitoring.
 * 
 * Features:
 * - Per-execution polling tracking to avoid duplicates
 * - Automatic polling until terminal state (completed/failed)
 * - Manual refresh support
 * - Cleanup on component unmount (route leave)
 * - Configurable polling interval
 */
import { computed, onBeforeUnmount, ref, watch, type Ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useCodegenWorkflowStore } from '../../stores/codegenWorkflowStore'
import type { CodegenExecution, CodegenExecutionStatus } from '../../types/codegen'

export interface UseExecutionPollingOptions {
  /**
   * Polling interval in milliseconds (default: 3000)
   */
  pollingIntervalMs?: number
  /**
   * Whether to automatically start polling when pending executions are detected (default: true)
   */
  autoStart?: boolean
  /**
   * Whether to poll execution details in addition to the list (default: true)
   */
  pollDetails?: boolean
}

const TERMINAL_STATUSES: CodegenExecutionStatus[] = ['completed', 'failed']
const NON_TERMINAL_STATUSES: CodegenExecutionStatus[] = ['pending', 'running']

/**
 * Check if an execution status is terminal
 */
function isTerminalStatus(status: string): boolean {
  return TERMINAL_STATUSES.includes(status as CodegenExecutionStatus)
}

/**
 * Check if an execution status is non-terminal (should be polled)
 */
function isNonTerminalStatus(status: string): boolean {
  return NON_TERMINAL_STATUSES.includes(status as CodegenExecutionStatus)
}

/**
 * Composable for managing execution polling with per-execution tracking.
 * Prevents duplicate polling for the same execution and automatically stops
 * when executions reach terminal states.
 */
export function useExecutionPolling(
  templateId: Ref<string | null>,
  options: UseExecutionPollingOptions = {}
) {
  const store = useCodegenWorkflowStore()
  const {
    currentExecutions,
    executionDetails,
    executionDetailLoading,
    executionsLoading
  } = storeToRefs(store)

  const pollingInterval = options.pollingIntervalMs ?? 3000
  const autoStart = options.autoStart !== false
  const pollDetails = options.pollDetails !== false

  // Track which executions are currently being polled
  const pollingExecutions = ref<Set<string>>(new Set())
  
  // Single unified polling timer (replaces per-execution timers)
  let unifiedPollingTimer: ReturnType<typeof setInterval> | null = null

  /**
   * Check if an execution should be polled (non-terminal status)
   */
  const shouldPollExecution = (execution: CodegenExecution): boolean => {
    return isNonTerminalStatus(String(execution.status))
  }

  /**
   * Get all non-terminal executions that should be polled
   */
  const getPollableExecutions = computed(() => {
    if (!templateId.value) return []
    return currentExecutions.value.filter(shouldPollExecution)
  })

  /**
   * Poll a specific execution detail
   */
  async function pollExecutionDetail(executionId: string): Promise<void> {
    // Skip if already polling this execution
    if (pollingExecutions.value.has(executionId)) {
      return
    }

    // Skip if already in terminal state
    const cached = executionDetails.value[executionId]
    if (cached && isTerminalStatus(String(cached.status))) {
      return
    }

    pollingExecutions.value.add(executionId)

    try {
      const execution = await store.fetchExecutionDetail(executionId, { force: true })
      
      // Stop polling if execution reached terminal state
      if (isTerminalStatus(String(execution.status))) {
        stopPollingExecution(executionId)
      }
    } catch (error) {
      // On error, continue polling (might be transient)
      console.warn(`Failed to poll execution ${executionId}:`, error)
    } finally {
      pollingExecutions.value.delete(executionId)
    }
  }

  /**
   * Poll execution list for the current template
   */
  async function pollExecutionList(): Promise<void> {
    if (!templateId.value || executionsLoading.value) {
      return
    }

    try {
      await store.fetchExecutions(templateId.value, { force: true })
    } catch (error) {
      console.warn(`Failed to poll execution list for template ${templateId.value}:`, error)
    }
  }

  /**
   * Start polling a specific execution (compatibility - now uses unified timer)
   */
  function startPollingExecution(_executionId: string): void {
    // Individual polling is now handled by the unified timer
    startUnifiedPolling()
  }

  /**
   * Stop polling a specific execution (compatibility)
   */
  function stopPollingExecution(executionId: string): void {
    pollingExecutions.value.delete(executionId)
  }

  /**
   * Start unified polling (replaces both list and per-execution timers)
   */
  function startUnifiedPolling(): void {
    if (unifiedPollingTimer) return

    unifiedPollingTimer = setInterval(async () => {
      // Skip if page is hidden
      if (document.hidden) return

      // Refresh execution list
      await pollExecutionList()

      // Batch refresh details for all non-terminal executions
      if (pollDetails) {
        const pollable = getPollableExecutions.value
        if (pollable.length > 0) {
          const promises = pollable.map(exec => pollExecutionDetail(exec.execution_id))
          await Promise.allSettled(promises)
        }
      }

      // Auto-stop if no more non-terminal executions
      if (getPollableExecutions.value.length === 0) {
        stopUnifiedPolling()
      }
    }, pollingInterval)
  }

  /**
   * Stop unified polling
   */
  function stopUnifiedPolling(): void {
    if (unifiedPollingTimer) {
      clearInterval(unifiedPollingTimer)
      unifiedPollingTimer = null
    }
  }

  /**
   * Start polling all non-terminal executions
   */
  function startPollingAll(): void {
    if (!templateId.value) return
    startUnifiedPolling()
  }

  /**
   * Stop all polling
   */
  function stopAllPolling(): void {
    stopUnifiedPolling()
    pollingExecutions.value.clear()
  }

  /**
   * Manually refresh execution list and details
   */
  async function refreshExecutions(): Promise<void> {
    if (!templateId.value) return

    try {
      // Refresh list
      await store.fetchExecutions(templateId.value, { force: true })

      // Refresh details for all non-terminal executions
      if (pollDetails) {
        const promises = getPollableExecutions.value.map((execution) =>
          store.fetchExecutionDetail(execution.execution_id, { force: true })
        )
        await Promise.allSettled(promises)
      }
    } catch (error) {
      console.error('Failed to refresh executions:', error)
      throw error
    }
  }

  /**
   * Manually refresh a specific execution
   */
  async function refreshExecution(executionId: string): Promise<void> {
    try {
      await store.fetchExecutionDetail(executionId, { force: true })
    } catch (error) {
      console.error(`Failed to refresh execution ${executionId}:`, error)
      throw error
    }
  }

  // Watch for new non-terminal executions and manage unified polling
  watch(
    getPollableExecutions,
    (newExecutions) => {
      if (!autoStart) return

      if (newExecutions.length > 0) {
        startUnifiedPolling()
      } else {
        stopUnifiedPolling()
      }
    },
    { immediate: true }
  )

  // Watch template changes and cleanup
  watch(
    templateId,
    (newId, oldId) => {
      // Stop all polling when template changes
      if (oldId !== null) {
        stopAllPolling()
      }

      // Start polling for new template if autoStart is enabled
      if (newId && autoStart) {
        startPollingAll()
      }
    },
    { immediate: false }
  )

  // Page visibility awareness: pause polling when tab is hidden
  function handleVisibilityChange() {
    if (document.hidden) {
      stopUnifiedPolling()
    } else if (getPollableExecutions.value.length > 0) {
      // Immediately refresh and restart when tab becomes visible
      void refreshExecutions()
      startUnifiedPolling()
    }
  }

  document.addEventListener('visibilitychange', handleVisibilityChange)

  // Cleanup on unmount (route leave)
  onBeforeUnmount(() => {
    stopAllPolling()
    document.removeEventListener('visibilitychange', handleVisibilityChange)
  })

  return {
    // State
    pollingExecutions: computed(() => Array.from(pollingExecutions.value)),
    isPolling: computed(() => unifiedPollingTimer !== null),

    // Actions
    startPollingAll,
    stopAllPolling,
    startPollingExecution,
    stopPollingExecution,
    refreshExecutions,
    refreshExecution,
    pollExecutionList,
    pollExecutionDetail,

    // Computed
    getPollableExecutions
  }
}

