<template>
  <div class="service-management-help">
    <div class="page-container">
      <!-- Main Content -->
      <div ref="mainContentRef" class="main-content">
        <div class="page-header">
          <h1>{{ $t('help.sections.serviceManagement.title') }}</h1>
          <p class="subtitle">{{ $t('help.sections.serviceManagement.description') }}</p>
        </div>

        <!-- Service Information -->
        <div id="section-0" class="info-card">
          <div class="card-header">
            <Icon name="services" size="md" />
            <h2>{{ $t('help.sections.serviceManagement.serviceInfo.title') }}</h2>
          </div>
          <div class="card-content">
            <p class="section-intro">{{ $t('help.sections.serviceManagement.serviceInfo.description') }}</p>
            
            <div class="feature-grid">
              <div class="feature-box">
                <div class="feature-box-header">
                  <Icon name="check" size="sm" />
                  <h3>{{ $t('help.sections.serviceManagement.serviceInfo.functions.title') }}</h3>
                </div>
                <ul class="feature-list">
                  <li v-for="(item, idx) in serviceFunctions" :key="idx">{{ item }}</li>
                </ul>
              </div>
              
              <div class="feature-box">
                <div class="feature-box-header">
                  <Icon name="light-bulb" size="sm" />
                  <h3>{{ $t('help.sections.serviceManagement.serviceInfo.useCases.title') }}</h3>
                </div>
                <ul class="feature-list">
                  <li v-for="(item, idx) in serviceUseCases" :key="idx">{{ item }}</li>
                </ul>
              </div>
            </div>

            <div class="screenshot-section">
              <h4>{{ $t('help.sections.serviceManagement.serviceInfo.images.list') }}</h4>
              <img :src="getImagePath('service_info_list.png')" :alt="$t('help.sections.serviceManagement.serviceInfo.images.list')" />
            </div>

            <div class="screenshot-section">
              <h4>{{ $t('help.sections.serviceManagement.serviceInfo.images.detail') }}</h4>
              <img :src="getImagePath('service_info_detail.png')" :alt="$t('help.sections.serviceManagement.serviceInfo.images.detail')" />
            </div>
          </div>
        </div>

        <!-- Relationship Graph -->
        <div id="section-1" class="info-card">
          <div class="card-header">
            <Icon name="diagram" size="md" />
            <h2>{{ $t('help.sections.serviceManagement.relationshipGraph.title') }}</h2>
          </div>
          <div class="card-content">
            <p class="section-intro">{{ $t('help.sections.serviceManagement.relationshipGraph.description') }}</p>
            
            <div class="graph-features">
              <div class="graph-feature-item">
                <div class="feature-badge">
                  <Icon name="refresh-cw" size="md" />
                </div>
                <div class="feature-details">
                  <h4>{{ $t('help.sections.serviceManagement.relationshipGraph.functions.components.title') }}</h4>
                  <ul>
                    <li v-for="(item, idx) in graphComponents" :key="idx">{{ item }}</li>
                  </ul>
                </div>
              </div>

              <div class="graph-feature-item">
                <div class="feature-badge">
                  <Icon name="cursor" size="md" />
                </div>
                <div class="feature-details">
                  <h4>{{ $t('help.sections.serviceManagement.relationshipGraph.interactions.title') }}</h4>
                  <ul>
                    <li v-for="(item, idx) in graphInteractions" :key="idx">{{ item }}</li>
                  </ul>
                </div>
              </div>

              <div class="graph-feature-item">
                <div class="feature-badge">
                  <Icon name="star" size="md" />
                </div>
                <div class="feature-details">
                  <h4>{{ $t('help.sections.serviceManagement.relationshipGraph.useCases.title') }}</h4>
                  <ul>
                    <li v-for="(item, idx) in graphUseCases" :key="idx">{{ item }}</li>
                  </ul>
                </div>
              </div>
            </div>

            <div class="screenshot-section">
              <h4>{{ $t('help.sections.serviceManagement.relationshipGraph.images.overview') }}</h4>
              <img :src="getImagePath('relationship_graph_overview.png')" :alt="$t('help.sections.serviceManagement.relationshipGraph.images.overview')" />
            </div>

            <div class="screenshot-section">
              <h4>{{ $t('help.sections.serviceManagement.relationshipGraph.images.interaction') }}</h4>
              <img :src="getImagePath('relationship_graph_interaction.png')" :alt="$t('help.sections.serviceManagement.relationshipGraph.images.interaction')" />
            </div>
          </div>
        </div>
        
        <!-- Service Upload Guide -->
        <div id="section-2" class="info-card">
          <div class="card-header upload-header">
            <Icon name="upload" size="md" />
            <h2>{{ $t('help.sections.serviceManagement.serviceUpload.title') }}</h2>
          </div>
          <div class="card-content">
            <p class="section-intro">{{ $t('help.sections.serviceManagement.serviceUpload.description') }}</p>

            <div class="download-banner">
               <div class="download-banner-icon">
                  <Icon name="download" size="lg" />
               </div>
               <div class="download-banner-content">
                 <h4>{{ $t('help.sections.serviceManagement.serviceUpload.downloadBanner.title') }}</h4>
                 <p>{{ $t('help.sections.serviceManagement.serviceUpload.downloadBanner.description') }}</p>
                 <div class="action-buttons">
                   <a href="/STAnalyzer/paste_service_example.zip" download class="button button-primary">
                      <Icon name="document-zip" size="sm" />
                      {{ $t('help.sections.serviceManagement.serviceUpload.downloadBanner.button') }}
                   </a>
                   <button @click="goToCreateService" class="button button-secondary go-create-btn">
                      <Icon name="plus" size="sm" />
                      {{ $t('help.sections.serviceManagement.serviceUpload.downloadBanner.goCreateButton') }}
                   </button>
                 </div>
               </div>
            </div>

            <div class="upload-steps">
              <div v-for="(step, idx) in uploadSteps" :key="idx" class="upload-step-item">
                <div class="upload-step-number">{{ idx + 1 }}</div>
                <div class="upload-step-content">
                  <h4>{{ step.title }}</h4>
                  <p>{{ step.desc }}</p>
                  <el-image class="upload-step-image"
                    :src="getImagePath(step.image)"
                    :alt="step.title"
                    fit="contain"
                    :preview-src-list="[getImagePath(step.image)]"
                    :preview-teleported="true"
                    :scale="0.6"
                  />
                  <!-- <img :src="getImagePath(step.image)" :alt="step.title" /> -->
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Sidebar Navigation -->
      <SidebarNavigation 
        :steps="navigationSteps" 
        :title="$t('help.common.navigation')"
        sectionPrefix="section-"
        @update:currentStep="(index) => currentStep = index"
      />
      
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import Icon from '../common/Icon.vue'
import SidebarNavigation from '../common/SidebarNavigation.vue'

