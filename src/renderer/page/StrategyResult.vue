<script lang="ts" setup>
import { ref, computed, onBeforeMount } from 'vue'
import { useRoute } from 'vue-router'
import {
  ElCard, ElTag, ElScrollbar, ElDescriptions, ElDescriptionsItem,
  ElAlert, ElSkeleton, ElTable, ElTableColumn,
  ElTabs, ElTabPane, ElEmpty, ElSelect, ElOption, ElButton
} from 'element-plus'
import { fetch } from '../../api/base'
import { taskResult } from '../../store'
import ResultChartOfDefault from '../element/ResultChartOfDefault.vue'

interface TaskMeta {
  strategyName: string
  runnerName: string
  multiParam: string
  multiValues: (string | number | boolean)[]
  subIds?: string[]
}

interface SubResult {
  id: string
  value: string
  status: 'success' | 'failed' | 'loading'
  result?: taskResult
  error?: string
  /** 预解析的交易数据行 */
  tradeRows?: any[]
  /** 交易数据中的信号列名 */
  signalCol?: string
}

const route = useRoute()
const taskId = (route.query.id as string) || ''

const meta = ref<TaskMeta | null>(null)
const singleResult = ref<taskResult | null>(null)
const singleError = ref('')
const singleTradeRows = ref<any[]>([])
const singleSignalCol = ref('signal')
const detailTab = ref<'chart' | 'trade'>('chart')

const subResults = ref<SubResult[]>([])
const selectedSubIndex = ref(0)
const selectedSubResult = computed(() => subResults.value[selectedSubIndex.value] ?? null)
const firstSuccessResult = computed(() => subResults.value.find(s => s.status === 'success' && s.result)?.result ?? null)
const loading = ref(true)

const metricLabels: Record<string, string> = {
  netValue: '累计净值',
  premium: '手续费',
  annualizedRateOfReturn: '年化收益率',
  monthlyRateOfReturn: '月化收益率',
  maximumDrawdown: '最大回撤',
  tradeCount: '交易次数',
  winRate: '胜率 (%)',
  maximumProfit: '最大盈利 (%)',
  maximumLoss: '最大亏损 (%)',
  averageProfitLossRatio: '平均盈亏比',
}

function parseTradeData(json: string | undefined): any[] {
  if (!json) return []
  try {
    const arr = JSON.parse(json)
    return Array.isArray(arr) ? arr : []
  } catch {
    return []
  }
}

/** 从执行参数中获取信号列名，默认 'signal' */
function detectSignalCol(params: Record<string, any> | undefined): string {
  return params?.signalName || 'signal'
}

function formatMetric(val: any): string {
  if (val === null || val === undefined) return '-'
  if (typeof val === 'number') {
    return val.toFixed(4)
  }
  return String(val)
}

function formatTime(ts: number | null | undefined): string {
  if (ts == null) return '-'
  return new Date(ts).toLocaleString()
}

function formatPeriod(seconds: number | null | undefined): string {
  if (seconds == null) return '-'
  if (seconds >= 86400) return '天'
  if (seconds >= 3600) return '小时'
  if (seconds >= 60) return '分钟'
  return '秒'
}

function exportCsv() {
  if (!singleResult.value?.data) return
  try {
    const rows = JSON.parse(singleResult.value.data)
    if (!Array.isArray(rows) || !rows.length) return
    const cols = Object.keys(rows[0])
    const header = cols.join(',')
    const body = rows.map((r: any) => cols.map(c => {
      const v = r[c]
      if (v === null || v === undefined) return ''
      const s = String(v)
      return s.includes(',') || s.includes('"') || s.includes('\n') ? `"${s.replace(/"/g, '""')}"` : s
    }).join(','))
    const csv = [header, ...body].join('\n')
    const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `backtest_data_${taskId.slice(0, 8)}.csv`
    a.click()
    URL.revokeObjectURL(url)
  } catch { /* ignore */ }
}

function formatTarget(target: string[] | null | undefined): string {
  if (!target || !target.length) return '-'
  if (target.length <= 5) return target.join(', ')
  return target.slice(0, 5).join(', ') + ` ...等 ${target.length} 个`
}

