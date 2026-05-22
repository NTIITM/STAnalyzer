/**
 * Simple in-memory cache with TTL support.
 *
 * Provides helpers to read/write cached values and determine expiry.
 * Intentionally lightweight — no external dependencies.
 */

export interface CacheEntry<T> {
  value: T
  /**
   * Unix timestamp in milliseconds when the entry becomes stale.
   */
  expiresAt: number
}

export interface TimedCacheOptions {
  /**
   * Time-to-live for each cache entry in milliseconds.
   */
  ttl: number
}

export interface TimedCacheControls<K, V> {
  get(key: K): V | null
  set(key: K, value: V, ttlOverride?: number): void
  delete(key: K): void
  clear(): void
  peek(key: K): CacheEntry<V> | undefined
  isExpired(entry: CacheEntry<V>): boolean
}

/**
 * createTimedCache returns a minimal key-value cache with TTL semantics.
 * Consumers may optionally supply a per-entry TTL override when setting values.
 */
export function createTimedCache<K, V>(options: TimedCacheOptions): TimedCacheControls<K, V> {
  const store = new Map<K, CacheEntry<V>>()

  function resolveTtl(ttlOverride?: number): number {
    return typeof ttlOverride === 'number' && ttlOverride >= 0 ? ttlOverride : options.ttl
  }

  function get(key: K): V | null {
    const entry = store.get(key)
    if (!entry) {
      return null
    }
    if (entry.expiresAt <= Date.now()) {
      store.delete(key)
      return null
    }
    return entry.value
  }

  function set(key: K, value: V, ttlOverride?: number): void {
    const ttl = resolveTtl(ttlOverride)
    store.set(key, {
      value,
      expiresAt: Date.now() + ttl
    })
  }

  function deleteKey(key: K): void {
    store.delete(key)
  }

  function clear(): void {
    store.clear()
  }

  function peek(key: K): CacheEntry<V> | undefined {
    return store.get(key)
  }

  function isExpired(entry: CacheEntry<V>): boolean {
    return entry.expiresAt <= Date.now()
  }

  return {
    get,
    set,
    delete: deleteKey,
    clear,
    peek,
    isExpired
  }
}

