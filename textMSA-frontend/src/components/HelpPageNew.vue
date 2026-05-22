<template>
  <div class="help-page-container">
    <div class="help-layout">
      <!-- Sidebar Navigation -->
      <aside class="help-sidebar">
        <div class="sidebar-header">
          <Icon name="help" size="lg" />
          <h2>{{ $t('help.title') }}</h2>
        </div>
        <nav class="sidebar-nav">
          <template v-for="section in sections" :key="section.id">
            <!-- Parent Section -->
            <div v-if="section.isParent" class="parent-section">
              <div class="parent-title">{{ section.title }}</div>
            </div>
            <!-- Child Section -->
            <button
              v-else
              :class="['nav-button', { active: activeSection === section.id, child: section.isChild }]"
              @click="activeSection = section.id"
            >
              <Icon v-if="section.icon" :name="section.icon" size="md" />
              <span>{{ section.title }}</span>
            </button>
          </template>
          <!-- <button
            @click="downloadSampleFile"
            class="nav-button"
          >
            <Icon name="download" size="md" />
            <span>{{ $t('help.downloadSampleData') }}</span>
          </button> -->
        </nav>
      </aside>

      <!-- Main Content -->
      <main class="help-main">
        <transition name="fade" mode="out-in">
          <component :is="currentComponent" :key="activeSection" />
        </transition>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import Icon from './common/Icon.vue'
import IntroductionPage from './help/IntroductionPage.vue'
import GettingStartedPage from './help/GettingStartedPage.vue'
import AnalysisPageHelp from './help/AnalysisPageHelp.vue'
import ServiceManagementHelp from './help/ServiceManagementHelp.vue'

const { t } = useI18n()

const activeSection = ref('introduction')

const sections = computed(() => [
  {
    id: 'introduction',
    title: t('help.introduction.title'),
    icon: 'info',
    component: IntroductionPage
  },
  {
    id: 'getting-started',
    title: t('help.sections.gettingStarted.title'),
    icon: 'rocket',
    component: GettingStartedPage
  },
  {
    id: 'pages-introduction',
    title: 'Pages Introduction',
    isParent: true
  },
  {
    id: 'analysis-page',
    title: t('help.sections.analysisPage.title'),
    icon: 'analysis',
    component: AnalysisPageHelp,
    isChild: true
  },
  {
    id: 'service-management',
    title: t('help.sections.serviceManagement.title'),
    icon: 'services',
    component: ServiceManagementHelp,
    isChild: true
  }
])

const currentComponent = computed(() => {
  const section = sections.value.find(s => s.id === activeSection.value)
  return section?.component || IntroductionPage
})

// 使用 window.open 方式下载
function downloadSampleFile() {
  const fileId = '0'
  const url = `/STAnalyzer/api/file/download/${fileId}`
  window.open(url, '_blank')
}
</script>

<style scoped>
.help-page-container {
  width: 100%;
  height: 100%;
  background: var(--bg-secondary);
  overflow: hidden;
}

.help-layout {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  height: 100%;
  max-width: 1800px;
  margin: 0 auto;
  gap: var(--spacing-lg);
  padding: var(--spacing-lg);
}

/* Sidebar */
.help-sidebar {
  display: flex;
  flex-direction: column;
  background: var(--bg-primary);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-color);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

.sidebar-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  padding: var(--spacing-xl) var(--spacing-lg);
  background: var(--bg-tertiary);
  border-bottom: 1px solid var(--border-color);
}

.sidebar-header h2 {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--text-primary);
}

.sidebar-nav {
  flex: 1;
  padding: var(--spacing-md);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.parent-section {
  margin: var(--spacing-xs) 0;
}

.parent-title {
  padding: var(--spacing-sm) var(--spacing-lg);
  background: var(--bg-tertiary);
  border-radius: var(--radius-md);
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text-primary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.nav-button {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  padding: var(--spacing-md) var(--spacing-lg);
  border: none;
  background: transparent;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all 0.2s ease;
  text-align: left;
  font-size: 0.9375rem;
  font-weight: 500;
  color: var(--text-secondary);
}



.nav-button:hover {
  background: var(--bg-tertiary);
  color: var(--text-primary);
}

.nav-button.active {
  background: var(--bg-tertiary);
  color: var(--accent-primary);
  font-weight: 600;
}

.nav-button span {
  flex: 1;
}

/* Main Content */
.help-main {
  background: var(--bg-primary);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-color);
  box-shadow: var(--shadow-sm);
  overflow-y: auto;
  overflow-x: hidden;
}

/* Fade Transition */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.fade-enter-from {
  opacity: 0;
  transform: translateY(10px);
}

.fade-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

/* Scrollbar Styling */
.help-main::-webkit-scrollbar,
.sidebar-nav::-webkit-scrollbar {
  width: 8px;
}

.help-main::-webkit-scrollbar-track,
.sidebar-nav::-webkit-scrollbar-track {
  background: var(--bg-secondary);
}

.help-main::-webkit-scrollbar-thumb,
.sidebar-nav::-webkit-scrollbar-thumb {
  background: var(--border-color);
  border-radius: 4px;
}

.help-main::-webkit-scrollbar-thumb:hover,
.sidebar-nav::-webkit-scrollbar-thumb:hover {
  background: var(--text-tertiary);
}

/* Responsive */
@media (max-width: 768px) {
  .help-layout {
    grid-template-columns: 1fr;
    grid-template-rows: auto 1fr;
    padding: var(--spacing-md);
  }

  .help-sidebar {
    max-height: 200px;
  }

  .sidebar-nav {
    flex-direction: row;
    overflow-x: auto;
    overflow-y: hidden;
  }

  .nav-button {
    flex-shrink: 0;
    white-space: nowrap;
  }
}
</style>
