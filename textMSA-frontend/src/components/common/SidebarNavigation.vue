<template>
  <div class="sidebar" :class="{ 'collapsed': !sidebarExpanded }">
    <div class="sidebar-header">
      <button class="toggle-btn" @click="toggleSidebar">
        <Icon :name="sidebarExpanded ? 'arrow-right' : 'arrow-left'" size="md" />
      </button>
      <h3 v-if="sidebarExpanded">{{ title }}</h3>
    </div>
    <nav class="sidebar-nav">
      <ul>
        <li 
          v-for="(step, index) in steps" 
          :key="index"
          :class="{ 'active': currentStep === index }"
          @click="scrollToStep(index)"
        >
          <div class="nav-item">
            <div class="step-number-sidebar">{{ index + 1 }}</div>
            <span v-if="sidebarExpanded">{{ step.title }}</span>
          </div>
        </li>
      </ul>
    </nav>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import Icon from './Icon.vue'

// Props
const props = defineProps<{
  steps: Array<{
    title: string
  }>
  title?: string
  sectionPrefix?: string
  storageKey?: string
}>()

// Default values
const title = props.title || 'Navigation'
const sectionPrefix = props.sectionPrefix || 'section-' // Default prefix for section IDs
const storageKey = props.storageKey || 'sidebarExpanded' // Key for local storage

// Emits
const emit = defineEmits(['update:currentStep'])

// Sidebar state
const getInitialSidebarState = (): boolean => {
  const savedState = localStorage.getItem(storageKey)
  return savedState ? JSON.parse(savedState) : true
}

const sidebarExpanded = ref<boolean>(getInitialSidebarState())

// Current active step
const currentStep = ref<number>(0)
// Flag to control whether scroll event can update current step
const allowScrollUpdate = ref<boolean>(true)

// Toggle sidebar
const toggleSidebar = () => {
  sidebarExpanded.value = !sidebarExpanded.value
  localStorage.setItem(storageKey, JSON.stringify(sidebarExpanded.value))
}

// Scroll to step
const scrollToStep = (index: number) => {
  const element = document.getElementById(`${sectionPrefix}${index}`)
  if (element) {
    // Disable scroll update during navigation
    allowScrollUpdate.value = false
    // Scroll to target section
    element.scrollIntoView({ behavior: 'smooth' })
    // Update current step immediately
    currentStep.value = index
    // Emit event to parent
    emit('update:currentStep', index)
    // Re-enable scroll update after a delay (allowing scroll to complete)
    setTimeout(() => {
      allowScrollUpdate.value = true
    }, 1000) // Adjust delay as needed
  }
}

// Throttle function to limit the frequency of function calls
const throttle = (func: Function, delay: number) => {
  let lastCall = 0
  return function(...args: any[]) {
    const now = Date.now()
    if (now - lastCall < delay) {
      return
    }
    lastCall = now
    return func(...args)
  }
}

// Update current step based on scroll position
const updateCurrentStep = throttle(() => {
  // Skip update if scroll update is disabled (during navigation)
  if (!allowScrollUpdate.value) {
    return
  }
  
  const steps = props.steps
  let current = 0

  const viewportHeight = window.innerHeight

  for (let i = steps.length - 1; i >= 0; i--) {
    const element = document.getElementById(`${sectionPrefix}${i}`)
    if (element) {
      const rect = element.getBoundingClientRect()
      // 核心逻辑：判断元素的顶部是否在视口的顶部到中间区域
      // 这样可以防止滚动过快时，两个步骤交替闪烁
      if (rect.top <= viewportHeight * 0.6) { // 60%视口高度处即触发
        current = i
        break // 找到第一个符合条件的步骤后就退出循环
      }
    }
  }
  if (currentStep.value !== current) {
    currentStep.value = current
    // Emit event to parent
    emit('update:currentStep', current)
  }
}, 500) // 500ms的节流延迟

// Watch sidebar state change
watch(sidebarExpanded, (newValue) => {
  localStorage.setItem(storageKey, JSON.stringify(newValue))
})

// Lifecycle hooks
onMounted(() => {
  // Add scroll event listener to window
  window.addEventListener('scroll', updateCurrentStep, { capture: true, passive: false })
  // Initialize once
  updateCurrentStep()
})

onUnmounted(() => {
  // Remove scroll event listener from window
  window.removeEventListener('scroll', updateCurrentStep, { capture: true })
})
</script>

<style scoped>
/* Sidebar Styles */
.sidebar {
  width: 250px;
  background: var(--color-card);
  border-left: 1px solid var(--color-border);
  transition: width 0.3s ease;
  position: sticky;
  top: 0;
  height: 100vh;
  overflow-y: hidden;
  overflow-x: hidden;
  box-shadow: var(--shadow-soft);
}

.sidebar.collapsed {
  width: 60px;
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-lg);
  border-bottom: 1px solid var(--color-border);
  background: rgba(255, 255, 255, 0.6);
}

.sidebar-header h3 {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--color-text-dark);
  transition: opacity 0.3s ease;
  font-family: 'Clash Display', sans-serif;
}

.sidebar.collapsed .sidebar-header h3 {
  opacity: 0;
  width: 0;
  overflow: hidden;
}

.toggle-btn {
  background: none;
  border: none;
  color: var(--color-text-dark);
  cursor: pointer;
  padding: var(--spacing-xs);
  border-radius: var(--radius-sm);
  transition: background-color 0.2s ease;
}

.toggle-btn:hover {
  background: rgba(59, 130, 246, 0.1);
}

.sidebar-nav ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.sidebar-nav li {
  margin: 0;
  padding: 0;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  padding: var(--spacing-md) var(--spacing-lg);
  color: var(--color-text-muted);
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.23, 1, 0.32, 1);
  border-right: 3px solid transparent;
  justify-content: flex-start;
}

.step-number-sidebar {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-accent-light);
  color: #275fb9;
  border-radius: 50%;
  font-size: 1.2rem;
  font-weight: 600;
  flex-shrink: 0;
  box-shadow: 0 4px 15px -5px var(--color-accent);
}

.nav-item:hover {
  background: rgba(59, 130, 246, 0.05);
  color: var(--color-text-dark);
  transform: translateX(-4px);
}

.sidebar-nav li.active .nav-item {
  background: rgba(59, 130, 246, 0.05);
  color: var(--color-accent);
  border-right-color: var(--color-accent);
  font-weight: 500;
  transform: translateX(-4px);
}

.sidebar.collapsed .nav-item span {
  opacity: 0;
  width: 0;
  overflow: hidden;
  transition: opacity 0.3s ease, width 0.3s ease;
}

.sidebar.collapsed .nav-item {
  justify-content: center;
  padding: var(--spacing-md);
  border-right: none;
}

.sidebar.collapsed .step-number-sidebar {
  display: flex;
}

/* Responsive Design */
@media (max-width: 768px) {
  .sidebar {
    width: 100%;
    height: auto;
    position: relative;
    border-left: none;
    border-bottom: 1px solid var(--color-border);
  }

  .sidebar.collapsed {
    width: 100%;
  }
}
</style>