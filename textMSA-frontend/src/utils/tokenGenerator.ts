/**
 * Token 生成工具
 * 生成唯一的 Token 用于用户认证
 */

/**
 * 生成唯一 Token
 * 格式: timestamp-random-uuid
 * 示例: 1704067200000-a1b2c3d4-e5f6-7890-abcd-ef1234567890
 */
export function generateToken(): string {
  const timestamp = Date.now()
  const random = Math.random().toString(36).substring(2, 10)
  
  // 使用 crypto.randomUUID() 如果可用，否则使用替代方案
  let uuid: string
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    uuid = crypto.randomUUID()
  } else {
    // 兼容方案：生成类似 UUID 的字符串
    uuid = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
      const r = (Math.random() * 16) | 0
      const v = c === 'x' ? r : (r & 0x3) | 0x8
      return v.toString(16)
    })
  }
  
  return `${timestamp}-${random}-${uuid}`
}

