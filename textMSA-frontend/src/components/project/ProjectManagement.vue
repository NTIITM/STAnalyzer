<template>
  <div class="project-management-container">
    <div class="project-header">
      <div class="project-header-left">
        <el-button class="back-to-analysis-btn" @click="goToAnalysis">
          <Icon name="arrow-left" size="md" />
          <span>{{ $t('project.backToAnalysis') }}</span>
        </el-button>
        <h2>{{ $t('project.management') }}</h2>
      </div>
      <el-button type="primary" @click="showCreateProject">
        <Icon name="plus" size="md" />
        <span>{{ $t('project.create') }}</span>
      </el-button>
    </div>

    <!-- 项目列表 -->
    <div v-if="loading" class="loading-state">
      <el-skeleton :rows="4" animated />
    </div>
    <div v-else-if="error" class="error-state">
      <el-alert :title="error" type="error" show-icon :closable="false" />
      <el-button class="retry-btn" @click="loadProjects">{{ $t('common.retry') }}</el-button>
    </div>
    <div v-else-if="projects.length === 0" class="empty-state">
      <el-empty :description="$t('project.noProjects')" />
      <el-button type="primary" @click="showCreateProject">
        {{ $t('project.createFirst') }}
      </el-button>
    </div>
    <div v-else class="project-list">
      <div 
        v-for="project in projects" 
        :key="project.project_id"
        class="project-card"
        @click="openProject(project.project_id)"
      >
        <div class="project-card-header">
          <div class="project-title">
            <span class="project-icon">📁</span>
            <span class="project-name">{{ project.name }}</span>
          </div>
          <div class="project-actions" @click.stop>
            <button 
              class="action-btn" 
              @click="showConfigProject(project)"
              :title="$t('project.config')"
            >
              <Icon name="settings" size="sm" />
            </button>
            <button 
              class="action-btn action-btn-danger" 
              @click="confirmDeleteProject(project)"
              :title="$t('common.delete')"
            >
              <Icon name="delete" size="sm" />
            </button>
          </div>
        </div>
        <div class="project-card-body">
          <div v-if="project.description" class="project-info-item">
            <span class="info-label">{{ $t('project.description') }}:</span>
            <span class="info-value">{{ project.description }}</span>
          </div>
          <div class="project-info-item">
            <span class="info-label">{{ $t('project.fileCount') }}:</span>
            <span class="info-value">{{ project.file_ids?.length || 0 }}</span>
          </div>
          <div class="project-info-item">
            <span class="info-label">{{ $t('project.createdAt') }}:</span>
            <span class="info-value">{{ formatDate(project.created_at) }}</span>
          </div>
          <div class="project-info-item">
            <span class="info-label">{{ $t('project.updatedAt') }}:</span>
            <span class="info-value">{{ formatDate(project.updated_at) }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElAlert, ElButton, ElEmpty, ElSkeleton } from 'element-plus'
import { getProjectList, deleteProject, type Project } from '../../api/project'
import Icon from '../common/Icon.vue'

const router = useRouter()
const { t } = useI18n()

const projects = ref<Project[]>([])
const loading = ref(false)
const error = ref('')

/**
 * 加载项目列表
 */
async function loadProjects() {
  try {
    loading.value = true
    error.value = ''
    // request 拦截器已经提取了 data 字段，所以 getProjectList() 返回的是 Project[] 数组
    const result = await getProjectList()
    projects.value = Array.isArray(result) ? result : []
  } catch (err: any) {
    console.error('加载项目列表失败:', err)
    error.value = err.message || '加载失败'
  } finally {
    loading.value = false
  }
}

/**
 * 返回分析页面
 */
function goToAnalysis() {
  router.push('/analysis')
}

/**
 * 打开项目（进入分析页面）
 */
function openProject(projectId: string) {
  router.push(`/analysis?projectId=${projectId}`)
}

/**
 * 显示创建项目对话框
 */
function showCreateProject() {
  router.push('/projects/create')
}

/**
 * 显示项目配置页面（包含编辑功能）
 */
function showConfigProject(project: Project) {
  router.push(`/projects/${project.project_id}/config`)
}

/**
 * 确认删除项目
 */
async function confirmDeleteProject(project: Project) {
  if (!confirm(t('project.actions.confirmDelete', { name: project.name }))) {
    return
  }

  try {
    await deleteProject(project.project_id)
    await loadProjects()
  } catch (err: any) {
    alert(`${t('project.actions.deleteFailed')}: ${err.message || '未知错误'}`)
  }
}

/**
 * 格式化日期
 */
function formatDate(dateStr: string | undefined): string {
  if (!dateStr) return '-'
  try {
    const date = new Date(dateStr)
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    })
  } catch {
    return dateStr
  }
}

onMounted(() => {
  loadProjects()
})
</script>

<style scoped>
.project-management-container {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100%;
  padding: var(--spacing-xl);
  background: var(--bg-secondary);
  overflow: hidden;
}

.project-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-xl);
  background: var(--bg-primary);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-color);
  box-shadow: var(--shadow-sm);
  margin-bottom: var(--spacing-lg);
}

.project-header-left {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
}

.back-to-analysis-btn {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.project-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 500;
  line-height: 1.4;
  color: rgba(0, 0, 0, 0.85);
  letter-spacing: 0;
}

.project-list {
  flex: 1;
  overflow-y: auto;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(420px, 1fr));
  gap: var(--spacing-xl);
  padding-bottom: var(--spacing-xl);
  min-height: 0;
}

.project-card {
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: var(--spacing-xl);
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.project-card:hover {
  border-color: var(--accent-primary);
  box-shadow: var(--shadow-lg);
  transform: translateY(-4px);
}

.project-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.75rem;
}

.project-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex: 1;
}

.project-icon {
  font-size: 1.2rem;
}

.project-name {
  font-size: 14px;
  font-weight: 400;
  line-height: 1.5715;
  color: rgba(0, 0, 0, 0.85);
  flex: 1;
  letter-spacing: 0;
}

.project-actions {
  display: flex;
  gap: 0.5rem;
}

.action-btn {
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  border-radius: 4px;
  cursor: pointer;
  font-size: 1rem;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.action-btn:hover {
  background: var(--bg-tertiary);
}

.action-btn-danger:hover {
  background: rgba(220, 100, 100, 0.2);
}

.project-card-body {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.project-info-item {
  display: flex;
  gap: 0.5rem;
  font-size: 0.85rem;
}

.info-label {
  color: var(--text-secondary);
  font-weight: 500;
  min-width: 80px;
}

.info-value {
  color: var(--text-primary);
  flex: 1;
  word-break: break-all;
}

.loading-state,
.error-state,
.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  padding: 3rem;
  color: var(--text-secondary);
}
</style>
