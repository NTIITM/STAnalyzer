/**
 * 文件管理 API (TypeScript)
 */
import request from './request'
import type { FileType, RawFileType } from '../types/file'

// 文件信息
export interface FileInfo {
  fileId: string
  name: string
  size: number
  status: string
  time: string
  description?: string
  file_type?: FileType | string | null
  fileType?: FileType | string | null
  file_type_id?: string
}

// 上传文件响应
export interface UploadFileResponse {
  fileId: string
  file_id?: string
  file_type?: FileType | string | null
  fileType?: FileType | string | null
  file_type_id?: string
}

// 文件详情响应
export interface FileDetailResponse {
  metaData: Record<string, any>
  file_type?: FileType | string | null
}

// 更新文件信息参数
export interface UpdateFileInfoParams {
  name?: string
  description?: string
}

// 更新文件信息响应
export interface UpdateFileInfoResponse {
  fileId: string
  name: string
  description?: string
}

// 上传进度回调函数类型
export type UploadProgressCallback = (progress: number) => void

export interface UploadFileOptions {
  file: File
  fileTypeId: string
  onProgress?: UploadProgressCallback
  projectId?: string
  name?: string
  description?: string
}

export interface GetFileListParams {
  projectId?: string
}

export interface GetFileTypesParams {
  category?: string
  force?: boolean
}

// 预览选项
export interface PreviewFileOptions {
  maxRows?: number
  imageSize?: 'thumbnail' | 'medium' | 'full'
  maxSize?: number
}

const FILE_TYPE_CACHE_KEY_ALL = '__all__'
const fileTypesCache = new Map<string, { list: FileType[]; fetchedAt: number }>()

function normalizeExtension(value?: string | null): string | null {
  if (!value) return null
  const trimmed = value.trim()
  if (!trimmed) return null
  // 允许同时支持 `.csv` 和 `csv`，统一返回带点格式
  if (trimmed.startsWith('.')) {
    return trimmed
  }
  return `.${trimmed}`
}

function normalizeFileType(raw: RawFileType | null | undefined): FileType {
  const rawObj = raw as any
  const fallbackId = rawObj?.id || rawObj?.file_type_id || rawObj?.fileTypeId || 'unknown'
  const name =
    rawObj?.name ||
    rawObj?.file_type_name ||
    rawObj?.display_name ||
    rawObj?.displayName ||
    fallbackId
  const displayName =
    rawObj?.display_name ||
    rawObj?.displayName ||
    rawObj?.file_type_display_name ||
    name ||
    fallbackId
  const extensionsSource =
    rawObj?.extensions ??
    (Array.isArray(rawObj?.extension) ? rawObj?.extension : rawObj?.extension)

  const extensions = Array.isArray(extensionsSource)
    ? extensionsSource
        .map(item =>
          typeof item === 'string' ? normalizeExtension(item) : null
        )
        .filter((ext): ext is string => !!ext)
    : typeof extensionsSource === 'string'
      ? [normalizeExtension(extensionsSource)].filter(
          (ext): ext is string => !!ext
        )
      : []

  return {
    id: fallbackId,
    name: name || fallbackId,
    display_name: displayName || name || fallbackId,
    description:
      rawObj?.description ??
      rawObj?.file_type_description ??
      rawObj?.fileTypeDescription ??
      null,
    category:
      rawObj?.category ??
      rawObj?.file_type_category ??
      rawObj?.fileTypeCategory ??
      null,
    extensions,
    is_default:
      rawObj?.is_default ??
      rawObj?.default ??
      rawObj?.isDefault ??
      undefined
  }
}

function extractList<T>(payload: unknown): T[] {
  if (Array.isArray(payload)) {
    return payload
  }

  if (
    payload &&
    typeof payload === 'object' &&
    Array.isArray((payload as any).items)
  ) {
    return (payload as any).items
  }

  if (
    payload &&
    typeof payload === 'object' &&
    (payload as any).data &&
    Array.isArray((payload as any).data.items)
  ) {
    return (payload as any).data.items
  }

  if (
    payload &&
    typeof payload === 'object' &&
    Array.isArray((payload as any).data)
  ) {
    return (payload as any).data
  }

  return []
}

function cacheKeyForCategory(category?: string) {
  return category ? `category:${category}` : FILE_TYPE_CACHE_KEY_ALL
}

/**
 * 上传文件
 * @param options - 上传参数（包含文件类型 ID 等）
 */
export async function uploadFile(options: UploadFileOptions): Promise<UploadFileResponse> {
  const { file, fileTypeId, onProgress, projectId, name, description } = options
  if (!fileTypeId) {
    throw new Error('uploadFile: fileTypeId is required')
  }

  const formData = new FormData()
  formData.append('file', file)
  formData.append('fileTypeId', fileTypeId)
  if (name) {
    formData.append('name', name)
  }
  if (description) {
    formData.append('description', description)
  }
  
  // 将 project_id 作为 Query 参数传递（后端期望的是 Query 参数，别名是 projectId）
  const params: Record<string, string> = {}
  if (projectId) {
    params.projectId = projectId
  }
  
  return request({
    url: '/file/upload',
    method: 'POST',
    data: formData,
    params: params,  // Query 参数
    headers: {
      'Content-Type': 'multipart/form-data'
    },
    onUploadProgress: (progressEvent) => {
      if (onProgress && progressEvent.total) {
        const percentCompleted = Math.round(
          (progressEvent.loaded * 100) / progressEvent.total
        )
        onProgress(percentCompleted)
      }
    }
  }) as Promise<UploadFileResponse>
}

// 文件列表缓存（15秒 TTL，较短以保证数据新鲜度）
const FILE_LIST_CACHE_TTL = 15000
const fileListCache = new Map<string, { list: FileInfo[]; fetchedAt: number }>()

