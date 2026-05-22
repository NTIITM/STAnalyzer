<template>
  <div class="getting-started-page">
    <div class="page-container">
      <!-- Main Content -->
      <div ref="mainContentRef" class="main-content">
        <div class="page-header">
          <h1>{{ $t('help.sections.gettingStarted.title') }}</h1>
          <p class="subtitle">{{ $t('help.sections.gettingStarted.description') }}</p>
        </div>

        <!-- Workflow Steps -->
        <div class="workflow-container">
          <!-- Steps 1-5 -->
          <div 
            class="workflow-step" 
            v-for="(step, index) in workflowSteps.slice(0, 5)" 
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
                <div class="step-description">
                  <p>{{ step.description }}</p>
                  <p v-if="step.icon === 'upload'">
                    <span>🌟</span>
                    <a href="/STAnalyzer/Xenium_V1_Human_Lung_Cancer_Addon_FFPE_outs.h5ad" download class="download-text" rel="noopener noreferrer">
                      {{ $t('help.downloadSampleDataPrompt') }}
                    </a>
                    <span>🌟</span>
                  </p>
                </div>
                
                <!-- Key Points -->
                <div v-if="step.keyPoints" class="key-points">
                  <h4>{{ $t('help.common.keyPoints') }}</h4>
                  <ul>
                    <li v-for="(point, idx) in step.keyPoints" :key="idx">{{ point }}</li>
                  </ul>
                </div>

                <!-- Prompt -->
                <div v-if="step.prompt" class="prompt-points">
                  <h4>{{ $t('help.common.prompt') }}</h4>
                  <p>{{ step.prompt }}</p>
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
                <div v-if="step.tableData" class="step-table">
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
                </div>

                <!-- Sub Steps -->
                <div v-if="step.hasSubSteps && step.subSteps" class="sub-steps">
                  <div class="sub-step" v-for="(subStep, subIdx) in step.subSteps" :key="subIdx">
                    <div class="sub-step-badge">{{ subIdx + 1 }}</div>
                    <div class="sub-step-content">
                      <h5>{{ subStep.title }}</h5>
                      <p v-if="subStep.description">{{ subStep.description }}</p>
                      
                      <!-- Sub Step Single Image -->
                      <div v-if="subStep.image" class="step-screenshot">
                        <el-image
                          :src="getImagePath(subStep.image)"
                          :alt="subStep.title"
                          fit="contain"
                          :preview-src-list="[getImagePath(subStep.image)]"
                          :preview-teleported="true"
                          :scale="0.7"
                          class="el-image-medium el-image-no-border"
                        />
                      </div>
                      
                      <!-- Sub Step Multiple Images -->
                      <div v-else-if="subStep.images" class="step-screenshot">
                        <el-carousel v-if="subStep.images.length > 1" height="300px" :interval="0" indicator-position="outside">
                          <el-carousel-item v-for="(img, imgIdx) in subStep.images" :key="imgIdx">
                            <el-image
                              :src="getImagePath(img)"
                              :alt="subStep.title"
                              fit="contain"
                              :preview-src-list="[getImagePath(img)]"
                              :preview-teleported="true"
                              :scale="0.7"
                              style="width: 100%; height: 100%; cursor: pointer;"
                            />
                          </el-carousel-item>
                        </el-carousel>
                        <el-image v-else
                          :src="getImagePath(subStep.images[0])"
                          :alt="subStep.title"
                          fit="contain"
                          :preview-src-list="[getImagePath(subStep.images[0])]"
                          :preview-teleported="true"
                          :scale="0.7"
                          class="el-image-small el-image-no-border"
                        />
                      </div>
                    </div>
                  </div>
                </div>

                <!-- Tips -->
                <div v-if="step.tips" class="tips-box">
                  <Icon name="light-bulb" size="md" />
                  <span>{{ step.tips }}</span>
                </div>
              </div>
            </div>
            <div v-if="index < 4" class="step-arrow" @click="scrollToStep(index + 1)">
              <Icon name="arrow-down" size="lg" />
            </div>
          </div>

          <div class="step-arrow"  @click="scrollToStep(5)">
            <Icon name="arrow-down" size="lg" />
          </div>
          <!-- Transition Text -->
          <div class="transition-section">
            <div class="transition-text">
              {{ $t('help.sections.gettingStarted.transitionText') }}
            </div>
          </div>

          <!-- Remaining Steps -->
          <div 
            class="workflow-step" 
            v-for="(step, index) in workflowSteps.slice(5)" 
            :key="index + 5"
            :id="`step-${index + 5}`"
          >
            <div class="step-number">{{ index + 6 }}</div>
            <div class="step-card">
              <div class="step-header">
                <Icon :name="step.icon" size="lg" />
                <h2>{{ step.title }}</h2>
              </div>
              <div class="step-content">
                <div class="step-description">
                  <p>{{ step.description }}</p>
                  <p v-if="step.icon === 'upload'">
                    <span>🌟</span>
                    <a href="/STAnalyzer/Xenium_V1_Human_Lung_Cancer_Addon_FFPE_outs.h5ad" download class="download-text" rel="noopener noreferrer">
                      {{ $t('help.downloadSampleDataPrompt') }}
                    </a>
                    <span>🌟</span>
                  </p>
                </div>
                
                <!-- Key Points -->
                <div v-if="step.keyPoints" class="key-points">
                  <h4>{{ $t('help.common.keyPoints') }}</h4>
                  <ul>
                    <li v-for="(point, idx) in step.keyPoints" :key="idx">{{ point }}</li>
                  </ul>
                </div>

                <!-- Prompt -->
                <div v-if="step.prompt" class="prompt-points">
                  <h4>{{ $t('help.common.prompt') }}</h4>
                  <p>{{ step.prompt }}</p>
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
                <div v-if="step.tableData" class="step-table">
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
                </div>

                <!-- Sub Steps -->
                <div v-if="step.hasSubSteps && step.subSteps" class="sub-steps">
                  <div class="sub-step" v-for="(subStep, subIdx) in step.subSteps" :key="subIdx">
                    <div class="sub-step-badge">{{ subIdx + 1 }}</div>
                    <div class="sub-step-content">
                      <h5>{{ subStep.title }}</h5>
                      <p v-if="subStep.description">{{ subStep.description }}</p>
                      
                      <!-- Sub Step Single Image -->
                      <div v-if="subStep.image" class="step-screenshot">
                        <el-image
                          :src="getImagePath(subStep.image)"
                          :alt="subStep.title"
                          fit="contain"
                          :preview-src-list="[getImagePath(subStep.image)]"
                          :preview-teleported="true"
                          :scale="0.7"
                          class="el-image-medium el-image-no-border"
                        />
                      </div>
                      
                      <!-- Sub Step Multiple Images -->
                      <div v-else-if="subStep.images" class="step-screenshot">
                        <el-carousel v-if="subStep.images.length > 1" height="300px" :interval="0" indicator-position="outside">
                          <el-carousel-item v-for="(img, imgIdx) in subStep.images" :key="imgIdx">
                            <el-image
                              :src="getImagePath(img)"
                              :alt="subStep.title"
                              fit="contain"
                              :preview-src-list="[getImagePath(img)]"
                              :preview-teleported="true"
                              :scale="0.7"
                              style="width: 100%; height: 100%; cursor: pointer;"
                            />
                          </el-carousel-item>
                        </el-carousel>
                        <el-image v-else
                          :src="getImagePath(subStep.images[0])"
                          :alt="subStep.title"
                          fit="contain"
                          :preview-src-list="[getImagePath(subStep.images[0])]"
                          :preview-teleported="true"
                          :scale="0.7"
                          class="el-image-small el-image-no-border"
                        />
                      </div>
                    </div>
                  </div>
                </div>

                <!-- Tips -->
                <div v-if="step.tips" class="tips-box">
                  <Icon name="light-bulb" size="md" />
                  <span>{{ step.tips }}</span>
                </div>
              </div>
            </div>
            <div v-if="index + 5 < workflowSteps.length - 1" class="step-arrow" @click="scrollToStep(index + 6)">
              <Icon name="arrow-down" size="lg" />
            </div>
          </div>
        </div>
      </div>

      <!-- Sidebar Navigation -->
      <SidebarNavigation 
        :steps="workflowSteps" 
        :title="$t('help.common.steps')"
        sectionPrefix="step-"
        @update:currentStep="(index) => currentStep = index"
      />
      
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import Icon from '../common/Icon.vue'
import { ElCarousel, ElCarouselItem, ElImage } from 'element-plus'
import SidebarNavigation from '../common/SidebarNavigation.vue'

