<template>
  <div class="spatial-transcriptomics-page">
    <!-- 头部区域 -->
    <div class="header">
      <div class="header-left">
        <h1>
          <Icon name="diagram" size="lg" class="header-icon" />
          {{ $t('spatialTranscriptomics.title') }}
        </h1>
        <p class="header-subtitle">{{ $t('spatialTranscriptomics.subtitle') }}</p>
      </div>
      <div class="header-controls">
        <el-button type="primary" @click="loadSampleData">
          <Icon name="upload" size="sm" class="button-icon" />
          {{ $t('spatialTranscriptomics.loadSample') }}
        </el-button>
        <el-button @click="exportImage">
          <Icon name="download" size="sm" class="button-icon" />
          {{ $t('spatialTranscriptomics.export') }}
        </el-button>
      </div>
    </div>

    <!-- 主要内容区域 -->
    <div class="main-content">
      <!-- 左侧控制面板 -->
      <div class="sidebar">
        <!-- 聚类算法选择 -->
        <el-card class="control-section" shadow="never">
          <template #header>
            <div class="section-title">
              <Icon name="settings" size="sm" class="section-icon" />
              {{ $t('spatialTranscriptomics.algorithm.title') }}
            </div>
          </template>

          <div class="control-group">
            <label class="control-label">{{ $t('spatialTranscriptomics.algorithm.method') }}</label>
            <el-select v-model="selectedAlgorithm" class="select-box" @change="handleAlgorithmChange">
              <el-option
                v-for="algo in algorithms"
                :key="algo.value"
                :label="algo.label"
                :value="algo.value"
              />
            </el-select>
          </div>

          <div class="control-group">
            <label class="control-label">
              {{ $t('spatialTranscriptomics.algorithm.clusterCount') }}
              <span class="value-display">{{ clusterCount }}</span>
            </label>
            <el-slider
              v-model="clusterCount"
              :min="2"
              :max="20"
              :step="1"
              @change="updateClustering"
            />
          </div>

          <div class="control-group">
            <label class="control-label">
              {{ $t('spatialTranscriptomics.algorithm.resolution') }}
              <span class="value-display">{{ resolution.toFixed(2) }}</span>
            </label>
            <el-slider
              v-model="resolution"
              :min="0.1"
              :max="2.0"
              :step="0.1"
              @change="updateClustering"
            />
          </div>

          <el-button type="primary" class="analyze-btn" @click="runClustering">
            <Icon name="play" size="sm" class="button-icon" />
            {{ $t('spatialTranscriptomics.algorithm.runClustering') }}
          </el-button>
        </el-card>

        <!-- 可视化参数 -->
        <el-card class="control-section" shadow="never">
          <template #header>
            <div class="section-title">
              <Icon name="chart" size="sm" class="section-icon" />
              {{ $t('spatialTranscriptomics.visualization.title') }}
            </div>
          </template>

          <div class="control-group">
            <label class="control-label">{{ $t('spatialTranscriptomics.visualization.colorScheme') }}</label>
            <el-select v-model="colorScheme" class="select-box" @change="updateVisualization">
              <el-option
                v-for="scheme in colorSchemes"
                :key="scheme.value"
                :label="scheme.label"
                :value="scheme.value"
              />
            </el-select>
          </div>

          <div class="control-group">
            <label class="control-label">
              {{ $t('spatialTranscriptomics.visualization.pointSize') }}
              <span class="value-display">{{ pointSize }}</span>
            </label>
            <el-slider
              v-model="pointSize"
              :min="1"
              :max="10"
              :step="0.5"
              @change="updateVisualization"
            />
          </div>

          <div class="control-group">
            <label class="control-label">
              {{ $t('spatialTranscriptomics.visualization.opacity') }}
              <span class="value-display">{{ opacity.toFixed(1) }}</span>
            </label>
            <el-slider
              v-model="opacity"
              :min="0.1"
              :max="1.0"
              :step="0.1"
              @change="updateVisualization"
            />
          </div>

          <div class="control-group">
            <el-checkbox v-model="showLabels" @change="updateVisualization">
              {{ $t('spatialTranscriptomics.visualization.showLabels') }}
            </el-checkbox>
          </div>

          <div class="control-group">
            <el-checkbox v-model="showOutlines" @change="updateVisualization">
              {{ $t('spatialTranscriptomics.visualization.showOutlines') }}
            </el-checkbox>
          </div>
        </el-card>

        <!-- 基因表达筛选 -->
        <el-card class="control-section" shadow="never">
          <template #header>
            <div class="section-title">
              <Icon name="search" size="sm" class="section-icon" />
              {{ $t('spatialTranscriptomics.filter.title') }}
            </div>
          </template>

          <div class="control-group">
            <label class="control-label">{{ $t('spatialTranscriptomics.filter.searchGene') }}</label>
            <el-input
              v-model="searchGene"
              :placeholder="$t('spatialTranscriptomics.filter.searchPlaceholder')"
              clearable
              @input="handleGeneSearch"
            />
          </div>

          <div class="control-group">
            <label class="control-label">{{ $t('spatialTranscriptomics.filter.selectedGenes') }}</label>
            <div class="gene-list">
              <el-scrollbar height="150px">
                <div
                  v-for="gene in selectedGenes"
                  :key="gene"
                  class="gene-item"
                  @click="removeGene(gene)"
                >
                  <span>{{ gene }}</span>
                  <Icon name="close" size="sm" class="remove-icon" />
                </div>
                <div v-if="selectedGenes.length === 0" class="empty-gene">
                  {{ $t('spatialTranscriptomics.filter.noGenesSelected') }}
                </div>
              </el-scrollbar>
            </div>
          </div>
        </el-card>

        <!-- 统计信息 -->
        <el-card class="control-section" shadow="never">
          <template #header>
            <div class="section-title">
              <Icon name="document" size="sm" class="section-icon" />
              {{ $t('spatialTranscriptomics.stats.title') }}
            </div>
          </template>

          <div class="stats-item">
            <span class="stats-label">{{ $t('spatialTranscriptomics.stats.totalCells') }}</span>
            <span class="stats-value">{{ totalCells }}</span>
          </div>
          <div class="stats-item">
            <span class="stats-label">{{ $t('spatialTranscriptomics.stats.clusterCount') }}</span>
            <span class="stats-value">{{ actualClusterCount }}</span>
          </div>
          <div class="stats-item">
            <span class="stats-label">{{ $t('spatialTranscriptomics.stats.silhouetteScore') }}</span>
            <span class="stats-value">{{ silhouetteScore.toFixed(3) }}</span>
          </div>
          <div class="stats-item">
            <span class="stats-label">{{ $t('spatialTranscriptomics.stats.daviesBouldin') }}</span>
            <span class="stats-value">{{ daviesBouldin.toFixed(3) }}</span>
          </div>
        </el-card>
      </div>

      <!-- 右侧可视化区域 -->
      <div class="visualization-area">
        <el-tabs v-model="activeTab" @tab-change="handleTabChange">
          <el-tab-pane :label="$t('spatialTranscriptomics.tabs.spatial')" name="spatial">
            <div ref="spatialContainer" class="visualization-container"></div>
          </el-tab-pane>
          <el-tab-pane :label="$t('spatialTranscriptomics.tabs.network')" name="network">
            <div ref="networkContainer" class="visualization-container"></div>
          </el-tab-pane>
          <el-tab-pane :label="$t('spatialTranscriptomics.tabs.heatmap')" name="heatmap">
            <div ref="heatmapContainer" class="visualization-container"></div>
          </el-tab-pane>
          <el-tab-pane :label="$t('spatialTranscriptomics.tabs.dendrogram')" name="dendrogram">
            <div ref="dendrogramContainer" class="visualization-container"></div>
          </el-tab-pane>
          <el-tab-pane :label="$t('spatialTranscriptomics.tabs.umap')" name="umap">
            <div ref="umapContainer" class="visualization-container"></div>
          </el-tab-pane>
        </el-tabs>
      </div>
    </div>

    <!-- 底部基因表达面板 -->
    <div class="gene-expression-panel" v-if="selectedGenes.length > 0">
      <div class="panel-header">
        <h3>{{ $t('spatialTranscriptomics.heatmap.expression') }}</h3>
        <el-button size="small" @click="clearSelectedGenes">
          {{ $t('common.clear') }}
        </el-button>
      </div>
      <div ref="geneExpressionContainer" class="gene-expression-chart"></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, nextTick, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import * as echarts from 'echarts'
