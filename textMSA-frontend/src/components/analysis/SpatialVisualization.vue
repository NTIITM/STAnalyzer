<template>
  <div class="spatial-visualization-container">
    <!-- 控制面板 -->
    <div class="control-panel">

      <div class="panel-section">
        <h4>{{ t('spatial.geneExpression') }}</h4>
        <div class="form-group">
          <label>{{ t('spatial.selectGene') }}:</label>
          <div class="gene-autocomplete-container">
            <input 
              type="text" 
              v-model="geneSearch"
              :placeholder="t('spatial.geneSearchPlaceholder')"
              class="gene-autocomplete-input"
              @input="handleGeneInput"
              @focus="showSuggestions = true"
              @blur="handleBlur"
              @keydown.enter="handleEnterKey"
              @keydown.arrow-down.prevent="selectNext"
              @keydown.arrow-up.prevent="selectPrev"
            />
            <!-- 自动补全下拉列表 -->
            <div 
              v-if="showSuggestions && filteredGenes.length > 0" 
              class="gene-suggestions"
            >
              <div 
                v-for="(gene, index) in filteredGenes" 
                :key="gene"
                class="gene-suggestion-item"
                :class="{ active: selectedIndex === index }"
                @click="selectGene(gene)"
                @mouseenter="selectedIndex = index"
              >
                {{ gene }}
              </div>
            </div>
            <div 
              v-if="showSuggestions && filteredGenes.length === 0 && geneSearch.trim()"
              class="gene-suggestions"
            >
              <div class="gene-suggestion-item gene-suggestion-empty">
                {{ t('spatial.noGenesFound') }}
              </div>
            </div>
          </div>
          <div v-if="selectedGene" class="selected-gene-info">
            <div class="gene-chip">
              <span class="gene-name">{{ selectedGene }}</span>
              <button class="gene-chip-close" @click="clearGene">×</button>
            </div>
            <div class="gene-expression-info">
              <span class="info-label">{{ t('spatial.expressionRange') }}:</span>
              <span class="info-value">{{ minExpression.toFixed(2) }} - {{ maxExpression.toFixed(2) }}</span>
            </div>
          </div>
        </div>
      </div>
      
      <div class="panel-section">
        <h4>{{ t('spatial.grouping.title') }}</h4>
        <div class="form-group">
          <label>{{ t('spatial.grouping.attribute') }}:</label>
          <select 
            v-model="selectedGroupAttribute" 
            class="form-select"
            @change="onGroupAttributeChange"
          >
            <option value="">{{ t('spatial.grouping.selectPlaceholder') }}</option>
            <option 
              v-for="attr in availableGroupAttributes" 
              :key="attr" 
              :value="attr"
            >
              {{ attr }}
            </option>
          </select>
        </div>
      </div>

      <div class="panel-section">
        <h4>{{ t('spatial.visualizationParams') }}</h4>
        <div class="form-group">
          <label>{{ t('spatial.spotSize') }}:</label>
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
          <label>{{ t('spatial.spotOpacity') }}:</label>
          <input 
            type="range" 
            v-model.number="spotOpacity" 
            min="0" 
            max="1" 
            step="0.1"
            @input="updateVisualization"
          />
          <span class="form-value">{{ spotOpacity.toFixed(1) }}</span>
        </div>
        <div class="form-group">
          <label>{{ t('spatial.imageOpacity') }}:</label>
          <input 
            type="range" 
            v-model.number="imageOpacity" 
            min="0" 
            max="1" 
            step="0.1"
            @input="updateVisualization"
          />
          <span class="form-value">{{ imageOpacity.toFixed(1) }}</span>
        </div>
      </div>

      <div class="panel-section">
        <h4>{{ t('spatial.displayOptions') }}</h4>
        <div class="form-group">
          <label>
            <input type="checkbox" v-model="showSpots" @change="updateVisualization" />
            {{ t('spatial.showSpots') }}
          </label>
        </div>
        <div class="form-group">
          <label>
            <input type="checkbox" v-model="showStatistics" @change="updateVisualization" />
            {{ t('spatial.showStatistics') }}
          </label>
        </div>
      </div>
    </div>
    
    <!-- 可视化区域 -->
    <div class="visualization-area">
      <div class="viz-header">
        <h3>{{ t('spatial.spatialTranscriptomics') }}</h3>
        <div class="viz-stats">
          <span class="stat-item">
            <strong>Spots:</strong> {{ spotsCount }}
          </span>
          <span v-if="selectedGene" class="stat-item">
            <strong>{{ t('spatial.currentGene') }}:</strong> {{ selectedGene }}
          </span>
        </div>
      </div>
      
      <div class="viz-canvas-wrapper" ref="vizCanvasWrapper">
        <div v-if="loading" class="loading-state">
          <div class="spinner"></div>
          <p>{{ t('spatial.loadingData') }}</p>
        </div>
        
        <div v-else-if="error" class="error-state">
          <div class="error-icon">⚠️</div>
          <p>{{ error }}</p>
        </div>
        
        <div v-else class="viz-canvas-container">
          <img 
            v-if="sliceImageUrl" 
            :src="sliceImageUrl" 
            :alt="t('spatialTranscriptomics.sliceImage')"
            class="slice-background"
            :style="{ opacity: imageOpacity }"
            @load="onImageLoad"
          />
          
          <!-- No Image 提示 -->
          <div v-if="!hasImage" class="no-image-notice">
            <div class="notice-icon">🖼️</div>
            <p class="notice-text">No image available</p>
            <p class="notice-subtext">Displaying spots data only</p>
          </div>
          
          <canvas 
            ref="spotsCanvas" 
            class="spots-canvas"
            @mousemove="handleCanvasMouseMove"
            @mouseleave="handleCanvasMouseLeave"
            @click="handleCanvasClick"
          ></canvas>
          
          <!-- 颜色图例 -->
          <div v-if="selectedGene" class="color-scale">
            <div class="color-scale-title">{{ t('spatialTranscriptomics.expression') }}</div>
            <div class="color-scale-gradient"></div>
            <div class="color-scale-labels">
              <span>{{ minExpression.toFixed(2) }}</span>
              <span>{{ maxExpression.toFixed(2) }}</span>
            </div>
          </div>
          
          <!-- Spot信息提示框 -->
          <div 
            v-if="hoveredSpot"
            class="spot-tooltip spot-tooltip-fixed"
          >
            <div class="tooltip-header">
              <span class="tooltip-icon">📍</span>
              <span class="tooltip-title">Spot {{ hoveredSpot.id }}</span>
            </div>
            <div class="tooltip-content">
              <div class="tooltip-item">
                <span class="tooltip-label">{{ t('spatialTranscriptomics.position') }}:</span>
                <span class="tooltip-value">({{ hoveredSpot.x.toFixed(2) }}, {{ hoveredSpot.y.toFixed(2) }})</span>
              </div>
              <div v-if="hasClusterLabel && hoveredSpot.clusterLabel !== undefined && hoveredSpot.clusterLabel !== null && hoveredSpot.clusterLabel !== ''" class="tooltip-item">
                <span class="tooltip-label">Cluster:</span>
                <span class="tooltip-value">{{ hoveredSpot.clusterLabel }}</span>
                <span v-if="hoveredClusterSpots.length > 1" class="tooltip-value" style="margin-left: 0.5rem; color: rgba(100, 100, 110, 0.7);">
                  {{ t('spatialTranscriptomics.totalSpots', { count: hoveredClusterSpots.length }) }}
                </span>
              </div>
              <div v-if="selectedGene && hoveredSpot.geneExpression !== undefined" class="tooltip-item">
                <span class="tooltip-label">{{ selectedGene }} {{ t('spatialTranscriptomics.expressionValue') }}:</span>
                <span class="tooltip-value">{{ hoveredSpot.geneExpression.toFixed(2) }}</span>
              </div>
              <div v-if="hasClusterLabel && hoveredClusterSpots.length > 1 && hoveredClusterSpots.length <= 10" class="tooltip-item" style="margin-top: 0.5rem; padding-top: 0.5rem; border-top: 1px solid rgba(200, 200, 210, 0.3);">
                <span class="tooltip-label" style="width: 100%; margin-bottom: 0.25rem;">{{ t('spatialTranscriptomics.sameClusterSpots') }}:</span>
                <div style="display: flex; flex-wrap: wrap; gap: 0.25rem;">
                  <span 
                    v-for="spot in hoveredClusterSpots" 
                    :key="spot.id"
                    class="spot-id-tag"
                  >
                    {{ spot.id }}
                  </span>
                </div>
              </div>
              <div v-if="hasClusterLabel && hoveredClusterSpots.length > 10" class="tooltip-item" style="margin-top: 0.5rem; padding-top: 0.5rem; border-top: 1px solid rgba(200, 200, 210, 0.3);">
                <span class="tooltip-label">{{ t('spatialTranscriptomics.sameClusterSpots') }}:</span>
                <span class="tooltip-value">{{ t('spatialTranscriptomics.showingFirst10') }}</span>
                <div style="display: flex; flex-wrap: wrap; gap: 0.25rem; margin-top: 0.25rem;">
                  <span 
                    v-for="spot in hoveredClusterSpots.slice(0, 10)" 
                    :key="spot.id"
                    class="spot-id-tag"
                  >
                    {{ spot.id }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <!-- 统计分析面板 -->
      <div v-if="showStatistics && selectedGene" class="statistics-panel" :class="{ collapsed: statisticsCollapsed }">
        <div class="statistics-header" @click="statisticsCollapsed = !statisticsCollapsed">
          <h4>{{ t('spatial.statisticalAnalysis') }}</h4>
          <button class="collapse-btn">
            {{ statisticsCollapsed ? '▲' : '▼' }}
          </button>
        </div>
        <div v-if="!statisticsCollapsed" class="statistics-content">
          <div class="statistics-grid">
            <!-- 表达分布直方图 -->
            <div class="chart-card">
              <h5>{{ t('spatial.expressionDistribution') }}</h5>
              <div ref="histogramChart" class="chart-container"></div>
            </div>
            
            <!-- 箱线图 -->
            <div v-if="hasClusterLabel" class="chart-card">
              <h5>{{ t('spatial.expressionByCluster') }}</h5>
              <div ref="boxplotChart" class="chart-container"></div>
            </div>
            
            <!-- Cluster 饼图 -->
            <div v-if="hasClusterLabel" class="chart-card">
              <h5>{{ t('spatial.clusterDistribution') }}</h5>
              <div ref="pieChart" class="chart-container"></div>
            </div>
            
            <!-- Cluster 柱状图 -->
            <div v-if="hasClusterLabel" class="chart-card">
              <h5>{{ t('spatial.clusterStatistics') }}</h5>
              <div ref="barChart" class="chart-container"></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { getSpatialSliceImage, getSpatialSpots, getGeneExpression, getGeneList } from '../../api/spatial'
import { useSpatialStatistics } from '../../composables/useSpatialStatistics'

const { t } = useI18n()

const {
  renderHistogram,
  renderBoxplot,
  renderPieChart,
  renderBarChart,
  resizeAll: resizeStatistics,
  disposeAll: disposeStatistics
} = useSpatialStatistics()

// Props
const props = defineProps({
  fileId: {
    type: String,
    default: ''
  }
})

// 状态变量
const spotSize = ref(3)
const spotOpacity = ref(0.8)
const imageOpacity = ref(0.7)
const showSpots = ref(true)
const showStatistics = ref(true)
const statisticsCollapsed = ref(false)
const loading = ref(false)
const error = ref('')
const spots = ref([])
const sliceImageUrl = ref('')
const imageWidth = ref(0)
const imageHeight = ref(0)
const spotsCount = ref(0)
const hasImage = ref(false) // 标记是否成功加载图像

// 基因搜索相关
const geneSearch = ref('')
const selectedGene = ref('')
const geneExpressionData = ref(new Map()) // Map<spotId, expressionValue>
const minExpression = ref(0)
const maxExpression = ref(0)
const allGenes = ref([]) // 所有可用基因列表
const filteredGenes = ref([]) // 过滤后的基因列表
const showSuggestions = ref(false)
const selectedIndex = ref(-1)

// Canvas相关
const vizCanvasWrapper = ref(null)
const spotsCanvas = ref(null)
let canvasContext = null
let imageElement = null
let imageLoaded = false

const histogramChart = ref(null)
const boxplotChart = ref(null)
const pieChart = ref(null)
const barChart = ref(null)

// 交互相关
const hoveredSpot = ref(null)
const hoveredClusterSpots = ref([]) // 当前悬浮的cluster的所有spots
const scaleFactor = ref(1)
const offsetX = ref(0)
const offsetY = ref(0)

// Cluster相关
const hasClusterLabel = ref(false) // 是否包含clusterLabel字段
const clusterColorMap = ref(new Map()) // Map<clusterLabel, color>
const clusterSpotsMap = ref(new Map()) // Map<clusterLabel, spots[]>
const selectedGroupAttribute = ref('') // 用户选择的分组属性
const availableGroupAttributes = ref([]) // 可用的group属性列表

// 方法
/**
 * 加载默认切片数据
 */
async function loadData() {
  const targetFileId = props.fileId
  if (!targetFileId) {
    error.value = t('spatial.missingFileId')
    return
  }
  
  loading.value = true
  error.value = ''
  
  try {
    // 首先加载切片图像（不指定sliceId，使用默认切片）
    try {
      const sliceImage = await getSpatialSliceImage(targetFileId)
      
      // 检查返回的图像数据是否为空对象
      if (!sliceImage || Object.keys(sliceImage).length === 0 || !sliceImage.imageUrl) {
        console.warn('No image data available')
        sliceImageUrl.value = ''
        imageWidth.value = 0
        imageHeight.value = 0
        hasImage.value = false
        // 如果没有图像，直接返回，不请求 spots 数据
        return
      }
      
      sliceImageUrl.value = sliceImage.imageUrl
      imageWidth.value = sliceImage.width || 0
      imageHeight.value = sliceImage.height || 0
      hasImage.value = true
    } catch (imgErr) {
      console.warn('Failed to load slice image:', imgErr)
      sliceImageUrl.value = ''
      imageWidth.value = 0
      imageHeight.value = 0
      hasImage.value = false
      // 图像请求失败，直接返回，不请求 spots 数据
      return
    }
    
    // 只有在有图像的情况下才加载 Spots 数据
    const spotsData = await getSpatialSpots(targetFileId)
    spots.value = spotsData.spots || []
    spotsCount.value = spots.value.length
    
    // 处理clusterLabel数据
    processClusterLabels()
    
    // 加载基因列表
    await loadGeneList()
    
    // 等待DOM更新后渲染
    await nextTick()
    renderVisualization()
  } catch (err) {
    error.value = t('analysis.errors.loadDataFailed', { error: err?.message || t('app.unknownError') })
  } finally {
    loading.value = false
  }
}
/**
 * 提取可用的group属性
 */
function extractGroupAttributes() {
  const firstSpot = spots.value[0]
  if (!firstSpot || !firstSpot.group || typeof firstSpot.group !== 'object') {
    availableGroupAttributes.value = []
    return
  }

  // 从第一个spot的group对象中提取所有属性键
  const attributes = Object.keys(firstSpot.group)
  availableGroupAttributes.value = attributes

  // 如果有可用属性且未选择，自动选择第一个
  if (attributes.length > 0 && !selectedGroupAttribute.value) {
    // 优先选择常见的聚类字段
    const preferredFields = ['leiden', 'louvain', 'cluster', 'cell_type', 'region']
    const preferred = preferredFields.find(field => attributes.includes(field))
    selectedGroupAttribute.value = preferred || attributes[0]
  }
}

/**
 * 处理clusterLabel数据
 */
function processClusterLabels() {
  const firstSpot = spots.value[0]
  if (!firstSpot) {
    hasClusterLabel.value = false
    return
  }

  // 提取可用的group属性
  extractGroupAttributes()

  // 如果没有选择分组属性，不进行分组
  if (!selectedGroupAttribute.value) {
    hasClusterLabel.value = false
    clusterColorMap.value.clear()
    clusterSpotsMap.value.clear()
    return
  }

  // 检查group对象是否存在且包含选中的属性
  const groupObj = firstSpot.group
  if (!groupObj || typeof groupObj !== 'object' || !selectedGroupAttribute.value || !(selectedGroupAttribute.value in groupObj)) {
    hasClusterLabel.value = false
    clusterColorMap.value.clear()
    clusterSpotsMap.value.clear()
    return
  }

  hasClusterLabel.value = true

  // 从group对象中读取选中的属性值作为clusterLabel
  spots.value.forEach(spot => {
    const spotGroup = spot.group
    if (spotGroup && typeof spotGroup === 'object' && selectedGroupAttribute.value && selectedGroupAttribute.value in spotGroup) {
      const value = spotGroup[selectedGroupAttribute.value]
      spot.clusterLabel = value !== undefined && value !== null ? String(value) : null
    } else {
      spot.clusterLabel = null
    }
  })

  // 统计唯一 label
  const uniqueLabels = new Set()
  spots.value.forEach(spot => {
    if (spot.clusterLabel !== undefined && spot.clusterLabel !== null && spot.clusterLabel !== '') {
      uniqueLabels.add(String(spot.clusterLabel))
    }
  })

  // 为每个 label 分配颜色并分组
  const labels = Array.from(uniqueLabels).sort()
  clusterColorMap.value.clear()
  clusterSpotsMap.value.clear()

  labels.forEach((label, index) => {
    clusterColorMap.value.set(label, getClusterColorByIndex(index))
    clusterSpotsMap.value.set(label, [])
  })

  spots.value.forEach(spot => {
    const label = spot.clusterLabel ? String(spot.clusterLabel) : null
    if (label && clusterSpotsMap.value.has(label)) {
      clusterSpotsMap.value.get(label).push(spot)
    }
  })
}

/**
 * 当用户更改分组属性时调用
 */
function onGroupAttributeChange() {
  processClusterLabels()
  renderVisualization()
  if (selectedGene.value) {
    renderStatisticsCharts()
  }
}

/**
 * 根据索引获取cluster颜色
 * 使用预定义的调色板，确保颜色区分度高
 */
function getClusterColorByIndex(index) {
  // 使用20种区分度高的颜色
  const colorPalette = [
    '#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8',
    '#F7DC6F', '#BB8FCE', '#85C1E2', '#F8B739', '#52BE80',
    '#EC7063', '#5DADE2', '#F1948A', '#82E0AA', '#F4D03F',
    '#A569BD', '#5DADE2', '#F39C12', '#1ABC9C', '#E74C3C'
  ]
  return colorPalette[index % colorPalette.length]
}

/**
 * 获取spot的颜色
 * 优先级：基因表达颜色 > cluster颜色 > 默认颜色
 */
function getSpotColor(spot) {
  // 如果选择了基因且有表达值，使用基因表达颜色
  if (selectedGene.value && spot.geneExpression !== undefined) {
    const normalizedValue = (spot.geneExpression - minExpression.value) / 
      (maxExpression.value - minExpression.value || 1)
    return getExpressionColor(normalizedValue)
  }
  
  // 如果有clusterLabel，使用cluster颜色
  if (hasClusterLabel.value && spot.clusterLabel !== undefined && spot.clusterLabel !== null && spot.clusterLabel !== '') {
    const label = String(spot.clusterLabel)
    const color = clusterColorMap.value.get(label)
    if (color) {
      // 将hex颜色转换为rgba格式，应用透明度
      const r = parseInt(color.slice(1, 3), 16)
      const g = parseInt(color.slice(3, 5), 16)
      const b = parseInt(color.slice(5, 7), 16)
      return `rgba(${r}, ${g}, ${b}, ${spotOpacity.value})`
    }
  }
  
  // 默认颜色 - 淡蓝色
  return `rgba(100, 150, 220, ${spotOpacity.value})`
}

/**
 * 加载基因列表
 */
async function loadGeneList() {
  const targetFileId = props.fileId
  if (!targetFileId) return
  
  try {
    const genes = await getGeneList(targetFileId)
    allGenes.value = genes || []
    filteredGenes.value = allGenes.value.slice(0, 10) // 初始显示前10个
  } catch (err) {
    // 加载基因列表失败，保持空列表
  }
}

/**
 * 处理基因输入
 */
function handleGeneInput() {
  const query = geneSearch.value.trim().toLowerCase()
  selectedIndex.value = -1
  
  if (query === '') {
    filteredGenes.value = allGenes.value.slice(0, 10)
  } else {
    // 过滤基因列表
    filteredGenes.value = allGenes.value
      .filter(gene => gene.toLowerCase().includes(query))
      .slice(0, 10) // 最多显示10个结果
  }
  
  showSuggestions.value = true
}

/**
 * 选择基因
 */
function selectGene(geneName) {
  geneSearch.value = geneName
  selectedGene.value = geneName
  showSuggestions.value = false
  selectedIndex.value = -1
  
  // 自动加载基因表达数据
  loadGeneExpression(geneName)
}

/**
 * 处理输入框失焦
 */
function handleBlur() {
  // 延迟隐藏，以便点击选项时可以触发
  setTimeout(() => {
    showSuggestions.value = false
  }, 200)
}

/**
 * 处理Enter键
 */
function handleEnterKey() {
  if (selectedIndex.value >= 0 && filteredGenes.value[selectedIndex.value]) {
    selectGene(filteredGenes.value[selectedIndex.value])
  } else if (filteredGenes.value.length === 1) {
    selectGene(filteredGenes.value[0])
  } else if (geneSearch.value.trim() && allGenes.value.includes(geneSearch.value.trim())) {
    selectGene(geneSearch.value.trim())
  }
}

/**
 * 选择下一个建议项
 */
function selectNext() {
  if (selectedIndex.value < filteredGenes.value.length - 1) {
    selectedIndex.value++
  }
}

/**
 * 选择上一个建议项
 */
function selectPrev() {
  if (selectedIndex.value > 0) {
    selectedIndex.value--
  }
}

/**
 * 加载基因表达数据
 */
async function loadGeneExpression(geneName) {
  const targetFileId = props.fileId
  if (!targetFileId) return
  
  loading.value = true
  error.value = ''
  
  try {
    // 调用API获取基因表达数据
    const expressionData = await getGeneExpression(targetFileId, geneName)
    
    // 将表达数据存储到Map中
    geneExpressionData.value.clear()
    expressionData.forEach(item => {
      geneExpressionData.value.set(item.spotId, item.value)
    })
    
    // 更新spots数据，添加基因表达值
    spots.value.forEach(spot => {
      const expressionValue = geneExpressionData.value.get(spot.id)
      if (expressionValue !== undefined) {
        spot.geneExpression = expressionValue
      } else {
        spot.geneExpression = 0
      }
    })
    
    // 计算表达范围
    const expressionValues = Array.from(geneExpressionData.value.values())
    if (expressionValues.length > 0) {
      minExpression.value = Math.min(...expressionValues)
      maxExpression.value = Math.max(...expressionValues)
    } else {
      minExpression.value = 0
      maxExpression.value = 0
    }
    
    renderVisualization()
    renderStatisticsCharts()
  } catch (err) {
    error.value = t('analysis.errors.loadGeneDataFailed', { error: err?.message || t('app.unknownError') })
  } finally {
    loading.value = false
  }
}

/**
 * 清除基因选择
 */
function clearGene() {
  selectedGene.value = ''
  geneSearch.value = ''
  geneExpressionData.value.clear()
  minExpression.value = 0
  maxExpression.value = 0
  showSuggestions.value = false
  selectedIndex.value = -1
  
  // 移除spots中的基因表达值
  spots.value.forEach(spot => {
    delete spot.geneExpression
  })
  
  renderVisualization()
}

function onImageLoad() {
  imageLoaded = true
  // 确保DOM已准备好后再渲染
  nextTick(() => {
    if (spotsCanvas.value) {
      renderVisualization()
    }
  })
}

function updateVisualization() {
  renderCanvas()
  if (selectedGene.value) {
    renderStatisticsCharts()
  }
}

function renderVisualization() {
  renderCanvas()
}

function renderCanvas() {
  if (!spotsCanvas.value) {
    return
  }
  
  const canvas = spotsCanvas.value
  const wrapper = vizCanvasWrapper.value
  
  if (!wrapper) {
    return
  }
  
  // 设置canvas尺寸
  const rect = wrapper.getBoundingClientRect()
  if (rect.width === 0 || rect.height === 0) {
    return
  }
  
  canvas.width = rect.width
  canvas.height = rect.height
  
  canvasContext = canvas.getContext('2d')
  if (!canvasContext) {
    return
  }
  
  canvasContext.clearRect(0, 0, canvas.width, canvas.height)
  
  if (!showSpots.value) {
    return
  }
  
  if (spots.value.length === 0) {
    return
  }
  
  // 计算图像在canvas上的显示位置和缩放因子
  // 关键：spots坐标基于图像坐标系（image coordinates），需要映射到canvas坐标系
  // 使用接口返回的图像尺寸，而不是从图像元素获取
  if (sliceImageUrl.value && imageWidth.value > 0 && imageHeight.value > 0) {
    // 使用接口返回的图像尺寸
    const imgWidth = imageWidth.value
    const imgHeight = imageHeight.value
    
    // 计算图像在canvas上的缩放和偏移（保持宽高比，居中显示）
    const imgAspect = imgWidth / imgHeight
    const canvasAspect = canvas.width / canvas.height
    
    if (imgAspect > canvasAspect) {
      // 图像更宽，以宽度为基准适配canvas
      scaleFactor.value = canvas.width / imgWidth
      offsetX.value = 0
      offsetY.value = (canvas.height - imgHeight * scaleFactor.value) / 2
    } else {
      // 图像更高，以高度为基准适配canvas
      scaleFactor.value = canvas.height / imgHeight
      offsetX.value = (canvas.width - imgWidth * scaleFactor.value) / 2
      offsetY.value = 0
    }
  } else {
    scaleFactor.value = 1
    offsetX.value = 0
    offsetY.value = 0
  }
  // 绘制Spots
  spots.value.forEach(spot => {
    const x = spot.x * scaleFactor.value + offsetX.value
    const y = spot.y * scaleFactor.value + offsetY.value
    
    // 获取spot颜色（优先级：基因表达 > cluster > 默认）
    const spotColor = getSpotColor(spot)
    
    // 绘制spot圆圈
    canvasContext.fillStyle = spotColor
    canvasContext.beginPath()
    canvasContext.arc(x, y, spotSize.value, 0, Math.PI * 2)
    canvasContext.fill()
    
    // 绘制边框
    // 如果有clusterLabel，使用对应的边框颜色；否则使用默认边框
    let borderColor
    if (hasClusterLabel.value && spot.clusterLabel !== undefined && spot.clusterLabel !== null && spot.clusterLabel !== '') {
      const label = String(spot.clusterLabel)
      const color = clusterColorMap.value.get(label)
      if (color) {
        const r = parseInt(color.slice(1, 3), 16)
        const g = parseInt(color.slice(3, 5), 16)
        const b = parseInt(color.slice(5, 7), 16)
        borderColor = `rgba(${r}, ${g}, ${b}, ${spotOpacity.value * 0.6})`
      } else {
        borderColor = `rgba(60, 100, 160, ${spotOpacity.value * 0.6})`
      }
    } else {
      borderColor = `rgba(60, 100, 160, ${spotOpacity.value * 0.6})`
    }
    
    canvasContext.strokeStyle = borderColor
    canvasContext.lineWidth = 0.5
    canvasContext.stroke()
  })
}

/**
 * 根据归一化的表达值获取颜色
 * 低表达 = 蓝色，高表达 = 红色
 */
function getExpressionColor(normalizedValue) {
  // 将值限制在0-1之间
  const value = Math.max(0, Math.min(1, normalizedValue))

  // 低表达 = 蓝色，高表达 = 红色
  const r = Math.round(255 * value)
  const g = Math.round(100 * (1 - Math.abs(value - 0.5) * 2))
  const b = Math.round(255 * (1 - value))

  return `rgba(${r}, ${g}, ${b}, ${spotOpacity.value})`
}

// 统计图表渲染
function renderStatisticsCharts() {
  if (!showStatistics.value || !selectedGene.value) return
  
  nextTick(() => {
    if (histogramChart.value) {
      renderHistogram(histogramChart.value, spots.value)
    }
    
    if (hasClusterLabel.value) {
      if (boxplotChart.value) {
        renderBoxplot(boxplotChart.value, clusterSpotsMap.value)
      }
      if (pieChart.value) {
        renderPieChart(pieChart.value, clusterSpotsMap.value, clusterColorMap.value)
      }
      if (barChart.value) {
        renderBarChart(barChart.value, clusterSpotsMap.value)
      }
    }
  })
}

function handleCanvasMouseMove(event) {
  if (!spotsCanvas.value || !showSpots.value) return
  
  const rect = spotsCanvas.value.getBoundingClientRect()
  const x = event.clientX - rect.left
  const y = event.clientY - rect.top
  
  // 查找最近的spot
  const nearestSpot = findNearestSpot(x, y)
  
  if (nearestSpot) {
    hoveredSpot.value = nearestSpot
    
    // 如果有clusterLabel，找到同label的所有spots
    if (hasClusterLabel.value && nearestSpot.clusterLabel !== undefined && nearestSpot.clusterLabel !== null && nearestSpot.clusterLabel !== '') {
      const label = String(nearestSpot.clusterLabel)
      hoveredClusterSpots.value = clusterSpotsMap.value.get(label) || []
    } else {
      // 没有clusterLabel时，只高亮当前spot
      hoveredClusterSpots.value = [nearestSpot]
    }
    
    // 高亮spot（重新渲染）
    renderVisualization()
    highlightClusterSpots(hoveredClusterSpots.value)
  } else {
    hoveredSpot.value = null
    hoveredClusterSpots.value = []
    renderVisualization()
  }
}

function handleCanvasMouseLeave() {
  hoveredSpot.value = null
  hoveredClusterSpots.value = []
  renderVisualization()
}

function handleCanvasClick(event) {
  // 可以实现点击选择spot等功能
}

function findNearestSpot(x, y) {
  if (spots.value.length === 0) return null
  
  let nearest = null
  let minDist = Infinity
  const threshold = spotSize.value * 2
  
  spots.value.forEach(spot => {
    const spotX = spot.x * scaleFactor.value + offsetX.value
    const spotY = spot.y * scaleFactor.value + offsetY.value
    const dist = Math.sqrt(Math.pow(spotX - x, 2) + Math.pow(spotY - y, 2))
    
    if (dist < minDist && dist < threshold) {
      minDist = dist
      nearest = spot
    }
  })
  
  return nearest
}

function highlightClusterSpots(clusterSpots) {
  if (!canvasContext || !clusterSpots || clusterSpots.length === 0) return
  
  // 为所有同cluster的spots绘制高亮效果
  clusterSpots.forEach(spot => {
    const x = spot.x * scaleFactor.value + offsetX.value
    const y = spot.y * scaleFactor.value + offsetY.value
    
    // 获取spot的颜色作为高亮颜色
    const baseColor = getSpotColor(spot)
    // 提取RGB值，增加亮度
    const colorMatch = baseColor.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/)
    if (colorMatch) {
      const r = Math.min(255, parseInt(colorMatch[1]) + 30)
      const g = Math.min(255, parseInt(colorMatch[2]) + 30)
      const b = Math.min(255, parseInt(colorMatch[3]) + 30)
      
      // 绘制高亮效果（放大和发光）
      canvasContext.save()
      canvasContext.shadowBlur = 15
      canvasContext.shadowColor = baseColor
      canvasContext.fillStyle = `rgba(${r}, ${g}, ${b}, ${Math.min(1, spotOpacity.value + 0.2)})`
      canvasContext.beginPath()
      canvasContext.arc(x, y, spotSize.value * 1.8, 0, Math.PI * 2)
      canvasContext.fill()
      canvasContext.restore()
    }
  })
}

