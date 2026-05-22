<template>
  <div class="multi-select-wrapper">
    <!-- 搜索框 -->
    <input
      :value="searchKeyword"
      type="text"
      class="search-input"
      :placeholder="searchPlaceholder"
      @input="handleSearchInput"
    />
    
    <!-- 已选标签 -->
    <div v-if="selectedIds.length > 0" class="selected-tags">
      <span class="tag-count">已选择 {{ selectedIds.length }} 个{{ itemLabel }}</span>
      <div class="tags">
        <span
          v-for="id in selectedIds"
          :key="id"
          class="tag"
        >
          {{ getItemDisplayText(id) }}
          <button
            class="tag-remove"
            @click="handleRemove(id)"
            type="button"
          >×</button>
        </span>
      </div>
    </div>
    
    <!-- 可选列表 -->
    <div v-if="loading" class="loading-inline">
      <span>{{ $t('common.loading') }}</span>
    </div>
    <div v-else-if="error" class="error-inline">
      <span>{{ error }}</span>
      <el-button @click="$emit('retry')">
        {{ $t('common.retry') }}
      </el-button>
    </div>
    <div v-else class="selectable-list">
      <div
        v-for="item in filteredItems"
        :key="getItemId(item)"
        class="list-item"
        :class="{ 'selected': selectedIds.includes(getItemId(item)) }"
        @click="handleToggle(getItemId(item))"
      >
        <input
          type="checkbox"
          :checked="selectedIds.includes(getItemId(item))"
          @change.stop="handleToggle(getItemId(item))"
        />
        <div class="item-content">
          <div class="item-title">
            <slot name="item-title" :item="item">
              {{ getItemTitle(item) }}
            </slot>
          </div>
          <div class="item-description">
            <slot name="item-description" :item="item">
              {{ getItemDescription(item) || '无描述' }}
            </slot>
          </div>
        </div>
      </div>
      <div v-if="filteredItems.length === 0 && !loading" class="empty-state">
        {{ emptyMessage }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

export interface MultiSelectListItem {
  [key: string]: any
}

export interface MultiSelectListProps {
  items: MultiSelectListItem[]
  selectedIds: string[]
  loading?: boolean
  error?: string | null
  searchKeyword: string
  searchPlaceholder?: string
  emptyMessage?: string
  itemLabel?: string
  itemIdKey?: string
  itemTitleKey?: string
  itemDescriptionKey?: string
  displayFormatter?: (item: MultiSelectListItem) => string
}

const props = withDefaults(defineProps<MultiSelectListProps>(), {
  loading: false,
  error: null,
  searchPlaceholder: '搜索...',
  emptyMessage: '暂无数据',
  itemLabel: '项',
  itemIdKey: 'id',
  itemTitleKey: 'title',
  itemDescriptionKey: 'description'
})

const emit = defineEmits<{
  'update:selectedIds': [ids: string[]]
  'update:searchKeyword': [keyword: string]
  retry: []
}>()

/**
 * 获取项目的ID
 */
function getItemId(item: MultiSelectListItem): string {
  return String(item[props.itemIdKey] || '')
}

/**
 * 获取项目的标题
 */
function getItemTitle(item: MultiSelectListItem): string {
  return String(item[props.itemTitleKey] || '')
}

/**
 * 获取项目的描述
 */
function getItemDescription(item: MultiSelectListItem): string {
  return String(item[props.itemDescriptionKey] || '')
}

/**
 * 获取项目的显示文本（用于已选标签）
 */
function getItemDisplayText(id: string): string {
  const item = props.items.find(i => getItemId(i) === id)
  if (!item) return id
  
  if (props.displayFormatter) {
    return props.displayFormatter(item)
  }
  
  return getItemTitle(item)
}

/**
 * 筛选列表（根据搜索关键词）
 */
const filteredItems = computed(() => {
  const keyword = props.searchKeyword.trim().toLowerCase()
  if (!keyword) {
    return props.items
  }
  
  return props.items.filter(item => {
    const title = getItemTitle(item).toLowerCase()
    const description = getItemDescription(item).toLowerCase()
    const id = getItemId(item).toLowerCase()
    
    return title.includes(keyword) || 
           description.includes(keyword) ||
           id.includes(keyword)
  })
})

/**
 * 处理搜索输入
 */
function handleSearchInput(event: Event) {
  const target = event.target as HTMLInputElement
  emit('update:searchKeyword', target.value)
}

/**
 * 切换选择状态
 */
function handleToggle(id: string) {
  const newSelectedIds = [...props.selectedIds]
  const index = newSelectedIds.indexOf(id)
  if (index > -1) {
    newSelectedIds.splice(index, 1)
  } else {
    newSelectedIds.push(id)
  }
  emit('update:selectedIds', newSelectedIds)
}

/**
 * 移除已选项
 */
function handleRemove(id: string) {
  const newSelectedIds = props.selectedIds.filter(selectedId => selectedId !== id)
  emit('update:selectedIds', newSelectedIds)
}
</script>

<style scoped>
.multi-select-wrapper {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.search-input {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid var(--border-color, #cbd5e1);
  border-radius: 8px;
  font-size: 14px;
  background-color: #f8fafc;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  color: var(--text-primary, #0f172a);
}

.search-input:hover {
  border-color: #94a3b8;
}

.search-input:focus {
  outline: none;
  background-color: white;
  border-color: var(--accent-primary, #3b82f6);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15);
}

.selected-tags {
  margin-bottom: 4px;
}

.tag-count {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary, #64748b);
  margin-bottom: 10px;
  display: block;
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  background: rgba(59, 130, 246, 0.1);
  color: var(--accent-primary, #3b82f6);
  border: 1px solid rgba(59, 130, 246, 0.2);
  border-radius: 16px;
  font-size: 13px;
  font-weight: 500;
  transition: all 0.2s ease;
}

.tag:hover {
  background: rgba(59, 130, 246, 0.15);
  border-color: rgba(59, 130, 246, 0.3);
}

.tag-remove {
  background: rgba(59, 130, 246, 0.1);
  border: none;
  color: var(--accent-primary, #3b82f6);
  border-radius: 50%;
  cursor: pointer;
  font-size: 14px;
  line-height: 1;
  padding: 0;
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.tag-remove:hover {
  background: var(--accent-primary, #3b82f6);
  color: white;
}

.loading-inline {
  padding: 24px;
  text-align: center;
  color: var(--text-secondary, #64748b);
}

.error-inline {
  padding: 24px;
  text-align: center;
  color: #ef4444;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.button {
  padding: 10px 20px;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
}

.selectable-list {
  max-height: 320px;
  overflow-y: auto;
  border: 1px solid var(--border-color, #e2e8f0);
  border-radius: 8px;
  background: white;
  box-shadow: inset 0 2px 4px 0 rgba(0, 0, 0, 0.02);
}

.list-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border-color, #f1f5f9);
  cursor: pointer;
  transition: all 0.2s ease;
}

.list-item:last-child {
  border-bottom: none;
}

.list-item:hover {
  background: #f8fafc;
}

.list-item.selected {
  background: #f0fdf4;
  border-left: 3px solid #22c55e;
}

.list-item input[type="checkbox"] {
  margin-top: 4px;
  cursor: pointer;
  width: 16px;
  height: 16px;
  accent-color: var(--accent-primary, #3b82f6);
}

.item-content {
  flex: 1;
  min-width: 0;
}

.item-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary, #1e293b);
  margin-bottom: 6px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.item-version {
  font-size: 12px;
  background: #f1f5f9;
  padding: 2px 6px;
  border-radius: 12px;
  color: var(--text-secondary, #64748b);
  margin-left: auto;
}

.item-description {
  font-size: 13px;
  color: var(--text-secondary, #64748b);
  line-height: 1.5;
}

.empty-state {
  padding: 32px 24px;
  text-align: center;
  color: var(--text-secondary, #94a3b8);
  font-size: 14px;
  font-style: italic;
}
</style>

