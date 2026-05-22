<template>
  <div class="spatial-transcriptomics-container">
    <!-- 控制面板 -->
    <div class="control-panel">
      <div class="panel-section">
        <h4>{{ $t('spatialTranscriptomics.dataSlice') }}</h4>
        <div class="form-group">
          <label>{{ $t('spatialTranscriptomics.sliceSelection') }}</label>
          <select v-model="selectedSlice" @change="handleSliceChange">
            <option v-for="slice in slices" :key="slice.id" :value="slice.id">
              {{ slice.name }}
            </option>
          </select>
        </div>
        <div class="form-group">
          <label>{{ $t('spatialTranscriptomics.displayMode') }}</label>
          <select v-model="displayMode">
            <option value="spots">{{ $t('spatialTranscriptomics.spots') }}</option>
            <option value="clusters">{{ $t('spatialTranscriptomics.clusters') }}</option>
            <option value="genes">{{ $t('spatialTranscriptomics.genes') }}</option>
          </select>
        </div>
      </div>
      
      <div class="panel-section">
        <h4>{{ $t('spatialTranscriptomics.visualizationParams') }}</h4>
        <div class="form-group">
          <label>{{ $t('spatialTranscriptomics.spotSize') }}</label>
          <input 
            type="range" 
            v-model.number="spotSize" 
            min="1" 
            max="10" 
            step="0.5"
            @input="updateVisualization"
          />
          <span class="form-value">{{ spotSize }}</span>
        </div>
        <div class="form-group">
          <label>{{ $t('spatialTranscriptomics.opacity') }}</label>
          <input 
            type="range" 
            v-model.number="opacity" 
            min="0" 
            max="1" 
            step="0.1"
            @input="updateVisualization"
          />
          <span class="form-value">{{ opacity.toFixed(1) }}</span>
        </div>
      </div>
      
      <div class="panel-section">
        <h4>{{ $t('spatialTranscriptomics.visualizationType') }}</h4>
        <div class="chart-type-buttons">
          <button 
            v-for="type in chartTypes" 
            :key="type.value"
            :class="{ active: chartType === type.value }"
            @click="selectChartType(type.value)"
          >
            {{ type.icon }} {{ type.label }}
          </button>
        </div>
      </div>
      
      <div class="panel-section">
        <h4>{{ $t('spatialTranscriptomics.geneFeatureSelection') }}</h4>
        <div class="form-group">
          <label>{{ $t('spatialTranscriptomics.searchGene') }}</label>
          <input 
            type="text" 
            v-model="geneSearch"
            :placeholder="$t('spatialTranscriptomics.geneSearchPlaceholder')"
            class="gene-search-input"
          />
        </div>
        <div class="selected-genes" v-if="selectedGenes.length > 0">
          <div 
            v-for="gene in selectedGenes" 
            :key="gene"
            class="gene-tag"
            @click="removeGene(gene)"
          >
            {{ gene }} ×
          </div>
        </div>
      </div>
    </div>
    
    <!-- 可视化区域 -->
    <div class="visualization-area">
      <div class="viz-header">
        <h3>{{ currentChartTitle }}</h3>
        <div class="viz-stats">
          <span class="stat-item">
            <strong>{{ $t('spatialTranscriptomics.spots') }}:</strong> {{ spotsCount }}
          </span>
          <span class="stat-item">
            <strong>{{ $t('spatialTranscriptomics.genes') }}:</strong> {{ genesCount }}
          </span>
          <span class="stat-item">
            <strong>{{ $t('spatialTranscriptomics.clusters') }}:</strong> {{ clusterCount }}
          </span>
        </div>
      </div>
      
      <div class="viz-canvas" ref="vizCanvas">
        <div v-if="!hasData" class="empty-state">
          <div class="empty-icon">🧬</div>
          <p>STAnalyzer</p>
          <p class="empty-hint">{{ $t('spatialTranscriptomics.adjustParamsHint') }}</p>
        </div>
        
        <div v-else class="chart-display">
          <canvas ref="chartCanvas" @mousemove="handleCanvasMouseMove" @click="handleCanvasClick"></canvas>
          
          <!-- Spot信息提示框 -->
          <div 
            v-if="hoveredSpot"
            class="spot-tooltip"
            :style="tooltipStyle"
          >
            <div class="tooltip-header">Spot {{ hoveredSpot.id }}</div>
            <div class="tooltip-content">
              <div class="tooltip-item">
                <span class="tooltip-label">{{ $t('spatialTranscriptomics.coordinate') }}:</span>
                <span class="tooltip-value">({{ hoveredSpot.x }}, {{ hoveredSpot.y }})</span>
              </div>
              <div class="tooltip-item">
                <span class="tooltip-label">{{ $t('spatialTranscriptomics.cluster') }}:</span>
                <span class="tooltip-value">{{ hoveredSpot.cluster }}</span>
              </div>
              <div v-if="hoveredSpot.genes" class="tooltip-item">
                <span class="tooltip-label">{{ $t('spatialTranscriptomics.topGenes') }}:</span>
                <span class="tooltip-value">{{ hoveredSpot.genes.join(', ') }}</span>
              </div>
            </div>
          </div>
          
          <!-- 聚类信息卡片 -->
          <div class="cluster-cards">
            <div 
              v-for="cluster in clusters" 
              :key="cluster.id"
              class="cluster-card"
              :class="{ selected: isClusterSelected(cluster.id) }"
              @click="toggleCluster(cluster.id)"
            >
              <div class="cluster-color" :style="{ background: cluster.color }"></div>
              <div class="cluster-info">
                <div class="cluster-name">{{ $t('spatialTranscriptomics.cluster') }} {{ cluster.id }}</div>
                <div class="cluster-count">{{ cluster.count }} {{ $t('spatialTranscriptomics.spots') }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

// Props
const props = defineProps({
  fileId: {
    type: String,
    default: ''
  }
})

// 状态变量
const selectedSlice = ref('slice1')
const displayMode = ref('spots')
const spotSize = ref(3)
const opacity = ref(0.8)
const chartType = ref('spatial')
const geneSearch = ref('')
const selectedGenes = ref([])
const hasData = ref(true)
const vizCanvas = ref(null)
const chartCanvas = ref(null)
const hoveredSpot = ref(null)
const tooltipStyle = ref({})
const spotsCount = ref(0)
const genesCount = ref(0)
const clusterCount = ref(0)

// 数据
const slices = computed(() => [
  { id: 'slice1', name: t('spatialTranscriptomics.slice1') },
  { id: 'slice2', name: t('spatialTranscriptomics.slice2') },
  { id: 'slice3', name: t('spatialTranscriptomics.slice3') }
])

const clusters = ref([])
const spots = ref([])

// 图表类型选项
const chartTypes = computed(() => [
  { value: 'spatial', label: t('spatialTranscriptomics.spatialDistribution'), icon: '🗺️' },
  { value: 'umap', label: 'UMAP', icon: '📈' },
  { value: 'violin', label: t('spatialTranscriptomics.violinPlot'), icon: '🎻' }
])

// 计算属性
const currentChartTitle = computed(() => {
  const type = chartTypes.value.find(t => t.value === chartType.value)
  return type ? `${type.icon} ${type.label}` : t('spatialTranscriptomics.spatialVisualization')
})

// 方法
function handleSliceChange() {
  generateMockData()
  renderChart()
}

function selectChartType(type) {
  chartType.value = type
  renderChart()
}

function updateVisualization() {
  renderChart()
}

function isClusterSelected(clusterId) {
  return true // 简化实现
}

function toggleCluster(clusterId) {
  renderChart()
}

function removeGene(gene) {
  const index = selectedGenes.value.indexOf(gene)
  if (index > -1) {
    selectedGenes.value.splice(index, 1)
  }
}

function handleCanvasMouseMove(event) {
  if (!chartCanvas.value) return
  
  const rect = chartCanvas.value.getBoundingClientRect()
  const x = event.clientX - rect.left
  const y = event.clientY - rect.top
  
  // 查找最近的spot
  const nearestSpot = findNearestSpot(x, y)
  if (nearestSpot) {
    hoveredSpot.value = nearestSpot
    tooltipStyle.value = {
      left: `${event.clientX + 10}px`,
      top: `${event.clientY + 10}px`
    }
  } else {
    hoveredSpot.value = null
  }
}

function handleCanvasClick(event) {
  if (hoveredSpot.value) {
    // 可以选择spot或执行其他操作
  }
}

function findNearestSpot(x, y) {
  if (spots.value.length === 0) return null
  
  let nearest = null
  let minDist = Infinity
  
  spots.value.forEach(spot => {
    const dist = Math.sqrt(Math.pow(spot.x - x, 2) + Math.pow(spot.y - y, 2))
    if (dist < minDist && dist < 10) {
      minDist = dist
      nearest = spot
    }
  })
  
  return nearest
}

function generateMockData() {
  const colors = [
    '#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A',
    '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E2'
  ]
  
  // 生成模拟clusters
  const numClusters = 6
  clusters.value = Array.from({ length: numClusters }, (_, i) => ({
    id: String(i + 1),
    color: colors[i % colors.length],
    count: Math.floor(Math.random() * 500) + 100
  }))
  
  // 生成模拟spots
  spots.value = []
  clusters.value.forEach((cluster, clusterIdx) => {
    for (let i = 0; i < cluster.count; i++) {
      spots.value.push({
        id: `spot_${clusterIdx}_${i}`,
        x: Math.random() * 800,
        y: Math.random() * 600,
        cluster: cluster.id,
        genes: ['Gene1', 'Gene2', 'Gene3'].slice(0, Math.floor(Math.random() * 3) + 1)
      })
    }
  })
  
  spotsCount.value = spots.value.length
  genesCount.value = 2000
  clusterCount.value = clusters.value.length
}

function renderChart() {
  if (!chartCanvas.value || !vizCanvas.value) return
  
  const canvas = chartCanvas.value
  const ctx = canvas.getContext('2d')
  const rect = vizCanvas.value.getBoundingClientRect()
  const width = rect.width || 800
  const height = rect.height - 100 || 600
  
  canvas.width = width
  canvas.height = height
  
  // 清空画布
  ctx.clearRect(0, 0, width, height)
  
  // 根据chartType渲染不同的图表
  switch (chartType.value) {
    case 'spatial':
      renderSpatialPlot(ctx, width, height)
      break
    case 'umap':
      renderUMAPPlot(ctx, width, height)
      break
    case 'violin':
      renderViolinPlot(ctx, width, height)
      break
  }
}

function renderSpatialPlot(ctx, width, height) {
  // 缩放spots到canvas大小
  const scaleX = width / 800
  const scaleY = height / 600
  
  clusters.value.forEach(cluster => {
    const clusterSpots = spots.value.filter(s => s.cluster === cluster.id)
    
    clusterSpots.forEach(spot => {
      const x = spot.x * scaleX
      const y = spot.y * scaleY
      
      ctx.fillStyle = cluster.color + Math.floor(opacity.value * 255).toString(16).padStart(2, '0')
      ctx.beginPath()
      ctx.arc(x, y, spotSize.value, 0, Math.PI * 2)
      ctx.fill()
    })
  })
}

function renderUMAPPlot(ctx, width, height) {
  clusters.value.forEach(cluster => {
    const clusterSpots = spots.value.filter(s => s.cluster === cluster.id)
    const centerX = Math.random() * (width - 200) + 100
    const centerY = Math.random() * (height - 200) + 100
    
    clusterSpots.forEach(spot => {
      const angle = Math.random() * Math.PI * 2
      const radius = Math.random() * 50 + Math.random() * 50
      const x = centerX + Math.cos(angle) * radius
      const y = centerY + Math.sin(angle) * radius
      
      ctx.fillStyle = cluster.color + Math.floor(opacity.value * 255).toString(16).padStart(2, '0')
      ctx.beginPath()
      ctx.arc(x, y, spotSize.value, 0, Math.PI * 2)
      ctx.fill()
    })
  })
}

function renderViolinPlot(ctx, width, height) {
  const padding = 50
  const plotWidth = (width - padding * 2) / clusters.value.length
  
  clusters.value.forEach((cluster, idx) => {
    const centerX = padding + idx * plotWidth + plotWidth / 2
    const maxWidth = plotWidth * 0.6
    
    ctx.fillStyle = cluster.color + Math.floor(opacity.value * 255).toString(16).padStart(2, '0')
    ctx.beginPath()
    
    for (let i = 0; i <= 100; i++) {
      const y = (height - padding * 2) * (i / 100) + padding
      const widthAtY = maxWidth * Math.sin((i / 100) * Math.PI) * 0.5
      
      if (i === 0) {
        ctx.moveTo(centerX - widthAtY, y)
      } else {
        ctx.lineTo(centerX - widthAtY, y)
      }
    }
    
    for (let i = 100; i >= 0; i--) {
      const y = (height - padding * 2) * (i / 100) + padding
      const widthAtY = maxWidth * Math.sin((i / 100) * Math.PI) * 0.5
      ctx.lineTo(centerX + widthAtY, y)
    }
    
    ctx.closePath()
    ctx.fill()
    
    ctx.strokeStyle = '#666'
    ctx.lineWidth = 1
    ctx.beginPath()
    ctx.moveTo(centerX, padding)
    ctx.lineTo(centerX, height - padding)
    ctx.stroke()
  })
}

onMounted(() => {
  generateMockData()
  setTimeout(() => {
    renderChart()
  }, 100)
  
  window.addEventListener('resize', () => {
    renderChart()
  })
})
</script>

<style scoped>
.spatial-transcriptomics-container {
  display: flex;
  width: 100%;
  height: 100%;
  gap: 1rem;
  overflow: hidden;
}

.control-panel {
  width: 280px;
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(10px);
  border-radius: 8px;
  padding: 1.5rem;
  overflow-y: auto;
  border: 1px solid rgba(200, 200, 210, 0.4);
}

.panel-section {
  margin-bottom: 1.5rem;
}

.panel-section h4 {
  margin: 0 0 1rem 0;
  font-size: 0.95rem;
  font-weight: 600;
  color: rgba(60, 60, 70, 0.9);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.form-group {
  margin-bottom: 1rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  font-size: 0.85rem;
  color: rgba(100, 100, 110, 0.8);
  font-weight: 500;
}

.form-group input,
.form-group select {
  width: 100%;
  padding: 0.5rem;
  border: 1px solid rgba(200, 200, 210, 0.4);
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.8);
  font-size: 0.9rem;
  color: rgba(60, 60, 70, 0.9);
  transition: all 0.2s ease;
}

.form-group input:focus,
.form-group select:focus {
  outline: none;
  border-color: rgba(100, 150, 220, 0.6);
  background: white;
}

.form-group input[type="range"] {
  padding: 0;
}

.form-value {
  display: inline-block;
  margin-left: 0.5rem;
  font-size: 0.85rem;
  color: rgba(100, 100, 110, 0.8);
}

.gene-search-input {
  width: 100%;
}

.selected-genes {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.5rem;
}

.gene-tag {
  padding: 0.25rem 0.5rem;
  background: rgba(100, 150, 220, 0.1);
  border: 1px solid rgba(100, 150, 220, 0.3);
  border-radius: 4px;
  font-size: 0.8rem;
  cursor: pointer;
  transition: all 0.2s ease;
}

.gene-tag:hover {
  background: rgba(100, 150, 220, 0.2);
}

.chart-type-buttons {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.chart-type-buttons button {
  padding: 0.75rem;
  border: 1px solid rgba(200, 200, 210, 0.4);
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.6);
  color: rgba(60, 60, 70, 0.9);
  font-size: 0.85rem;
  cursor: pointer;
  transition: all 0.2s ease;
  text-align: left;
}

.chart-type-buttons button:hover {
  background: rgba(100, 150, 220, 0.1);
  border-color: rgba(100, 150, 220, 0.4);
}

.chart-type-buttons button.active {
  background: rgba(100, 150, 220, 0.6);
  color: white;
  border-color: rgba(100, 150, 220, 0.8);
  font-weight: 500;
}

.visualization-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(10px);
  border-radius: 8px;
  border: 1px solid rgba(200, 200, 210, 0.4);
  overflow: hidden;
}

