/**
 * 节点操作选项配置
 * 根据文件信息动态生成操作选项
 */

import { canPreviewFile, detectFileType } from '../utils/fileType'
import { openFileDownload } from '../api/request'

/**
 * 操作选项接口
 */
export interface NodeActionOption {
  id: string
  label: string
  icon?: string
  action: (fileNode: any) => void | Promise<void>
  disabled?: (fileNode: any) => boolean
  danger?: boolean
  divider?: boolean // 是否在该选项前添加分隔线
  category?: 'file' | 'fileAnalysis' | 'analysis' // 操作类别：文件操作、文件分析或分析操作
}

/**
 * 操作选项分组接口
 */
export interface NodeActionGroups {
  fileOperations: NodeActionOption[]
  fileAnalysis: NodeActionOption[]
  analysisOperations: NodeActionOption[]
}

/**
 * 节点操作函数接口
 */
export interface NodeActionHandlers {
  triggerAnalysisComponent?: (componentId: string, fileId: string) => void
  showEditFileDialog?: (fileId: string | any) => void // 支持 fileId（字符串）或 dataItem（向后兼容）
  deleteFileNode?: (fileId: string, fileName?: string) => Promise<void>
  deleteFileChildren?: (fileId: string, fileName?: string) => Promise<void>
  showServiceExecuteDialog?: (service: any, fileId: string) => void
  showFilePreview?: (fileId: string) => void
  addFileToContext?: (fileId: string, fileName: string) => void // 加入对话上下文
}

/**
 * 翻译函数类型
 */
type TranslateFunction = (key: string, params?: Record<string, any>) => string

/**
 * 根据文件节点信息生成操作选项（分组）
 * @param fileNode - 文件节点信息
 * @param handlers - 操作函数处理器（必需，通过 provide/inject 传递）
 * @param services - Service列表（可选，用于添加到进一步分析）
 * @param t - 翻译函数（可选，用于国际化）
 * @returns 分组的操作选项
 */
