import { ref, Ref } from 'vue'
import * as echarts from 'echarts'

export interface SpotData {
  id: string
  x: number
  y: number
  geneExpression?: number
  clusterLabel?: string | number
}

export function useSpatialECharts() {
  const echartsInstance: Ref<echarts.ECharts | null> = ref(null)

  function initECharts(container: HTMLElement) {
    if (echartsInstance.value) {
      echartsInstance.value.dispose()
    }
    echartsInstance.value = echarts.init(container)
    return echartsInstance.value
  }

  function renderScatter(
    spots: SpotData[],
    options: {
      selectedGene?: string
      minExpression: number
      maxExpression: number
      spotSize: number
      hasClusterLabel: boolean
      clusterColorMap: Map<string, string>
      t: (key: string) => string
    }
  ) {
    if (!echartsInstance.value) return

    const scatterData = spots.map(spot => {
      const value = options.selectedGene && spot.geneExpression !== undefined 
        ? spot.geneExpression 
        : 0
      
      let color = '#6496DC'
      if (options.selectedGene) {
        color = getExpressionColorHex(
          (value - options.minExpression) / (options.maxExpression - options.minExpression || 1)
        )
      } else if (options.hasClusterLabel && spot.clusterLabel !== undefined) {
        color = options.clusterColorMap.get(String(spot.clusterLabel)) || '#6496DC'
      }
      
      return {
        value: [spot.x, spot.y, value],
        itemStyle: { color },
        spotId: spot.id,
        cluster: spot.clusterLabel
      }
    })
    
    const option: echarts.EChartsOption = {
      backgroundColor: 'transparent',
      tooltip: {
        formatter: (params: any) => {
          const data = params.data
          let html = `<strong>Spot ${data.spotId}</strong><br/>`
          html += `${options.t('spatial.position')}: (${data.value[0].toFixed(2)}, ${data.value[1].toFixed(2)})<br/>`
          if (data.cluster !== undefined && data.cluster !== null) {
            html += `Cluster: ${data.cluster}<br/>`
          }
          if (options.selectedGene) {
            html += `${options.selectedGene}: ${data.value[2].toFixed(2)}`
          }
          return html
        }
      },
      grid: {
        left: '3%',
        right: '7%',
        bottom: options.selectedGene ? '12%' : '7%',
        top: '3%',
        containLabel: true
      },
      xAxis: {
        type: 'value',
        name: 'X',
        splitLine: { show: false }
      },
      yAxis: {
        type: 'value',
        name: 'Y',
        splitLine: { show: false },
        inverse: true
      },
      series: [{
        type: 'scatter',
        symbolSize: options.spotSize * 2,
        data: scatterData,
        emphasis: {
          focus: 'self',
          itemStyle: {
            borderColor: '#000',
            borderWidth: 2
          }
        }
      }]
    }
    
    // 只在选择基因时添加 visualMap
    if (options.selectedGene) {
      option.visualMap = {
        min: options.minExpression,
        max: options.maxExpression,
        dimension: 2,
        orient: 'horizontal',
        left: 'center',
        bottom: '0%',
        text: ['High', 'Low'],
        calculable: true,
        inRange: {
          color: ['#0000FF', '#00FFFF', '#00FF00', '#FFFF00', '#FF0000']
        }
      }
    }
    
    echartsInstance.value.setOption(option, true)
  }

  function renderHeatmap(
    spots: SpotData[],
    options: {
      minExpression: number
      maxExpression: number
      heatmapResolution: number
      colorScheme: string
      t: (key: string) => string
    }
  ) {
    if (!echartsInstance.value || spots.length === 0) return

    const heatmapData = generateHeatmapData(spots, options.heatmapResolution)
    
    const option: echarts.EChartsOption = {
      backgroundColor: 'transparent',
      tooltip: {
        position: 'top',
        formatter: (params: any) => {
          return `${options.t('spatial.position')}: (${params.data[0]}, ${params.data[1]})<br/>
                  ${options.t('spatial.expression')}: ${params.data[2].toFixed(2)}`
        }
      },
      grid: {
        left: '3%',
        right: '7%',
        bottom: '10%',
        top: '3%',
        containLabel: true
      },
      xAxis: {
        type: 'category',
        data: heatmapData.xAxis,
        splitArea: { show: false }
      },
      yAxis: {
        type: 'category',
        data: heatmapData.yAxis,
        splitArea: { show: false },
        inverse: true
      },
      visualMap: {
        min: options.minExpression,
        max: options.maxExpression,
        calculable: true,
        orient: 'horizontal',
        left: 'center',
        bottom: '0%',
        inRange: {
          color: getColorSchemeColors(options.colorScheme)
        }
      },
      series: [{
        type: 'heatmap',
        data: heatmapData.data,
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowColor: 'rgba(0, 0, 0, 0.5)'
          }
        }
      }]
    }
    
    echartsInstance.value.setOption(option, true)
  }

  function generateHeatmapData(spots: SpotData[], resolution: number) {
    const xValues = spots.map(s => s.x)
    const yValues = spots.map(s => s.y)
    const minX = Math.min(...xValues)
    const maxX = Math.max(...xValues)
    const minY = Math.min(...yValues)
    const maxY = Math.max(...yValues)
    
    const xStep = (maxX - minX) / resolution
    const yStep = (maxY - minY) / resolution
    
    const xAxis = []
    const yAxis = []
    const data = []
    
    for (let i = 0; i <= resolution; i++) {
      xAxis.push((minX + i * xStep).toFixed(1))
      yAxis.push((minY + i * yStep).toFixed(1))
    }
    
    for (let yi = 0; yi <= resolution; yi++) {
      for (let xi = 0; xi <= resolution; xi++) {
        const x = minX + xi * xStep
        const y = minY + yi * yStep
        
        let minDist = Infinity
        let nearestValue = 0
        
        spots.forEach(spot => {
          if (spot.geneExpression === undefined) return
          const dist = Math.sqrt(Math.pow(spot.x - x, 2) + Math.pow(spot.y - y, 2))
          if (dist < minDist) {
            minDist = dist
            nearestValue = spot.geneExpression
          }
        })
        
        data.push([xi, yi, nearestValue])
      }
    }
    
    return { xAxis, yAxis, data }
  }

  function getColorSchemeColors(scheme: string): string[] {
    const schemes: Record<string, string[]> = {
      viridis: ['#440154', '#414487', '#2a788e', '#22a884', '#7ad151', '#fde725'],
      plasma: ['#0d0887', '#6a00a8', '#b12a90', '#e16462', '#fca636', '#f0f921'],
      inferno: ['#000004', '#420a68', '#932667', '#dd513a', '#fca50a', '#fcffa4'],
      magma: ['#000004', '#3b0f70', '#8c2981', '#de4968', '#fe9f6d', '#fcfdbf'],
      redblue: ['#0000FF', '#4040FF', '#8080FF', '#C0C0FF', '#FFC0C0', '#FF8080', '#FF4040', '#FF0000']
    }
    return schemes[scheme] || schemes.viridis
  }

  function getExpressionColorHex(normalizedValue: number): string {
    const value = Math.max(0, Math.min(1, normalizedValue))
    const r = Math.round(255 * (1 - value))
    const g = Math.round(100 * (1 - Math.abs(value - 0.5) * 2))
    const b = Math.round(255 * value)
    return `rgb(${r}, ${g}, ${b})`
  }

  function resize() {
    if (echartsInstance.value) {
      echartsInstance.value.resize()
    }
  }

  function dispose() {
    if (echartsInstance.value) {
      echartsInstance.value.dispose()
      echartsInstance.value = null
    }
  }

  return {
    echartsInstance,
    initECharts,
    renderScatter,
    renderHeatmap,
    resize,
    dispose
  }
}
