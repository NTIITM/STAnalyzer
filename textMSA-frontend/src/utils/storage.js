/**
 * 本地存储工具
 * 用于持久化数据列表和对话历史
 */

const STORAGE_KEY_DATA = 'spatial_visualization_data'

/**
 * 保存数据列表
 */
export function saveDataList(dataList) {
  try {
    const dataToSave = dataList.map(data => ({
      id: data.id,
      name: data.name,
      uploadTime: data.uploadTime,
      fileId: data.fileId,
      fileInfo: data.fileInfo
    }))
    localStorage.setItem(STORAGE_KEY_DATA, JSON.stringify(dataToSave))
    return true
  } catch (error) {
    console.error('保存数据列表失败:', error)
    return false
  }
}

/**
 * 加载数据列表
 */
export function loadDataList() {
  try {
    const data = localStorage.getItem(STORAGE_KEY_DATA)
    return data ? JSON.parse(data) : []
  } catch (error) {
    console.error('加载数据列表失败:', error)
    return []
  }
}

/**
 * 保存对话历史
 */
/**
 * 清除所有数据
 */
export function clearAllData() {
  try {
    localStorage.removeItem(STORAGE_KEY_DATA)
    return true
  } catch (error) {
    console.error('清除数据失败:', error)
    return false
  }
}

