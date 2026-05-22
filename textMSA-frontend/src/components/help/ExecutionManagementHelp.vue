<template>
  <div class="execution-management-help">
    <div class="page-header">
      <h1>{{ $t('help.sections.executionManagement.title') }}</h1>
      <p class="subtitle">{{ $t('help.sections.executionManagement.description') }}</p>
    </div>

    <!-- Main Features -->
    <div class="info-card">
      <div class="card-header">
        <Icon name="timeline" size="md" />
        <h2>{{ $t('help.sections.executionManagement.functions.title') }}</h2>
      </div>
      <div class="card-content">
        <div class="feature-sections">
          <div class="feature-section">
            <div class="section-icon">
              <Icon name="list" size="lg" />
            </div>
            <div class="section-content">
              <h3>{{ $t('help.sections.executionManagement.functions.executionList.title') }}</h3>
              <ul class="field-list">
                <li v-for="(item, idx) in executionListFeatures" :key="idx">
                  <Icon name="check" size="sm" />
                  <span>{{ item }}</span>
                </li>
              </ul>
            </div>
          </div>

          <div class="feature-section">
            <div class="section-icon">
              <Icon name="info" size="lg" />
            </div>
            <div class="section-content">
              <h3>{{ $t('help.sections.executionManagement.functions.executionDetails.title') }}</h3>
              <ul class="field-list">
                <li v-for="(item, idx) in executionDetailsFeatures" :key="idx">
                  <Icon name="check" size="sm" />
                  <span>{{ item }}</span>
                </li>
              </ul>
            </div>
          </div>
        </div>

        <div class="screenshot-section">
          <h4>{{ $t('help.sections.executionManagement.functions.images.list') }}</h4>
          <img :src="getImagePath('execution_management_list.png')" :alt="$t('help.sections.executionManagement.functions.images.list')" />
        </div>

        <div class="screenshot-section">
          <h4>{{ $t('help.sections.executionManagement.functions.images.detail') }}</h4>
          <img :src="getImagePath('execution_management_detail.png')" :alt="$t('help.sections.executionManagement.functions.images.detail')" />
        </div>
      </div>
    </div>

    <!-- Key Information -->
    <div class="info-card">
      <div class="card-header">
        <Icon name="info" size="md" />
        <h2>{{ $t('help.sections.executionManagement.keyInfo.title') }}</h2>
      </div>
      <div class="card-content">
        <div class="info-grid">
          <div class="info-item" v-for="(info, idx) in keyInformation" :key="idx">
            <div class="info-label">{{ info.label }}</div>
            <div class="info-value">{{ info.value }}</div>
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

const { t } = useI18n()

const executionListFeatures = computed(() => [
  t('help.sections.executionManagement.functions.executionList.feature1'),
  t('help.sections.executionManagement.functions.executionList.feature2'),
  t('help.sections.executionManagement.functions.executionList.feature3'),
  t('help.sections.executionManagement.functions.executionList.feature4')
])

const executionDetailsFeatures = computed(() => [
  t('help.sections.executionManagement.functions.executionDetails.feature1'),
  t('help.sections.executionManagement.functions.executionDetails.feature2'),
  t('help.sections.executionManagement.functions.executionDetails.feature3'),
  t('help.sections.executionManagement.functions.executionDetails.feature4')
])

const keyInformation = computed(() => [
  {
    label: t('help.sections.executionManagement.keyInfo.status.label'),
    value: t('help.sections.executionManagement.keyInfo.status.value')
  },
  {
    label: t('help.sections.executionManagement.keyInfo.time.label'),
    value: t('help.sections.executionManagement.keyInfo.time.value')
  },
  {
    label: t('help.sections.executionManagement.keyInfo.service.label'),
    value: t('help.sections.executionManagement.keyInfo.service.value')
  },
  {
    label: t('help.sections.executionManagement.keyInfo.files.label'),
    value: t('help.sections.executionManagement.keyInfo.files.value')
  }
])

function getImagePath(imageName: string): string {
  const base = import.meta.env.BASE_URL.replace(/\/$/, '')
  return `${base}/pictures/${imageName}`
}
</script>

<style scoped>
.execution-management-help {
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

.feature-sections {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xl);
  margin-bottom: var(--spacing-xl);
}

.feature-section {
  display: flex;
  gap: var(--spacing-lg);
  padding: var(--spacing-lg);
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
}

.section-icon {
  flex-shrink: 0;
  width: 56px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-primary);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
}

.section-content {
  flex: 1;
}

.section-content h3 {
  margin: 0 0 var(--spacing-md) 0;
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--text-primary);
}

.field-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.field-list li {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-sm);
  font-size: 0.875rem;
  line-height: 1.6;
  color: var(--text-secondary);
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

.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: var(--spacing-lg);
}

.info-item {
  padding: var(--spacing-lg);
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-color);
}

.info-label {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: var(--spacing-xs);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.info-value {
  font-size: 0.9375rem;
  line-height: 1.6;
  color: var(--text-primary);
}

@media (max-width: 768px) {
  .execution-management-help {
    padding: var(--spacing-md);
  }

  .feature-section {
    flex-direction: column;
  }

  .info-grid {
    grid-template-columns: 1fr;
  }
}
</style>
