<script lang="ts" setup>
import { ElButton, ElCheckbox, ElCol, ElFormItem, ElInput, ElMessage, ElMessageBox, ElOption, ElRow, ElScrollbar, ElSelect, ElTabPane, ElTabs, ElDialog, ElCollapse, ElCollapseItem, ElTag, ElTooltip, MessageBoxInputData } from 'element-plus';
import { ref, computed, onBeforeMount, watch } from 'vue';
import { useRouter } from 'vue-router';
import {Monaco} from 'vue-shiki-monaco';
import {Strategy, Factor, ParamType, ThemeStore } from '../../store';
import {getStrategyDetail, getStrategyGroup, updateStrategy, deleteStrategy, executeStrategy, getRunnerList} from '../../api/strategy';
import {getFactorList, getFactorGroup} from '../../api/factor';
import ParamBand from '../element/ParamBand.vue';
import ParamEditor from '../element/ParamEditor.vue';
import CustomIcon from '../element/CustomIcon.vue';
import { StrategyResultStore } from '../../store';

const router = useRouter();

const props = defineProps({
    uuid: {
        type: String,
        default: '',
    }
})

const strategy = ref<Strategy>({
    uuid: '',
    name: 'unamed',
    params: [
        // 杠杆参数
        {name: 'leverage', type: ParamType.Number, v: 1, enum: []},
        {name: 'premium', type: ParamType.Number, v: 0.001, enum: []},
        {name: 'signalName', type: ParamType.String, v: 'signal', enum: []}
    ],
    version: '0.0.0',
    factors: [],
    description: '',
    group: 'default',
    content: `
"""
策略文件示例
"""
import pandas as pd
import numpy as np

import typing as t

# 参数
params: t.Dict[str, t.Any] = {}

# 执行上下文
context: t.Dict[str, t.Any] = {}

def run(data: pd.DataFrame):
    return data
`
});

// 因子显示信息映射：uuid → {name, version, description}
const factorMap = ref<Record<string, { name: string; version: string; description: string }>>({});

const show = ref<string>("code");

const themeStore = ThemeStore();
const monacoTheme = computed(() => themeStore.isDark ? 'github-dark' : 'github-light');
const monacoRef = ref<{ getValue: () => string } | null>(null);

// 分组下拉选项
const groupOptions = ref<{ id: string; name: string; description: string }[]>([]);

async function fetchGroupOptions() {
    groupOptions.value = await getStrategyGroup();
}

// 正在编辑的参数（null=新建，非null=编辑已有）
const editingParam = ref<{ name: string; type: ParamType; v: string | number | boolean; enum: string[] } | null>(null);
// 编辑时对应在 param 数组中的索引，-1 为新建
const editingIndex = ref<number>(-1);

// 校验重名时排除自身
const existingNames = computed(() => {
    if (!strategy.value || !strategy.value.params) return [];
    const names = strategy.value.params.map(p => p.name);
    if (editingIndex.value >= 0) {
        return names.filter((_, i) => i !== editingIndex.value);
    }
    return names;
});

async function save() {
    if (!strategy.value) return;
    // 同步编辑器内容
    if (monacoRef.value) {
        strategy.value.content = monacoRef.value.getValue();
    }
    const resp = await updateStrategy(strategy.value);
    if (resp.code === 0) {
        // 新建策略：后端返回 uuid，更新并跳转到编辑页面
        if (!strategy.value.uuid && resp.data && typeof resp.data === 'string') {
            strategy.value.uuid = resp.data
            router.replace({ name: 'Strategy', params: { uuid: resp.data } })
        }
        ElMessage.success('策略已保存');
    } else {
        ElMessage.error('保存失败: ' + resp.msg);
    }
}

