<template>
  <div class="analysis-page-help">
    <div class="page-header">
      <h1>{{ $t('help.sections.analysisPage.title') }}</h1>
      <p class="subtitle">{{ $t('help.sections.analysisPage.description') }}</p>
    </div>

    <!-- Page Structure Overview -->
    <div class="structure-card">
      <div class="card-header">
        <Icon name="layout" size="md" />
        <h2>{{ $t('help.sections.analysisPage.pageStructure.title') }}</h2>
      </div>
      <div class="card-content">
        <div class="structure-diagram">
          <div class="structure-item left-panel">
            <Icon name="folder" size="lg" />
            <h3>{{ $t('help.sections.analysisPage.leftPanel.title') }}</h3>
            <p>{{ $t('help.sections.analysisPage.leftPanel.description') }}</p>
          </div>
          <div class="structure-item middle-panel">
            <Icon name="diagram" size="lg" />
            <h3>{{ $t('help.sections.analysisPage.middleContent.title') }}</h3>
            <p>{{ $t('help.sections.analysisPage.middleContent.description') }}</p>
          </div>
          <div class="structure-item right-panel">
            <Icon name="info" size="lg" />
            <h3>{{ $t('help.sections.analysisPage.rightPanel.title') }}</h3>
            <p>{{ $t('help.sections.analysisPage.rightPanel.description') }}</p>
          </div>
        </div>
        <div class="overview-image">
          <el-image
            :src="getImagePath('analysis_page_intro_0.png')"
            :alt="$t('help.sections.analysisPage.overviewImage')"
            fit="contain"
            :preview-src-list="[getImagePath('analysis_page_intro_0.png')]"
            :preview-teleported="true"
            :scale="0.7"
            style="width: 100%; height: 500px; cursor: pointer; border-radius: var(--radius-md); box-shadow: var(--shadow-sm); border: 1px solid var(--border-color);"
          />
        </div>
      </div>
    </div>

    <!-- Left Panel Details -->
    <div class="feature-card">
      <div class="card-header">
        <Icon name="folder" size="md" />
        <h2>{{ $t('help.sections.analysisPage.leftPanel.title') }}</h2>
      </div>
      <div class="card-content">
        <div class="feature-sections">
          <div class="feature-section">
            <h3>{{ $t('help.sections.analysisPage.leftPanel.projectList.title') }}</h3>
            <div class="field-list">
              <div class="field-item" v-for="(item, idx) in leftPanelProjectFeatures" :key="idx">
                <Icon name="check" size="sm" />
                <span>{{ item }}</span>
              </div>
            </div>
          </div>
          <div class="feature-section">
            <h3>{{ $t('help.sections.analysisPage.leftPanel.fileList.title') }}</h3>
            <div class="field-list">
              <div class="field-item" v-for="(item, idx) in leftPanelFileFeatures" :key="idx">
                <Icon name="check" size="sm" />
                <span>{{ item }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Middle Content Details -->
    <div class="feature-card">
      <div class="card-header">
        <Icon name="diagram" size="md" />
        <h2>{{ $t('help.sections.analysisPage.middleContent.title') }}</h2>
      </div>
      <div class="card-content">
        <div class="feature-sections">
          <div class="feature-section">
            <h3>{{ $t('help.sections.analysisPage.middleContent.dagView.title') }}</h3>
            <p>{{ $t('help.sections.analysisPage.middleContent.dagView.description') }}</p>
            <div class="dag-elements">
              <div class="element-card">
                <div class="element-icon nodes">
                  <Icon name="circle" size="md" />
                </div>
                <div class="element-info">
                  <h4>{{ $t('help.sections.analysisPage.middleContent.dagView.elements.nodes') }}</h4>
                  <ul>
                    <li v-for="(detail, idx) in dagNodeDetails" :key="idx">{{ detail }}</li>
                  </ul>
                </div>
              </div>
              <div class="element-card">
                <div class="element-icon edges">
                  <Icon name="arrow-right" size="md" />
                </div>
                <div class="element-info">
                  <h4>{{ $t('help.sections.analysisPage.middleContent.dagView.elements.edges') }}</h4>
                  <ul>
                    <li v-for="(detail, idx) in dagEdgeDetails" :key="idx">{{ detail }}</li>
                  </ul>
                </div>
              </div>
              <div class="element-card">
                <div class="element-icon files">
                  <Icon name="file" size="md" />
                </div>
                <div class="element-info">
                  <h4>{{ $t('help.sections.analysisPage.middleContent.dagView.elements.files') }}</h4>
                  <p>{{ $t('help.sections.analysisPage.middleContent.dagView.elements.filesDesc') }}</p>
                </div>
              </div>
            </div>
          </div>
          <div class="feature-section">
            <h3>{{ $t('help.sections.analysisPage.middleContent.dataVisualization.title') }}</h3>
            <div class="field-list">
              <div class="field-item" v-for="(item, idx) in dataVisualizationFeatures" :key="idx">
                <Icon name="check" size="sm" />
                <span>{{ item }}</span>
              </div>
            </div>
            <div class="feature-image">
              <el-image
                :src="getImagePath('file_preview.png')"
                :alt="$t('help.sections.analysisPage.middleContent.dataVisualization.image')"
                fit="contain"
                :preview-src-list="[getImagePath('file_preview.png')]"
                :preview-teleported="true"
                :scale="0.7"
                style="width: 100%; height: 500px; cursor: pointer; border-radius: var(--radius-md); box-shadow: var(--shadow-sm); border: 1px solid var(--border-color);"
              />
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Right Panel Details -->
    <div class="feature-card">
      <div class="card-header">
        <Icon name="info" size="md" />
        <h2>{{ $t('help.sections.analysisPage.rightPanel.title') }}</h2>
      </div>
      <div class="card-content">
        <div class="field-list">
          <div class="field-item" v-for="(item, idx) in rightPanelFeatures" :key="idx">
            <Icon name="check" size="sm" />
            <span>{{ item }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Manual Execution -->
    <div class="feature-card">
      <div class="card-header">
        <Icon name="play" size="md" />
        <h2>{{ $t('help.sections.analysisPage.manualExecution.title') }}</h2>
      </div>
      <div class="card-content">
        <p class="section-intro">{{ $t('help.sections.analysisPage.manualExecution.description') }}</p>
        <div class="execution-steps">
          <div class="execution-step" v-for="(step, idx) in manualExecutionSteps" :key="idx">
            <div class="step-badge">{{ idx + 1 }}</div>
            <div class="step-details">
              <h4>{{ step.title }}</h4>
              <p v-html="step.description"></p>
              <div v-if="step.image" class="step-screenshot">
                <el-image
                  :src="getImagePath(step.image)"
                  :alt="step.title"
                  fit="contain"
                  :preview-src-list="[getImagePath(step.image)]"
                  :preview-teleported="true"
                  :scale="0.7"
                  style="width: 100%; height: 500px; cursor: pointer; border-radius: var(--radius-md); box-shadow: var(--shadow-sm); border: 1px solid var(--border-color);"
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Natural Language Execution -->
    <div class="feature-card">
      <div class="card-header">
        <Icon name="robot" size="md" />
        <h2>Natural Language Execution</h2>
      </div>
      <div class="card-content">
        <p class="section-intro">{{ $t('help.sections.gettingStarted.description') }}</p>
        <div class="execution-steps">
          <div class="execution-step" v-for="(step, idx) in naturalLanguageExecutionSteps" :key="idx">
            <div class="step-badge">{{ idx + 1 }}</div>
            <div class="step-details">
              <h4>{{ step.title }}</h4>
              <p v-if="step.isPrompt"><span class="prompt-label">Prompt:</span> {{ step.description }}</p>
              <p v-else>{{ step.description }}</p>
              
              <!-- Single Image -->
              <div v-if="step.image && step.isSingleImage" class="step-screenshot">
                <el-image
                  :src="getImagePath(step.image)"
                  :alt="step.title"
                  fit="contain"
                  :preview-src-list="[getImagePath(step.image)]"
                  :preview-teleported="true"
                  :scale="0.7"
                  style="width: 100%; height: 500px; cursor: pointer; border-radius: var(--radius-md); box-shadow: var(--shadow-sm); border: 1px solid var(--border-color);"
                />
              </div>
              
              <!-- Multiple Images -->
              <div v-else-if="step.images" class="step-screenshot">
                <div class="image-grid">
                  <div v-for="(img, imgIdx) in step.images" :key="imgIdx" class="image-item">
                    <el-image
                      :src="getImagePath(img)"
                      :alt="step.title"
                      fit="contain"
                      :preview-src-list="[getImagePath(img)]"
                      :preview-teleported="true"
                      :scale="0.7"
                      style="width: 100%; height: 200px; cursor: pointer; border-radius: var(--radius-md); box-shadow: var(--shadow-sm); border: 1px solid var(--border-color);"
                    />
                  </div>
                </div>
              </div>
              
              <!-- Table -->
              <div v-else-if="step.hasTable" class="step-screenshot">
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
                      <tr v-for="(item, itemIdx) in validationTableData" :key="itemIdx">
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
                        style="width: 100%; height: 400px; cursor: pointer; border-radius: var(--radius-md); box-shadow: var(--shadow-sm); border: 1px solid var(--border-color);"
                      />
                    </div>
                    
                    <!-- Sub Step Multiple Images -->
                    <div v-else-if="subStep.images" class="step-screenshot">
                      <div class="image-grid">
                        <div v-for="(img, imgIdx) in subStep.images" :key="imgIdx" class="image-item">
                          <el-image
                            :src="getImagePath(img)"
                            :alt="subStep.title"
                            fit="contain"
                            :preview-src-list="[getImagePath(img)]"
                            :preview-teleported="true"
                            :scale="0.7"
                            style="width: 100%; height: 200px; cursor: pointer; border-radius: var(--radius-md); box-shadow: var(--shadow-sm); border: 1px solid var(--border-color);"
                          />
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import Icon from '../common/Icon.vue'
import { ElImage } from 'element-plus'

const { t } = useI18n()

const leftPanelProjectFeatures = computed(() => [
  t('help.sections.analysisPage.leftPanel.projectList.feature1'),
  t('help.sections.analysisPage.leftPanel.projectList.feature2'),
  t('help.sections.analysisPage.leftPanel.projectList.feature3')
])

const leftPanelFileFeatures = computed(() => [
  t('help.sections.analysisPage.leftPanel.fileList.feature1'),
  t('help.sections.analysisPage.leftPanel.fileList.feature2'),
  t('help.sections.analysisPage.leftPanel.fileList.feature3')
])

const dagNodeDetails = computed(() => [
  t('help.sections.analysisPage.middleContent.dagView.elements.nodesDetail1'),
  t('help.sections.analysisPage.middleContent.dagView.elements.nodesDetail2'),
  t('help.sections.analysisPage.middleContent.dagView.elements.nodesDetail3')
])

const dagEdgeDetails = computed(() => [
  t('help.sections.analysisPage.middleContent.dagView.elements.edgesDetail1'),
  t('help.sections.analysisPage.middleContent.dagView.elements.edgesDetail2')
])

const dataVisualizationFeatures = computed(() => [
  t('help.sections.analysisPage.middleContent.dataVisualization.feature1'),
  t('help.sections.analysisPage.middleContent.dataVisualization.feature2'),
  t('help.sections.analysisPage.middleContent.dataVisualization.feature3')
])

const rightPanelFeatures = computed(() => [
  t('help.sections.analysisPage.rightPanel.feature1'),
  t('help.sections.analysisPage.rightPanel.feature2'),
  t('help.sections.analysisPage.rightPanel.feature3')
])

const manualExecutionSteps = computed(() => [
  {
    title: t('help.sections.analysisPage.manualExecution.step1.title'),
    description: t('help.sections.analysisPage.manualExecution.step1.description'),
    image: 'analysis_page_manual0.png'
  },
  {
    title: t('help.sections.analysisPage.manualExecution.step2.title') + ' & ' + t('help.sections.analysisPage.manualExecution.step3.title'),
    description: t('help.sections.analysisPage.manualExecution.step2.description') + '<br> ' + t('help.sections.analysisPage.manualExecution.step3.description'),
    image: 'analysis_page_manual1.png'
  },
  // {
  //   title: t('help.sections.analysisPage.manualExecution.step3.title'),
  //   description: t('help.sections.analysisPage.manualExecution.step3.description'),
  //   image: 'manual_execution_running.png'
  // },
  {
    title: t('help.sections.analysisPage.manualExecution.step4.title'),
    description: t('help.sections.analysisPage.manualExecution.step4.description'),
    image: 'analysis_page_manual2.png'
  }
])

const naturalLanguageExecutionSteps = computed(() => [
  {
    title: t('help.sections.gettingStarted.steps.askAgent.title'),
    description: t('help.sections.gettingStarted.steps.askAgent.description'),
    image: 'send_query_0.png',
    isSingleImage: true
  },
  {
    title: t('help.sections.gettingStarted.steps.analysis.title'),
    description: t('help.sections.gettingStarted.steps.analysis.description'),
    images: ['analysis_0.png', 'analysis_1.png', 'analysis_2.png', 'analysis_3.png']
  },
  {
    title: t('help.sections.gettingStarted.steps.analysis2.title'),
    description: t('help.sections.gettingStarted.steps.analysis2.description'),
    image: 'analysis2_0.png',
    isSingleImage: true,
    isPrompt: true
  },
  {
    title: t('help.sections.gettingStarted.steps.illustrations.title'),
    description: t('help.sections.gettingStarted.steps.illustrations.description'),
    images: ['illustrations_0.png', 'illustrations_1.png'],
    isPrompt: true
  },
  {
    title: t('help.sections.gettingStarted.steps.validation.title'),
    description: t('help.sections.gettingStarted.steps.validation.description'),
    hasTable: true,
    isPrompt: true
  },
  {
    title: 'Explore Valuable Research Directions',
    description: 'Utilize the platform to explore valuable research directions, guide meaningful biological discoveries, and avoid blind large-scale analysis. Perform cell communication analysis among the 9 spatial domains, identify the two spatial domains with the greatest research significance and the cell interactions between them, and provide an explanatory description as well as a summary report.',
    images: ['research_direction_0.png', 'research_direction_1.png'],
    isPrompt: true
  },
  {
    title: 'Multi-Agent Collaboration for Accelerated Biological Discoveries',
    description: 'The current dataset possesses a truly accurate resolution of subcellular physical coordinates. Our previous analysis has successfully identified a crucial physical communication boundary: Domain 0 (the core of adaptive immunity dominated by T cells) and Domain 3 (the immunosuppressive barrier dominated by Tregs). Please focus on the interface where physical contact occurs between Domain 0 and Domain 3 (the boundary). From the perspective of subcellular analysis, deduce and extract potential new biological discoveries. Please conduct a deep analysis using an explainable thought chain (Chain of Thought).',
    hasSubSteps: true,
    subSteps: [
      {
        title: 'Automatic Code Analysis',
        image: 'code_analysis_0.png'
      },
      {
        title: 'Mechanism-Based Reasoning',
        description: 'Synthesize all available evidence from file metadata, decision history, and established knowledge base to automatically propose deep, mechanism-based reasoning results (each hypothesis has a traceable chain of thought):',
        images: ['reasoning_0.png', 'reasoning_1.png', 'reasoning_2.png']
      },
      {
        title: 'Summary Report',
        description: 'Provide a summary report of the novel biological phenomena discovered:',
        images: ['summary_0.png', 'summary_1.png', 'summary_2.png']
      }
    ],
    isPrompt: true
  }
])

const validationTableData = computed(() => [
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
])

function getImagePath(imageName: string): string {
  const base = import.meta.env.BASE_URL.replace(/\/$/, '')
  return `${base}/pictures/${imageName}`
}
</script>

<style scoped>
.analysis-page-help {
  padding: var(--spacing-xl);
  max-width: 1200px;
  margin: 0 auto;
  background: var(--bg-secondary);
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
  max-width: 800px;
  margin: 0 auto;
}

.structure-card,
.feature-card {
  background: var(--bg-primary);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-color);
  margin-bottom: var(--spacing-lg);
  overflow: hidden;
  box-shadow: var(--shadow-sm);
}

.card-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  padding: var(--spacing-lg);
  background: var(--bg-tertiary);
  border-bottom: 1px solid var(--border-color);
}

