/**
 * Codegen API Development Mocks
 * 
 * 为开发环境提供模拟数据，用于前端开发时无需后端支持。
 * 通过环境变量 VITE_USE_MOCK=true 启用。
 * 
 * 注意：此文件用于开发环境，测试环境应使用 codegen.ts 中的 vitest mocks
 */
import type {
  CodegenConversationContinueResponse,
  CodegenConversationHistoryResponse,
  CodegenConversationStartResponse,
  CodegenExecuteResponse,
  CodegenExecution,
  CodegenExecutionList,
  CodegenTemplate,
  CodegenTemplateList
} from '../../types/codegen'

const ISO_TIMESTAMP = '2024-01-01T00:00:00.000Z'

// 模拟延迟，让请求看起来更真实
const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms))

export const mockTemplate: CodegenTemplate = {
  template_id: 'tmpl-1',
  name: 'Mock Template',
  description: 'Mock template description',
  user_requirement: 'Analyze spatial transcriptomics dataset',
  input_file_name: 'mock-input.csv',
  input_file_description: 'Mock input file description',
  parameter_template: {
    normalize: true,
    qc_threshold: 0.3,
    min_genes: 200,
    max_genes: 5000,
    method: 'standard'
  },
  parameter_schema: {
    normalize: {
      type: 'boolean',
      default_value: true,
      description: '是否进行标准化',
      required: false
    },
    qc_threshold: {
      type: 'continuous',
      default_value: 0.3,
      min_value: 0.0,
      max_value: 1.0,
      description: '质量控制阈值',
      required: true
    },
    min_genes: {
      type: 'discrete',
      default_value: 200,
      min_value: 0,
      max_value: 10000,
      description: '最小基因数',
      required: true
    },
    max_genes: {
      type: 'discrete',
      default_value: 5000,
      min_value: 0,
      max_value: 50000,
      description: '最大基因数',
      required: true
    },
    method: {
      type: 'enum',
      default_value: 'standard',
      enum_values: ['standard', 'robust'],
      description: '标准化方法',
      required: true
    }
  },
  output_config: {
    collection_description: '输出预处理后的数据文件和处理结果',
    items: [
      {
        type: 'file',
        filename: 'preprocessed_data.h5ad',
        description: '预处理后的数据文件，包含质量控制后的数据和标准化结果'
      },
      {
        type: 'text',
        filename: '处理状态摘要',
        description: '包含质量控制统计、标准化统计和最终数据维度等信息'
      }
    ]
  },
  generated_code: '# mock code\nimport scanpy as sc\nimport pandas as pd\n\n# 加载数据\ndata = sc.read_h5ad("input.h5ad")\n\n# 质量控制\nsc.pp.filter_cells(data, min_genes=200)\nsc.pp.filter_genes(data, min_cells=3)\n\n# 标准化\nsc.pp.normalize_total(data, target_sum=1e4)\nsc.pp.log1p(data)\n\n# 保存结果\ndata.write("preprocessed_data.h5ad")',
  code_language: 'python',
  status: 'template_generated',
  created_at: ISO_TIMESTAMP,
  service_id: 'svc-1',
  project_id: 'proj-1',
  metadata: {}
}

export const mockExecution: CodegenExecution = {
  execution_id: 'exec-1',
  template_id: mockTemplate.template_id,
  user_id: 'user-1',
  code: mockTemplate.generated_code || '# mock code',
  language: 'python',
  parameters: {},
  status: 'completed',
  input_file_id: 'file-1',
  output_file_id: 'file-2',
  output_data: {
    files: [
      {
        file_id: 'file-2',
        filename: 'preprocessed_data.h5ad',
        description: '预处理后的数据文件'
      }
    ]
  },
  error_message: null,
  execution_log: '开始执行...\n加载数据...\n执行质量控制...\n执行标准化...\n保存结果...\n执行完成！',
  created_at: ISO_TIMESTAMP,
  started_at: ISO_TIMESTAMP,
  completed_at: new Date(Date.now()).toISOString(),
  duration_seconds: 120
}

