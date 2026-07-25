<script lang="ts" setup>
import { ref, computed, watch } from 'vue'
import {
  ElDialog, ElForm, ElFormItem, ElDatePicker, ElSelect, ElOption,
  ElCheckbox, ElButton, ElTag, ElInput, ElMessage
} from 'element-plus'
import { getRunnerList } from '../../api/strategy'
import { getExchanges, getTargets } from '../../api/dataCenter'
import { ParamType } from '../../store'
import type { binanceInterval, tradeType } from '../../exchanges/binance'

const props = defineProps<{
  show: boolean
  strategyName: string
  strategyParams: any[]
  factorInfos: any[]
}>()

const emit = defineEmits<{
  'update:show': [val: boolean]
  run: [payload: Record<string, any>]
}>()

// ===== 表单数据 =====
const start_time = ref('')
const end_time = ref('')
const targets = ref<string[]>([])
const targetInput = ref('')
const period = ref(3600)
const runner_name = ref('default')
const multiEnabled = ref(false)
const runExchange = ref('')

const runnerList = ref<string[]>([])
const exchanges = ref<{ id: number; name: string }[]>([])
const targetOptions = ref<string[]>([])
const targetLoading = ref(false)

const periodOptions = [
  { label: '秒', value: 1 }, { label: '分钟', value: 60 },
  { label: '小时', value: 3600 }, { label: '日', value: 86400 },
]

// ===== 多参数 =====
interface MultiParamRow {
  paramKey: string
  valueInput: string
  values: (string | number | boolean)[]
  expression: string
  useExpression: boolean
}
const multiParamRows = ref<MultiParamRow[]>([])

interface ParamOption { key: string; label: string }
const allParamOptions = computed(() => {
  const options: ParamOption[] = []
  if (props.strategyParams) {
    for (const p of props.strategyParams) {
      options.push({ key: `_strategy.${p.name}`, label: `${p.name} (策略)` })
    }
  }
  if (props.factorInfos) {
    for (const fi of props.factorInfos) {
      if (fi.params) {
        for (const p of fi.params) {
          options.push({ key: `_factor.${fi.uuid}.${p.name}`, label: `${p.name} (因子:${fi.name})` })
        }
      }
    }
  }
  return options
})

const cartesianCount = computed(() => {
  let count = 1; let hasExpr = false
  for (const row of multiParamRows.value) {
    if (row.useExpression && row.expression.trim()) { hasExpr = true; continue }
    if (row.values.length > 0) count *= row.values.length
  }
  return { count, hasExpr }
})
const cartesianExceeded = computed(() => cartesianCount.value.count > 1000)

function addMultiParamRow() {
  multiParamRows.value.push({ paramKey: '', valueInput: '', values: [], expression: '', useExpression: false })
}
function removeMultiParamRow(idx: number) { multiParamRows.value.splice(idx, 1) }

function addMultiValue(row: MultiParamRow) {
  const raw = row.valueInput.trim()
  if (!raw || !row.paramKey) return
  const parts = row.paramKey.split('.')
  const pureName = parts.length >= 2 ? parts.slice(-1)[0] : row.paramKey
  let pType: ParamType | undefined
  for (const p of props.strategyParams || []) {
    if (p.name === pureName) { pType = p.type; break }
  }
  if (!pType && props.factorInfos) {
    for (const fi of props.factorInfos) {
      for (const p of (fi.params || [])) {
        if (p.name === pureName) { pType = p.type; break }
      }
    }
  }
  const val = convertMultiValue(raw, pType)
  if (!row.values.includes(val)) row.values.push(val)
  row.valueInput = ''
}

function convertMultiValue(raw: string, type?: ParamType): string | number | boolean {
  if (!type) return raw
  switch (type) {
    case ParamType.Number: return Number(raw)
    case ParamType.Boolean: return raw.toLowerCase() === 'true' || raw === '1'
    default: return raw
  }
}
function removeMultiValue(row: MultiParamRow, idx: number) { row.values.splice(idx, 1) }

