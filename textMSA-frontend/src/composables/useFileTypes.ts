import { ref, computed, type Ref } from 'vue'
import { getFileTypes } from '../api/file'
import type { FileType, FileTypeDictionary } from '../types/file'

const CACHE_TTL = 5 * 60 * 1000
const CATEGORY_ALL = '__all__'

interface FileTypeState {
  list: Ref<FileType[]>
  loading: Ref<boolean>
  error: Ref<string | null>
  lastFetchedAt: Ref<number | null>
  promise: Promise<FileType[]> | null
}

const sharedStates = new Map<string, FileTypeState>()

function categoryKey(category?: string) {
  return category ? `category:${category}` : CATEGORY_ALL
}

function ensureState(key: string): FileTypeState {
  if (!sharedStates.has(key)) {
    sharedStates.set(key, {
      list: ref<FileType[]>([]),
      loading: ref(false),
      error: ref<string | null>(null),
      lastFetchedAt: ref<number | null>(null),
      promise: null
    })
  }
  return sharedStates.get(key)!
}

function isCacheValid(state: FileTypeState) {
  if (!state.lastFetchedAt.value) return false
  if (!state.list.value.length) return false
  return Date.now() - state.lastFetchedAt.value < CACHE_TTL
}

async function loadState(state: FileTypeState, category?: string, force = false) {
  if (!force && isCacheValid(state)) {
    return state.list.value
  }

  if (state.promise) {
    return state.promise
  }

  state.loading.value = true
  state.error.value = null

  const params =
    category || force
      ? {
          ...(category ? { category } : {}),
          ...(force ? { force: true } : {})
        }
      : undefined

  state.promise = getFileTypes(params)
    .then(list => {
      state.list.value = list
      state.lastFetchedAt.value = Date.now()
      state.error.value = null
      return list
    })
    .catch(error => {
      const message =
        error instanceof Error ? error.message : 'Failed to load file types'
      state.error.value = message
      throw error
    })
    .finally(() => {
      state.loading.value = false
      state.promise = null
    })

  return state.promise
}

function normalizeExtension(ext?: string | null) {
  if (!ext) return null
  const trimmed = ext.trim().toLowerCase()
  if (!trimmed) return null
  return trimmed.startsWith('.') ? trimmed : `.${trimmed}`
}

function extractExtensionFromName(name?: string | null) {
  if (!name) return null
  const normalized = name.trim().toLowerCase()
  if (!normalized) return null
  const lastDot = normalized.lastIndexOf('.')
  if (lastDot === -1) return null
  return normalized.slice(lastDot)
}

export function useFileTypes(initialCategory?: string) {
  const activeCategory = ref<string | undefined>(initialCategory)

  const state = computed(() => ensureState(categoryKey(activeCategory.value)))

  const fileTypes = computed(() => state.value.list.value)
  const loading = computed(() => state.value.loading.value)
  const error = computed(() => state.value.error.value)
  const lastFetchedAt = computed(() => state.value.lastFetchedAt.value)

  async function ensureLoaded(category?: string) {
    if (category !== undefined) {
      activeCategory.value = category || undefined
    }
    return loadState(state.value, activeCategory.value)
  }

  async function refresh() {
    return loadState(state.value, activeCategory.value, true)
  }

  function setCategory(category?: string) {
    activeCategory.value = category || undefined
  }

  function detectTypeByFile(file: File | { name?: string } | string | null) {
    if (!file) return null

    let fileName: string | undefined
    if (typeof file === 'string') {
      fileName = file
    } else if (file instanceof File) {
      fileName = file.name
    } else {
      fileName = file.name
    }

    const extension = extractExtensionFromName(fileName)
    if (!extension) return null

    return (
      fileTypes.value.find(type =>
        (type.extensions || []).some(
          ext => normalizeExtension(ext) === extension
        )
      ) || null
    )
  }

  const fileTypeMap = computed<FileTypeDictionary>(() => {
    const map: FileTypeDictionary = {}
    fileTypes.value.forEach(type => {
      map[type.id] = type
    })
    return map
  })

  const extensionWhitelist = computed(() => {
    const list = new Set<string>()
    fileTypes.value.forEach(type => {
      type.extensions?.forEach(ext => {
        const normalized = normalizeExtension(ext)
        if (normalized) {
          list.add(normalized)
        }
      })
    })
    return Array.from(list)
  })

  return {
    fileTypes,
    loading,
    error,
    lastFetchedAt,
    ensureLoaded,
    refresh,
    setCategory,
    detectTypeByFile,
    fileTypeMap,
    extensionWhitelist
  }
}

export type UseFileTypesReturn = ReturnType<typeof useFileTypes>