export const mockConversation: CodegenConversationHistoryResponse = {
  template_id: mockTemplate.template_id,
  messages: [
    {
      role: 'user',
      text: 'Please prepare a QC pipeline for spatial transcriptomics data.',
      time: ISO_TIMESTAMP
    },
    {
      role: 'agent',
      text: 'I\'ll help you create a quality control pipeline. Let me generate an initial template based on your requirements.',
      time: ISO_TIMESTAMP,
      requires_action: false
    },
    {
      role: 'user',
      text: 'Can you add normalization step?',
      time: new Date(Date.now() - 3600000).toISOString()
    },
    {
      role: 'agent',
      text: 'Sure! I\'ve added normalization steps to the pipeline. The template now includes total count normalization and log transformation.',
      time: new Date(Date.now() - 3600000).toISOString(),
      requires_action: false
    }
  ]
}

// Mock API 函数实现
export const codegenDevMocks = {
  /**
   * 获取模板列表
   */
  async listTemplates(params?: any): Promise<CodegenTemplateList> {
    await delay(300)
    console.log('[Mock] listTemplates', params)
    
    // 可以根据 params 返回不同的模板
    const templates = [mockTemplate]
    
    // 如果指定了 projectId 或 serviceId，可以过滤
    if (params?.project_id) {
      // 模拟过滤
    }
    if (params?.service_id) {
      // 模拟过滤
    }
    
    return {
      templates,
      total: templates.length
    }
  },

  /**
   * 获取模板详情
   */
  async getTemplate(templateId: string): Promise<CodegenTemplate> {
    await delay(200)
    console.log('[Mock] getTemplate', templateId)
    return { ...mockTemplate, template_id: templateId }
  },

  /**
   * 更新模板
   */
  async updateTemplate(templateId: string, payload: any): Promise<CodegenTemplate> {
    await delay(300)
    console.log('[Mock] updateTemplate', templateId, payload)
    return {
      ...mockTemplate,
      template_id: templateId,
      ...payload
    }
  },

  /**
   * 确认模板
   */
  async confirmTemplate(templateId: string): Promise<CodegenTemplate> {
    await delay(300)
    console.log('[Mock] confirmTemplate', templateId)
    return {
      ...mockTemplate,
      template_id: templateId,
      status: 'template_confirmed'
    }
  },

  /**
   * 生成代码
   */
  async generateCode(templateId: string): Promise<CodegenTemplate> {
    await delay(1000)
    console.log('[Mock] generateCode', templateId)
    return {
      ...mockTemplate,
      template_id: templateId,
      status: 'code_generated',
      generated_code: mockTemplate.generated_code
    }
  },

  /**
   * 完成模板
   */
  async finalizeTemplate(templateId: string): Promise<CodegenTemplate> {
    await delay(300)
    console.log('[Mock] finalizeTemplate', templateId)
    return {
      ...mockTemplate,
      template_id: templateId,
      status: 'template_finalized'
    }
  },

  /**
   * 执行模板
   */
  async executeTemplate(templateId: string, payload?: any): Promise<CodegenExecuteResponse> {
    await delay(500)
    console.log('[Mock] executeTemplate', templateId, payload)
    const executionId = `exec-${Date.now()}`
    return {
      execution_id: executionId,
      template_id: templateId,
      status: 'pending',
      created_at: new Date().toISOString()
    }
  },

  /**
   * 获取执行列表
   */
  async listTemplateExecutions(params?: any): Promise<CodegenExecutionList> {
    await delay(300)
    console.log('[Mock] listTemplateExecutions', params)
    return {
      executions: [mockExecution],
      total: 1
    }
  },

  /**
   * 获取执行详情
   */
  async getTemplateExecution(executionId: string): Promise<CodegenExecution> {
    await delay(200)
    console.log('[Mock] getTemplateExecution', executionId)
    return {
      ...mockExecution,
      execution_id: executionId
    }
  },

  /**
   * 启动会话
   */
  async startConversation(payload: any): Promise<CodegenConversationStartResponse> {
    await delay(800)
    console.log('[Mock] startConversation', payload)
    const templateId = `tmpl-${Date.now()}`
    return {
      template_id: templateId,
      conversation_id: `conv-${Date.now()}`,
      template: {
        ...mockTemplate,
        template_id: templateId,
        user_requirement: payload.user_requirement || mockTemplate.user_requirement,
        status: 'template_created'
      },
      agent_message: 'I\'ve created an initial template based on your requirements. Let me know if you\'d like to make any adjustments.'
    }
  },

  /**
   * 继续会话
   */
  async continueConversation(templateId: string, payload: any): Promise<CodegenConversationContinueResponse> {
    await delay(800)
    console.log('[Mock] continueConversation', templateId, payload)
    return {
      template: {
        ...mockTemplate,
        template_id: templateId
      },
      agent_message: 'I understand. I\'ve updated the template accordingly. Is there anything else you\'d like to modify?',
      requires_action: false,
      conversation_ended: false
    }
  },

  /**
   * 获取会话历史
   */
  async getConversation(templateId: string): Promise<CodegenConversationHistoryResponse> {
    await delay(200)
    console.log('[Mock] getConversation', templateId)
    return {
      ...mockConversation,
      template_id: templateId
    }
  }
}