// ===== 交易所 & 标的 =====
async function loadExchanges() {
  exchanges.value = await getExchanges()
  runExchange.value = exchanges.value[0]?.name || ''
}

async function searchTargets(keyword: string) {
  if (!runExchange.value) { targetOptions.value = []; return }
  targetLoading.value = true
  try {
    targetOptions.value = await getTargets(runExchange.value, keyword)
  } finally { targetLoading.value = false }
}

function addTarget() {
  const val = targetInput.value.trim().toUpperCase()
  if (!val) return
  if (!targets.value.includes(val)) targets.value.push(val)
  targetInput.value = ''
}
function removeTarget(idx: number) { targets.value.splice(idx, 1) }

// ===== 生命周期 =====
watch(() => props.show, async (val) => {
  if (val) {
    resetForm()
    if (exchanges.value.length === 0) await loadExchanges()
    if (runnerList.value.length === 0) runnerList.value = await getRunnerList()
  }
})

function handleCancel() { emit('update:show', false) }

function handleConfirm() {
  if (!start_time.value || !end_time.value) {
    ElMessage.warning('请选择起止时间')
    return
  }
  const s = Math.floor(new Date(start_time.value).getTime())
  const e = Math.floor(new Date(end_time.value).getTime())
  if (s >= e) { ElMessage.warning('起始时间必须早于结束时间'); return }

  if (multiEnabled.value && cartesianExceeded.value) {
    ElMessage.error(`参数组合数 ${cartesianCount.value.count} 超过上限 1000`)
    return
  }

  const payload: Record<string, any> = {
    start_time: s, end_time: e, period: period.value, runner_name: runner_name.value, exchange: runExchange.value
  }
  if (targets.value.length > 0) payload.target = targets.value
  if (multiEnabled.value && multiParamRows.value.length > 0) {
    const mp: Record<string, (string | number | boolean)[]> = {}
    const me: Record<string, string> = {}
    for (const row of multiParamRows.value) {
      if (!row.paramKey) continue
      if (row.useExpression && row.expression.trim()) {
        me[row.paramKey] = row.expression.trim()
      } else if (row.values.length > 0) {
        mp[row.paramKey] = [...row.values]
      }
    }
    if (Object.keys(mp).length > 0) payload.multi_params = mp
    if (Object.keys(me).length > 0) payload.multi_expressions = me
  }

  // 收集多参数键
  payload.allKeys = [
    ...Object.keys(payload.multi_params || {}),
    ...Object.keys(payload.multi_expressions || {}),
  ]

  emit('run', payload)
}

function resetForm() {
  start_time.value = ''
  end_time.value = ''
  targets.value = []
  targetInput.value = ''
  period.value = 3600
  runner_name.value = 'default'
  multiEnabled.value = false
  multiParamRows.value = []
}
</script>