const { t } = useI18n()

// Current active step
const currentStep = ref<number>(0)

// Scroll to step function
const scrollToStep = (index: number) => {
  const element = document.getElementById(`step-${index}`)
  if (element) {
    element.scrollIntoView({ behavior: 'smooth' })
  }
}

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
  {
    icon: 'analysis',
    title: t('help.sections.gettingStarted.steps.analysis2.title'),
    description: t('help.sections.gettingStarted.steps.analysis2.description'),
    prompt: t('help.sections.gettingStarted.steps.analysis2.prompt'),
    images: ['analysis2_0.png'],
    tips: t('help.sections.gettingStarted.steps.analysis2.tip')
  },
  {
    icon: 'analysis',
    title: t('help.sections.gettingStarted.steps.illustrations.title'),
    description: t('help.sections.gettingStarted.steps.illustrations.description'),
    prompt: t('help.sections.gettingStarted.steps.illustrations.prompt'),
    images: ['illustrations_0.png', 'illustrations_1.png'],
    tips: t('help.sections.gettingStarted.steps.illustrations.tip')
  },
  {
    icon: 'analysis',
    title: t('help.sections.gettingStarted.steps.validation.title'),
    description: t('help.sections.gettingStarted.steps.validation.description'),
    prompt: t('help.sections.gettingStarted.steps.validation.prompt'),
    tableData: [
      {
        cluster: '0',
        domain: 'T-cell–rich adaptive immune niche',
        evidence: 'Top terms: T cell activation (GO:0042110), lymphocyte differentiation (GO:0030098), regulation of immune effector process (GO:0002697). Strong enrichment for CD3D, CD3E, CD247, IL2RA. Suggests organized, antigen-experienced T-cell microenvironment — potentially tertiary lymphoid structure (TLS)-like or tumor-infiltrating lymphocyte (TIL) aggregate.'
      },
      {
        cluster: '1',
        domain: 'B-cell–dominant lymphoid aggregate',
        evidence: 'Top terms: B cell activation (GO:0042113), humoral immune response (GO:0006959), antibody-mediated immunity (GO:0002443). High load of CD19, MS4A1 (CD20), CD79A, IGHM. Consistent with germinal center–adjacent or ectopic B-cell follicle — functionally distinct from cluster 0, emphasizing humoral over cytotoxic immunity.'
      },
      {
        cluster: '2',
        domain: 'Proliferating epithelial / tumor cell zone',
        evidence: 'Top terms: mitotic nuclear division (GO:0007067), cell cycle phase transition (GO:0044770), DNA replication initiation (GO:0006270). Enriched for MKI67, TOP2A, PCNA, UBE2C. Absence of strong immune/stromal signatures supports a rapidly cycling epithelial or malignant compartment — likely the core tumor proliferation region.'
      },
      {
        cluster: '3',
        domain: 'Regulatory T-cell / immunosuppressive interface',
        evidence: 'Top terms: regulation of T cell activation (GO:0050870), negative regulation of immune response (GO:0045089), T cell tolerance induction (GO:0001819). Co-enrichment of FOXP3, CTLA4, TGFB1, IL10RA. Suggests an immune-modulatory boundary zone — possibly tumor–stroma interface where suppression limits anti-tumor immunity.'
      },
      {
        cluster: '4',
        domain: 'Vascular–endothelial niche',
        evidence: 'Top terms: angiogenesis (GO:0001525), blood vessel development (GO:0001568), endothelial cell migration (GO:0043547). Enriched for PECAM1, VWF, CDH5, ENG. Represents functional vasculature — critical for nutrient supply, immune cell trafficking, and potential metastatic gateway.'
      },
      {
        cluster: '5',
        domain: 'Fibroblast–myofibroblast stromal region',
        evidence: 'Top terms: extracellular matrix organization (GO:0030198), collagen fibril organization (GO:0030199), wound healing (GO:0042060). Strong signals for COL1A1, ACTA2, TAGLN, FN1. Characteristic of reactive stroma — likely cancer-associated fibroblasts (CAFs) driving desmoplasia and structural remodeling.'
      },
      {
        cluster: '6',
        domain: 'Metabolically active stroma / adipose-adjacent interface',
        evidence: 'Top terms: fatty acid metabolic process (GO:0006631), oxidative phosphorylation (GO:0006119), mitochondrial respiratory chain complex assembly (GO:0070463). Enriched for ACADM, NDUFA4, COX7A2L. Lower immune/epithelial signals; higher mitochondrial/metabolic gene load suggests metabolically engaged stromal cells — possibly peritumoral adipocytes or oxidative stromal subsets influencing tumor metabolism.'
      },
      {
        cluster: '7',
        domain: 'Innate immune / myeloid-rich inflammatory zone',
        evidence: 'Top terms: neutrophil activation (GO:0042119), myeloid leukocyte activation (GO:0002274), response to cytokine (GO:0034097). Enriched for S100A8, S100A9, FCGR3A, CD14, MMP9. Reflects acute inflammation — neutrophil extracellular trap (NET)-associated or macrophage-dense region, potentially linked to necrosis, hypoxia, or infection-like responses.'
      },
      {
        cluster: '8',
        domain: 'Differentiated epithelial / glandular or barrier tissue',
        evidence: 'Top terms: epithelial cell differentiation (GO:0030855), cell–cell adhesion via plasma membrane proteins (GO:0098631), tight junction assembly (GO:0061024). Enriched for KRT19, EPCAM, CLDN4, CDH1. Highest enrichment signal (combined score = 26.75); minimal proliferation or immune signatures. Consistent with mature, polarized epithelium — e.g., normal ductal structures, benign glands, or well-differentiated tumor regions with intact barrier function.'
      }
    ],
    tips: t('help.sections.gettingStarted.steps.validation.tip')
  },
  {
    icon: 'analysis',
    title: t('help.sections.gettingStarted.steps.researchDirections.title'),
    description: t('help.sections.gettingStarted.steps.researchDirections.description'),
    prompt: t('help.sections.gettingStarted.steps.researchDirections.prompt'),
    images: ['research_direction_0.png', 'research_direction_1.png'],
    tips: t('help.sections.gettingStarted.steps.researchDirections.tip')
  },
  {
    icon: 'analysis',
    title: t('help.sections.gettingStarted.steps.multiAgent.title'),
    description: t('help.sections.gettingStarted.steps.multiAgent.description'),
    prompt: t('help.sections.gettingStarted.steps.multiAgent.prompt'),
    hasSubSteps: true,
    subSteps: [
      {
        title: t('help.sections.gettingStarted.steps.multiAgent.subSteps.automaticCodeAnalysis.title'),
        description: t('help.sections.gettingStarted.steps.multiAgent.subSteps.automaticCodeAnalysis.description'),
        image: 'code_analysis_0.png'
      },
      {
        title: t('help.sections.gettingStarted.steps.multiAgent.subSteps.mechanismBasedReasoning.title'),
        description: t('help.sections.gettingStarted.steps.multiAgent.subSteps.mechanismBasedReasoning.description'),
        images: ['reasoning_0.png', 'reasoning_1.png', 'reasoning_2.png']
      },
      {
        title: t('help.sections.gettingStarted.steps.multiAgent.subSteps.summaryReport.title'),
        description: t('help.sections.gettingStarted.steps.multiAgent.subSteps.summaryReport.description'),
        images: ['summary_0.png', 'summary_1.png', 'summary_2.png']
      }
    ],
    tips: t('help.sections.gettingStarted.steps.multiAgent.tip')
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
  --color-text-dark: #2C3E50;
  --color-text-muted: #64748B;
  --color-bg-page: #FAF9F6; /* Eye-friendly warm off-white / soft paper */
  --color-card: #FFFFFF;
  --color-accent: #1E40AF; /* Primary Blue */
  --color-accent-light: #3B82F6;
  --color-accent-lighter: #93C5FD;
  --color-border: #EAE6DF;
  --radius-xl: 20px;
  --radius-md: 12px;
  --radius-sm: 8px;
  --shadow-soft: 0 10px 25px -10px rgba(94, 110, 130, 0.08); /* Softer shadow */
  --shadow-hover: 0 20px 40px -10px rgba(94, 110, 130, 0.12);
}

