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

    <!-- Core Features -->
    <div class="info-card">
      <div class="card-header">
        <Icon name="star" size="md" />
        <h2>{{ $t('help.introduction.coreFeatures.title') }}</h2>
      </div>
      <div class="card-content">
        <div class="feature-grid">
          <div v-for="(feature, index) in coreFeatures" :key="index" class="feature-item">
            <div class="feature-icon">
              <Icon :name="feature.icon" size="lg" />
            </div>
            <div class="feature-text">
              <h3>{{ feature.title }}</h3>
              <p>{{ feature.description }}</p>
            </div>
          </div>
        </div>
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

    <!-- Advantages -->
    <div class="info-card">
      <div class="card-header">
        <Icon name="check" size="md" />
        <h2>{{ $t('help.introduction.advantages.title') }}</h2>
      </div>
      <div class="card-content">
        <div class="advantages-list">
          <div v-for="(advantage, index) in advantages" :key="index" class="advantage-item">
            <div class="advantage-number">{{ index + 1 }}</div>
            <div class="advantage-content">
              <h4>{{ advantage.title }}</h4>
              <p>{{ advantage.description }}</p>
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

const coreFeatures = computed(() => [
  {
    icon: 'folder',
    title: t('help.introduction.coreFeatures.projectManagement.title'),
    description: t('help.introduction.coreFeatures.projectManagement.description')
  },
  {
    icon: 'diagram',
    title: t('help.introduction.coreFeatures.dagVisualization.title'),
    description: t('help.introduction.coreFeatures.dagVisualization.description')
  },
  {
    icon: 'analysis',
    title: t('help.introduction.coreFeatures.multiPerspective.title'),
    description: t('help.introduction.coreFeatures.multiPerspective.description')
  },
  {
    icon: 'robot',
    title: t('help.introduction.coreFeatures.intelligentAgent.title'),
    description: t('help.introduction.coreFeatures.intelligentAgent.description')
  },
  {
    icon: 'services',
    title: t('help.introduction.coreFeatures.serviceManagement.title'),
    description: t('help.introduction.coreFeatures.serviceManagement.description')
  }
])

const advantages = computed(() => [
  {
    title: t('help.introduction.advantages.automation.title'),
    description: t('help.introduction.advantages.automation.description')
  },
  {
    title: t('help.introduction.advantages.integration.title'),
    description: t('help.introduction.advantages.integration.description')
  },
  {
    title: t('help.introduction.advantages.intelligent.title'),
    description: t('help.introduction.advantages.intelligent.description')
  },
  {
    title: t('help.introduction.advantages.visualization.title'),
    description: t('help.introduction.advantages.visualization.description')
  }
])

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