import Icon from '../components/common/Icon.vue'
import { ElMessage } from 'element-plus'

const { t } = useI18n()

// 数据类型定义
interface Cell {
  id: string
  x: number
  y: number
  cluster: number
  expression: { [gene: string]: number }
}

// 响应式数据
const selectedAlgorithm = ref('kmeans')
const clusterCount = ref(8)
const resolution = ref(0.8)
const colorScheme = ref('viridis')
const pointSize = ref(4)
const opacity = ref(0.7)
const showLabels = ref(false)
const showOutlines = ref(true)
const searchGene = ref('')
const selectedGenes = ref<string[]>([])
const activeTab = ref('spatial')

// 图表实例
const spatialContainer = ref<HTMLElement | null>(null)
const networkContainer = ref<HTMLElement | null>(null)
const heatmapContainer = ref<HTMLElement | null>(null)
const dendrogramContainer = ref<HTMLElement | null>(null)
const umapContainer = ref<HTMLElement | null>(null)
const geneExpressionContainer = ref<HTMLElement | null>(null)

let spatialChart: echarts.ECharts | null = null
let networkChart: echarts.ECharts | null = null
let heatmapChart: echarts.ECharts | null = null
let dendrogramChart: echarts.ECharts | null = null
let umapChart: echarts.ECharts | null = null
let geneExpressionChart: echarts.ECharts | null = null

// 数据
const cells = ref<Cell[]>([])
const clusters = ref<number[]>([])
const geneList = ref<string[]>([])

