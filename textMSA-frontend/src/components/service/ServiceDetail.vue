<template>
  <div class="service-detail">
    <div class="detail-section">
      <h3>{{ $t('service.detail.basicInfo') }}</h3>
      <div class="detail-item">
        <span class="detail-label">Service ID:</span>
        <span class="detail-value">{{ service.service_id }}</span>
      </div>
      <div class="detail-item">
        <span class="detail-label">{{ $t('service.form.name') }}:</span>
        <span class="detail-value">{{ service.name }}</span>
      </div>
      <div v-if="service.description" class="detail-item">
        <span class="detail-label">{{ $t('service.form.description') }}:</span>
        <span class="detail-value">{{ service.description }}</span>
      </div>
      <div class="detail-item">
        <span class="detail-label">{{ $t('service.form.version') }}:</span>
        <span class="detail-value">{{ service.version }}</span>
      </div>
      <div class="detail-item">
        <span class="detail-label">{{ $t('service.form.baseurl') }}:</span>
        <span class="detail-value detail-value-url">{{ service.baseurl }}</span>
      </div>
      <div v-if="service.service_suffix" class="detail-item">
        <span class="detail-label">{{ $t('service.form.serviceSuffix') }}:</span>
        <span class="detail-value detail-value-url">{{ service.service_suffix }}</span>
      </div>
      <div v-if="service.download_suffix" class="detail-item">
        <span class="detail-label">{{ $t('service.form.downloadSuffix') }}:</span>
        <span class="detail-value detail-value-url">{{ service.download_suffix }}</span>
      </div>
      <div class="detail-item">
        <span class="detail-label">{{ $t('service.form.visibility') }}:</span>
        <span class="detail-value">
          <span class="service-visibility-badge" :class="`visibility-${service.visibility || 'private'}`">
            {{ service.visibility || 'private' }}
          </span>
        </span>
      </div>
    </div>



    <div v-if="service.parameter_template && Object.keys(service.parameter_template).length > 0" class="detail-section">
      <h3>{{ $t('service.detail.parameterTemplate') }}</h3>
      <pre class="config-json">{{ JSON.stringify(service.parameter_template, null, 2) }}</pre>
    </div>

    <div v-if="service.parameter_schema && Object.keys(service.parameter_schema).length > 0" class="detail-section">
      <h3>{{ $t('service.detail.parameterSchema') }}</h3>
      <pre class="config-json">{{ JSON.stringify(service.parameter_schema, null, 2) }}</pre>
    </div>

    <!-- accepted_files 显示区域 -->
    <div v-if="service.accepted_files && Object.keys(service.accepted_files).length > 0" class="detail-section">
      <h3>{{ $t('service.detail.acceptedFiles') }}</h3>
      <div class="accepted-files-list">
        <div 
          v-for="(config, filename) in service.accepted_files" 
          :key="filename"
          class="accepted-file-item"
        >
          <div class="accepted-file-header">
            <span class="filename-badge">{{ filename }}</span>
          </div>
          <div class="accepted-file-content">
            <div class="detail-item">
              <span class="detail-label">{{ $t('service.detail.fileTypeIds') }}:</span>
              <div class="file-type-ids-tags">
                <span 
                  v-for="typeId in config.file_type_ids" 
                  :key="typeId"
                  class="file-type-id-tag"
                >
                  {{ typeId }}
                </span>
              </div>
            </div>
            <div v-if="config.description" class="detail-item">
              <span class="detail-label">{{ $t('service.detail.description') }}:</span>
              <span class="detail-value">{{ config.description }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
    <div v-else class="detail-section">
      <h3>{{ $t('service.detail.acceptedFiles') }}</h3>
      <p class="empty-message">{{ $t('service.detail.noAcceptedFiles') }}</p>
    </div>

    <div v-if="service.output_config" class="detail-section">
      <h3>{{ $t('service.detail.outputConfig') }}</h3>
      <div v-if="service.output_config.collection_description" class="detail-item">
        <span class="detail-label">{{ $t('service.detail.collectionDescription') }}:</span>
        <span class="detail-value">{{ service.output_config.collection_description }}</span>
      </div>
      <div v-if="service.output_config.items && service.output_config.items.length > 0" class="output-items-display">
        <div v-for="(item, index) in service.output_config.items" :key="index" class="output-item-display">
          <div class="output-item-header">
            <span class="output-item-type-badge" :class="`type-${item.type}`">
              {{ item.type === 'file' ? $t('service.detail.fileType') : $t('service.detail.textType') }}
            </span>
          </div>
          <div class="output-item-content">
            <div class="detail-item">
              <span class="detail-label">{{ $t('service.detail.filename') }}:</span>
              <span class="detail-value">{{ item.filename }}</span>
            </div>
            <div v-if="item.type === 'file' && item.file_type_id" class="detail-item">
              <span class="detail-label">{{ $t('service.detail.fileTypeId') }}:</span>
              <span class="detail-value file-type-id-value">{{ item.file_type_id }}</span>
            </div>
            <div v-if="item.type === 'file' && !item.file_type_id" class="detail-item warning">
              <span class="detail-label">{{ $t('service.detail.fileTypeId') }}:</span>
              <span class="detail-value warning-text">{{ $t('service.detail.fileTypeIdNotSet') }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">{{ $t('service.detail.outputDescription') }}:</span>
              <span class="detail-value">{{ item.description }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="detail-section">
      <h3>{{ $t('service.detail.metadata') }}</h3>
      <div class="detail-item">
        <span class="detail-label">{{ $t('service.detail.createdAt') }}:</span>
        <span class="detail-value">{{ formatDate(service.created_at) }}</span>
      </div>
      <div class="detail-item">
        <span class="detail-label">{{ $t('service.detail.updatedAt') }}:</span>
        <span class="detail-value">{{ formatDate(service.updated_at) }}</span>
      </div>
      <div v-if="service.created_by" class="detail-item">
        <span class="detail-label">{{ $t('service.detail.createdBy') }}:</span>
        <span class="detail-value">{{ service.created_by }}</span>
      </div>
    </div>

    <div class="detail-actions">
      <el-button type="primary" @click="$emit('edit', service)">{{ $t('common.edit') }}</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { type Service } from '../../api/service'

defineProps<{
  service: Service
}>()

defineEmits<{
  edit: [service: Service]
}>()

function formatDate(date?: string): string {
  if (!date) return '-'
  return new Date(date).toLocaleString('zh-CN')
}
</script>

<style scoped>
.service-detail {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.service-visibility-badge {
  padding: 0 8px;
  border-radius: 2px;
  font-size: 12px;
  font-weight: 400;
  line-height: 1.5715;
}

.visibility-private {
  background: rgba(120, 120, 120, 0.15);
  color: rgba(80, 80, 80, 0.95);
}

.visibility-public {
  background: rgba(40, 140, 240, 0.15);
  color: rgba(20, 100, 200, 0.95);
}

.visibility-system {
  background: rgba(250, 160, 60, 0.18);
  color: rgba(200, 120, 30, 0.95);
}

.detail-section {
  border-bottom: 1px solid var(--border-color);
  padding-bottom: 1rem;
}

.detail-section:last-of-type {
  border-bottom: none;
}

.detail-section h3 {
  margin: 0 0 0.75rem 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
}

.detail-item {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
  font-size: 0.9rem;
}

.detail-label {
  color: var(--text-secondary);
  font-weight: 500;
  min-width: 100px;
}

.detail-value {
  color: var(--text-primary);
  flex: 1;
}

.detail-value-url {
  font-family: monospace;
  font-size: 0.85rem;
  word-break: break-all;
}

.status-badge {
  display: inline-block;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.85rem;
  font-weight: 500;
}

.status-active {
  background: rgba(100, 200, 100, 0.2);
  color: rgba(50, 150, 50, 0.9);
}

.status-inactive {
  background: rgba(200, 200, 200, 0.2);
  color: rgba(120, 120, 120, 0.9);
}

.status-deprecated {
  background: rgba(220, 100, 100, 0.2);
  color: rgba(180, 50, 50, 0.9);
}


.config-json {
  background: var(--bg-tertiary);
  padding: 1rem;
  border-radius: 6px;
  font-family: monospace;
  font-size: 0.85rem;
  color: var(--text-primary);
  overflow-x: auto;
  margin: 0;
}

.detail-actions {
  padding-top: 1rem;
  border-top: 1px solid var(--border-color);
}

/* 输出结果配置显示样式 */
.output-items-display {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
  margin-top: var(--spacing-md);
}

.output-item-display {
  border: 1px solid var(--border-color);
  border-radius: 10px;
  padding: 1.25rem;
  background: var(--bg-secondary);
  transition: all 0.2s ease;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.output-item-display:hover {
  border-color: var(--accent-primary);
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.1);
}

.output-item-display .output-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  padding-bottom: 0.75rem;
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

.output-item-display .output-item-content {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

/* accepted_files 显示样式 */
.accepted-files-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  margin-top: 0.75rem;
}

.accepted-file-item {
  border: 1px solid var(--border-color);
  border-radius: 10px;
  padding: 1.25rem;
  background: var(--bg-secondary);
  transition: all 0.2s ease;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.accepted-file-item:hover {
  border-color: var(--accent-primary);
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.1);
}

.accepted-file-header {
  margin-bottom: 1rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid var(--border-color);
}

.filename-badge {
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

.file-type-ids-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.625rem;
  align-items: center;
}

.file-type-id-tag {
  display: inline-flex;
  align-items: center;
  padding: 0.375rem 0.875rem;
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  color: white;
  border-radius: 6px;
  font-size: 0.8125rem;
  font-weight: 500;
  box-shadow: 0 2px 4px rgba(59, 130, 246, 0.2);
  transition: all 0.2s ease;
}

.file-type-id-tag:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(59, 130, 246, 0.3);
}

.file-type-id-value {
  display: inline-flex;
  align-items: center;
  padding: 0.25rem 0.625rem;
  background: rgba(37, 99, 235, 0.1);
  color: #2563eb;
  border-radius: 4px;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', 'Consolas', monospace;
  font-size: 0.875rem;
  font-weight: 500;
  border: 1px solid rgba(37, 99, 235, 0.2);
}

.warning-text {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  color: #f59e0b;
  font-weight: 500;
  padding: 0.25rem 0.625rem;
  background: rgba(245, 158, 11, 0.1);
  border-radius: 4px;
  border: 1px solid rgba(245, 158, 11, 0.2);
}

.detail-item.warning {
  border-left: 3px solid #f59e0b;
  padding-left: 0.75rem;
  background: rgba(245, 158, 11, 0.05);
  border-radius: 4px;
  padding-top: 0.5rem;
  padding-bottom: 0.5rem;
  margin-left: -0.75rem;
}

.empty-message {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2rem;
  color: var(--text-tertiary);
  font-style: italic;
  background: var(--bg-tertiary);
  border-radius: 8px;
  border: 1px dashed var(--border-color);
}
</style>