const { t } = useI18n()
const router = useRouter()

// Current active step
const currentStep = ref<number>(0)

// Navigation steps for sidebar
const navigationSteps = computed(() => [
  {
    title: t('help.sections.serviceManagement.serviceInfo.title')
  },
  {
    title: t('help.sections.serviceManagement.relationshipGraph.title')
  },
  {
    title: t('help.sections.serviceManagement.serviceUpload.title')
  }
])

const goToCreateService = () => {
  router.push('/services/create')
}

const serviceFunctions = computed(() => [
  t('help.sections.serviceManagement.serviceInfo.functions.function1'),
  t('help.sections.serviceManagement.serviceInfo.functions.function2'),
  t('help.sections.serviceManagement.serviceInfo.functions.function3')
])

const serviceUseCases = computed(() => [
  t('help.sections.serviceManagement.serviceInfo.useCases.case1'),
  t('help.sections.serviceManagement.serviceInfo.useCases.case2'),
  t('help.sections.serviceManagement.serviceInfo.useCases.case3')
])

const graphComponents = computed(() => [
  t('help.sections.serviceManagement.relationshipGraph.functions.components.component1'),
  t('help.sections.serviceManagement.relationshipGraph.functions.components.component2'),
  t('help.sections.serviceManagement.relationshipGraph.functions.components.component3')
])