// 监听fileId变化，重新加载数据
watch(
  () => props.fileId,
  (newFileId) => {
    if (newFileId) {
      loadData()
    }
  },
  { immediate: false }
)

// 监听图像加载
watch(() => sliceImageUrl.value, (newUrl) => {
  if (newUrl) {
    imageElement = new Image()
    imageElement.crossOrigin = 'anonymous'
    imageElement.onload = () => {
      imageLoaded = true
      renderVisualization()
    }
    imageElement.onerror = () => {
      imageLoaded = false
      error.value = t('analysis.errors.imageLoadFailed')
    }
    imageElement.src = newUrl
  } else {
    imageElement = null
    imageLoaded = false
  }
})

function handleResize() {
  renderVisualization()
  resizeStatistics()
}

onMounted(() => {
  loadData()
  
  // 监听窗口大小变化
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)

  disposeStatistics()
})
</script>

<style scoped>
.spatial-visualization-container {
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

.form-group input[type="range"],
.form-group select,
.form-group input[type="text"] {
  width: 100%;
  padding: 0.5rem;
  border: 1px solid rgba(200, 200, 210, 0.4);
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.8);
  font-size: 0.9rem;
  color: rgba(60, 60, 70, 0.9);
}

.form-group input[type="range"] {
  padding: 0;
}