.viz-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.5rem;
  border-bottom: 1px solid rgba(200, 200, 210, 0.4);
}

.viz-header h3 {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 600;
  color: rgba(60, 60, 70, 0.9);
}

.viz-stats {
  display: flex;
  gap: 1.5rem;
}

.stat-item {
  font-size: 0.85rem;
  color: rgba(100, 100, 110, 0.8);
}

.stat-item strong {
  color: rgba(60, 60, 70, 0.9);
  font-weight: 600;
}

.viz-canvas {
  flex: 1;
  position: relative;
  overflow: hidden;
}

.empty-state {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: rgba(100, 100, 110, 0.7);
}

.empty-icon {
  font-size: 4rem;
  margin-bottom: 1rem;
  opacity: 0.5;
}

.empty-hint {
  font-size: 0.85rem;
  margin-top: 0.5rem;
  opacity: 0.6;
}

.chart-display {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.chart-display canvas {
  flex: 1;
  width: 100%;
  cursor: crosshair;
}

.spot-tooltip {
  position: fixed;
  background: rgba(40, 40, 50, 0.95);
  color: white;
  padding: 0.75rem 1rem;
  border-radius: 8px;
  font-size: 0.85rem;
  pointer-events: none;
  z-index: 10000;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
  max-width: 250px;
}

.tooltip-header {
  font-weight: 600;
  margin-bottom: 0.5rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.2);
}

