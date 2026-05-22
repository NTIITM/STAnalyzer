<template>
  <div class="left-panel">
    <!-- 上方：添加数据按钮 -->
    <div class="left-panel-top">
      <button class="add-data-btn" style="margin-top: 8px;" @click="$emit('add-data')">
        <Icon name="plus" size="md" />
        <span>{{ $t('app.addData') }}</span>
      </button>
    </div>
    
    <!-- 下方：文件列表 -->
    <div class="left-panel-bottom">
      <div class="data-list-header">
        <button class="back-to-projects-btn" @click="$emit('back-to-projects')">
          <Icon name="arrow-left" size="sm" />
          <span>{{ $t('project.backToProjects') }}</span>
        </button>
        <div class="header-title">{{ $t('project.filesHeader') || '项目文件' }}</div>
      </div>
      <div class="data-list">
        <div 
          v-for="file in (files || [])" 
          :key="file.id"
          class="data-item"
          :class="{ active: currentFileId === file.id }"
          @click="$emit('select-file', file.id)"
        >
          <div class="data-item-content">
            <div class="data-item-name">{{ file.name }}</div>
            <div class="data-item-meta">
              {{ file.uploadTime }}
            </div>
          </div>
          <div class="data-item-actions">
            <!-- 预留操作菜单位置 -->
            <div class="action-menu-wrapper">
              <button 
                class="action-btn" 
                :title="$t('project.actions.menu')"
                @click.stop="$emit('toggle-action-menu', $event, file.id)"
              >
                ⋯
              </button>
            </div>
          </div>
        </div>
        <div v-if="!files || files.length === 0" class="empty-state">
          {{ $t('app.noData') || '暂无文件' }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import Icon from '../common/Icon.vue'

interface DataItem {
  id: string
  name: string
  uploadTime: string
  fileId?: string | null
  description?: string
}

defineProps<{
  files: DataItem[] | null
  currentFileId: string | null
}>()

defineEmits<{
  'add-data': []
  'back-to-projects': []
  'select-file': [fileId: string]
  'toggle-action-menu': [event: MouseEvent, fileId: string]
}>()
</script>

<style scoped>
.left-panel {
  display: flex;
  flex-direction: column;
  background: var(--bg-primary);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-color);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
  height: 100%;
}

.left-panel-top {
  padding: var(--spacing-lg);
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}

.add-data-btn {
  width: 100%;
  padding: var(--spacing-md);
  height: 40px;
  background: var(--accent-primary);
  border: 1px solid var(--accent-primary);
  border-radius: var(--radius-md);
  font-size: 14px;
  font-weight: 400;
  line-height: 1.5715;
  color: white;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.645, 0.045, 0.355, 1);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-sm);
  box-shadow: 0 2px 0 rgba(0, 0, 0, 0.015);
}

.add-data-btn:hover {
  background: var(--accent-hover);
  transform: translateY(-1px);
  box-shadow: var(--shadow-md);
}

.add-data-btn:focus {
  outline: none;
  box-shadow: 0 0 0 2px rgba(24, 144, 255, 0.2);
}

.left-panel-bottom {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}

.data-list-header {
  padding: var(--spacing-md) var(--spacing-lg);
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.back-to-projects-btn {
  width: 100%;
  padding: 10px var(--spacing-md);
  background: transparent;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-xs);
  margin-bottom: var(--spacing-sm);
}

.back-to-projects-btn:hover {
  background: var(--bg-secondary);
  color: var(--text-primary);
  border-color: var(--accent-primary);
}

.data-list {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-md);
  min-height: 0;
}

.data-item {
  padding: 12px 14px;
  margin-bottom: var(--spacing-sm);
  background: var(--bg-tertiary);
  border-radius: var(--radius-md);
  border: 1px solid transparent;
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-sm);
  position: relative;
}

.header-title {
  font-size: 15px;
  font-weight: 650;
  color: var(--text-primary);
}

.data-item-content {
  flex: 1;
  min-width: 0;
}

.data-item-name {
  font-size: 15px;
  font-weight: 600;
  line-height: 1.5;
  color: var(--text-primary);
  margin-bottom: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.data-item-meta {
  font-size: 12px;
  font-weight: 400;
  line-height: 1.4;
  color: rgba(0, 0, 0, 0.55);
}

.data-item:hover {
  background: rgba(255, 255, 255, 0.7);
  border-color: var(--border-hover);
}

.data-item.active {
  background: linear-gradient(135deg, var(--accent-primary), var(--accent-hover));
  color: white;
  border-color: transparent;
}

.data-item.active .data-item-name,
.data-item.active .data-item-meta {
  color: white;
}

.data-item-actions {
  display: flex;
  gap: var(--spacing-xs);
  opacity: 1;
  transition: opacity 0.2s ease;
  position: relative;
}

.action-menu-wrapper {
  position: relative;
}

.action-btn {
  background: transparent;
  border: none;
  cursor: pointer;
  padding: var(--spacing-xs) var(--spacing-sm);
  border-radius: var(--radius-sm);
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  color: inherit; /* 继承父元素颜色，在 active 状态下为白色 */
}

.action-btn:hover {
  background: rgba(255, 255, 255, 0.2);
}

.empty-state {
  padding: var(--spacing-2xl);
  text-align: center;
  color: rgba(0, 0, 0, 0.45);
  font-size: 14px;
  font-weight: 400;
  line-height: 1.5715;
}
</style>
