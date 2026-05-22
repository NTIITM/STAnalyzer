<template>
  <div class="panel-card activity-panel">
    <div class="panel-header">
      <div>
        <p class="panel-eyebrow">{{ $t('knowledge.activity.badge') }}</p>
        <h4>{{ $t('knowledge.activity.title') }}</h4>
      </div>
      <Icon name="timeline" size="md" />
    </div>
    <ul v-if="items.length" class="activity-list">
      <li v-for="entry in items" :key="entry.id">
        <p class="activity-message">{{ entry.message }}</p>
        <small>{{ formatDate(entry.timestamp) }}</small>
      </li>
    </ul>
    <p v-else class="empty-activity">{{ $t('knowledge.activity.empty') }}</p>
  </div>
</template>

<script setup lang="ts">
import Icon from '../common/Icon.vue'

interface ActivityEntry {
  id: string
  message: string
  timestamp: string
}

defineProps<{
  items: ActivityEntry[]
}>()

function formatDate(value: string) {
  if (!value) return '--'
  return new Date(value).toLocaleString()
}
</script>

<style scoped>
.panel-card {
  background: var(--bg-primary);
  border-radius: var(--radius-lg);
  padding: var(--spacing-lg);
  box-shadow: var(--shadow-md);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.panel-eyebrow {
  font-size: 12px;
  font-weight: 400;
  line-height: 1.5715;
  text-transform: uppercase;
  color: rgba(0, 0, 0, 0.45);
  letter-spacing: 0.08em;
  margin: 0 0 4px 0;
}

.panel-header h4 {
  margin: 0;
  font-size: 16px;
  font-weight: 500;
  line-height: 1.5;
  color: rgba(0, 0, 0, 0.85);
  letter-spacing: 0;
}

.activity-list {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
  margin: 0;
  padding: 0;
}

.activity-message {
  margin: 0 0 4px 0;
  font-size: 14px;
  font-weight: 400;
  line-height: 1.5715;
  color: rgba(0, 0, 0, 0.85);
}

.activity-list small {
  font-size: 12px;
  font-weight: 400;
  line-height: 1.5715;
  color: rgba(0, 0, 0, 0.45);
}

.empty-activity {
  color: rgba(0, 0, 0, 0.45);
  font-size: 14px;
  font-weight: 400;
  line-height: 1.5715;
  margin: 0;
  text-align: center;
  padding: var(--spacing-lg);
}
</style>

