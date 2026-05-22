import { createTimedCache } from '../utils/cache'
import {
  DEFAULT_PROJECT_SERVICES_LIMIT,
  listProjectServices,
  type ProjectService,
  type ProjectServicesResponse
} from '../services/services'

export type { ProjectService } from '../services/services'

const DEFAULT_CACHE_TTL = 60_000
const DEFAULT_SKIP = 0

type CacheKey = string

interface CacheValue {
  response: ProjectServicesResponse
  fetchedAt: number
}

interface InFlightEntry {
  promise: Promise<ProjectServicesResult>
  controller: AbortController
}

const cache = createTimedCache<CacheKey, CacheValue>({ ttl: DEFAULT_CACHE_TTL })
const inFlightRequests = new Map<CacheKey, InFlightEntry>()

const env = (typeof import.meta !== 'undefined' && (import.meta as any)?.env) || {}
const DEFAULT_CACHE_ENABLED = env?.VITE_ENABLE_SERVICES_CACHE !== 'false'
let cacheEnabled = DEFAULT_CACHE_ENABLED

function buildCacheKey(projectId: string, skip: number, limit: number): CacheKey {
  return `${projectId}::${skip}::${limit}`
}

function ensureProjectId(projectId: string): void {
  if (!projectId) {
    throw new Error('projectId is required to fetch services')
  }
}

export interface FetchProjectServicesOptions {
  projectId: string
  skip?: number
  limit?: number
  force?: boolean
  ttl?: number
  signal?: AbortSignal
}

export interface ProjectServicesResult extends ProjectServicesResponse {
  services: ProjectService[]
  fromCache: boolean
  fetchedAt: number
}

function toResult(cacheValue: CacheValue, fromCache: boolean): ProjectServicesResult {
  return {
    ...cacheValue.response,
    services: cacheValue.response.services ?? [],
    fromCache,
    fetchedAt: cacheValue.fetchedAt
  }
}

function linkAbortSignals(source: AbortController, external?: AbortSignal): void {
  if (!external) {
    return
  }
  if (external.aborted) {
    source.abort()
    return
  }
  const abort = () => {
    source.abort()
    external.removeEventListener('abort', abort)
  }
  external.addEventListener('abort', abort, { once: true })
}

/**
 * Fetch project services with caching and deduplication.
 * Subsequent requests within the TTL resolve from cache unless `force` is passed.
 */
export function isProjectServicesCacheEnabled(): boolean {
  return cacheEnabled
}

export function setProjectServicesCacheEnabled(enabled: boolean): void {
  cacheEnabled = enabled
  if (!enabled) {
    cache.clear()
    inFlightRequests.forEach((entry) => entry.controller.abort())
    inFlightRequests.clear()
  }
}

export async function fetchProjectServices(
  options: FetchProjectServicesOptions
): Promise<ProjectServicesResult> {
  const {
    projectId,
    skip = DEFAULT_SKIP,
    limit = DEFAULT_PROJECT_SERVICES_LIMIT,
    force = false,
    ttl,
    signal
  } = options

  ensureProjectId(projectId)
  const cacheKey = buildCacheKey(projectId, skip, limit)

  if (!force && cacheEnabled) {
    const cached = cache.get(cacheKey)
    if (cached) {
      return toResult(cached, true)
    }
  }

  const existing = inFlightRequests.get(cacheKey)
  if (existing) {
    if (force || !cacheEnabled) {
      existing.controller.abort()
      inFlightRequests.delete(cacheKey)
    } else {
      linkAbortSignals(existing.controller, signal)
      return existing.promise
    }
  }

  const controller = new AbortController()
  linkAbortSignals(controller, signal)

  const requestPromise = listProjectServices({
    projectId,
    skip,
    limit,
    signal: controller.signal
  })
    .then((response) => {
      const cacheValue: CacheValue = {
        response,
        fetchedAt: Date.now()
      }
      if (cacheEnabled) {
        cache.set(cacheKey, cacheValue, ttl)
      }
      return toResult(cacheValue, false)
    })
    .finally(() => {
    const tracked = inFlightRequests.get(cacheKey)
    if (tracked && tracked.controller === controller) {
      inFlightRequests.delete(cacheKey)
    }
  })

  const trackedEntry: InFlightEntry = {
    promise: requestPromise,
    controller
  }
  inFlightRequests.set(cacheKey, trackedEntry)

  return requestPromise
}

/**
 * Retrieve the cached services for a project if available.
 */
export function getCachedProjectServices(
  projectId: string,
  skip = DEFAULT_SKIP,
  limit = DEFAULT_PROJECT_SERVICES_LIMIT
): ProjectServicesResult | null {
  if (!cacheEnabled) {
    return null
  }
  ensureProjectId(projectId)
  const cacheKey = buildCacheKey(projectId, skip, limit)
  const cached = cache.get(cacheKey)
  return cached ? toResult(cached, true) : null
}

/**
 * Manually invalidate cached services.
 * If projectId is omitted, all cache entries are cleared.
 */
export function invalidateProjectServicesCache(
  projectId?: string,
  skip = DEFAULT_SKIP,
  limit = DEFAULT_PROJECT_SERVICES_LIMIT
): void {
  if (!projectId) {
    cache.clear()
    inFlightRequests.forEach((entry) => entry.controller.abort())
    inFlightRequests.clear()
    return
  }
  const cacheKey = buildCacheKey(projectId, skip, limit)
  cache.delete(cacheKey)
  const inFlight = inFlightRequests.get(cacheKey)
  if (inFlight) {
    inFlight.controller.abort()
    inFlightRequests.delete(cacheKey)
  }
}

/**
 * Abort in-flight fetch for the given project (and pagination tuple).
 */
export function abortProjectServicesRequest(
  projectId: string,
  skip = DEFAULT_SKIP,
  limit = DEFAULT_PROJECT_SERVICES_LIMIT
): void {
  ensureProjectId(projectId)
  const cacheKey = buildCacheKey(projectId, skip, limit)
  const entry = inFlightRequests.get(cacheKey)
  if (entry) {
    entry.controller.abort()
    inFlightRequests.delete(cacheKey)
  }
}