const graphInteractions = computed(() => [
  t('help.sections.serviceManagement.relationshipGraph.interactions.interaction1'),
  t('help.sections.serviceManagement.relationshipGraph.interactions.interaction2'),
  t('help.sections.serviceManagement.relationshipGraph.interactions.interaction3')
])

const graphUseCases = computed(() => [
  t('help.sections.serviceManagement.relationshipGraph.useCases.case1'),
  t('help.sections.serviceManagement.relationshipGraph.useCases.case2'),
  t('help.sections.serviceManagement.relationshipGraph.useCases.case3')
])

const uploadSteps = computed(() => [
  { title: t('help.sections.serviceManagement.serviceUpload.steps.step1.title'), 
    desc: t('help.sections.serviceManagement.serviceUpload.steps.step1.desc') ,
    image: 'upload_step1.png'
},
  { title: t('help.sections.serviceManagement.serviceUpload.steps.step2.title'), 
    desc: t('help.sections.serviceManagement.serviceUpload.steps.step2.desc') ,
    image: 'upload_step2.png'
},
  { title: t('help.sections.serviceManagement.serviceUpload.steps.step3.title'), 
    desc: t('help.sections.serviceManagement.serviceUpload.steps.step3.desc') ,
    image: 'upload_step3.png'
},
  { title: t('help.sections.serviceManagement.serviceUpload.steps.step4.title'), 
    desc: t('help.sections.serviceManagement.serviceUpload.steps.step4.desc') ,
    image: 'upload_step4.png'
},
  { title: t('help.sections.serviceManagement.serviceUpload.steps.step5.title'), 
    desc: t('help.sections.serviceManagement.serviceUpload.steps.step5.desc') ,
    image: 'upload_step5.png'
},
  { title: t('help.sections.serviceManagement.serviceUpload.steps.step6.title'), 
    desc: t('help.sections.serviceManagement.serviceUpload.steps.step6.desc') ,
    image: 'upload_step6.png'
},
  { title: t('help.sections.serviceManagement.serviceUpload.steps.step7.title'), 
    desc: t('help.sections.serviceManagement.serviceUpload.steps.step7.desc') ,
    image: 'upload_step7.png'
}
])

function getImagePath(imageName: string): string {
  const base = import.meta.env.BASE_URL.replace(/\/$/, '')
  return `${base}/pictures/${imageName}`
}
</script>

<style scoped>
/* ==========================================
   🎨 Global Theme & Variables (Editorial Tech)
   ========================================== */
@import url('https://fonts.googleapis.com/css2?family=Clash+Display:wght@400;600;700&family=Satoshi:wght@300;400;500;700&display=swap');

:root {
  --color-text-dark: #0F172A;
  --color-text-muted: #64748B;
  --color-bg-page: #F8FAFC;
  --color-card: #FFFFFF;
  --color-accent: #1E40AF; /* Primary Blue */
  --color-accent-light: #3B82F6;
  --color-accent-lighter: #93C5FD;
  --color-border: #E2E8F0;
  --radius-xl: 20px;
  --radius-md: 12px;
  --radius-sm: 8px;
  --shadow-soft: 0 10px 25px -10px rgba(59, 130, 246, 0.1);
  --shadow-hover: 0 20px 40px -10px rgba(59, 130, 246, 0.15);
}

.service-management-help {
  background: var(--color-bg-page);
  min-height: 100vh;
  font-family: 'Satoshi', -apple-system, BlinkMacSystemFont, sans-serif;
  color: var(--color-text-muted);
  line-height: 1.7;
}

.page-header {
  margin-bottom: var(--spacing-xl);
  text-align: center;
  position: relative;
}

.page-header::after {
  content: '';
  position: absolute;
  bottom: -30px;
  left: 50%;
  transform: translateX(-50%);
  width: 60px;
  height: 4px;
  background: linear-gradient(to right, transparent, var(--color-accent), transparent);
  border-radius: 2px;
}

