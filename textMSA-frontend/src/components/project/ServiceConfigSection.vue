<template>
  <div v-if="isEditMode" class="form-section">
    <h2 class="section-title">{{ $t('project.serviceConfig') }}</h2>
    
    <div class="form-group">
      <label>{{ $t('project.serviceMode') }}</label>
      <el-select 
        :model-value="serviceSelection.serviceMode.value"
        :placeholder="$t('project.serviceMode')"
        @change="handleModeChange"
      >
        <el-option :label="$t('project.modeAll')" value="all" />
        <el-option :label="$t('project.modeWhitelist')" value="whitelist" />
      </el-select>
    </div>

    <div v-if="serviceSelection.serviceMode.value === 'whitelist'" class="form-group">
      <label>{{ $t('project.selectService') }}</label>
      <MultiSelectList
        :items="serviceSelection.availableServiceList.value || []"
        :selected-ids="serviceSelection.selectedServiceIds.value || []"
        :loading="serviceSelection.loadingServices.value || false"
        :error="serviceSelection.serviceError.value || null"
        :search-keyword="serviceSelection.searchServiceKeyword.value || ''"
        :search-placeholder="$t('project.searchService')"
        :empty-message="$t('project.noServiceData')"
        :item-label="$t('project.serviceLabel')"
        item-id-key="service_id"
        item-title-key="name"
        item-description-key="description"
        :display-formatter="formatServiceDisplay"
        @update:selected-ids="handleSelectedIdsUpdate"
        @update:search-keyword="handleSearchKeywordUpdate"
        @retry="serviceSelection.loadServiceList"
      >
        <template #item-title="{ item }">
          {{ item.name }}
          <span class="item-version">v{{ item.version }}</span>
        </template>
        <template #item-description="{ item }">
          {{ item.description || $t('project.noDescription') }}
        </template>
      </MultiSelectList>
    </div>
  </div>
</template>

<script setup lang="ts">
import MultiSelectList from '../common/MultiSelectList.vue'
import type { UseServiceSelectionReturn } from '../../composables/useServiceSelection'
import type { Service } from '../../api/service'

const props = defineProps<{
  isEditMode: boolean
  serviceSelection: UseServiceSelectionReturn
}>()

function formatServiceDisplay(item: any): string {
  const service = item as Service
  return `${service.name} v${service.version}`
}

async function handleModeChange(event: Event) {
  const target = event.target as HTMLSelectElement
  const mode = target.value as 'all' | 'whitelist'
  props.serviceSelection.serviceMode.value = mode
  await props.serviceSelection.handleServiceModeChange()
}

function handleSelectedIdsUpdate(ids: string[]) {
  props.serviceSelection.selectedServiceIds.value = ids
}

function handleSearchKeywordUpdate(keyword: string) {
  props.serviceSelection.searchServiceKeyword.value = keyword
}
</script>

<style scoped>
.form-section {
  background: white;
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 24px;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
  transition: box-shadow 0.3s ease;
}

.form-section:hover {
  box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05), 0 4px 6px -2px rgba(0, 0, 0, 0.025);
}

.section-title {
  margin: 0 0 20px 0;
  font-size: 18px;
  font-weight: 600;
  line-height: 1.4;
  color: var(--text-primary, #1e293b);
  border-bottom: 1px solid var(--border-color, #f1f5f9);
  padding-bottom: 12px;
}

.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary, #334155);
}

.form-input {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid var(--border-color, #cbd5e1);
  border-radius: 8px;
  font-size: 14px;
  font-family: inherit;
  background-color: #f8fafc;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  color: var(--text-primary, #0f172a);
}

.form-input:hover {
  border-color: #94a3b8;
}

.form-input:focus {
  outline: none;
  background-color: white;
  border-color: var(--accent-primary, #3b82f6);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15);
}

.item-version {
  font-size: 12px;
  color: var(--text-secondary, #64748b);
  background-color: #f1f5f9;
  padding: 2px 6px;
  border-radius: 12px;
  margin-left: 8px;
  font-weight: 500;
}
</style>