.card-header h2 {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 600;
  color: var(--text-primary);
}

.card-content {
  padding: var(--spacing-xl);
}

.structure-diagram {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--spacing-lg);
  margin-bottom: var(--spacing-xl);
}

.structure-item {
  padding: var(--spacing-lg);
  border-radius: var(--radius-md);
  text-align: center;
  transition: all 0.2s ease;
  border: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  align-items: center;
}

.structure-item.left-panel {
  background: var(--bg-secondary);
}

.structure-item.middle-panel {
  background: var(--bg-secondary);
}

.structure-item.right-panel {
  background: var(--bg-secondary);
}

.structure-item:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.structure-item h3 {
  margin: var(--spacing-md) 0 var(--spacing-xs) 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
}

.structure-item p {
  margin: 0;
  font-size: 0.875rem;
  color: var(--text-secondary);
  line-height: 1.5;
}

.overview-image {
  text-align: center;
}

.overview-image img {
  max-width: 100%;
  height: auto;
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--border-color);
}

.feature-sections {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xl);
}

.feature-section h3 {
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: var(--spacing-md);
}

.feature-section p {
  font-size: 0.9375rem;
  line-height: 1.6;
  color: var(--text-secondary);
  margin-bottom: var(--spacing-md);
}

.field-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.field-item {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--bg-secondary);
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-color);
}

