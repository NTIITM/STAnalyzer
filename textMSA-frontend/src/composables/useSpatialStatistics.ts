import * as echarts from 'echarts'
import { SpotData } from './useSpatialECharts'

export function useSpatialStatistics() {
  let histogramInstance: echarts.ECharts | null = null
  let boxplotInstance: echarts.ECharts | null = null
  let pieInstance: echarts.ECharts | null = null
  let barInstance: echarts.ECharts | null = null

  function renderHistogram(
    container: HTMLElement,
    spots: SpotData[]
  ) {
    if (!histogramInstance) {
      histogramInstance = echarts.init(container)
    }
    
    const expressionValues = spots
      .map(s => s.geneExpression)
      .filter((v): v is number => v !== undefined)
    
    if (expressionValues.length === 0) return
    
    const bins = 20
    const min = Math.min(...expressionValues)
    const max = Math.max(...expressionValues)
    const binWidth = (max - min) / bins
    
    const histogram = new Array(bins).fill(0)
    expressionValues.forEach(value => {
      const binIndex = Math.min(Math.floor((value - min) / binWidth), bins - 1)
      histogram[binIndex]++
    })
    
    const xAxisData = []
    for (let i = 0; i < bins; i++) {
      xAxisData.push((min + i * binWidth).toFixed(2))
    }
    
    const sortedValues = [...expressionValues].sort((a, b) => a - b)
    const mean = expressionValues.reduce((a, b) => a + b, 0) / expressionValues.length
    const median = sortedValues[Math.floor(sortedValues.length / 2)]
    
    const option: echarts.EChartsOption = {
      title: {
        text: `Mean: ${mean.toFixed(2)}, Median: ${median.toFixed(2)}`,
        textStyle: { fontSize: 12 },
        left: 'center'
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' }
      },
      grid: {
        left: '10%',
        right: '10%',
        bottom: '15%',
        top: '20%'
      },
      xAxis: {
        type: 'category',
        data: xAxisData,
        axisLabel: { rotate: 45, fontSize: 10 }
      },
      yAxis: {
        type: 'value',
        name: 'Count'
      },
      series: [{
        type: 'bar',
        data: histogram,
        itemStyle: {
          color: '#5470c6'
        }
      }]
    }
    
    histogramInstance.setOption(option, true)
  }

  function renderBoxplot(
    container: HTMLElement,
    clusterSpotsMap: Map<string, SpotData[]>
  ) {
    if (!boxplotInstance) {
      boxplotInstance = echarts.init(container)
    }
    
    const clusterData: number[][] = []
    const clusterNames: string[] = []
    
    clusterSpotsMap.forEach((clusterSpots, label) => {
      const values = clusterSpots
        .map(s => s.geneExpression)
        .filter((v): v is number => v !== undefined)
        .sort((a, b) => a - b)
      
      if (values.length > 0) {
        clusterNames.push(label)
        const q1 = values[Math.floor(values.length * 0.25)]
        const median = values[Math.floor(values.length * 0.5)]
        const q3 = values[Math.floor(values.length * 0.75)]
        const min = values[0]
        const max = values[values.length - 1]
        
        clusterData.push([min, q1, median, q3, max])
      }
    })
    
    const option: echarts.EChartsOption = {
      tooltip: {
        trigger: 'item',
        axisPointer: { type: 'shadow' }
      },
      grid: {
        left: '15%',
        right: '10%',
        bottom: '15%',
        top: '10%'
      },
      xAxis: {
        type: 'category',
        data: clusterNames,
        axisLabel: { fontSize: 10 }
      },
      yAxis: {
        type: 'value',
        name: 'Expression'
      },
      series: [{
        type: 'boxplot',
        data: clusterData,
        itemStyle: {
          color: '#91cc75'
        }
      }]
    }
    
    boxplotInstance.setOption(option, true)
  }

  function renderPieChart(
    container: HTMLElement,
    clusterSpotsMap: Map<string, SpotData[]>,
    clusterColorMap: Map<string, string>
  ) {
    if (!pieInstance) {
      pieInstance = echarts.init(container)
    }
    
    const pieData: any[] = []
    clusterSpotsMap.forEach((clusterSpots, label) => {
      pieData.push({
        name: `Cluster ${label}`,
        value: clusterSpots.length,
        itemStyle: {
          color: clusterColorMap.get(label)
        }
      })
    })
    
    const option: echarts.EChartsOption = {
      tooltip: {
        trigger: 'item',
        formatter: '{b}: {c} ({d}%)'
      },
      legend: {
        orient: 'vertical',
        right: '5%',
        top: 'center',
        textStyle: { fontSize: 10 }
      },
      series: [{
        type: 'pie',
        radius: ['40%', '70%'],
        center: ['40%', '50%'],
        data: pieData,
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.5)'
          }
        }
      }]
    }
    
    pieInstance.setOption(option, true)
  }

  function renderBarChart(
    container: HTMLElement,
    clusterSpotsMap: Map<string, SpotData[]>
  ) {
    if (!barInstance) {
      barInstance = echarts.init(container)
    }
    
    const clusterNames: string[] = []
    const spotCounts: number[] = []
    const avgExpressions: number[] = []
    
    clusterSpotsMap.forEach((clusterSpots, label) => {
      clusterNames.push(`Cluster ${label}`)
      spotCounts.push(clusterSpots.length)
      
      const values = clusterSpots
        .map(s => s.geneExpression)
        .filter((v): v is number => v !== undefined)
      
      const avg = values.length > 0 
        ? values.reduce((a, b) => a + b, 0) / values.length 
        : 0
      avgExpressions.push(avg)
    })
    
    const option: echarts.EChartsOption = {
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' }
      },
      legend: {
        data: ['Spot Count', 'Avg Expression'],
        textStyle: { fontSize: 10 }
      },
      grid: {
        left: '15%',
        right: '10%',
        bottom: '15%',
        top: '15%'
      },
      xAxis: {
        type: 'category',
        data: clusterNames,
        axisLabel: { rotate: 45, fontSize: 10 }
      },
      yAxis: [
        {
          type: 'value',
          name: 'Count',
          position: 'left'
        },
        {
          type: 'value',
          name: 'Expression',
          position: 'right'
        }
      ],
      series: [
        {
          name: 'Spot Count',
          type: 'bar',
          data: spotCounts,
          itemStyle: { color: '#5470c6' }
        },
        {
          name: 'Avg Expression',
          type: 'line',
          yAxisIndex: 1,
          data: avgExpressions,
          itemStyle: { color: '#ee6666' }
        }
      ]
    }
    
    barInstance.setOption(option, true)
  }

  function resizeAll() {
    histogramInstance?.resize()
    boxplotInstance?.resize()
    pieInstance?.resize()
    barInstance?.resize()
  }

  function disposeAll() {
    histogramInstance?.dispose()
    boxplotInstance?.dispose()
    pieInstance?.dispose()
    barInstance?.dispose()
    
    histogramInstance = null
    boxplotInstance = null
    pieInstance = null
    barInstance = null
  }

  return {
    renderHistogram,
    renderBoxplot,
    renderPieChart,
    renderBarChart,
    resizeAll,
    disposeAll
  }
}
