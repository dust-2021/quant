<script lang="ts" setup>
import { ref, computed, onBeforeMount, onBeforeUnmount, nextTick } from 'vue'
import { Binance, eventData, binanceInterval, tradeType } from '../../exchanges/binance'
import * as echarts from 'echarts'

// ===== 配置 =====
const HISTORY_COUNT = 200
const INTERVAL_MS: Record<string, number> = {
  '1s': 1000, '1m': 60000, '3m': 180000, '5m': 300000, '15m': 900000,
  '30m': 1800000, '1h': 3600000, '2h': 7200000, '4h': 14400000,
  '6h': 21600000, '8h': 28800000, '12h': 43200000,
  '1d': 86400000, '3d': 259200000, '1w': 604800000, '1M': 2592000000,
}
const INTERVALS: binanceInterval[] = ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d', '3d', '1w', '1M']
const TRADE_TYPES: tradeType[] = ['spot', 'swap']

type KlineItem = { time: number; open: number; close: number; high: number; low: number; volume?: number }

const target = ref('BTCUSDT')
const interval = ref<binanceInterval>('1h')
const t = ref<tradeType>('swap')
const showIntervalPicker = ref(false)
const showTradeTypePicker = ref(false)
const currentStream = computed(() => `${target.value.toLowerCase()}@kline_${interval.value}`)
const binance = Binance.getInstance()

// ===== K线数据 =====
const historyData = ref<KlineItem[]>([])
const currentCandle = ref<KlineItem | null>(null)
let lastKlineTime = 0
let rafId = 0
let chartInstance: echarts.ECharts | null = null
const chartRef = ref<HTMLDivElement | null>(null)
const upColor = '#ef5350'
const downColor = '#26a69a'
const resizeObserver = new ResizeObserver(() => {
  chartInstance?.resize()
})

// 构建 ECharts 所需的全部数据（历史 + 当前）
function buildChartData(): { candlestick: any[]; volumes: any[]; times: string[] } {
  const candlestick: any[] = []
  const volumes: any[] = []
  const times: string[] = []
  for (const item of historyData.value) {
    candlestick.push([item.open, item.close, item.low, item.high])
    volumes.push([candlestick.length - 1, item.volume ?? 0, item.close >= item.open ? 1 : -1])
    times.push(formatTime(item.time))
  }
  if (currentCandle.value) {
    const c = currentCandle.value
    candlestick.push([c.open, c.close, c.low, c.high])
    volumes.push([candlestick.length - 1, c.volume ?? 0, c.close >= c.open ? 1 : -1])
    times.push(formatTime(c.time))
  }
  return { candlestick, volumes, times }
}

function formatTime(ts: number): string {
  const d = new Date(ts)
  const pad = (n: number) => String(n).padStart(2, '0')
  const ms = INTERVAL_MS[interval.value] ?? 60000
  if (ms < 60000) return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
  if (ms < 86400000) return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

// ===== ECharts 初始化 =====
function initChart() {
  if (!chartRef.value) return
  disposeChart()
  chartInstance = echarts.init(chartRef.value)
  const option: echarts.EChartsOption = {
    backgroundColor: 'transparent',
    animation: false,
    grid: [
      { left: '3%', right: '3%', top: '3%', height: '65%' },
      { left: '3%', right: '3%', top: '75%', height: '22%' },
    ],
    xAxis: [
      { type: 'category', gridIndex: 0, data: [], axisLine: { lineStyle: { color: '#666' } }, axisLabel: { show: false } },
      { type: 'category', gridIndex: 1, data: [], axisLine: { lineStyle: { color: '#666' } }, axisLabel: { color: '#999', fontSize: 10 } },
    ],
    yAxis: [
      { type: 'value', gridIndex: 0, scale: true, splitLine: { lineStyle: { color: '#333', type: 'dashed' } }, axisLabel: { color: '#999' } },
      { type: 'value', gridIndex: 1, splitLine: { show: false }, axisLabel: { color: '#999', fontSize: 10 } },
    ],
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross', crossStyle: { color: '#999' } },
      backgroundColor: 'rgba(30, 30, 30, 0.9)',
      borderColor: '#555',
      textStyle: { color: '#ccc', fontSize: 12 },
      formatter: (params: any) => {
        if (!params || params.length === 0) return ''
        const time = params[0].axisValue
        let html = `<div style="font-weight:600;margin-bottom:4px;">${time}</div>`
        for (const p of params) {
          if (p.seriesName === '成交量') continue
          const d = p.data
          if (Array.isArray(d) && d.length >= 4) {
            const change = d[2] - d[1]
            const pct = d[1] !== 0 ? ((change / d[1]) * 100).toFixed(2) : '0.00'
            const sign = change >= 0 ? '+' : ''
            html += `<div>开 <b>${d[1]}</b>  收 <b>${d[2]}</b>  高 <b>${d[4]}</b>  低 <b>${d[3]}</b></div>`
            html += `<div style="color:${change >= 0 ? upColor : downColor}">涨跌 ${sign}${change.toFixed(4)}  ${sign}${pct}%</div>`
          }
        }
        for (const p of params) {
          if (p.seriesName !== '成交量') continue
          html += `<div style="margin-top:2px;color:#999;">成交量 ${p.data?.[1] ?? '-'}</div>`
        }
        return html
      },
    },
    dataZoom: [
      {
        type: 'inside',
        xAxisIndex: [0, 1],
        start: 70,
        end: 100,
        zoomOnMouseWheel: true,
        moveOnMouseMove: true,
        moveOnMouseWheel: false,
      },
    ],
    series: [
      {
        name: 'K线', type: 'candlestick', xAxisIndex: 0, yAxisIndex: 0,
        data: [],
        itemStyle: { color: upColor, color0: downColor, borderColor: upColor, borderColor0: downColor },
        markLine: {
          silent: true,
          symbol: 'none',
          label: { show: false },
          lineStyle: { color: '#e6a23c', type: 'dashed', width: 1 },
          data: [],
        },
      },
      {
        name: '成交量', type: 'bar', xAxisIndex: 1, yAxisIndex: 1,
        data: [],
        itemStyle: {
          color: (params: any) => params.data?.[2] === 1 ? upColor : downColor,
        },
      },
    ],
  }
  chartInstance.setOption(option)
}

