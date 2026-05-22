/**
 * Codegen API Mocks
 * 
 * 为所有 codegen API 端点提供类型安全的 mock 实现，用于单元测试。
 * 覆盖所有生命周期和会话端点（R1-R7）。
 */
// @ts-ignore -- Vitest types are only available in the test environment
import { vi } from 'vitest'
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
  generated_code: '# mock code',
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
  code: '# mock code',
  language: 'python',
  parameters: {},
  status: 'pending',
  input_file_id: 'file-1',
  output_file_id: null,
  output_data: null,
  error_message: null,
  execution_log: null,
  created_at: ISO_TIMESTAMP,
  started_at: null,
  completed_at: null,
  duration_seconds: null
}

export const mockExecuteResponse: CodegenExecuteResponse = {
  execution_id: mockExecution.execution_id,
  template_id: mockExecution.template_id,
  status: mockExecution.status,
  created_at: ISO_TIMESTAMP
}

export const mockConversation: CodegenConversationHistoryResponse = {
  template_id: mockTemplate.template_id,
  messages: [
    {
      role: 'user',
      text: 'Please prepare a QC pipeline.',
      time: ISO_TIMESTAMP
    },
    {
      role: 'agent',
      text: 'Generated initial template.',
      time: ISO_TIMESTAMP,
      requires_action: false
    }
  ]
}

export const mockConversationStartResponse: CodegenConversationStartResponse = {
  template_id: mockTemplate.template_id,
  conversation_id: 'conv-1',
  template: mockTemplate,
  agent_message: 'Mock agent initial response.'
}

// Helper to create mock responses with custom data
export function createMockTemplate(overrides?: Partial<CodegenTemplate>): CodegenTemplate {
  return { ...mockTemplate, ...overrides }
}

export function createMockExecution(overrides?: Partial<CodegenExecution>): CodegenExecution {
  return { ...mockExecution, ...overrides }
}

export const mockConversationContinueResponse: CodegenConversationContinueResponse = {
  template: mockTemplate,
  agent_message: 'Mock agent follow-up response.',
  requires_action: false,
  conversation_ended: false
}

const defaultListTemplatesImplementation = async (): Promise<CodegenTemplateList> => {
  return {
    templates: [mockTemplate],
    total: 1
  }
}

const defaultListTemplateExecutionsImplementation = async (): Promise<CodegenExecutionList> => {
  return {
    executions: [mockExecution],
    total: 1
  }
}

export const getTemplate = vi.fn()
export const listTemplates = vi.fn(defaultListTemplatesImplementation)
export const updateTemplate = vi.fn()
export const confirmTemplate = vi.fn()
export const generateCode = vi.fn()
export const finalizeTemplate = vi.fn()
export const executeTemplate = vi.fn()
export const getTemplateExecution = vi.fn()
export const listTemplateExecutions = vi.fn(defaultListTemplateExecutionsImplementation)
export const startConversation = vi.fn()
export const continueConversation = vi.fn()
export const getConversation = vi.fn()

// Type assertions for mock functions to match actual API signatures
export type MockCodegenAPI = {
  getTemplate: typeof getTemplate
  listTemplates: typeof listTemplates
  updateTemplate: typeof updateTemplate
  confirmTemplate: typeof confirmTemplate
  generateCode: typeof generateCode
  finalizeTemplate: typeof finalizeTemplate
  executeTemplate: typeof executeTemplate
  getTemplateExecution: typeof getTemplateExecution
  listTemplateExecutions: typeof listTemplateExecutions
  startConversation: typeof startConversation
  continueConversation: typeof continueConversation
  getConversation: typeof getConversation
}

/**
 * 重置所有 codegen API mocks 为默认实现
 * 在测试的 beforeEach 中调用以确保干净的测试状态
 */
export function resetCodegenMocks(): void {
  getTemplate.mockResolvedValue(mockTemplate)
  updateTemplate.mockResolvedValue(mockTemplate)
  confirmTemplate.mockResolvedValue(mockTemplate)
  generateCode.mockResolvedValue(mockTemplate)
  finalizeTemplate.mockResolvedValue(mockTemplate)
  executeTemplate.mockResolvedValue(mockExecuteResponse)
  getTemplateExecution.mockResolvedValue(mockExecution)
  listTemplates.mockImplementation(defaultListTemplatesImplementation)
  listTemplateExecutions.mockImplementation(defaultListTemplateExecutionsImplementation)
  startConversation.mockResolvedValue(mockConversationStartResponse)
  continueConversation.mockResolvedValue(mockConversationContinueResponse)
  getConversation.mockResolvedValue(mockConversation)
}

// Initialize mocks on module load
resetCodegenMocks()

