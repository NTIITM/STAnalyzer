const normalizeEnvValue = (value?: string) => (value ?? '').trim()

const envDefaultId =
  normalizeEnvValue(import.meta.env.VITE_DEFAULT_FILE_TYPE_ID) ||
  normalizeEnvValue(import.meta.env.VITE_FALLBACK_FILE_TYPE_ID)

/**
 * 默认（回退）文件类型 ID。
 *
 * - 可通过 `VITE_DEFAULT_FILE_TYPE_ID` 或 `VITE_FALLBACK_FILE_TYPE_ID` 配置
 * - 若两者都未设置，则返回 `'type-unknown'` 作为兜底值
 */
export const FALLBACK_FILE_TYPE_ID = envDefaultId || 'type-unknown'

/**
 * 获取当前环境配置的文件类型 ID；缺失时返回 `null`
 */
export function getConfiguredFileTypeId(): string | null {
  return envDefaultId || null
}