async function saveAsNewVersion() {
    if (!strategy.value) return;
    try {
        const { value: newVersion } = await ElMessageBox.prompt('请输入新版本号', '保存为新版本', {
            confirmButtonText: '确定',
            cancelButtonText: '取消',
            inputValue: strategy.value.version,
            inputPattern: /.*/,
            inputErrorMessage: '版本号格式不正确',
        });
        if (!newVersion) return;
        // 同步编辑器内容
        if (monacoRef.value) {
            strategy.value.content = monacoRef.value.getValue();
        }
        // 清空 uuid，使后端作为新记录创建
        const saveData = { ...strategy.value, uuid: '', version: newVersion };
        const resp = await updateStrategy(saveData);
        if (resp.code === 0) {
            ElMessage.success('新版本已保存');
        } else {
            ElMessage.error('保存失败: ' + resp.msg);
        }
    } catch {
        // 用户取消提示框
    }
}

async function handleDelete() {
    if (!strategy.value || !strategy.value.uuid) return;
    try {
        await ElMessageBox.confirm(
            `确定要删除策略「${strategy.value.name}」版本 ${strategy.value.version} 吗？此操作不可撤销。`,
            '确认删除',
            {
                confirmButtonText: '删除',
                cancelButtonText: '取消',
                type: 'warning',
            }
        );
        const resp = await deleteStrategy(strategy.value.uuid);
        if (resp.code === 0) {
            ElMessage.success('策略已删除');
            router.push({ name: 'StrategyView' });
        } else {
            ElMessage.error('删除失败: ' + resp.msg);
        }
    } catch {
        // 用户取消
    }
}

async function run() {
    if (!strategy.value?.uuid) {
        ElMessage.warning('请先保存策略后再运行');
        return;
    }
    // 同步编辑器内容
    if (monacoRef.value) {
        strategy.value.content = monacoRef.value.getValue();
    }
    showRunDialog.value = true;
    runForm.value.start_time = '';
    runForm.value.end_time = '';
    runForm.value.targets = [];
    runForm.value.period = 3600;
    runForm.value.runner_name = 'default';
    runForm.value.multiEnabled = false;
    runForm.value.targetInput = '';
    multiParamRows.value = [];
    // 加载执行器列表
    runnerList.value = await getRunnerList();
}

// ========= 运行设置弹窗 =========
const showRunDialog = ref(false);
const runnerList = ref<string[]>([]);

interface RunForm {
    start_time: string;
    end_time: string;
    targets: string[];
    period: number;
    runner_name: string;
    multiEnabled: boolean;
    targetInput: string;
}

interface MultiParamRow {
    paramKey: string;     // 带前缀: "_strategy.{param}" 或 "_factor.{uuid}.{param}"
    valueInput: string;
    values: (string | number | boolean)[];
    expression: string;   // Python 列表推导式，非空时优先于 values
    useExpression: boolean;
}

const runForm = ref<RunForm>({
    start_time: '',
    end_time: '',
    targets: [],
    period: 3600,
    runner_name: 'default',
    multiEnabled: false,
    targetInput: '',
});

const multiParamRows = ref<MultiParamRow[]>([]);

const periodOptions = [
    { label: '秒', value: 1 },
    { label: '分钟', value: 60 },
    { label: '小时', value: 3600 },
    { label: '日', value: 86400 },
];

function addTarget() {
    const val = runForm.value.targetInput.trim();
    if (!val) return;
    if (!runForm.value.targets.includes(val)) {
        runForm.value.targets.push(val);
    }
    runForm.value.targetInput = '';
}

function removeTarget(idx: number) {
    runForm.value.targets.splice(idx, 1);
}

// ===== 多参数并行 =====
// 收集所有可选参数（带前缀键，避免重名）
interface ParamOption { key: string; label: string }
const allParamOptions = computed(() => {
  const options: ParamOption[] = []
  if (strategy.value?.params) {
    for (const p of strategy.value.params) {
      options.push({ key: `_strategy.${p.name}`, label: `${p.name} (策略)` })
    }
  }
  if ((strategy.value as any)?.factor_infos) {
    for (const fi of (strategy.value as any).factor_infos) {
      if (fi.params) {
        for (const p of fi.params) {
          options.push({ key: `_factor.${fi.uuid}.${p.name}`, label: `${p.name} (因子:${fi.name})` })
        }
      }
    }
  }
  return options
})

