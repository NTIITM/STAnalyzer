/**
 * Mock database for front-end only development.
 * Stores in-memory entities that mimic backend resources so we can service API requests.
 */
export type ExecutionStatus = 'pending' | 'running' | 'completed' | 'failed'

export interface MockUser {
  userId: string
  username: string
  password: string
  email: string
  token: string
}

export interface MockFile {
  fileId: string
  name: string
  size: number
  status: string
  time: string
  description?: string
  metaData: Record<string, any>
}

export interface MockProject {
  project_id: string
  user_id: string
  name: string
  description?: string
  knowledge_config: ProjectConfig
  service_config: ProjectConfig
  file_ids: string[]
  created_at: string
  updated_at: string
}

export interface ProjectConfig {
  mode: 'whitelist' | 'blacklist' | 'all'
  whitelist: string[]
  blacklist: string[]
}

export interface MockService {
  service_id: string
  name: string
  description?: string
  version: string
  baseurl: string
  service_suffix: string
  download_suffix?: string
  parameter_template: Record<string, any>
  parameter_schema?: Record<string, any>
  output_config?: {
    collection_description?: string
    items: Array<{
      type: 'file' | 'text'
      filename: string
      description: string
    }>
  }
  visibility?: 'private' | 'public' | 'system'
  created_at?: string
  updated_at?: string
  created_by?: string
}

export interface MockServiceExecution {
  execution_id: string
  service_id: string
  service_name: string
  user_id: string
  input_file_ids: string[]
  output_file_ids?: string[]
  status: ExecutionStatus
  parameters: Record<string, any>
  response_data?: Record<string, any>
  error_message?: string | null
  created_at: string
  started_at?: string
  completed_at?: string
  duration_seconds?: number
}

export interface MockKnowledgeRecord {
  id: string
  title: string
  description: string
  relationSummary?: {
    fromEntity: string
    relation: string
    endEntity: string
  }
  tags: string[]
  scope: 'private' | 'public' | 'system'
  editedByUser?: boolean
  source?: string
  ownerId?: string
  createdAt?: string
  lastModified?: string
  sharedAt?: string
  metadata?: Record<string, any> | null
}

export interface MockPromptTemplate {
  id: string
  label: string
  name?: string
  description?: string
  entityPrompt: Record<string, string>
  relationPrompt: Record<string, string>
  constraints?: string
  isDefault?: boolean
  updatedAt?: string
}

export interface MockPromptConfig extends MockPromptTemplate {
  createdAt?: string
}

export interface MockPendingPrompt {
  pendingPromptId: string
  query: string
  context: string
  entityPrompt: Record<string, string>
  relationPrompt: Record<string, string>
  description?: string
  createdAt: string
}

export interface MockAnalysisTree {
  project_id: string
  root: {
    id: string
    type: 'project' | 'file' | 'knowledge'
    status: string
    children?: Array<MockAnalysisTree['root']>
  }
  files: Array<{
    file_id: string
    filename: string
    file_type: string
    status: string
  }>
  executions: Array<{
    execution_id: string
    input_file_ids: string[]
    output_file_ids: string[]
    project_id: string
    status: string
    parameters?: Record<string, any>
    created_at: string
    started_at?: string
    completed_at?: string
  }>
}

export interface MockAgentConversation {
  projectId: string
  messages: Array<{
    role: 'user' | 'agent'
    text: string
    time: string
    requires_action?: boolean
  }>
}

const now = () => new Date().toISOString()

const defaultConfig: ProjectConfig = {
  mode: 'all',
  whitelist: [],
  blacklist: []
}

