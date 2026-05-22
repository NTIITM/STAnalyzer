<template>
  <div class="knowledge-list-container">
    <div class="knowledge-toolbar">
      <div class="search-field">
        <Icon name="search" size="sm" />
        <input
          v-model.trim="keyword"
          type="text"
          class="form-input"
          :placeholder="$t('knowledge.searchPlaceholder')"
          @input="$emit('search', keyword)"
        />
      </div>
      <div class="toolbar-buttons">
        <button class="button button-secondary" @click="$emit('toggle-edited-only')">
          <Icon name="info" size="sm" />
          <span>
            {{ showEditedOnly ? $t('knowledge.filters.showAll') : $t('knowledge.filters.onlyEdited') }}
          </span>
        </button>
        <button class="button button-secondary" @click="$emit('sort-recent')">
          <Icon name="sort" size="sm" />
          <span>{{ $t('knowledge.filters.sortRecent') }}</span>
        </button>
      </div>
    </div>

    <div v-if="items.length === 0" class="empty-list">
      <Icon name="info" size="lg" />
      <p>{{ $t('knowledge.empty') }}</p>
      <button class="button button-primary" @click="$emit('create')">
        {{ $t('knowledge.actions.addFirst') }}
      </button>
    </div>
    <div v-else class="knowledge-list">
      <KnowledgeCard
        v-for="item in items"
        :key="item.id"
        :item="item"
        :highlighted="highlightedId === item.id"
        @share="$emit('share', $event)"
        @edit="$emit('edit', $event)"
        @delete="$emit('delete', $event)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import Icon from '../common/Icon.vue'
import KnowledgeCard from './KnowledgeCard.vue'
import type { KnowledgeRecord } from '../../api/knowledge'

defineProps<{
  items: KnowledgeRecord[]
  showEditedOnly: boolean
  highlightedId?: string | null
}>()

defineEmits<{
  search: [keyword: string]
  'toggle-edited-only': []
  'sort-recent': []
  create: []
  share: [item: KnowledgeRecord]
  edit: [item: KnowledgeRecord]
  delete: [item: KnowledgeRecord]
}>()

const keyword = ref('')
</script>

<style scoped>
.knowledge-list-container {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
}

.knowledge-toolbar {
  display: flex;
  justify-content: space-between;
  gap: var(--spacing-md);
  flex-wrap: wrap;
}

.search-field {
  flex: 1;
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  min-width: 200px;
}

.search-field .form-input {
  flex: 1;
}

.toolbar-buttons {
  display: flex;
  gap: var(--spacing-sm);
}

.knowledge-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.empty-list {
  padding: var(--spacing-2xl) var(--spacing-lg);
  text-align: center;
  color: rgba(0, 0, 0, 0.65);
  border: 1px dashed var(--border-color);
  border-radius: var(--radius-lg);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
  align-items: center;
}

.empty-list p {
  margin: 0;
  font-size: 14px;
  font-weight: 400;
  line-height: 1.5715;
}
</style>

