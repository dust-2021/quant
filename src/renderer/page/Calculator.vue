<script lang="ts" setup>
import { ref, computed, onBeforeMount } from 'vue'
import {
  ElTable, ElTableColumn, ElButton, ElDialog, ElForm, ElFormItem,
  ElInput, ElMessage, ElMessageBox, ElTag, ElEmpty, ElScrollbar
} from 'element-plus'
import { Monaco } from 'vue-shiki-monaco'
import { getCalculatorList, saveCalculator, deleteCalculator, CalculatorItem } from '../../api/calculator'
import { ThemeStore } from '../../store'

const themeStore = ThemeStore()
const monacoTheme = computed(() => themeStore.isDark ? 'github-dark' : 'github-light')

const calculators = ref<CalculatorItem[]>([])
const loading = ref(false)

// 编辑弹窗
const showDialog = ref(false)
const editingName = ref('')
const editingDescription = ref('')
const editingContent = ref('')
const monacoRef = ref<{ getValue: () => string } | null>(null)
const isNew = ref(true)
const saving = ref(false)

const defaultContent = `"""
自定义回测算子
需定义 run 函数，接收 df, ctx, params 参数
"""
import typing as t
import pandas as pd
import numpy as np


def run(df: pd.DataFrame, ctx: t.Dict[str, t.Any], params: t.Dict[str, t.Any]):
    """
    df: 行情数据 DataFrame
    ctx: 策略上下文
    params: 策略参数
    返回: 回测结果 dict
    """
    pass
`

async function refresh() {
  loading.value = true
  try {
    calculators.value = await getCalculatorList()
  } finally {
    loading.value = false
  }
}

function openCreate() {
  isNew.value = true
  editingName.value = ''
  editingDescription.value = ''
  editingContent.value = defaultContent
  showDialog.value = true
}

function openEdit(row: CalculatorItem) {
  if (row.name === 'default') {
    ElMessage.warning('default 算子不可修改')
    return
  }
  isNew.value = false
  editingName.value = row.name
  editingDescription.value = row.description
  editingContent.value = row.content
  showDialog.value = true
}

async function handleSave() {
  const name = editingName.value.trim()
  if (!name) {
    ElMessage.warning('请输入算子名称')
    return
  }
  if (monacoRef.value) {
    editingContent.value = monacoRef.value.getValue()
  }
  saving.value = true
  try {
    const ok = await saveCalculator(name, editingContent.value, editingDescription.value.trim())
    if (ok) {
      showDialog.value = false
      await refresh()
    }
  } finally {
    saving.value = false
  }
}

async function handleDelete(row: CalculatorItem) {
  if (row.name === 'default') {
    ElMessage.warning('default 算子不可删除')
    return
  }
  try {
    await ElMessageBox.confirm(`确定删除算子「${row.name}」？`, '删除算子', {
      type: 'warning', confirmButtonText: '确定', cancelButtonText: '取消',
    })
  } catch { return }
  await deleteCalculator(row.name)
  await refresh()
}

function formatTime(ts: number): string {
  return new Date(ts * 1000).toLocaleString()
}

onBeforeMount(() => refresh())
</script>

<template>
  <div class="calculator-page">
    <div class="page-header">
      <h3>回测算子</h3>
      <ElButton type="primary" size="small" @click="openCreate">新增算子</ElButton>
    </div>
    <ElScrollbar v-loading="loading">
      <ElTable v-if="calculators.length" :data="calculators" stripe style="width: 100%; height: 100%;">
        <ElTableColumn prop="id" label="ID" width="60" align="center" />
        <ElTableColumn prop="name" label="名称" width="140">
          <template #default="{ row }">
            <span :style="{ fontWeight: row.name === 'default' ? 600 : 400 }">{{ row.name }}</span>
            <ElTag v-if="row.name === 'default'" size="small" type="info" effect="plain" style="margin-left: 4px;">内置</ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn prop="description" label="描述" min-width="200" show-overflow-tooltip />
        <ElTableColumn prop="create_time" label="创建时间" width="160">
          <template #default="{ row }">{{ formatTime(row.create_time) }}</template>
        </ElTableColumn>
        <ElTableColumn prop="update_time" label="更新时间" width="160">
          <template #default="{ row }">{{ formatTime(row.update_time) }}</template>
        </ElTableColumn>
        <ElTableColumn label="操作" width="140" align="center" fixed="right">
          <template #default="{ row }">
            <ElButton size="small" type="primary" link @click="openEdit(row)">编辑</ElButton>
            <ElButton size="small" type="danger" link @click="handleDelete(row)"
              :disabled="row.name === 'default'">删除</ElButton>
          </template>
        </ElTableColumn>
      </ElTable>
      <ElEmpty v-if="!loading && !calculators.length" description="暂无算子" />
    </ElScrollbar>

    <!-- 编辑弹窗 -->
    <ElDialog v-model="showDialog" :title="isNew ? '新增算子' : `编辑 - ${editingName}`"
      width="800px" :close-on-click-modal="false" draggable>
      <ElForm label-width="80px" style="margin-bottom: 12px;">
        <ElFormItem label="名称" required>
          <ElInput v-model="editingName" placeholder="算子名称" :disabled="!isNew" style="width: 300px;" />
        </ElFormItem>
        <ElFormItem label="描述">
          <ElInput v-model="editingDescription" placeholder="算子描述" style="width: 400px;" />
        </ElFormItem>
      </ElForm>
      <div class="editor-container">
        <Monaco ref="monacoRef" current-language="python" :value="editingContent"
          :current-theme="monacoTheme"
          :file-name="`${editingName || 'calculator'}.py`" height="100%"
          style="width: 100%; height: 100%;" />
      </div>
      <template #footer>
        <ElButton @click="showDialog = false">取消</ElButton>
        <ElButton type="primary" @click="handleSave" :loading="saving">保存</ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<style scoped>
.calculator-page {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 16px;
  box-sizing: border-box;
  background-color: var(--bg-page);
}
.page-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  flex-shrink: 0;
}
.page-header h3 { margin: 0; font-size: 16px; font-weight: 600; }

.calculator-page :deep(.el-scrollbar) {
  flex: 1;
  min-height: 0;
}

.editor-container {
  height: 400px;
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
  overflow: hidden;
}
</style>