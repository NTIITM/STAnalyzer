<template>
  <div class="getting-started-page">
    <div class="page-container">
      <!-- Sidebar Navigation -->
      <div class="sidebar" :class="{ 'collapsed': !sidebarExpanded }">
        <div class="sidebar-header">
          <h3 v-if="sidebarExpanded">{{ $t('help.common.navigation') }}</h3>
          <button class="toggle-btn" @click="toggleSidebar">
            <Icon :name="sidebarExpanded ? 'arrow-left' : 'arrow-right'" size="md" />
          </button>
        </div>
        <nav class="sidebar-nav">
          <ul>
            <li 
              v-for="(step, index) in workflowSteps" 
              :key="index"
              :class="{ 'active': currentStep === index }"
              @click="scrollToStep(index)"
            >
              <div class="nav-item">
                <div class="step-number-sidebar">{{ index + 1 }}</div>
                <!-- <Icon :name="step.icon" size="sm" /> -->
                <span v-if="sidebarExpanded">{{ step.title }}</span>
              </div>
            </li>
          </ul>
        </nav>
      </div>

      <!-- Main Content -->
      <div class="main-content">
        <div class="page-header">
          <h1>{{ $t('help.sections.gettingStarted.title') }}</h1>
          <p class="subtitle">{{ $t('help.sections.gettingStarted.description') }}</p>
        </div>

        <!-- Workflow Steps -->
        <div class="workflow-container">
          <div 
            class="workflow-step" 
            v-for="(step, index) in workflowSteps" 
            :key="index"
            :id="`step-${index}`"
          >
            <div class="step-number">{{ index + 1 }}</div>
            <div class="step-card">
              <div class="step-header">
                <Icon :name="step.icon" size="lg" />
                <h2>{{ step.title }}</h2>
              </div>
              <div class="step-content">
                <p class="step-description">
                  {{ step.description }}
                  <p v-if="step.icon === 'upload'">
                    <span>🌟</span>
                    <span @click="downloadSampleFile()" class="download-text">
                      {{ $t('help.downloadSampleDataPrompt') }}
                    </span>
                    <span>🌟</span>
                  </p>
                </p>
                
                <!-- Key Points -->
                <div v-if="step.keyPoints" class="key-points">
                  <h4>{{ $t('help.common.keyPoints') }}</h4>
                  <ul>
                    <li v-for="(point, idx) in step.keyPoints" :key="idx">{{ point }}</li>
                  </ul>
                </div>

                <!-- Screenshot Carousel -->
                <div v-if="step.images" class="step-image">
                  <el-carousel v-if="step.images.length > 1" height="400px" :interval="0" indicator-position="outside">
                    <el-carousel-item v-for="(img, idx) in step.images" :key="idx">
                      <el-image
                        :src="getImagePath(img)"
                        :alt="step.title"
                        fit="contain"
                        :preview-src-list="[getImagePath(img)]"
                        :preview-teleported="true"
                        :scale="0.6"
                        style="width: 100%; height: 100%; cursor: pointer;"
                      />
                    </el-carousel-item>
                  </el-carousel>
                  <div v-else class="single-image-container">
                    <el-image
                      :src="getImagePath(step.images[0])"
                      :alt="step.title"
                      fit="contain"
                      :preview-src-list="[getImagePath(step.images[0])]"
                      :preview-teleported="true"
                      :scale="0.6"
                      style="width: 100%; height: 100%; cursor: pointer;"
                    />
                  </div>
                </div>

                <!-- Table Data -->
                <!-- <div v-if="step.tableData" class="step-table">
                  <div class="table-responsive">
                    <table class="data-table">
                      <thead>
                        <tr>
                          <th>Cluster</th>
                          <th>Primary Functional Domain Inference</th>
                          <th>Key Supporting Evidence</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr v-for="(item, idx) in step.tableData" :key="idx">
                          <td class="cluster-cell">{{ item.cluster }}</td>
                          <td class="domain-cell">{{ item.domain }}</td>
                          <td class="evidence-cell">{{ item.evidence }}</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div> -->

                <!-- Tips -->
                <div v-if="step.tips" class="tips-box">
                  <Icon name="light-bulb" size="md" />
                  <span>{{ step.tips }}</span>
                </div>
              </div>
            </div>
            <div v-if="index < workflowSteps.length - 1" class="step-arrow" @click="scrollToStep(index + 1)">
              <Icon name="arrow-down" size="lg" />
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import Icon from '../common/Icon.vue'
import { ElCarousel, ElCarouselItem, ElImage } from 'element-plus'

