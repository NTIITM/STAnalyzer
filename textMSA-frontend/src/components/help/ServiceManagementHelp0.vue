<template>
  <div class="service-management-help">
    <div class="page-header">
      <h1>{{ $t('help.sections.serviceManagement.title') }}</h1>
      <p class="subtitle">{{ $t('help.sections.serviceManagement.description') }}</p>
    </div>

    <!-- Service Information -->
    <div class="info-card">
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
              <Icon name="lightbulb" size="sm" />
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
    <div class="info-card">
      <div class="card-header">
        <Icon name="diagram" size="md" />
        <h2>{{ $t('help.sections.serviceManagement.relationshipGraph.title') }}</h2>
      </div>
      <div class="card-content">
        <p class="section-intro">{{ $t('help.sections.serviceManagement.relationshipGraph.description') }}</p>
        
        <div class="graph-features">
          <div class="graph-feature-item">
            <div class="feature-badge">
              <Icon name="circle" size="md" />
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
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import Icon from '../common/Icon.vue'

const { t } = useI18n()

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

function getImagePath(imageName: string): string {
  const base = import.meta.env.BASE_URL.replace(/\/$/, '')
  return `${base}/pictures/${imageName}`
}
</script>

<style scoped>
.service-management-help {
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

.section-intro {
  font-size: 0.9375rem;
  line-height: 1.6;
  color: var(--text-secondary);
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
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
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
  color: var(--text-primary);
}

.feature-list {
  margin: 0;
  padding-left: var(--spacing-lg);
  list-style: disc;
}

.feature-list li {
  font-size: 0.875rem;
  line-height: 1.6;
  color: var(--text-secondary);
  margin-bottom: var(--spacing-sm);
}

.screenshot-section {
  margin-top: var(--spacing-xl);
}

.screenshot-section h4 {
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: var(--spacing-md);
}

.screenshot-section img {
  width: 100%;
  height: auto;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
  box-shadow: var(--shadow-sm);
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
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
}

.feature-badge {
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

.feature-details h4 {
  margin: 0 0 var(--spacing-sm) 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
}

.feature-details ul {
  margin: 0;
  padding-left: var(--spacing-lg);
  list-style: disc;
}

.feature-details li {
  font-size: 0.875rem;
  line-height: 1.6;
  color: var(--text-secondary);
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
}
</style>
