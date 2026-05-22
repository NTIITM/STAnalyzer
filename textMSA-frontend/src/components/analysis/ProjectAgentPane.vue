<template>
  <div class="project-agent-pane">
    <header class="pane-header">
      <span>{{ t('app.agentConversation') }}</span>
      <span v-if="projectName" class="project-tag">#{{ projectName }}</span>
    </header>
    <main class="pane-body">
      <AgentConversationPanel
        ref="conversationRef"
        :project-id="projectId"
        :project-name="projectName"
        @conversation-start="emit('conversation-start')"
        @conversation-stop="emit('conversation-stop')"
        @dag-refresh-files="emit('dag-refresh-files')"
      />
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AgentConversationPanel from '../agent/AgentConversationPanel.vue'

const props = defineProps<{
  projectId: string | null
  projectName: string | null
}>()

const emit = defineEmits<{
  (e: 'conversation-start'): void
  (e: 'conversation-stop'): void
  (e: 'dag-refresh-files'): void
}>()

const { t } = useI18n()
const conversationRef = ref<InstanceType<typeof AgentConversationPanel> | null>(null)

function addFileToContext(fileId: string, fileName: string) {
  conversationRef.value?.addFileToContext?.(fileId, fileName)
}

function removeContextFile(fileId: string) {
  conversationRef.value?.removeContextFile?.(fileId)
}

function clearContextFiles() {
  conversationRef.value?.clearContextFiles?.()
}

defineExpose({
  addFileToContext,
  removeContextFile,
  clearContextFiles
})
</script>

<style scoped>
.project-agent-pane {
  display: flex;
  flex-direction: column;
  background: var(--bg-primary);
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-color);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
  min-height: 0;
  height: 100%;
}

.pane-header {
  padding: var(--spacing-lg);
  font-size: 14px;
  font-weight: 500;
  line-height: 1.5;
  color: rgba(0, 0, 0, 0.85);
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-secondary);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-md);
}

.project-tag {
  font-size: 12px;
  color: var(--text-secondary);
  background: var(--bg-tertiary);
  padding: 0 8px;
  border-radius: 999px;
  line-height: 22px;
}

.pane-body {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}

.pane-conversation {
  flex: 1;
  min-width: 0;
}

.conversation-job-panel {
  width: 100%;
}

@media (max-width: 1200px) {
  .pane-body {
    flex-direction: column;
  }
}
</style>