export function getNodeActionOptions(
  fileNode: any, 
  handlers: NodeActionHandlers,
  services?: any[],
  t?: TranslateFunction
): NodeActionGroups {
  const fileOperations: NodeActionOption[] = []
  const fileAnalysis: NodeActionOption[] = []
  const analysisOperations: NodeActionOption[] = []

  // ============ 文件操作 ============
  
  // 0. 预览文件（如果支持）
  if (canPreviewFile(fileNode)) {
    const fileTypeInfo = detectFileType(fileNode)
    let icon = '📄'
    if (fileTypeInfo.category === 'image') {
      icon = '🖼️'
    } else if (fileTypeInfo.category === 'spreadsheet') {
      icon = '📊'
    } else if (fileTypeInfo.category === 'text') {
      icon = '📄'
    }
    fileOperations.push({
      id: 'preview-file',
      label: t ? t('analysis.nodeMenu.previewFile') : '预览文件',
      icon: icon,
      category: 'file',
      action: (node) => {
        const fileId = (node as any).id || (node as any).file_id
        // 触发预览对话框（只传递 fileId，完整信息从 filesDict 获取）
        if (handlers.showFilePreview) {
          handlers.showFilePreview(fileId)
        } else {
          const errorMsg = t ? t('analysis.nodeMenu.errors.previewFileNotInitialized') : '预览文件功能未初始化'
          const errorDetail = t ? t('analysis.nodeMenu.errors.previewFileNotInitializedDetail') : '预览文件功能未初始化：handlers.showFilePreview 缺失'
          console.error(errorDetail)
          alert(errorMsg)
        }
      }
    })
  }
  
  // 1. 下载文件：使用带 token 的直链下载，浏览器显示系统下载进度条
  fileOperations.push({
    id: 'download',
    label: t ? t('analysis.nodeMenu.downloadFile') : '下载文件',
    icon: '⬇️',
    category: 'file',
    action: async (node) => {
      try {
        const fileId = (node as any).id || (node as any).file_id
        if (!fileId) {
          const errorMsg = t ? t('analysis.nodeMenu.errors.invalidFileId') : '无效的文件ID'
          throw new Error(errorMsg)
        }
        // 直接打开新标签页进行下载，使用浏览器自带下载进度条
        openFileDownload(fileId)
      } catch (err) {
        const errorMsg = t ? t('analysis.nodeMenu.errors.downloadFailed') : '下载失败，请稍后重试'
        console.error(errorMsg, err)
        alert(errorMsg)
      }
    }
  })

  // 2. 编辑文件信息
  if (fileNode.file_id) {
    fileOperations.push({
      id: 'edit-file',
      label: t ? t('analysis.nodeMenu.editFile') : '编辑文件信息',
      icon: '✏️',
      category: 'file',
      action: (node) => {
        // 只传递 fileId，完整信息从 filesDict 获取
        const fileId = (node as any).file_id || (node as any).id
        // 调用编辑函数（只传递 fileId）
        if (handlers.showEditFileDialog) {
          handlers.showEditFileDialog(fileId)
        } else {
          const errorMsg = t ? t('analysis.nodeMenu.errors.editFileNotInitialized') : '编辑文件功能未初始化'
          const errorDetail = t ? t('analysis.nodeMenu.errors.editFileNotInitializedDetail') : '编辑文件功能未初始化：handlers.showEditFileDialog 缺失'
          console.error(errorDetail)
          alert(errorMsg)
        }
      }
    })
  }

  // 3. 加入对话上下文
  if (fileNode.file_id) {
    fileOperations.push({
      id: 'add-to-context',
      label: t ? t('analysis.nodeMenu.addToContext') : '加入对话上下文',
      icon: '💬',
      category: 'file',
      action: (node) => {
        const fileId = (node as any).file_id || (node as any).id
        const fileName = (node as any).filename || (node as any).file_name || (node as any).fileName || fileId
        if (handlers.addFileToContext) {
          handlers.addFileToContext(fileId, fileName)
        } else {
          const errorMsg = t ? t('analysis.nodeMenu.errors.addToContextNotInitialized') : '加入对话上下文功能未初始化'
          const errorDetail = t ? t('analysis.nodeMenu.errors.addToContextNotInitializedDetail') : '加入对话上下文功能未初始化：handlers.addFileToContext 缺失'
          console.error(errorDetail)
          alert(errorMsg)
        }
      }
    })
  }

  // 4. 删除文件
  if (fileNode.file_id) {
    fileOperations.push({
      id: 'delete-file',
      label: t ? t('analysis.nodeMenu.deleteFile') : '删除文件',
      icon: '🗑️',
      category: 'file',
      danger: true,
      action: async (node) => {
        const fileId = (node as any).file_id || (node as any).id
        const fileName = (node as any).filename || (node as any).file_name || (node as any).fileName || fileId
        if (handlers.deleteFileNode) {
          await handlers.deleteFileNode(fileId, fileName)
        } else {
          const errorMsg = t ? t('analysis.nodeMenu.errors.deleteFileNotInitialized') : '删除文件功能未初始化'
          const errorDetail = t ? t('analysis.nodeMenu.errors.deleteFileNotInitializedDetail') : '删除文件功能未初始化：handlers.deleteFileNode 缺失'
          console.error(errorDetail)
          alert(errorMsg)
        }
      }
    })
  }

  // 4.1 删除子文件（不删除自身）
  if (fileNode.file_id) {
    fileOperations.push({
      id: 'delete-file-children',
      label: t ? t('analysis.nodeMenu.deleteFileChildren') : '删除子文件',
      icon: '🗑️',
      category: 'file',
      danger: true,
      action: async (node) => {
        const fileId = (node as any).file_id || (node as any).id
        const fileName = (node as any).filename || (node as any).file_name || (node as any).fileName || fileId
        if (handlers.deleteFileChildren) {
          await handlers.deleteFileChildren(fileId, fileName)
        } else {
          const errorMsg = t ? t('analysis.nodeMenu.errors.deleteFileChildrenNotInitialized') : '删除子文件功能未初始化'
          const errorDetail = t ? t('analysis.nodeMenu.errors.deleteFileChildrenNotInitializedDetail') : '删除子文件功能未初始化：handlers.deleteFileChildren 缺失'
          console.error(errorDetail)
          alert(errorMsg)
        }
      }
    })
  }

  // ============ 进一步分析 ============
  
  console.log('fileNode', fileNode)
  // 获取文件节点的 file_type_id
  const fileTypeId = (fileNode as any).file_type_id
  
  // 4. 添加兼容的Service到进一步分析（根据 file_type_id 筛选）
  if (services && services.length > 0 && fileTypeId) {
    services.forEach((service) => {
      // 检查服务是否接受该文件类型
      const isCompatible = (() => {
        // 如果服务没有 accepted_files 或为空，不显示
        if (!service.accepted_files || Object.keys(service.accepted_files).length === 0) {
          return false
        }
        
        // 检查服务的 accepted_files 中是否有任何配置包含该 file_type_id
        for (const config of Object.values(service.accepted_files)) {
          if (config && config.file_type_ids && Array.isArray(config.file_type_ids)) {
            if (config.file_type_ids.includes(fileTypeId)) {
              return true
            }
          }
        }
        
        return false
      })()
      
      // 只添加兼容的服务
      if (isCompatible) {
        analysisOperations.push({
          id: `service-${service.service_id}`,
          label: service.name || service.service_id,
          icon: '⚙️',
          category: 'analysis',
          action: (node) => {
            // 触发显示Service执行对话框
            const fileId = (node as any).file_id || (node as any).id
            if (handlers.showServiceExecuteDialog) {
              handlers.showServiceExecuteDialog(service, fileId)
            } else {
              const errorMsg = t ? t('analysis.nodeMenu.errors.serviceExecuteNotInitialized') : 'Service执行对话框功能未初始化'
              const errorDetail = t ? t('analysis.nodeMenu.errors.serviceExecuteNotInitializedDetail') : 'Service执行对话框功能未初始化：handlers.showServiceExecuteDialog 缺失'
              console.error(errorDetail)
              alert(errorMsg)
            }
          }
        })
      }
    })
  }

  return {
    fileOperations,
    fileAnalysis,
    analysisOperations
  }
}
