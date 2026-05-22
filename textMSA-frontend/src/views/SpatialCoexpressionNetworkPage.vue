<template>
  <div class="spatial-coexpression-page">
    <!-- 头部区域 -->
    <div class="header">
      <div class="header-left">
        <h1>
          <Icon name="graph" size="lg" class="header-icon" />
          {{ $t('spatialCoexpression.title') }}
        </h1>
        <p class="header-subtitle">{{ $t('spatialCoexpression.subtitle') }}</p>
      </div>
      <div class="header-controls">
        <el-button type="primary" @click="loadSampleData">
          <Icon name="upload" size="sm" class="button-icon" />
          {{ $t('spatialCoexpression.loadSample') }}
        </el-button>
        <el-button @click="exportImage">
          <Icon name="download" size="sm" class="button-icon" />
          {{ $t('spatialCoexpression.export') }}
        </el-button>
      </div>
    </div>

    <!-- 主要内容区域 -->
    <div class="main-content">
      <!-- 左侧控制面板 -->
      <div class="sidebar">
        <!-- 数据控制部分 -->
        <el-card class="control-section" shadow="never">
          <template #header>
            <div class="section-title">
              <Icon name="document" size="sm" class="section-icon" />
              {{ $t('spatialCoexpression.dataControl.title') }}
            </div>
          </template>

          <div class="control-group">
            <label class="control-label">{{ $t('spatialCoexpression.dataControl.dataset') }}</label>
            <el-select v-model="selectedDataset" class="select-box" @change="handleDatasetChange">
              <el-option
                v-for="ds in datasets"
                :key="ds.value"
                :label="ds.label"
                :value="ds.value"
              />
            </el-select>
          </div>

          <div class="control-group">
            <label class="control-label">{{ $t('spatialCoexpression.dataControl.genes') }}</label>
            <div class="gene-list">
              <el-scrollbar height="200px">
                <div
                  v-for="gene in filteredGenes"
                  :key="gene.id"
                  class="gene-item"
                  :class="{ selected: selectedGenes.includes(gene.id) }"
                  @click="toggleGeneSelection(gene.id)"
                >
                  <span>{{ gene.name }}</span>
                  <span class="expression-level">{{ gene.expression.toFixed(1) }}</span>
                </div>
              </el-scrollbar>
            </div>
          </div>

          <el-button type="primary" class="analyze-btn" @click="runAnalysis">
            <Icon name="play" size="sm" class="button-icon" />
            {{ $t('spatialCoexpression.dataControl.runAnalysis') }}
          </el-button>
        </el-card>

        <!-- 可视化参数 -->
        <el-card class="control-section" shadow="never">
          <template #header>
            <div class="section-title">
              <Icon name="settings" size="sm" class="section-icon" />
              {{ $t('spatialCoexpression.visualization.title') }}
            </div>
          </template>

          <div class="control-group">
            <label class="control-label">{{ $t('spatialCoexpression.visualization.layout') }}</label>
            <el-select v-model="layoutType" class="select-box" @change="updateLayout">
              <el-option
                v-for="layout in layouts"
                :key="layout.value"
                :label="layout.label"
                :value="layout.value"
              />
            </el-select>
          </div>

          <div class="control-group">
            <label class="control-label">
              {{ $t('spatialCoexpression.visualization.nodeSize') }}
              <span class="value-display">{{ nodeSizeScale }}</span>
            </label>
            <el-slider
              v-model="nodeSizeScale"
              :min="1"
              :max="10"
              :step="0.5"
              @change="updateNodeSize"
            />
          </div>

          <div class="control-group">
            <label class="control-label">
              {{ $t('spatialCoexpression.visualization.threshold') }}
              <span class="value-display">{{ connectionThreshold }}</span>
            </label>
            <el-slider
              v-model="connectionThreshold"
              :min="0"
              :max="1"
              :step="0.1"
              @change="updateThreshold"
            />
          </div>

          <div class="control-group">
            <label class="control-label">{{ $t('spatialCoexpression.visualization.colorScheme') }}</label>
            <el-select v-model="colorScheme" class="select-box" @change="updateColorScheme">
              <el-option
                v-for="scheme in colorSchemes"
                :key="scheme.value"
                :label="scheme.label"
                :value="scheme.value"
              />
            </el-select>
          </div>
        </el-card>

        <!-- 筛选与搜索 -->
        <el-card class="control-section" shadow="never">
          <template #header>
            <div class="section-title">
              <Icon name="search" size="sm" class="section-icon" />
              {{ $t('spatialCoexpression.filter.title') }}
            </div>
          </template>

          <div class="control-group">
            <label class="control-label">{{ $t('spatialCoexpression.filter.search') }}</label>
            <el-input
              v-model="searchTerm"
              :placeholder="$t('spatialCoexpression.filter.searchPlaceholder')"
              clearable
              @input="handleSearch"
            />
          </div>

          <div class="control-group">
            <label class="control-label">{{ $t('spatialCoexpression.filter.expressionRange') }}</label>
            <div class="range-inputs">
              <el-input-number
                v-model="minExpression"
                :placeholder="$t('spatialCoexpression.filter.min')"
                :min="0"
                :max="10"
                :step="0.1"
                size="small"
                style="flex: 1"
              />
              <span class="range-separator">-</span>
              <el-input-number
                v-model="maxExpression"
                :placeholder="$t('spatialCoexpression.filter.max')"
                :min="0"
                :max="10"
                :step="0.1"
                size="small"
                style="flex: 1"
              />
            </div>
          </div>

          <el-button @click="applyFilter">
            <Icon name="sort" size="sm" class="button-icon" />
            {{ $t('spatialCoexpression.filter.apply') }}
          </el-button>
        </el-card>
      </div>

      <!-- 右侧可视化区域 -->
      <div class="visualization-area">
        <el-tabs v-model="activeTab" @tab-change="handleTabChange">
          <el-tab-pane :label="$t('spatialCoexpression.tabs.network')" name="network">
            <div ref="networkContainer" class="visualization-container"></div>
          </el-tab-pane>
          <el-tab-pane :label="$t('spatialCoexpression.tabs.spatial')" name="spatial">
            <div ref="spatialContainer" class="visualization-container"></div>
          </el-tab-pane>
          <el-tab-pane :label="$t('spatialCoexpression.tabs.heatmap')" name="heatmap">
            <div ref="heatmapContainer" class="visualization-container"></div>
          </el-tab-pane>
        </el-tabs>

        <!-- 图例 -->
        <div class="legend">
          <div class="legend-item">
            <div class="legend-color low"></div>
            <span>{{ $t('spatialCoexpression.legend.low') }}</span>
          </div>
          <div class="legend-item">
            <div class="legend-color medium"></div>
            <span>{{ $t('spatialCoexpression.legend.medium') }}</span>
          </div>
          <div class="legend-item">
            <div class="legend-color high"></div>
            <span>{{ $t('spatialCoexpression.legend.high') }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import * as echarts from 'echarts'
import Icon from '../components/common/Icon.vue'
import { ElMessage } from 'element-plus'

const { t } = useI18n()

// 模拟数据
interface Gene {
  id: string
  name: string
  expression: number
  x: number
  y: number
}

interface Link {
  source: string
  target: string
  weight: number
}

// 响应式数据
const selectedDataset = ref('sample1')
const selectedGenes = ref<string[]>([])
const searchTerm = ref('')
const minExpression = ref(0)
const maxExpression = ref(10)
const nodeSizeScale = ref(5)
const connectionThreshold = ref(0.5)
const layoutType = ref('force')
const colorScheme = ref('viridis')
const activeTab = ref('network')

// 图表实例
const networkContainer = ref<HTMLElement | null>(null)
const spatialContainer = ref<HTMLElement | null>(null)
const heatmapContainer = ref<HTMLElement | null>(null)
let networkChart: echarts.ECharts | null = null
let spatialChart: echarts.ECharts | null = null
let heatmapChart: echarts.ECharts | null = null

// 模拟基因数据
const sampleGenes: Gene[] = [
  { id: 'gene1', name: 'Sox2', expression: 8.5, x: 150, y: 200 },
  { id: 'gene2', name: 'Pax6', expression: 7.2, x: 300, y: 180 },
  { id: 'gene3', name: 'Neurod1', expression: 6.8, x: 250, y: 300 },
  { id: 'gene4', name: 'Tbr1', expression: 5.5, x: 400, y: 250 },
  { id: 'gene5', name: 'Gad1', expression: 4.2, x: 350, y: 400 },
  { id: 'gene6', name: 'Vglut1', expression: 7.9, x: 500, y: 350 },
  { id: 'gene7', name: 'Nestin', expression: 9.1, x: 200, y: 100 },
  { id: 'gene8', name: 'Mapt', expression: 6.3, x: 450, y: 150 },
  { id: 'gene9', name: 'S100b', expression: 3.8, x: 550, y: 200 },
  { id: 'gene10', name: 'Cx3cr1', expression: 4.5, x: 600, y: 300 }
]

const sampleLinks: Link[] = [
  { source: 'gene1', target: 'gene2', weight: 0.89 },
  { source: 'gene1', target: 'gene3', weight: 0.76 },
  { source: 'gene2', target: 'gene4', weight: 0.82 },
  { source: 'gene3', target: 'gene5', weight: 0.71 },
  { source: 'gene4', target: 'gene6', weight: 0.68 },
  { source: 'gene5', target: 'gene6', weight: 0.55 },
  { source: 'gene7', target: 'gene1', weight: 0.92 },
  { source: 'gene7', target: 'gene2', weight: 0.78 },
  { source: 'gene8', target: 'gene4', weight: 0.65 },
  { source: 'gene9', target: 'gene5', weight: 0.59 },
  { source: 'gene10', target: 'gene6', weight: 0.48 }
]

const genes = ref<Gene[]>(sampleGenes)
const links = ref<Link[]>(sampleLinks)

// 选项数据
const datasets = [
  { label: t('spatialCoexpression.datasets.sample1'), value: 'sample1' },
  { label: t('spatialCoexpression.datasets.sample2'), value: 'sample2' },
  { label: t('spatialCoexpression.datasets.sample3'), value: 'sample3' }
]

const layouts = [
  { label: t('spatialCoexpression.layouts.force'), value: 'force' },
  { label: t('spatialCoexpression.layouts.circular'), value: 'circular' },
  { label: t('spatialCoexpression.layouts.grid'), value: 'grid' }
]

const colorSchemes = [
  { label: 'Viridis (默认)', value: 'viridis' },
  { label: 'Plasma', value: 'plasma' },
  { label: 'Inferno', value: 'inferno' },
  { label: 'Magma', value: 'magma' }
]

// 计算属性
const filteredGenes = computed(() => {
  let result = genes.value

  // 搜索过滤
  if (searchTerm.value) {
    const term = searchTerm.value.toLowerCase()
    result = result.filter(gene => gene.name.toLowerCase().includes(term))
  }

  // 表达量范围过滤
  result = result.filter(
    gene => gene.expression >= minExpression.value && gene.expression <= maxExpression.value
  )

  return result
})

// 根据表达量获取颜色
function getColorByExpression(expression: number): string {
  const colors = [
    '#440154', '#482475', '#414487', '#355f8d',
    '#2a788e', '#21918c', '#22a884', '#44bf70',
    '#7ad151', '#bddf26', '#fde725'
  ]
  const maxExpr = 10
  const normalized = Math.min(expression / maxExpr, 1)
  const index = Math.floor(normalized * (colors.length - 1))
  return colors[index]
}

// 初始化网络图
function initNetworkChart() {
  if (!networkContainer.value) return

  networkChart = echarts.init(networkContainer.value)

  const filteredLinks = links.value.filter(link => link.weight >= connectionThreshold.value)

  const nodes = genes.value.map(gene => ({
    id: gene.id,
    name: gene.name,
    value: gene.expression,
    symbolSize: Math.sqrt(gene.expression) * 3 * (nodeSizeScale.value / 5),
    itemStyle: {
      color: getColorByExpression(gene.expression)
    },
    label: {
      show: true,
      fontSize: 12
    }
  }))

  const edges = filteredLinks.map(link => ({
    source: link.source,
    target: link.target,
    value: link.weight,
    lineStyle: {
      width: link.weight * 5,
      opacity: 0.6
    }
  }))

  const option: echarts.EChartsOption = {
    title: {
      text: t('spatialCoexpression.tabs.network'),
      left: 'center'
    },
    tooltip: {
      trigger: 'item',
      formatter: (params: any) => {
        if (params.dataType === 'node') {
          return `${params.data.name}<br/>${t('spatialCoexpression.tooltip.expression')}: ${params.data.value.toFixed(2)}`
        }
        return `${params.data.source} → ${params.data.target}<br/>${t('spatialCoexpression.tooltip.weight')}: ${params.data.value.toFixed(2)}`
      }
    },
    series: [
      {
        type: 'graph',
        layout: layoutType.value === 'force' ? 'force' : layoutType.value === 'circular' ? 'circular' : 'none',
        data: nodes,
        links: edges,
        roam: true,
        label: {
          show: true,
          position: 'right',
          fontSize: 12
        },
        lineStyle: {
          color: '#999',
          curveness: 0.3
        },
        emphasis: {
          focus: 'adjacency',
          lineStyle: {
            width: 4
          }
        },
        force: {
          repulsion: 300,
          gravity: 0.1,
          edgeLength: 100
        }
      }
    ]
  }

  networkChart.setOption(option)

  // 添加点击事件
  networkChart.on('click', (params: any) => {
    if (params.dataType === 'node') {
      toggleGeneSelection(params.data.id)
    }
  })
}

// 初始化空间分布图
function initSpatialChart() {
  if (!spatialContainer.value) return

  spatialChart = echarts.init(spatialContainer.value)

  const data = genes.value.map(gene => [
    gene.x,
    gene.y,
    gene.expression,
    gene.name
  ])

  const option: echarts.EChartsOption = {
    title: {
      text: t('spatialCoexpression.tabs.spatial'),
      left: 'center'
    },
    tooltip: {
      trigger: 'item',
      formatter: (params: any) => {
        return `${params.data[3]}<br/>${t('spatialCoexpression.tooltip.expression')}: ${params.data[2].toFixed(2)}<br/>X: ${params.data[0]}, Y: ${params.data[1]}`
      }
    },
    xAxis: {
      type: 'value',
      name: 'X',
      scale: true
    },
    yAxis: {
      type: 'value',
      name: 'Y',
      scale: true
    },
    visualMap: {
      min: 0,
      max: 10,
      dimension: 2,
      inRange: {
        color: ['#440154', '#21918c', '#fde725']
      },
      calculable: true,
      text: [t('spatialCoexpression.legend.high'), t('spatialCoexpression.legend.low')],
      left: 'right'
    },
    series: [
      {
        type: 'scatter',
        data: data,
        symbolSize: (data: any) => data[2] * 3,
        itemStyle: {
          opacity: 0.8
        },
        label: {
          show: true,
          formatter: (params: any) => params.data[3],
          position: 'top'
        }
      }
    ]
  }

  spatialChart.setOption(option)
}

// 初始化热图
function initHeatmapChart() {
  if (!heatmapContainer.value) return

  heatmapChart = echarts.init(heatmapContainer.value)

  // 生成模拟表达矩阵
  const regions = Array.from({ length: 10 }, (_, i) => `区域${i + 1}`)
  const geneNames = genes.value.map(g => g.name)
  const expressionMatrix: number[][] = []

  genes.value.forEach((gene, i) => {
    const row: number[] = []
    for (let j = 0; j < 10; j++) {
      // 基于基因表达量生成相关数据
      row.push(gene.expression * (0.7 + Math.random() * 0.6))
    }
    expressionMatrix.push(row)
  })

  const option: echarts.EChartsOption = {
    title: {
      text: t('spatialCoexpression.tabs.heatmap'),
      left: 'center'
    },
    tooltip: {
      position: 'top',
      formatter: (params: any) => {
        return `${params.seriesName}<br/>${params.name}: ${params.value[1]}<br/>${t('spatialCoexpression.tooltip.expression')}: ${params.value[2].toFixed(2)}`
      }
    },
    grid: {
      height: '50%',
      top: '10%'
    },
    xAxis: {
      type: 'category',
      data: regions,
      splitArea: {
        show: true
      }
    },
    yAxis: {
      type: 'category',
      data: geneNames,
      splitArea: {
        show: true
      }
    },
    visualMap: {
      min: 0,
      max: 10,
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: '5%',
      inRange: {
        color: ['#440154', '#21918c', '#fde725']
      }
    },
    series: [
      {
        name: t('spatialCoexpression.tabs.heatmap'),
        type: 'heatmap',
        data: expressionMatrix.flatMap((row, i) =>
          row.map((value, j) => [j, i, value])
        ),
        label: {
          show: true,
          fontSize: 10
        },
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowColor: 'rgba(0, 0, 0, 0.5)'
          }
        }
      }
    ]
  }

  heatmapChart.setOption(option)
}

