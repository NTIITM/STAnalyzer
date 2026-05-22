<template>
  <div class="cell-comm-page">
    <aside class="sidebar">
      <div class="sidebar-header">
        <h3>{{ t('cellComm.title') }}</h3>
        <p class="subtitle">{{ t('cellComm.subtitle') }}</p>
      </div>

      <div class="panel">
        <div class="panel-title">{{ t('cellComm.filter') }}</div>
        <label class="panel-item">
          {{ t('cellComm.minScore') }}
          <input type="number" step="0.1" v-model.number="minScore" />
        </label>
        <label class="panel-item">
          {{ t('cellComm.minNormScore') }}
          <input type="number" step="0.0001" v-model.number="minNormScore" />
        </label>
        <label class="panel-item">
          {{ t('cellComm.senderCells') }}
          <select v-model="senderFilter" multiple>
            <option v-for="s in uniqueSenders" :key="s" :value="s">{{ s }}</option>
          </select>
        </label>
        <label class="panel-item">
          {{ t('cellComm.receiverCells') }}
          <select v-model="receiverFilter" multiple>
            <option v-for="r in uniqueReceivers" :key="r" :value="r">{{ r }}</option>
          </select>
        </label>
        <label class="panel-item">
          {{ t('cellComm.ligandReceptorContains') }}
          <input type="text" v-model.trim="geneKeyword" :placeholder="t('cellComm.ligandReceptorPlaceholder')" />
        </label>
        <div class="panel-actions">
          <button class="btn" :disabled="loading" @click="loadData">
            {{ loading ? t('cellComm.loading') : t('cellComm.reload') }}
          </button>
          <button class="btn ghost" @click="resetFilters">{{ t('cellComm.reset') }}</button>
        </div>
      </div>

      <div class="stats">
        <div class="stat">
          <div class="label">{{ t('cellComm.interactions') }}</div>
          <div class="value">{{ filteredRows.length }}</div>
        </div>
        <div class="stat">
          <div class="label">{{ t('cellComm.uniqueLRPairs') }}</div>
          <div class="value">{{ uniquePairsCount }}</div>
        </div>
        <div class="stat">
          <div class="label">{{ t('cellComm.senderCells') }}</div>
          <div class="value">{{ uniqueSenders.length }}</div>
        </div>
        <div class="stat">
          <div class="label">{{ t('cellComm.receiverCells') }}</div>
          <div class="value">{{ uniqueReceivers.length }}</div>
        </div>
      </div>
    </aside>

    <section class="main">
      <div class="main-header">
        <div>
          <h3>{{ t('cellComm.visualizationTitle') }}</h3>
          <p class="subtitle">{{ t('cellComm.visualizationSubtitle') }}</p>
        </div>
        <div class="tabs">
          <div
            v-for="tab in tabs"
            :key="tab"
            class="tab"
            :class="{ active: activeTab === tab }"
            @click="switchTab(tab)"
          >
            {{ tabLabels[tab] }}
          </div>
        </div>
      </div>

      <div class="panel-body">
        <div v-if="loading" class="status">{{ t('cellComm.loading') }}</div>
        <div v-else-if="error" class="status error">{{ error }}</div>
        <div v-else-if="!rows.length" class="status">{{ t('cellComm.noData') }}</div>

        <div v-show="!loading && !error && rows.length" class="views">
          <div v-show="activeTab === 'network'" class="card">
            <div class="card-header">
              <div class="title">{{ t('cellComm.networkTitle') }}</div>
              <div class="hint">{{ t('cellComm.networkHint') }}</div>
            </div>
            <div class="chart" ref="networkRef"></div>
          </div>

          <div v-show="activeTab === 'heatmap'" class="card">
            <div class="card-header">
              <div class="title">{{ t('cellComm.heatmapTitle') }}</div>
              <div class="hint">{{ t('cellComm.heatmapHint') }}</div>
            </div>
            <div class="chart" ref="heatmapRef"></div>
          </div>

          <div v-show="activeTab === 'distribution'" class="card">
            <div class="card-header">
              <div class="title">{{ t('cellComm.distributionTitle') }}</div>
              <div class="hint">{{ t('cellComm.distributionHint') }}</div>
            </div>
            <div class="chart" ref="distRef"></div>
          </div>

          <div v-show="activeTab === 'table'" class="card table-card">
            <div class="card-header">
              <div class="title">{{ t('cellComm.tableTitle') }}</div>
              <div class="hint">{{ t('cellComm.tableHint') }}</div>
            </div>
            <div class="table-wrapper">
              <table>
                <thead>
                  <tr>
                    <th>#</th>
                    <th>{{ t('cellComm.table.sender') }}</th>
                    <th>{{ t('cellComm.table.receiver') }}</th>
                    <th>{{ t('cellComm.table.ligand') }}</th>
                    <th>{{ t('cellComm.table.receptor') }}</th>
                    <th>{{ t('cellComm.table.distance') }}</th>
                    <th>{{ t('cellComm.table.score') }}</th>
                    <th>{{ t('cellComm.table.normScore') }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(r, idx) in tableRows" :key="idx">
                    <td>{{ idx + 1 }}</td>
                    <td>{{ r.sender }}</td>
                    <td>{{ r.receiver }}</td>
                    <td class="ligand">{{ r.ligand }}</td>
                    <td class="receptor">{{ r.receptor }}</td>
                    <td>{{ formatNumber(r.distance) }}</td>
                    <td>{{ formatNumber(r.score) }}</td>
                    <td>{{ formatNumber(r.normalized_score) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import Papa from 'papaparse'
import { downloadFileById } from '../../api/file'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

interface CommRow {
  sender: string
  receiver: string
  ligand: string
  receptor: string
  distance: number
  transport_kernel: number
  score: number
  normalized_score: number
}

const props = defineProps<{
  fileId: string
}>()

const loading = ref(false)
const error = ref<string | null>(null)
const rows = ref<CommRow[]>([])

const minScore = ref(0)
const minNormScore = ref(0)
const senderFilter = ref<string[]>([])
const receiverFilter = ref<string[]>([])
const geneKeyword = ref('')

const tabs = ['network', 'heatmap', 'distribution', 'table'] as const
const tabLabels = computed<Record<(typeof tabs)[number], string>>(() => ({
  network: t('cellComm.tabs.network'),
  heatmap: t('cellComm.tabs.heatmap'),
  distribution: t('cellComm.tabs.distribution'),
  table: t('cellComm.tabs.table')
}))
const activeTab = ref<(typeof tabs)[number]>('network')

const networkRef = ref<HTMLDivElement | null>(null)
const heatmapRef = ref<HTMLDivElement | null>(null)
const distRef = ref<HTMLDivElement | null>(null)
let networkChart: echarts.ECharts | null = null
let heatmapChart: echarts.ECharts | null = null
let distChart: echarts.ECharts | null = null

const uniqueSenders = computed(() => Array.from(new Set(rows.value.map(r => r.sender))).filter(Boolean))
const uniqueReceivers = computed(() => Array.from(new Set(rows.value.map(r => r.receiver))).filter(Boolean))
const uniquePairsCount = computed(() => new Set(rows.value.map(r => `${r.ligand}-${r.receptor}`)).size)

const filteredRows = computed(() => {
  const keyword = geneKeyword.value.trim().toLowerCase()
  return rows.value.filter(r => {
    if (r.score < minScore.value) return false
    if (r.normalized_score < minNormScore.value) return false
    if (senderFilter.value.length && !senderFilter.value.includes(r.sender)) return false
    if (receiverFilter.value.length && !receiverFilter.value.includes(r.receiver)) return false
    if (keyword) {
      const text = `${r.ligand} ${r.receptor}`.toLowerCase()
      if (!text.includes(keyword)) return false
    }
    return true
  })
})

const tableRows = computed(() =>
  [...filteredRows.value].sort((a, b) => b.score - a.score || b.normalized_score - a.normalized_score)
)

const matrixData = computed(() => {
  const senders = uniqueSenders.value
  const receivers = uniqueReceivers.value
  const matrix: [number, number, number][] = []
  const acc = new Map<string, number>()
  filteredRows.value.forEach(r => {
    const key = `${r.sender}||${r.receiver}`
    acc.set(key, (acc.get(key) || 0) + (Number(r.score) || 0))
  })
  let max = 0
  senders.forEach((s, si) => {
    receivers.forEach((r, ri) => {
      const val = acc.get(`${s}||${r}`) || 0
      max = Math.max(max, val)
      matrix.push([si, ri, val])
    })
  })
  return { senders, receivers, matrix, max: max || 1 }
})

const networkData = computed(() => {
  const nodesMap = new Map<string, { id: string; name: string; category: string; value: number }>()
  const edges: { source: string; target: string; value: number; label: string; lineStyle: any }[] = []
  filteredRows.value.forEach(r => {
    if (!nodesMap.has(r.sender)) nodesMap.set(r.sender, { id: r.sender, name: r.sender, category: 'sender', value: 1 })
    if (!nodesMap.has(r.receiver)) nodesMap.set(r.receiver, { id: r.receiver, name: r.receiver, category: 'receiver', value: 1 })
    nodesMap.get(r.sender)!.value += 1
    nodesMap.get(r.receiver)!.value += 1
    edges.push({
      source: r.sender,
      target: r.receiver,
      value: r.normalized_score,
      label: `${r.ligand}-${r.receptor}`,
      lineStyle: { width: Math.max(1, Math.min(6, r.normalized_score * 4)) }
    })
  })
  return { nodes: Array.from(nodesMap.values()), edges }
})

const chordData = computed(() => {
  const senders = uniqueSenders.value
  const receivers = uniqueReceivers.value
  const nodeNames = Array.from(new Set([...senders, ...receivers].filter(Boolean)))
    // 计算每个节点的连接数作为 value
  const nodeValueMap = new Map<string, number>()
  filteredRows.value.forEach(r => {
    const s = r.sender || t('cellComm.unknown')
    const recv = r.receiver || t('cellComm.unknown')
    if (s) nodeValueMap.set(s, (nodeValueMap.get(s) || 0) + 1)
    if (recv) nodeValueMap.set(recv, (nodeValueMap.get(recv) || 0) + 1)
  })
  
  const nodes = nodeNames.map(name => ({ name, raw: name, value: nodeValueMap.get(name) || 1 }))
  const nodeSet = new Set(nodeNames)
  const acc = new Map<string, number>()
  filteredRows.value.forEach(r => {
    const s = r.sender || t('cellComm.unknown')
    const recv = r.receiver || t('cellComm.unknown')
    if (!s || !recv) return
    const key = `${s}||${recv}`
    const weight = Number(r.normalized_score) || Number(r.score) || 0
    acc.set(key, (acc.get(key) || 0) + weight)
  })
  const links = Array.from(acc.entries())
    .map(([k, value]) => {
      const [s, recv] = k.split('||')
      return { source: s, target: recv, value }
    })
    .filter(l => nodeSet.has(l.source) && nodeSet.has(l.target) && l.value !== undefined)
  return { nodes, links }
})

const distSeries = computed(() => {
  const scores = filteredRows.value.map(r => r.score)
  const norms = filteredRows.value.map(r => r.normalized_score)
  const bins = 20
  const histo = (arr: number[]) => {
    if (!arr.length) return { edges: [], counts: [] }
    const min = Math.min(...arr)
    const max = Math.max(...arr)
    const step = (max - min || 1) / bins
    const counts = Array(bins).fill(0)
    arr.forEach(v => {
      const idx = Math.min(bins - 1, Math.floor((v - min) / step))
      counts[idx] += 1
    })
    const edges = counts.map((_, i) => (min + step * i).toFixed(2))
    return { edges, counts }
  }
  return { score: histo(scores), norm: histo(norms) }
})

function resetFilters() {
  minScore.value = 0
  minNormScore.value = 0
  senderFilter.value = []
  receiverFilter.value = []
  geneKeyword.value = ''
}

function switchTab(tab: (typeof tabs)[number]) {
  activeTab.value = tab
  nextTick(() => {
    if (tab === 'network') {
      networkChart?.resize()
      refreshNetwork()
    } else if (tab === 'heatmap') {
      heatmapChart?.resize()
      refreshHeatmap()
    } else if (tab === 'distribution') {
      distChart?.resize()
      refreshDistribution()
    }
  })
}

async function loadData() {
  if (!props.fileId) {
    error.value = t('cellComm.missingFileId')
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
      dynamicTyping: true,
      delimitersToGuess: [',', '\t', ';', '|']
    })
    const normalize = (raw: any) => {
      const lowered: Record<string, any> = {}
      Object.entries(raw || {}).forEach(([k, v]) => lowered[k.toString().trim().toLowerCase()] = v)
      return lowered
    }
    const pick = (obj: Record<string, any>, keys: string[], fallback: any = '') => {
      for (const k of keys) {
        const v = obj[k]
        if (v !== undefined && v !== null && v !== '') return v
      }
      return fallback
    }
    rows.value = (parsed.data as any[]).map(r => {
      const n = normalize(r)
      return {
        sender: String(pick(n, ['sender', 'source', 'from'], '') || '').trim(),
        receiver: String(pick(n, ['receiver', 'target', 'to'], '') || '').trim(),
        ligand: String(pick(n, ['ligand', 'ligand_gene', 'l'], '') || '').trim(),
        receptor: String(pick(n, ['receptor', 'receptor_gene', 'r'], '') || '').trim(),
        distance: Number(pick(n, ['distance', 'dist'], 0)) || 0,
        transport_kernel: Number(pick(n, ['transport_kernel', 'kernel'], 0)) || 0,
        score: Number(pick(n, ['score', 'interaction_score'], 0)) || 0,
        normalized_score: Number(pick(n, ['normalized_score', 'norm_score'], 0)) || 0
      }
    }).filter(item => item.sender && item.receiver && item.ligand && item.receptor)
    // 依靠 watch(filteredRows) 自动渲染，避免在 loading 结束前同步渲染导致 DOM 未更新
  } catch (e: any) {
    console.error(e)
    error.value = e?.message || t('cellComm.loadFailed')
  } finally {
    loading.value = false
  }
}

function refreshNetwork() {
  if (!networkChart) return
  const data = chordData.value
  if (!data.nodes.length || !data.links.length) {
    networkChart.clear()
    return
  }
  const palette = [
    '#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de',
    '#3ba272', '#fc8452', '#9a60b4', '#ea7ccc'
  ]

  networkChart.setOption({
    tooltip: {
      trigger: 'item',
      formatter: (p: any) => {
        if (p.dataType === 'edge' || p.data?.source) {
          return `${p.data.source} → ${p.data.target}<br/>${t('cellComm.score')}: ${formatNumber(p.data.value)}`
        }
        const name = (p.data?.raw ?? p.data?.name ?? '').toString()
        return `${name}`
      }
    },
    legend: { show: false },
    series: [
      {
        name: t('cellComm.chordChart'),
        type: 'graph',
        layout: 'circular',
        circular: { rotateLabel: true },
        roam: true,
        edgeSymbol: ['none', 'arrow'],
        edgeSymbolSize: 8,
        data: data.nodes.map((n, idx) => ({
          ...n,
          symbolSize: 30 + Math.min(n.value, 20),
          label: { show: true, position: 'right' },
          itemStyle: { color: palette[idx % palette.length] }
        })),
        links: data.links,
        lineStyle: { color: 'source', curveness: 0.3, opacity: 0.7 },
        label: { show: true }
      }
    ]
  })
}

function refreshHeatmap() {
  if (!heatmapChart) return
  const m = matrixData.value
  heatmapChart.setOption({
    tooltip: {
      formatter: (p: any) => {
        const s = m.senders[p.data[0]]
        const r = m.receivers[p.data[1]]
        return `${s} → ${r}<br/>${t('cellComm.score')}: ${formatNumber(p.data[2])}`
      }
    },
    grid: { left: 100, right: 40, top: 20, bottom: 80 },
    xAxis: { type: 'category', data: m.senders, axisLabel: { rotate: 45 } },
    yAxis: { type: 'category', data: m.receivers },
    visualMap: {
      min: 0,
      max: m.max,
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: 10,
      inRange: {
        color: ['#f6efa6', '#f3b471', '#d88273', '#bf444c'] // 更美观的暖色系热力图渐变
      }
    },
    series: [
      {
        type: 'heatmap',
        data: m.matrix,
        emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.3)' } }
      }
    ]
  })
}

