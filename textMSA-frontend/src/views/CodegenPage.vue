<template>
  <div class="codegen-page">
    <CodegenWorkspaceLayout
      :project-id="projectId"
      :service-id="serviceId"
      @error="handleError"
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import CodegenWorkspaceLayout from '../components/codegen/CodegenWorkspaceLayout.vue'

const route = useRoute()

// Extract projectId and serviceId from route query params
const projectId = computed(() => (route.query.projectId as string) || null)
const serviceId = computed(() => (route.query.serviceId as string) || null)

function handleError(message: string) {
  // Emit error to global notification system if available
  if (window.showMessage) {
    window.showMessage.error(message)
  } else {
    console.error('Codegen error:', message)
  }
}
</script>

<style scoped>
.codegen-page {
  width: 100%;
  height: 100%;
  overflow: hidden;
}
</style>