.getting-started-page {
  background: var(--color-bg-page);
  min-height: 100vh;
  font-family: 'Satoshi', -apple-system, BlinkMacSystemFont, sans-serif;
  color: var(--color-text-muted);
  line-height: 1.7;
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
  max-width: 600px;
  margin-left: auto;
  margin-right: auto;
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
  margin-bottom: var(--spacing-xl);
}

.step-number {
  width: 64px;
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #275fb9;
  color: white;
  border-radius: 50%;
  font-size: 1.5rem;
  font-weight: 800;
  font-style: italic;
  font-family: 'Clash Display', sans-serif;
  box-shadow: 0 4px 15px -5px var(--color-accent);
  z-index: 10;
  margin-bottom: var(--spacing-lg);
  position: relative;
  overflow: visible;
  opacity: 1;
  transform: translateY(-10px);
}

.step-card {
  width: 100%;
  background: var(--color-card);
  border-radius: var(--radius-xl);
  border: 1px solid var(--color-border);
  overflow: hidden;
  box-shadow: var(--shadow-soft);
  transition: all 0.4s cubic-bezier(0.23, 1, 0.32, 1);
  position: relative;
  border: 1px solid rgba(226, 232, 240, 0.4);
}

/* Custom Card Accent */
.step-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 4px;
  background: linear-gradient(90deg, var(--color-accent), var(--color-accent-light));
  border-radius: var(--radius-xl) var(--radius-xl) 0 0;
}