function refreshDistribution() {
  if (!distChart) return
  const s = distSeries.value
  distChart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['score', 'normalized_score'] },
    grid: { left: 60, right: 20, top: 30, bottom: 50 },
    xAxis: { type: 'category', data: s.score.edges.length ? s.score.edges : s.norm.edges },
    yAxis: { type: 'value', name: t('cellComm.frequency') },
    series: [
      { name: 'score', type: 'bar', data: s.score.counts, itemStyle: { color: '#5470c6' }, barGap: 0 },
      { name: 'normalized_score', type: 'bar', data: s.norm.counts, itemStyle: { color: '#fac858' } }
    ]
  })
}

function formatNumber(v: number) {
  if (v === undefined || v === null || Number.isNaN(v)) return '-'
  return Number(v).toFixed(3)
}

onMounted(() => {
  if (networkRef.value) networkChart = echarts.init(networkRef.value)
  if (heatmapRef.value) heatmapChart = echarts.init(heatmapRef.value)
  if (distRef.value) distChart = echarts.init(distRef.value)
  loadData()
})

watch(filteredRows, () => {
  // DOM 必须在 nextTick 后才取消 display: none 的隐藏状态
  // 否则 echarts.init 得到的尺寸将是 0x0
  nextTick(() => {
    networkChart?.resize()
    heatmapChart?.resize()
    distChart?.resize()
    refreshNetwork()
    refreshHeatmap()
    refreshDistribution()
  })
}, { deep: true })

