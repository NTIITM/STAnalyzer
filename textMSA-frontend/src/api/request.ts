/**
 * API 请求封装 (TypeScript)
 * 统一处理 axios 配置、token 管理、错误处理
 */
import axios, { AxiosInstance, InternalAxiosRequestConfig, AxiosResponse, AxiosError } from 'axios'

// 环境配置
const isTest = import.meta.env.MODE === 'test' || import.meta.env.VITE_APP_ENV === 'test'
const isDev = import.meta.env.MODE === 'development' || import.meta.env.DEV
const useMock = import.meta.env.VITE_USE_MOCK === 'true' || import.meta.env.VITE_USE_MOCK === '1'
const DEFAULT_TEST_TOKEN = 'test_123'

axios.defaults.withCredentials = true

// Token 存储键名
const TOKEN_KEY = 'autost_mas_token'
const USER_INFO_KEY = 'autost_mas_user_info'

// 用户信息接口
export interface UserInfo {
  userId: string
  username: string
  email?: string
}

// API 响应格式
export interface ApiResponse<T = any> {
  code: number
  data: T
  message?: string
}

// 自定义错误类型
export class ApiError extends Error {
  code: number
  status?: number
  data?: any

  constructor(message: string, code: number, status?: number, data?: any) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
    this.data = data
  }
}

/**
 * Token 管理工具
 */
export const tokenManager = {
  /**
   * 获取 token
   */
  getToken(): string | null {
    // 测试环境下返回默认 token
    if (isTest) {
      const storedToken = localStorage.getItem(TOKEN_KEY)
      return storedToken || DEFAULT_TEST_TOKEN
    }
    return localStorage.getItem(TOKEN_KEY)
  },

  /**
   * 设置 token
   */
  setToken(token: string | null): void {
    if (token) {
      localStorage.setItem(TOKEN_KEY, token)
    } else {
      localStorage.removeItem(TOKEN_KEY)
    }
  },

  /**
   * 移除 token
   */
  removeToken(): void {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_INFO_KEY)
  },

  /**
   * 获取用户信息
   */
  getUserInfo(): UserInfo | null {
    const userInfo = localStorage.getItem(USER_INFO_KEY)
    return userInfo ? JSON.parse(userInfo) : null
  },

  /**
   * 设置用户信息
   */
  setUserInfo(userInfo: UserInfo | null): void {
    if (userInfo) {
      localStorage.setItem(USER_INFO_KEY, JSON.stringify(userInfo))
    } else {
      localStorage.removeItem(USER_INFO_KEY)
    }
  },

  /**
   * 检查是否已登录
   */
  isAuthenticated(): boolean {
    return !!this.getToken()
  }
}

// 预加载 mock 模块（开发环境）
let codegenMockModule: typeof import('./__mocks__/codegenDev') | null = null
if (isDev && useMock) {
  import('./__mocks__/codegenDev').then(module => {
    codegenMockModule = module
    console.log('[Mock] Codegen mock 模块已加载')
  }).catch(err => {
    console.warn('[Mock] 加载 mock 模块失败:', err)
  })
}

// 创建 axios 实例
const request: AxiosInstance = axios.create({
  // 生产环境：通过 nginx，走 https://www.sdu-idea.cn/STAnalyzer/api/xxx
  // 开发环境：由 Vite 代理，将 /STAnalyzer/api/xxx 转发为 http://127.0.0.1:8000/api/xxx
  baseURL: '/STAnalyzer/api',
  // 将超时时间从 30 秒提高到 10 分钟，避免大文件上传在前端超时
  timeout: 600000,   // 10 分钟超时（单位：毫秒）
  headers: {
    'Content-Type': 'application/json'
  },
  // 开发环境 mock adapter
  adapter: isDev && useMock ? async (config) => {
    const url = config.url || ''
    const method = config.method?.toUpperCase() || 'GET'
    
    // 只拦截 codegen API
    if (url.includes('/codegen/')) {
      try {
        // 动态加载 mock 模块（如果还未加载）
        let mockModule = codegenMockModule
        if (!mockModule) {
          mockModule = await import('./__mocks__/codegenDev')
          codegenMockModule = mockModule
        }
        
        const mockFn = mockModule.matchCodegenMock(url, method)
        
        if (mockFn) {
          console.log(`[Mock] 拦截请求: ${method} ${url}`)
          
          // 调用 mock 函数
          const mockData = await mockFn(config.data)
          
          // 返回模拟响应
          return Promise.resolve({
            data: {
              code: 200,
              data: mockData,
              message: 'success'
            },
            status: 200,
            statusText: 'OK',
            headers: {},
            config: config as any,
            request: {}
          } as AxiosResponse)
        }
      } catch (error) {
        console.warn('[Mock] Mock 执行失败，使用真实 API:', error)
      }
    }
    
    // 非 mock 请求，使用默认 adapter
    // 移除 adapter 配置，让 axios 使用默认的 adapter
    const configWithoutAdapter = { ...config }
    delete (configWithoutAdapter as any).adapter
    // 使用原始的 axios 实例发送请求（不设置 adapter）
    return axios(configWithoutAdapter)
  } : undefined
})