.field-item span {
  font-size: 0.875rem;
  line-height: 1.5;
  color: var(--text-secondary);
}

.dag-elements {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: var(--spacing-lg);
  margin-top: var(--spacing-lg);
}

.element-card {
  padding: var(--spacing-lg);
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
}

.element-icon {
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-md);
  margin-bottom: var(--spacing-md);
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
}

.element-info h4 {
  margin: 0 0 var(--spacing-sm) 0;
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--text-primary);
}

.element-info ul {
  margin: 0;
  padding-left: var(--spacing-lg);
  list-style: disc;
}

.element-info li {
  font-size: 0.875rem;
  line-height: 1.5;
  color: var(--text-secondary);
  margin-bottom: var(--spacing-xs);
}

.element-info p {
  margin: 0;
  font-size: 0.875rem;
  line-height: 1.5;
  color: var(--text-secondary);
}

.feature-image {
  margin-top: var(--spacing-lg);
  text-align: center;
}

.feature-image img {
  max-width: 100%;
  height: auto;
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--border-color);
}

.section-intro {
  font-size: 0.9375rem;
  line-height: 1.6;
  color: var(--text-secondary);
  margin-bottom: var(--spacing-xl);
}

.execution-steps {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xl);
}

.execution-step {
  display: flex;
  gap: var(--spacing-lg);
}