/**
 * 获取文件列表（带缓存）
 * @param params - 查询参数
 * @param force - 强制刷新缓存
 */
export async function getFileList(params?: GetFileListParams, force: boolean = false): Promise<FileInfo[]> {
  const cacheKey = params?.projectId || '__all__'

  if (!force) {
    const cached = fileListCache.get(cacheKey)
    if (cached && (Date.now() - cached.fetchedAt) < FILE_LIST_CACHE_TTL) {
      return cached.list
    }
  }

  const response = await request({
    url: '/file/list',
    method: 'GET',
    params: params?.projectId ? { projectId: params.projectId } : undefined
  })
  const list = extractList<FileInfo>(response)

  fileListCache.set(cacheKey, { list, fetchedAt: Date.now() })
  return list
}

/**
 * 清除文件列表缓存
 */
export function clearFileListCache(projectId?: string) {
  if (projectId) {
    fileListCache.delete(projectId)
  } else {
    fileListCache.clear()
  }
}

/**
 * 获取文件详情
 * @param fileId - 文件ID
 */
export async function getFileInfo(fileId: string): Promise<FileDetailResponse> {
  return request({
    url: `/file/${fileId}`,
    method: 'GET'
  }) as Promise<FileDetailResponse>
}

// /**
//  * 获取示例数据文件
//  */
// export async function getSampleFile(): Promise<Blob> {
//   const file_id = '0'
//   const response = await request({
//     url: `/file/download/${file_id}`,
//     method: 'GET',
//     responseType: 'blob',
//     // 大文件下载需要更长的超时时间（5分钟）
//     timeout: 300000
//   } as any)
//   console.log("getSampleFile response:", response)
//   return response as Blob
// }



/**
 * 更新文件信息
 * @param fileId - 文件ID
 * @param params - 更新参数（名称、描述等）
 */
export async function updateFileInfo(
  fileId: string,
  params: UpdateFileInfoParams
): Promise<UpdateFileInfoResponse> {
  return request({
    url: `/file/${fileId}`,
    method: 'PUT',
    data: params
  }) as Promise<UpdateFileInfoResponse>
}

/**
 * 删除文件
 * @param fileId - 文件ID
 */
export async function deleteFile(fileId: string): Promise<string> {
  return request({
    url: `/file/${fileId}`,
    method: 'DELETE'
  }) as Promise<string>
}

/**
 * 递归删除子文件（不删除自身）
 * @param fileId - 文件ID
 * @param projectId - 可选项目ID限定
 */
export async function deleteFileChildren(fileId: string, projectId?: string): Promise<string> {
  return request({
    url: `/file/${fileId}/children`,
    method: 'DELETE',
    params: projectId ? { projectId } : undefined
  }) as Promise<string>
}

/**
 * 预览文件（用于前端预览组件）
 * - 返回 Blob，用于在前端展示文件内容
 * - 后端可以返回优化后的内容（如缩略图、部分内容等）
 * - 接口路径: GET /file/preview/{fileId}
 * @param fileId - 文件ID
 * @param options - 可选参数（如行数限制、图片尺寸等）
 */
export async function previewFileById(fileId: string, options?: PreviewFileOptions): Promise<Blob> {
  const response = await request({
    url: `/file/preview/${fileId}`,
    method: 'GET',
    params: options,
    // 重要：告知 axios 我们期望的是二进制
    responseType: 'blob',
    // 预览文件超时时间（2分钟）
    timeout: 120000
  } as any)
  return response as Blob
}

/**
 * 下载文件（用于文件下载）
 * - 返回 Blob，调用方可触发浏览器保存
 * - 后端需支持 GET /file/download/{fileId} 返回完整文件，并带 Content-Disposition: attachment
 * - 接口路径: GET /file/download/{fileId}
 * @param fileId - 文件ID
 */
export async function downloadFileById(fileId: string): Promise<Blob> {
  const response = await request({
    url: `/file/download/${fileId}`,
    method: 'GET',
    // 重要：告知 axios 我们期望的是二进制
    responseType: 'blob',
    // 大文件下载需要更长的超时时间（5分钟）
    timeout: 300000
  } as any)
  return response as Blob
}

/**
 * 批量删除文件
 * @param fileIds - 文件ID数组
 * @returns 成功删除的文件ID列表
 */
export async function deleteFiles(fileIds: string[]): Promise<string[]> {
  const results = await Promise.allSettled(
    fileIds.map(fileId => deleteFile(fileId))
  )
  
  const successIds: string[] = []
  const failedIds: string[] = []
  
  results.forEach((result, index) => {
    if (result.status === 'fulfilled') {
      successIds.push(fileIds[index])
    } else {
      failedIds.push(fileIds[index])
    }
  })
  
  if (failedIds.length > 0) {
    console.warn('部分文件删除失败:', failedIds)
  }
  
  return successIds
}

/**
 * 获取文件类型列表
 */
export async function getFileTypes(params?: GetFileTypesParams): Promise<FileType[]> {
  const key = cacheKeyForCategory(params?.category)
  if (!params?.force && fileTypesCache.has(key)) {
    return fileTypesCache.get(key)!.list
  }

  const response = await request({
    url: '/file-types',
    method: 'GET',
    params: params?.category ? { category: params.category } : undefined
  })

  const normalized = extractList<RawFileType>(response)
    .filter(Boolean)
    .map(item => normalizeFileType(item))

  fileTypesCache.set(key, { list: normalized, fetchedAt: Date.now() })
  return normalized
}

/**
 * 清理缓存，供调试或强制刷新使用
 */
export function clearFileTypesCache(category?: string) {
  if (category) {
    fileTypesCache.delete(cacheKeyForCategory(category))
  } else {
    fileTypesCache.clear()
  }
}