function initSingleResult(result: taskResult) {
  singleResult.value = result
  singleTradeRows.value = parseTradeData(result.tradeData)
  singleSignalCol.value = detectSignalCol(result.params)
}

function initSubResult(sr: SubResult) {
  if (sr.result?.tradeData) {
    sr.tradeRows = parseTradeData(sr.result.tradeData)
    sr.signalCol = detectSignalCol(sr.result.params)
  }
  // 从实际执行参数中获取并行参数值
  if (sr.result?.params && meta.value?.multiParam) {
    const v = sr.result.params[meta.value.multiParam]
    if (v !== undefined && v !== null) {
      sr.value = String(v)
    }
  }
}

async function loadResult() {
  const raw = sessionStorage.getItem(`task_${taskId}`)
  if (raw) {
    meta.value = JSON.parse(raw)
  }

  if (meta.value?.subIds && meta.value.subIds.length > 1) {
    const multiValues = meta.value.multiValues || []
    subResults.value = meta.value.subIds.map((subId, i) => ({
      id: subId,
      value: String(multiValues[i] ?? subId.slice(0, 8)),
      status: 'loading' as const,
    }))
    const promises = subResults.value.map(async (sr) => {
      const resp = await fetch<any>(`/api/execute/result/${sr.id}`, 'GET')
      if (resp.code === 0) {
        const result = resp.data as taskResult
        sr.status = 'success'
        sr.result = result
        // 订单数据
        if (result.tradeData) {
          sr.tradeRows = parseTradeData(result.tradeData)
          sr.signalCol = detectSignalCol(result.params)
        }
        // 从实际执行参数中提取并行参数值
        if (result.params && meta.value?.multiParam) {
          const v = result.params[meta.value.multiParam]
          if (v !== undefined && v !== null) {
            sr.value = String(v)
          }
        }
      } else {
        sr.status = 'failed'
        sr.error = resp.msg || '执行失败'
      }
    })
    await Promise.all(promises)
  } else {
    const resp = await fetch<any>(`/api/execute/result/${taskId}`, 'GET')
    if (resp.code === 0) {
      initSingleResult(resp.data as taskResult)
    } else {
      singleError.value = resp.msg || '执行失败'
    }
  }
  loading.value = false
}

onBeforeMount(() => {
  loadResult()
})
</script>