.page-header h1 {
  font-size: 2rem;
  font-weight: 700;
  color: var(--color-text-dark);
  margin-bottom: var(--spacing-md);
  font-family: 'Clash Display', sans-serif;
  letter-spacing: -1.5px;
  line-height: 1.5;
  background: linear-gradient(135deg, #0F172A 0%, #1E40AF 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.subtitle {
  font-size: 1rem;
  color: var(--color-text-muted);
  line-height: 1.6;
  max-width: 800px;
  margin: 0 auto;
}

.info-card {
  background: var(--color-card);
  border-radius: var(--radius-xl);
  border: 1px solid var(--color-border);
  margin-bottom: var(--spacing-lg);
  overflow: hidden;
  box-shadow: var(--shadow-soft);
  transition: all 0.4s cubic-bezier(0.23, 1, 0.32, 1);
  position: relative;
  border: 1px solid rgba(226, 232, 240, 0.4);
}

/* Custom Card Accent */
.info-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 4px;
  background: linear-gradient(90deg, var(--color-accent), var(--color-accent-light));
  border-radius: var(--radius-xl) var(--radius-xl) 0 0;
}

.info-card:hover {
  transform: translateY(-6px);
  box-shadow: var(--shadow-hover);
  border-color: rgba(59, 130, 246, 0.2);
}

.card-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  padding: var(--spacing-lg);
  background: rgba(255, 255, 255, 0.6);
  border-bottom: 1px solid var(--color-border);
  position: relative;
  overflow: hidden;
}

/* Gradient Overlay for Header */
.card-header::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 100%;
  background: linear-gradient(90deg, rgba(59, 130, 246, 0.05), transparent 50%);
  pointer-events: none;
}

.card-header h2 {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 600;
  color: var(--color-text-dark);
  font-family: 'Clash Display', sans-serif;
  position: relative;
  z-index: 1;
}

.card-content {
  padding: var(--spacing-xl);
}

.section-intro {
  font-size: 0.9375rem;
  line-height: 1.6;
  color: var(--color-text-muted);
  margin-bottom: var(--spacing-lg);
}

.feature-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: var(--spacing-lg);
  margin-bottom: var(--spacing-xl);
}

.feature-box {
  padding: var(--spacing-lg);
  background: linear-gradient(to right, #FCFDFF, #F9FAFB);
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border);
  transition: all 0.3s cubic-bezier(0.23, 1, 0.32, 1);
  position: relative;
  overflow: hidden;
  border-left: 3px solid transparent;
}

.feature-box:hover {
  border-left-color: var(--color-accent);
  background: linear-gradient(to right, #FCFDFF, #EFF6FF);
  transform: translateY(-4px);
  box-shadow: var(--shadow-soft);
}

.feature-box-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-md);
}

.feature-box-header h3 {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--color-text-dark);
  font-family: 'Satoshi', sans-serif;
}

.feature-list {
  margin: 0;
  padding-left: var(--spacing-lg);
  list-style: disc;
}

.feature-list li {
  font-size: 0.875rem;
  line-height: 1.6;
  color: var(--color-text-muted);
  margin-bottom: var(--spacing-sm);
}

.screenshot-section {
  margin-top: var(--spacing-xl);
  background: linear-gradient(to bottom, rgba(241, 245, 249, 0.5), transparent);
  border-radius: var(--radius-md);
  padding: 40px 0;
  margin: 0 -48px;
  text-align: center;
}

.screenshot-section h4 {
  font-size: 1rem;
  font-weight: 600;
  color: var(--color-text-dark);
  margin-bottom: var(--spacing-md);
  font-family: 'Satoshi', sans-serif;
}

.screenshot-section img {
  width: 90%;
  height: auto;
  border-radius: var(--radius-md);
  border: 1px solid #eee;
  box-shadow: 0 10px 30px -15px rgba(0, 0, 0, 0.1);
  transition: all 0.3s ease;
}

.screenshot-section img:hover {
  transform: scale(1.03);
  box-shadow: 0 20px 40px -10px rgba(0, 0, 0, 0.15);
}

.graph-features {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
  margin-bottom: var(--spacing-xl);
}

.graph-feature-item {
  display: flex;
  gap: var(--spacing-lg);
  padding: var(--spacing-lg);
  background: linear-gradient(to right, #FCFDFF, #F9FAFB);
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border);
  transition: all 0.3s cubic-bezier(0.23, 1, 0.32, 1);
  border-left: 3px solid transparent;
}

