<script lang="ts" setup>
import { ref, computed, onBeforeMount } from 'vue'
import { ElCard, ElTable, ElTableColumn, ElTag, ElButton, ElMessage, ElScrollbar, ElEmpty, ElDialog, ElForm, ElFormItem, ElInput, ElMessageBox, ElTabs, ElTabPane, ElSelect, ElOption, ElResult, ElDatePicker, ElDescriptions, ElDescriptionsItem } from 'element-plus'
import { Monaco } from 'vue-shiki-monaco'
import { getExchanges, getScripts, setExchangeConfig, saveScript, deleteScript, executeScript, getTargets, checkDataTable, checkDataIntegrity, createExchange, deleteExchange } from '../../api/dataCenter'
import { getSetting } from '../../api/setting'
import { ThemeStore } from '../../store'
import type { ExchangeItem, ScriptItem } from '../../api/dataCenter'

const themeStore = ThemeStore()
const monacoTheme = computed(() => themeStore.isDark ? 'github-dark' : 'github-light')

// ===== 交易所 =====
const exchanges = ref<ExchangeItem[]>([])
const currentExchange = ref<string>('')
const exchangeLoading = ref(false)

async function refreshExchanges() {
  exchangeLoading.value = true
  try {
    exchanges.value = await getExchanges()
    currentExchange.value = (await getSetting<string>('Exchange')) || ''
  } finally {
    exchangeLoading.value = false
  }
}

async function handleSelectExchange(exchange: ExchangeItem) {
  const success = await setExchangeConfig(exchange.name)
  if (success) {
    currentExchange.value = exchange.name
  }
}

// ===== 交易所新增/删除 =====
const showExchangeDialog = ref(false)
const newExchangeName = ref('')
const exchangeSaving = ref(false)

async function handleCreateExchange() {
  const name = newExchangeName.value.trim()
  if (!name) {
    ElMessage.warning('请输入交易所名称')
    return
  }
  exchangeSaving.value = true
  try {
    const ok = await createExchange(name)
    if (ok) {
      showExchangeDialog.value = false
      newExchangeName.value = ''
      await refreshExchanges()
    }
  } finally {
    exchangeSaving.value = false
  }
}

