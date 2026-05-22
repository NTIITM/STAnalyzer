<template>
  <div class="intro-page">
    <div class="page-container">
      <!-- Main Content -->
      <div ref="mainContentRef" class="main-content">
        <div class="page-header">
          <h1 :data-text="$t('help.introduction.title')">{{ $t('help.introduction.title') }}</h1>
          <p class="subtitle">{{ $t('help.introduction.subtitle') }}</p>
          <div class="journal-notice" style="margin-top: 16px; padding: 12px; background-color: rgba(59, 130, 246, 0.1); border-left: 4px solid var(--color-accent); border-radius: 4px; color: var(--color-text-dark); font-weight: 500; font-size: 0.95rem; text-align: left; max-width: 600px; margin-left: auto; margin-right: auto; display: flex; align-items: flex-start; gap: 8px;">
            <Icon name="info" size="md" style="flex-shrink: 0;" />
            <span>This website is free and open to all users and there is no login requirement.</span>
          </div>
        </div>

        <!-- What is STAnalyzer -->
        <div id="section-0" class="info-card">
          <div class="card-header">
            <Icon name="info" size="md" />
            <h2>{{ $t('help.introduction.whatIs.title') }}</h2>
          </div>
          <div class="card-content">
            <p>{{ $t('help.introduction.whatIs.description') }}</p>
          </div>
        </div>

        <!-- System Architecture -->
        <div id="section-1" class="info-card">
          <div class="card-header">
            <Icon name="diagram" size="md" />
            <h2>{{ $t('help.introduction.architecture.title') }}</h2>
          </div>
          <div class="card-content">
            <div class="architecture-diagram" 
                 @mousemove="handleMouseMove"
                 @mouseleave="handleMouseLeave"
                 ref="architectureContainer">
              <el-image
                :src="getImagePath('Architecture_of_System.png')"
                :alt="$t('help.introduction.frameworkImage')"
                fit="contain"
                :preview-src-list="[getImagePath('Architecture_of_System.png')]"
                :preview-teleported="true"
                :scale="1"
                :style="imageStyle"
              />
            </div>
          </div>
        </div>

        <!-- Overview & Core Concept -->
        <div id="section-2" class="info-card">
          <div class="card-header">
            <Icon name="overview" size="md" />
            <h2>{{ $t('help.introduction.overview.title') }}</h2>
          </div>
          <div class="card-content">
            <div class="overview-list">
              <div class="overview-item">
                <div class="overview-number">1</div>
                <div class="overview-content">
                  <h3>{{ $t('help.introduction.overview.systemIdentity.title') }}</h3>
                  <p>{{ $t('help.introduction.overview.systemIdentity.description') }}</p>
                </div>
              </div>
              <div class="overview-item">
                <div class="overview-number">2</div>
                <div class="overview-content">
                  <h3>{{ $t('help.introduction.overview.primaryFunction.title') }}</h3>
                  <p>{{ $t('help.introduction.overview.primaryFunction.description') }}</p>
                </div>
              </div>
              <div class="overview-item">
                <div class="overview-number">3</div>
                <div class="overview-content">
                  <h3>{{ $t('help.introduction.overview.architecturalParadigm.title') }}</h3>
                  <p>{{ $t('help.introduction.overview.architecturalParadigm.description') }}</p>
                </div>
              </div>
              <div class="overview-item">
                <div class="overview-number">4</div>
                <div class="overview-content">
                  <h3>{{ $t('help.introduction.overview.mission.title') }}</h3>
                  <p>{{ $t('help.introduction.overview.mission.description') }}</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Key Technological Features -->
        <div id="section-3" class="info-card">
          <div class="card-header">
            <Icon name="star-square" size="md" />
            <h2>{{ $t('help.introduction.keyFeatures.title') }}</h2>
          </div>
          <div class="card-content">
            <div class="feature-grid">
              <div class="feature-item">
                <div class="feature-icon">
                  <Icon name="message" size="lg" />
                </div>
                <div class="feature-text">
                  <h3>{{ $t('help.introduction.keyFeatures.intentDriven.title') }}</h3>
                  <p>{{ $t('help.introduction.keyFeatures.intentDriven.description') }}</p>
                </div>
              </div>
              <div class="feature-item">
                <div class="feature-icon">
                  <Icon name="refresh-cw" size="lg" />
                </div>
                <div class="feature-text">
                  <h3>{{ $t('help.introduction.keyFeatures.multiModal.title') }}</h3>
                  <p>{{ $t('help.introduction.keyFeatures.multiModal.description') }}</p>
                </div>
              </div>
              <div class="feature-item">
                <div class="feature-icon">
                  <Icon name="check" size="lg" />
                </div>
                <div class="feature-text">
                  <h3>{{ $t('help.introduction.keyFeatures.evidenceBased.title') }}</h3>
                  <p>{{ $t('help.introduction.keyFeatures.evidenceBased.description') }}</p>
                </div>
              </div>
              <div class="feature-item">
                <div class="feature-icon">
                  <Icon name="light-bulb" size="lg" />
                </div>
                <div class="feature-text">
                  <h3>{{ $t('help.introduction.keyFeatures.fullTraceability.title') }}</h3>
                  <p>{{ $t('help.introduction.keyFeatures.fullTraceability.description') }}</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Functional Modules -->
        <div id="section-4" class="info-card">
          <div class="card-header">
            <Icon name="diagram" size="md" />
            <h2>{{ $t('help.introduction.multiAgent.title') }}</h2>
          </div>
          <div class="card-content">
            <div class="feature-grid">
              <div class="feature-item">
                <div class="feature-icon">
                  <Icon name="user" size="lg" />
                </div>
                <div class="feature-text">
                  <h3>{{ $t('help.introduction.multiAgent.orchestrator.title') }}</h3>
                  <p>{{ $t('help.introduction.multiAgent.orchestrator.description') }}</p>
                </div>
              </div>
              <div class="feature-item">
                <div class="feature-icon">
                  <Icon name="services" size="lg" />
                </div>
                <div class="feature-text">
                  <h3>{{ $t('help.introduction.multiAgent.servicePlanner.title') }}</h3>
                  <p>{{ $t('help.introduction.multiAgent.servicePlanner.description') }}</p>
                </div>
              </div>
              <div class="feature-item">
                <div class="feature-icon">
                  <Icon name="chart-pie" size="lg" />
                </div>
                <div class="feature-text">
                  <h3>{{ $t('help.introduction.multiAgent.dataInterpretation.title') }}</h3>
                  <p>{{ $t('help.introduction.multiAgent.dataInterpretation.description') }}</p>
                </div>
              </div>
              <div class="feature-item">
                <div class="feature-icon">
                  <Icon name="database" size="lg" />
                </div>
                <div class="feature-text">
                  <h3>{{ $t('help.introduction.multiAgent.knowledgeIntegration.title') }}</h3>
                  <p>{{ $t('help.introduction.multiAgent.knowledgeIntegration.description') }}</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- User Interface & Experience -->
        <div id="section-5" class="info-card">
          <div class="card-header">
            <Icon name="user" size="md" />
            <h2>{{ $t('help.introduction.ui.title') }}</h2>
          </div>
          <div class="card-content">
            <div class="feature-grid">

              <div class="feature-item">
                <div class="feature-icon">
                  <Icon name="chart-pie" size="lg" />
                </div>
                <div class="feature-text">
                  <h3>{{ $t('help.introduction.ui.interactiveVisualization.title') }}</h3>
                  <p>{{ $t('help.introduction.ui.interactiveVisualization.description') }}</p>
                </div>
              </div>
              <div class="feature-item">
                <div class="feature-icon">
                  <Icon name="services" size="lg" />
                </div>
                <div class="feature-text">
                  <h3>{{ $t('help.introduction.ui.serviceManagement.title') }}</h3>
                  <p>{{ $t('help.introduction.ui.serviceManagement.description') }}</p>
                </div>
              </div>
              <div class="feature-item">
                <div class="feature-icon">
                  <Icon name="activity" size="lg" />
                </div>
                <div class="feature-text">
                  <h3>{{ $t('help.introduction.ui.executionMonitoring.title') }}</h3>
                  <p>{{ $t('help.introduction.ui.executionMonitoring.description') }}</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Core Advantages -->
        <div id="section-6" class="info-card">
          <div class="card-header">
            <Icon name="star" size="md" />
            <h2>{{ $t('help.introduction.coreAdvantages.title') }}</h2>
          </div>
          <div class="card-content">
            <div class="advantages-list">
              <div class="advantage-item">
                <div class="advantage-number">1</div>
                <div class="advantage-content">
                  <h4>{{ $t('help.introduction.coreAdvantages.lowBarrier.title') }}</h4>
                  <p>{{ $t('help.introduction.coreAdvantages.lowBarrier.description') }}</p>
                </div>
              </div>
              <div class="advantage-item">
                <div class="advantage-number">2</div>
                <div class="advantage-content">
                  <h4>{{ $t('help.introduction.coreAdvantages.highEfficiency.title') }}</h4>
                  <p>{{ $t('help.introduction.coreAdvantages.highEfficiency.description') }}</p>
                </div>
              </div>
              <div class="advantage-item">
                <div class="advantage-number">3</div>
                <div class="advantage-content">
                  <h4>{{ $t('help.introduction.coreAdvantages.reproducibility.title') }}</h4>
                  <p>{{ $t('help.introduction.coreAdvantages.reproducibility.description') }}</p>
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
        :currentStep="currentStep"
        @update:currentStep="(index) => currentStep = index"
      />
      
    </div>
  </div>