.step-badge {
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--accent-primary);
  color: white;
  border-radius: 50%;
  font-weight: 700;
  font-size: 1.125rem;
}

.step-details {
  flex: 1;
}

.step-details h4 {
  margin: 0 0 var(--spacing-xs) 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
}

.step-details p {
  margin: 0 0 var(--spacing-md) 0;
  font-size: 0.875rem;
  line-height: 1.5;
  color: var(--text-secondary);
}

.step-screenshot {
  margin-top: var(--spacing-md);
}

.step-screenshot img {
  max-width: 100%;
  height: auto;
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--border-color);
}

@media (max-width: 768px) {
  .analysis-page-help {
    padding: var(--spacing-md);
  }

  .structure-diagram {
    grid-template-columns: 1fr;
  }

  .dag-elements {
    grid-template-columns: 1fr;
  }
  
  .image-grid {
    grid-template-columns: 1fr;
  }
  
  .sub-step {
    flex-direction: column;
  }
  
  .sub-step-badge {
    margin-bottom: var(--spacing-sm);
  }
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
  width: 30px;
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #8fbaeb;
  color: white;
  border-radius: var(--radius-sm);
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
  color: var(--text-primary);
}

.sub-step-content p {
  margin: 0 0 var(--spacing-md) 0;
  font-size: 0.875rem;
  line-height: 1.5;
  color: var(--text-secondary);
}

