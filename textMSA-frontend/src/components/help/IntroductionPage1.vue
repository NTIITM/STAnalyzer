<template>
  <div class="intro-page">
    <div class="page-header">
      <h1>{{ $t('help.introduction.title') }}</h1>
      <p class="subtitle">{{ $t('help.introduction.subtitle') }}</p>
    </div>

    <!-- What is STAnalyzer -->
    <div class="info-card">
      <div class="card-header">
        <Icon name="info" size="md" />
        <h2>{{ $t('help.introduction.whatIs.title') }}</h2>
      </div>
      <div class="card-content">
        <p>{{ $t('help.introduction.whatIs.description') }}</p>
      </div>
    </div>

    <!-- System Architecture -->
    <div class="info-card">
      <div class="card-header">
        <Icon name="diagram" size="md" />
        <h2>{{ $t('help.introduction.architecture.title') }}</h2>
      </div>
      <div class="card-content">
        <div class="architecture-diagram">
          <el-image
            :src="getImagePath('framework.png')"
            :alt="$t('help.introduction.frameworkImage')"
            fit="contain"
            :preview-src-list="[getImagePath('framework.png')]"
            :preview-teleported="true"
            :scale="1"
            style="width: 70%; cursor: pointer;"
          />
        </div>
      </div>
    </div>

    <!-- Overview & Core Concept -->
    <div class="info-card">
      <div class="card-header">
        <Icon name="info" size="md" />
        <h2>Overview & Core Concept</h2>
      </div>
      <div class="card-content">
        <div class="overview-list">
          <div class="overview-item">
            <h3>System Identity</h3>
            <p>STAnalyzer (Spatial Transcriptomics Analyzer by Multi-agent Analysis System)</p>
          </div>
          <div class="overview-item">
            <h3>Primary Function</h3>
            <p>End-to-end automated analysis lifecycle for Spatial Transcriptomics (ST) data</p>
          </div>
          <div class="overview-item">
            <h3>Architectural Paradigm</h3>
            <p>Collaborative Intelligence Architecture</p>
          </div>
          <div class="overview-item">
            <h3>Mission</h3>
            <p>Bridge the gap between complex raw data and verifiable biological insights by eliminating manual coordination bottlenecks</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Key Technological Features -->
    <div class="info-card">
      <div class="card-header">
        <Icon name="analysis" size="md" />
        <h2>Key Technological Features</h2>
      </div>
      <div class="card-content">
        <div class="feature-grid">
          <div class="feature-item">
            <div class="feature-icon">
              <Icon name="message-square" size="lg" />
            </div>
            <div class="feature-text">
              <h3>Intent-Driven Orchestration</h3>
              <p>Natural Language Interface (NLI) converts user queries into rigorous bioinformatics workflows</p>
            </div>
          </div>
          <div class="feature-item">
            <div class="feature-icon">
              <Icon name="refresh-cw" size="lg" />
            </div>
            <div class="feature-text">
              <h3>Multi-Modal Self-Optimization</h3>
              <p>Closed-loop validation combining visual patterns (e.g., UMAP) and statistical metrics</p>
            </div>
          </div>
          <div class="feature-item">
            <div class="feature-icon">
              <Icon name="check-circle" size="lg" />
            </div>
            <div class="feature-text">
              <h3>Evidence-Based Cross-Validation</h3>
              <p>Anchors data-driven correlations in causal biological explanations via literature and structured databases (UniProt, PubMed)</p>
            </div>
          </div>
          <div class="feature-item">
            <div class="feature-icon">
              <Icon name="git-branch" size="lg" />
            </div>
            <div class="feature-text">
              <h3>Full Traceability</h3>
              <p>DAG (Directed Acyclic Graph) visualization of execution flow and data lineage</p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Functional Modules -->
    <div class="info-card">
      <div class="card-header">
        <Icon name="diagram" size="md" />
        <h2>Functional Modules</h2>
      </div>
      <div class="card-content">
        <div class="feature-grid">
          <div class="feature-item">
            <div class="feature-icon">
              <Icon name="database" size="lg" />
            </div>
            <div class="feature-text">
              <h3>Data Processing</h3>
              <p>Multi-format support (.h5ad, .csv, .png, etc.), Context integration, DAG auto-refresh</p>
            </div>
          </div>
          <div class="feature-item">
            <div class="feature-icon">
              <Icon name="robot" size="lg" />
            </div>
            <div class="feature-text">
              <h3>Autonomous Analysis</h3>
              <p>Natural language dialogue with Agents, Automated service execution, and Result interpretation</p>
            </div>
          </div>
          <div class="feature-item">
            <div class="feature-icon">
              <Icon name="file-text" size="lg" />
            </div>
            <div class="feature-text">
              <h3>Report Generation</h3>
              <p>Markdown-formatted output with Key Findings, Biological Interpretation, and Research Conclusions</p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- User Interface & Experience -->
    <div class="info-card">
      <div class="card-header">
        <Icon name="check" size="md" />
        <h2>User Interface & Experience</h2>
      </div>
      <div class="card-content">
        <div class="feature-grid">

          <div class="feature-item">
            <div class="feature-icon">
              <Icon name="bar-chart-3" size="lg" />
            </div>
            <div class="feature-text">
              <h3>Interactive Visualization</h3>
              <p>Tree-structured workflow display, Full-screen image preview, and Interactive data lists</p>
            </div>
          </div>
          <div class="feature-item">
            <div class="feature-icon">
              <Icon name="settings" size="lg" />
            </div>
            <div class="feature-text">
              <h3>Service Management</h3>
              <p>"Private/Public/System" service classification, Real-time status synchronization, and Parameter validation</p>
            </div>
          </div>
          <div class="feature-item">
            <div class="feature-icon">
              <Icon name="activity" size="lg" />
            </div>
            <div class="feature-text">
              <h3>Execution Monitoring</h3>
              <p>Comprehensive log records, State tracking (Success/Failure), and Audit trails (User ID, Timestamps)</p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Core Advantages -->
    <div class="info-card">
      <div class="card-header">
        <Icon name="star" size="md" />
        <h2>Core Advantages</h2>
      </div>
      <div class="card-content">
        <div class="advantages-list">
          <div class="advantage-item">
            <div class="advantage-number">1</div>
            <div class="advantage-content">
              <h4>Low Technical Barrier</h4>
              <p>Democratizes access to complex ST data analysis</p>
            </div>
          </div>
          <div class="advantage-item">
            <div class="advantage-number">2</div>
            <div class="advantage-content">
              <h4>High Efficiency</h4>
              <p>Accelerates the conversion of data into discoveries</p>
            </div>
          </div>
          <div class="advantage-item">
            <div class="advantage-number">3</div>
            <div class="advantage-content">
              <h4>Reproducibility</h4>
              <p>Persistent project saving and full input/output archiving (via UUID)</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import Icon from '../common/Icon.vue'