const { t } = useI18n()

// Sidebar state
const getInitialSidebarState = (): boolean => {
  const savedState = localStorage.getItem('sidebarExpanded')
  return savedState ? JSON.parse(savedState) : true
}

const sidebarExpanded = ref<boolean>(getInitialSidebarState())

// Current active step
const currentStep = ref<number>(0)

// Toggle sidebar
const toggleSidebar = () => {
  sidebarExpanded.value = !sidebarExpanded.value
  localStorage.setItem('sidebarExpanded', JSON.stringify(sidebarExpanded.value))
}

// Scroll to step
const scrollToStep = (index: number) => {
  const element = document.getElementById(`step-${index}`)
  if (element) {
    element.scrollIntoView({ behavior: 'smooth' })
    currentStep.value = index
  }
}

// Update current step based on scroll position
const updateCurrentStep = () => {
  const steps = workflowSteps.value
  for (let i = steps.length - 1; i >= 0; i--) {
    const element = document.getElementById(`step-${i}`)
    if (element) {
      const rect = element.getBoundingClientRect()
      if (rect.top <= 100) {
        currentStep.value = i
        break
      }
    }
  }
}

// Watch sidebar state change
watch(sidebarExpanded, (newValue) => {
  localStorage.setItem('sidebarExpanded', JSON.stringify(newValue))
})

// Lifecycle hooks
onMounted(() => {
  window.addEventListener('scroll', updateCurrentStep)
  // Initial update
  updateCurrentStep()
})

onUnmounted(() => {
  window.removeEventListener('scroll', updateCurrentStep)
})