/**
 * 根据 URL 和方法匹配对应的 mock 函数
 */
export function matchCodegenMock(url: string, method: string): (() => Promise<any>) | null {
  // 模板列表
  if (url.includes('/codegen/templates') && method === 'GET' && !url.match(/\/codegen\/templates\/[^/]+$/)) {
    return () => codegenDevMocks.listTemplates()
  }
  
  // 模板详情
  const templateMatch = url.match(/\/codegen\/templates\/([^/]+)$/)
  if (templateMatch && method === 'GET') {
    const templateId = templateMatch[1]
    return () => codegenDevMocks.getTemplate(templateId)
  }
  
  // 更新模板
  if (templateMatch && method === 'PUT') {
    const templateId = templateMatch[1]
    return (data?: any) => codegenDevMocks.updateTemplate(templateId, data)
  }
  
  // 确认模板
  if (url.match(/\/codegen\/templates\/[^/]+\/confirm$/) && method === 'POST') {
    const templateId = url.match(/\/codegen\/templates\/([^/]+)\/confirm$/)?.[1] || ''
    return () => codegenDevMocks.confirmTemplate(templateId)
  }
  
  // 生成代码
  if (url.match(/\/codegen\/templates\/[^/]+\/generate-code$/) && method === 'POST') {
    const templateId = url.match(/\/codegen\/templates\/([^/]+)\/generate-code$/)?.[1] || ''
    return () => codegenDevMocks.generateCode(templateId)
  }
  
  // 完成模板
  if (url.match(/\/codegen\/templates\/[^/]+\/finalize$/) && method === 'POST') {
    const templateId = url.match(/\/codegen\/templates\/([^/]+)\/finalize$/)?.[1] || ''
    return () => codegenDevMocks.finalizeTemplate(templateId)
  }
  
  // 执行模板
  if (url.match(/\/codegen\/templates\/[^/]+\/execute$/) && method === 'POST') {
    const templateId = url.match(/\/codegen\/templates\/([^/]+)\/execute$/)?.[1] || ''
    return (data?: any) => codegenDevMocks.executeTemplate(templateId, data)
  }
  
  // 执行列表
  if (url.includes('/codegen/executions') && method === 'GET' && !url.match(/\/codegen\/executions\/[^/]+$/)) {
    return () => codegenDevMocks.listTemplateExecutions()
  }
  
  // 执行详情
  const executionMatch = url.match(/\/codegen\/executions\/([^/]+)$/)
  if (executionMatch && method === 'GET') {
    const executionId = executionMatch[1]
    return () => codegenDevMocks.getTemplateExecution(executionId)
  }
  
  // 启动会话
  if (url.includes('/codegen/conversations/start') && method === 'POST') {
    return (data?: any) => codegenDevMocks.startConversation(data)
  }
  
  // 继续会话
  const continueMatch = url.match(/\/codegen\/conversations\/([^/]+)\/continue$/)
  if (continueMatch && method === 'POST') {
    const templateId = continueMatch[1]
    return (data?: any) => codegenDevMocks.continueConversation(templateId, data)
  }
  
  // 获取会话历史
  const conversationMatch = url.match(/\/codegen\/conversations\/([^/]+)$/)
  if (conversationMatch && method === 'GET') {
    const templateId = conversationMatch[1]
    return () => codegenDevMocks.getConversation(templateId)
  }
  
  return null
}


