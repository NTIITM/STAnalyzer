/**
 * Workspace routing helper that synchronizes Pinia state with router query parameters.
 * Implements requirements R1, R2, R5, R7 for persisting workspace context.
 */
import { computed, onBeforeUnmount, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useCodegenWorkflowStore } from '../../stores/codegenWorkflowStore'

export interface WorkspaceRoutingState {
  projectId: string | null
  serviceId: string | null
  templateId: string | null
  executionId: string | null
  conversationDraft: string | null
}

const DEBOUNCE_MS = 300

/**
 * Debounce helper to avoid thrashing router updates
 */
function debounce<T extends (...args: any[]) => void>(fn: T, delay: number): T {
  let timeoutId: ReturnType<typeof setTimeout> | null = null
  return ((...args: Parameters<T>) => {
    if (timeoutId) {
      clearTimeout(timeoutId)
    }
    timeoutId = setTimeout(() => {
      fn(...args)
      timeoutId = null
    }, delay)
  }) as T
}

/**
 * Composable that syncs workspace state with router query parameters.
 * Reads initial state from query params on mount and updates query when state changes.
 */
export function useWorkspaceRouting() {
  const route = useRoute()
  const router = useRouter()
  const store = useCodegenWorkflowStore()
  const { selectedTemplateId, conversationDrafts, activeExecutionId } = storeToRefs(store)

  // Extract initial state from query params
  const initialProjectId = computed(() => (route.query.projectId as string) || null)
  const initialServiceId = computed(() => (route.query.serviceId as string) || null)
  const initialTemplateId = computed(() => (route.query.templateId as string) || null)
  const initialExecutionId = computed(() => (route.query.executionId as string) || null)

  // Get conversation draft for current template
  const currentDraft = computed(() => {
    const templateId = selectedTemplateId.value
    if (!templateId) return null
    return conversationDrafts.value[templateId] || null
  })

  // Debounced function to update router query
  const updateQuery = debounce((updates: Partial<WorkspaceRoutingState>) => {
    const currentQuery = { ...route.query }
    const newQuery: Record<string, string | undefined> = {}

    // Preserve existing projectId and serviceId from route
    if (currentQuery.projectId) {
      newQuery.projectId = currentQuery.projectId as string
    }
    if (currentQuery.serviceId) {
      newQuery.serviceId = currentQuery.serviceId as string
    }

    // Update with new values
    if (updates.projectId !== undefined) {
      newQuery.projectId = updates.projectId || undefined
    }
    if (updates.serviceId !== undefined) {
      newQuery.serviceId = updates.serviceId || undefined
    }
    if (updates.templateId !== undefined) {
      newQuery.templateId = updates.templateId || undefined
    }
    if (updates.executionId !== undefined) {
      newQuery.executionId = updates.executionId || undefined
    }
    if (updates.conversationDraft !== undefined) {
      // Only persist non-empty drafts to avoid cluttering URL
      newQuery.draft = updates.conversationDraft || undefined
    }

    // Remove undefined values
    Object.keys(newQuery).forEach((key) => {
      if (newQuery[key] === undefined) {
        delete newQuery[key]
      }
    })

    // Only update if query actually changed
    const queryChanged = Object.keys(newQuery).some(
      (key) => currentQuery[key] !== newQuery[key]
    ) || Object.keys(currentQuery).some((key) => !(key in newQuery))

    if (queryChanged) {
      router.replace({
        path: route.path,
        query: newQuery
      })
    }
  }, DEBOUNCE_MS)

  // Watch store state and sync to query params
  watch(
    selectedTemplateId,
    (templateId) => {
      updateQuery({ templateId })
    },
    { immediate: false }
  )

  watch(
    activeExecutionId,
    (executionId) => {
      updateQuery({ executionId })
    },
    { immediate: false }
  )

  watch(
    currentDraft,
    (draft) => {
      updateQuery({ conversationDraft: draft })
    },
    { immediate: false }
  )

  // Initialize store from query params on mount
  function initializeFromQuery() {
    const templateId = initialTemplateId.value
    const executionId = initialExecutionId.value
    const draft = (route.query.draft as string) || null

    if (templateId) {
      // Load template and restore draft if present
      void store.loadTemplate(templateId, {
        fetchConversation: true,
        fetchExecutions: true
      })
      if (draft) {
        store.setConversationDraft(templateId, draft)
      }
    }

    if (executionId) {
      store.setActiveExecution(executionId)
      void store.fetchExecutionDetail(executionId)
    }
  }

  // Expose reactive state from query params
  const projectId = computed(() => initialProjectId.value)
  const serviceId = computed(() => initialServiceId.value)
  const templateId = computed(() => initialTemplateId.value)
  const executionId = computed(() => initialExecutionId.value)

  // Cleanup on unmount
  onBeforeUnmount(() => {
    // Debounce cleanup is handled by closure, no explicit cleanup needed
  })

  return {
    // Reactive state from query params
    projectId,
    serviceId,
    templateId,
    executionId,
    // Initialization function
    initializeFromQuery,
    // Manual update helpers (for programmatic navigation)
    updateQuery: (updates: Partial<WorkspaceRoutingState>) => {
      updateQuery(updates)
    }
  }
}