// 事件处理
function handleDatasetChange() {
  // 可以在这里加载不同的数据集
  ElMessage.info(t('spatialCoexpression.messages.datasetChanged'))
}

function toggleGeneSelection(geneId: string) {
  const index = selectedGenes.value.indexOf(geneId)
  if (index > -1) {
    selectedGenes.value.splice(index, 1)
  } else {
    selectedGenes.value.push(geneId)
  }
  updateNetworkHighlight()
}

function updateNetworkHighlight() {
  if (!networkChart) return
  const option = networkChart.getOption() as any
  if (option.series && option.series[0]) {
    option.series[0].data = option.series[0].data.map((node: any) => ({
      ...node,
      itemStyle: {
        ...node.itemStyle,
        borderColor: selectedGenes.value.includes(node.id) ? '#ff6b6b' : '#fff',
        borderWidth: selectedGenes.value.includes(node.id) ? 4 : 2
      }
    }))
    networkChart.setOption(option)
  }
}

function runAnalysis() {
  ElMessage.success(t('spatialCoexpression.messages.analysisStarted'))
  // 这里可以添加实际的共表达分析逻辑
}

function updateLayout() {
  initNetworkChart()
}

function updateNodeSize() {
  if (!networkChart) return
  const option = networkChart.getOption() as any
  if (option.series && option.series[0]) {
    option.series[0].data = option.series[0].data.map((node: any) => ({
      ...node,
      symbolSize: Math.sqrt(node.value) * 3 * (nodeSizeScale.value / 5)
    }))
    networkChart.setOption(option)
  }
}