const workflowSteps = computed(() => [
  {
    icon: 'folder',
    title: t('help.sections.gettingStarted.steps.createProject.title'),
    description: t('help.sections.gettingStarted.steps.createProject.description'),
    keyPoints: [
      t('help.sections.gettingStarted.steps.createProject.point0'),
      t('help.sections.gettingStarted.steps.createProject.point1'),
      t('help.sections.gettingStarted.steps.createProject.point2'),
      t('help.sections.gettingStarted.steps.createProject.point3')
    ],
    images: ['create_project_0.png', 'create_project_1.png'],
    tips: t('help.sections.gettingStarted.steps.createProject.tip')
  },
  {
    icon: 'upload',
    title: t('help.sections.gettingStarted.steps.uploadData.title'),
    description: t('help.sections.gettingStarted.steps.uploadData.description'),
    keyPoints: [
      t('help.sections.gettingStarted.steps.uploadData.point1'),
      t('help.sections.gettingStarted.steps.uploadData.point2'),
      t('help.sections.gettingStarted.steps.uploadData.point3'),
      t('help.sections.gettingStarted.steps.uploadData.point4')
    ],
    images: ['upload_data_0.png', 'upload_data_1.png', 'upload_data_2.png'],
    tips: t('help.sections.gettingStarted.steps.uploadData.tip')
  },
  {
    icon: 'context',
    title: t('help.sections.gettingStarted.steps.addContext.title'),
    description: t('help.sections.gettingStarted.steps.addContext.description'),
    keyPoints: [
      t('help.sections.gettingStarted.steps.addContext.point1'),
      t('help.sections.gettingStarted.steps.addContext.point2'),
      t('help.sections.gettingStarted.steps.addContext.point3')
    ],
    images: ['add_file_to_context_0.png'],
    tips: t('help.sections.gettingStarted.steps.addContext.tip')
  },
  {
    icon: 'robot',
    title: t('help.sections.gettingStarted.steps.askAgent.title'),
    description: t('help.sections.gettingStarted.steps.askAgent.description'),
    keyPoints: [
      t('help.sections.gettingStarted.steps.askAgent.point1'),
      t('help.sections.gettingStarted.steps.askAgent.point2'),
      t('help.sections.gettingStarted.steps.askAgent.point3')
    ],
    images: ['send_query_0.png'],
    tips: t('help.sections.gettingStarted.steps.askAgent.tip')
  },
  // {
  //   icon: 'document',
  //   title: t('help.sections.gettingStarted.steps.viewReport.title'),
  //   description: t('help.sections.gettingStarted.steps.viewReport.description'),
  //   keyPoints: [
  //     t('help.sections.gettingStarted.steps.viewReport.point1'),
  //     t('help.sections.gettingStarted.steps.viewReport.point2'),
  //     t('help.sections.gettingStarted.steps.viewReport.point3')
  //   ],
  //   images: ['agent_generate_conclusion.png'],
  //   tips: t('help.sections.gettingStarted.steps.viewReport.tip')
  // },
  {
    icon: 'results',
    title: t('help.sections.gettingStarted.steps.analysis.title'),
    description: t('help.sections.gettingStarted.steps.analysis.description'),
    keyPoints: [
      t('help.sections.gettingStarted.steps.analysis.point1'),
      t('help.sections.gettingStarted.steps.analysis.point2'),
      t('help.sections.gettingStarted.steps.analysis.point3')
    ],
    images: ['analysis_0.png', 'analysis_1.png', 'analysis_2.png', 'analysis_3.png'],
    tips: t('help.sections.gettingStarted.steps.analysis.tip')
  },
  // {
  //   icon: 'analysis',
  //   title: t('help.sections.gettingStarted.steps.analysis2.title'),
  //   description: t('help.sections.gettingStarted.steps.analysis2.description'),
  //   images: ['analysis2_0.png'],
  // },
  // {
  //   icon: 'analysis',
  //   title: t('help.sections.gettingStarted.steps.illustrations.title'),
  //   description: t('help.sections.gettingStarted.steps.illustrations.description'),
  //   images: ['illustrations_0.png', 'illustrations_1.png'],
  // },
  // {
  //   icon: 'analysis',
  //   title: t('help.sections.gettingStarted.steps.validation.title'),
  //   description: t('help.sections.gettingStarted.steps.validation.description'),
  //   tableData: [
  //     {
  //       cluster: '0',
  //       domain: 'T-cell–rich adaptive immune niche',
  //       evidence: 'Top terms: T cell activation (GO:0042110), lymphocyte differentiation (GO:0030098), regulation of immune effector process (GO:0002697). Strong enrichment for CD3D, CD3E, CD247, IL2RA. Suggests organized, antigen-experienced T-cell microenvironment — potentially tertiary lymphoid structure (TLS)-like or tumor-infiltrating lymphocyte (TIL) aggregate.'
  //     },
  //     {
  //       cluster: '1',
  //       domain: 'B-cell–dominant lymphoid aggregate',
  //       evidence: 'Top terms: B cell activation (GO:0042113), humoral immune response (GO:0006959), antibody-mediated immunity (GO:0002443). High load of CD19, MS4A1 (CD20), CD79A, IGHM. Consistent with germinal center–adjacent or ectopic B-cell follicle — functionally distinct from cluster 0, emphasizing humoral over cytotoxic immunity.'
  //     },
  //     {
  //       cluster: '2',
  //       domain: 'Proliferating epithelial / tumor cell zone',
  //       evidence: 'Top terms: mitotic nuclear division (GO:0007067), cell cycle phase transition (GO:0044770), DNA replication initiation (GO:0006270). Enriched for MKI67, TOP2A, PCNA, UBE2C. Absence of strong immune/stromal signatures supports a rapidly cycling epithelial or malignant compartment — likely the core tumor proliferation region.'
  //     },
  //     {
  //       cluster: '3',
  //       domain: 'Regulatory T-cell / immunosuppressive interface',
  //       evidence: 'Top terms: regulation of T cell activation (GO:0050870), negative regulation of immune response (GO:0045089), T cell tolerance induction (GO:0001819). Co-enrichment of FOXP3, CTLA4, TGFB1, IL10RA. Suggests an immune-modulatory boundary zone — possibly tumor–stroma interface where suppression limits anti-tumor immunity.'
  //     },
  //     {
  //       cluster: '4',
  //       domain: 'Vascular–endothelial niche',
  //       evidence: 'Top terms: angiogenesis (GO:0001525), blood vessel development (GO:0001568), endothelial cell migration (GO:0043547). Enriched for PECAM1, VWF, CDH5, ENG. Represents functional vasculature — critical for nutrient supply, immune cell trafficking, and potential metastatic gateway.'
  //     },
  //     {
  //       cluster: '5',
  //       domain: 'Fibroblast–myofibroblast stromal region',
  //       evidence: 'Top terms: extracellular matrix organization (GO:0030198), collagen fibril organization (GO:0030199), wound healing (GO:0042060). Strong signals for COL1A1, ACTA2, TAGLN, FN1. Characteristic of reactive stroma — likely cancer-associated fibroblasts (CAFs) driving desmoplasia and structural remodeling.'
  //     },
  //     {
  //       cluster: '6',
  //       domain: 'Metabolically active stroma / adipose-adjacent interface',
  //       evidence: 'Top terms: fatty acid metabolic process (GO:0006631), oxidative phosphorylation (GO:0006119), mitochondrial respiratory chain complex assembly (GO:0070463). Enriched for ACADM, NDUFA4, COX7A2L. Lower immune/epithelial signals; higher mitochondrial/metabolic gene load suggests metabolically engaged stromal cells — possibly peritumoral adipocytes or oxidative stromal subsets influencing tumor metabolism.'
  //     },
  //     {
  //       cluster: '7',
  //       domain: 'Innate immune / myeloid-rich inflammatory zone',
  //       evidence: 'Top terms: neutrophil activation (GO:0042119), myeloid leukocyte activation (GO:0002274), response to cytokine (GO:0034097). Enriched for S100A8, S100A9, FCGR3A, CD14, MMP9. Reflects acute inflammation — neutrophil extracellular trap (NET)-associated or macrophage-dense region, potentially linked to necrosis, hypoxia, or infection-like responses.'
  //     },
  //     {
  //       cluster: '8',
  //       domain: 'Differentiated epithelial / glandular or barrier tissue',
  //       evidence: 'Top terms: epithelial cell differentiation (GO:0030855), cell–cell adhesion via plasma membrane proteins (GO:0098631), tight junction assembly (GO:0061024). Enriched for KRT19, EPCAM, CLDN4, CDH1. Highest enrichment signal (combined score = 26.75); minimal proliferation or immune signatures. Consistent with mature, polarized epithelium — e.g., normal ductal structures, benign glands, or well-differentiated tumor regions with intact barrier function.'
  //     }
  //   ]
  // },
])