<template>
  <ElDialog :model-value="show" @update:model-value="emit('update:show', $event)"
    title="运行设置" width="560px" :close-on-click-modal="false" @open="resetForm"
  >
    <ElForm label-width="80px">
      <ElFormItem label="起始时间" required>
        <ElDatePicker v-model="start_time" type="datetime" placeholder="选择起始时间"
          format="YYYY-MM-DD HH:mm:ss" value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%;" />
      </ElFormItem>
      <ElFormItem label="结束时间" required>
        <ElDatePicker v-model="end_time" type="datetime" placeholder="选择结束时间"
          format="YYYY-MM-DD HH:mm:ss" value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%;" />
      </ElFormItem>
      <ElFormItem label="交易所">
        <ElSelect v-model="runExchange" placeholder="选择交易所" style="width: 100%;" @change="targets = []">
          <ElOption v-for="ex in exchanges" :key="ex.id" :label="ex.name" :value="ex.name" />
        </ElSelect>
      </ElFormItem>
      <ElFormItem label="标的代码">
        <div style="display: flex; flex-wrap: wrap; gap: 4px; align-items: center;">
          <ElTag v-for="(t, idx) in targets" :key="t" closable size="small" type="info" @close="removeTarget(idx)">{{ t }}</ElTag>
          <ElSelect v-model="targetInput" placeholder="搜索标的" size="small" style="width: 200px;"
            filterable remote allow-create :remote-method="searchTargets" :loading="targetLoading"
            @change="(val: string) => { if (val) { addTarget(); targetInput = '' } }"
          >
            <ElOption v-for="c in targetOptions" :key="c" :label="c" :value="c" />
          </ElSelect>
        </div>
      </ElFormItem>
      <ElFormItem label="周期">
        <ElSelect v-model="period" style="width: 100%;">
          <ElOption v-for="p in periodOptions" :key="p.value" :label="p.label" :value="p.value" />
        </ElSelect>
      </ElFormItem>
      <ElFormItem label="执行器">
        <ElSelect v-model="runner_name" style="width: 100%;">
          <ElOption v-for="r in runnerList" :key="r" :label="r" :value="r" />
        </ElSelect>
      </ElFormItem>
      <ElFormItem label="并行回测">
        <ElCheckbox v-model="multiEnabled">启用多参数并行回测</ElCheckbox>
        <span v-if="multiEnabled && multiParamRows.length > 0" style="margin-left: 8px; font-size: 12px;">
          组合数: <b :style="{ color: cartesianExceeded ? '#f56c6c' : '#67c23a' }">{{ cartesianCount.count }}</b>
          <span v-if="cartesianCount.hasExpr" style="color: #e6a23c;"> (含表达式)</span>
          <span v-if="cartesianExceeded" style="color: #f56c6c;"> (超过上限 1000)</span>
        </span>
      </ElFormItem>
      <template v-if="multiEnabled">
        <div style="max-height: 260px; overflow-y: auto; padding-right: 4px;">
          <div v-for="(row, idx) in multiParamRows" :key="idx" style="margin-bottom: 8px; padding: 8px; background: rgba(255,255,255,0.03); border-radius: 6px;">
            <ElFormItem :label="`参数 ${idx + 1}`" style="margin-bottom: 4px;">
              <div style="display: flex; gap: 8px; align-items: center; width: 100%; flex-wrap: wrap;">
                <ElSelect v-model="row.paramKey" placeholder="选择参数" style="width: 220px;" filterable>
                  <ElOption v-for="opt in allParamOptions" :key="opt.key" :label="opt.label" :value="opt.key" />
                </ElSelect>
                <ElButton size="small" :type="row.useExpression ? 'warning' : ''" @click="row.useExpression = !row.useExpression">
                  {{ row.useExpression ? '手动输入' : '表达式' }}
                </ElButton>
                <ElButton type="danger" size="small" circle @click="removeMultiParamRow(idx)">✕</ElButton>
              </div>
            </ElFormItem>
            <div v-if="row.useExpression && row.paramKey" style="margin-left: 80px;">
              <ElInput v-model="row.expression" placeholder="输入 Python 列表推导式，如: [i/10 for i in range(1,21)]" size="small" style="width: 100%; max-width: 500px;" />
              <div style="font-size: 11px; color: #909399; margin-top: 2px;">支持 range, len, int, float, abs, min, max, round, sum</div>
            </div>
            <div v-if="!row.useExpression && row.paramKey" style="display: flex; flex-wrap: wrap; gap: 4px; align-items: center; margin-left: 80px;">
              <ElTag v-for="(v, vIdx) in row.values" :key="vIdx" closable size="small" type="warning" @close="removeMultiValue(row, vIdx)">{{ v }}</ElTag>
              <ElInput v-model="row.valueInput" placeholder="输入后回车添加" size="small" style="width: 140px;" @keyup.enter="addMultiValue(row)" />
            </div>
          </div>
        </div>
        <ElFormItem>
          <ElButton size="small" @click="addMultiParamRow">+ 添加参数</ElButton>
        </ElFormItem>
      </template>
    </ElForm>
    <template #footer>
      <ElButton @click="handleCancel">取消</ElButton>
      <ElButton type="primary" @click="handleConfirm">运行</ElButton>
    </template>
  </ElDialog>
</template>