async function handleDeleteExchange(exchange: ExchangeItem) {
  try {
    await ElMessageBox.confirm(
      `确定要删除交易所「${exchange.name}」吗？该交易所下的所有标的也将被删除。此操作不可恢复。`,
      '删除交易所',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }
  const ok = await deleteExchange(exchange.name)
  if (ok) {
    if (currentExchange.value === exchange.name) {
      currentExchange.value = ''
    }
    await refreshExchanges()
  }
}

// ===== 脚本 =====
const scripts = ref<ScriptItem[]>([])
const scriptLoading = ref(false)

async function refreshScripts() {
  scriptLoading.value = true
  try {
    scripts.value = await getScripts()
  } finally {
    scriptLoading.value = false
  }
}

// ===== 脚本编辑弹窗 =====
const showScriptDialog = ref(false)
const editingScriptName = ref('')
const editingScriptContent = ref('')
const scriptMonacoRef = ref<{ getValue: () => string } | null>(null)
const isNewScript = ref(true)
const saving = ref(false)

const defaultScriptContent = `"""
数据脚本示例
"""
import pandas as pd
import numpy as np

import typing as t

def run():
    """入口函数，必须定义"""
    pass
`

function openCreateDialog() {
  isNewScript.value = true
  editingScriptName.value = ''
  editingScriptContent.value = defaultScriptContent
  showScriptDialog.value = true
}

function openEditDialog(script: ScriptItem) {
  isNewScript.value = false
  editingScriptName.value = script.name
  editingScriptContent.value = script.content
  showScriptDialog.value = true
}

async function handleSaveScript() {
  const name = editingScriptName.value.trim()
  if (!name) {
    ElMessage.warning('请输入脚本名称')
    return
  }
  if (scriptMonacoRef.value) {
    editingScriptContent.value = scriptMonacoRef.value.getValue()
  }
  saving.value = true
  try {
    const ok = await saveScript(name, editingScriptContent.value)
    if (ok) {
      showScriptDialog.value = false
      await refreshScripts()
    }
  } finally {
    saving.value = false
  }
}

async function handleDeleteScript(script: ScriptItem) {
  try {
    await ElMessageBox.confirm(
      `确定要删除脚本「${script.name}」吗？此操作不可恢复。`,
      '删除脚本',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }
  const ok = await deleteScript(script.name)
  if (ok) {
    await refreshScripts()
  }
}

// ===== 执行脚本 =====
const executing = ref<string | null>(null)
const showResultDialog = ref(false)
const executeResult = ref<any>(null)
const executeResultName = ref('')
const executeError = ref<string | null>(null)

async function handleExecuteScript(script: ScriptItem) {
  executing.value = script.name
  try {
    const { data, error } = await executeScript(script.name)
    executeResult.value = data
    executeError.value = error
    executeResultName.value = script.name
    showResultDialog.value = true
  } finally {
    executing.value = null
  }
}

// ===== 数据检查 =====
const checkTab = ref('scripts')
const checkExchange = ref('')
const checkCode = ref('')
const checkPeriod = ref(3600)
const checkTargets = ref<string[]>([])
const checkTargetsLoading = ref(false)
const checkResult = ref<{ table: string; exists: boolean } | null>(null)
const checkLoading = ref(false)

// 完整性检查
const integrityStart = ref('')
const integrityEnd = ref('')
const integrityResult = ref<any>(null)
const integrityLoading = ref(false)

const periodOptions = [
  { label: '秒', value: 1 },
  { label: '分钟', value: 60 },
  { label: '小时', value: 3600 },
  { label: '天', value: 86400 },
]

async function onCheckExchangeChange(val: string) {
  checkCode.value = ''
  checkResult.value = null
}

async function searchTargets(keyword: string) {
  if (!checkExchange.value) { checkTargets.value = []; return }
  checkTargetsLoading.value = true
  try {
    checkTargets.value = await getTargets(checkExchange.value, keyword)
  } finally {
    checkTargetsLoading.value = false
  }
}

async function doCheckTable() {
  if (!checkExchange.value || !checkCode.value) {
    ElMessage.warning('请选择交易所和标的')
    return
  }
  checkLoading.value = true
  checkResult.value = null
  integrityResult.value = null
  try {
    const result = await checkDataTable(checkExchange.value, checkCode.value, checkPeriod.value)
    if (result === null) {
      ElMessage.error('检查失败，数据中心未连接或接口异常')
    } else {
      checkResult.value = result
    }
  } finally {
    checkLoading.value = false
  }
}

async function doCheckIntegrity() {
  if (!integrityStart.value || !integrityEnd.value) {
    ElMessage.warning('请选择起止时间')
    return
  }
  const start = Math.floor(new Date(integrityStart.value).getTime())
  const end = Math.floor(new Date(integrityEnd.value).getTime())
  if (start >= end) {
    ElMessage.warning('起始时间必须早于结束时间')
    return
  }
  integrityLoading.value = true
  integrityResult.value = null
  try {
    const result = await checkDataIntegrity(checkExchange.value, checkCode.value, checkPeriod.value, start, end)
    if (result === null) {
      ElMessage.error('完整性检查失败')
    } else {
      integrityResult.value = result
    }
  } finally {
    integrityLoading.value = false
  }
}

onBeforeMount(async () => {
  await Promise.all([refreshExchanges(), refreshScripts()])
})
</script>

<template>
  <div class="data-center-page">
    <!-- 上半部分：交易所 -->
    <div class="section exchange-section">
      <div class="section-header">
        <h3>交易所</h3>
        <ElTag v-if="currentExchange" type="success" effect="dark">
          当前: {{ currentExchange }}
        </ElTag>
        <ElTag v-else type="info">未配置交易所</ElTag>
        <ElButton type="primary" size="small" style="margin-left: auto;" @click="showExchangeDialog = true">新增交易所</ElButton>
      </div>
      <ElScrollbar v-loading="exchangeLoading">
        <div class="exchange-grid" v-if="exchanges.length > 0">
          <ElCard
            v-for="item in exchanges"
            :key="item.id"
            class="exchange-card"
            :class="{ active: currentExchange === item.name }"
            shadow="hover"
            @click="handleSelectExchange(item)"
          >
            <div class="exchange-card__content">
              <span class="exchange-card__name">{{ item.name }}</span>
              <div class="exchange-card__actions">
                <ElTag
                  v-if="currentExchange === item.name"
                  type="success"
                  size="small"
                  effect="plain"
                >
                  已选择
                </ElTag>
                <ElTag v-else type="info" size="small" effect="plain">
                  点击切换
                </ElTag>
                <ElButton
                  type="danger"
                  size="small"
                  link
                  @click.stop="handleDeleteExchange(item)"
                >
                  删除
                </ElButton>
              </div>
            </div>
          </ElCard>
        </div>
        <ElEmpty v-else description="暂无交易所数据" />
      </ElScrollbar>
    </div>

    <!-- 下半部分：Tabs -->
    <div class="section script-section">
      <ElTabs v-model="checkTab" type="card" style="height: 100%; display: flex; flex-direction: column;">
        <!-- 脚本 Tab -->
        <ElTabPane label="脚本列表" name="scripts">
          <div class="section-header">
            <span class="section-header__count">共 {{ scripts.length }} 个脚本</span>
            <ElButton type="primary" size="small" @click="openCreateDialog">新增脚本</ElButton>
          </div>
          <ElScrollbar v-loading="scriptLoading">
            <ElTable v-if="scripts.length > 0" :data="scripts" stripe style="width: 100%; height: 100%;">
              <ElTableColumn prop="id" label="ID" width="80" align="center" />
              <ElTableColumn prop="name" label="脚本名称" min-width="180" />
              <ElTableColumn prop="content" label="脚本内容" min-width="300">
                <template #default="{ row }">
                  <div class="script-content" :title="row.content">{{ row.content }}</div>
                </template>
              </ElTableColumn>
              <ElTableColumn label="操作" width="200" align="center" fixed="right">
                <template #default="{ row }">
                  <ElButton size="small" type="primary" link @click="openEditDialog(row)">编辑</ElButton>
                  <ElButton size="small" type="success" link @click="handleExecuteScript(row)" :loading="executing === row.name">执行</ElButton>
                  <ElButton size="small" type="danger" link @click="handleDeleteScript(row)">删除</ElButton>
                </template>
              </ElTableColumn>
            </ElTable>
            <ElEmpty v-else description="暂无脚本数据" />
          </ElScrollbar>
        </ElTabPane>

        <!-- 数据检查 Tab -->
        <ElTabPane label="数据检查" name="check">
          <div class="check-form">
            <span class="check-label">交易所：</span>
            <ElSelect v-model="checkExchange" placeholder="选择交易所" size="small" style="width: 140px;" @change="onCheckExchangeChange">
              <ElOption v-for="ex in exchanges" :key="ex.id" :label="ex.name" :value="ex.name" />
            </ElSelect>
            <span class="check-label">标的：</span>
            <ElSelect v-model="checkCode" placeholder="输入关键字搜索" size="small" style="width: 200px;"
              filterable remote :remote-method="searchTargets" :loading="checkTargetsLoading"
              @change="checkResult = null" @focus="searchTargets('')">
              <ElOption v-for="c in checkTargets" :key="c" :label="c" :value="c" />
            </ElSelect>
            <span class="check-label">周期：</span>
            <ElSelect v-model="checkPeriod" size="small" style="width: 100px;" @change="checkResult = null">
              <ElOption v-for="p in periodOptions" :key="p.value" :label="p.label" :value="p.value" />
            </ElSelect>
            <ElButton type="primary" size="small" @click="doCheckTable" :loading="checkLoading">检查</ElButton>
          </div>
          <div v-if="checkResult" class="check-result">
            <ElResult :type="checkResult.exists ? 'success' : 'warning'"
              :title="checkResult.exists ? '数据表存在' : '数据表不存在'"
              :sub-title="`表名：${checkResult.table}`" />
            <!-- 完整性检查 -->
            <template v-if="checkResult.exists">
              <h4 style="margin: 16px 0 8px;">数据完整性检查</h4>
              <div class="check-form">
                <ElDatePicker v-model="integrityStart" type="datetime" placeholder="起始时间"
                  format="YYYY-MM-DD HH:mm:ss" value-format="YYYY-MM-DD HH:mm:ss" size="small" style="width: 180px;" />
                <span>~</span>
                <ElDatePicker v-model="integrityEnd" type="datetime" placeholder="结束时间"
                  format="YYYY-MM-DD HH:mm:ss" value-format="YYYY-MM-DD HH:mm:ss" size="small" style="width: 180px;" />
                <ElButton type="primary" size="small" @click="doCheckIntegrity" :loading="integrityLoading">检查完整性</ElButton>
              </div>
              <div v-if="integrityResult" style="margin-top: 12px;">
                <ElDescriptions :column="2" border size="small">
                  <ElDescriptionsItem label="实际条数">{{ integrityResult.count }}</ElDescriptionsItem>
                  <ElDescriptionsItem label="应有条数">{{ integrityResult.expected }}</ElDescriptionsItem>
                  <ElDescriptionsItem label="查询范围起">{{ integrityResult.query_start ? new Date(integrityResult.query_start).toLocaleString() : '-' }}</ElDescriptionsItem>
                  <ElDescriptionsItem label="查询范围止">{{ integrityResult.query_end ? new Date(integrityResult.query_end).toLocaleString() : '-' }}</ElDescriptionsItem>
                  <ElDescriptionsItem label="数据起始">{{ integrityResult.min_time ? new Date(integrityResult.min_time).toLocaleString() : '-' }}</ElDescriptionsItem>
                  <ElDescriptionsItem label="数据结束">{{ integrityResult.max_time ? new Date(integrityResult.max_time).toLocaleString() : '-' }}</ElDescriptionsItem>
                </ElDescriptions>
                <ElResult style="margin-top: 8px;"
                  :type="integrityResult.complete ? 'success' : 'warning'"
                  :title="integrityResult.complete ? '数据完整' : '数据不完整'"
                  :sub-title="integrityResult.complete ? '' : `缺失约 ${integrityResult.expected - integrityResult.count} 条数据`" />
              </div>
            </template>
          </div>
          <ElEmpty v-if="!checkResult" description="选择交易所、标的和周期后点击检查" />
        </ElTabPane>
      </ElTabs>
    </div>

    <!-- 交易所新增弹窗 -->
    <ElDialog
      v-model="showExchangeDialog"
      title="新增交易所"
      width="420px"
      :close-on-click-modal="false"
    >
      <ElForm label-width="80px">
        <ElFormItem label="交易所名称" required>
          <ElInput v-model="newExchangeName" placeholder="请输入交易所名称，如 Binance" style="width: 100%;" />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="showExchangeDialog = false">取消</ElButton>
        <ElButton type="primary" @click="handleCreateExchange" :loading="exchangeSaving">创建</ElButton>
      </template>
    </ElDialog>

    <!-- 脚本编辑弹窗 -->
    <ElDialog
      v-model="showScriptDialog"
      :title="isNewScript ? '新增脚本' : `编辑脚本 - ${editingScriptName}`"
      width="800px"
      :close-on-click-modal="false"
      draggable
    >
      <div class="dialog-body">
        <ElForm label-width="80px" v-if="isNewScript">
          <ElFormItem label="脚本名称" required>
            <ElInput v-model="editingScriptName" placeholder="请输入脚本名称" style="width: 300px;" />
          </ElFormItem>
        </ElForm>
        <div class="editor-container">
          <Monaco
            ref="scriptMonacoRef"
            current-language="python"
            :value="editingScriptContent"
            :file-name="`${editingScriptName || 'script'}.py`"
            :current-theme="monacoTheme"
            height="100%"
            style="width: 100%; height: 100%;"
          />
        </div>
      </div>
      <template #footer>
        <span class="dialog-footer">
          <ElButton @click="showScriptDialog = false">取消</ElButton>
          <ElButton type="primary" @click="handleSaveScript" :loading="saving">保存</ElButton>
        </span>
      </template>
    </ElDialog>

    <!-- 执行结果弹窗 -->
    <ElDialog
      v-model="showResultDialog"
      :title="`执行结果 - ${executeResultName}`"
      width="700px"
      :close-on-click-modal="false"
    >
      <div v-if="executeError" class="result-error">{{ executeError }}</div>
      <pre v-else class="result-content">{{ JSON.stringify(executeResult, null, 2) }}</pre>
      <template #footer>
        <ElButton @click="showResultDialog = false">关闭</ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<style scoped>
.data-center-page {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 12px;
  box-sizing: border-box;
  background-color: var(--bg-page);
  overflow: hidden;
}

.section {
  display: flex;
  flex-direction: column;
  background-color: var(--bg-card);
  border-radius: 8px;
  padding: 12px;
  min-height: 0;
  overflow: hidden;
}

.exchange-section {
  flex: 0 0 auto;
  max-height: 35%;
}

.script-section {
  flex: 1;
  min-height: 0;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
  flex-shrink: 0;
}

.section-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.section-header__count {
  color: var(--text-secondary);
  font-size: 13px;
  flex: 1;
}

.exchange-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 2px 0;
}

.section :deep(.el-scrollbar) {
  flex: 1;
  min-height: 0;
}

.script-section :deep(.el-tabs) {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.script-section :deep(.el-tabs__header) {
  flex-shrink: 0;
}

.script-section :deep(.el-tabs__content) {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.script-section :deep(.el-tab-pane) {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.exchange-card {
  cursor: pointer;
  transition: border-color 0.3s, box-shadow 0.3s;
  min-width: 160px;
}

.exchange-card.active {
  border-color: var(--el-color-success);
  box-shadow: 0 0 0 1px var(--el-color-success);
}

.exchange-card__content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.exchange-card__actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.exchange-card__name {
  font-size: 15px;
  font-weight: 500;
}

.script-content {
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: 'Courier New', Courier, monospace;
  font-size: 13px;
  color: var(--text-secondary);
}

.dialog-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.editor-container {
  height: 420px;
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
  overflow: hidden;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.check-form {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  flex-wrap: wrap;
}

.check-label {
  font-size: 13px;
  color: var(--text-secondary);
}

.check-result {
  margin-top: 16px;
}

.result-content {
  background-color: var(--el-fill-color-light);
  border-radius: 4px;
  padding: 12px;
  max-height: 400px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: 'Courier New', Courier, monospace;
  font-size: 13px;
  margin: 0;
}

.result-error {
  background-color: var(--el-color-danger-light-9);
  border: 1px solid var(--el-color-danger-light-5);
  border-radius: 4px;
  padding: 12px 16px;
  color: var(--el-color-danger);
  font-size: 14px;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>