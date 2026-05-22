/**
 * 文件类型检测和分类工具
 */
import type { FileType } from '../types/file'

export type FileCategory = 'spreadsheet' | 'image' | 'text' | 'json' | 'unknown'

export interface FileTypeInfo {
  category: FileCategory
  extension: string
  mimeType?: string
  canPreview: boolean
}

// 支持预览的文件扩展名
const PREVIEWABLE_EXTENSIONS = {
  spreadsheet: ['csv', 'xlsx', 'xls', 'tsv'],
  image: ['png', 'jpg', 'jpeg', 'gif', 'svg', 'webp', 'bmp', 'ico'],
  text: ['txt', 'md', 'log'],
  json: ['json']
} as const

/**
 * 从文件名或文件类型获取扩展名
 */
export function getFileExtension(fileNameOrType: string): string {
  if (!fileNameOrType) return ''
  
  // 如果包含点，提取扩展名
  if (fileNameOrType.includes('.')) {
    const parts = fileNameOrType.toLowerCase().split('.')
    return parts[parts.length - 1]
  }
  
  // 否则直接返回（可能是 file_type 字段的值）
  return fileNameOrType.toLowerCase()
}

/**
 * 检测文件类型信息
 */
export function detectFileType(fileNode: {
  filename?: string
  file_type?: string | FileType | null
  fileName?: string
  file_name?: string
}): FileTypeInfo {
  const fileName = fileNode.filename || fileNode.fileName || fileNode.file_name || ''
  const rawFileType = fileNode.file_type
  const fileTypeString =
    typeof rawFileType === 'string'
      ? rawFileType
      : rawFileType?.name ||
        rawFileType?.display_name ||
        rawFileType?.id ||
        ''
  
  const extension = getFileExtension(fileName || fileTypeString)
  
  // 检查是否支持预览
  for (const [category, extensions] of Object.entries(PREVIEWABLE_EXTENSIONS)) {
    if (extensions.includes(extension)) {
      return {
        category: category as FileCategory,
        extension,
        canPreview: true
      }
    }
  }
  
  return {
    category: 'unknown',
    extension,
    canPreview: false
  }
}

/**
 * 判断文件是否支持预览
 */
export function canPreviewFile(fileNode: any): boolean {
  return detectFileType(fileNode).canPreview
}

/**
 * 判断是否为 h5ad 文件
 */
export function isH5adFile(fileName?: string): boolean {
  if (!fileName) return false
  return fileName.toLowerCase().endsWith('.h5ad')
}

/**
 * 判断是否为隐藏系统文件（如 gen- 开头的文件）
 */
export function isHiddenSystemFile(fileName?: string): boolean {
  if (!fileName) return true
  return fileName.trim().toLowerCase().startsWith('gen')
}

/**
 * 判断是否为有效的分析结果文件（如差异基因结果、细胞间通讯结果）
 */
export function isAnalysisResultFile(fileName: string, fileTypeId?: string | null): boolean {
  const name = (fileName || '').trim().toLowerCase()
  const isDgeCsv = fileTypeId === 'dge_results_csv' || (name.endsWith('.csv') && name.includes('dge'))
  const isLigrec = fileTypeId === 'ligrec_interactions_csv'
  return isDgeCsv || isLigrec
}

