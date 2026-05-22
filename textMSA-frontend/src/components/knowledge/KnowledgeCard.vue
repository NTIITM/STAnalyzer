<template>
  <article
    class="knowledge-card"
    :class="[{ highlighted: highlighted }, `is-${item.scope}`]"
  >
    <header class="card-header">
      <div>
        <p class="item-id">#{{ item.id }}</p>
        <h3>{{ item.title }}</h3>
        <div class="meta-chips">
          <span class="chip">{{ $t(`knowledge.scopes.${item.scope}`) }}</span>
          <span v-if="item.editedByUser" class="chip chip-warning">
            {{ $t('knowledge.flags.userEdited') }}
          </span>
        </div>
      </div>
      <div class="card-actions">
        <button
          v-if="item.scope === 'private'"
          class="action-btn"
          @click="$emit('share', item)"
          :title="$t('knowledge.actions.share')"
        >
          <Icon name="share" size="sm" />
        </button>
        <button
          v-if="item.scope !== 'system'"
          class="action-btn"
          @click="$emit('edit', item)"
          :title="$t('common.edit')"
        >
          <Icon name="edit" size="sm" />
        </button>
        <button
          v-if="item.scope !== 'system'"
          class="action-btn action-btn-danger"
          @click="$emit('delete', item)"
          :title="$t('common.delete')"
        >
          <Icon name="delete" size="sm" />
        </button>
      </div>
    </header>
    <p class="item-description">{{ item.description }}</p>
    <p class="item-relation" v-if="item.relationSummary">
      <strong>{{ $t('knowledge.labels.relation') }}:</strong>
      <span>{{ formatRelation(item.relationSummary) }}</span>
    </p>
    <footer class="card-footer">
      <div class="footer-left">
        <span>{{ $t('knowledge.labels.lastUpdated') }} {{ formatDate(item.lastModified) }}</span>
        <span>•</span>
        <span>{{ $t('knowledge.labels.source') }} {{ item.source }}</span>
      </div>
      <div class="tag-list">
        <span v-for="tag in item.tags" :key="tag" class="tag-pill">{{ tag }}</span>
      </div>
    </footer>
  </article>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import Icon from '../common/Icon.vue'
import type { KnowledgeRecord } from '../../api/knowledge'

const { t } = useI18n()

defineProps<{
  item: KnowledgeRecord
  highlighted?: boolean
}>()

defineEmits<{
  share: [item: KnowledgeRecord]
  edit: [item: KnowledgeRecord]
  delete: [item: KnowledgeRecord]
}>()

function formatDate(value?: string) {
  if (!value) return '--'
  return new Date(value).toLocaleString()
}

function formatRelation(summary?: KnowledgeRecord['relationSummary']) {
  if (!summary) return ''
  return `${summary.fromEntity} ${summary.relation} ${summary.endEntity}`.trim()
}
</script>

<style scoped>
.knowledge-card {
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: var(--spacing-lg);
  background: var(--bg-primary);
  box-shadow: var(--shadow-sm);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
  transition: all 0.2s cubic-bezier(0.645, 0.045, 0.355, 1);
}

.knowledge-card:hover {
  border-color: var(--border-hover);
  box-shadow: var(--shadow-md);
}

.knowledge-card.highlighted {
  border-color: #1890ff;
  box-shadow: 0 0 0 2px rgba(24, 144, 255, 0.2);
}

.knowledge-card.is-system {
  background: var(--bg-tertiary);
}

.card-header {
  display: flex;
  justify-content: space-between;
  gap: var(--spacing-md);
}

.item-id {
  font-size: 12px;
  font-weight: 400;
  line-height: 1.5715;
  color: rgba(0, 0, 0, 0.45);
  margin-bottom: 4px;
}

.card-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 500;
  line-height: 1.5;
  color: rgba(0, 0, 0, 0.85);
  letter-spacing: 0;
}

.card-actions {
  display: flex;
  gap: var(--spacing-xs);
}

.action-btn {
  width: 32px;
  height: 32px;
  border: 1px solid #d9d9d9;
  border-radius: var(--radius-sm);
  background: white;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s cubic-bezier(0.645, 0.045, 0.355, 1);
  color: rgba(0, 0, 0, 0.65);
}

.action-btn:hover {
  background: var(--bg-tertiary);
  border-color: #40a9ff;
  color: #1890ff;
}

.action-btn-danger {
  color: #ff4d4f;
  border-color: rgba(255, 77, 79, 0.4);
}

.action-btn-danger:hover {
  background: rgba(255, 77, 79, 0.1);
  border-color: #ff4d4f;
}

.meta-chips {
  display: flex;
  gap: var(--spacing-xs);
  flex-wrap: wrap;
  margin-top: var(--spacing-xs);
}

.chip {
  font-size: 12px;
  font-weight: 400;
  line-height: 1.5715;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(24, 144, 255, 0.12);
  color: #1890ff;
}

.chip-outline {
  border: 1px dashed rgba(24, 144, 255, 0.4);
  background: transparent;
}

.chip-warning {
  background: rgba(245, 166, 35, 0.15);
  color: #a06305;
}

.item-description {
  color: rgba(0, 0, 0, 0.65);
  font-size: 14px;
  font-weight: 400;
  line-height: 1.5715;
  margin: 0;
}

.item-relation {
  font-size: 13px;
  font-weight: 400;
  line-height: 1.5715;
  color: rgba(0, 0, 0, 0.65);
  margin: 0;
}

.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--spacing-md);
  flex-wrap: wrap;
  font-size: 12px;
  font-weight: 400;
  line-height: 1.5715;
  color: rgba(0, 0, 0, 0.45);
}

.tag-list {
  display: flex;
  gap: var(--spacing-xs);
  flex-wrap: wrap;
}

.tag-pill {
  background: var(--bg-tertiary);
  border-radius: 999px;
  padding: 2px 10px;
  font-size: 12px;
  font-weight: 400;
  line-height: 1.5715;
}
</style>
