<template>
  <div class="dge-visualization">
    <!-- 控制面板 -->
    <div class="control-panel">
      <div class="panel-section">
        <h4>{{ t('dge.title') }}</h4>
        <p class="subtitle">{{ t('dge.subtitle') }}</p>
      </div>
      
      <div class="panel-section">
        <div class="form-group">
          <label>{{ t('dge.log2fcThreshold') }}</label>
          <input v-model.number="log2fcThreshold" type="number" step="0.1" min="0" class="form-input" />
        </div>
        <div class="form-group">
          <label>{{ t('dge.fdrThreshold') }}</label>
          <input v-model.number="fdrThreshold" type="number" step="0.01" min="0" max="1" class="form-input" />
        </div>
        <div class="form-group">
          <label>{{ t('dge.topN') }}</label>
          <input v-model.number="topN" type="number" step="10" min="10" class="form-input" />
        </div>
      </div>

      <div class="panel-section">
        <div class="form-group checkbox-group">
          <label>
            <input v-model="showThresholdLines" type="checkbox" />
            {{ t('dge.showThresholdLines') }}
          </label>
        </div>
        <div class="form-group checkbox-group">
          <label>
            <input v-model="showGeneLabels" type="checkbox" />
            {{ t('dge.showGeneLabels') }}
          </label>
        </div>
      </div>

      <div class="panel-section stats-section">
        <div class="stat-card">
          <div class="stat-label">{{ t('dge.totalGenes') }}</div>
          <div class="stat-value">{{ rows.length }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">{{ t('dge.significantGenes') }}</div>
          <div class="stat-value">{{ sigRows.length }}</div>
        </div>
        <div class="stat-card up">
          <div class="stat-label">{{ t('dge.upregulated') }}</div>
          <div class="stat-value">{{ upCount }}</div>
        </div>
        <div class="stat-card down">
          <div class="stat-label">{{ t('dge.downregulated') }}</div>
          <div class="stat-value">{{ downCount }}</div>
        </div>
      </div>

      <button class="refresh-btn" @click="loadData" :disabled="loading">
        {{ loading ? t('dge.loading') : t('dge.refreshData') }}
      </button>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="status-container">
      <div class="loading-spinner"></div>
      <p>{{ t('dge.loadingData') }}</p>
    </div>

    <!-- 错误状态 -->
    <div v-else-if="error" class="status-container error">
      <p>{{ error }}</p>
      <button @click="loadData" class="retry-btn">{{ t('dge.retry') }}</button>
    </div>

    <!-- 主内容 -->
    <div v-else-if="rows.length > 0" class="content">
      <!-- 标签页 -->
      <div class="tabs">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          class="tab-btn"
          :class="{ active: activeTab === tab.id }"
          @click="activeTab = tab.id"
        >
          {{ tab.label }}
        </button>
      </div>

      <!-- 标签页内容 -->
      <div class="tab-content">
        <!-- 火山图 -->
        <div v-show="activeTab === 'volcano'" class="chart-panel">
          <div ref="volcanoRef" class="chart"></div>
        </div>

        <!-- Top 基因表 -->
        <div v-show="activeTab === 'table'" class="table-panel">
          <table class="data-table">
            <thead>
              <tr>
                <th>{{ t('dge.table.gene') }}</th>
                <th>{{ t('dge.table.group') }}</th>
                <th>{{ t('dge.table.log2fc') }}</th>
                <th>{{ t('dge.table.pvalue') }}</th>
                <th>{{ t('dge.table.fdr') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in topRows" :key="row.gene">
                <td class="gene-name">{{ row.gene }}</td>
                <td>{{ row.group || '-' }}</td>
                <td :class="row.logfoldchange > 0 ? 'positive' : 'negative'">
                  {{ row.logfoldchange.toFixed(3) }}
                </td>
                <td>{{ row.pval.toExponential(2) }}</td>
                <td>{{ row.pval_adj.toExponential(2) }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- 热图 -->
        <div v-show="activeTab === 'heatmap'" class="chart-panel">
          <div ref="heatmapRef" class="chart"></div>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else class="status-container">
      <p>{{ t('dge.noData') }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import * as echarts from 'echarts'
import Papa from 'papaparse'
import { downloadFileById } from '../../api/file'

const { t } = useI18n()

const props = defineProps<{
  fileId: string
}>()

// 状态
const loading = ref(false)
const error = ref<string | null>(null)
const rows = ref<any[]>([])
const activeTab = ref('volcano')

// 控制参数
const log2fcThreshold = ref(1)
const fdrThreshold = ref(0.05)
const topN = ref(30)
const showThresholdLines = ref(true)
const showGeneLabels = ref(false)

// 标签页配置
const tabs = computed(() => [
  { id: 'volcano', label: t('dge.tabs.volcano') },
  { id: 'table', label: t('dge.tabs.topGenes') },
  { id: 'heatmap', label: t('dge.tabs.heatmap') }
])

// 图表引用
const volcanoRef = ref<HTMLElement>()
const heatmapRef = ref<HTMLElement>()
let volcanoChart: echarts.ECharts | null = null
let heatmapChart: echarts.ECharts | null = null
let resizeObserver: ResizeObserver | null = null

// 计算属性
const sigRows = computed(() => 
  rows.value.filter(r => 
    r.pval_adj <= fdrThreshold.value &&
    Math.abs(r.logfoldchange) >= log2fcThreshold.value
  )
)

const upCount = computed(() => 
  sigRows.value.filter(r => r.logfoldchange > 0).length
)

const downCount = computed(() => 
  sigRows.value.filter(r => r.logfoldchange < 0).length
)

const topRows = computed(() => {
  return [...rows.value]
    .filter(r => r.pval_adj <= fdrThreshold.value)
    .sort((a, b) => a.pval_adj - b.pval_adj)
    .slice(0, topN.value)
})

const volcanoData = computed(() => {
  return rows.value.map(r => {
    const x = r.logfoldchange
    const y = r.pval_adj > 0 ? -Math.log10(r.pval_adj) : 0
    const isSig = r.pval_adj <= fdrThreshold.value && Math.abs(r.logfoldchange) >= log2fcThreshold.value
    const isUp = r.logfoldchange >= log2fcThreshold.value
    const isDown = r.logfoldchange <= -log2fcThreshold.value
    
    let color = '#999'
    if (isSig && isUp) color = '#e74c3c'
    else if (isSig && isDown) color = '#3498db'
    
    return {
      value: [x, y],
      itemStyle: { color },
      gene: r.gene,
      group: r.group
    }
  })
})

// 加载数据
async function loadData() {
  if (!props.fileId) {
    error.value = t('dge.missingFileId')
    return
  }

  loading.value = true
  error.value = null

  try {
    const blob = await downloadFileById(props.fileId)
    const text = await blob.text()
    
    const parsed = Papa.parse(text, {
      header: true,
      skipEmptyLines: true,
      dynamicTyping: true
    })

    rows.value = (parsed.data as any[])
      .map(row => ({
        gene: String(row.gene || row.genes || row.symbol || '').trim(),
        group: String(row.group || row.cluster || ''),
        logfoldchange: Number(row.logfoldchange || row.log2fc || row.logfc || 0),
        pval: Number(row.pval || row.p_value || row.pvalue || 0),
        pval_adj: Number(row.pval_adj || row.padj || row.fdr || 1)
      }))
      .filter(r => r.gene)

    // 等待 DOM 更新并确保图表容器已渲染
    await nextTick()
    setTimeout(() => {
      initCharts()
      updateCharts()
    }, 100)
  } catch (e: any) {
    console.error('加载失败:', e)
    error.value = e?.message || t('dge.loadFailed')
  } finally {
    loading.value = false
  }
}

// 初始化图表
function initCharts() {
  if (volcanoRef.value && !volcanoChart) {
    const width = volcanoRef.value.clientWidth
    const height = volcanoRef.value.clientHeight
    console.log('火山图容器尺寸:', width, height)
    if (width > 0 && height > 0) {
      volcanoChart = echarts.init(volcanoRef.value)
      // 初始化后立即调整大小
      setTimeout(() => {
        if (volcanoChart) {
          volcanoChart.resize()
        }
      }, 50)
    }
  }
  if (heatmapRef.value && !heatmapChart) {
    const width = heatmapRef.value.clientWidth
    const height = heatmapRef.value.clientHeight
    console.log('热图容器尺寸:', width, height)
    if (width > 0 && height > 0) {
      heatmapChart = echarts.init(heatmapRef.value)
      // 初始化后立即调整大小
      setTimeout(() => {
        if (heatmapChart) {
          heatmapChart.resize()
        }
      }, 50)
    }
  }
}

// 更新图表
function updateCharts() {
  updateVolcano()
  updateHeatmap()
}

function updateVolcano() {
  if (!volcanoChart) return

  const thresholdY = -Math.log10(fdrThreshold.value)
  const markLineData: any[] = []
  
  if (showThresholdLines.value) {
    markLineData.push(
      { xAxis: log2fcThreshold.value, lineStyle: { color: '#e74c3c', type: 'dashed' } },
      { xAxis: -log2fcThreshold.value, lineStyle: { color: '#3498db', type: 'dashed' } },
      { yAxis: thresholdY, lineStyle: { color: '#95a5a6', type: 'dashed' } }
    )
  }

  const topGenes = showGeneLabels.value 
    ? sigRows.value.slice(0, 10).map(r => r.gene)
    : []

  volcanoChart.setOption({
    tooltip: {
      trigger: 'item',
      formatter: (params: any) => {
        const d = params.data
        return `<b>${d.gene}</b><br/>` +
               `${t('dge.table.group')}: ${d.group || 'N/A'}<br/>` +
               `${t('dge.table.log2fc')}: ${params.value[0].toFixed(3)}<br/>` +
               `-log10(${t('dge.table.fdr')}): ${params.value[1].toFixed(3)}`
      }
    },
    legend: {
      data: [t('dge.legend.upregulated'), t('dge.legend.downregulated'), t('dge.legend.notSignificant')],
      top: 10,
      right: 20
    },
    grid: { left: 70, right: 40, top: 50, bottom: 70 },
    xAxis: {
      name: 'log2(Fold Change)',
      nameLocation: 'middle',
      nameGap: 40,
      nameTextStyle: { fontSize: 14, fontWeight: 'bold' },
      splitLine: { show: true, lineStyle: { color: '#ecf0f1', type: 'solid' } }
    },
    yAxis: {
      name: '-log10(FDR)',
      nameLocation: 'middle',
      nameGap: 50,
      nameTextStyle: { fontSize: 14, fontWeight: 'bold' },
      splitLine: { show: true, lineStyle: { color: '#ecf0f1', type: 'solid' } }
    },
    series: [{
      type: 'scatter',
      data: volcanoData.value,
      symbolSize: 6,
      markLine: markLineData.length > 0 ? {
        silent: true,
        symbol: 'none',
        data: markLineData,
        label: { show: false }
      } : undefined,
      label: {
        show: showGeneLabels.value,
        formatter: (params: any) => {
          return topGenes.includes(params.data.gene) ? params.data.gene : ''
        },
        position: 'top',
        fontSize: 10,
        color: '#2c3e50'
      }
    }]
  })
}

function updateHeatmap() {
  if (!heatmapChart || topRows.value.length === 0) return

  const genes = topRows.value.map(r => r.gene)
  const groups = [...new Set(rows.value.map(r => r.group).filter(Boolean))]
  
  const data: any[] = []
  genes.forEach((gene, i) => {
    groups.forEach((group, j) => {
      const row = rows.value.find(r => r.gene === gene && r.group === group)
      if (row) {
        data.push([j, i, row.logfoldchange])
      }
    })
  })

  heatmapChart.setOption({
    tooltip: {
      position: 'top',
      formatter: (p: any) => {
        return `${genes[p.data[1]]} / ${groups[p.data[0]]}<br/>${t('dge.table.log2fc')}: ${p.data[2].toFixed(2)}`
      }
    },
    grid: { left: 100, right: 30, top: 30, bottom: 100 },
    xAxis: {
      type: 'category',
      data: groups,
      axisLabel: { rotate: 45 }
    },
    yAxis: {
      type: 'category',
      data: genes
    },
    visualMap: {
      min: -3,
      max: 3,
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: 10,
      inRange: {
        color: ['#3498db', '#ecf0f1', '#e74c3c']
      }
    },
    series: [{
      type: 'heatmap',
      data,
      emphasis: {
        itemStyle: {
          shadowBlur: 10,
          shadowColor: 'rgba(0, 0, 0, 0.5)'
        }
      }
    }]
  })
}

// 监听参数变化
watch([log2fcThreshold, fdrThreshold, showThresholdLines, showGeneLabels], () => {
  updateVolcano()
})

watch(topN, () => {
  updateHeatmap()
})

// 监听标签页切换，确保图表已初始化
watch(activeTab, async (newTab) => {
  await nextTick()
  if (newTab === 'volcano' && !volcanoChart && volcanoRef.value) {
    initCharts()
    updateVolcano()
    // 为新初始化的图表设置 ResizeObserver
    if (resizeObserver && volcanoRef.value) {
      resizeObserver.observe(volcanoRef.value)
    }
  } else if (newTab === 'heatmap' && !heatmapChart && heatmapRef.value) {
    initCharts()
    updateHeatmap()
    // 为新初始化的图表设置 ResizeObserver
    if (resizeObserver && heatmapRef.value) {
      resizeObserver.observe(heatmapRef.value)
    }
  }
  // 切换标签页后立即调整图表大小
  setTimeout(() => handleResize(), 100)
})

// 生命周期
onMounted(() => {
  loadData()
  window.addEventListener('resize', handleResize)
  setupResizeObserver()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
  
  if (volcanoChart) {
    volcanoChart.dispose()
    volcanoChart = null
  }
  if (heatmapChart) {
    heatmapChart.dispose()
    heatmapChart = null
  }
})

function setupResizeObserver() {
  resizeObserver = new ResizeObserver(() => {
    handleResize()
  })
  
  if (volcanoRef.value) {
    resizeObserver.observe(volcanoRef.value)
  }
  if (heatmapRef.value) {
    resizeObserver.observe(heatmapRef.value)
  }
}

function handleResize() {
  if (volcanoChart) {
    volcanoChart.resize()
  }
  if (heatmapChart) {
    heatmapChart.resize()
  }
}
</script>

<style scoped>
.dge-visualization {
  display: flex;
  height: 100%;
  background: #f5f7fa;
  overflow: hidden;
}

/* 控制面板 */
.control-panel {
  width: 280px;
  background: white;
  border-right: 1px solid #e1e8ed;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.panel-section {
  padding: 20px;
  border-bottom: 1px solid #e1e8ed;
}

.panel-section h4 {
  margin: 0 0 5px 0;
  font-size: 16px;
  font-weight: 600;
  color: #2c3e50;
}

.subtitle {
  margin: 0;
  font-size: 12px;
  color: #95a5a6;
}

.form-group {
  margin-bottom: 15px;
}

.form-group:last-child {
  margin-bottom: 0;
}

.form-group label {
  display: block;
  margin-bottom: 6px;
  font-size: 13px;
  font-weight: 500;
  color: #34495e;
}

.form-input {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  font-size: 13px;
  transition: border-color 0.2s;
}

.form-input:focus {
  outline: none;
  border-color: #409eff;
}

.checkbox-group label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  user-select: none;
}

.checkbox-group input[type="checkbox"] {
  width: 16px;
  height: 16px;
  cursor: pointer;
}

/* 统计卡片 */
.stats-section {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.stat-card {
  padding: 12px;
  background: #f8f9fa;
  border-radius: 6px;
  text-align: center;
}

.stat-card.up {
  background: #fff5f5;
  border: 1px solid #ffd6d6;
}

.stat-card.down {
  background: #f0f9ff;
  border: 1px solid #d6edff;
}

.stat-label {
  font-size: 12px;
  color: #7f8c8d;
  margin-bottom: 4px;
}

.stat-value {
  font-size: 20px;
  font-weight: 600;
  color: #2c3e50;
}

.stat-card.up .stat-value {
  color: #e74c3c;
}

.stat-card.down .stat-value {
  color: #3498db;
}

.refresh-btn {
  margin: 20px;
  padding: 10px;
  background: #409eff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: background 0.2s;
}

.refresh-btn:hover:not(:disabled) {
  background: #66b1ff;
}

.refresh-btn:disabled {
  background: #c0c4cc;
  cursor: not-allowed;
}

/* 状态容器 */
.status-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  background: white;
}

.status-container.error {
  color: #f56c6c;
}

.loading-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid #e4e7ed;
  border-top-color: #409eff;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.retry-btn {
  margin-top: 15px;
  padding: 8px 20px;
  background: #409eff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.retry-btn:hover {
  background: #66b1ff;
}

/* 内容区域 */
.content {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.tabs {
  display: flex;
  background: white;
  border-bottom: 2px solid #e4e7ed;
}

.tab-btn {
  padding: 15px 30px;
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  color: #606266;
  transition: all 0.3s;
}

.tab-btn:hover {
  color: #409eff;
}

.tab-btn.active {
  color: #409eff;
  border-bottom-color: #409eff;
}

.tab-content {
  flex: 1;
  min-height: 0;
  background: white;
  overflow: hidden;
}

.chart-panel {
  height: 100%;
  padding: 20px;
  box-sizing: border-box;
}

.chart {
  width: 100%;
  height: 100%;
  min-height: 400px;
}

.table-panel {
  height: 100%;
  overflow: auto;
  padding: 20px;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
}

.data-table th,
.data-table td {
  padding: 12px;
  text-align: left;
  border-bottom: 1px solid #ecf0f1;
}

.data-table th {
  background: #f8f9fa;
  font-weight: 600;
  color: #2c3e50;
  position: sticky;
  top: 0;
}

.data-table tr:hover {
  background: #f8f9fa;
}

.gene-name {
  font-weight: 600;
  color: #2c3e50;
}

.positive {
  color: #e74c3c;
  font-weight: 500;
}

.negative {
  color: #3498db;
  font-weight: 500;
}
</style>
