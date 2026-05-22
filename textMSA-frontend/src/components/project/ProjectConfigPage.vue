<template>
  <div class="project-config-page">
    <!-- 页面头部 -->
    <ProjectConfigHeader
      :is-edit-mode="isEditMode"
      :saving="!!projectConfig.saving.value"
      :is-form-valid="!!projectConfig.isFormValid.value"
      @back="handleBack"
      @save="handleSave"
    />

    <!-- 主内容区域 -->
    <div v-if="projectConfig.loading.value" class="loading-state">
      <div class="spinner"></div>
      <span>{{ $t('common.loading') }}</span>
    </div>
    <div v-else-if="projectConfig.error.value" class="error-state">
      <span>{{ projectConfig.error.value }}</span>
      <button class="button button-secondary" @click="projectConfig.loadProjectData">
        {{ $t('common.retry') }}
      </button>
    </div>
    <div v-else class="form-container">
      <!-- 基本信息 -->
      <BasicInfoSection
        v-if="projectConfig.formData.value"
        :form-data="{
          name: projectConfig.formData.value.name || '',
          description: projectConfig.formData.value.description || ''
        }"
        @update:form-data="handleFormDataUpdate"
      />

      <!-- 服务配置（仅编辑模式显示） -->
      <ServiceConfigSection
        v-if="isEditMode"
        :is-edit-mode="isEditMode"
        :service-selection="serviceSelection"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import type { Project } from '../../api/project'
import ProjectConfigHeader from './ProjectConfigHeader.vue'
import BasicInfoSection from './BasicInfoSection.vue'
import ServiceConfigSection from './ServiceConfigSection.vue'
import { useProjectConfig } from '../../composables/useProjectConfig'
import { useServiceSelection } from '../../composables/useServiceSelection'
import type { BasicInfoFormData } from './BasicInfoSection.vue'

const router = useRouter()
const route = useRoute()

// 创建模式：路由为 /projects/create，params.id 为 undefined
// 编辑模式：路由为 /projects/:id/config，params.id 为项目ID
const projectId = computed(() => route.params.id as string | undefined)
const isEditMode = computed(() => !!projectId.value)

// 使用服务选择 composable
const serviceSelection = useServiceSelection({
  onModeChange: () => {
    // 模式变化时的处理
  }
})

// 使用项目配置 composable
const projectConfig = useProjectConfig({
  projectId: projectId.value || null,
  isEditMode: isEditMode.value,
  onLoadComplete: (project: Project) => {
    // 同步服务配置
    if (project.service_config) {
      const mode = project.service_config.mode
      serviceSelection.serviceMode.value = (mode === 'all' || mode === 'whitelist') ? mode : 'all'
      serviceSelection.selectedServiceIds.value = [...(project.service_config.whitelist || [])]
    } else {
      // 如果没有配置，使用项目数据中的 service_ids
      serviceSelection.selectedServiceIds.value = [...((project as any).service_ids || [])]
    }

    if (serviceSelection.serviceMode.value === 'whitelist') {
      serviceSelection.loadServiceList()
    }
}
})

/**
 * 处理表单数据更新
 */
function handleFormDataUpdate(data: BasicInfoFormData) {
  if (projectConfig.formData.value) {
    projectConfig.formData.value = {
      ...projectConfig.formData.value,
      name: data.name,
      description: data.description
    }
  }
}

/**
 * 保存项目配置
 */
async function handleSave() {
  await projectConfig.saveProject({
    serviceMode: serviceSelection.serviceMode.value || 'all',
    selectedServiceIds: serviceSelection.selectedServiceIds.value || []
  })
}

/**
 * 返回
 */
function handleBack() {
  router.push('/analysis')
}

onMounted(() => {
  if (isEditMode.value) {
    projectConfig.loadProjectData()
  } else {
    // 创建模式：如果默认是白名单模式，也需要加载服务列表
    if (serviceSelection.serviceMode.value === 'whitelist') {
      serviceSelection.loadServiceList()
    }
  }
})
</script>

<style scoped>
.project-config-page {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100%;
  background: var(--bg-secondary, #f8fafc);
  overflow: hidden;
  font-family: 'Inter', system-ui, Avenir, Helvetica, Arial, sans-serif;
}

.form-container {
  flex: 1;
  overflow-y: auto;
  padding: 2rem;
  max-width: 1200px;
  margin: 0 auto;
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.loading-state,
.error-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1.5rem;
  padding: 3rem;
  color: var(--text-secondary);
  font-size: 1.1rem;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 4px solid rgba(0,0,0,0.05);
  border-top-color: var(--accent-primary, #3b82f6);
  border-radius: 50%;
  animation: spin 0.8s cubic-bezier(0.5, 0, 0.5, 1) infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.button {
  padding: 10px 20px;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}

.button-secondary {
  background: white;
  color: var(--text-primary);
  border: 1px solid var(--border-color, #e2e8f0);
}

.button-secondary:hover {
  background: #f8fafc;
  transform: translateY(-1px);
  box-shadow: 0 4px 6px rgba(0,0,0,0.05);
}

.button:active {
  transform: translateY(0);
}
</style>