// 笛卡尔积数量（表达式不计入客户端计算，由服务端校验）
const cartesianCount = computed(() => {
  let count = 1
  let hasExpr = false
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

function removeMultiParamRow(idx: number) {
  multiParamRows.value.splice(idx, 1)
}

function addMultiValue(row: MultiParamRow) {
  const raw = row.valueInput.trim()
  if (!raw || !row.paramKey) return
  // 查找参数类型（去掉前缀后匹配）
  const parts = row.paramKey.split('.')
  const pureName = parts.length >= 2 ? parts.slice(-1)[0] : row.paramKey
  let pType: ParamType | undefined
  for (const p of strategy.value?.params || []) {
    if (p.name === pureName) { pType = p.type; break }
  }
  if (!pType && (strategy.value as any)?.factor_infos) {
    for (const fi of (strategy.value as any).factor_infos) {
      for (const p of (fi.params || [])) {
        if (p.name === pureName) { pType = p.type; break }
      }
    }
  }
  const val = convertMultiValue(raw, pType)
  if (!row.values.includes(val)) {
    row.values.push(val)
  }
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

function removeMultiValue(row: MultiParamRow, vIdx: number) {
  row.values.splice(vIdx, 1)
}

async function confirmRun() {
    if (!runForm.value.start_time || !runForm.value.end_time) {
        ElMessage.warning('请选择起止时间');
        return;
    }
    const startTime = Math.floor(new Date(runForm.value.start_time).getTime());
    const endTime = Math.floor(new Date(runForm.value.end_time).getTime());
    if (startTime >= endTime) {
        ElMessage.warning('起始时间必须早于结束时间');
        return;
    }
    if (!strategy.value) return;

    // 校验多参数
    if (runForm.value.multiEnabled && cartesianExceeded.value) {
        ElMessage.error(`参数组合数 ${cartesianCount.value.count} 超过上限 1000，请减少参数或取值`);
        return;
    }

    const payload: {
        uuid: string;
        start_time: number;
        end_time: number;
        target?: string[];
        period?: number;
        runner_name?: string;
        multi_params?: Record<string, (string | number | boolean)[]>;
        multi_expressions?: Record<string, string>;
    } = {
        uuid: strategy.value.uuid,
        start_time: startTime,
        end_time: endTime,
        period: runForm.value.period,
        runner_name: runForm.value.runner_name,
    };
    if (runForm.value.targets.length > 0) {
        payload.target = runForm.value.targets;
    }
    if (runForm.value.multiEnabled && multiParamRows.value.length > 0) {
        const mp: Record<string, (string | number | boolean)[]> = {};
        const me: Record<string, string> = {};
        for (const row of multiParamRows.value) {
            if (!row.paramKey) continue;
            if (row.useExpression && row.expression.trim()) {
                me[row.paramKey] = row.expression.trim();
            } else if (row.values.length > 0) {
                mp[row.paramKey] = [...row.values];
            }
        }
        if (Object.keys(mp).length > 0) payload.multi_params = mp;
        if (Object.keys(me).length > 0) payload.multi_expressions = me;
    }

    const resp = await executeStrategy(payload);
    if (resp.code === 0) {
        const taskStore = StrategyResultStore();
        const resultIds = resp.data;
        if (!resultIds) return;
        // 收集所有多参数键名（含表达式键）
        const allKeys = [
            ...Object.keys(payload.multi_params || {}),
            ...Object.keys(payload.multi_expressions || {}),
        ];
        taskStore.addTasks(resultIds, strategy.value?.name || '', runForm.value.runner_name, allKeys);

        ElMessage.success('策略已提交运行');
        showRunDialog.value = false;
    } else {
        ElMessage.error('运行失败: ' + (resp.msg || '未知错误'));
    }
}

async function deleteParam(name: string) {
    if (!strategy.value || !strategy.value.params) return;
    // 如果正在编辑该参数，重置编辑状态
    if (editingParam.value && editingParam.value.name === name) {
        editingParam.value = null;
        editingIndex.value = -1;
    }
    strategy.value.params = strategy.value.params.filter(param => param.name !== name);
}

// 点击参数卡片 → 打开编辑 Tab
function editParam(name: string) {
    if (!strategy.value || !strategy.value.params || !Array.isArray(strategy.value.params)) return;
    const idx = strategy.value.params.findIndex(p => p.name === name);
    if (idx === -1) return;
    editingIndex.value = idx;
    editingParam.value = { ...strategy.value.params[idx], enum: [...(strategy.value.params[idx].enum || [])] };
    show.value = 'edit';
}

// ParamEditor 保存回调
function onSaveParam(data: { name: string; type: ParamType; v: string | number | boolean; enum: string[] }) {
    if (!strategy.value) return;
    if (editingIndex.value === -1) {
        // 新建
        strategy.value.params.push({ ...data });
    } else {
        // 编辑已有
        strategy.value.params[editingIndex.value] = { ...data };
    }
    editingParam.value = null;
    editingIndex.value = -1;
    ElMessage.success('参数已保存');
}

// ParamEditor 取消回调
function onCancelEdit() {
    editingParam.value = null;
    editingIndex.value = -1;
}

// ParamEditor 删除回调
function onDeleteParam(name: string) {
    deleteParam(name);
    editingParam.value = null;
    editingIndex.value = -1;
}

async function addParam() {
    if (!strategy.value) return;
    editingIndex.value = -1;
    editingParam.value = null;  // null 表示新建模式
    show.value = 'edit';
}

// ========= 因子筛选弹窗 =========
interface FactorItem {
    group_name: string;
    factor_name: string;
    uuid: string;
    version: string;
    description: string;
}

const showFactorDialog = ref(false);
const factorSearchKeyword = ref('');
const allFactors = ref<FactorItem[]>([]);
const factorGroups = ref<{ id: string; name: string; description: string }[]>([]);

const filteredFactors = computed(() => {
    const keyword = factorSearchKeyword.value.trim().toLowerCase();
    if (!keyword) return allFactors.value;
    return allFactors.value.filter(f =>
        f.factor_name.toLowerCase().includes(keyword) ||
        f.description.toLowerCase().includes(keyword)
    );
});

// 按因子分组聚合筛选后的结果
const filteredFactorGroups = computed(() => {
    const map = new Map<string, FactorItem[]>();
    for (const f of filteredFactors.value) {
        const groupName = f.group_name || '未分组';
        const items = map.get(groupName) || [];
        items.push(f);
        map.set(groupName, items);
    }
    // 按 factorGroups 的顺序排序
    const result: { groupName: string; items: FactorItem[] }[] = [];
    for (const g of factorGroups.value) {
        const items = map.get(g.name);
        if (items && items.length > 0) {
            result.push({ groupName: g.name, items });
            map.delete(g.name);
        }
    }
    // 剩余未在分组列表中的
    for (const [groupName, items] of map) {
        result.push({ groupName, items });
    }
    return result;
});

async function openFactorDialog() {
    showFactorDialog.value = true;
    factorSearchKeyword.value = '';
    const [list, groups] = await Promise.all([
        getFactorList(),
        getFactorGroup(),
    ]);
    allFactors.value = list || [];
    factorGroups.value = groups;
}

function addFactorToStrategy(factor: FactorItem) {
    if (!strategy.value) return;
    // 检查是否已添加（按 uuid 去重）
    if (strategy.value.factors.includes(factor.uuid)) {
        ElMessage.warning('该因子已添加');
        return;
    }
    strategy.value.factors.push(factor.uuid);
    factorMap.value[factor.uuid] = { name: factor.factor_name, version: factor.version, description: factor.description || '' };
    ElMessage.success(`因子「${factor.factor_name}」已添加`);
}

function removeFactorFromStrategy(uuid: string) {
    if (!strategy.value) return;
    strategy.value.factors = strategy.value.factors.filter(id => id !== uuid);
    delete factorMap.value[uuid];
}

function goToFactor(uuid: string) {
    router.push({ name: 'Factor', params: { uuid } });
}

// ========= 因子拖拽排序 =========
const dragFactorIndex = ref<number>(-1);

function onFactorDragStart(index: number, event: DragEvent) {
    dragFactorIndex.value = index;
    if (event.dataTransfer) {
        event.dataTransfer.effectAllowed = 'move';
        event.dataTransfer.setData('text/plain', String(index));
    }
    (event.target as HTMLElement)?.classList.add('dragging');
}

function onFactorDragOver(index: number, event: DragEvent) {
    event.preventDefault();
    if (event.dataTransfer) {
        event.dataTransfer.dropEffect = 'move';
    }
}

function onFactorDrop(index: number, event: DragEvent) {
    event.preventDefault();
    if (!strategy.value || dragFactorIndex.value < 0) return;
    const from = dragFactorIndex.value;
    const to = index;
    if (from === to) return;
    const items = [...strategy.value.factors];
    const [moved] = items.splice(from, 1);
    items.splice(to, 0, moved);
    strategy.value.factors = items;
}

function onFactorDragEnd(event: DragEvent) {
    dragFactorIndex.value = -1;
    (event.target as HTMLElement)?.classList.remove('dragging');
}

async function loadStrategy() {
    if (!props.uuid) {
        return;
    }
    const data = await getStrategyDetail(props.uuid);
    if (!data) {
        ElMessage.error('策略不存在');
        return;
    }
    strategy.value = data;
    strategy.value.uuid = props.uuid;
    // 从 factor_infos 填充因子显示映射
    const infos: Record<string, { name: string; version: string; description: string }> = {};
    if ((data as any).factor_infos) {
        for (const fi of (data as any).factor_infos) {
            infos[fi.uuid] = { name: fi.name, version: fi.version, description: fi.description || '' };
        }
    }
    factorMap.value = infos;
}

onBeforeMount(async () => {
    fetchGroupOptions();
    await loadStrategy();
});

// 版本切换时（同一组件复用）重新加载策略数据
watch(() => props.uuid, async (newUuid) => {
    if (newUuid) {
        await loadStrategy();
    }
});

</script>

<template>              
    <div style="width: 100%; height: 100%;padding-top: 10px;box-sizing: border-box;">
        <ElRow :gutter="24" style="height: 100%;margin: 0;">
            <ElCol :span="6">
                <div style="height: 100%; width: 100%;"> 
                    <div style="height: calc(60% - 70px);background-color: var(--bg-card);border-radius: 5px; padding: 10px;box-sizing: border-box;margin-bottom: 10px;">
                        <div style="height: 30px;width: 100%;"><ElButton style="border: none;" @click="addParam">添加参数</ElButton></div>
                        <div style="height: calc(100% - 30px); display: flex; flex-wrap: wrap; gap: 6px; padding: 4px 0; align-content: flex-start; overflow-y: auto; overflow-x: hidden; box-sizing: border-box;">
                            <ParamBand :key="item.name" :name="item.name" :type="item.type" :v="item.v" :change-type="true" :on-delete="deleteParam" :on-click="editParam" v-for="item in strategy?.params" />
                        </div>
                    </div>
                    <div style="height: 40%;background-color: var(--bg-card);border-radius: 5px; padding: 10px;box-sizing: border-box;">
                        <div style="height: 30px;width: 100%;"><ElButton style="border: none;" @click="openFactorDialog">添加因子</ElButton></div>
                        <ElScrollbar>
                            <div
                                v-for="(uuid, idx) in strategy.factors"
                                :key="uuid"
                                class="factor-tag-row"
                                :class="{ 'drag-over': dragFactorIndex >= 0 && dragFactorIndex !== idx }"
                                draggable="true"
                                @dragstart="onFactorDragStart(idx, $event)"
                                @dragover="onFactorDragOver(idx, $event)"
                                @drop="onFactorDrop(idx, $event)"
                                @dragend="onFactorDragEnd"
                            >
                                <span class="drag-handle">⠿</span>
                                <ElTooltip :content="factorMap[uuid]?.description || ''" :disabled="!factorMap[uuid]?.description" placement="top" :show-after="300">
                                    <ElTag closable size="small" type="success" effect="plain" @close="removeFactorFromStrategy(uuid)" @click.stop="goToFactor(uuid)" style="cursor: pointer;">
                                        {{ factorMap[uuid]?.name || uuid }} <span class="factor-tag-version">{{ factorMap[uuid]?.version || '' }}</span>
                                    </ElTag>
                                </ElTooltip>
                            </div>
                        </ElScrollbar>
                    </div>
                    <div style="height: 60px; padding-top: 5px;box-sizing: border-box;">
                        <ElButton type="primary" @click="save" plain>保存</ElButton>
                        <ElButton v-if="strategy.uuid" type="success" @click="saveAsNewVersion" plain>保存为新版本</ElButton>
                        <ElButton type="primary" @click="run" plain>运行</ElButton>
                    </div>
                </div>   
            </ElCol> 
            <ElCol :span="18">
                <ElTabs style="height: 100%" type="card" v-model="show">
                    <ElTabPane name="info" style="height: 100%;">
                        <template #label>
                            <CustomIcon name="info"></CustomIcon>
                        </template>
                        <ElForm :model="strategy" label-width="100px" max-width="80%">
                            <ElFormItem label="策略名称">
                                <ElInput v-model="strategy.name" style="width: 240px;" :disabled="uuid !== ''"/>
                            </ElFormItem>
                            <ElFormItem label="版本">
                                <ElInput v-model="strategy.version" style="width: 240px;" :disabled="uuid !== ''"/>
                            </ElFormItem>
                            <ElFormItem label="分组">
                                <ElSelect v-model="strategy.group" style="width: 240px;" placeholder="请选择分组">
                                    <ElOption v-for="g in groupOptions" :key="g.id" :label="g.name" :value="g.name"/>
                                </ElSelect>
                            </ElFormItem>
                            <ElFormItem label="描述">
                                <ElInput v-model="strategy.description" type="textarea" :auto-size="{minRows: 2, maxRows: 4}" style="width: 400px;"/>
                            </ElFormItem>
                            <ElFormItem v-if="strategy.uuid" label=" ">
                                <ElButton type="danger" plain @click="handleDelete">删除策略</ElButton>
                            </ElFormItem>
                        </ElForm>
                    </ElTabPane>
                    <ElTabPane name="code" style="height: 100%;">
                        <template #label>
                            <CustomIcon name="code"></CustomIcon>
                        </template>
                        <Monaco ref="monacoRef" current-language="python" :value="strategy.content" :file-name="`${strategy.name}.py`" 
                        style="height: calc(100% - 10px);border: 0;box-shadow: none;border-radius: 0;background-color: var(--bg-card);"
                        :current-theme="monacoTheme" height="90%">
                        </Monaco>
                    </ElTabPane>
                    <ElTabPane name="chart" style="height: 100%;">
                        <template #label>
                            <CustomIcon name="chart"></CustomIcon>
                        </template>
                    </ElTabPane>
                    <ElTabPane label="编辑" name="edit" style="height: 100%;" v-if="show === 'edit'">
                        <ParamEditor
                            :param="editingParam"
                            :existing-names="existingNames"
                            @save="onSaveParam"
                            @cancel="onCancelEdit"
                            @delete="onDeleteParam"
                        />
                    </ElTabPane>
                </ElTabs>
            </ElCol>
        </ElRow>

        <!-- 因子筛选弹窗 -->
        <ElDialog v-model="showFactorDialog" title="选择因子" width="560px" :close-on-click-modal="false">
            <ElInput
                v-model="factorSearchKeyword"
                placeholder="输入关键字搜索因子名称或描述"
                clearable
                style="margin-bottom: 16px;"
            />
            <ElScrollbar max-height="400px">
                <div v-if="filteredFactorGroups.length === 0" style="text-align: center; padding: 40px 0; color: var(--text-secondary);">
                    暂无因子
                </div>
                <ElCollapse v-else>
                    <ElCollapseItem
                        v-for="grp in filteredFactorGroups"
                        :key="grp.groupName"
                        :name="grp.groupName"
                    >
                        <template #title>
                            <span class="factor-group-title">{{ grp.groupName }}</span>
                            <ElTag size="small" type="info" effect="plain" style="margin-left: 8px;">{{ grp.items.length }}</ElTag>
                        </template>
                        <div
                            v-for="item in grp.items"
                            :key="item.uuid"
                            class="factor-select-item"
                            @click="addFactorToStrategy(item)"
                        >
                            <div class="factor-select-item__header">
                                <span class="factor-select-item__name">{{ item.factor_name }}</span>
                                <ElTag size="small" type="info" effect="plain">v{{ item.version }}</ElTag>
                            </div>
                            <div class="factor-select-item__desc" v-if="item.description">{{ item.description }}</div>
                        </div>
                    </ElCollapseItem>
                </ElCollapse>
            </ElScrollbar>
            <template #footer>
                <ElButton @click="showFactorDialog = false">关闭</ElButton>
            </template>
        </ElDialog>

        <!-- 运行设置弹窗 -->
        <ElDialog v-model="showRunDialog" title="运行设置" width="560px" :close-on-click-modal="false">
            <ElForm label-width="80px">
                <ElFormItem label="起始时间" required>
                    <ElDatePicker
                        v-model="runForm.start_time"
                        type="datetime"
                        placeholder="选择起始时间"
                        format="YYYY-MM-DD HH:mm:ss"
                        value-format="YYYY-MM-DD HH:mm:ss"
                        style="width: 100%;"
                    />
                </ElFormItem>
                <ElFormItem label="结束时间" required>
                    <ElDatePicker
                        v-model="runForm.end_time"
                        type="datetime"
                        placeholder="选择结束时间"
                        format="YYYY-MM-DD HH:mm:ss"
                        value-format="YYYY-MM-DD HH:mm:ss"
                        style="width: 100%;"
                    />
                </ElFormItem>
                <ElFormItem label="标的代码">
                    <div style="display: flex; flex-wrap: wrap; gap: 4px; align-items: center;">
                        <ElTag
                            v-for="(t, idx) in runForm.targets"
                            :key="t"
                            closable
                            size="small"
                            type="info"
                            @close="removeTarget(idx)"
                        >{{ t }}</ElTag>
                        <ElInput
                            v-model="runForm.targetInput"
                            placeholder="输入后回车添加"
                            size="small"
                            style="width: 160px;"
                            @keyup.enter="addTarget"
                        />
                    </div>
                </ElFormItem>
                <ElFormItem label="周期">
                    <ElSelect v-model="runForm.period" style="width: 100%;">
                        <ElOption v-for="p in periodOptions" :key="p.value" :label="p.label" :value="p.value"/>
                    </ElSelect>
                </ElFormItem>
                <ElFormItem label="执行器">
                    <ElSelect v-model="runForm.runner_name" style="width: 100%;">
                        <ElOption v-for="r in runnerList" :key="r" :label="r" :value="r"/>
                    </ElSelect>
                </ElFormItem>
                <ElFormItem label="并行回测">
                    <ElCheckbox v-model="runForm.multiEnabled">启用多参数并行回测</ElCheckbox>
                    <span v-if="runForm.multiEnabled && multiParamRows.length > 0" style="margin-left: 8px; font-size: 12px;">
                        组合数: <b :style="{ color: cartesianExceeded ? '#f56c6c' : '#67c23a' }">{{ cartesianCount.count }}</b>
                        <span v-if="cartesianCount.hasExpr" style="color: #e6a23c;"> (含表达式)</span>
                        <span v-if="cartesianExceeded" style="color: #f56c6c;"> (超过上限 1000)</span>
                    </span>
                </ElFormItem>
                <template v-if="runForm.multiEnabled">
                    <div v-for="(row, idx) in multiParamRows" :key="idx" style="margin-bottom: 8px; padding: 8px; background: rgba(255,255,255,0.03); border-radius: 6px;">
                        <ElFormItem :label="`参数 ${idx + 1}`" style="margin-bottom: 4px;">
                            <div style="display: flex; gap: 8px; align-items: center; width: 100%; flex-wrap: wrap;">
                                <ElSelect v-model="row.paramKey" placeholder="选择参数" style="width: 220px;" filterable>
                                    <ElOption v-for="opt in allParamOptions" :key="opt.key" :label="opt.label" :value="opt.key"/>
                                </ElSelect>
                                <ElButton size="small" :type="row.useExpression ? 'warning' : ''" @click="row.useExpression = !row.useExpression">
                                    {{ row.useExpression ? '手动输入' : '表达式' }}
                                </ElButton>
                                <ElButton type="danger" size="small" circle @click="removeMultiParamRow(idx)">✕</ElButton>
                            </div>
                        </ElFormItem>
                        <!-- 表达式模式 -->
                        <div v-if="row.useExpression && row.paramKey" style="margin-left: 80px;">
                            <ElInput v-model="row.expression" placeholder="输入 Python 列表推导式，如: [i/10 for i in range(1,21)]" size="small" style="width: 100%; max-width: 500px;" />
                            <div style="font-size: 11px; color: #909399; margin-top: 2px;">支持 range, len, int, float, abs, min, max, round, sum</div>
                        </div>
                        <!-- 手动输入模式 -->
                        <div v-if="!row.useExpression && row.paramKey" style="display: flex; flex-wrap: wrap; gap: 4px; align-items: center; margin-left: 80px;">
                            <ElTag
                                v-for="(v, vIdx) in row.values"
                                :key="vIdx"
                                closable size="small" type="warning"
                                @close="removeMultiValue(row, vIdx)"
                            >{{ v }}</ElTag>
                            <ElInput
                                v-model="row.valueInput"
                                placeholder="输入后回车添加"
                                size="small"
                                style="width: 140px;"
                                @keyup.enter="addMultiValue(row)"
                            />
                        </div>
                    </div>
                    <ElFormItem>
                        <ElButton size="small" @click="addMultiParamRow">+ 添加参数</ElButton>
                    </ElFormItem>
                </template>
            </ElForm>
            <template #footer>
                <ElButton @click="showRunDialog = false">取消</ElButton>
                <ElButton type="primary" @click="confirmRun">运行</ElButton>
            </template>
        </ElDialog>
    </div>
</template>

<style scoped>
.factor-tag-row {
    display: inline-flex;
    align-items: center;
    margin: 2px 4px;
    cursor: grab;
    user-select: none;
    transition: opacity 0.15s;
    border-radius: 4px;
    padding: 2px 4px;
}
.factor-tag-row:active {
    cursor: grabbing;
}
.factor-tag-row.dragging {
    opacity: 0.4;
}
.factor-tag-row.drag-over {
    background-color: var(--el-color-primary-light-9, #ecf5ff);
    border-radius: 4px;
}

.drag-handle {
    display: inline-flex;
    align-items: center;
    margin-right: 2px;
    font-size: 14px;
    color: var(--text-placeholder, #c0c4cc);
    cursor: grab;
    line-height: 1;
}

.factor-tag-version {
    opacity: 0.7;
    font-size: 11px;
}

.factor-group-title {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
}

.factor-select-item {
    padding: 10px 12px;
    border-radius: 6px;
    cursor: pointer;
    transition: background-color 0.15s;
    margin-bottom: 2px;
}
.factor-select-item:hover {
    background-color: var(--bg-tag-hover, #ecf5ff);
}

.factor-select-item__header {
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.factor-select-item__name {
    font-size: 14px;
    font-weight: 500;
    color: var(--text-primary);
}

.factor-select-item__desc {
    margin-top: 4px;
    font-size: 12px;
    color: var(--text-regular);
    line-height: 1.5;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
</style>