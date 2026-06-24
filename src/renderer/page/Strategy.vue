<script lang="ts" setup>
import { ElButton, ElCol, ElFormItem, ElInput, ElMessage, ElMessageBox, ElOption, ElRow, ElScrollbar, ElSelect, ElTabPane, ElTabs, ElDialog, ElCollapse, ElCollapseItem, ElTag, ElTooltip, MessageBoxInputData } from 'element-plus';
import { ref, computed, onBeforeMount, watch } from 'vue';
import { useRouter } from 'vue-router';
import {Monaco} from 'vue-shiki-monaco';
import {Strategy, Factor, ParamType, ThemeStore } from '../../store';
import {getStrategyDetail, getStrategyGroup, updateStrategy, deleteStrategy, executeStrategy, getRunnerList} from '../../api/strategy';
import {getFactorList, getFactorGroup} from '../../api/factor';
import ParamBand from '../element/ParamBand.vue';
import ParamEditor from '../element/ParamEditor.vue';
import CustomIcon from '../element/CustomIcon.vue';
import { info } from 'node:console';

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
    params: [],
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
    pass
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
            inputPattern: /^\d+\.\d+\.\d+$/,
            inputErrorMessage: '版本号格式不正确，请使用 x.y.z 格式',
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
    runForm.value.multi = false;
    runForm.value.multi_param = '';
    runForm.value.multi_values = [];
    runForm.value.targetInput = '';
    runForm.value.multiValueInput = '';
    runForm.value.multiExpressionInput = '';
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
    multi: boolean;
    multi_param: string;
    multi_values: string[];
    targetInput: string;
    multiValueInput: string;
    multiExpressionInput: string;
}

const runForm = ref<RunForm>({
    start_time: '',
    end_time: '',
    targets: [],
    period: 3600,
    runner_name: 'default',
    multi: false,
    multi_param: '',
    multi_values: [],
    targetInput: '',
    multiValueInput: '',
    multiExpressionInput: '',
});

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

function addMultiValue() {
    const val = runForm.value.multiValueInput.trim();
    if (!val) return;
    if (!runForm.value.multi_values.includes(val)) {
        runForm.value.multi_values.push(val);
    }
    runForm.value.multiValueInput = '';
}

function removeMultiValue(idx: number) {
    runForm.value.multi_values.splice(idx, 1);
}

async function confirmRun() {
    if (!runForm.value.start_time || !runForm.value.end_time) {
        ElMessage.warning('请选择起止时间');
        return;
    }
    const startTime = Math.floor(new Date(runForm.value.start_time).getTime() / 1000);
    const endTime = Math.floor(new Date(runForm.value.end_time).getTime() / 1000);
    if (startTime >= endTime) {
        ElMessage.warning('起始时间必须早于结束时间');
        return;
    }
    if (!strategy.value) return;

    const payload: {
        uuid: string;
        start_time: number;
        end_time: number;
        target?: string[];
        period?: number;
        runner_name?: string;
        multi?: boolean;
        multi_param?: string;
        multi_values?: string[];
        multi_expression?: string;
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
    if (runForm.value.multi) {
        payload.multi = true;
        payload.multi_param = runForm.value.multi_param;
        payload.multi_values = runForm.value.multi_values;
        if (runForm.value.multiExpressionInput.trim()) {
            payload.multi_expression = runForm.value.multiExpressionInput.trim();
        }
    }

    const resp = await executeStrategy(payload);
    if (resp.code === 0) {
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
                            <ParamBand :name="item.name" :type="item.type" :v="item.v" :change-type="true" :on-delete="deleteParam" :on-click="editParam" v-for="item in strategy?.params" />
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
                    <ElCheckbox v-model="runForm.multi">启用多参数并行回测</ElCheckbox>
                </ElFormItem>
                <template v-if="runForm.multi">
                    <ElFormItem label="并行参数">
                        <ElSelect v-model="runForm.multi_param" placeholder="选择要并行的参数" style="width: 100%;">
                            <ElOption v-for="p in strategy.params" :key="p.name" :label="p.name" :value="p.name"/>
                        </ElSelect>
                    </ElFormItem>
                    <ElFormItem label="参数值">
                        <div style="display: flex; flex-wrap: wrap; gap: 4px; align-items: center;">
                            <ElTag
                                v-for="(v, idx) in runForm.multi_values"
                                :key="v"
                                closable
                                size="small"
                                type="warning"
                                @close="removeMultiValue(idx)"
                            >{{ v }}</ElTag>
                            <ElInput
                                v-model="runForm.multiValueInput"
                                placeholder="输入后回车添加"
                                size="small"
                                style="width: 160px;"
                                @keyup.enter="addMultiValue"
                            />
                        </div>
                    </ElFormItem>
                    <ElFormItem label="列表推导式">
                        <ElInput
                            v-model="runForm.multiExpressionInput"
                            placeholder="如: [i/10 for i in range(1, 21)]"
                            style="width: 100%;"
                        />
                        <div style="font-size: 12px; color: #909399; margin-top: 4px;">
                            Python 列表推导式，优先级高于上方的参数值列表。支持 range, len, int, float, abs, min, max, round, sum
                        </div>
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