.step-card:hover {
  transform: translateY(-6px);
  box-shadow: var(--shadow-hover);
  border-color: rgba(59, 130, 246, 0.2);
}

.step-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  padding: var(--spacing-lg);
  background: rgba(250, 249, 246, 0.9);
  border-bottom: 1px solid var(--color-border);
  position: relative;
  overflow: hidden;
}

/* Gradient Overlay for Header */
.step-header::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 100%;
  background: linear-gradient(90deg, rgba(59, 130, 246, 0.05), transparent 50%);
  pointer-events: none;
}

.step-header h2 {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 600;
  color: var(--color-text-dark);
  font-family: 'Clash Display', sans-serif;
  position: relative;
  z-index: 1;
}

.step-content {
  padding: var(--spacing-xl);
}

.step-description {
  font-size: 0.9375rem;
  line-height: 1.6;
  color: var(--color-text-muted);
  margin-bottom: var(--spacing-lg);
}

/* Prompt Label Styles */
.step-description p .prompt-label {
  font-weight: bold;
  font-style: italic;
  font-size: 1.1rem;
  color: #1E40AF;
  margin-right: var(--spacing-sm);
  display: inline-block;
}

.key-points {
  margin-bottom: var(--spacing-lg);
  padding: var(--spacing-lg);
  background: #FFFBF0; /* Warm subtle yellow cream */
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border);
  transition: all 0.3s;
  border-left: 4px solid transparent;
}

