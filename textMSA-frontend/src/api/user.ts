/**
 * 用户管理 API (TypeScript)
 */
import request from './request'
import { tokenManager } from './request'

// 注册参数
export interface RegisterParams {
  username: string
  password: string
  email: string
}

// 注册响应
export interface RegisterResponse {
  userId: string
}

// 登录参数
export interface LoginParams {
  token?: string  // 可选：如果提供token，使用token登录；否则自动创建用户
  username?: string  // 已废弃，保留用于兼容性
  password?: string  // 已废弃，保留用于兼容性
}

// 登录响应（根据API文档：data字段包含token, user_id, username）
export interface LoginResponse {
  token: string
  user_id: string
  username: string | null
}

// 用户信息响应
export interface UserInfoResponse {
  username: string
  userId: string
  email?: string
}

export interface UpdateProfileParams {
  username?: string
  email?: string
}

export interface ChangePasswordParams {
  currentPassword: string
  newPassword: string
}

/**
 * 用户注册
 */
export async function register(params: RegisterParams): Promise<RegisterResponse> {
  return request({
    url: '/user/register',
    method: 'POST',
    data: {
      username: params.username,
      password: params.password,
      email: params.email
    }
  }) as Promise<RegisterResponse>
}

/**
 * 用户登录
 * 支持三种方式：
 * 1. 使用token登录：传入 { token: "..." }
 * 2. 自动创建用户：传入 {} 或不传参数
 * 3. 使用 Cookie 登录：后端会自动读取浏览器中的认证 Cookie 进行登录
 * 
 * 登录成功后会自动保存 token 和用户信息
 */
export async function login(params: LoginParams = {}): Promise<LoginResponse> {
  try {
    // 构建请求体：如果有token则使用token，否则发送空对象（自动创建用户）
    const requestBody: { token?: string } = {}
    if (params.token) {
      requestBody.token = params.token
    }
    
    const data = await request({
      url: '/user/login',
      method: 'POST',
      data: requestBody
    }) as LoginResponse
    
    // 保存 token 和用户信息
    if (data.token) {
      tokenManager.setToken(data.token)
    }
    if (data.user_id) {
      tokenManager.setUserInfo({
        userId: data.user_id,
        username: data.username || 'default user'
      })
    }
    
    return data
  } catch (error) {
    // 登录失败，清除可能的旧 token
    tokenManager.removeToken()
    throw error
  }
}

/**
 * 自动登录
 * 尝试使用保存的token登录，如果没有token或token无效则自动创建新用户
 */
export async function autoLogin(): Promise<LoginResponse> {
  const savedToken = tokenManager.getToken()
  
  try {
    // 如果有保存的token，先尝试使用token登录
    if (savedToken) {
      const result = await login({ token: savedToken })
      return result
    } else {
      // 没有token，直接自动创建用户
      const result = await login({})
      return result
    }
  } catch (error: any) {
    // 如果token无效（401错误），清除token并重新尝试登录（自动创建用户）
    if (error?.status === 401 || error?.code === 401) {
      tokenManager.removeToken()
      // 重新尝试登录（会自动创建新用户）
      const result = await login({})
      return result
    }
    // 其他错误直接抛出
    throw error
  }
}

/**
 * 使用 Cookie 登录
 * 后端会自动读取浏览器中的认证 Cookie 进行登录
 */
export async function loginWithCookie(): Promise<LoginResponse> {
  try {
    const data = await request({
      url: '/user/login',
      method: 'POST',
      data: {}
    }) as LoginResponse
    
    if (data.token) {
      tokenManager.setToken(data.token)
    }
    if (data.user_id) {
      tokenManager.setUserInfo({
        userId: data.user_id,
        username: data.username || 'default user'
      })
    }
    
    return data
  } catch (error) {
    tokenManager.removeToken()
    throw error
  }
}


/**
 * 用户登出
 */
export function logout(): void {
  tokenManager.removeToken()
  // 触发登出事件
  window.dispatchEvent(new CustomEvent('auth:logout'))
}

/**
 * 获取用户信息
 */
export async function getUserInfo(): Promise<UserInfoResponse> {
  return request({
    url: '/user/info',
    method: 'GET'
  }) as Promise<UserInfoResponse>
}

/**
 * 更新用户信息
 */
export async function updateUserProfile(params: UpdateProfileParams): Promise<UserInfoResponse> {
  if (!params.username && !params.email) {
    throw new Error('请至少提供用户名或邮箱')
  }

  const data = await request({
    url: '/user/profile',
    method: 'PUT',
    data: params
  }) as UserInfoResponse

  // 同步更新本地缓存
  if (data?.userId) {
    tokenManager.setUserInfo({
      userId: data.userId,
      username: data.username,
      email: data.email
    })
  }

  return data
}

/**
 * 修改密码
 */
export async function changePassword(params: ChangePasswordParams): Promise<{ updated: boolean }> {
  return request({
    url: '/user/password',
    method: 'PUT',
    data: {
      currentPassword: params.currentPassword,
      newPassword: params.newPassword
    }
  }) as Promise<{ updated: boolean }>
}

/**
 * 检查登录状态
 */
export function isAuthenticated(): boolean {
  return tokenManager.isAuthenticated()
}

/**
 * 获取当前用户ID
 */
export function getCurrentUserId(): string | null {
  const userInfo = tokenManager.getUserInfo()
  return userInfo?.userId || null
}

/**
 * 获取当前用户名
 */
export function getCurrentUsername(): string | null {
  const userInfo = tokenManager.getUserInfo()
  return userInfo?.username || null
}
