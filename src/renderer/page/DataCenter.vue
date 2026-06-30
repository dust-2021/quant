<script lang="ts" setup>
import { ref, computed, onBeforeMount } from 'vue'
import { ElCard, ElTable, ElTableColumn, ElTag, ElButton, ElMessage, ElScrollbar, ElEmpty, ElDialog, ElForm, ElFormItem, ElInput, ElMessageBox } from 'element-plus'
import { Monaco } from 'vue-shiki-monaco'
import { getExchanges, getScripts, setExchangeConfig, saveScript, deleteScript, executeScript } from '../../api/dataCenter'
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
            </div>
          </ElCard>
        </div>
        <ElEmpty v-else description="暂无交易所数据" />
      </ElScrollbar>
    </div>

    <!-- 下半部分：脚本 -->
    <div class="section script-section">
      <div class="section-header">
        <h3>脚本列表</h3>
        <span class="section-header__count">共 {{ scripts.length }} 个脚本</span>
        <ElButton type="primary" size="small" @click="openCreateDialog">新增脚本</ElButton>
      </div>
      <ElScrollbar v-loading="scriptLoading">
        <ElTable
          v-if="scripts.length > 0"
          :data="scripts"
          stripe
          style="width: 100%; height: 100%;"
        >
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
    </div>

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