<template>
  <div class="left-panel">
    <!-- 上方：添加数据按钮 -->
    <div class="left-panel-top">
      <button class="add-data-btn" style="margin-top: 8px;" @click="$emit('add-data')">
        <Icon name="plus" size="md" />
        <span>{{ $t('app.addData') }}</span>
      </button>
    </div>
    
    <!-- 下方：服务列表 -->
    <div class="left-panel-bottom">
      <div class="data-list-header">
        <button class="back-to-projects-btn" @click="$emit('back-to-projects')">
          <Icon name="arrow-left" size="sm" />
          <span>{{ $t('project.backToProjects') }}</span>
        </button>
        <div style="margin-top: 8px;">{{ $t('project.servicesHeader') }}</div>
      </div>
      <div class="data-list">
        <div 
          v-for="svc in (projectServices || [])" 
          :key="svc.service_id"
          class="data-item"
          :class="{ active: currentServiceId === svc.service_id }"
          @click="$emit('select-service', svc.service_id)"
        >
          <div class="data-item-content">
            <div class="data-item-name">{{ svc.name }} <span style="opacity:.6;">v{{ svc.version }}</span></div>
            <div class="data-item-meta">
              {{ svc.description || '—' }}
            </div>
          </div>
          <div class="data-item-actions">
            <div class="action-menu-wrapper">
              <button 
                class="action-btn" 
                :title="$t('project.actions.menu')"
                @click.stop="$emit('toggle-action-menu', $event, svc.service_id)"
              >
                ⋯
              </button>
            </div>
          </div>
        </div>
        <div v-if="!projectServices || projectServices.length === 0" class="empty-state">
          {{ $t('app.serviceMenuEmpty') }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import Icon from '../common/Icon.vue'
import type { ProjectService } from '../../stores/servicesCache'

defineProps<{
  projectServices: ProjectService[] | null
  currentServiceId: string | null
}>()

defineEmits<{
  'add-data': []
  'back-to-projects': []
  'select-service': [serviceId: string]
  'toggle-action-menu': [event: MouseEvent, serviceId: string]
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
  font-size: 12px;
  font-weight: 500;
  color: rgba(0, 0, 0, 0.65);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}

.back-to-projects-btn {
  width: 100%;
  padding: var(--spacing-sm) var(--spacing-md);
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
  padding: var(--spacing-sm);
  min-height: 0;
}

.data-item {
  padding: var(--spacing-md);
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

.data-item-content {
  flex: 1;
  min-width: 0;
}

.data-item-name {
  font-size: 14px;
  font-weight: 400;
  line-height: 1.5715;
  color: rgba(0, 0, 0, 0.85);
  margin-bottom: 4px;
}

.data-item-meta {
  font-size: 12px;
  font-weight: 400;
  line-height: 1.5715;
  color: rgba(0, 0, 0, 0.45);
}

.data-item:hover {
  background: rgba(255, 255, 255, 0.7);
  border-color: var(--border-hover);
}

.data-item.active {
  background: var(--accent-primary);
  color: white;
  border-color: var(--accent-hover);
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
