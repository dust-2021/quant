<script lang="ts" setup>
import { ref, nextTick, onBeforeUnmount, watch } from 'vue'
import { ElButton, ElEmpty, ElSelect, ElOption } from 'element-plus'
import * as echarts from 'echarts'

const props = defineProps<{
  dataJson: string
  signalCol?: string
}>()

const MAX_CHART_ROWS = 10000
const chartRef = ref<HTMLDivElement | null>(null)
let chartInstance: echarts.ECharts | null = null
const chartReady = ref(false)
const chartDataTooLarge = ref(false)
const colorReversed = ref(false)
const candlestickData = ref<any[]>([])
const fundingData = ref<any[]>([])
const drawdownData = ref<any[]>([])
const volumeData = ref<any[]>([])
const signalMarkData = ref<any[]>([])  // 信号竖线标注
const allRows = ref<any[]>([])
const dataCount = ref(0)
const periodMs = ref(3600000)
// 可选字段
const availableFields = ref<string[]>([])
const selectedFields = ref<string[]>([])
// 已知已渲染字段
const knownFields = new Set(['open_time', 'open', 'close', 'high', 'low', 'code',
  '__pos', '__istrade', '__tradeId', '__priceBuy', '__priceSell',
  '__timeSell', '__income', '__trade_volume', '__premium', '__drawdown',
  '__funding', 'quote_asset_volume', 'taker_buy_base_asset_volume',
  'taker_buy_quote_asset_volume', 'number_of_trades', 'ignore'])
// 额外线条颜色
const lineColors = ['#e6a23c', '#67c23a', '#f56c6c', '#909399', '#b37feb', '#36cfc9', '#ff85c0', '#597ef7']

function parseChartData() {
  candlestickData.value = []
  fundingData.value = []
  drawdownData.value = []
  volumeData.value = []
  signalMarkData.value = []
  allRows.value = []
  dataCount.value = 0
  chartDataTooLarge.value = false
  periodMs.value = 3600000
  availableFields.value = []
  if (!props.dataJson) return
  try {
    const arr = JSON.parse(props.dataJson)
    if (!Array.isArray(arr)) return
    if (arr.length > MAX_CHART_ROWS) {
      chartDataTooLarge.value = true
      return
    }
    allRows.value = arr
    dataCount.value = arr.length
    if (arr.length >= 2) {
      periodMs.value = arr[1].open_time - arr[0].open_time
    }
    if (arr.length > 0) {
      availableFields.value = Object.keys(arr[0]).filter(k => !knownFields.has(k))
    }
    // 提取信号标注点
    const sigCol = props.signalCol || 'signal'
    for (let i = 0; i < arr.length; i++) {
      const row = arr[i]
      candlestickData.value.push([row.open_time, row.open, row.close, row.low, row.high])
      fundingData.value.push(row.__funding ?? null)
      drawdownData.value.push(row.__drawdown ?? null)
      volumeData.value.push(row.quote_asset_volume ?? 0)
      // 非空信号点添加竖线标注
      const sigVal = row[sigCol]
      if (sigVal != null && sigVal !== '' && !Number.isNaN(Number(sigVal))) {
        const val = Number(sigVal)
        signalMarkData.value.push({
          xAxis: i,
          name: val > 0 ? `BUY ${val.toFixed(2)}` : `SELL ${val.toFixed(2)}`,
          lineStyle: { color: val > 0 ? '#ef5350' : '#26a69a', width: 1.5, type: 'dashed' as const },
          label: { show: true, position: 'insideStartTop' as const, formatter: val > 0 ? '▲' : '▼', fontSize: 10, color: val > 0 ? '#ef5350' : '#26a69a' },
        })
      }
    }
  } catch { /* ignore */ }
}

