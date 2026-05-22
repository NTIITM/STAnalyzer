<template>
  <div class="enrichment-viz-panel">
    <div class="enrichment-controls">
      <el-form
        label-position="left"
        label-width="120px"
        class="enrichment-form"
      >
        <el-form-item label="Top N">
          <el-input-number v-model="topN" :min="5" :max="200" />
        </el-form-item>
        <el-form-item label="Sort by">
          <el-select v-model="sortKey" style="width: 180px">
            <el-option label="Adjusted P-value (asc)" value="adjP" />
            <el-option label="P-value (asc)" value="pValue" />
            <el-option label="Combined Score (desc)" value="combinedScore" />
            <el-option label="Odds Ratio (desc)" value="oddsRatio" />
          </el-select>
        </el-form-item>
        <el-form-item label="Gene set filter">
          <el-select
            v-model="geneSetFilter"
            clearable
            filterable
            placeholder="All"
            style="width: 200px"
          >
            <el-option
              v-for="gs in geneSetOptions"
              :key="gs"
              :label="gs"
              :value="gs"
            />
          </el-select>
        </el-form-item>
      </el-form>
    </div>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="Bar plot" name="bar">
        <div v-if="hasData" ref="barRef" class="chart-card"></div>
        <el-empty v-else description="No data" />
      </el-tab-pane>
      <el-tab-pane label="Dot plot" name="dot">
        <div v-if="hasData" ref="dotRef" class="chart-card"></div>
        <el-empty v-else description="No data" />
      </el-tab-pane>
      <el-tab-pane label="Sunburst" name="sunburst">
        <div v-if="hasData" ref="sunburstRef" class="chart-card"></div>
        <el-empty v-else description="No data" />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import * as echarts from 'echarts/core'
import {
  BarChart,
  ScatterChart,
  SunburstChart
} from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent,
  DataZoomComponent
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { ElEmpty, ElForm, ElFormItem, ElInputNumber, ElSelect, ElOption, ElTabs, ElTabPane } from 'element-plus'

echarts.use([
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent,
  DataZoomComponent,
  BarChart,
  ScatterChart,
  SunburstChart,
  CanvasRenderer
])

interface EnrichmentRecord {
  geneSet: string
  term: string
  overlap: string
  pValue: number
  adjP: number
  oldP?: number
  oldAdjP?: number
  oddsRatio?: number
  combinedScore?: number
  genes: string[] | string
}

const props = defineProps<{
  records: EnrichmentRecord[]
}>()

const activeTab = ref<'bar' | 'dot' | 'sunburst'>('bar')
const topN = ref(20)
const sortKey = ref<'adjP' | 'pValue' | 'combinedScore' | 'oddsRatio'>('adjP')
const geneSetFilter = ref<string | null>(null)

const barRef = ref<HTMLElement | null>(null)
const dotRef = ref<HTMLElement | null>(null)
const sunburstRef = ref<HTMLElement | null>(null)

let barChart: echarts.ECharts | null = null
let dotChart: echarts.ECharts | null = null
let sunburstChart: echarts.ECharts | null = null

const normalized = computed(() => {
  const normalizeGenes = (genes: EnrichmentRecord['genes']) => {
    if (Array.isArray(genes)) return genes
    if (typeof genes === 'string') {
      return genes
        .split(/[;,]/)
        .map(g => g.trim())
        .filter(Boolean)
    }
    return []
  }

  return (props.records || []).map((r) => {
    const [numStr, denStr] = (r.overlap || '').split('/')
    const geneCount = Number(numStr) || 0
    const bgCount = Number(denStr) || 0
    const geneRatio = bgCount > 0 ? geneCount / bgCount : 0
    return {
      ...r,
      geneCount,
      bgCount,
      geneRatio,
      genes: normalizeGenes(r.genes)
    }
  })
})

const geneSetOptions = computed(() => {
  const set = new Set<string>()
  normalized.value.forEach(item => {
    if (item.geneSet) set.add(item.geneSet)
  })
  return Array.from(set)
})

const filtered = computed(() => {
  let data = normalized.value
  if (geneSetFilter.value) {
    data = data.filter(d => d.geneSet === geneSetFilter.value)
  }
  const sorted = [...data].sort((a, b) => {
    if (sortKey.value === 'adjP') return (a.adjP ?? Infinity) - (b.adjP ?? Infinity)
    if (sortKey.value === 'pValue') return (a.pValue ?? Infinity) - (b.pValue ?? Infinity)
    if (sortKey.value === 'combinedScore') return (b.combinedScore ?? -Infinity) - (a.combinedScore ?? -Infinity)
    return (b.oddsRatio ?? -Infinity) - (a.oddsRatio ?? -Infinity)
  })
  return sorted.slice(0, topN.value)
})