// 统计信息
const totalCells = computed(() => cells.value.length)
const actualClusterCount = computed(() => new Set(clusters.value).size)
const silhouetteScore = ref(0.65)
const daviesBouldin = ref(0.42)

// 选项数据
const algorithms = [
  { label: 'K-means', value: 'kmeans' },
  { label: '层次聚类', value: 'hierarchical' },
  { label: 'Leiden', value: 'leiden' },
  { label: 'DBSCAN', value: 'dbscan' }
]

const colorSchemes = [
  { label: 'Viridis', value: 'viridis' },
  { label: 'Plasma', value: 'plasma' },
  { label: 'Set3', value: 'set3' },
  { label: 'Tab20', value: 'tab20' }
]

// 生成模拟数据
function generateSampleData() {
  const numCells = 2000
  const numGenes = 50
  const genes: string[] = []
  
  // 生成基因列表
  const genePrefixes = ['ACT', 'GAPDH', 'TP53', 'MYC', 'EGFR', 'VIM', 'CDH1', 'FN1', 'COL1A1', 'TUBB3']
  for (let i = 0; i < numGenes; i++) {
    const prefix = genePrefixes[i % genePrefixes.length]
    genes.push(`${prefix}_${Math.floor(i / genePrefixes.length) + 1}`)
  }
  geneList.value = genes

  // 生成细胞数据
  const newCells: Cell[] = []
  const newClusters: number[] = []
  
  // 创建8个聚类区域
  const clusterCenters = [
    { x: 200, y: 200, cluster: 0 },
    { x: 600, y: 200, cluster: 1 },
    { x: 400, y: 400, cluster: 2 },
    { x: 800, y: 400, cluster: 3 },
    { x: 300, y: 600, cluster: 4 },
    { x: 700, y: 600, cluster: 5 },
    { x: 500, y: 800, cluster: 6 },
    { x: 900, y: 800, cluster: 7 }
  ]

  for (let i = 0; i < numCells; i++) {
    const center = clusterCenters[i % clusterCenters.length]
    const cluster = center.cluster
    
    // 在聚类中心周围随机分布
    const x = center.x + (Math.random() - 0.5) * 150
    const y = center.y + (Math.random() - 0.5) * 150
    
    // 生成表达数据（不同聚类有不同的表达模式）
    const expression: { [gene: string]: number } = {}
    genes.forEach((gene, idx) => {
      // 每个聚类有特定的高表达基因
      const clusterGeneIdx = (cluster * 5 + idx) % genes.length
      const baseExpr = cluster === Math.floor(clusterGeneIdx / 5) ? 5 + Math.random() * 5 : Math.random() * 3
      expression[gene] = Math.max(0, baseExpr + (Math.random() - 0.5) * 2)
    })
    
    newCells.push({
      id: `cell_${i}`,
      x,
      y,
      cluster,
      expression
    })
    newClusters.push(cluster)
  }
  
  cells.value = newCells
  clusters.value = newClusters
}

// 获取聚类颜色
function getClusterColor(clusterId: number, scheme: string = colorScheme.value): string {
  const schemes: { [key: string]: string[] } = {
    viridis: [
      '#440154', '#482777', '#3f4a8a', '#31678e', '#26838f',
      '#1f9d8a', '#6cce5a', '#b6de2b', '#fee825'
    ],
    plasma: [
      '#0d0887', '#46039f', '#7201a8', '#9c179e', '#bd3786',
      '#d8576b', '#ed7953', '#fb9f3a', '#f0f921'
    ],
    set3: [
      '#8dd3c7', '#ffffb3', '#bebada', '#fb8072', '#80b1d3',
      '#fdb462', '#b3de69', '#fccde5', '#d9d9d9'
    ],
    tab20: [
      '#1f77b4', '#aec7e8', '#ff7f0e', '#ffbb78', '#2ca02c',
      '#98df8a', '#d62728', '#ff9896', '#9467bd'
    ]
  }
  
  const colors = schemes[scheme] || schemes.viridis
  return colors[clusterId % colors.length]
}