/* Prompt Label Styles */
.step-details p .prompt-label {
  font-weight: bold;
  font-style: italic;
  font-size: 1.1rem;
  color: var(--text-secondary);
  margin-right: var(--spacing-sm);
  display: inline-block;
}

/* Image Grid Styles */
.image-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: var(--spacing-md);
  margin-top: var(--spacing-md);
}

.image-item {
  transition: transform 0.2s ease;
}

.image-item:hover {
  transform: translateY(-2px);
}

/* Step Card Styles */
.step-card {
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
  margin-bottom: var(--spacing-lg);
  overflow: hidden;
  box-shadow: var(--shadow-sm);
}

.step-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  padding: var(--spacing-lg);
  background: var(--bg-tertiary);
  border-bottom: 1px solid var(--border-color);
}

.step-header h3 {
  margin: 0;
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--text-primary);
}

.step-content {
  padding: var(--spacing-lg);
}

.step-description {
  font-size: 0.9375rem;
  line-height: 1.6;
  color: var(--text-secondary);
  margin-bottom: var(--spacing-md);
}

.key-points {
  margin: var(--spacing-md) 0;
}

.key-points h4 {
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: var(--spacing-sm);
}

.key-points ul {
  margin: 0;
  padding-left: var(--spacing-md);
  list-style-type: disc;
}