.form-group input[type="checkbox"] {
  margin-right: 0.5rem;
}

.gene-search-container {
  display: flex;
  gap: 0.5rem;
}

.gene-search-input {
  flex: 1;
}

.gene-search-btn {
  padding: 0.5rem 1rem;
  background: rgba(100, 150, 220, 0.6);
  border: none;
  border-radius: 4px;
  color: white;
  font-size: 0.9rem;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
}

.gene-search-btn:hover:not(:disabled) {
  background: rgba(100, 150, 220, 0.8);
}

.gene-search-btn:disabled {
  background: rgba(200, 200, 210, 0.4);
  cursor: not-allowed;
  opacity: 0.6;
}

.gene-autocomplete-container {
  position: relative;
  width: 100%;
}

.gene-autocomplete-input {
  width: 100%;
  padding: 0.5rem;
  border: 1px solid rgba(200, 200, 210, 0.4);
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.8);
  font-size: 0.9rem;
  color: rgba(60, 60, 70, 0.9);
}

.gene-autocomplete-input:focus {
  outline: none;
  border-color: rgba(100, 150, 220, 0.6);
  box-shadow: 0 0 0 2px rgba(100, 150, 220, 0.1);
}

.gene-suggestions {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  margin-top: 4px;
  background: rgba(255, 255, 255, 0.98);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(200, 200, 210, 0.4);
  border-radius: 4px;
  max-height: 200px;
  overflow-y: auto;
  z-index: 1000;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.gene-suggestion-item {
  padding: 0.5rem 0.75rem;
  cursor: pointer;
  font-size: 0.9rem;
  color: rgba(60, 60, 70, 0.9);
  transition: background-color 0.15s ease;
}

.gene-suggestion-item:hover,
.gene-suggestion-item.active {
  background-color: rgba(100, 150, 220, 0.1);
}

.gene-suggestion-item:first-child {
  border-top-left-radius: 4px;
  border-top-right-radius: 4px;
}

.gene-suggestion-item:last-child {
  border-bottom-left-radius: 4px;
  border-bottom-right-radius: 4px;
}

.gene-suggestion-empty {
  color: rgba(100, 100, 110, 0.6);
  font-style: italic;
  cursor: default;
}

.gene-suggestion-empty:hover {
  background-color: transparent;
}

.selected-gene-info {
  margin-top: 0.75rem;
  padding: 0.75rem;
  background: rgba(100, 150, 220, 0.1);
  border-radius: 6px;
  border: 1px solid rgba(100, 150, 220, 0.3);
}

.gene-chip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.5rem;
}