</template>

<script setup lang="ts">
import Icon from '../common/Icon.vue'
import { ElImage } from 'element-plus'
import SidebarNavigation from '../common/SidebarNavigation.vue'
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

// Current active step
const currentStep = ref<number>(0)

// Navigation steps for sidebar
const navigationSteps = computed(() => [
  {
    title: t('help.introduction.whatIs.title')
  },
  {
    title: t('help.introduction.architecture.title')
  },
  {
    title: t('help.introduction.overview.title')
  },
  {
    title: t('help.introduction.keyFeatures.title')
  },
  {
    title: t('help.introduction.multiAgent.title')
  },
  {
    title: t('help.introduction.ui.title')
  },
  {
    title: t('help.introduction.coreAdvantages.title')
  }
])

function getImagePath(imageName: string): string {
  const base = import.meta.env.BASE_URL.replace(/\/$/, '')
  return `${base}/pictures/${imageName}`
}

// 3D鼠标跟随效果
const architectureContainer = ref(null)
const imageStyle = reactive({
  width: '70%',
  cursor: 'pointer',
  transform: 'perspective(1000px) rotateX(0deg) rotateY(0deg) translateZ(0px)',
  transition: 'transform 0.1s ease-out'
})

function handleMouseMove(event: MouseEvent) {
  if (!architectureContainer.value) return
  
  const container = architectureContainer.value as HTMLElement
  const rect = container.getBoundingClientRect()
  const centerX = rect.left + rect.width / 2
  const centerY = rect.top + rect.height / 2
  
  // 计算鼠标相对于容器中心的位置
  const mouseX = event.clientX - centerX
  const mouseY = event.clientY - centerY
  
  // 计算旋转角度，范围限制在-10到10度之间
  const rotateX = (mouseY / (rect.height / 2)) * -10
  const rotateY = (mouseX / (rect.width / 2)) * 10
  
  // 计算Z轴位移，范围限制在-20到20px之间
  const translateZ = Math.sqrt(mouseX * mouseX + mouseY * mouseY) / 10
  
  // 应用变换
  imageStyle.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateZ(${translateZ}px)`
}

function handleMouseLeave() {
  // 鼠标离开时重置变换
  imageStyle.transform = 'perspective(1000px) rotateX(0deg) rotateY(0deg) translateZ(0px)'
}

// 移除IntersectionObserver，减少性能负担
let scrollHandler: () => void

onMounted(() => {
  // 仅保留导航联动逻辑，移除动画相关代码
  scrollHandler = () => {
    const sections = document.querySelectorAll('[id^="section-"]')
    let currentSectionIndex = 0
    
    sections.forEach((section, index) => {
      const rect = section.getBoundingClientRect()
      if (rect.top <= 100) {
        currentSectionIndex = index
      }
    })
    
    currentStep.value = currentSectionIndex
  }
  
  // 添加滚动事件监听器
  window.addEventListener('scroll', scrollHandler)
})

onUnmounted(() => {
  // 清理滚动事件监听器
  if (scrollHandler) {
    window.removeEventListener('scroll', scrollHandler)
  }
})

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
  --spacing-xs: 8px;
  --spacing-md: 16px;
  --spacing-lg: 24px;
  --spacing-xl: 32px;
}

/* ========================================== 
   🎬 Animation Styles
   ========================================== */
/* 移除入场动画，减少渲染负担 */
.info-card, .overview-item, .feature-item, .advantage-item {
  opacity: 1;
  transform: translateY(0);
  transition: none;
}

.intro-page {
  min-height: 100vh;
  font-family: 'Satoshi', -apple-system, BlinkMacSystemFont, sans-serif;
  color: var(--color-text-muted);
  line-height: 1.7;
  /* 渐变背景 */
  background: linear-gradient(135deg, #F8FAFC 0%, #E2E8F0 100%);
  /* 添加背景纹理 */
  background-image: 
    radial-gradient(circle at 25% 25%, rgba(59, 130, 246, 0.05) 0%, transparent 50%),
    radial-gradient(circle at 75% 75%, rgba(30, 64, 175, 0.05) 0%, transparent 50%);
  background-attachment: fixed;
  /* 平滑滚动 */
  scroll-behavior: smooth;
}

/* 全局平滑滚动 */
html {
  scroll-behavior: smooth;
}

/* 滚动条样式 */
::-webkit-scrollbar {
  width: 8px;
}

::-webkit-scrollbar-track {
  background: #f1f5f9;
  border-radius: 4px;
}

::-webkit-scrollbar-thumb {
  background: linear-gradient(135deg, #3B82F6, #1E40AF);
  border-radius: 4px;
  transition: background 0.3s ease;
}

::-webkit-scrollbar-thumb:hover {
  background: linear-gradient(135deg, #1E40AF, #3B82F6);
}

/* ==========================================
   📰 Editorial Header (Magazine Style)
   ========================================== */
.page-header {
  text-align: center;
  max-width: 800px;
  margin: 0 auto var(--spacing-xl);
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
  margin: 0;
  font-family: 'Clash Display', sans-serif;
  font-size: 2.5rem;
  font-weight: 700;
  color: var(--color-text-dark);
  letter-spacing: -1.5px;
  line-height: 1.5;
  background: linear-gradient(135deg, #0F172A 0%, #1E40AF 50%, #3B82F6 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin-bottom: var(--spacing-md);
  text-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  position: relative;
  display: inline-block;
}

/* 标题发光效果 */
.page-header h1::after {
  content: attr(data-text);
  position: absolute;
  left: 0;
  top: 0;
  width: 100%;
  height: 100%;
  background: linear-gradient(135deg, #3B82F6 0%, #1E40AF 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  filter: blur(8px);
  opacity: 0.3;
  z-index: -1;
}

.subtitle {
  font-size: 1rem;
  font-weight: 400;
  color: var(--color-text-muted);
  margin-top: 16px;
  max-width: 600px;
  margin-left: auto;
  margin-right: auto;
  line-height: 1.6;
}

/* ==========================================
   🃏 Refined Cards (Glass & Shadow)
   ========================================== */
.info-card {
  background: var(--color-card);
  border-radius: var(--radius-xl);
  border: 1px solid var(--color-border);
  margin-bottom: var(--spacing-lg);
  overflow: hidden;
  box-shadow: var(--shadow-soft);
  position: relative;
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
  box-shadow: var(--shadow-hover);
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
  font-family: 'Clash Display', sans-serif;
  font-size: 1.5rem;
  font-weight: 600;
  color: var(--color-text-dark);
  position: relative;
  z-index: 1;
  background: linear-gradient(90deg, #0F172A 0%, #1E40AF 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
  display: inline-block;
}

.card-content {
  padding: var(--spacing-xl);
}

.card-content p {
  font-size: 0.9375rem;
  line-height: 1.6;
  color: var(--color-text-muted);
  margin: 0;
}

/* ==========================================
   🖼️ Architecture Hero (Asymmetric Layout)
   ========================================== */
.architecture-diagram {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 40px 0;
  background: linear-gradient(to bottom, rgba(241, 245, 249, 0.5), transparent);
  border-radius: var(--radius-md);
  margin: 0 -48px;
  text-align: center;
}

.architecture-diagram img {
  max-width: 100%;
  height: auto;
  border-radius: var(--radius-md);
  box-shadow: 0 10px 30px -15px rgba(0, 0, 0, 0.1);
  border: 1px solid #eee;
  transition: all 0.3s ease;
}

.architecture-diagram img:hover {
  transform: scale(1.03);
  box-shadow: 0 20px 40px -10px rgba(0, 0, 0, 0.15);
}

.architecture-diagram :deep(.el-image) {
  border-radius: var(--radius-md);
  overflow: hidden;
  border: 1px solid #eee;
  box-shadow: 0 10px 30px -15px rgba(0, 0, 0, 0.1);
  transition: all 0.3s ease;
}

.architecture-diagram :deep(.el-image):hover {
  transform: scale(1.03);
  box-shadow: 0 20px 40px -10px rgba(0, 0, 0, 0.15);
}

/* ==========================================
   📊 Overview Grid (Typography Focus)
   ========================================== */
.overview-list {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
}

.overview-item {
  padding: var(--spacing-lg);
  background: #FCFDFF;
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border);
  transition: all 0.3s;
  border-left: 3px solid transparent;
  background: linear-gradient(to right, #FCFDFF, #F9FAFB);
}

.overview-item:hover {
  border-left-color: var(--color-accent);
  background: linear-gradient(to right, #FCFDFF, #EFF6FF);
}

.overview-item h3 {
  margin: 0 0 var(--spacing-xs) 0;
  font-size: 1.1rem;
  font-weight: 600;
  color: #212f5c;
  font-family: 'Satoshi', sans-serif;
  display: flex;
  align-items: center;
  gap: 8px;
  background: linear-gradient(90deg, #0F172A 0%, #1E40AF 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.overview-number {
  flex-shrink: 0;
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, var(--color-accent) 0%, #3B82F6 100%);
  color: rgb(21, 71, 152);
  border-radius: 12px;
  font-weight: 800;
  font-size: 1.5rem;
  font-style: italic;
  font-family: 'Clash Display', sans-serif;
  box-shadow: 0 4px 15px -5px var(--color-accent);
  z-index: 10;
  position: relative;
  overflow: visible;
  opacity: 1;
  margin-right: var(--spacing-md);
}

.overview-item {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-lg);
  padding: var(--spacing-md);
  background: linear-gradient(to right, #FFFFFF, #F9FAFB);
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border);
  transition: all 0.3s;
}

.overview-content {
  flex: 1;
}

.overview-item p {
  margin: 0;
  font-weight: 300;
  color: #475569;
  font-size: 0.875rem;
  line-height: 1.5;
}

/* ==========================================
   ⚙️ Feature Grid (Gradient Accents)
   ========================================== */
.feature-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: var(--spacing-lg);
  grid-auto-rows: 1fr;
}

.feature-item {
  display: flex;
  gap: var(--spacing-md);
  padding: var(--spacing-lg);
  background: var(--color-card);
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border);
  position: relative;
  overflow: hidden;
  border-bottom: 3px solid transparent;
}

.feature-item:hover {
  border-bottom-color: var(--color-accent);
  box-shadow: var(--shadow-hover);
}

.feature-icon {
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
}

.feature-icon :deep(svg) {
  width: 24px;
  height: 24px;
  color: #1E40AF;
}

.feature-text h3 {
  margin: 0 0 var(--spacing-xs) 0;
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--color-text-dark);
  font-family: 'Satoshi', sans-serif;
  background: linear-gradient(90deg, #0F172A 0%, #1E40AF 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.feature-text p {
  margin: 0;
  font-weight: 300;
  color: var(--color-text-muted);
  font-size: 0.875rem;
  line-height: 1.5;
}

/* ==========================================
   🏆 Advantages (Gradient Numbers)
   ========================================== */
.advantages-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
}

.advantage-item {
  display: flex;
  gap: var(--spacing-lg);
  padding: var(--spacing-lg);
  background: var(--color-card);
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border);
  position: relative;
  overflow: hidden;
}

.advantage-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 6px;
  background: linear-gradient(to bottom, var(--color-accent), #3B82F6);
  opacity: 0;
}

.advantage-item:hover {
  box-shadow: var(--shadow-hover);
}

.advantage-item:hover::before {
  opacity: 1;
}

.advantage-number {
  flex-shrink: 0;
  width: 64px;
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, var(--color-accent) 0%, #3B82F6 100%);
  color: rgb(21, 71, 152);
  border-radius: 16px;
  font-weight: 800;
  font-size: 2rem;
  font-style: italic;
  font-family: 'Clash Display', sans-serif;
  box-shadow: 0 4px 15px -5px var(--color-accent);
  z-index: 10;
  position: relative;
  margin-right: var(--spacing-lg);
}

.advantage-content h4 {
  margin: 0 0 var(--spacing-xs) 0;
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--color-text-dark);
  font-family: 'Satoshi', sans-serif;
  background: linear-gradient(90deg, #0F172A 0%, #1E40AF 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.advantage-content p {
  margin: 0;
  font-weight: 300;
  color: var(--color-text-muted);
  font-size: 0.875rem;
  line-height: 1.5;
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
  overflow-y: auto;
  overflow-x: hidden;
  box-shadow: var(--shadow-soft);
  background: var(--color-card);
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
  background: linear-gradient(90deg, #0F172A 0%, #1E40AF 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
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
  transition: all 0.2s ease;
  border-right: 3px solid transparent;
  justify-content: flex-start;
}

.step-number-sidebar {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, var(--color-accent) 0%, #3B82F6 100%);
  color: white;
  border-radius: 50%;
  font-size: 0.8rem;
  font-weight: 600;
  flex-shrink: 0;
  box-shadow: 0 4px 15px -5px var(--color-accent);
}

.nav-item:hover {
  background: rgba(59, 130, 246, 0.05);
  color: var(--color-text-dark);
}

.sidebar-nav li.active .nav-item {
  background: rgba(59, 130, 246, 0.05);
  color: var(--color-accent);
  border-right-color: var(--color-accent);
  font-weight: 500;
}

.sidebar-nav li.active .step-number-sidebar {
  background: linear-gradient(135deg, #3B82F6 0%, var(--color-accent) 100%);
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
@media (max-width: 1024px) {
  .page-header h1 {
    font-size: 2rem;
  }
  
  .overview-list {
    grid-template-columns: 1fr;
  }
  
  .feature-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .intro-page {
    padding: var(--spacing-md);
  }

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

  .page-header h1 {
    font-size: 1.8rem;
    letter-spacing: -1px;
  }

  .card-content {
    padding: 24px;
  }

  .feature-grid {
    grid-template-columns: 1fr;
  }

  .architecture-diagram :deep(.el-image) {
    transform: rotate(0deg) !important;
    width: 100% !important;
    margin: 0 auto;
  }

  .advantage-number {
    width: 56px;
    height: 56px;
    font-size: 1.8rem;
    z-index: 1;
    position: relative;
    color: white;
  }
  
  .feature-icon {
    width: 48px;
    height: 48px;
  }
  
  .feature-icon :deep(svg) {
    width: 24px;
    height: 24px;
  }
}

@media (max-width: 480px) {
  .page-header h1 {
    font-size: 1.5rem;
  }
  
  .card-header h2 {
    font-size: 1.2rem;
  }
  
  .feature-text h3,
  .overview-item h3,
  .advantage-content h4 {
    font-size: 1rem;
  }
  
  .card-content {
    padding: 16px;
  }
  
  .advantage-number {
    width: 48px;
    height: 48px;
    font-size: 1.5rem;
  }
  
  .feature-icon {
    width: 40px;
    height: 40px;
  }
  
  .feature-icon :deep(svg) {
    width: 20px;
    height: 20px;
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
  background: transparent;
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