onBeforeUnmount(() => {
  networkChart?.dispose()
  heatmapChart?.dispose()
  distChart?.dispose()
  networkChart = null
  heatmapChart = null
  distChart = null
})
</script>

<style scoped>
.cell-comm-page {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: 16px;
  height: 100%;
  padding: 12px;
  box-sizing: border-box;
}
.sidebar {
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid var(--border-color, #e5e5e5);
  border-radius: 10px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.sidebar-header h3 {
  margin: 0;
}
.subtitle {
  margin: 4px 0 0;
  color: #666;
  font-size: 12px;
}
.panel {
  background: #f8f9fb;
  border: 1px solid var(--border-color, #e5e5e5);
  border-radius: 8px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.panel-title {
  font-weight: 600;
  color: #2c3e50;
}
.panel-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
}
.panel-item input,
.panel-item select {
  padding: 6px 8px;
  border-radius: 6px;
  border: 1px solid var(--border-color, #dcdcdc);
  background: #fff;
}
.panel-item select {
  min-height: 90px;
}
.panel-actions {
  display: flex;
  gap: 8px;
  margin-top: 6px;
}
.btn {
  flex: 1;
  padding: 8px 10px;
  border-radius: 6px;
  border: 1px solid var(--border-color, #dcdcdc);
  background: #fff;
  cursor: pointer;
}
.btn.ghost {
  background: #f6f7fb;
}
.stats {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}
.stat {
  padding: 8px;
  border-radius: 8px;
  border: 1px solid var(--border-color, #e5e5e5);
  background: linear-gradient(180deg, rgba(255,255,255,0.9), rgba(245,247,250,0.9));
}
.stat .label {
  font-size: 12px;
  color: #666;
}
.stat .value {
  font-size: 18px;
  font-weight: 700;
  color: #2c3e50;
}
.main {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.main-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 12px;
  margin-bottom: 8px;
}
.tabs {
  display: flex;
  gap: 8px;
}
.tab {
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid var(--border-color, #e5e5e5);
  background: #fff;
  cursor: pointer;
  font-weight: 600;
}
.tab.active {
  background: linear-gradient(90deg, #6a8bff, #a16bff);
  color: #fff;
  border-color: #6a8bff;
}
.panel-body {
  background: #fff;
  border: 1px solid var(--border-color, #e5e5e5);
  border-radius: 12px;
  padding: 10px;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.status {
  display: flex;
  justify-content: center;
  align-items: center;
  flex: 1;
  color: #666;
}
.status.error {
  color: #d9534f;
}
.views {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.card {
  border: 1px solid var(--border-color, #e5e5e5);
  border-radius: 10px;
  background: linear-gradient(180deg, rgba(255,255,255,0.95), rgba(250,250,252,0.95));
  display: flex;
  flex-direction: column;
  min-height: 280px;
}
.card-header {
  padding: 10px 12px;
  border-bottom: 1px solid var(--border-color, #e5e5e5);
}
.card-header .title {
  font-weight: 700;
}
.card-header .hint {
  font-size: 12px;
  color: #666;
  margin-top: 2px;
}
.chart {
  flex: 1;
  min-height: 550px; /* 增加画框大小，原本360px过小 */
}
.table-card {
  flex: 1;
}
.table-wrapper {
  overflow: auto;
  padding: 10px;
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
th, td {
  border-bottom: 1px solid var(--border-color, #eee);
  padding: 6px 8px;
  text-align: left;
}
th {
  background: #f8f9fb;
  position: sticky;
  top: 0;
}
.ligand {
  color: #d35400;
  font-weight: 600;
}
.receptor {
  color: #2980b9;
  font-weight: 600;
}
@media (max-width: 1100px) {
  .cell-comm-page {
    grid-template-columns: 1fr;
  }
  .sidebar {
    order: 2;
  }
}
</style>
