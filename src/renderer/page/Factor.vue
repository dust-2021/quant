<script lang="ts" setup>
import { ElButton, ElCol, ElFormItem, ElIcon, ElInput, ElMessage, ElMessageBox, ElOption, ElRow, ElScrollbar, ElSelect, ElTabPane, ElTabs, MessageBoxInputData } from 'element-plus';
import { ref, computed, onBeforeMount, watch } from 'vue';
import { useRouter } from 'vue-router';
import {Monaco} from 'vue-shiki-monaco';
import {Factor, ParamType, ThemeStore } from '../../store';
import {getFactorDetail, updateFactor, deleteFactor, getFactorGroup} from '../../api/factor';
import ParamBand from '../element/ParamBand.vue';
import ParamEditor from '../element/ParamEditor.vue';

const router = useRouter();

const props = defineProps({
    uuid: {
        type: String,
        default: '',
    }
})

const factor = ref<Factor>({
    uuid: '',
    name: 'unamed',
    params: [],
    version: '0.0.0',
    description: '',
    group: 'default',
    content: `
"""
因子文件示例
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

const show = ref<string>("code");

const themeStore = ThemeStore();
const monacoTheme = computed(() => themeStore.isDark ? 'github-dark' : 'github-light');
const monacoRef = ref<{ getValue: () => string } | null>(null);

// 分组下拉选项
const groupOptions = ref<{ id: string; name: string; description: string }[]>([]);

async function fetchGroupOptions() {
    groupOptions.value = await getFactorGroup();
}

// 正在编辑的参数（null=新建，非null=编辑已有）
const editingParam = ref<{ name: string; type: ParamType; v: string | number | boolean; enum: string[] } | null>(null);
const editingIndex = ref<number>(-1);

// 校验重名时排除自身
const existingNames = computed(() => {
    if (!factor.value || !factor.value.params) return [];
    const names = factor.value.params.map(p => p.name);
    if (editingIndex.value >= 0) {
        return names.filter((_, i) => i !== editingIndex.value);
    }
    return names;
});

async function save() {
    if (!factor.value) return;
    // 同步编辑器内容
    if (monacoRef.value) {
        factor.value.content = monacoRef.value.getValue();
    }
    const resp = await updateFactor(factor.value);
    if (resp.code === 0) {
        ElMessage.success('因子已保存');
    } else {
        ElMessage.error('保存失败: ' + resp.msg);
    }
}

async function saveAsNewVersion() {
    if (!factor.value) return;
    try {
        const { value: newVersion } = await ElMessageBox.prompt('请输入新版本号', '保存为新版本', {
            confirmButtonText: '确定',
            cancelButtonText: '取消',
            inputValue: factor.value.version,
            inputPattern: /^\d+\.\d+\.\d+$/,
            inputErrorMessage: '版本号格式不正确，请使用 x.y.z 格式',
        });
        if (!newVersion) return;
        // 同步编辑器内容
        if (monacoRef.value) {
            factor.value.content = monacoRef.value.getValue();
        }
        const saveData = { ...factor.value, uuid: '', version: newVersion };
        const resp = await updateFactor(saveData);
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
    if (!factor.value || !factor.value.uuid) return;
    try {
        await ElMessageBox.confirm(
            `确定要删除因子「${factor.value.name}」版本 ${factor.value.version} 吗？此操作不可撤销。`,
            '确认删除',
            {
                confirmButtonText: '删除',
                cancelButtonText: '取消',
                type: 'warning',
            }
        );
        const resp = await deleteFactor(factor.value.uuid);
        if (resp.code === 0) {
            ElMessage.success('因子已删除');
            router.push({ name: 'FactorView' });
        } else {
            ElMessage.error('删除失败: ' + resp.msg);
        }
    } catch {
        // 用户取消
    }
}

async function deleteParam(name: string) {
    if (!factor.value || !factor.value.params) return;
    if (editingParam.value && editingParam.value.name === name) {
        editingParam.value = null;
        editingIndex.value = -1;
    }
    factor.value.params = factor.value.params.filter(param => param.name !== name);
}

function editParam(name: string) {
    if (!factor.value || !factor.value.params || !Array.isArray(factor.value.params)) return;
    const idx = factor.value.params.findIndex(p => p.name === name);
    if (idx === -1) return;
    editingIndex.value = idx;
    editingParam.value = { ...factor.value.params[idx], enum: [...(factor.value.params[idx].enum || [])] };
    show.value = 'edit';
}

function onSaveParam(data: { name: string; type: ParamType; v: string | number | boolean; enum: string[] }) {
    if (!factor.value) return;
    if (editingIndex.value === -1) {
        factor.value.params.push({ ...data });
    } else {
        factor.value.params[editingIndex.value] = { ...data };
    }
    editingParam.value = null;
    editingIndex.value = -1;
    ElMessage.success('参数已保存');
}

function onCancelEdit() {
    editingParam.value = null;
    editingIndex.value = -1;
}

function onDeleteParam(name: string) {
    deleteParam(name);
    editingParam.value = null;
    editingIndex.value = -1;
}

async function addParam() {
    if (!factor.value) return;
    editingIndex.value = -1;
    editingParam.value = null;
    show.value = 'edit';
}

async function loadFactor() {
    if (!props.uuid) {
        return;
    }
    const data = await getFactorDetail(props.uuid);
    if (!data) {
        ElMessage.error('因子不存在');
        return;
    }
    factor.value = data;
    factor.value.uuid = props.uuid;
}

onBeforeMount(async () => {
    fetchGroupOptions();
    await loadFactor();
});

watch(() => props.uuid, async (newUuid) => {
    if (newUuid) {
        await loadFactor();
    }
});

</script>

<template>
    <div style="width: 100%; height: 100%;padding-top: 10px;box-sizing: border-box;">
        <ElRow :gutter="24" style="height: calc(100% - 10px);margin: 0;">
            <ElCol :span="6">
                <div style="height: 100%; width: 100%;">
                    <div style="height: calc(100% - 60px);background-color: var(--bg-card);border-radius: 5px; padding: 10px;box-sizing: border-box;margin-bottom: 10px;">
                        <div style="height: 30px;width: 100%;"><ElButton style="border: none;" @click="addParam">添加参数</ElButton></div>
                        <div style="height: calc(100% - 30px); display: flex; flex-wrap: wrap; gap: 6px; padding: 4px 0; align-content: flex-start; overflow-y: auto; overflow-x: hidden; box-sizing: border-box;">
                            <ParamBand :name="item.name" :type="item.type" :v="item.v" :change-type="true" :on-delete="deleteParam" :on-click="editParam" v-for="item in factor?.params" />
                        </div>
                    </div>
                    <div style="height: 60px; padding-top: 5px;box-sizing: border-box;">
                        <ElButton type="primary" @click="save" plain>保存</ElButton>
                        <ElButton v-if="factor.uuid" type="success" @click="saveAsNewVersion" plain>保存为新版本</ElButton>
                    </div>
                </div>
            </ElCol>
            <ElCol :span="18">
                <ElTabs style="height: 100%" type="card" v-model="show">
                    <ElTabPane label="信息" name="info" style="height: 100%;">
                        <ElForm :model="factor" label-width="100px" max-width="80%">
                            <ElFormItem label="因子名称">
                                <ElInput v-model="factor.name" style="width: 240px;" :disabled="uuid !== ''"/>
                            </ElFormItem>
                            <ElFormItem label="版本">
                                <ElInput v-model="factor.version" style="width: 240px;" :disabled="uuid !== ''"/>
                            </ElFormItem>
                            <ElFormItem label="分组">
                                <ElSelect v-model="factor.group" style="width: 240px;" placeholder="请选择分组">
                                    <ElOption v-for="g in groupOptions" :key="g.id" :label="g.name" :value="g.name"/>
                                </ElSelect>
                            </ElFormItem>
                            <ElFormItem label="描述">
                                <ElInput v-model="factor.description" type="textarea" :auto-size="{minRows: 2, maxRows: 4}" style="width: 400px;"/>
                            </ElFormItem>
                            <ElFormItem v-if="factor.uuid" label=" ">
                                <ElButton type="danger" plain @click="handleDelete">删除因子</ElButton>
                            </ElFormItem>
                        </ElForm>
                    </ElTabPane>
                    <ElTabPane label="代码" name="code" style="height: 100%;">
                        <Monaco ref="monacoRef" current-language="python" :value="factor.content" :file-name="`${factor.name}.py`"
                        style="height: calc(100% - 10px);border: 0;box-shadow: none;border-radius: 0;background-color: var(--bg-card);"
                        :current-theme="monacoTheme" height="90%">
                        </Monaco>
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
    </div>
</template>