.graph-feature-item:hover {
  border-left-color: var(--color-accent);
  background: linear-gradient(to right, #FCFDFF, #EFF6FF);
  transform: translateX(4px);
  box-shadow: var(--shadow-soft);
}

.feature-badge {
  flex-shrink: 0;
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #EFF6FF 0%, #DBEAFE 100%);
  border-radius: 16px;
  border: 1px solid var(--color-accent-light);
  box-shadow: 0 4px 15px -5px var(--color-accent-light);
  transition: all 0.3s;
}

.feature-badge:hover {
  background: linear-gradient(135deg, var(--color-accent) 0%, #3B82F6 100%);
  transform: scale(1.1) rotate(5deg);
}

.feature-badge :deep(svg) {
  width: 24px;
  height: 24px;
  color: #1E40AF;
  transition: color 0.3s;
}

.feature-badge:hover :deep(svg) {
  color: white;
}

.feature-details h4 {
  margin: 0 0 var(--spacing-sm) 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--color-text-dark);
  font-family: 'Satoshi', sans-serif;
}

.feature-details ul {
  margin: 0;
  padding-left: var(--spacing-lg);
  list-style: disc;
}

.feature-details li {
  font-size: 0.875rem;
  line-height: 1.6;
  color: var(--color-text-muted);
  margin-bottom: var(--spacing-xs);
}

@media (max-width: 768px) {
  .service-management-help {
    padding: var(--spacing-md);
  }

  .feature-grid {
    grid-template-columns: 1fr;
  }

  .graph-feature-item {
    flex-direction: column;
  }
  
  .screenshot-section {
    margin: 0 -24px;
    padding: 20px 0;
  }
  
  .screenshot-section img {
    width: 100%;
  }
  
  .page-header h1 {
    font-size: 1.5rem;
    letter-spacing: -1px;
  }
  
  .card-content {
    padding: var(--spacing-lg);
  }
}

/* Service Upload Guide Styles */
.upload-header::before {
  background: linear-gradient(90deg, rgba(34, 197, 94, 0.05), transparent 50%);
}

.upload-header h2 {
  color: #15803d; /* Green accent */
}

.upload-header .icon {
  color: #16a34a;
}

.download-banner {
  display: flex;
  align-items: center;
  gap: var(--spacing-xl);
  background: linear-gradient(135deg, #F0FDF4 0%, #DCFCE7 100%);
  border: 1px solid #BBF7D0;
  border-left: 4px solid #22C55E;
  padding: var(--spacing-xl);
  border-radius: var(--radius-md);
  margin-top: var(--spacing-xl);
  margin-bottom: var(--spacing-xl);
  transition: all 0.3s cubic-bezier(0.23, 1, 0.32, 1);
}

.download-banner:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 25px -10px rgba(34, 197, 94, 0.2);
}

.download-banner-icon {
  width: 64px;
  height: 64px;
  background: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #16A34A;
  box-shadow: 0 4px 15px rgba(22, 163, 74, 0.15);
  flex-shrink: 0;
}

.download-banner-content h4 {
  margin: 0 0 var(--spacing-xs) 0;
  font-size: 1.125rem;
  color: #166534;
  font-family: 'Satoshi', sans-serif;
}

.download-banner-content p {
  margin: 0 0 var(--spacing-lg) 0;
  color: #14532D;
  font-size: 0.9375rem;
}

.action-buttons {
  display: flex;
  gap: var(--spacing-md);
  flex-wrap: wrap;
}

.go-create-btn {
  background: white;
  color: #166534;
  border: 1px solid #86EFAC;
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: 0 var(--spacing-lg);
  height: 40px;
  border-radius: var(--radius-sm);
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.go-create-btn:hover {
  background: #F0FDF4;
  border-color: #22C55E;
  color: #14532D;
}

.upload-steps {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.upload-step-item {
  display: flex;
  gap: var(--spacing-md);
  padding: var(--spacing-md) var(--spacing-lg);
  background: white;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  transition: all 0.2s ease;
}

.upload-step-item:hover {
  border-color: #86EFAC;
  background: #F0FDF4;
}

.upload-step-number {
  width: 28px;
  height: 28px;
  background: #22C55E;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  font-weight: 700;
  font-family: 'Clash Display', sans-serif;
  flex-shrink: 0;
  margin-top: 2px;
}

.upload-step-content h4 {
  margin: 0 0 4px 0;
  color: var(--color-text-dark);
  font-family: 'Satoshi', sans-serif;
}

.upload-step-content p {
  margin: 0;
  color: var(--color-text-muted);
  font-size: 0.875rem;
}

.upload-step-image {
  width: 100%;
  height: auto;
  border-radius: var(--radius-md);
  border: 1px solid #eee;
  box-shadow: 0 10px 30px -15px rgba(0, 0, 0, 0.1);
  transition: all 0.3s ease;
}

/* .upload-step-content img:hover {
  transform: scale(1.03);
  box-shadow: 0 20px 40px -10px rgba(0, 0, 0, 0.15);
} */

@media (max-width: 768px) {
  .download-banner {
    flex-direction: column;
    text-align: center;
    gap: var(--spacing-md);
  }
}
/* Page Container */
.page-container {
  display: flex;
  max-width: 1400px;
  margin: 0 auto;
  width: 100%;
}

/* Sidebar Styles */
.sidebar {
  width: 250px;
  background: var(--color-card);
  border-left: 1px solid var(--color-border);
  transition: width 0.3s ease;
  position: sticky;
  top: 0;
  height: 100vh;
  overflow-y: hidden;
  overflow-x: hidden;
  box-shadow: var(--shadow-soft);
}

.sidebar.collapsed {
  width: 60px;
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-lg);
  border-bottom: 1px solid var(--color-border);
  background: rgba(255, 255, 255, 0.6);
}

.sidebar-header h3 {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--color-text-dark);
  transition: opacity 0.3s ease;
  font-family: 'Clash Display', sans-serif;
}

.sidebar.collapsed .sidebar-header h3 {
  opacity: 0;
  width: 0;
  overflow: hidden;
}

.toggle-btn {
  background: none;
  border: none;
  color: var(--color-text-dark);
  cursor: pointer;
  padding: var(--spacing-xs);
  border-radius: var(--radius-sm);
  transition: background-color 0.2s ease;
}

.toggle-btn:hover {
  background: rgba(59, 130, 246, 0.1);
}

.sidebar-nav ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.sidebar-nav li {
  margin: 0;
  padding: 0;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  padding: var(--spacing-md) var(--spacing-lg);
  color: var(--color-text-muted);
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.23, 1, 0.32, 1);
  border-right: 3px solid transparent;
  justify-content: flex-start;
}