function disposeChart() {
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
}

// 刷新图表（throttled via rAF）
function scheduleChartUpdate() {
  if (rafId) return
  rafId = requestAnimationFrame(() => {
    rafId = 0
    if (!chartInstance) return
    const { candlestick, volumes, times } = buildChartData()
    const priceLine = currentCandle.value ? [{ yAxis: currentCandle.value.close }] : []
    chartInstance.setOption({
      xAxis: [{ data: times }, { data: times }],
      series: [{ data: candlestick, markLine: { data: priceLine } }, { data: volumes }],
    } as any)
  })
}

// ===== WS 数据处理 =====
async function handle(r: eventData) {
  if (!r.k) return
  const k = r.k
  const item: KlineItem = {
    time: k.t,
    open: Number(k.o),
    close: Number(k.c),
    high: Number(k.h),
    low: Number(k.l),
    volume: Number(k.v),
  }

  // 检测新K线开始（时间戳变化）
  if (lastKlineTime !== 0 && k.t !== lastKlineTime) {
    // 旧当前K线已完成，加入历史
    if (currentCandle.value) {
      historyData.value.push({ ...currentCandle.value })
      // 保持历史数据上限
      if (historyData.value.length > HISTORY_COUNT * 2) {
        historyData.value = historyData.value.slice(-HISTORY_COUNT)
      }
    }
    // 补拉上一根已完成的K线（防止ws断连期间遗漏）
    fetchMissingKline(lastKlineTime)
  }
  lastKlineTime = k.t
  currentCandle.value = item
  scheduleChartUpdate()
}

// 补拉单根历史K线
async function fetchMissingKline(prevTime: number) {
  const ms = INTERVAL_MS[interval.value] ?? 60000
  try {
    const rows = await binance.historyKline(target.value, interval.value, prevTime, prevTime + ms - 1, t.value)
    if (rows.length > 0) {
      const row = rows[0]
      const k: KlineItem = {
        time: Number(row[0]), open: Number(row[1]), high: Number(row[2]),
        low: Number(row[3]), close: Number(row[4]), volume: Number(row[5]),
      }
      // 检查是否已存在（避免重复）
      const exists = historyData.value.some(h => h.time === k.time)
      if (!exists && (currentCandle.value === null || k.time !== currentCandle.value.time)) {
        historyData.value.push(k)
        historyData.value.sort((a, b) => a.time - b.time)
      }
    }
  } catch { /* 忽略补拉失败 */ }
}

// ===== 切换周期/类型 =====
const switching = ref(false)

async function switchParams(newInterval?: binanceInterval, newType?: tradeType) {
  if (switching.value) return
  switching.value = true
  showIntervalPicker.value = false
  showTradeTypePicker.value = false

  // 取消旧订阅
  binance.unsubscribe([currentStream.value], t.value)

  // 更新参数
  if (newInterval) interval.value = newInterval
  if (newType) t.value = newType

  // 清空数据
  historyData.value = []
  currentCandle.value = null
  lastKlineTime = 0

  // 重新加载历史数据并订阅
  await loadHistoryAndSubscribe()
  switching.value = false
}