const hasData = computed(() => filtered.value.length > 0)

const renderBar = () => {
  if (!barRef.value) return
  if (!barChart) {
    barChart = echarts.init(barRef.value)
  }
  const data = filtered.value
  const option = {
    title: { text: 'Bar plot (Top terms)' },
    grid: { left: 140, right: 30, top: 40, bottom: 40 },
    tooltip: {
      trigger: 'axis'
    },
    xAxis: { type: 'value', name: '-log10(adjP)' },
    yAxis: { type: 'category', data: data.map(d => d.term) },
    series: [
      {
        type: 'bar',
        data: data.map(d => ({
          value: d.adjP ? -Math.log10(d.adjP) : 0,
          name: d.term
        })),
        itemStyle: { color: '#5470c6' }
      }
    ]
  }
  barChart.setOption(option, true)
}

const renderDot = () => {
  if (!dotRef.value) return
  if (!dotChart) {
    dotChart = echarts.init(dotRef.value)
  }
  const data = filtered.value
  const option = {
    title: { text: 'Dot plot' },
    grid: { left: 140, right: 40, top: 40, bottom: 60 },
    legend: { top: 10, right: 10 },
    tooltip: {
      trigger: 'item',
      formatter: (params: any) => {
        const d = params.data
        return [
          `<b>${d.term}</b>`,
          `Gene set: ${d.geneSet || '-'}`,
          `Gene ratio: ${(d.geneRatio * 100).toFixed(2)}%`,
          `Gene count: ${d.geneCount}/${d.bgCount}`,
          `AdjP: ${d.adjP}`
        ].join('<br/>')
      }
    },
    xAxis: {
      type: 'value',
      name: 'Gene ratio',
      axisLabel: { formatter: (v: number) => `${(v * 100).toFixed(0)}%` }
    },
    yAxis: { type: 'category', data: data.map(d => d.term) },
    series: [
      {
        type: 'scatter',
        data: data.map(d => ({
          value: [d.geneRatio, d.term],
          term: d.term,
          geneSet: d.geneSet,
          geneRatio: d.geneRatio,
          geneCount: d.geneCount,
          bgCount: d.bgCount,
          adjP: d.adjP,
          symbolSize: Math.max(8, Math.sqrt(d.geneCount || 1) * 6),
          itemStyle: {
            color: d.adjP ? echarts.color.modifyHSL('#ff6b6b', 0, 0, Math.min(0.9, 1 - Math.log10(d.adjP + 1e-12) / 20)) : '#ffb74d'
          }
        }))
      }
    ],
    dataZoom: [{ type: 'inside' }, { type: 'slider' }]
  }
  dotChart.setOption(option, true)
}

const renderSunburst = () => {
  if (!sunburstRef.value) return
  if (!sunburstChart) {
    sunburstChart = echarts.init(sunburstRef.value)
  }
  const groupByGeneSet = filtered.value.reduce<Record<string, any[]>>((acc, cur) => {
    if (!acc[cur.geneSet]) acc[cur.geneSet] = []
    acc[cur.geneSet].push(cur)
    return acc
  }, {})

  const seriesData = Object.entries(groupByGeneSet).map(([geneSet, items]) => ({
    name: geneSet || 'Unknown',
    children: items.map(item => ({
      name: item.term,
      value: item.combinedScore ?? item.geneRatio ?? 1
    }))
  }))

  const option = {
    title: { text: 'Sunburst by gene set' },
    series: [
      {
        type: 'sunburst',
        radius: [0, '90%'],
        data: seriesData,
        label: { rotate: 'radial' }
      }
    ]
  }
  sunburstChart.setOption(option, true)
}

const renderActive = () => {
  if (!hasData.value) return
  if (activeTab.value === 'bar') renderBar()
  if (activeTab.value === 'dot') renderDot()
  if (activeTab.value === 'sunburst') renderSunburst()
}

const resizeObserver = new ResizeObserver(() => {
  barChart?.resize()
  dotChart?.resize()
  sunburstChart?.resize()
})

onMounted(() => {
  if (barRef.value) resizeObserver.observe(barRef.value)
  if (dotRef.value) resizeObserver.observe(dotRef.value)
  if (sunburstRef.value) resizeObserver.observe(sunburstRef.value)
  renderActive()
})

onUnmounted(() => {
  resizeObserver.disconnect()
  barChart?.dispose()
  dotChart?.dispose()
  sunburstChart?.dispose()
})

watch([activeTab, filtered], () => {
  renderActive()
})
</script>

<style scoped>
.enrichment-viz-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  width: 100%;
}

.enrichment-controls {
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 12px 16px;
}

.enrichment-form {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
}

.chart-card {
  width: 100%;
  height: 520px;
}
</style>