function updateThreshold() {
  initNetworkChart()
}

function updateColorScheme() {
  initNetworkChart()
  initSpatialChart()
  initHeatmapChart()
}

function handleSearch() {
  // 搜索过滤已在computed中处理
}

function applyFilter() {
  ElMessage.success(t('spatialCoexpression.messages.filterApplied'))
}

function handleTabChange(tab: string) {
  nextTick(() => {
    if (tab === 'network' && networkContainer.value) {
      initNetworkChart()
    } else if (tab === 'spatial' && spatialContainer.value) {
      initSpatialChart()
    } else if (tab === 'heatmap' && heatmapContainer.value) {
      initHeatmapChart()
    }
  })
}

function loadSampleData() {
  genes.value = [...sampleGenes]
  links.value = [...sampleLinks]
  selectedGenes.value = []
  searchTerm.value = ''
  minExpression.value = 0
  maxExpression.value = 10
  initNetworkChart()
  initSpatialChart()
  initHeatmapChart()
  ElMessage.success(t('spatialCoexpression.messages.sampleLoaded'))
}

function exportImage() {
  const currentChart = activeTab.value === 'network' ? networkChart
    : activeTab.value === 'spatial' ? spatialChart
    : heatmapChart

  if (currentChart) {
    const url = currentChart.getDataURL({
      type: 'png',
      pixelRatio: 2,
      backgroundColor: '#fff'
    })
    const link = document.createElement('a')
    link.download = `spatial-coexpression-${activeTab.value}.png`
    link.href = url
    link.click()
    ElMessage.success(t('spatialCoexpression.messages.exported'))
  }
}