.key-points:hover {
  border-left-color: #EAB308; /* Soft golden yellow for hover border */
  background: #FEF9C3;
  transform: translateX(4px);
}

.key-points h4 {
  margin: 0 0 var(--spacing-md) 0;
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--color-text-dark);
  font-family: 'Satoshi', sans-serif;
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
  color: var(--color-text-muted);
}

.key-points li::before {
  content: "✓";
  position: absolute;
  left: 0;
  color: var(--color-accent);
  font-weight: 700;
}

.prompt-points {
  margin-bottom: var(--spacing-lg);
  padding: var(--spacing-lg);
  background: #EFF6FF; /* Light blue */
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border);
  transition: all 0.3s;
  border-left: 4px solid transparent;
}

.prompt-points:hover {
  border-left-color: #3B82F6; /* Blue for hover border */
  background: #DBEAFE;
  transform: translateX(4px);
}

/* Prompt Label Styles */
.prompt-points h4 {
  font-weight: bold;
  font-style: italic;
  font-size: 1.1rem;
  color: #1E40AF;
  margin-right: var(--spacing-sm);
  display: inline-block;
}

.step-image {
  margin: var(--spacing-lg) 0;
  text-align: center;
  background: linear-gradient(to bottom, rgba(241, 245, 249, 0.5), transparent);
  border-radius: var(--radius-md);
  padding: 40px 0;
  margin: 0 -48px;
}

