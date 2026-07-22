<script lang="ts" setup>
import { ref, computed, onBeforeMount } from 'vue'
import { useRoute } from 'vue-router'
import {
  ElCard, ElTag, ElScrollbar, ElDescriptions, ElDescriptionsItem,
  ElAlert, ElSkeleton, ElTable, ElTableColumn, ElMessage, ElMessageBox, ElCollapse, ElCollapseItem,
  ElTabs, ElTabPane, ElEmpty, ElSelect, ElOption, ElButton
} from 'element-plus'
import { fetch } from '../../api/base'
import { taskResult } from '../../store'
import { getSavedResultDetail, saveStrategyResult } from '../../api/strategy'
import ResultChartOfDefault from '../element/ResultChartOfDefault.vue'

interface TaskMeta {
  strategyName: string
  runnerName: string
  multiParamKeys: string[]
  strategyUid: string
  strategyVersion: string
  factorSnapshots?: { uuid: string; name: string; version: string; params: any[] }[]
  subIds?: string[]
}

interface SubResult {
  id: string
  /** 多参数值，key 为纯净参数名 */
  paramDisplay: Record<string, string>
  status: 'success' | 'failed' | 'loading'
  result?: taskResult
  error?: string
  tradeRows?: any[]
  signalCol?: string
}

const route = useRoute()
const taskId = (route.query.id as string) || ''
const isSaved = route.query.saved === '1'

const meta = ref<TaskMeta | null>(null)
const savedInfo = ref<{
  strategyVersion: string; strategyParams: Record<string, any>;
  factorSnapshots: { uuid: string; name: string; version: string; params: any[] }[];
} | null>(null)
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

/** 指标列的排序方法 */
const metricSortFns = Object.fromEntries(
  Object.keys(metricLabels).map(key => [key, (a: SubResult, b: SubResult) => {
    const va = a.result?.[key as keyof taskResult]
    const vb = b.result?.[key as keyof taskResult]
    if (va == null && vb == null) return 0
    if (va == null) return 1
    if (vb == null) return -1
    return (Number(va) || 0) - (Number(vb) || 0)
  }])
)

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
  // 从执行参数中提取多参数值（使用完整前缀键）
  sr.paramDisplay = {}
  if (sr.result?.params && meta.value?.multiParamKeys) {
    for (const key of meta.value.multiParamKeys) {
      const v = sr.result.params[key]
      if (v !== undefined && v !== null) {
        sr.paramDisplay[key] = String(v)
      }
    }
  }
}