.step-number-sidebar {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-accent-light);
  color: #275fb9;
  border-radius: 50%;
  font-size: 1.2rem;
  font-weight: 600;
  flex-shrink: 0;
  box-shadow: 0 4px 15px -5px var(--color-accent);
}

.nav-item:hover {
  background: rgba(59, 130, 246, 0.05);
  color: var(--color-text-dark);
  transform: translateX(-4px);
}

.sidebar-nav li.active .nav-item {
  background: rgba(59, 130, 246, 0.05);
  color: var(--color-accent);
  border-right-color: var(--color-accent);
  font-weight: 500;
  transform: translateX(-4px);
}

.sidebar.collapsed .nav-item span {
  opacity: 0;
  width: 0;
  overflow: hidden;
  transition: opacity 0.3s ease, width 0.3s ease;
}

.sidebar.collapsed .nav-item {
  justify-content: center;
  padding: var(--spacing-md);
  border-right: none;
}

.sidebar.collapsed .step-number-sidebar {
  display: flex;
}

/* Main Content Styles */
.main-content {
  flex: 1;
  padding: var(--spacing-xl);
  overflow-y: auto;
  background: var(--color-bg-page);
}

/* Responsive Design */
@media (max-width: 768px) {
  .page-container {
    flex-direction: column;
  }

  .sidebar {
    width: 100%;
    height: auto;
    position: relative;
    border-left: none;
    border-bottom: 1px solid var(--color-border);
  }

  .sidebar.collapsed {
    width: 100%;
  }

  .main-content {
    padding: var(--spacing-lg);
  }
}
</style>