.gene-name {
  font-weight: 600;
  color: rgba(60, 60, 70, 0.9);
  font-size: 0.95rem;
}

.gene-chip-close {
  background: transparent;
  border: none;
  font-size: 1.2rem;
  color: rgba(100, 100, 110, 0.7);
  cursor: pointer;
  padding: 0;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  transition: all 0.2s ease;
}

.gene-chip-close:hover {
  background: rgba(220, 100, 100, 0.1);
  color: rgba(220, 100, 100, 0.9);
}

.gene-expression-info {
  display: flex;
  gap: 0.5rem;
  font-size: 0.85rem;
}

.info-label {
  color: rgba(100, 100, 110, 0.7);
}

.info-value {
  color: rgba(60, 60, 70, 0.9);
  font-weight: 500;
}

.color-scale {
  position: absolute;
  bottom: 1rem;
  left: 1rem;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(200, 200, 210, 0.5);
  border-radius: 8px;
  padding: 0.75rem 1rem;
  z-index: 100;
  min-width: 120px;
}

.color-scale-title {
  font-size: 0.8rem;
  font-weight: 600;
  color: rgba(60, 60, 70, 0.9);
  margin-bottom: 0.5rem;
}

.color-scale-gradient {
  width: 100%;
  height: 20px;
  background: linear-gradient(to right, 
    rgba(0, 100, 255, 0.8),
    rgba(255, 0, 0, 0.8)
  );
  border-radius: 4px;
  margin-bottom: 0.5rem;
}