async function doRenderChart() {
  if (!candlestickData.value.length) return
  chartReady.value = true
  await nextTick()
  if (!chartRef.value) return
  disposeChart()
  chartInstance = echarts.init(chartRef.value)
  const upColor = colorReversed.value ? '#26a69a' : '#ef5350'
  const downColor = colorReversed.value ? '#ef5350' : '#26a69a'

  // 构建选中字段的 series
  const extraSeries: any[] = selectedFields.value.map((field, idx) => ({
    name: field,
    type: 'line',
    xAxisIndex: 0,
    yAxisIndex: 1,
    data: allRows.value.map((r: any) => r[field] ?? null),
    smooth: true,
    symbol: 'none',
    connectNulls: true,
    lineStyle: { color: lineColors[idx % lineColors.length], width: 1.5 },
  }))

  chartInstance.setOption({
    legend: {
      data: ['K线', '资金曲线', '回撤', ...selectedFields.value],
      top: 0,
      selected: { '资金曲线': false, '回撤': false },
    },
    grid: [
      { left: 60, right: 120, top: 30, bottom: '38%' },
      { left: 60, right: 120, top: '75%', bottom: 0 },
    ],
    xAxis: [
      {
        type: 'category',
        gridIndex: 0,
        data: candlestickData.value.map((item: any[]) => {
          const date = new Date(item[0])
          const pad = (n: number) => String(n).padStart(2, '0')
          if (periodMs.value < 60000) {
            return `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
          }
          if (periodMs.value < 3600000) {
            return `${date.getMonth() + 1}/${date.getDate()} ${pad(date.getHours())}:${pad(date.getMinutes())}`
          }
          if (periodMs.value < 86400000) {
            return `${date.getMonth() + 1}/${date.getDate()} ${pad(date.getHours())}:00`
          }
          return `${date.getMonth() + 1}/${date.getDate()}`
        }),
        axisLabel: { fontSize: 10 },
      },
      {
        type: 'category',
        gridIndex: 1,
        data: candlestickData.value.map(() => ''),
        axisLabel: { show: false },
        axisTick: { show: false },
        axisLine: { show: false },
      },
    ],
    yAxis: [
      { type: 'value', scale: true, position: 'left', name: '价格', gridIndex: 0 },
      { type: 'value', scale: true, position: 'right', name: '资金', splitLine: { show: false }, gridIndex: 0 },
      { type: 'value', scale: true, position: 'right', offset: 60, name: '回撤', splitLine: { show: false }, axisLabel: { formatter: function(v: number) { return (v * 100).toFixed(0) + '%' } }, gridIndex: 0 },
      { type: 'value', scale: true, position: 'left', name: '交易额', splitLine: { show: false }, axisLabel: { fontSize: 10 }, gridIndex: 1 },
    ],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: candlestickData.value.map((d: any[]) => d.slice(1)),
        itemStyle: {
          color: upColor,
          color0: downColor,
          borderColor: upColor,
          borderColor0: downColor,
        },
        markLine: signalMarkData.value.length > 0 ? {
          silent: true,
          symbol: 'none',
          data: signalMarkData.value,
        } : undefined,
      },
      {
        name: '资金曲线',
        type: 'line',
        xAxisIndex: 0,
        yAxisIndex: 1,
        data: fundingData.value,
        smooth: true,
        symbol: 'none',
        connectNulls: true,
        lineStyle: { color: '#409eff', width: 1.5 },
      },
      {
        name: '回撤',
        type: 'line',
        xAxisIndex: 0,
        yAxisIndex: 2,
        data: drawdownData.value,
        smooth: true,
        symbol: 'none',
        connectNulls: true,
        lineStyle: { color: '#e6a23c', width: 1.5 },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(230, 162, 60, 0.25)' },
            { offset: 1, color: 'rgba(230, 162, 60, 0.02)' },
          ]),
        },
      },
      {
        name: '交易额',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 3,
        data: volumeData.value,
        itemStyle: {
          color: function (params: any) {
            const idx = params.dataIndex
            const row = candlestickData.value[idx]
            if (!row) return downColor
            return row[2] >= row[1] ? upColor : downColor
          },
        },
      },
      ...extraSeries,
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1] },
    ],
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
    },
  }, true)
}

function disposeChart() {
  chartInstance?.dispose()
  chartInstance = null
}

function toggleColor() {
  colorReversed.value = !colorReversed.value
  if (chartReady.value) {
    doRenderChart()
  }
}

onBeforeUnmount(() => {
  disposeChart()
})

// 初始解析
parseChartData()

// dataJson 变化时重新解析
watch(() => props.dataJson, () => {
  chartReady.value = false
  disposeChart()
  parseChartData()
})
</script>

<template>
  <div class="chart-wrapper">
    <template v-if="chartDataTooLarge">
      <ElEmpty description="数据量过大，不绘制图表" />
    </template>
    <template v-else-if="!chartReady && candlestickData.length">
      <div class="chart-placeholder">
        <p>共 {{ dataCount }} 条 K 线数据</p>
        <div class="chart-actions">
          <ElButton type="primary" @click="doRenderChart">渲染图表</ElButton>
          <ElButton @click="toggleColor">{{ colorReversed ? '红跌绿涨' : '红涨绿跌' }}</ElButton>
        </div>
        <div class="chart-fields" v-if="availableFields.length">
          <span class="chart-fields__label">附加字段：</span>
          <ElSelect v-model="selectedFields" multiple placeholder="选择要显示的字段" size="small" style="width: 360px;">
            <ElOption v-for="f in availableFields" :key="f" :label="f" :value="f" />
          </ElSelect>
        </div>
      </div>
    </template>
    <template v-else-if="!candlestickData.length">
      <ElEmpty description="无图表数据" />
    </template>
    <div v-show="chartReady" ref="chartRef" class="chart-container" />
  </div>
</template>

<style scoped>
.chart-wrapper {
  width: 100%;
}

.chart-container {
  width: 100%;
  height: 550px;
}

.chart-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  gap: 12px;
  color: var(--text-secondary);
}

.chart-actions {
  display: flex;
  gap: 8px;
}

.chart-fields {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
}

.chart-fields__label {
  font-size: 13px;
  color: var(--text-secondary);
  white-space: nowrap;
}
</style>