.tooltip-content {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.tooltip-item {
  display: flex;
  gap: 0.5rem;
}

.tooltip-label {
  color: rgba(255, 255, 255, 0.7);
}

.tooltip-value {
  color: rgba(100, 200, 255, 0.9);
}

.cluster-cards {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  padding: 1rem;
  border-top: 1px solid rgba(200, 200, 210, 0.4);
  background: rgba(245, 245, 250, 0.5);
  max-height: 150px;
  overflow-y: auto;
}

.cluster-card {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  background: rgba(255, 255, 255, 0.8);
  border: 1px solid rgba(200, 200, 210, 0.4);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.cluster-card:hover {
  background: white;
  border-color: rgba(100, 150, 220, 0.4);
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.cluster-card.selected {
  background: rgba(100, 150, 220, 0.1);
  border-color: rgba(100, 150, 220, 0.6);
  border-width: 2px;
}

.cluster-color {
  width: 16px;
  height: 16px;
  border-radius: 3px;
  flex-shrink: 0;
}

.cluster-info {
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
}

.cluster-name {
  font-size: 0.85rem;
  font-weight: 500;
  color: rgba(60, 60, 70, 0.9);
}

.cluster-count {
  font-size: 0.75rem;
  color: rgba(100, 100, 110, 0.7);
}
</style>