.key-points li {
  font-size: 0.875rem;
  line-height: 1.5;
  color: var(--text-secondary);
  margin-bottom: var(--spacing-xs);
}

.step-image {
  margin: var(--spacing-md) 0;
}

.single-image-container {
  height: 400px;
  border-radius: var(--radius-md);
  overflow: hidden;
  border: 1px solid var(--border-color);
  box-shadow: var(--shadow-sm);
}

.tips-box {
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: var(--spacing-md);
  margin-top: var(--spacing-md);
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-sm);
}

.tips-box span {
  font-size: 0.875rem;
  line-height: 1.5;
  color: var(--text-secondary);
}

.step-table {
  margin: var(--spacing-md) 0;
}

.table-responsive {
  overflow-x: auto;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.data-table th,
.data-table td {
  padding: var(--spacing-sm) var(--spacing-md);
  text-align: left;
  border-bottom: 1px solid var(--border-color);
}

.data-table th {
  background: var(--bg-tertiary);
  font-weight: 600;
  color: var(--text-primary);
}

.data-table tr:hover {
  background: var(--bg-secondary);
}

.cluster-cell {
  font-weight: 600;
  color: var(--text-primary);
  width: 10%;
}

.domain-cell {
  font-weight: 500;
  color: var(--text-primary);
  width: 30%;
}

.evidence-cell {
  color: var(--text-secondary);
  line-height: 1.4;
  width: 60%;
}
</style>
