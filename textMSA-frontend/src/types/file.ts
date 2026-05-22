/**
 * 文件类型相关公共定义
 */
export interface FileType {
  id: string
  name: string
  display_name: string
  description?: string | null
  category?: string | null
  extensions: string[]
  is_default?: boolean
}

export type FileTypeDictionary = Record<string, FileType>

export type RawFileType =
  | FileType
  | {
      id?: string
      file_type_id?: string
      fileTypeId?: string
      name?: string
      file_type_name?: string
      display_name?: string
      displayName?: string
      file_type_display_name?: string
      description?: string | null
      file_type_description?: string | null
      category?: string | null
      file_type_category?: string | null
      extensions?: string[] | string
      extension?: string
      is_default?: boolean
    }