function getImagePath(imageName: string): string {
  const base = import.meta.env.BASE_URL.replace(/\/$/, '')
  return `${base}/pictures/${imageName}`
}

// 使用 window.open 方式下载
function downloadSampleFile() {
  const fileId = '0'
  const url = `/STAnalyzer/api/file/sample`
  window.open(url, '_blank')
}
</script>

<style scoped>
.getting-started-page {
  background: var(--bg-secondary);
  min-height: 100vh;
}

.page-container {
  display: flex;
  max-width: 1400px;
  margin: 0 auto;
  width: 100%;
}

/* Sidebar Styles */
.sidebar {
  width: 250px;
  background: var(--bg-primary);
  border-right: 1px solid var(--border-color);
  transition: width 0.3s ease;
  position: sticky;
  top: 0;
  height: 100vh;
  overflow-y: auto;
  box-shadow: var(--shadow-sm);
}

.sidebar.collapsed {
  width: 60px;
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-lg);
  border-bottom: 1px solid var(--border-color);
}

.sidebar-header h3 {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
  transition: opacity 0.3s ease;
}

.sidebar.collapsed .sidebar-header h3 {
  opacity: 0;
  width: 0;
  overflow: hidden;
}

.toggle-btn {
  background: none;
  border: none;
  color: var(--text-primary);
  cursor: pointer;
  padding: var(--spacing-xs);
  border-radius: var(--radius-sm);
  transition: background-color 0.2s ease;
}

.toggle-btn:hover {
  background: var(--bg-secondary);
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
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s ease;
  border-left: 3px solid transparent;
}

.step-number-sidebar {
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--accent-primary);
  color: white;
  border-radius: 50%;
  font-size: 0.75rem;
  font-weight: 600;
  flex-shrink: 0;
}

.nav-item:hover {
  background: var(--bg-secondary);
  color: var(--text-primary);
}

.sidebar-nav li.active .nav-item {
  background: var(--bg-secondary);
  color: var(--accent-primary);
  border-left-color: var(--accent-primary);
  font-weight: 500;
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
}

.sidebar.collapsed .step-number-sidebar {
  display: flex;
}

/* Main Content Styles */
.main-content {
  flex: 1;
  padding: var(--spacing-xl);
  overflow-y: auto;
}

.page-header {
  margin-bottom: var(--spacing-xl);
  text-align: center;
}

.page-header h1 {
  font-size: 2rem;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: var(--spacing-md);
}

.subtitle {
  font-size: 1rem;
  color: var(--text-secondary);
  line-height: 1.6;
}

.workflow-container {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.workflow-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  position: relative;
}

.step-number {
  width: 56px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--accent-primary);
  color: white;
  border-radius: 50%;
  font-size: 1.5rem;
  font-weight: 700;
  box-shadow: var(--shadow-md);
  z-index: 2;
  margin-bottom: var(--spacing-lg);
}

.step-card {
  width: 100%;
  background: var(--bg-primary);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-color);
  overflow: hidden;
  box-shadow: var(--shadow-sm);
  transition: all 0.2s ease;
}

.step-card:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}

