<template>
  <div class="left-panel">
    <!-- 上方：创建项目按钮 -->
    <div class="left-panel-top">
      <button class="create-project-btn" @click="createProject">
        <Icon name="plus" size="md" />
        <span>{{ $t('project.create') }}</span>
      </button>
    </div>
    
    <!-- 下方：项目列表 -->
    <div class="left-panel-bottom">
      <div class="data-list-header">{{ $t('project.projectList') }}</div>
      <div class="data-list">
        <div 
          v-for="project in (projectList || [])" 
          :key="project.project_id"
          class="data-item"
          :class="{ active: currentProjectId === project.project_id }"
          @click="$emit('select-project', project.project_id)"
        >
          <div class="data-item-content">
            <div class="data-item-name">{{ project.name }}</div>
            <div v-if="project.description" class="data-item-description">
              {{ project.description }}
            </div>
            <div class="data-item-meta">{{ formatDate(project.created_at) }}</div>
          </div>
          <div class="data-item-actions">
            <div class="action-menu-wrapper">
              <button 
                class="action-btn" 
                :title="t('project.actions.menu')"
                @click.stop="toggleActionMenu($event, project.project_id)"
              >
                ⋯
              </button>
            </div>
          </div>
        </div>
        <div v-if="!projectList || projectList.length === 0" class="empty-state">
          {{ $t('project.noProjects') }}
        </div>
      </div>
    </div>

    <!-- 操作菜单（使用固定定位） -->
    <div 
      v-if="activeMenuId && actionMenuPosition" 
      class="action-menu" 
      :style="actionMenuStyle"
      @click.stop
    >
      <div 
        class="action-menu-item" 
        @click="editProject(activeMenuId)"
      >
        {{ $t('project.edit') }}
      </div>
      <div 
        class="action-menu-item action-menu-item-danger" 
        @click="handleDeleteClick(activeMenuId)"
      >
        {{ $t('common.delete') }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import Icon from '../common/Icon.vue'
import type { Project } from '../../api/project'

const props = defineProps<{
  projectList: Project[] | null
  currentProjectId: string | null
}>()

const emit = defineEmits<{
  'select-project': [projectId: string]
  'delete-project': [project: Project]
}>()

const router = useRouter()
const { t } = useI18n()

// ==================== 操作菜单管理 ====================
const activeMenuId = ref<string | null>(null)
const actionMenuPosition = ref<{ top: number; left: number } | null>(null)

const actionMenuStyle = computed(() => {
  if (!actionMenuPosition.value) {
    return {}
  }
  return {
    top: `${actionMenuPosition.value.top}px`,
    left: `${actionMenuPosition.value.left}px`
  }
})

function toggleActionMenu(event: MouseEvent, projectId: string) {
  if (activeMenuId.value === projectId) {
    activeMenuId.value = null
    actionMenuPosition.value = null
  } else {
    activeMenuId.value = projectId
    const button = event.currentTarget as HTMLElement
    const rect = button.getBoundingClientRect()
    actionMenuPosition.value = {
      top: rect.bottom + 4,
      left: rect.right - 180
    }
  }
}

function handleClickOutside(event: MouseEvent) {
  if (activeMenuId.value) {
    const target = event.target as HTMLElement
    if (!target.closest('.action-menu-wrapper') && !target.closest('.action-menu')) {
      activeMenuId.value = null
      actionMenuPosition.value = null
    }
  }
}

// ==================== 项目操作 ====================

/**
 * 创建项目
 */
function createProject() {
  router.push('/projects/create')
}

/**
 * 编辑项目
 */
function editProject(projectId: string) {
  activeMenuId.value = null
  actionMenuPosition.value = null
  router.push(`/projects/${projectId}/config`)
}

/**
 * 处理删除点击
 */
function handleDeleteClick(projectId: string) {
  activeMenuId.value = null
  actionMenuPosition.value = null
  
  const project = props.projectList?.find(p => p.project_id === projectId)
  if (!project) return
  
  emit('delete-project', project)
}

/**
 * 格式化日期
 */
function formatDate(dateString: string): string {
  if (!dateString) return ''
  const date = new Date(dateString)
  return date.toLocaleDateString('zh-CN', { 
    year: 'numeric', 
    month: '2-digit', 
    day: '2-digit' 
  })
}

// ==================== 生命周期 ====================
onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})
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

.create-project-btn {
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

.create-project-btn:hover {
  background: var(--accent-hover);
  transform: translateY(-1px);
  box-shadow: var(--shadow-md);
}

.create-project-btn:focus {
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

.data-item-description {
  font-size: 12px;
  font-weight: 400;
  line-height: 1.5715;
  color: rgba(0, 0, 0, 0.65);
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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
.data-item.active .data-item-description,
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
  font-size: 18px;
  color: rgba(0, 0, 0, 0.45);
}

.action-btn:hover {
  background: rgba(255, 255, 255, 0.2);
  color: rgba(0, 0, 0, 0.85);
}

.data-item.active .action-btn {
  color: rgba(255, 255, 255, 0.8);
}

.data-item.active .action-btn:hover {
  background: rgba(255, 255, 255, 0.2);
  color: white;
}

.action-menu {
  position: fixed;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  z-index: 10001;
  min-width: 180px;
  padding: var(--spacing-xs) 0;
  animation: fadeIn 0.15s ease;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(-4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.action-menu-item {
  padding: var(--spacing-sm) var(--spacing-lg);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  font-size: 14px;
  font-weight: 400;
  line-height: 1.5715;
  color: rgba(0, 0, 0, 0.85);
  transition: all 0.2s ease;
}

.action-menu-item:hover {
  background: var(--bg-tertiary);
}

.action-menu-item-danger {
  color: #ff4d4f;
}

.action-menu-item-danger:hover {
  background: rgba(255, 77, 79, 0.1);
  color: #ff4d4f;
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