<template>
  <div class="result-page">
    <div class="result-header">
      <h3>回测结果</h3>
      <span v-if="meta?.strategyName" class="result-header__name">{{ meta.strategyName }}</span>
      <ElTag v-if="meta?.multiParam" type="info" size="small" effect="plain">
        并行: {{ meta.multiParam }}
      </ElTag>
    </div>

    <ElScrollbar>
      <!-- 加载中 -->
      <ElSkeleton v-if="loading" :rows="6" animated />

      <!-- 多参数并行结果 -->
      <template v-else-if="subResults.length > 0">
        <!-- 回测信息（取第一个成功结果） -->
        <div class="time-info" v-if="firstSuccessResult">
          <div>回测区间：{{ formatTime(firstSuccessResult.startTime) }} ~ {{ formatTime(firstSuccessResult.endTime) }} · 周期：{{ formatPeriod(firstSuccessResult.period) }}</div>
          <div>标的：{{ formatTarget(firstSuccessResult.target) }}</div>
        </div>
        <!-- 执行参数（取第一个成功结果） -->
        <template v-if="firstSuccessResult">
          <h4 style="margin: 0 0 8px;">执行参数</h4>
          <ElDescriptions :column="4" border size="small" style="margin-bottom: 16px;">
            <ElDescriptionsItem v-for="(v, k) in firstSuccessResult.params" :key="k" :label="String(k)">
              {{ typeof v === 'boolean' ? String(v) : formatMetric(v) }}
            </ElDescriptionsItem>
          </ElDescriptions>
        </template>
        <!-- 指标汇总表 -->
        <h4 style="margin: 0 0 8px;">指标对比</h4>
        <ElTable :data="subResults" stripe size="small" style="width: 100%; margin-bottom: 16px;">
          <ElTableColumn prop="value" :label="meta?.multiParam || '参数值'" width="120" fixed="left">
            <template #default="{ row }">
              <span :style="{ fontWeight: 500 }">{{ row.value }}</span>
              <ElTag v-if="row.status === 'failed'" type="danger" size="small" effect="plain" style="margin-left: 4px;">失败</ElTag>
            </template>
          </ElTableColumn>
          <ElTableColumn v-for="(label, key) in metricLabels" :key="key" :label="label" min-width="100" align="right">
            <template #default="{ row }">
              <span v-if="row.status === 'success' && row.result">{{ formatMetric(row.result[key as keyof taskResult]) }}</span>
              <span v-else style="color: var(--el-color-danger);">-</span>
            </template>
          </ElTableColumn>
        </ElTable>

        <!-- 失败任务错误 -->
        <ElAlert v-for="sr in subResults.filter(s => s.status === 'failed')" :key="sr.id"
          :title="`${meta?.multiParam || '参数'} = ${sr.value} 执行失败`" type="error" show-icon :closable="false"
          style="margin-bottom: 8px;">
          <template #default><pre class="error-trace" style="max-height: 120px;">{{ sr.error }}</pre></template>
        </ElAlert>

        <!-- 订单详情：下拉选择参数 -->
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
          <h4 style="margin: 0;">交易订单</h4>
          <ElSelect v-model="selectedSubIndex" size="small" style="width: 180px;">
            <ElOption v-for="(sr, idx) in subResults.filter(s => s.status === 'success')" :key="sr.id"
              :label="`${meta?.multiParam || '参数'} = ${sr.value}`" :value="idx" />
          </ElSelect>
        </div>
        <ElTable
          v-if="selectedSubResult?.tradeRows?.length"
          :data="selectedSubResult.tradeRows"
          stripe size="small" max-height="300" style="width: 100%;"
        >
          <ElTableColumn prop="open_time" label="开仓时间" width="160">
            <template #default="{ row }">{{ formatTime(row.open_time) }}</template>
          </ElTableColumn>
          <ElTableColumn :label="selectedSubResult.signalCol || '信号'" width="80">
            <template #default="{ row }">{{ row[selectedSubResult.signalCol || 'signal'] }}</template>
          </ElTableColumn>
          <ElTableColumn prop="open" label="开" width="100" />
          <ElTableColumn prop="high" label="高" width="100" />
          <ElTableColumn prop="low" label="低" width="100" />
          <ElTableColumn prop="close" label="收" width="100" />
          <ElTableColumn prop="__timeSell" label="平仓时间" width="160">
            <template #default="{ row }">{{ formatTime(row.__timeSell) }}</template>
          </ElTableColumn>
          <ElTableColumn prop="__priceBuy" label="买入价" width="100" />
          <ElTableColumn prop="__priceSell" label="卖出价" width="100" />
          <ElTableColumn prop="__income" label="收益率" width="100">
            <template #default="{ row }">{{ row.__income != null ? (row.__income * 100).toFixed(2) + '%' : '-' }}</template>
          </ElTableColumn>
        </ElTable>
        <ElEmpty v-else description="暂无订单数据" />
      </template>

      <!-- 单任务结果 -->
      <template v-else>
        <ElAlert v-if="singleError" :title="'执行失败'" type="error" show-icon :closable="false" style="margin-bottom: 12px;" />
        <pre v-if="singleError" class="error-trace">{{ singleError }}</pre>
        <template v-else-if="singleResult">
          <!-- 执行参数 -->
          <h4 v-if="singleResult.params && Object.keys(singleResult.params).length" style="margin: 0 0 8px;">执行参数</h4>
          <ElDescriptions v-if="singleResult.params && Object.keys(singleResult.params).length" :column="4" border size="small" style="margin-bottom: 16px;">
            <ElDescriptionsItem v-for="(v, k) in singleResult.params" :key="k" :label="String(k)">
              {{ typeof v === 'boolean' ? String(v) : formatMetric(v) }}
            </ElDescriptionsItem>
          </ElDescriptions>
          <!-- 回测起止时间 & 爆仓 -->
          <div class="time-info">
            <div style="display: flex; align-items: center; gap: 8px;">
              <span>回测区间：{{ formatTime(singleResult.startTime) }} ~ {{ formatTime(singleResult.endTime) }} · 周期：{{ formatPeriod(singleResult.period) }}</span>
              <ElButton v-if="singleResult.data" size="small" @click="exportCsv">导出CSV</ElButton>
            </div>
            <div>标的：{{ formatTarget(singleResult.target) }}</div>
            <div>
              <span v-if="singleResult.liquidation != null" style="color: var(--el-color-danger);">爆仓时间：{{ formatTime(singleResult.liquidation) }}</span>
              <span v-else style="color: var(--el-color-success);">未爆仓</span>
            </div>
          </div>
          <ElDescriptions :column="4" border size="small" style="margin-bottom: 16px;">
            <ElDescriptionsItem v-for="(label, key) in metricLabels" :key="key" :label="label">
              {{ formatMetric(singleResult[key as keyof taskResult]) }}
            </ElDescriptionsItem>
          </ElDescriptions>

          <!-- 图表 & 交易订单 Tab 切换 -->
          <ElTabs v-model="detailTab" type="card">
            <ElTabPane label="K线图" name="chart">
              <ResultChartOfDefault
                v-if="singleResult.data && meta?.runnerName === 'default'"
                :data-json="singleResult.data"
              />
              <ElEmpty v-else description="仅 default 执行器支持图表" />
            </ElTabPane>
            <ElTabPane label="交易订单" name="trade">
              <ElTable
                v-if="singleTradeRows.length"
                :data="singleTradeRows"
                stripe
                size="small"
                max-height="400"
                style="width: 100%;"
              >
                <ElTableColumn prop="open_time" label="开仓时间" width="160">
                  <template #default="{ row }">
                    {{ formatTime(row.open_time) }}
                  </template>
                </ElTableColumn>
                <ElTableColumn :label="singleSignalCol" width="80">
                  <template #default="{ row }">
                    {{ row[singleSignalCol] }}
                  </template>
                </ElTableColumn>
                <ElTableColumn prop="open" label="开" width="100" />
                <ElTableColumn prop="high" label="高" width="100" />
                <ElTableColumn prop="low" label="低" width="100" />
                <ElTableColumn prop="close" label="收" width="100" />
                <ElTableColumn prop="__timeSell" label="平仓时间" width="160">
                  <template #default="{ row }">
                    {{ formatTime(row.__timeSell) }}
                  </template>
                </ElTableColumn>
                <ElTableColumn prop="__priceBuy" label="买入价" width="100" />
                <ElTableColumn prop="__priceSell" label="卖出价" width="100" />
                <ElTableColumn prop="__income" label="收益率" width="100">
                  <template #default="{ row }">
                    {{ row.__income != null ? (row.__income * 100).toFixed(2) + '%' : '-' }}
                  </template>
                </ElTableColumn>
              </ElTable>
              <ElEmpty v-else description="暂无交易数据" />
            </ElTabPane>
          </ElTabs>
        </template>
      </template>
    </ElScrollbar>
  </div>
</template>

<style scoped>
.result-page {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 16px;
  box-sizing: border-box;
  background-color: var(--bg-page);
}

.result-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  flex-shrink: 0;
}

.result-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.result-header__name {
  color: var(--text-secondary);
  font-size: 14px;
  flex: 1;
}

.sub-result-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.time-info {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 12px;
  line-height: 1.6;
}

.error-trace {
  background-color: var(--el-fill-color-light);
  border: 1px solid var(--el-border-color-light);
  border-radius: 4px;
  padding: 12px;
  max-height: 300px;
  overflow: auto;
  font-family: 'Courier New', Courier, monospace;
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
}

.chart-container {
  width: 100%;
  height: 420px;
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
</style>