.step-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  padding: var(--spacing-lg);
  background: var(--bg-tertiary);
  border-bottom: 1px solid var(--border-color);
}

.step-header h2 {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 600;
  color: var(--text-primary);
}

.step-content {
  padding: var(--spacing-xl);
}

.step-description {
  font-size: 0.9375rem;
  line-height: 1.6;
  color: var(--text-secondary);
  margin-bottom: var(--spacing-lg);
}

.key-points {
  margin-bottom: var(--spacing-lg);
  padding: var(--spacing-lg);
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
}

.key-points h4 {
  margin: 0 0 var(--spacing-md) 0;
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--text-primary);
}

.key-points ul {
  margin: 0;
  padding-left: var(--spacing-lg);
  list-style: none;
}

.key-points li {
  position: relative;
  padding-left: var(--spacing-lg);
  margin-bottom: var(--spacing-sm);
  font-size: 0.875rem;
  line-height: 1.5;
  color: var(--text-secondary);
}

.key-points li::before {
  content: "✓";
  position: absolute;
  left: 0;
  color: var(--accent-primary);
  font-weight: 700;
}

.step-image {
  margin: var(--spacing-lg) 0;
  text-align: center;
}

.step-image img {
  max-width: 100%;
  height: auto;
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--border-color);
}

.single-image-container {
  height: 400px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--border-color);
  background: var(--bg-primary);
}

.step-table {
  margin: var(--spacing-lg) 0;
}

.table-responsive {
  overflow-x: auto;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  background: var(--bg-primary);
}

.data-table th {
  background: var(--bg-tertiary);
  color: var(--text-primary);
  font-weight: 600;
  text-align: left;
  padding: var(--spacing-md);
  border-bottom: 2px solid var(--border-color);
  white-space: nowrap;
}

.data-table td {
  padding: var(--spacing-md);
  border-bottom: 1px solid var(--border-color);
  vertical-align: top;
}

.data-table tr:last-child td {
  border-bottom: none;
}

.data-table tr:hover {
  background: var(--bg-secondary);
  transition: background 0.2s ease;
}

.cluster-cell {
  width: 80px;
  font-weight: 600;
  color: var(--accent-primary);
  text-align: center;
}

.domain-cell {
  width: 300px;
  font-weight: 500;
}

.evidence-cell {
  flex: 1;
  line-height: 1.5;
  color: var(--text-secondary);
}

@media (max-width: 768px) {
  .data-table th,
  .data-table td {
    padding: var(--spacing-sm);
    font-size: 0.875rem;
  }
  
  .cluster-cell {
    width: 60px;
  }
  
  .domain-cell {
    width: 200px;
  }
}

.tips-box {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-md);
  padding: var(--spacing-md) var(--spacing-lg);
  background: var(--bg-tertiary);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
  margin-top: var(--spacing-lg);
}

.tips-box span {
  font-size: 0.875rem;
  line-height: 1.5;
  color: var(--text-secondary);
}

.download-text {
  color: var(--accent-primary);
  font-style: italic;
  text-decoration: none;
  cursor: pointer;
  transition: color 0.2s ease;
}

.download-text:hover {
  color: var(--accent-secondary);
  text-decoration: underline;
}

.step-arrow {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 48px;
  color: var(--text-tertiary);
  cursor: pointer;
  transition: color 0.2s ease;
}

.step-arrow:hover {
  color: var(--accent-primary);
}

@media (max-width: 768px) {
  .page-container {
    flex-direction: column;
  }

  .sidebar {
    width: 100%;
    height: auto;
    position: relative;
    border-right: none;
    border-bottom: 1px solid var(--border-color);
  }

  .sidebar.collapsed {
    width: 100%;
  }

  .sidebar-header {
    padding: var(--spacing-md);
  }

  .sidebar-nav ul {
    display: flex;
    overflow-x: auto;
  }

  .sidebar-nav li {
    white-space: nowrap;
    flex-shrink: 0;
  }

  .nav-item {
    padding: var(--spacing-sm) var(--spacing-md);
    border-left: none;
    border-bottom: 3px solid transparent;
  }

  .sidebar-nav li.active .nav-item {
    border-left-color: transparent;
    border-bottom-color: var(--accent-primary);
  }

  .sidebar.collapsed .nav-item {
    justify-content: center;
    padding: var(--spacing-sm);
  }

  .main-content {
    padding: var(--spacing-md);
  }

  .page-header h1 {
    font-size: 1.5rem;
  }

  .step-content {
    padding: var(--spacing-lg);
  }
}
</style>
