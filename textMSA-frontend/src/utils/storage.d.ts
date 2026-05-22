/**
 * storage.js 类型定义
 */
export interface DataItem {
  id: string
  name: string
  uploadTime: string
  fileId?: string | null
  fileInfo?: any
}

export function saveDataList(dataList: DataItem[]): boolean
export function loadDataList(): DataItem[]
export function clearAllData(): boolean