async function loadHistoryAndSubscribe() {
  const ms = INTERVAL_MS[interval.value] ?? 60000
  const endTime = Date.now()
  const startTime = endTime - HISTORY_COUNT * ms
  try {
    const rows = await binance.historyKline(target.value, interval.value, startTime, endTime, t.value)
    historyData.value = rows.map(row => ({
      time: Number(row[0]), open: Number(row[1]), high: Number(row[2]),
      low: Number(row[3]), close: Number(row[4]), volume: Number(row[5]),
    }))
    if (historyData.value.length > 0) {
      const last = historyData.value.pop()!
      currentCandle.value = last
      lastKlineTime = last.time
    }
  } catch (e) { console.log(e) }

  if (!chartInstance) {
    await nextTick()
    initChart()
  }
  scheduleChartUpdate()

  // 订阅新的实时数据
  binance.subscribeKline(currentStream.value, t.value, handle)
}

// ===== 生命周期 =====
function closeDropdowns() {
  showIntervalPicker.value = false
  showTradeTypePicker.value = false
}

onBeforeMount(async () => {
  await nextTick()
  if (chartRef.value) resizeObserver.observe(chartRef.value)
  document.addEventListener('click', closeDropdowns)
  await loadHistoryAndSubscribe()
})

onBeforeUnmount(() => {
  document.removeEventListener('click', closeDropdowns)
  resizeObserver.disconnect()
  if (rafId) cancelAnimationFrame(rafId)
  disposeChart()
  binance.unsubscribe([currentStream.value], t.value)
})
</script>

<template>
  <div class="kline-wrapper">
    <!-- 顶部信息栏 -->
    <div class="kline-header">
      <span class="kline-symbol">{{ target }}</span>
      <span class="kline-price" :style="{ color: currentCandle ? (currentCandle.close >= currentCandle.open ? upColor : downColor) : '#999' }">
        {{ currentCandle ? currentCandle.close.toPrecision(8) : '--' }}
      </span>
      <div class="kline-selectors">
        <div class="kline-select" @click.stop="showIntervalPicker = !showIntervalPicker; showTradeTypePicker = false">
          <span>{{ interval }}</span>
          <span class="kline-arrow">▾</span>
          <div v-if="showIntervalPicker" class="kline-dropdown">
            <div v-for="iv in INTERVALS" :key="iv"
              :class="['kline-dropdown__item', { active: iv === interval }]"
              @click.stop="switchParams(iv)">{{ iv }}</div>
          </div>
        </div>
        <span class="kline-sep">|</span>
        <div class="kline-select" @click.stop="showTradeTypePicker = !showTradeTypePicker; showIntervalPicker = false">
          <span>{{ t }}</span>
          <span class="kline-arrow">▾</span>
          <div v-if="showTradeTypePicker" class="kline-dropdown">
            <div v-for="tt in TRADE_TYPES" :key="tt"
              :class="['kline-dropdown__item', { active: tt === t }]"
              @click.stop="switchParams(undefined, tt)">{{ tt }}</div>
          </div>
        </div>
      </div>
    </div>
    <!-- 图表 -->
    <div ref="chartRef" class="kline-chart" v-loading="switching"></div>
  </div>
</template>

<style scoped>
.kline-wrapper {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.kline-header {
  display: flex;
  align-items: center;
  padding: 6px 12px;
  flex-shrink: 0;
  border-bottom: 1px solid #333;
}

.kline-symbol {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary, #e0e0e0);
}

.kline-price {
  margin-left: 10px;
  font-size: 14px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.kline-selectors {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-left: auto;
}

.kline-select {
  position: relative;
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 2px 8px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
  color: var(--text-secondary, #bbb);
  background: rgba(255, 255, 255, 0.06);
  user-select: none;
  transition: background 0.2s;
}
.kline-select:hover {
  background: rgba(255, 255, 255, 0.12);
}

.kline-arrow {
  font-size: 10px;
  color: #888;
}

.kline-sep {
  color: #555;
  font-size: 14px;
}

.kline-dropdown {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 4px;
  min-width: 70px;
  max-height: 260px;
  overflow-y: auto;
  background: #1e1e1e;
  border: 1px solid #444;
  border-radius: 6px;
  z-index: 100;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
}

.kline-dropdown__item {
  padding: 5px 12px;
  cursor: pointer;
  font-size: 13px;
  color: #ccc;
  transition: background 0.15s;
}
.kline-dropdown__item:hover {
  background: rgba(255, 255, 255, 0.08);
}
.kline-dropdown__item.active {
  color: #409eff;
  font-weight: 600;
}

.kline-chart {
  flex: 1;
  min-height: 0;
}
</style>