// 窗口大小调整
function handleResize() {
  networkChart?.resize()
  spatialChart?.resize()
  heatmapChart?.resize()
}

onMounted(() => {
  nextTick(() => {
    initNetworkChart()
    window.addEventListener('resize', handleResize)
  })
})

onUnmounted(() => {
  networkChart?.dispose()
  spatialChart?.dispose()
  heatmapChart?.dispose()
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
.spatial-coexpression-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 16px;
  gap: 16px;
  background-color: #f5f7fa;
}

.header {
  background: linear-gradient(135deg, #1a237e 0%, #283593 100%);
  color: white;
  padding: 20px 24px;
  border-radius: 10px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left h1 {
  font-size: 1.8rem;
  font-weight: 600;
  margin: 0;
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-subtitle {
  font-size: 0.9rem;
  margin: 8px 0 0 0;
  opacity: 0.9;
}

.header-controls {
  display: flex;
  gap: 12px;
}

.button-icon {
  margin-right: 6px;
}

.main-content {
  flex: 1;
  display: flex;
  gap: 16px;
  overflow: hidden;
  min-height: 0;
}

.sidebar {
  width: 320px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow-y: auto;
}

.control-section {
  margin-bottom: 0;
}

.section-title {
  font-size: 1.1rem;
  font-weight: 600;
  color: #1a237e;
  display: flex;
  align-items: center;
  gap: 8px;
}

.section-icon {
  color: #1a237e;
}

.control-group {
  margin-bottom: 20px;
}

.control-group:last-child {
  margin-bottom: 0;
}

.control-label {
  display: block;
  margin-bottom: 8px;
  font-weight: 500;
  font-size: 0.9rem;
  color: #555;
}

.value-display {
  float: right;
  color: #1a237e;
  font-weight: 600;
}

.select-box {
  width: 100%;
}

.gene-list {
  border: 1px solid #eaeaea;
  border-radius: 6px;
  background: #fff;
}

.gene-item {
  padding: 10px 12px;
  margin: 4px;
  background-color: #f9f9f9;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.9rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  transition: all 0.2s;
}

.gene-item:hover {
  background-color: #e3f2fd;
}

.gene-item.selected {
  background-color: #bbdefb;
  border-left: 4px solid #1a237e;
}

.expression-level {
  font-size: 0.8rem;
  color: #666;
}

.analyze-btn {
  width: 100%;
  margin-top: 12px;
}

.range-inputs {
  display: flex;
  align-items: center;
  gap: 8px;
}

.range-separator {
  color: #999;
}

.visualization-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: white;
  border-radius: 10px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  overflow: hidden;
}

.visualization-container {
  flex: 1;
  min-height: 400px;
  width: 100%;
}

.legend {
  display: flex;
  justify-content: center;
  gap: 30px;
  padding: 16px;
  border-top: 1px solid #eaeaea;
  background: #fafafa;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.85rem;
  color: #666;
}

.legend-color {
  width: 16px;
  height: 16px;
  border-radius: 3px;
}

.legend-color.low {
  background-color: #440154;
}

.legend-color.medium {
  background-color: #21918c;
}

.legend-color.high {
  background-color: #fde725;
}

:deep(.el-card__header) {
  padding: 16px;
  border-bottom: 1px solid #eaeaea;
}

:deep(.el-card__body) {
  padding: 16px;
}
</style>
