<template>
  <div class="service-form-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="page-header-left">
        <button class="back-btn" @click="handleBack">
          <Icon name="chevron-down" size="md" class="back-icon" />
          <span>{{ $t('common.cancel') }}</span>
        </button>
        <h1>{{ isEditMode ? $t('service.edit') : $t('service.create') }}</h1>
      </div>
      <div class="page-header-right">
        <button 
          class="button button-primary" 
          :class="{ 'button-saving': saving }"
          @click="handleSave" 
          :disabled="saving || !isFormValid"
        >
          <span v-if="saving" class="save-spinner"></span>
          <span>{{ saving ? $t('service.form.saving') : $t('common.save') }}</span>
        </button>
      </div>
    </div>

    <!-- 主内容区域：左右分栏（1:1） -->
    <div class="form-container">
      <!-- 左侧：基本信息 -->
      <div class="form-left">
        <div class="form-section">
          <h2 class="section-title">{{ $t('service.detail.basicInfo') }}</h2>
          
          

          <div class="form-group">
            <label>{{ $t('service.form.name') }} <span class="required">{{ $t('common.required') }}</span></label>
            <input 
              v-model="formData.name"
              type="text"
              class="form-input"
              :placeholder="$t('service.form.name')"
              required
            />
          </div>

          <div class="form-group">
            <label>{{ $t('service.form.description') }}</label>
            <textarea 
              v-model="formData.description"
              class="form-textarea"
              rows="3"
              :placeholder="$t('service.form.description')"
            />
          </div>

          <div class="form-group">
            <label>{{ $t('service.form.version') }}</label>
            <input 
              v-model="formData.version"
              type="text"
              class="form-input"
              :placeholder="$t('service.form.versionPlaceholder')"
            />
          </div>

          <div class="form-group">
            <label>{{ $t('service.form.visibility') }}</label>
            <el-select v-model="formData.visibility" :placeholder="$t('service.form.visibility')">
              <el-option :label="$t('service.visibility.private')" value="private" />
              <el-option :label="$t('service.visibility.public')" value="public" />
            </el-select>
          </div>

          <div class="form-group">
            <label>{{ $t('service.form.baseurl') }} <span class="required">{{ $t('common.required') }}</span></label>
            <input 
              v-model="formData.baseurl"
              type="url"
              class="form-input"
              :placeholder="$t('service.form.baseurlPlaceholder')"
              required
            />
            <small class="form-hint">{{ $t('service.form.baseurlHint') }}</small>
          </div>

          <div class="form-group">
            <label>{{ $t('service.form.serviceSuffix') }} <span class="required">{{ $t('common.required') }}</span></label>
            <input 
              v-model="formData.service_suffix"
              type="text"
              class="form-input"
              :placeholder="$t('service.form.serviceSuffixPlaceholder')"
              required
            />
            <small class="form-hint">{{ $t('service.form.serviceSuffixHint') }}</small>
          </div>

          <div class="form-group">
            <label>{{ $t('service.form.downloadSuffix') }}</label>
            <input 
              v-model="formData.download_suffix"
              type="text"
              class="form-input"
              :placeholder="$t('service.form.downloadSuffixPlaceholder')"
            />
            <small class="form-hint">{{ $t('service.form.downloadSuffixHint') }}</small>
          </div>

          <div class="form-group">
            <label>{{ $t('service.form.inputConfig') }}</label>
            <div class="input-config-editor">
              <div v-if="inputParams.length === 0" class="empty-input-config">
                <p>{{ $t('service.form.noParams') }}</p>
                <button type="button" class="button button-secondary" @click="addInputParam">
                  <Icon name="plus" size="sm" />
                  {{ $t('service.form.addParam') }}
                </button>
              </div>
              <div v-else class="input-items-list">
                <div class="input-items-actions-top">
                  <button type="button" class="button button-secondary" @click="addInputParam">
                    <Icon name="plus" size="sm" />
                    {{ $t('service.form.addParam') }}
                  </button>
                </div>
                <div class="input-table-wrapper">
                  <table class="input-table">
                    <thead>
                      <tr>
                        <th style="width: 20%;">{{ $t('service.form.paramName') }}</th>
                        <th style="width: 30%;">{{ $t('service.form.paramDescription') }}</th>
                        <th style="width: 14%;">{{ $t('service.form.paramType') }}</th>
                        <th style="width: 22%;">{{ $t('service.form.defaultValue') }}</th>
                        <th style="width: 20%;">{{ $t('service.form.constraints') }}</th>
                        <th style="width: 4%;"></th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="(p, idx) in inputParams" :key="idx">
                        <td>
                          <input v-model="p.name" type="text" class="form-input" :placeholder="$t('service.form.paramNamePlaceholder')" />
                        </td>
                        <td>
                          <input v-model="p.description" type="text" class="form-input" :placeholder="$t('service.form.paramDescriptionPlaceholder')" />
                        </td>
                        <td>
                          <el-select v-model="p.type" :placeholder="$t('service.form.typePlaceholder')">
                            <el-option label="boolean" value="boolean" />
                            <el-option label="continuous" value="continuous" />
                            <el-option label="discrete" value="discrete" />
                            <el-option label="enum" value="enum" />
                            <el-option label="string" value="string" />
                          </el-select>
                        </td>
                        <td>
                          <!-- 默认值输入，随类型变化 -->
                          <div v-if="p.type === 'boolean'">
                            <el-select v-model="p.default_value" :placeholder="$t('service.form.defaultPlaceholder')">
                              <el-option label="true" :value="true" />
                              <el-option label="false" :value="false" />
                            </el-select>
                          </div>
                          <div v-else-if="p.type === 'continuous' || p.type === 'discrete'">
                            <input v-model.number="p.default_value" type="number" class="form-input" :placeholder="$t('service.form.defaultNumberPlaceholder')" />
                          </div>
                          <div v-else-if="p.type === 'enum'">
                            <el-select v-if="(p.enum_values_text ?? '').trim().length > 0" v-model="p.default_value" :placeholder="$t('service.form.defaultPlaceholder')">
                              <el-option 
                                v-for="opt in (p.enum_values_text ?? '').split(',').map(s=>s.trim()).filter(Boolean)" 
                                :key="opt" 
                                :label="opt"
                                :value="opt"
                              />
                            </el-select>
                            <input v-else v-model="p.default_value" type="text" class="form-input" :placeholder="$t('service.form.defaultEnumPlaceholder')" />
                          </div>
                          <div v-else>
                            <input v-model="p.default_value" type="text" class="form-input" :placeholder="$t('service.form.defaultTextPlaceholder')" />
                          </div>
                        </td>
                        <td>
                          <div v-if="p.type === 'continuous' || p.type === 'discrete'" class="constraint-row">
                            <input v-model.number="p.min_value" type="number" class="form-input" :placeholder="$t('service.form.minValue')" />
                            <span class="constraint-sep">~</span>
                            <input v-model.number="p.max_value" type="number" class="form-input" :placeholder="$t('service.form.maxValue')" />
                          </div>
                          <div v-else-if="p.type === 'enum'" class="constraint-row">
                            <input
                              v-model="p.enum_values_text"
                              type="text"
                              class="form-input"
                              :placeholder="$t('service.form.enumValuesPlaceholder')"
                            />
                          </div>
                          <div v-else class="constraint-row">
                            <span class="text-muted">{{ $t('service.form.noExtraConstraints') }}</span>
                          </div>
                        </td>
                        <td>
                          <button type="button" class="button-icon" @click="removeInputParam(idx)">
                            <Icon name="x" size="sm" />
                          </button>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
            <small class="form-hint">{{ $t('service.form.inputConfigHint') }}</small>
          </div>

          <!-- accepted_files 配置区域 -->
          <div class="form-group">
            <label>{{ $t('service.form.acceptedFiles') }}</label>
            <div class="accepted-files-editor">
              <div v-if="acceptedFilesItems.length === 0" class="empty-accepted-files">
                <p>{{ $t('service.form.noAcceptedFiles') }}</p>
                <button type="button" class="button button-secondary" @click="addAcceptedFile">
                  <Icon name="document" size="sm" />
                  {{ $t('service.form.addAcceptedFile') }}
                </button>
              </div>
              <div v-else class="accepted-files-list">
                <div 
                  v-for="(item, index) in acceptedFilesItems" 
                  :key="index" 
                  class="accepted-file-card"
                >
                  <div class="accepted-file-header">
                    <span class="accepted-file-badge">{{ item.filename || $t('service.form.newFile') }}</span>
                    <button 
                      type="button" 
                      class="button-icon" 
                      @click="removeAcceptedFile(index)"
                    >
                      <Icon name="x" size="sm" />
                    </button>
                  </div>
                  <div class="accepted-file-content">
                    <div class="form-group-inline">
                      <label>{{ $t('service.form.filename') }} <span class="required">*</span></label>
                      <input 
                        v-model="item.filename" 
                        type="text" 
                        class="form-input" 
                        :placeholder="$t('service.form.filenamePlaceholder')" 
                      />
                    </div>
                    <div class="form-group-inline">
                      <label>{{ $t('service.form.fileTypeIds') }} <span class="required">*</span></label>
                      <div class="file-type-ids-input">
                        <div 
                          v-for="(_typeId, typeIndex) in item.file_type_ids" 
                          :key="typeIndex"
                          class="file-type-id-tag"
                        >
                          <input 
                            v-model="item.file_type_ids[typeIndex]" 
                            type="text" 
                            class="form-input tag-input" 
                            :placeholder="$t('service.form.fileTypeIdPlaceholder')" 
                          />
                          <button 
                            type="button" 
                            class="button-icon-small" 
                            @click="removeFileTypeId(index, typeIndex)"
                          >
                            <Icon name="x" size="sm" />
                          </button>
                        </div>
                        <button 
                          type="button" 
                          class="button button-secondary button-small" 
                          @click="addFileTypeId(index)"
                        >
                          <Icon name="plus" size="sm" />
                          {{ $t('service.form.addFileTypeId') }}
                        </button>
                      </div>
                    </div>
                    <div class="form-group-inline">
                      <label>{{ $t('service.form.fileDescription') }} <span class="required">*</span></label>
                      <textarea 
                        v-model="item.description" 
                        class="form-textarea" 
                        rows="2" 
                        :placeholder="$t('service.form.fileDescriptionPlaceholder')" 
                      />
                    </div>
                  </div>
                </div>
                <div class="accepted-files-actions">
                  <button 
                    type="button" 
                    class="button button-secondary" 
                    @click="addAcceptedFile"
                  >
                    <Icon name="document" size="sm" />
                    {{ $t('service.form.addAcceptedFile') }}
                  </button>
                </div>
              </div>
            </div>
            <small class="form-hint">{{ $t('service.form.acceptedFilesHint') }}</small>
          </div>

          <div class="form-group">
            <label>{{ $t('service.form.outputConfig') }}</label>
            <div class="output-config-editor">
              <div v-if="outputConfigItems.length === 0" class="empty-output-config">
                <p>{{ $t('service.form.noOutputItems') }}</p>
                <button type="button" class="button button-secondary" @click="addOutputItem('file')">
                  <Icon name="document" size="sm" />
                  {{ $t('service.form.addFileItem') }}
                </button>
                <button type="button" class="button button-secondary" @click="addOutputItem('text')">
                  <Icon name="document-text" size="sm" />
                  {{ $t('service.form.addTextItem') }}
                </button>
              </div>
              <div v-else class="output-items-list">
                <div v-for="(item, index) in outputConfigItems" :key="index" class="output-item-card">
                  <div class="output-item-header">
                    <span class="output-item-type-badge" :class="`type-${item.type}`">
                      {{ item.type === 'file' ? $t('service.form.fileType') : $t('service.form.textType') }}
                    </span>
                    <button type="button" class="button-icon" @click="removeOutputItem(index)">
                      <Icon name="x" size="sm" />
                    </button>
                  </div>
                  <div class="output-item-content">
                    <div class="form-group-inline">
                      <label>{{ $t('service.form.filename') }} <span class="required">*</span></label>
                      <input v-model="item.filename" type="text" class="form-input" :placeholder="$t('service.form.filenamePlaceholder')" />
                    </div>
                    <div v-if="item.type === 'file'" class="form-group-inline">
                      <label>{{ $t('service.form.fileTypeId') }} <span class="required">*</span></label>
                      <div class="file-type-id-input-wrapper">
                        <input 
                          v-model="item.file_type_id" 
                          type="text" 
                          class="form-input file-type-id-input" 
                          :placeholder="$t('service.form.fileTypeIdPlaceholder')" 
                          list="file-type-ids-suggestions"
                        />
                        <datalist id="file-type-ids-suggestions">
                          <option 
                            v-for="(typeId, idx) in availableFileTypeIds" 
                            :key="idx" 
                            :value="typeId"
                          />
                        </datalist>
                      </div>
                      <small class="form-hint">{{ $t('service.form.fileTypeIdHint') }}</small>
                    </div>
                    <div class="form-group-inline">
                      <label>{{ $t('service.form.outputDescription') }} <span class="required">*</span></label>
                      <textarea v-model="item.description" class="form-textarea" rows="2" :placeholder="$t('service.form.outputDescriptionPlaceholder')" />
                    </div>
                  </div>
                </div>
                <div class="output-items-actions">
                  <button type="button" class="button button-secondary" @click="addOutputItem('file')">
                    <Icon name="document" size="sm" />
                    {{ $t('service.form.addFileItem') }}
                  </button>
                  <button type="button" class="button button-secondary" @click="addOutputItem('text')">
                    <Icon name="document-text" size="sm" />
                    {{ $t('service.form.addTextItem') }}
                  </button>
                </div>
                <div class="form-group-inline">
                  <label>{{ $t('service.form.collectionDescription') }}</label>
                  <textarea v-model="outputConfigCollectionDescription" class="form-textarea" rows="2" :placeholder="$t('service.form.collectionDescriptionPlaceholder')" />
                </div>
              </div>
            </div>
            <small class="form-hint">{{ $t('service.form.outputConfigHint') }}</small>
          </div>
        </div>
      </div>

      <!-- 右侧：配置文件编辑器（JSON/YAML） -->
      <div class="form-right">
        <div class="form-section">
          <div class="section-header">
            <h2 class="section-title">{{ $t('service.form.configFile') }}</h2>
            <div class="section-actions">
              <input 
                ref="configFileInput"
                type="file"
                accept=".json,.yaml,.yml"
                style="display: none"
                @change="handleConfigFileUpload"
              />
              <button 
                type="button"
                class="button button-secondary"
                @click="triggerConfigFileUpload"
              >
                <Icon name="document" size="sm" />
                {{ $t('service.form.uploadFile') }}
              </button>
              <button 
                type="button"
                class="button button-secondary"
                @click="downloadExampleJson"
              >
                <Icon name="download" size="sm" />
                {{ $t('service.form.downloadExampleJson') }}
              </button>
              <button 
                type="button"
                class="button button-secondary"
                @click="downloadExampleYaml"
              >
                <Icon name="download" size="sm" />
                {{ $t('service.form.downloadExampleYaml') }}
              </button>
            </div>
          </div>

          <!-- 格式切换 -->
          <div class="format-switcher">
            <button 
              class="format-btn"
              :class="{ active: configFormat === 'json' }"
              @click="configFormat = 'json'"
            >
              JSON
            </button>
            <button 
              class="format-btn"
              :class="{ active: configFormat === 'yaml' }"
              @click="configFormat = 'yaml'"
            >
              YAML
            </button>
          </div>

          <!-- 配置文件编辑器区域 -->
          <div class="config-editor-container">
              <textarea 
              v-model="configText"
              class="config-editor"
              :class="{ 'config-error': configError }"
              :placeholder="configFormat === 'json' ? $t('service.form.jsonPlaceholder') : $t('service.form.yamlPlaceholder')"
              />
            <div v-if="configError" class="config-error-message">
              {{ configError }}
              </div>
            <div v-else class="config-stats">
              {{ $t('service.form.validConfig') }}
              </div>
            </div>
        </div>
      </div>
    </div>

    <!-- 错误提示 -->
    <div v-if="formError" class="form-error-toast">
      {{ formError }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import * as yaml from 'js-yaml'
import { createService, updateService, getServiceDetail, type ServiceCreateRequest } from '../../api/service'
import Icon from '../common/Icon.vue'
import serviceExampleJson from '../../../examples/service_example.json'

// YAML示例文件内容（作为字符串常量）
const serviceExampleYaml = `
name: 空间转录组预处理
description: 对空间转录组数据进行预处理和质量控制
version: 1.0.0
baseurl: https://api.example.com
service_suffix: /api/service
download_suffix: /api/download
visibility: private
parameter_template:
  normalize: true
  qc_threshold: 0.3
  min_genes: 200
  max_genes: 5000
parameter_schema:
  normalize:
    type: boolean
    default_value: true
    description: 是否进行标准化
    required: false
  qc_threshold:
    type: continuous
    default_value: 0.3
    min_value: 0.0
    max_value: 1.0
    description: 质量控制阈值
    required: true
  min_genes:
    type: discrete
    default_value: 200
    min_value: 0
    max_value: 10000
    description: 最小基因数
    required: true
  max_genes:
    type: discrete
    default_value: 5000
    min_value: 0
    max_value: 50000
    description: 最大基因数
    required: true
  method:
    type: enum
    default_value: standard
    enum_values:
      - standard
      - robust
    description: 标准化方法
    required: true
  output_config:
    collection_description: 输出预处理后的空间转录组数据文件和处理统计信息
    items:
      - type: file
        filename: preprocessed_data.h5ad
        description: 预处理后的空间转录组数据文件（h5ad格式），包含质量控制后的细胞和基因，标准化后的表达矩阵，以及高变基因信息
      - type: text
        filename: 处理统计信息
        description: 包含质量控制统计、标准化统计和最终数据维度等处理统计信息
`

const router = useRouter()
const route = useRoute()
const { t } = useI18n()

const serviceId = computed(() => route.params.id as string | undefined)
const isEditMode = computed(() => !!serviceId.value)

const saving = ref(false)
const formError = ref('')
const configFileInput = ref<HTMLInputElement | null>(null)
const configFormat = ref<'json' | 'yaml'>('json')
const configText = ref('')
const configError = ref('')
const previousFormat = ref<'json' | 'yaml'>('json')

interface ServiceFormData extends Partial<ServiceCreateRequest> {
}

const formData = ref<ServiceFormData>({
  name: '',
  description: '',
  version: '1.0.0',
  baseurl: '',
  service_suffix: '',
  download_suffix: undefined,
  parameter_template: {},
  parameter_schema: undefined,
  accepted_files: undefined,
  output_config: undefined,
  visibility: 'private',
})

// accepted_files 配置
interface AcceptedFileItem {
  filename: string
  file_type_ids: string[]
  description: string
}
const acceptedFilesItems = ref<AcceptedFileItem[]>([])

type OutputItemType = 'file' | 'text'
interface OutputConfigItem {
  type: OutputItemType
  filename: string
  description: string
  file_type_id?: string  // 仅文件类型需要
}

// 输出结果配置
const outputConfigItems = ref<OutputConfigItem[]>([])
const outputConfigCollectionDescription = ref('')

// 输入参数配置
type InputParamType = 'boolean' | 'continuous' | 'discrete' | 'enum' | 'string'
interface InputParamRow {
  name: string
  description: string
  type: InputParamType
  min_value?: number
  max_value?: number
  enum_values?: string[]
  enum_values_text?: string
  default_value?: any
}
const inputParams = ref<InputParamRow[]>([])

function addInputParam() {
  inputParams.value.push({
    name: '',
    description: '',
    type: 'string'
  })
}

function removeInputParam(index: number) {
  inputParams.value.splice(index, 1)
}

// accepted_files 相关函数
function addAcceptedFile() {
  acceptedFilesItems.value.push({
    filename: '',
    file_type_ids: [''],
    description: ''
  })
}

function removeAcceptedFile(index: number) {
  acceptedFilesItems.value.splice(index, 1)
}

function addFileTypeId(fileIndex: number) {
  acceptedFilesItems.value[fileIndex].file_type_ids.push('')
}

function removeFileTypeId(fileIndex: number, typeIndex: number) {
  acceptedFilesItems.value[fileIndex].file_type_ids.splice(typeIndex, 1)
}

// 同步 accepted_files 到 formData
function syncAcceptedFiles() {
  const acceptedFiles: Record<string, { file_type_ids: string[], description: string }> = {}
  for (const item of acceptedFilesItems.value) {
    if (item.filename && item.file_type_ids.length > 0 && item.file_type_ids.some(id => id.trim().length > 0)) {
      acceptedFiles[item.filename] = {
        file_type_ids: item.file_type_ids.filter(id => id.trim().length > 0),
        description: item.description || ''
      }
    }
  }
  formData.value.accepted_files = Object.keys(acceptedFiles).length > 0 ? acceptedFiles : undefined
}

// 从 formData 加载 accepted_files
function loadAcceptedFiles() {
  if (formData.value.accepted_files) {
    acceptedFilesItems.value = Object.entries(formData.value.accepted_files).map(([filename, config]) => ({
      filename,
      file_type_ids: config.file_type_ids && config.file_type_ids.length > 0 ? config.file_type_ids : [''],
      description: config.description || ''
    }))
  } else {
    acceptedFilesItems.value = []
  }
}

// 获取所有可用的文件类型ID（用于 datalist）
const availableFileTypeIds = computed(() => {
  const typeIds = new Set<string>()
  // 从 accepted_files 中收集
  for (const item of acceptedFilesItems.value) {
    for (const typeId of item.file_type_ids) {
      if (typeId.trim()) {
        typeIds.add(typeId.trim())
      }
    }
  }
  // 从输出配置中收集
  for (const item of outputConfigItems.value) {
    if (item.type === 'file' && item.file_type_id) {
      typeIds.add(item.file_type_id)
    }
  }
  return Array.from(typeIds)
})

function normalizeOutputItem(raw: any, fallbackType: OutputItemType = 'file'): OutputConfigItem {
  const type: OutputItemType = raw?.type === 'text' ? 'text' : raw?.type === 'file' ? 'file' : fallbackType
  let filename = typeof raw?.filename === 'string' ? raw.filename : ''
  if (!filename && typeof raw?.text === 'string') {
    filename = raw.text
  }
  const description = typeof raw?.description === 'string' ? raw.description : ''
  const file_type_id = type === 'file' && typeof raw?.file_type_id === 'string' ? raw.file_type_id : undefined
  return { type, filename, description, file_type_id }
}

function sanitizeOutputItems(items: OutputConfigItem[]): Array<{ type: 'file', filename: string, description: string, file_type_id: string } | { type: 'text', filename: string, description: string }> {
  return items.map(item => {
    if (item.type === 'file') {
      return {
        type: 'file' as const,
        filename: item.filename || '',
        description: item.description || '',
        file_type_id: item.file_type_id || ''
      }
    } else {
      return {
        type: 'text' as const,
        filename: item.filename || '',
        description: item.description || ''
      }
    }
  })
}

// 添加输出项
function addOutputItem(type: OutputItemType) {
  const item: OutputConfigItem = {
    type,
    filename: '',
    description: ''
  }
  if (type === 'file') {
    item.file_type_id = ''
  }
  outputConfigItems.value.push(item)
}

// 删除输出项
function removeOutputItem(index: number) {
  outputConfigItems.value.splice(index, 1)
}

// 同步输出配置到 formData
function syncOutputConfig() {
  const sanitizedItems = sanitizeOutputItems(outputConfigItems.value)
  if (sanitizedItems.length > 0) {
    formData.value.output_config = {
      items: sanitizedItems,
      collection_description: outputConfigCollectionDescription.value || undefined
    }
  } else {
    formData.value.output_config = undefined
  }
}

// 从 formData 加载输出配置
function loadOutputConfig() {
  if (formData.value.output_config && formData.value.output_config.items) {
    const clonedItems = JSON.parse(JSON.stringify(formData.value.output_config.items))
    outputConfigItems.value = Array.isArray(clonedItems)
      ? clonedItems.map((item: any) => normalizeOutputItem(item))
      : []
    outputConfigCollectionDescription.value = formData.value.output_config.collection_description || ''
  } else {
    outputConfigItems.value = []
    outputConfigCollectionDescription.value = ''
  }
}

// 从 formData 加载输入参数到编辑表
function loadInputParams() {
  const schema = formData.value.parameter_schema as any
  const template = (formData.value.parameter_template || {}) as Record<string, any>
  inputParams.value = []
  if (schema && typeof schema === 'object') {
    for (const key of Object.keys(schema)) {
      const s = schema[key] || {}
      const row: InputParamRow = {
        name: key,
        description: s.description || '',
        type: (s.type || 'string') as InputParamType,
        min_value: s.min_value,
        max_value: s.max_value,
        enum_values: Array.isArray(s.enum_values) ? s.enum_values : undefined,
        enum_values_text: Array.isArray(s.enum_values) ? s.enum_values.join(',') : undefined,
        default_value: template[key] !== undefined ? template[key] : (s.default_value !== undefined ? s.default_value : undefined)
      }
      inputParams.value.push(row)
    }
  }
}

// 配置文件对象（从configText解析而来）
const configData = computed(() => {
  try {
    if (!configText.value.trim()) {
      return {} // 空配置文件返回空对象，而不是 null
    }
    if (configFormat.value === 'json') {
      return JSON.parse(configText.value)
    } else {
      return yaml.load(configText.value) as any
    }
  } catch (err: any) {
    return null // 解析失败返回 null
  }
})

const isFormValid = computed(() => {
  // 基本字段验证（service_id 现在是可选的，不再作为必填字段）
  const hasRequiredFields = !!(formData.value.name && formData.value.baseurl && formData.value.service_suffix)
  
  // 配置文件验证：
  // 1. 如果没有错误
  // 2. 配置文件解析成功（configData.value !== null）或者配置文件为空（允许为空）
  const isConfigValid = !configError.value && (configData.value !== null || !configText.value.trim())
  
  // accepted_files 验证（可选，但如果有项，必须完整）
  const isAcceptedFilesValid = acceptedFilesItems.value.every(item => 
    item.filename.trim() && 
    item.file_type_ids.length > 0 && 
    item.file_type_ids.some(id => id.trim().length > 0) &&
    item.description.trim()
  )
  
  // 输出配置验证：如果有输出项，文件项必须完整（file_type_id required）；允许空 output_config
  const isOutputConfigValid = outputConfigItems.value.length === 0 || outputConfigItems.value.every(item => {
    if (item.type === 'file') {
      return item.filename.trim() && item.description.trim() && item.file_type_id?.trim()
    } else {
      return item.filename.trim() && item.description.trim()
    }
  })
  
  return hasRequiredFields && isConfigValid && isAcceptedFilesValid && isOutputConfigValid
})

// 监听配置文件格式变化，自动转换
watch(configFormat, (newFormat) => {
  // 如果没有内容，不进行转换
  if (!configText.value.trim()) {
    previousFormat.value = newFormat
    return
  }
  
  // 如果格式没有变化，跳过
  if (newFormat === previousFormat.value) {
    return
  }
  
  const oldFormat = previousFormat.value
  
  try {
    // 先验证当前格式的数据是否有效
    let data: any
    let parseSuccess = false
    
    if (oldFormat === 'json') {
      try {
        data = JSON.parse(configText.value)
        parseSuccess = true
      } catch (err) {
        // JSON无效，尝试按YAML解析（可能用户输入了YAML但选错了格式）
        try {
          data = yaml.load(configText.value)
          parseSuccess = true
          // 说明实际是YAML格式，但用户选择了JSON格式
        } catch {
          // 两种格式都无效
          configError.value = t('service.form.invalidContentCannotConvert')
          previousFormat.value = newFormat
          return
        }
      }
    } else {
      try {
        data = yaml.load(configText.value)
        parseSuccess = true
      } catch (err) {
        // YAML无效，尝试按JSON解析
        try {
          data = JSON.parse(configText.value)
          parseSuccess = true
          // 说明实际是JSON格式，但用户选择了YAML格式
        } catch {
          // 两种格式都无效
          configError.value = t('service.form.invalidContentCannotConvert')
          previousFormat.value = newFormat
          return
        }
      }
    }
    
    if (parseSuccess && data) {
      // 转换为新格式
      if (newFormat === 'json') {
        // YAML转JSON
        configText.value = JSON.stringify(data, null, 2)
      } else {
        // JSON转YAML
        configText.value = yaml.dump(data, { indent: 2, lineWidth: -1 })
      }
      configError.value = ''
    }
  } catch (err: any) {
    configError.value = t('service.form.convertFailed', { error: err?.message || '' })
  }
  
  // 更新上一次的格式
  previousFormat.value = newFormat
}, { immediate: false })

// 验证配置文件
function validateConfig(text: string, format: 'json' | 'yaml'): string {
  if (!text || !text.trim()) {
    return ''
  }
  try {
    if (format === 'json') {
    JSON.parse(text)
    } else {
      yaml.load(text)
    }
    return ''
  } catch (err: any) {
    return (
      err?.message ||
      (format === 'json' ? t('service.form.invalidJsonFormat') : t('service.form.invalidYamlFormat'))
    )
  }
}

// 防止循环更新的标志
const isUpdatingFromConfig = ref(false)
const isUpdatingFromForm = ref(false)

// 监听配置文件变化并验证，同时同步到表单
watch([configText, configFormat], ([text, format]) => {
  configError.value = validateConfig(text, format)
  formError.value = ''
  
  // 如果是从表单更新触发的，跳过
  if (isUpdatingFromForm.value) {
    return
  }
  
  // 如果配置文件格式错误，不进行同步
  if (configError.value) {
    return
  }
  
  // 解析配置文件
  let parsedData: any = null
  try {
    if (text.trim()) {
      if (format === 'json') {
        parsedData = JSON.parse(text)
  } else {
        parsedData = yaml.load(text) as any
      }
    }
  } catch (err) {
    // 解析失败，不进行同步
    return
  }
  
  // 同步所有字段到表单
  if (parsedData) {
    isUpdatingFromConfig.value = true
    // 同步基本信息
    if (parsedData.name !== undefined) formData.value.name = parsedData.name
    if (parsedData.description !== undefined) formData.value.description = parsedData.description || ''
    if (parsedData.version !== undefined) formData.value.version = parsedData.version
    // 处理新的字段结构
    if (parsedData.baseurl !== undefined) formData.value.baseurl = parsedData.baseurl
    if (parsedData.service_suffix !== undefined) formData.value.service_suffix = parsedData.service_suffix
    if (parsedData.download_suffix !== undefined) formData.value.download_suffix = parsedData.download_suffix
    // 向后兼容：如果配置文件中有旧的 url 字段，尝试解析它
    
    if (parsedData.visibility !== undefined) formData.value.visibility = parsedData.visibility
    if (parsedData.parameter_template !== undefined) formData.value.parameter_template = parsedData.parameter_template || {}
    if (parsedData.parameter_schema !== undefined) formData.value.parameter_schema = parsedData.parameter_schema
    
    // 同步 accepted_files
    if (parsedData.accepted_files) {
      formData.value.accepted_files = parsedData.accepted_files
      loadAcceptedFiles()
    } else {
      formData.value.accepted_files = undefined
      loadAcceptedFiles()
    }
    
    // 同步 output_config
    if (parsedData.output_config) {
      formData.value.output_config = parsedData.output_config
      loadOutputConfig()
  } else {
      // 如果配置文件中没有 output_config，清空表单
      formData.value.output_config = undefined
      loadOutputConfig()
    }
    // 同步输入参数表
    loadInputParams()
    // 使用 setTimeout 确保响应式更新完成
    setTimeout(() => {
      isUpdatingFromConfig.value = false
    }, 0)
  }
})

// 监听输出配置变化，同步到 formData 和配置文件
watch([acceptedFilesItems], () => {
  syncAcceptedFiles()
}, { deep: true })

watch([outputConfigItems, outputConfigCollectionDescription], () => {
  // 如果是从配置文件更新触发的，跳过
  if (isUpdatingFromConfig.value) {
    return
  }
  
  // 同步到 formData
  syncOutputConfig()
  
  // 同步到配置文件
  // 先尝试从 configText 解析当前配置
  let currentConfig: any = {}
  try {
    if (configText.value.trim()) {
      if (configFormat.value === 'json') {
        currentConfig = JSON.parse(configText.value)
      } else {
        currentConfig = yaml.load(configText.value) as any
      }
    } else {
      // 如果配置文件为空，使用 formData 构建基础配置
      currentConfig = {
        name: formData.value.name || '',
        description: formData.value.description || '',
        version: formData.value.version || '1.0.0',
        baseurl: formData.value.baseurl || '',
        service_suffix: formData.value.service_suffix || '',
        download_suffix: formData.value.download_suffix,
        visibility: formData.value.visibility || 'private',
        parameter_template: formData.value.parameter_template || {},
        parameter_schema: formData.value.parameter_schema
      }
    }
  } catch (err) {
    // 如果解析失败，使用 formData 构建基础配置
    currentConfig = {
      name: formData.value.name || '',
      description: formData.value.description || '',
      version: formData.value.version || '1.0.0',
      baseurl: formData.value.baseurl || '',
      service_suffix: formData.value.service_suffix || '',
      download_suffix: formData.value.download_suffix,
      visibility: formData.value.visibility || 'private',
      parameter_template: formData.value.parameter_template || {},
      parameter_schema: formData.value.parameter_schema
  }
}

  // 更新 output_config（深拷贝）
  const sanitizedItems = sanitizeOutputItems(outputConfigItems.value)
  if (sanitizedItems.length > 0) {
    currentConfig.output_config = {
      items: sanitizedItems,
      collection_description: outputConfigCollectionDescription.value || undefined
    }
  } else {
    delete currentConfig.output_config
  }
  
  // 更新配置文件文本
  isUpdatingFromForm.value = true
  try {
    if (configFormat.value === 'json') {
      configText.value = JSON.stringify(currentConfig, null, 2)
    } else {
      configText.value = yaml.dump(currentConfig, { indent: 2, lineWidth: -1 })
    }
  } catch (err) {
    // 如果更新失败，忽略错误
  } finally {
    // 使用 setTimeout 确保响应式更新完成
    setTimeout(() => {
      isUpdatingFromForm.value = false
    }, 10)
  }
}, { deep: true })

// 监听输入参数表变化，同步到 formData.parameter_schema 与 parameter_template，并更新配置文件文本
watch([inputParams], () => {
  if (isUpdatingFromConfig.value) return

  // 构建 schema 与 template
  const schema: Record<string, any> = {}
  const template: Record<string, any> = {}
  for (const row of inputParams.value) {
    if (!row.name) continue
    const entry: Record<string, any> = {
      type: row.type,
      description: row.description || '',
      required: true
    }
    // 写入默认值到 schema 与 template
    if (row.default_value !== undefined) {
      entry.default_value = row.default_value
      template[row.name] = row.default_value
    }
    if ((row.type === 'continuous' || row.type === 'discrete') && (row.min_value !== undefined || row.max_value !== undefined)) {
      if (row.min_value !== undefined) entry.min_value = row.min_value
      if (row.max_value !== undefined) entry.max_value = row.max_value
    }
    if (row.type === 'enum') {
      const enums = (row.enum_values_text ?? '')
        .split(',')
        .map(s => s.trim())
        .filter(s => s.length > 0)
      if (enums.length > 0) {
        entry.enum_values = enums
      }
    }
    schema[row.name] = entry
  }
  formData.value.parameter_schema = Object.keys(schema).length > 0 ? schema : undefined
  formData.value.parameter_template = Object.keys(template).length > 0 ? template : {}

  // 同步到配置文件文本
  let currentConfig: any = {}
  try {
    if (configText.value.trim()) {
      currentConfig = configFormat.value === 'json' ? JSON.parse(configText.value) : yaml.load(configText.value)
    } else {
      currentConfig = {}
    }
  } catch {
    currentConfig = {}
  }
  if (formData.value.parameter_schema !== undefined) {
    currentConfig.parameter_schema = formData.value.parameter_schema
  } else {
    delete currentConfig.parameter_schema
  }
  if (formData.value.parameter_template && Object.keys(formData.value.parameter_template).length > 0) {
    currentConfig.parameter_template = formData.value.parameter_template
  } else {
    currentConfig.parameter_template = {}
  }

  isUpdatingFromForm.value = true
  try {
    configText.value = configFormat.value === 'json'
      ? JSON.stringify(currentConfig, null, 2)
      : yaml.dump(currentConfig, { indent: 2, lineWidth: -1 })
  } finally {
    setTimeout(() => { isUpdatingFromForm.value = false }, 10)
  }
}, { deep: true })

// 监听表单字段变化，同步到配置文件
watch([
  () => formData.value.name,
  () => formData.value.description,
  () => formData.value.version,
  () => formData.value.baseurl,
  () => formData.value.service_suffix,
  () => formData.value.download_suffix,
  () => formData.value.visibility,
  () => formData.value.parameter_template,
  () => formData.value.parameter_schema
], () => {
  // 如果是从配置文件更新触发的，跳过
  if (isUpdatingFromConfig.value) {
    return
  }
  
  // 同步到配置文件
  let currentConfig: any = {}
  try {
    if (configText.value.trim()) {
      if (configFormat.value === 'json') {
        currentConfig = JSON.parse(configText.value)
      } else {
        currentConfig = yaml.load(configText.value) as any
      }
    }
  } catch (err) {
    // 如果解析失败，使用空对象
    currentConfig = {}
  }
  
  // 更新所有字段
  currentConfig.name = formData.value.name || ''
  currentConfig.description = formData.value.description || ''
  currentConfig.version = formData.value.version || '1.0.0'
  currentConfig.baseurl = formData.value.baseurl || ''
  currentConfig.service_suffix = formData.value.service_suffix || ''
  if (formData.value.download_suffix !== undefined) {
    currentConfig.download_suffix = formData.value.download_suffix
  }
  currentConfig.visibility = formData.value.visibility || 'private'
  currentConfig.parameter_template = formData.value.parameter_template || {}
  if (formData.value.parameter_schema !== undefined) {
    currentConfig.parameter_schema = formData.value.parameter_schema
  }
  
  // 更新配置文件文本
  isUpdatingFromForm.value = true
  try {
    if (configFormat.value === 'json') {
      configText.value = JSON.stringify(currentConfig, null, 2)
    } else {
      configText.value = yaml.dump(currentConfig, { indent: 2, lineWidth: -1 })
    }
  } catch (err) {
    // 如果更新失败，忽略错误
  } finally {
    setTimeout(() => {
      isUpdatingFromForm.value = false
    }, 10)
  }
}, { deep: true })

// 加载 Service 数据（编辑模式）
async function loadServiceData() {
  if (!serviceId.value) return
  
  try {
    const service = await getServiceDetail(serviceId.value)
    formData.value = {
      name: service.name,
      description: service.description || '',
      version: service.version,
      baseurl: service.baseurl,
      service_suffix: service.service_suffix,
      download_suffix: service.download_suffix,
      parameter_template: service.parameter_template || {},
      parameter_schema: service.parameter_schema,
      accepted_files: service.accepted_files,
      output_config: service.output_config,
      visibility: service.visibility || 'private',
    }
    loadAcceptedFiles()
    loadOutputConfig()
    loadInputParams()
    
    // 构建完整的配置对象
    const fullConfig = {
      description: service.description || '',
      version: service.version,
      baseurl: service.baseurl,
      service_suffix: service.service_suffix,
      download_suffix: service.download_suffix,
      visibility: service.visibility || 'private',
      parameter_template: service.parameter_template || {},
      parameter_schema: service.parameter_schema,
      accepted_files: service.accepted_files,
      output_config: service.output_config
    }
    
    // 默认使用JSON格式显示
    configFormat.value = 'json'
    previousFormat.value = 'json'
    configText.value = JSON.stringify(fullConfig, null, 2)
  } catch (err: any) {
    console.error('加载Service失败:', err)
    
    // 提取错误信息
    let errorMessage = t('service.form.loadFailed')
    
    if (err) {
      if (err.name === 'ApiError' || err.code) {
        errorMessage = err.message || err.data?.message || errorMessage
      } else if (err.response?.data) {
        const responseData = err.response.data
        errorMessage = responseData.message || responseData.detail || errorMessage
      } else if (err.message) {
        errorMessage = err.message
      }
    }
    
    formError.value = errorMessage
    
    // 显示全局错误提示
    if (window.showMessage) {
      window.showMessage.error(errorMessage)
    }
  }
}

// 从配置文件解析并填充表单
function parseConfigFile(data: any) {
  // 填充基本信息
  if (data.name) formData.value.name = data.name
  if (data.description !== undefined) formData.value.description = data.description || ''
  if (data.version) formData.value.version = data.version
  if (data.baseurl) formData.value.baseurl = data.baseurl
  if (data.service_suffix) formData.value.service_suffix = data.service_suffix
  if (data.download_suffix !== undefined) formData.value.download_suffix = data.download_suffix
  
  if (data.visibility) formData.value.visibility = data.visibility
  if (data.output_config !== undefined) {
    formData.value.output_config = data.output_config
    loadOutputConfig()
  }
  
  // 更新配置文件文本
  const currentFormat = configFormat.value
  if (currentFormat === 'json') {
    configText.value = JSON.stringify(data, null, 2)
    previousFormat.value = 'json'
  } else {
    configText.value = yaml.dump(data, { indent: 2, lineWidth: -1 })
    previousFormat.value = 'yaml'
  }
}

// 触发配置文件上传
function triggerConfigFileUpload() {
  configFileInput.value?.click()
}

// 处理配置文件上传
function handleConfigFileUpload(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return

  // 限制文件大小为 512MB
  const MAX_SIZE = 512 * 1024 * 1024
  if (file.size > MAX_SIZE) {
    if (window.showMessage) {
      window.showMessage.error(t('service.form.fileTooLarge'))
    }
    if (configFileInput.value) configFileInput.value.value = ''
    return
  }

  const fileName = file.name.toLowerCase()
  const isJson = fileName.endsWith('.json')
  const isYaml = fileName.endsWith('.yaml') || fileName.endsWith('.yml')
  
  if (!isJson && !isYaml) {
    if (window.showMessage) {
      window.showMessage.error(t('service.form.unsupportedFile'))
    }
    if (configFileInput.value) {
      configFileInput.value.value = ''
    }
    return
  }

  const reader = new FileReader()
  reader.onload = (e) => {
    try {
      const fileContent = e.target?.result as string
      let data: any
      
      if (isJson) {
        data = JSON.parse(fileContent)
        configFormat.value = 'json'
        previousFormat.value = 'json'
      } else {
        data = yaml.load(fileContent) as any
        configFormat.value = 'yaml'
        previousFormat.value = 'yaml'
      }
      
      // 解析并填充表单
      parseConfigFile(data)
      
      if (window.showMessage) {
        window.showMessage.success(t('service.form.parseSuccess'))
      }
    } catch (err: any) {
      if (window.showMessage) {
        window.showMessage.error(t('service.form.parseFailed', { error: err.message || 'format error' }))
      }
    }
    
    if (configFileInput.value) {
      configFileInput.value.value = ''
    }
  }
  
  reader.onerror = () => {
    if (window.showMessage) {
      window.showMessage.error(t('service.form.fileReadFailed'))
    }
    if (configFileInput.value) {
      configFileInput.value.value = ''
    }
  }
  
  reader.readAsText(file)
}

// 下载示例JSON文件
function downloadExampleJson() {
  try {
    const exampleData = {
      ...serviceExampleJson,
      visibility: 'private',
    }
    const blob = new Blob([JSON.stringify(exampleData, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'service_example.json'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    
    if (window.showMessage) {
      window.showMessage.success(t('service.form.exampleJsonDownloaded'))
    }
  } catch (err: any) {
    if (window.showMessage) {
      window.showMessage.error(t('service.form.downloadFailed'))
    }
  }
}

// 下载示例YAML文件
function downloadExampleYaml() {
  try {
    const blob = new Blob([serviceExampleYaml], { type: 'text/yaml' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'service_example.yml'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    
    if (window.showMessage) {
      window.showMessage.success(t('service.form.exampleYamlDownloaded'))
    }
  } catch (err: any) {
    if (window.showMessage) {
      window.showMessage.error(t('service.form.downloadFailed'))
    }
  }
}

// 返回
function handleBack() {
  router.push('/services')
}

// 保存
async function handleSave() {
  if (!isFormValid.value) {
    formError.value = t('service.form.fillRequired')
    return
  }

  try {
    saving.value = true
    formError.value = ''

    // 解析配置文件（如果配置文件为空，使用空对象）
    const config = configData.value || {} as any

    // 同步所有配置
    syncAcceptedFiles()
    syncOutputConfig()
    
    // 合并配置：表单数据优先（inputParams/acceptedFiles/outputConfig 由 watch 实时同步到 formData），配置文件补充兜底
    const submitData: any = {
      name: formData.value.name || config.name,
      description: formData.value.description || config.description || '',
      version: formData.value.version || config.version || '1.0.0',
      baseurl: formData.value.baseurl || config.baseurl,
      service_suffix: formData.value.service_suffix || config.service_suffix,
      download_suffix: formData.value.download_suffix !== undefined ? formData.value.download_suffix : (config.download_suffix !== undefined ? config.download_suffix : undefined),
      visibility: formData.value.visibility || config.visibility || 'private',
      // formData.parameter_template/schema 由 inputParams watch 实时维护，优先使用
      parameter_template: (formData.value.parameter_template && Object.keys(formData.value.parameter_template).length > 0)
        ? formData.value.parameter_template
        : (config.parameter_template || {}),
      parameter_schema: formData.value.parameter_schema !== undefined
        ? formData.value.parameter_schema
        : config.parameter_schema,
      accepted_files: formData.value.accepted_files || config.accepted_files,
      output_config: formData.value.output_config || config.output_config
    }


    if (isEditMode.value) {
      await updateService(serviceId.value!, submitData)
    } else {
      await createService(submitData as ServiceCreateRequest)
    }

    // 显示成功消息（延长显示时间，让用户看到反馈）
    if (window.showMessage) {
      window.showMessage.success(
        isEditMode.value ? t('service.form.updateSuccess') : t('service.form.createSuccess'),
        2000 // 显示2秒
      )
    }
    
    // 延迟跳转，确保用户看到成功消息
    setTimeout(() => {
      router.push('/services').catch((err) => {
        // 忽略导航重复的错误
        if (err.name !== 'NavigationDuplicated') {
          console.error('路由跳转失败:', err)
          // 如果跳转失败，尝试使用 replace
          router.replace('/services').catch(() => {
            // 如果 replace 也失败，使用 window.location
            window.location.href = '/services'
          })
        }
      })
    }, 500) // 延迟500ms跳转，让用户看到成功消息
  } catch (err: any) {
    console.error('保存Service失败:', err)
    
    // 提取错误信息
    let errorMessage = t('service.form.saveFailed')
    
    if (err) {
      // 如果是 ApiError，提取详细错误信息
      if (err.name === 'ApiError' || err.code) {
        errorMessage = err.message || err.data?.message || errorMessage
        // 如果有详细的验证错误，也显示
        if (err.data?.detail) {
          if (typeof err.data.detail === 'string') {
            errorMessage = err.data.detail
          } else if (Array.isArray(err.data.detail)) {
            errorMessage = err.data.detail.map((d: any) => {
              if (typeof d === 'string') return d
              if (d.msg) return d.msg
              if (d.message) return d.message
              return JSON.stringify(d)
            }).join('; ')
          } else if (typeof err.data.detail === 'object') {
            errorMessage = Object.entries(err.data.detail)
              .map(([key, value]: [string, any]) => {
                if (Array.isArray(value)) {
                  return `${key}: ${value.join(', ')}`
                }
                return `${key}: ${value}`
              })
              .join('; ')
          }
        }
      } else if (err.response?.data) {
        // 处理 axios 错误响应
        const responseData = err.response.data
        errorMessage = responseData.message || responseData.detail || errorMessage
        if (responseData.detail && typeof responseData.detail === 'object') {
          const detailMessages = Object.entries(responseData.detail)
            .map(([key, value]: [string, any]) => {
              if (Array.isArray(value)) {
                return `${key}: ${value.join(', ')}`
              }
              return `${key}: ${value}`
            })
            .join('; ')
          if (detailMessages) {
            errorMessage = detailMessages
          }
        }
      } else if (err.message) {
        errorMessage = err.message
      }
    }
    
    // 设置表单错误
    formError.value = errorMessage
    
    // 同时显示全局错误提示
    if (window.showMessage) {
      window.showMessage.error(errorMessage)
    }
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  if (isEditMode.value) {
    loadServiceData()
  } else {
    // 创建模式：初始化示例配置
    const exampleConfig = {
      name: '',
      description: '',
      version: '1.0.0',
      url: '',
      parameter_template: {},
      parameter_schema: undefined,
      output_config: undefined,
      visibility: 'private',

    }
    configFormat.value = 'json'
    previousFormat.value = 'json'
    configText.value = JSON.stringify(exampleConfig, null, 2)
    // 确保表单也同步初始化
    formData.value.output_config = undefined
    loadOutputConfig()
    inputParams.value = []
  }
})
</script>

<style scoped>
/* 输入参数配置编辑器样式 */
.input-config-editor {
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: var(--spacing-md);
  background: var(--bg-primary);
}

.empty-input-config {
  text-align: center;
  padding: var(--spacing-xl);
  color: var(--text-secondary);
}

.empty-input-config p {
  margin-bottom: var(--spacing-md);
}

.input-items-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.input-items-actions-top {
  display: flex;
  justify-content: flex-end;
}

.input-table-wrapper {
  width: 100%;
  overflow-x: auto;
}

.input-table {
  width: 100%;
  border-collapse: collapse;
}

.input-table th,
.input-table td {
  padding: 8px;
  border: 1px solid var(--border-color);
  vertical-align: middle;
}

.constraint-row {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
}

.constraint-sep {
  padding: 0 4px;
  color: var(--text-tertiary);
}

.text-muted {
  color: var(--text-tertiary);
  font-size: var(--font-size-sm);
}

/* 输出结果配置编辑器样式 */
.output-config-editor {
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: var(--spacing-md);
  background: var(--bg-primary);
}

.empty-output-config {
  text-align: center;
  padding: var(--spacing-xl);
  color: var(--text-secondary);
}

.empty-output-config p {
  margin-bottom: var(--spacing-md);
}

.empty-output-config .button {
  margin: 0 var(--spacing-xs);
}

.output-items-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.output-item-card {
  border: 1px solid var(--border-color);
  border-radius: 10px;
  padding: 1.25rem;
  background: var(--bg-secondary);
  transition: all 0.2s ease;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.output-item-card:hover {
  border-color: var(--accent-primary);
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.1);
}

.output-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-md);
  padding-bottom: var(--spacing-sm);
  border-bottom: 1px solid var(--border-color);
}

.output-item-type-badge {
  display: inline-flex;
  align-items: center;
  padding: 0.375rem 0.875rem;
  border-radius: 6px;
  font-size: 0.8125rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.output-item-type-badge.type-file {
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  color: white;
}

.output-item-type-badge.type-text {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  color: white;
}

.output-item-content {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

/* accepted_files 编辑器样式 */
.accepted-files-editor {
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: var(--spacing-md);
  background: var(--bg-primary);
}

.empty-accepted-files {
  text-align: center;
  padding: var(--spacing-xl);
  color: var(--text-secondary);
}

.empty-accepted-files p {
  margin-bottom: var(--spacing-md);
  font-size: 0.9rem;
}

.accepted-files-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.accepted-file-card {
  border: 1px solid var(--border-color);
  border-radius: 10px;
  padding: 1.25rem;
  background: var(--bg-secondary);
  transition: all 0.2s ease;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.accepted-file-card:hover {
  border-color: var(--accent-primary);
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.1);
}

.accepted-file-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-md);
  padding-bottom: var(--spacing-sm);
  border-bottom: 1px solid var(--border-color);
}

.accepted-file-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.375rem 0.875rem;
  background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
  color: white;
  border-radius: 6px;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', 'Consolas', monospace;
  font-size: 0.8125rem;
  font-weight: 500;
  box-shadow: 0 2px 4px rgba(37, 99, 235, 0.2);
}

.accepted-file-content {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.file-type-ids-input {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-sm);
  align-items: center;
}

.file-type-id-tag {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-xs);
  padding: 0.375rem 0.75rem;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  transition: all 0.2s ease;
}

.file-type-id-tag:hover {
  border-color: var(--accent-primary);
  box-shadow: 0 2px 4px rgba(37, 99, 235, 0.1);
}

.file-type-id-tag .tag-input {
  border: none;
  padding: 0.25rem 0.5rem;
  background: transparent;
  font-size: 0.875rem;
  min-width: 120px;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', 'Consolas', monospace;
  color: var(--text-primary);
  transition: all 0.2s ease;
}

.file-type-id-tag .tag-input::placeholder {
  color: var(--text-tertiary);
  font-style: italic;
}

.file-type-id-tag .tag-input:focus {
  outline: none;
  background: rgba(37, 99, 235, 0.05);
  border-radius: 4px;
}

.file-type-id-tag .button-icon-small {
  padding: 0.125rem;
  color: var(--text-secondary);
  transition: all 0.2s ease;
}

.file-type-id-tag .button-icon-small:hover {
  color: #ef4444;
  background: rgba(239, 68, 68, 0.1);
}

.file-type-id-input-wrapper {
  position: relative;
}

.file-type-id-input {
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', 'Consolas', monospace;
  font-size: 0.875rem;
  transition: all 0.2s ease;
}

.file-type-id-input:focus {
  border-color: var(--accent-primary);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

.accepted-files-actions {
  display: flex;
  gap: var(--spacing-sm);
  margin-top: var(--spacing-md);
  padding-top: var(--spacing-md);
  border-top: 1px solid var(--border-color);
}

.button-icon-small {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  padding: 0;
  background: transparent;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.button-small {
  padding: 0.375rem 0.75rem;
  font-size: 0.8125rem;
  height: auto;
}

.form-group-inline {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.form-group-inline label {
  font-size: var(--font-size-sm);
  font-weight: 500;
  color: var(--text-primary);
}

.output-items-actions {
  display: flex;
  gap: var(--spacing-sm);
  margin-top: var(--spacing-md);
  padding-top: var(--spacing-md);
  border-top: 1px solid var(--border-color);
}

.button-icon {
  background: transparent;
  border: none;
  padding: var(--spacing-xs);
  cursor: pointer;
  color: var(--text-secondary);
  border-radius: var(--radius-sm);
  transition: all 0.2s;
}

.button-icon:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

/* ServiceDetail 输出结果显示样式 */
.output-items-display {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
  margin-top: var(--spacing-md);
}

.output-item-display {
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: var(--spacing-md);
  background: var(--bg-secondary);
}

.output-item-display .output-item-header {
  margin-bottom: var(--spacing-md);
  padding-bottom: var(--spacing-sm);
  border-bottom: 1px solid var(--border-color);
}

.output-item-display .output-item-content {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.service-form-page {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100%;
  background: var(--bg-secondary);
  overflow: hidden;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-lg) var(--spacing-xl);
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-primary);
  flex-shrink: 0;
}

.page-header-left {
  display: flex;
  align-items: center;
  gap: var(--spacing-lg);
}

.back-btn {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: 4px 11px;
  height: 32px;
  background: transparent;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  color: rgba(0, 0, 0, 0.65);
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.645, 0.045, 0.355, 1);
  font-size: 14px;
  font-weight: 400;
  line-height: 1.5715;
}

.back-btn:focus {
  outline: none;
  border-color: #40a9ff;
  box-shadow: 0 0 0 2px rgba(24, 144, 255, 0.2);
}

.back-btn:hover {
  background: var(--bg-secondary);
  color: var(--text-primary);
}

.back-icon {
  transform: rotate(90deg);
}

.page-header h1 {
  margin: 0;
  font-size: 20px;
  font-weight: 500;
  line-height: 1.4;
  color: rgba(0, 0, 0, 0.85);
  letter-spacing: 0;
}

.page-header-right {
  display: flex;
  gap: var(--spacing-md);
}

.form-container {
  flex: 1;
  display: grid;
  grid-template-columns: 1fr 1fr; /* 左右大小相同 */
  gap: var(--spacing-xl);
  padding: var(--spacing-xl);
  overflow: hidden;
}

.form-left,
.form-right {
  overflow-y: auto;
  background: var(--bg-primary);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-color);
  padding: var(--spacing-xl);
}

.form-section {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
  height: 100%;
}

.section-title {
  margin: 0;
  font-size: 16px;
  font-weight: 500;
  line-height: 1.5;
  color: rgba(0, 0, 0, 0.85);
  letter-spacing: 0;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--spacing-md);
}

.section-actions {
  display: flex;
  gap: var(--spacing-sm);
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.form-group label {
  font-size: 14px;
  font-weight: 400;
  line-height: 1.5715;
  color: rgba(0, 0, 0, 0.85);
}

.required {
  color: rgba(220, 100, 100, 0.9);
}

.form-hint {
  font-size: 12px;
  color: var(--text-tertiary);
}

/* 格式切换器 */
.format-switcher {
  display: flex;
  gap: var(--spacing-xs);
  border-bottom: 1px solid var(--border-color);
  margin-bottom: var(--spacing-lg);
}

.format-btn {
  padding: 8px 16px;
  border: none;
  background: transparent;
  border-bottom: 2px solid transparent;
  color: rgba(0, 0, 0, 0.65);
  font-size: 14px;
  font-weight: 400;
  line-height: 1.5715;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.645, 0.045, 0.355, 1);
}

.format-btn:hover {
  color: var(--text-primary);
}

.format-btn.active {
  color: #1890ff;
  font-weight: 500;
  border-bottom-color: #1890ff;
}

/* 配置文件编辑器 */
.config-editor-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.config-editor {
  flex: 1;
  padding: 4px 11px;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  background: var(--bg-secondary);
  color: rgba(0, 0, 0, 0.85);
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', 'Consolas', 'monospace';
  font-size: 13px;
  font-weight: 400;
  line-height: 1.5715;
  resize: none;
  transition: all 0.2s cubic-bezier(0.645, 0.045, 0.355, 1);
  min-height: 400px;
}

.config-editor:hover {
  border-color: #40a9ff;
}

.config-editor:focus {
  outline: none;
  border-color: #40a9ff;
  box-shadow: 0 0 0 2px rgba(24, 144, 255, 0.2);
}

.config-editor.config-error {
  border-color: rgba(220, 100, 100, 0.6);
}

.config-error-message {
  font-size: 12px;
  font-weight: 400;
  line-height: 1.5715;
  color: #ff4d4f;
  padding: 4px 0;
}

.config-stats {
  font-size: 12px;
  font-weight: 400;
  line-height: 1.5715;
  color: rgba(0, 0, 0, 0.45);
  padding: 4px 0;
}

.form-error-toast {
  position: fixed;
  bottom: var(--spacing-xl);
  left: 50%;
  transform: translateX(-50%);
  padding: 8px 16px;
  background: #ff4d4f;
  color: white;
  border-radius: 6px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  z-index: 3000;
  font-size: 14px;
  font-weight: 400;
  line-height: 1.5715;
  animation: slideUp 0.3s ease;
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translate(-50%, 20px);
  }
  to {
    opacity: 1;
    transform: translate(-50%, 0);
  }
}

/* 保存按钮样式 */
.button-primary {
  background: #1890ff;
  color: white;
  border: 1px solid #1890ff;
  transition: all 0.2s cubic-bezier(0.645, 0.045, 0.355, 1);
}

.button-primary:hover:not(:disabled) {
  background: #40a9ff;
  border-color: #40a9ff;
  box-shadow: 0 2px 8px rgba(24, 144, 255, 0.3);
}

.button-primary:active:not(:disabled) {
  background: #096dd9;
  border-color: #096dd9;
}

.button-primary:disabled {
  background: #d9d9d9;
  border-color: #d9d9d9;
  color: rgba(0, 0, 0, 0.25);
  cursor: not-allowed;
}

.button-saving {
  position: relative;
  pointer-events: none;
}

.save-spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  margin-right: 8px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  vertical-align: middle;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