.step-image img {
  max-width: 100%;
  height: auto;
  border-radius: var(--radius-md);
  box-shadow: 0 10px 30px -15px rgba(0, 0, 0, 0.1);
  border: 1px solid #eee;
  transition: all 0.3s ease;
}

.step-image img:hover {
  transform: scale(1.03);
  box-shadow: 0 20px 40px -10px rgba(0, 0, 0, 0.15);
}

.single-image-container {
  height: 400px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-md);
  box-shadow: 0 10px 30px -15px rgba(0, 0, 0, 0.1);
  border: 1px solid #eee;
  background: linear-gradient(to bottom, rgba(241, 245, 249, 0.5), transparent);
  transition: all 0.3s ease;
}

.single-image-container:hover {
  transform: scale(1.02);
  box-shadow: 0 20px 40px -10px rgba(0, 0, 0, 0.15);
}

.step-table {
  margin: var(--spacing-lg) 0;
}

.table-responsive {
  overflow-x: auto;
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border);
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  background: var(--color-card);
}

.data-table th {
  background: rgba(255, 255, 255, 0.6);
  color: var(--color-text-dark);
  font-weight: 600;
  text-align: left;
  padding: var(--spacing-md);
  border-bottom: 2px solid var(--color-border);
  white-space: nowrap;
  font-family: 'Satoshi', sans-serif;
}

.data-table td {
  padding: var(--spacing-md);
  border-bottom: 1px solid var(--color-border);
  vertical-align: top;
}

.data-table tr:last-child td {
  border-bottom: none;
}

.data-table tr:hover {
  background: rgba(59, 130, 246, 0.05);
  transition: background 0.2s ease;
}

.cluster-cell {
  width: 80px;
  font-weight: 600;
  color: var(--color-accent);
  text-align: center;
}

.domain-cell {
  width: 300px;
  font-weight: 500;
}

.evidence-cell {
  flex: 1;
  line-height: 1.5;
  color: var(--color-text-muted);
}

/* Sub-step Styles */
.sub-steps {
  margin-top: var(--spacing-lg);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
}

.sub-step {
  display: flex;
  gap: var(--spacing-md);
  margin-left: var(--spacing-lg);
}

.sub-step-badge {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #5685d2;
  color: white;
  border-radius: 8px;
  font-weight: 600;
  font-size: 0.875rem;
  margin-top: 0.25rem;
}