// 初始化空间分布图
function initSpatialChart() {
  if (!spatialContainer.value) return

  spatialChart = echarts.init(spatialContainer.value)

  // 按聚类分组数据
  const clusterData: { [key: number]: number[][] } = {}
  cells.value.forEach(cell => {
    if (!clusterData[cell.cluster]) {
      clusterData[cell.cluster] = []
    }
    clusterData[cell.cluster].push([cell.x, cell.y, cell.cluster])
  })

  const series = Object.keys(clusterData).map(clusterId => {
    const id = parseInt(clusterId)
    return {
      name: `${t('spatialTranscriptomics.cluster')} ${id}`,
      type: 'scatter' as const,
      data: clusterData[id],
      symbolSize: pointSize.value,
      itemStyle: {
        color: getClusterColor(id),
        opacity: opacity.value
      },
      label: {
        show: showLabels.value,
        position: 'top' as const,
        fontSize: 10
      }
    }
  })

  const option: echarts.EChartsOption = {
    title: {
      text: t('spatialTranscriptomics.tabs.spatial'),
      left: 'center'
    },
    tooltip: {
      trigger: 'item',
      formatter: (params: any) => {
        const cell = cells.value.find(c => c.x === params.value[0] && c.y === params.value[1])
        if (cell) {
          return `${t('spatialTranscriptomics.tooltip.cell')}: ${cell.id}<br/>${t('spatialTranscriptomics.tooltip.cluster')}: ${cell.cluster}`
        }
        return ''
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
    legend: {
      data: series.map(s => s.name),
      bottom: 10,
      type: 'scroll'
    },
    series: series
  }

  spatialChart.setOption(option)

  // 添加点击事件
  spatialChart.on('click', (params: any) => {
    if (params.seriesType === 'scatter') {
      const cell = cells.value.find(c => c.x === params.value[0] && c.y === params.value[1])
      if (cell) {
        // 可以在这里显示细胞详细信息
        ElMessage.info(`${t('spatialTranscriptomics.tooltip.cell')}: ${cell.id}, ${t('spatialTranscriptomics.tooltip.cluster')}: ${cell.cluster}`)
      }
    }
  })
}

// 初始化聚类网络图
function initNetworkChart() {
  if (!networkContainer.value) return

  networkChart = echarts.init(networkContainer.value)

  // 计算聚类中心
  const clusterCenters: { [key: number]: { x: number, y: number, count: number } } = {}
  cells.value.forEach(cell => {
    if (!clusterCenters[cell.cluster]) {
      clusterCenters[cell.cluster] = { x: 0, y: 0, count: 0 }
    }
    clusterCenters[cell.cluster].x += cell.x
    clusterCenters[cell.cluster].y += cell.y
    clusterCenters[cell.cluster].count += 1
  })

  Object.keys(clusterCenters).forEach(id => {
    const center = clusterCenters[parseInt(id)]
    center.x /= center.count
    center.y /= center.count
  })

  // 生成节点和边
  const nodes = Object.keys(clusterCenters).map(id => {
    const clusterId = parseInt(id)
    const center = clusterCenters[clusterId]
    return {
      id: `cluster_${clusterId}`,
      name: `${t('spatialTranscriptomics.cluster')} ${clusterId}`,
      value: center.count,
      x: center.x,
      y: center.y,
      symbolSize: Math.sqrt(center.count) * 2,
      itemStyle: {
        color: getClusterColor(clusterId)
      }
    }
  })

  // 生成聚类之间的连接（基于空间距离）
  const links: any[] = []
  const clusterIds = Object.keys(clusterCenters).map(Number)
  for (let i = 0; i < clusterIds.length; i++) {
    for (let j = i + 1; j < clusterIds.length; j++) {
      const c1 = clusterCenters[clusterIds[i]]
      const c2 = clusterCenters[clusterIds[j]]
      const distance = Math.sqrt(Math.pow(c1.x - c2.x, 2) + Math.pow(c1.y - c2.y, 2))
      if (distance < 300) {
        links.push({
          source: `cluster_${clusterIds[i]}`,
          target: `cluster_${clusterIds[j]}`,
          value: 1 / (1 + distance / 100),
          lineStyle: {
            width: 2,
            opacity: 0.5
          }
        })
      }
    }
  }

  const option: echarts.EChartsOption = {
    title: {
      text: t('spatialTranscriptomics.tabs.network'),
      left: 'center'
    },
    tooltip: {
      trigger: 'item',
      formatter: (params: any) => {
        if (params.dataType === 'node') {
          return `${params.data.name}<br/>${t('spatialTranscriptomics.tooltip.cells')}: ${params.data.value}`
        }
        return `${params.data.source} → ${params.data.target}<br/>${t('spatialTranscriptomics.tooltip.similarity')}: ${params.data.value.toFixed(2)}`
      }
    },
    series: [
      {
        type: 'graph',
        layout: 'none',
        data: nodes,
        links: links,
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
        }
      }
    ]
  }

  networkChart.setOption(option)
}

// 初始化热图
// 简单的层次聚类算法（使用距离矩阵）
function hierarchicalClustering(items: any[], distanceFn: (a: any, b: any) => number): any[] {
  if (items.length <= 1) return items

  const clusters = items.map((item, idx) => ({
    id: idx,
    items: [item],
    height: 0
  }))

  const mergeHistory: Array<{ left: number, right: number, height: number }> = []

  while (clusters.length > 1) {
    let minDist = Infinity
    let mergeI = 0
    let mergeJ = 0

    // 找到距离最近的两个聚类
    for (let i = 0; i < clusters.length; i++) {
      for (let j = i + 1; j < clusters.length; j++) {
        // 计算两个聚类之间的平均距离
        let totalDist = 0
        let count = 0
        clusters[i].items.forEach(item1 => {
          clusters[j].items.forEach(item2 => {
            totalDist += distanceFn(item1, item2)
            count++
          })
        })
        const avgDist = totalDist / count

        if (avgDist < minDist) {
          minDist = avgDist
          mergeI = i
          mergeJ = j
        }
      }
    }

    // 合并聚类
    const merged = {
      id: clusters.length,
      items: [...clusters[mergeI].items, ...clusters[mergeJ].items],
      height: minDist,
      left: clusters[mergeI],
      right: clusters[mergeJ]
    }

    mergeHistory.push({
      left: mergeI,
      right: mergeJ,
      height: minDist
    })

    clusters.splice(mergeJ, 1)
    clusters.splice(mergeI, 1)
    clusters.push(merged)
  }

  return mergeHistory
}

// 根据层次聚类结果获取排序后的索引
function getOrderedIndices(items: any[], distanceFn: (a: any, b: any) => number): number[] {
  const mergeHistory = hierarchicalClustering(items, distanceFn)
  const n = items.length

  // 从合并历史中提取顺序
  const clusterMap = new Map<number, number[]>()
  for (let i = 0; i < n; i++) {
    clusterMap.set(i, [i])
  }

  mergeHistory.forEach((merge, mergeIdx) => {
    const leftItems = clusterMap.get(merge.left) || []
    const rightItems = clusterMap.get(merge.right) || []
    clusterMap.set(n + mergeIdx, [...leftItems, ...rightItems])
  })

  // 获取最终顺序
  const finalCluster = clusterMap.get(clusterMap.size - 1)
  return finalCluster || Array.from({ length: n }, (_, i) => i)
}

function initHeatmapChart() {
  if (!heatmapContainer.value) return

  heatmapChart = echarts.init(heatmapContainer.value)

  // 计算每个聚类的平均表达
  const clusterExpression: { [key: number]: { [gene: string]: number } } = {}
  const clusterSizes: { [key: number]: number } = {}

  cells.value.forEach(cell => {
    if (!clusterExpression[cell.cluster]) {
      clusterExpression[cell.cluster] = {}
      clusterSizes[cell.cluster] = 0
    }
    clusterSizes[cell.cluster] += 1
    geneList.value.forEach(gene => {
      if (!clusterExpression[cell.cluster][gene]) {
        clusterExpression[cell.cluster][gene] = 0
      }
      clusterExpression[cell.cluster][gene] += cell.expression[gene] || 0
    }
    )
  })

  // 计算平均值
  Object.keys(clusterExpression).forEach(clusterId => {
    const id = parseInt(clusterId)
    geneList.value.forEach(gene => {
      clusterExpression[id][gene] /= clusterSizes[id]
    })
  })

  // 选择前20个基因
  const topGenes = geneList.value.slice(0, 20)
  const clusterIds = Array.from(new Set(clusters.value)).sort((a, b) => a - b)

  // 对聚类进行层次聚类排序
  const clusterVectors = clusterIds.map(clusterId => {
    return topGenes.map(gene => clusterExpression[clusterId][gene] || 0)
  })
  const clusterOrder = getOrderedIndices(clusterVectors, (a, b) => {
    // 欧氏距离
    let sum = 0
    for (let i = 0; i < a.length; i++) {
      sum += Math.pow(a[i] - b[i], 2)
    }
    return Math.sqrt(sum)
  })
  const orderedClusterIds = clusterOrder.map(idx => clusterIds[idx])

  // 对基因进行层次聚类排序
  const geneVectors = topGenes.map(gene => {
    return clusterIds.map(clusterId => clusterExpression[clusterId][gene] || 0)
  })
  const geneOrder = getOrderedIndices(geneVectors, (a, b) => {
    let sum = 0
    for (let i = 0; i < a.length; i++) {
      sum += Math.pow(a[i] - b[i], 2)
    }
    return Math.sqrt(sum)
  })
  const orderedGenes = geneOrder.map(idx => topGenes[idx])

  // 生成热力图数据（按排序后的顺序）
  const data: number[][] = []
  orderedGenes.forEach((gene, geneIdx) => {
    orderedClusterIds.forEach((clusterId, clusterIdx) => {
      data.push([clusterIdx, geneIdx, clusterExpression[clusterId][gene] || 0])
    })
  })

  // 生成层次聚类树的数据（用于绘制树状图）
  const dendrogramHeight = 100
  const dendrogramWidth = 80

  // 构建聚类树状图 - 使用graphic组件绘制
  const buildDendrogram = (mergeHistory: Array<{ left: number, right: number, height: number }>, itemCount: number, isHorizontal: boolean) => {
    const lines: any[] = []
    const maxHeight = Math.max(...mergeHistory.map(m => m.height), 1)
    
    // 计算每个叶子节点的位置
    const leafPositions = new Map<number, number>()
    const itemSpacing = isHorizontal ? dendrogramWidth / itemCount : dendrogramHeight / itemCount
    
    // 初始化叶子节点位置
    for (let i = 0; i < itemCount; i++) {
      leafPositions.set(i, i * itemSpacing)
    }
    
    // 记录每个合并后的聚类位置
    let nextClusterId = itemCount
    const clusterPositions = new Map<number, number>()
    
    mergeHistory.forEach((merge) => {
      const leftPos = leafPositions.get(merge.left) ?? clusterPositions.get(merge.left) ?? 0
      const rightPos = leafPositions.get(merge.right) ?? clusterPositions.get(merge.right) ?? 0
      const centerPos = (leftPos + rightPos) / 2
      const height = (merge.height / maxHeight) * (isHorizontal ? dendrogramWidth : dendrogramHeight)
      
      if (isHorizontal) {
        // 水平树状图（用于聚类，在上方）
        lines.push({
          type: 'line',
          shape: { x1: 0, y1: leftPos, x2: height, y2: leftPos },
          style: { stroke: '#666', lineWidth: 1.5 }
        })
        lines.push({
          type: 'line',
          shape: { x1: 0, y1: rightPos, x2: height, y2: rightPos },
          style: { stroke: '#666', lineWidth: 1.5 }
        })
        lines.push({
          type: 'line',
          shape: { x1: height, y1: leftPos, x2: height, y2: rightPos },
          style: { stroke: '#666', lineWidth: 1.5 }
        })
      } else {
        // 垂直树状图（用于基因，在左侧）
        lines.push({
          type: 'line',
          shape: { x1: leftPos, y1: 0, x2: leftPos, y2: height },
          style: { stroke: '#666', lineWidth: 1.5 }
        })
        lines.push({
          type: 'line',
          shape: { x1: rightPos, y1: 0, x2: rightPos, y2: height },
          style: { stroke: '#666', lineWidth: 1.5 }
        })
        lines.push({
          type: 'line',
          shape: { x1: leftPos, y1: height, x2: rightPos, y2: height },
          style: { stroke: '#666', lineWidth: 1.5 }
        })
      }
      
      clusterPositions.set(nextClusterId, centerPos)
      nextClusterId++
    })
    
    return lines
  }

  // 聚类树状图数据
  const clusterMergeHistory = hierarchicalClustering(clusterVectors, (a, b) => {
    let sum = 0
    for (let i = 0; i < a.length; i++) {
      sum += Math.pow(a[i] - b[i], 2)
    }
    return Math.sqrt(sum)
  })
  const clusterDendrogramData = buildDendrogram(clusterMergeHistory, clusterIds.length, true)

  // 基因树状图数据
  const geneMergeHistory = hierarchicalClustering(geneVectors, (a, b) => {
    let sum = 0
    for (let i = 0; i < a.length; i++) {
      sum += Math.pow(a[i] - b[i], 2)
    }
    return Math.sqrt(sum)
  })
  const geneDendrogramData = buildDendrogram(geneMergeHistory, topGenes.length, false)

  const option: echarts.EChartsOption = {
    title: {
      text: t('spatialTranscriptomics.tabs.heatmap') + ' (层次聚类)',
      left: 'center',
      top: 10
    },
    tooltip: {
      position: 'top',
      formatter: (params: any) => {
        const clusterId = orderedClusterIds[params.value[0]]
        const gene = orderedGenes[params.value[1]]
        return `${t('spatialTranscriptomics.cluster')} ${clusterId}<br/>${gene}<br/>${t('spatialTranscriptomics.heatmap.expression')}: ${params.value[2].toFixed(2)}`
      }
    },
    grid: {
      left: dendrogramWidth + 20,
      right: 50,
      top: dendrogramHeight + 60,
      bottom: 80,
      height: 'auto'
    },
    xAxis: {
      type: 'category',
      data: orderedClusterIds.map(id => `${t('spatialTranscriptomics.cluster')} ${id}`),
      splitArea: {
        show: true
      },
      axisLabel: {
        rotate: 45
      }
    },
    yAxis: {
      type: 'category',
      data: orderedGenes,
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
      bottom: 20,
      inRange: {
        color: ['#440154', '#21918c', '#fde725']
      }
    },
    graphic: [
      // 聚类树状图（上方）
      {
        type: 'group',
        left: dendrogramWidth + 20,
        top: 60,
        children: clusterDendrogramData
      },
      // 基因树状图（左侧）
      {
        type: 'group',
        left: 20,
        top: dendrogramHeight + 60,
        children: geneDendrogramData
      }
    ],
    series: [
      {
        name: t('spatialTranscriptomics.heatmap.expression'),
        type: 'heatmap',
        data: data,
        label: {
          show: false
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

// 初始化层次聚类树
function initDendrogramChart() {
  if (!dendrogramContainer.value) return

  dendrogramChart = echarts.init(dendrogramContainer.value)

  // 生成模拟的层次聚类树数据
  const clusterIds = Array.from(new Set(clusters.value)).sort((a, b) => a - b)
  const leaves = clusterIds.map(id => ({
    name: `${t('spatialTranscriptomics.cluster')} ${id}`,
    value: cells.value.filter(c => c.cluster === id).length
  }))

  // 构建树结构（简化版）
  const treeData = {
    name: 'Root',
    children: [
      {
        name: 'Group1',
        children: leaves.slice(0, 4).map(l => ({ name: l.name, value: l.value }))
      },
      {
        name: 'Group2',
        children: leaves.slice(4).map(l => ({ name: l.name, value: l.value }))
      }
    ]
  }

  const option: echarts.EChartsOption = {
    title: {
      text: t('spatialTranscriptomics.tabs.dendrogram'),
      left: 'center'
    },
    tooltip: {
      trigger: 'item',
      triggerOn: 'mousemove'
    },
    series: [
      {
        type: 'tree',
        data: [treeData],
        top: '5%',
        left: '7%',
        bottom: '5%',
        right: '20%',
        symbolSize: 7,
        label: {
          position: 'left',
          verticalAlign: 'middle',
          align: 'right',
          fontSize: 12
        },
        leaves: {
          label: {
            position: 'right',
            verticalAlign: 'middle',
            align: 'left'
          }
        },
        emphasis: {
          focus: 'descendant'
        },
        expandAndCollapse: true,
        animationDuration: 550,
        animationDurationUpdate: 750
      }
    ]
  }

  dendrogramChart.setOption(option)
}

// 初始化UMAP降维图
function initUmapChart() {
  if (!umapContainer.value) return

  umapChart = echarts.init(umapContainer.value)

  // 生成模拟UMAP坐标（基于聚类）
  const umapData: { [key: number]: number[][] } = {}
  cells.value.forEach(cell => {
    if (!umapData[cell.cluster]) {
      umapData[cell.cluster] = []
    }
    // 模拟UMAP坐标（每个聚类形成一个区域）
    const baseX = (cell.cluster % 3) * 3 - 3
    const baseY = Math.floor(cell.cluster / 3) * 3 - 3
    umapData[cell.cluster].push([
      baseX + (Math.random() - 0.5) * 2,
      baseY + (Math.random() - 0.5) * 2,
      cell.cluster
    ])
  })

  const series = Object.keys(umapData).map(clusterId => {
    const id = parseInt(clusterId)
    return {
      name: `${t('spatialTranscriptomics.cluster')} ${id}`,
      type: 'scatter' as const,
      data: umapData[id],
      symbolSize: pointSize.value,
      itemStyle: {
        color: getClusterColor(id),
        opacity: opacity.value
      }
    }
  })

  const option: echarts.EChartsOption = {
    title: {
      text: 'UMAP ' + t('spatialTranscriptomics.tabs.umap'),
      left: 'center'
    },
    tooltip: {
      trigger: 'item',
      formatter: (params: any) => {
        return `${t('spatialTranscriptomics.tooltip.cluster')}: ${params.value[2]}`
      }
    },
    xAxis: {
      type: 'value',
      name: 'UMAP 1',
      scale: true
    },
    yAxis: {
      type: 'value',
      name: 'UMAP 2',
      scale: true
    },
    legend: {
      data: series.map(s => s.name),
      bottom: 10,
      type: 'scroll'
    },
    series: series
  }

  umapChart.setOption(option)
}

// 初始化基因表达图
function initGeneExpressionChart() {
  if (!geneExpressionContainer.value || selectedGenes.value.length === 0) return

  geneExpressionChart = echarts.init(geneExpressionContainer.value)

  // 计算每个聚类中每个基因的平均表达
  const clusterIds = Array.from(new Set(clusters.value)).sort((a, b) => a - b)
  const data: number[][] = []

  selectedGenes.value.forEach((gene, geneIdx) => {
    clusterIds.forEach((clusterId, clusterIdx) => {
      const clusterCells = cells.value.filter(c => c.cluster === clusterId)
      const avgExpr = clusterCells.length > 0
        ? clusterCells.reduce((sum, c) => sum + (c.expression[gene] || 0), 0) / clusterCells.length
        : 0
      data.push([clusterIdx, geneIdx, avgExpr])
    })
  })

  const option: echarts.EChartsOption = {
    title: {
      text: t('spatialTranscriptomics.heatmap.expression'),
      left: 'center'
    },
    tooltip: {
      position: 'top',
      formatter: (params: any) => {
        const clusterId = clusterIds[params.value[0]]
        const gene = selectedGenes.value[params.value[1]]
        return `${t('spatialTranscriptomics.cluster')} ${clusterId}<br/>${gene}<br/>${t('spatialTranscriptomics.heatmap.expression')}: ${params.value[2].toFixed(2)}`
      }
    },
    grid: {
      height: '70%',
      top: '15%'
    },
    xAxis: {
      type: 'category',
      data: clusterIds.map(id => `${t('spatialTranscriptomics.cluster')} ${id}`),
      splitArea: {
        show: true
      }
    },
    yAxis: {
      type: 'category',
      data: selectedGenes.value,
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
        name: t('spatialTranscriptomics.heatmap.expression'),
        type: 'heatmap',
        data: data,
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

  geneExpressionChart.setOption(option)
}

// 事件处理
function handleAlgorithmChange() {
  ElMessage.info(t('spatialTranscriptomics.messages.algorithmChanged'))
}

function updateClustering() {
  // 这里可以触发重新聚类
  // 目前只是更新可视化
  updateVisualization()
}

function runClustering() {
  ElMessage.success(t('spatialTranscriptomics.messages.clusteringCompleted'))
  // 重新生成聚类结果
  generateSampleData()
  updateAllCharts()
}

function updateVisualization() {
  updateAllCharts()
}

function handleTabChange(tab: string) {
  nextTick(() => {
    if (tab === 'spatial' && spatialContainer.value) {
      initSpatialChart()
    } else if (tab === 'network' && networkContainer.value) {
      initNetworkChart()
    } else if (tab === 'heatmap' && heatmapContainer.value) {
      initHeatmapChart()
    } else if (tab === 'dendrogram' && dendrogramContainer.value) {
      initDendrogramChart()
    } else if (tab === 'umap' && umapContainer.value) {
      initUmapChart()
    }
  })
}

function handleGeneSearch() {
  // 搜索功能可以在下拉框中实现
}

function removeGene(gene: string) {
  const index = selectedGenes.value.indexOf(gene)
  if (index > -1) {
    selectedGenes.value.splice(index, 1)
    nextTick(() => {
      if (selectedGenes.value.length > 0) {
        initGeneExpressionChart()
      } else {
        geneExpressionChart?.dispose()
        geneExpressionChart = null
      }
    })
  }
}

function clearSelectedGenes() {
  selectedGenes.value = []
  geneExpressionChart?.dispose()
  geneExpressionChart = null
}

function updateAllCharts() {
  if (activeTab.value === 'spatial') {
    initSpatialChart()
  } else if (activeTab.value === 'network') {
    initNetworkChart()
  } else if (activeTab.value === 'heatmap') {
    initHeatmapChart()
  } else if (activeTab.value === 'dendrogram') {
    initDendrogramChart()
  } else if (activeTab.value === 'umap') {
    initUmapChart()
  }
  
  if (selectedGenes.value.length > 0) {
    initGeneExpressionChart()
  }
}

function loadSampleData() {
  generateSampleData()
  updateAllCharts()
  ElMessage.success(t('spatialTranscriptomics.messages.sampleLoaded'))
}

function exportImage() {
  const currentChart = activeTab.value === 'spatial' ? spatialChart
    : activeTab.value === 'network' ? networkChart
    : activeTab.value === 'heatmap' ? heatmapChart
    : activeTab.value === 'dendrogram' ? dendrogramChart
    : umapChart

  if (currentChart) {
    const url = currentChart.getDataURL({
      type: 'png',
      pixelRatio: 2,
      backgroundColor: '#fff'
    })
    const link = document.createElement('a')
    link.download = `spatial-transcriptomics-${activeTab.value}.png`
    link.href = url
    link.click()
    ElMessage.success(t('spatialTranscriptomics.messages.exported'))
  }
}

// 窗口大小调整
function handleResize() {
  spatialChart?.resize()
  networkChart?.resize()
  heatmapChart?.resize()
  dendrogramChart?.resize()
  umapChart?.resize()
  geneExpressionChart?.resize()
}

onMounted(() => {
  generateSampleData()
  nextTick(() => {
    initSpatialChart()
    window.addEventListener('resize', handleResize)
  })
})

onUnmounted(() => {
  spatialChart?.dispose()
  networkChart?.dispose()
  heatmapChart?.dispose()
  dendrogramChart?.dispose()
  umapChart?.dispose()
  geneExpressionChart?.dispose()
  window.removeEventListener('resize', handleResize)
})

// 监听选中基因变化
watch(selectedGenes, (newGenes) => {
  if (newGenes.length > 0) {
    nextTick(() => {
      initGeneExpressionChart()
    })
  }
}, { deep: true })
</script>

<style scoped>
.spatial-transcriptomics-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 16px;
  gap: 16px;
  background-color: #f5f7fa;
}

.header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
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
  color: #667eea;
  display: flex;
  align-items: center;
  gap: 8px;
}

.section-icon {
  color: #667eea;
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
  color: #667eea;
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

.remove-icon {
  color: #999;
  cursor: pointer;
}

.empty-gene {
  padding: 20px;
  text-align: center;
  color: #999;
  font-size: 0.85rem;
}

.stats-item {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}

.stats-item:last-child {
  border-bottom: none;
}

.stats-label {
  font-size: 0.9rem;
  color: #666;
}

.stats-value {
  font-size: 0.9rem;
  font-weight: 600;
  color: #667eea;
}

.analyze-btn {
  width: 100%;
  margin-top: 12px;
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
  min-height: 500px;
  width: 100%;
}

.gene-expression-panel {
  background: white;
  border-radius: 10px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  padding: 16px;
  margin-top: 16px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.panel-header h3 {
  margin: 0;
  font-size: 1.1rem;
  color: #333;
}

.gene-expression-chart {
  width: 100%;
  height: 400px;
}

:deep(.el-card__header) {
  padding: 16px;
  border-bottom: 1px solid #eaeaea;
}

:deep(.el-card__body) {
  padding: 16px;
}
</style>