async function loadResult() {
  // 已保存结果：从 API 加载
  if (isSaved) {
    const saved = await getSavedResultDetail(taskId)
    if (!saved) { loading.value = false; return }
    meta.value = {
      strategyName: saved.name,
      runnerName: saved.runner_name,
      multiParamKeys: saved.multi_param_keys || [],
      strategyUid: saved.strategy_uid || '',
      strategyVersion: saved.strategy_version || '',
    }
    savedInfo.value = {
      strategyVersion: saved.strategy_version || '',
      strategyParams: saved.strategy_params || {},
      factorSnapshots: saved.factor_snapshots || [],
    }
    // 重建单结果数据
    singleResult.value = {
      startTime: saved.exec_start_time * 1000,
      endTime: saved.exec_end_time * 1000,
      target: saved.targets || [],
      period: saved.period,
      params: saved.strategy_params || {},
      liquidation: null,
      data: saved.chart_data,
      premium: 0,
      netValue: saved.metrics?.netValue ?? 0,
      annualizedRateOfReturn: saved.metrics?.annualizedRateOfReturn ?? 0,
      monthlyRateOfReturn: saved.metrics?.monthlyRateOfReturn ?? 0,
      maximumDrawdown: saved.metrics?.maximumDrawdown ?? 0,
      tradeCount: saved.metrics?.tradeCount ?? 0,
      winRate: saved.metrics?.winRate ?? null,
      maximumProfit: saved.metrics?.maximumProfit ?? 0,
      maximumLoss: saved.metrics?.maximumLoss ?? 0,
      averageProfitLossRatio: saved.metrics?.averageProfitLossRatio ?? 0,
      tradeData: saved.trade_data,
    }
    initSingleResult(singleResult.value)
    // 多参数子结果
    if (saved.multi_results && saved.multi_results.length > 0) {
      subResults.value = saved.multi_results.map((mr: any, i: number) => {
        const m = mr.metrics || {}
        const r: taskResult = {
          startTime: saved.exec_start_time * 1000, endTime: saved.exec_end_time * 1000,
          target: saved.targets || [], period: saved.period,
          params: { ...(saved.strategy_params || {}), ...(mr.key_values || {}) },
          liquidation: null, data: null,
          premium: 0,
          netValue: m.netValue ?? 0, annualizedRateOfReturn: m.annualizedRateOfReturn ?? 0,
          monthlyRateOfReturn: m.monthlyRateOfReturn ?? 0, maximumDrawdown: m.maximumDrawdown ?? 0,
          tradeCount: m.tradeCount ?? 0, winRate: m.winRate ?? null,
          maximumProfit: m.maximumProfit ?? 0, maximumLoss: m.maximumLoss ?? 0,
          averageProfitLossRatio: m.averageProfitLossRatio ?? 0,
          tradeData: mr.trade_data || null,
        }
        const sr: SubResult = { id: `saved_${i}`, paramDisplay: {}, status: 'success', result: r }
        initSubResult(sr)
        return sr
      })
    }
    loading.value = false
    return
  }

  // 实时任务结果
  const raw = sessionStorage.getItem(`task_${taskId}`)
  if (raw) { meta.value = JSON.parse(raw) }

  if (meta.value?.subIds && meta.value.subIds.length > 1) {
    subResults.value = meta.value.subIds.map((subId) => ({
      id: subId,
      paramDisplay: {},
      status: 'loading' as const,
    }))
    const promises = subResults.value.map(async (sr) => {
      const resp = await fetch<any>(`/api/execute/result/${sr.id}`, 'GET')
      if (resp.code === 0) {
        const result = resp.data as taskResult
        sr.status = 'success'
        sr.result = result
        if (result.tradeData) {
          sr.tradeRows = parseTradeData(result.tradeData)
          sr.signalCol = detectSignalCol(result.params)
        }
        // 提取多参数值（使用完整前缀键）
        sr.paramDisplay = {}
        if (result.params && meta.value?.multiParamKeys) {
          for (const key of meta.value.multiParamKeys) {
            const v = result.params[key]
            if (v !== undefined && v !== null) {
              sr.paramDisplay[key] = String(v)
            }
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
  // 填充运行时版本快照
  if (!isSaved && meta.value) {
    savedInfo.value = {
      strategyVersion: meta.value.strategyVersion || '',
      strategyParams: firstSuccessResult.value?.params || singleResult.value?.params || {},
      factorSnapshots: meta.value.factorSnapshots || [],
    }
  }
}

async function handleSaveResult() {
  try {
    const isMulti = subResults.value.length > 0
    const baseResult = isMulti ? firstSuccessResult.value : singleResult.value
    if (!baseResult) return
    const { value: name } = await ElMessageBox.prompt('请输入保存名称', '保存回测结果', {
      confirmButtonText: '保存', cancelButtonText: '取消',
      inputValue: meta.value?.strategyName || '',
    })
    if (!name) return
    const payload: any = {
      result_uuid: taskId, name,
      strategy_uid: meta.value?.strategyUid || '',
      strategy_version: meta.value?.strategyVersion || '',
      exec_start_time: Math.floor(baseResult.startTime / 1000), exec_end_time: Math.floor(baseResult.endTime / 1000),
      period: baseResult.period, targets: baseResult.target,
      runner_name: meta.value?.runnerName || 'default',
      metrics: {},
      strategy_params: baseResult.params,
      factor_snapshots: meta.value?.factorSnapshots || savedInfo.value?.factorSnapshots || null,
      trade_data: isMulti ? null : singleResult.value?.tradeData || null,
      chart_data: isMulti ? null : singleResult.value?.data || null,
      multi_param_keys: meta.value?.multiParamKeys || [],
    }
    // 指标
    if (isMulti) {
      // 多参数：metrics 填第一个成功结果
      for (const key of Object.keys(metricLabels)) {
        payload.metrics[key] = baseResult[key as keyof taskResult]
      }
    } else {
      for (const key of Object.keys(metricLabels)) {
        payload.metrics[key] = singleResult.value![key as keyof taskResult]
      }
    }
    // 多参数子结果
    if (isMulti) {
      payload.multi_results = subResults.value.map(sr => ({
        key_values: sr.paramDisplay,
        metrics: sr.result ? Object.fromEntries(
          Object.keys(metricLabels).map(k => [k, sr.result![k as keyof taskResult]])
        ) : {},
        trade_data: sr.result?.tradeData || null,
      }))
    }
    const resp = await saveStrategyResult(payload)
    if (resp.code === 0) {
      ElMessage.success('结果已保存')
    } else {
      ElMessage.error('保存失败: ' + (resp.msg || ''))
    }
  } catch { /* 取消 */ }
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
      <ElTag v-if="meta?.multiParamKeys?.length" type="info" size="small" effect="plain">
        并行: {{ meta.multiParamKeys.length }} 参数
      </ElTag>
      <ElButton v-if="!isSaved && (singleResult || subResults.length > 0)" size="small" type="success" style="margin-left: auto;" @click="handleSaveResult">保存结果</ElButton>
    </div>

    <div class="result-body">
      <!-- 加载中 -->
      <ElSkeleton v-if="loading" :rows="6" animated />

      <!-- 多参数并行结果 -->
      <template v-else-if="subResults.length > 0">
        <!-- 回测信息（取第一个成功结果） -->
        <div class="time-info" v-if="firstSuccessResult">
          <div>回测区间：{{ formatTime(firstSuccessResult.startTime) }} ~ {{ formatTime(firstSuccessResult.endTime) }} · 周期：{{ formatPeriod(firstSuccessResult.period) }}</div>
          <div>标的：{{ formatTarget(firstSuccessResult.target) }}</div>
        </div>
        <!-- 版本与参数快照（已保存结果） -->
        <ElCollapse v-if="savedInfo" style="margin-bottom: 12px;">
          <ElCollapseItem title="版本 & 参数快照" name="snapshot">
            <div v-if="savedInfo.strategyVersion" style="margin-bottom: 8px;">
              <span style="font-weight: 600; font-size: 13px;">策略版本：</span>
              <ElTag size="small" type="primary">{{ savedInfo.strategyVersion }}</ElTag>
            </div>
            <template v-if="Object.keys(savedInfo.strategyParams).length">
              <div style="font-weight: 600; font-size: 13px; margin-bottom: 4px;">策略参数：</div>
              <ElDescriptions :column="3" border size="small" style="margin-bottom: 8px;">
                <ElDescriptionsItem v-for="(v, k) in savedInfo.strategyParams" :key="k" :label="String(k)">
                  {{ typeof v === 'boolean' ? String(v) : v }}
                </ElDescriptionsItem>
              </ElDescriptions>
            </template>
            <template v-if="savedInfo.factorSnapshots.length">
              <div style="font-weight: 600; font-size: 13px; margin-bottom: 4px;">因子快照：</div>
              <div v-for="fs in savedInfo.factorSnapshots" :key="fs.uuid" style="margin-bottom: 8px;">
                <span style="font-size: 13px;">{{ fs.name }}</span>
                <ElTag size="small" type="info" effect="plain" style="margin-left: 6px;">v{{ fs.version }}</ElTag>
                <ElDescriptions v-if="fs.params && fs.params.length" :column="3" border size="small" style="margin-top: 4px;">
                  <ElDescriptionsItem v-for="p in fs.params" :key="p.name" :label="p.name">
                    {{ typeof p.v === 'boolean' ? String(p.v) : p.v }}
                  </ElDescriptionsItem>
                </ElDescriptions>
              </div>
            </template>
          </ElCollapseItem>
        </ElCollapse>
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
        <ElTable :data="subResults" stripe size="small" max-height="400" style="width: 100%; margin-bottom: 16px;">
          <ElTableColumn v-for="key in meta?.multiParamKeys || []" :key="key"
            :label="key.startsWith('_factor.') ? key.replace('_factor.', '').replace('.', ':') : key.replace('_strategy.', '')"
            :min-width="100" fixed="left" :prop="key" sortable
          >
            <template #default="{ row }">
              <span :style="{ fontWeight: 500 }">{{ row.paramDisplay?.[key] ?? '-' }}</span>
              <ElTag v-if="row.status === 'failed'" type="danger" size="small" effect="plain" style="margin-left: 4px;">失败</ElTag>
            </template>
          </ElTableColumn>
          <ElTableColumn v-for="(label, key) in metricLabels" :key="key" :label="label" min-width="100" align="right"
            sortable :sort-method="metricSortFns[key]" :prop="key"
          >
            <template #default="{ row }">
              <span v-if="row.status === 'success' && row.result">{{ formatMetric(row.result[key as keyof taskResult]) }}</span>
              <span v-else style="color: var(--el-color-danger);">-</span>
            </template>
          </ElTableColumn>
        </ElTable>

        <!-- 失败任务错误 -->
        <ElAlert v-for="sr in subResults.filter(s => s.status === 'failed')" :key="sr.id"
          :title="`执行失败 (${Object.entries(sr.paramDisplay).map(([k, v]) => `${k}=${v}`).join(', ') || sr.id.slice(0, 8)})`" type="error" show-icon :closable="false"
          style="margin-bottom: 8px;">
          <template #default><pre class="error-trace" style="max-height: 120px;">{{ sr.error }}</pre></template>
        </ElAlert>

        <!-- 订单详情：下拉选择参数 -->
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
          <h4 style="margin: 0;">交易订单</h4>
          <ElSelect v-model="selectedSubIndex" size="small" style="width: 240px;">
            <ElOption v-for="(sr, idx) in subResults.filter(s => s.status === 'success')" :key="sr.id"
              :label="Object.entries(sr.paramDisplay).map(([k, v]) => `${k}=${v}`).join(', ') || sr.id.slice(0, 8)" :value="idx" />
          </ElSelect>
        </div>
        <ElTable
          v-if="selectedSubResult?.tradeRows?.length"
          :data="selectedSubResult.tradeRows"
          stripe size="small" max-height="300" style="width: 100%;"
        >
          <ElTableColumn prop="open_time" label="开仓时间" width="160" sortable>
            <template #default="{ row }">{{ formatTime(row.open_time) }}</template>
          </ElTableColumn>
          <ElTableColumn :label="selectedSubResult.signalCol || '信号'" width="80" sortable>
            <template #default="{ row }">{{ row[selectedSubResult.signalCol || 'signal'] }}</template>
          </ElTableColumn>
          <ElTableColumn prop="open" label="开" width="100" sortable />
          <ElTableColumn prop="high" label="高" width="100" sortable />
          <ElTableColumn prop="low" label="低" width="100" sortable />
          <ElTableColumn prop="close" label="收" width="100" sortable />
          <ElTableColumn prop="__timeSell" label="平仓时间" width="160" sortable>
            <template #default="{ row }">{{ formatTime(row.__timeSell) }}</template>
          </ElTableColumn>
          <ElTableColumn prop="__priceBuy" label="买入价" width="100" sortable />
          <ElTableColumn prop="__priceSell" label="卖出价" width="100" sortable />
          <ElTableColumn prop="__income" label="收益率" width="100" sortable>
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
          <!-- 版本与参数快照（已保存结果） -->
          <ElCollapse v-if="savedInfo" style="margin-bottom: 12px;">
            <ElCollapseItem title="版本 & 参数快照" name="snapshot">
              <div v-if="savedInfo.strategyVersion" style="margin-bottom: 8px;">
                <span style="font-weight: 600; font-size: 13px;">策略版本：</span>
                <ElTag size="small" type="primary">{{ savedInfo.strategyVersion }}</ElTag>
              </div>
              <template v-if="Object.keys(savedInfo.strategyParams).length">
                <div style="font-weight: 600; font-size: 13px; margin-bottom: 4px;">策略参数：</div>
                <ElDescriptions :column="3" border size="small" style="margin-bottom: 8px;">
                  <ElDescriptionsItem v-for="(v, k) in savedInfo.strategyParams" :key="k" :label="String(k)">
                    {{ typeof v === 'boolean' ? String(v) : v }}
                  </ElDescriptionsItem>
                </ElDescriptions>
              </template>
              <template v-if="savedInfo.factorSnapshots.length">
                <div style="font-weight: 600; font-size: 13px; margin-bottom: 4px;">因子快照：</div>
                <div v-for="fs in savedInfo.factorSnapshots" :key="fs.uuid" style="margin-bottom: 8px;">
                  <span style="font-size: 13px;">{{ fs.name }}</span>
                  <ElTag size="small" type="info" effect="plain" style="margin-left: 6px;">v{{ fs.version }}</ElTag>
                  <ElDescriptions v-if="fs.params && fs.params.length" :column="3" border size="small" style="margin-top: 4px;">
                    <ElDescriptionsItem v-for="p in fs.params" :key="p.name" :label="p.name">
                      {{ typeof p.v === 'boolean' ? String(p.v) : p.v }}
                    </ElDescriptionsItem>
                  </ElDescriptions>
                </div>
              </template>
            </ElCollapseItem>
          </ElCollapse>
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
                :signal-col="singleSignalCol"
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
                <ElTableColumn prop="open_time" label="开仓时间" width="160" sortable>
                  <template #default="{ row }">
                    {{ formatTime(row.open_time) }}
                  </template>
                </ElTableColumn>
                <ElTableColumn :label="singleSignalCol" width="80" sortable>
                  <template #default="{ row }">
                    {{ row[singleSignalCol] }}
                  </template>
                </ElTableColumn>
                <ElTableColumn prop="open" label="开" width="100" sortable />
                <ElTableColumn prop="high" label="高" width="100" sortable />
                <ElTableColumn prop="low" label="低" width="100" sortable />
                <ElTableColumn prop="close" label="收" width="100" sortable />
                <ElTableColumn prop="__timeSell" label="平仓时间" width="160" sortable>
                  <template #default="{ row }">
                    {{ formatTime(row.__timeSell) }}
                  </template>
                </ElTableColumn>
                <ElTableColumn prop="__priceBuy" label="买入价" width="100" sortable />
                <ElTableColumn prop="__priceSell" label="卖出价" width="100" sortable />
                <ElTableColumn prop="__income" label="收益率" width="100" sortable>
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
    </div>
  </div>
</template>

<style scoped>
.result-page {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 16px;
  box-sizing: border-box;
  overflow: hidden;
}
.result-header {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}
.result-header h3 { margin: 0; }
.result-header__name { color: var(--text-secondary); font-size: 14px; }
.result-body {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
  padding-right: 4px;
}
.time-info {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 12px;
  line-height: 1.6;
}
.error-trace {
  margin: 0;
  font-family: 'Courier New', monospace;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>