export const mockDb = {
  users: [
    {
      userId: 'user-1',
      username: 'demo',
      password: 'demo123',
      email: 'demo@stanalyzer.ai',
      token: 'mock-token-demo'
    }
  ] as MockUser[],
  files: [
    {
      fileId: 'file-1',
      name: 'Visium_MouseBrain.h5ad',
      size: 524288000,
      status: 'completed',
      time: now(),
      description: 'Mouse brain Visium dataset',
      metaData: {
        organism: 'Mus musculus',
        platform: '10x Visium',
        sections: 4,
        spots: 4992
      }
    },
    {
      fileId: 'file-2',
      name: 'MERFISH_Liver.csv',
      size: 212336000,
      status: 'completed',
      time: now(),
      description: 'Liver MERFISH data',
      metaData: {
        organism: 'Homo sapiens',
        platform: 'MERFISH',
        genes: 500,
        cells: 12000
      }
    }
  ] as MockFile[],
  projects: [
    {
      project_id: 'proj-1',
      user_id: 'user-1',
      name: 'Spatial QC',
      description: 'Quality control and normalization pipeline',
      knowledge_config: { ...defaultConfig },
      service_config: { ...defaultConfig },
      file_ids: ['file-1', 'file-2'],
      created_at: now(),
      updated_at: now()
    }
  ] as MockProject[],
  services: [
    {
      service_id: 'svc-1',
      name: 'QC Pipeline',
      description: 'Filter spots and genes, normalize counts',
      version: '1.0.0',
      baseurl: 'https://mock.service/qc',
      service_suffix: '/run',
      parameter_template: {
        min_genes: 200,
        max_genes: 5000,
        min_counts: 0
      },
      parameter_schema: {
        min_genes: { type: 'integer', min: 0, max: 10000, default_value: 200 },
        max_genes: { type: 'integer', min: 0, max: 20000, default_value: 5000 },
        normalize: { type: 'boolean', default_value: true }
      },
      output_config: {
        collection_description: 'QC reports and filtered matrix',
        items: [
          { type: 'file', filename: 'filtered.h5ad', description: 'Filtered matrix' },
          { type: 'text', filename: 'qc_summary.txt', description: 'QC summary statistics' }
        ]
      },
      visibility: 'public',
      created_at: now(),
      updated_at: now(),
      created_by: 'user-1'
    },
    {
      service_id: 'svc-2',
      name: 'Cell Type Annotation',
      description: 'Annotate spots based on reference atlas',
      version: '0.5.0',
      baseurl: 'https://mock.service/annotation',
      service_suffix: '/predict',
      parameter_template: {
        reference: 'mouse_brain',
        confidence_threshold: 0.6
      },
      parameter_schema: {
        reference: { type: 'enum', enum_values: ['mouse_brain', 'human_liver'], default_value: 'mouse_brain' },
        confidence_threshold: { type: 'continuous', min_value: 0, max_value: 1, default_value: 0.6 }
      },
      visibility: 'public',
      created_at: now(),
      updated_at: now(),
      created_by: 'user-1'
    }
  ] as MockService[],
  serviceExecutions: [
    {
      execution_id: 'svc-exec-1',
      service_id: 'svc-1',
      service_name: 'QC Pipeline',
      user_id: 'user-1',
      input_file_ids: ['file-1'],
      output_file_ids: ['file-3'],
      status: 'completed',
      parameters: { min_genes: 200, max_genes: 5000 },
      response_data: {
        removed_spots: 120,
        removed_genes: 430
      },
      created_at: now(),
      started_at: now(),
      completed_at: now(),
      duration_seconds: 65
    }
  ] as MockServiceExecution[],
  knowledge: [
    {
      id: 'kn-1',
      title: 'Astrocyte Markers',
      description: 'GFAP and ALDH1L1 enriched in astrocytes across cortical layers.',
      relationSummary: {
        fromEntity: 'Astrocyte',
        relation: 'expresses',
        endEntity: 'GFAP'
      },
      tags: ['astrocyte', 'marker'],
      scope: 'public',
      editedByUser: true,
      source: 'Literature',
      ownerId: 'user-1',
      createdAt: now(),
      lastModified: now(),
      sharedAt: now(),
      metadata: {
        tissues: ['cortex'],
        references: ['PMID:123456']
      }
    },
    {
      id: 'kn-2',
      title: 'Liver Zonation',
      description: 'Pericentral hepatocytes up-regulate CYP2E1 and GLUL.',
      relationSummary: {
        fromEntity: 'Pericentral hepatocytes',
        relation: 'up-regulate',
        endEntity: 'CYP2E1'
      },
      tags: ['liver', 'zonation'],
      scope: 'private',
      editedByUser: false,
      source: 'Knowledge Graph',
      ownerId: 'user-1',
      createdAt: now(),
      lastModified: now(),
      metadata: {
        atlas: 'Liver Atlas v1'
      }
    }
  ] as MockKnowledgeRecord[],
  promptTemplates: [
    {
      id: 'tmpl-knowledge-1',
      label: 'Spatial Extraction Default',
      name: 'default_extraction',
      description: 'Default extraction prompt tuned for Visium datasets',
      entityPrompt: {
        cell: 'Describe the cell type precisely with organ and location.'
      },
      relationPrompt: {
        expresses: 'Describe expression relationship and supporting evidence.'
      },
      constraints: 'Return concise statements.',
      isDefault: true,
      updatedAt: now()
    }
  ] as MockPromptTemplate[],
  promptConfig: {
    id: 'tmpl-knowledge-1',
    label: 'Spatial Extraction Default',
    name: 'default_extraction',
    description: 'Default prompt config',
    entityPrompt: {
      cell: 'Describe the cell type precisely with organ and location.'
    },
    relationPrompt: {
      expresses: 'Describe expression relationship and supporting evidence.'
    },
    constraints: 'Return concise statements.',
    isDefault: true,
    createdAt: now(),
    updatedAt: now()
  } as MockPromptConfig,
  pendingPrompts: [] as MockPendingPrompt[],
  analysisTrees: {
    'proj-1': {
      project_id: 'proj-1',
      root: {
        id: 'proj-1',
        type: 'project',
        status: 'running',
        children: [
          { id: 'file-1', type: 'file', status: 'completed' },
          { id: 'file-2', type: 'file', status: 'pending' }
        ]
      },
      files: [
        {
          file_id: 'file-1',
          filename: 'Visium_MouseBrain.h5ad',
          file_type: 'h5ad',
          status: 'completed'
        },
        {
          file_id: 'file-2',
          filename: 'MERFISH_Liver.csv',
          file_type: 'csv',
          status: 'pending'
        }
      ],
      executions: [
        {
          execution_id: 'exec-graph-1',
          input_file_ids: ['file-1'],
          output_file_ids: ['file-3'],
          project_id: 'proj-1',
          status: 'completed',
          parameters: { method: 'qc' },
          created_at: now(),
          started_at: now(),
          completed_at: now()
        }
      ]
    }
  } as Record<string, MockAnalysisTree>,
  agentConversations: {
    'proj-1': {
      projectId: 'proj-1',
      messages: [
        {
          role: 'user',
          text: 'How many low-quality spots remain?',
          time: now()
        },
        {
          role: 'agent',
          text: 'After QC, 142 low-quality spots remain across 2 slides.',
          time: now(),
          requires_action: false
        }
      ]
    }
  } as Record<string, MockAgentConversation>
}

export function generateId(prefix: string) {
  return `${prefix}-${Math.random().toString(36).slice(2, 10)}`
}