.color-scale-labels {
  display: flex;
  justify-content: space-between;
  font-size: 0.75rem;
  color: rgba(100, 100, 110, 0.8);
}

.form-value {
  display: inline-block;
  margin-left: 0.5rem;
  font-size: 0.85rem;
  color: rgba(100, 100, 110, 0.8);
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

.viz-canvas-wrapper {
  flex: 1;
  position: relative;
  overflow: hidden;
  background: #f5f5f5;
}

.loading-state,
.error-state {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: rgba(100, 100, 110, 0.7);
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid rgba(200, 200, 210, 0.3);
  border-top-color: rgba(100, 150, 220, 0.6);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin-bottom: 1rem;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.error-icon {
  font-size: 3rem;
  margin-bottom: 1rem;
}

.viz-canvas-container {
  position: relative;
  width: 100%;
  height: 100%;
}

.slice-background {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
  z-index: 1;
}

.no-image-notice {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 50;
  text-align: center;
}

.notice-icon {
  font-size: 4rem;
  margin-bottom: 1rem;
  opacity: 0.4;
}

.notice-text {
  margin: 0;
  font-size: 1.2rem;
  font-weight: 500;
  color: rgba(100, 100, 110, 0.7);
}

.notice-subtext {
  margin: 0.5rem 0 0 0;
  font-size: 0.9rem;
  color: rgba(120, 120, 130, 0.6);
}


.spots-canvas {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 2;
  cursor: crosshair;
}

.spot-tooltip {
  position: fixed;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(200, 200, 210, 0.5);
  border-radius: 8px;
  padding: 0.75rem 1rem;
  font-size: 0.85rem;
  pointer-events: none;
  z-index: 10000;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  max-width: 300px;
}

.spot-tooltip-fixed {
  position: absolute;
  bottom: 1rem;
  right: 1rem;
  max-width: 280px;
}

.tooltip-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: 600;
  margin-bottom: 0.5rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid rgba(200, 200, 210, 0.4);
}

.tooltip-icon {
  font-size: 1.2rem;
}

.tooltip-title {
  font-size: 0.95rem;
  color: rgba(60, 60, 70, 0.9);
}

.tooltip-content {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.tooltip-item {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.tooltip-label {
  color: rgba(100, 100, 110, 0.8);
  font-weight: 500;
}

.tooltip-value {
  color: rgba(60, 60, 70, 0.9);
  font-weight: 500;
}

.tooltip-genes {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  margin-top: 0.25rem;
}

.gene-tag-small {
  display: inline-block;
  padding: 0.125rem 0.375rem;
  background: rgba(100, 150, 220, 0.2);
  border-radius: 4px;
  font-size: 0.75rem;
  margin-right: 0.25rem;
  margin-bottom: 0.125rem;
}

.spot-id-tag {
  display: inline-block;
  padding: 0.125rem 0.375rem;
  background: rgba(100, 150, 220, 0.15);
  border: 1px solid rgba(100, 150, 220, 0.3);
  border-radius: 4px;
  font-size: 0.75rem;
  color: rgba(60, 60, 70, 0.8);
  font-family: monospace;
}

/* 新增样式 */
.form-select {
  width: 100%;
  padding: 0.5rem;
  border: 1px solid rgba(200, 200, 210, 0.4);
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.8);
  font-size: 0.9rem;
  color: rgba(60, 60, 70, 0.9);
  cursor: pointer;
}

.form-select:focus {
  outline: none;
  border-color: rgba(100, 150, 220, 0.6);
  box-shadow: 0 0 0 2px rgba(100, 150, 220, 0.1);
}

.echarts-container {
  width: 100%;
  height: 100%;
}

.statistics-panel {
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(10px);
  border-radius: 8px;
  border: 1px solid rgba(200, 200, 210, 0.4);
  overflow: hidden;
  transition: max-height 0.3s ease;
  max-height: 400px;
}

.statistics-panel.collapsed {
  max-height: 50px;
}

.statistics-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.5rem;
  border-bottom: 1px solid rgba(200, 200, 210, 0.4);
  cursor: pointer;
  user-select: none;
}

.statistics-header:hover {
  background: rgba(100, 150, 220, 0.05);
}

.statistics-header h4 {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: rgba(60, 60, 70, 0.9);
}

.collapse-btn {
  background: transparent;
  border: none;
  font-size: 1rem;
  color: rgba(100, 100, 110, 0.7);
  cursor: pointer;
  padding: 0.25rem 0.5rem;
}

.statistics-content {
  padding: 1rem;
}

.statistics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 1rem;
}

.chart-card {
  background: rgba(255, 255, 255, 0.9);
  border-radius: 6px;
  padding: 1rem;
  border: 1px solid rgba(200, 200, 210, 0.3);
}

.chart-card h5 {
  margin: 0 0 0.75rem 0;
  font-size: 0.9rem;
  font-weight: 600;
  color: rgba(60, 60, 70, 0.9);
}

.chart-container {
  width: 100%;
  height: 250px;
}
</style>