.sub-step-content {
  flex: 1;
}

.sub-step-content h5 {
  margin: 0 0 var(--spacing-sm) 0;
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--color-text-dark);
  font-family: 'Satoshi', sans-serif;
}

.sub-step-content p {
  margin: 0 0 var(--spacing-md) 0;
  font-size: 0.875rem;
  line-height: 1.5;
  color: var(--color-text-muted);
}

/* Image Grid Styles */
.image-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: var(--spacing-md);
  margin-top: var(--spacing-md);
  padding: 0 48px;
}

.image-item {
  transition: all 0.3s cubic-bezier(0.23, 1, 0.32, 1);
  border-radius: var(--radius-md);
  overflow: hidden;
  border: 1px solid var(--color-border);
  box-shadow: var(--shadow-soft);
}

.image-item:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-hover);
  border-color: rgba(59, 130, 246, 0.2);
}

/* Image Size Classes */
.el-image-large {
  width: 100%;
  height: 500px;
  cursor: pointer;
}

.el-image-medium {
  width: 90%;
  height: 400px;
  cursor: pointer;
}

.el-image-small {
  width: 100%;
  height: 200px;
  cursor: pointer;
}

/* Image Border Classes */
.el-image-with-border {
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
}



/* Image Hover Effects */
.el-image-with-border:hover {
  transform: scale(1.03);
  box-shadow: 0 20px 40px -10px rgba(0, 0, 0, 0.15);
  transition: all 0.3s ease;
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
  background: #fff8db;
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border);
  margin-top: var(--spacing-lg);
  transition: all 0.3s;
  position: relative;
  overflow: hidden;
}

.tips-box::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 6px;
  background: linear-gradient(to bottom, var(--color-accent), #3B82F6);
  opacity: 0;
  transition: opacity 0.3s;
}

.tips-box:hover {
  /* background: linear-gradient(to right, #FFFFFF, #EFF6FF); */
  transform: translateX(8px);
}

.tips-box:hover::before {
  opacity: 1;
}

.tips-box span {
  font-size: 0.875rem;
  line-height: 1.5;
  color: var(--color-text-muted);
}

.download-text {
  color: #275fb9;
  font-style: italic;
  text-decoration: none;
  cursor: pointer;
  transition: color 0.2s ease;
}

.download-text:hover {
  color: #3B82F6;
  text-decoration: underline;
}

.step-arrow {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 48px;
  color: var(--color-text-muted);
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.23, 1, 0.32, 1);
  margin-top: var(--spacing-lg);
}

.step-arrow:hover {
  color: var(--color-accent);
  transform: translateY(4px);
}

/* Transition Section Styles */
.transition-section {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: var(--spacing-xl) 0;
  margin: var(--spacing-xl) 0;
  position: relative;
}

.transition-section::before {
  content: '';
  position: absolute;
  top: 50%;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(to right, transparent, var(--color-border), transparent);
  transform: translateY(-50%);
  z-index: 1;
}

.transition-text {
  background: #EFF6FF; /* 淡蓝色背景 */
  padding: var(--spacing-md) var(--spacing-lg);
  font-size: 1.1rem;
  font-weight: 500;
  color: var(--color-accent);
  text-align: center;
  font-style: italic;
  z-index: 2;
  max-width: 800px;
  line-height: 1.6;
  font-family: 'Satoshi', sans-serif;
  border-radius: var(--radius-md); /* 圆角效果 */
  border: 1px solid var(--color-border); /* 边框效果 */
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
    border-bottom: 1px solid var(--color-border);
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
    border-bottom-color: var(--color-accent);
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
    letter-spacing: -1px;
  }

  .step-content {
    padding: var(--spacing-lg);
  }

  .step-image {
    margin: 0 -24px;
    padding: 20px 0;
  }

  .step-number {
    width: 50px;
    height: 50px;
    font-size: 1.2rem;
  }
}
</style>