import { ElImage } from 'element-plus'

const { t } = useI18n()

function getImagePath(imageName: string): string {
  const base = import.meta.env.BASE_URL.replace(/\/$/, '')
  return `${base}/pictures/${imageName}`
}
</script>

<style scoped>
.intro-page {
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
}

.info-card {
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

.card-content p {
  font-size: 0.9375rem;
  line-height: 1.6;
  color: var(--text-secondary);
  margin: 0;
}

/* Feature Grid */
.feature-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: var(--spacing-lg);
}

.feature-item {
  display: flex;
  gap: var(--spacing-md);
  padding: var(--spacing-lg);
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
  transition: all 0.2s ease;
}

.feature-item:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}

.feature-icon {
  flex-shrink: 0;
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-primary);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
}

.feature-text h3 {
  margin: 0 0 var(--spacing-xs) 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
}

.feature-text p {
  margin: 0;
  font-size: 0.875rem;
  line-height: 1.5;
  color: var(--text-secondary);
}

/* Overview List */
.overview-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
}

.overview-item {
  padding: var(--spacing-lg);
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
}

.overview-item h3 {
  margin: 0 0 var(--spacing-xs) 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
}

.overview-item p {
  margin: 0;
  font-size: 0.875rem;
  line-height: 1.5;
  color: var(--text-secondary);
}

/* Architecture Diagram */
.architecture-diagram {
  text-align: center;
}

.architecture-diagram img {
  max-width: 100%;
  height: auto;
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--border-color);
}

.architecture-diagram :deep(.el-image) {
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--border-color);
}

/* Advantages List */
.advantages-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
}

.advantage-item {
  display: flex;
  gap: var(--spacing-lg);
  padding: var(--spacing-lg);
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
}

.advantage-number {
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

.advantage-content h4 {
  margin: 0 0 var(--spacing-xs) 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
}

.advantage-content p {
  margin: 0;
  font-size: 0.875rem;
  line-height: 1.5;
  color: var(--text-secondary);
}

@media (max-width: 768px) {
  .intro-page {
    padding: var(--spacing-md);
  }

  .page-header h1 {
    font-size: 1.5rem;
  }

  .feature-grid {
    grid-template-columns: 1fr;
  }
}
</style>