// 请求拦截器 - 添加 token
request.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = tokenManager.getToken()
    
    if (token && config.headers) {
      // 优先使用 Authorization Bearer 方式（根据 Postman 集合）
      config.headers.Authorization = `Bearer ${token}`
      // 也可以同时设置 token 字段（如果后端需要）
      config.headers.token = token
    }
    return config
  },
  (error: AxiosError) => {
    console.error('请求错误:', error)
    return Promise.reject(error)
  }
)

// 响应拦截器 - 统一处理错误和 mock
request.interceptors.response.use(
  (response: AxiosResponse<ApiResponse>) => {
    // 直接透传二进制下载（如文件下载）
    // 若调用方设置了 responseType: 'blob'，后端不会返回 { code, data } 包装
    if (
      (response.config as any)?.responseType === 'blob' ||
      (typeof Blob !== 'undefined' && response.data instanceof Blob)
    ) {
      // 不再解包，直接返回原始数据
      // 调用方负责处理文件名等信息（可从 Content-Disposition 解析）
      // 注意：直接返回 response.data，不要包装在 Promise.resolve 中
      return response.data as unknown as any
    }
    
    // 对于非 blob 响应，检查是否是包装的 JSON 格式
    // 如果 response.data 不是对象，直接返回
    if (typeof response.data !== 'object' || response.data === null) {
      return response.data
    }
    
    const { code, data, message } = response.data
    
    // 根据后端响应格式处理
    // 200: 成功
    // 201: 创建成功（HTTP标准，用于POST创建资源）
    // 2xx范围内的其他状态码也视为成功
    if (code === 200 || code === 201 || (code >= 200 && code < 300)) {
      return Promise.resolve(data || response.data)
    } else {
      // 业务错误
      const error = new ApiError(message || '请求失败', code)
      error.data = data
      return Promise.reject(error)
    }
  },
  (error: AxiosError<ApiResponse>) => {
    // HTTP 错误
    if (error.response) {
      const { status, data } = error.response
      
      switch (status) {
        case 401:
          // 未授权，清除 token 并跳转登录
          tokenManager.removeToken()
          // 触发登录跳转事件
          window.dispatchEvent(new CustomEvent('auth:unauthorized'))
          break
        case 403:
          console.error('权限不足')
          break
        case 404:
          console.error('资源不存在')
          break
        case 500:
          console.error('服务器错误')
          break
        default:
          console.error('请求失败:', status)
      }
      
      // 优先使用 detail 字段（FastAPI 标准错误格式）
      // 然后使用 message 字段，最后使用默认消息
      // 注意：如果 data 是 Blob 或其他非对象类型，需要特殊处理
      let errorMessage = `请求失败 (${status})`
      let errorCode = status || 0
      
      if (data && typeof data === 'object' && !(data instanceof Blob)) {
        errorMessage = data.detail || data.message || errorMessage
        errorCode = data.code || errorCode
      } else if (typeof data === 'string') {
        errorMessage = data
      }
      
      const customError = new ApiError(
        errorMessage,
        errorCode,
        status,
        data
      )
      
      return Promise.reject(customError)
    } else if (error.request) {
      // 请求已发送但没有收到响应
      console.error('网络错误，请检查网络连接')
      return Promise.reject(new ApiError('网络错误，请检查网络连接', 0))
    } else {
      // 请求配置错误
      console.error('请求配置错误:', error.message)
      return Promise.reject(new ApiError(error.message || '请求配置错误', 0))
    }
  }
)

export default request

/**
 * 构造文件下载直链 URL（带 token），用于让浏览器直接处理下载并显示系统进度条
 *
 * 使用示例：
 *   const url = getFileDownloadUrl(fileId)
 *   window.open(url) // 或 <a :href="url">下载</a>
 */
export function getFileDownloadUrl(fileId: string): string {
  const token = tokenManager.getToken()

  // 与 axios 的 baseURL 保持一致：/STAnalyzer/api
  const basePath = '/STAnalyzer/api'
  const encodedId = encodeURIComponent(fileId)
  let url = `${basePath}/file/download/${encodedId}`

  if (token) {
    const encodedToken = encodeURIComponent(token)
    url += `?token=${encodedToken}`
  }

  return url
}

/**
 * 直接在浏览器中打开文件下载（新窗口 / 新标签），使用浏览器自带下载进度条
 */
export function openFileDownload(fileId: string): void {
  const url = getFileDownloadUrl(fileId)
  window.open(url, '_blank')
}
