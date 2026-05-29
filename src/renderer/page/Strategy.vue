<script lang="ts" setup>
import { ElButton, ElCol, ElFormItem, ElIcon, ElInput, ElMessage, ElMessageBox, ElOption, ElRow, ElScrollbar, ElSelect, ElTabPane, ElTabs, MessageBoxInputData } from 'element-plus';
import { ref, computed, onBeforeMount } from 'vue';
import {Monaco} from 'vue-shiki-monaco';
import {Strategy, Factor, ParamType } from '../../store';
import {getStrategyDetail, getStrategyGroup, updateStrategy} from '../../api/strategy';
import ParamBand from '../element/ParamBand.vue';
import ParamEditor from '../element/ParamEditor.vue';

const props = defineProps({
    uuid: {
        type: String,
        default: '',
    }
})

const strategy = ref<Strategy>({
    uuid: '',
    name: 'unamed',
    param: [],
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

# 执行上下文
context: t.Dict[str, t.Any] = {}

def run(data: pd.DataFrame):
    pass
`
});

const show = ref<string>("code");

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
    const names = strategy.value.param.map(p => p.name);
    if (editingIndex.value >= 0) {
        return names.filter((_, i) => i !== editingIndex.value);
    }
    return names;
});

async function save() {
    if (!strategy.value) return;
    const resp = await updateStrategy(strategy.value);
    if (resp.code === 0) {
        ElMessage.success('策略已保存');
    } else {
        ElMessage.error('保存失败' + resp.msg);
    }
}

async function run() {

}

async function deleteParam(name: string) {
    // 如果正在编辑该参数，重置编辑状态
    if (editingParam.value && editingParam.value.name === name) {
        editingParam.value = null;
        editingIndex.value = -1;
    }
    strategy.value.param = strategy.value.param.filter(param => param.name !== name);
}

// 点击参数卡片 → 打开编辑 Tab
function editParam(name: string) {
    const idx = strategy.value.param.findIndex(p => p.name === name);
    if (idx === -1) return;
    editingIndex.value = idx;
    editingParam.value = { ...strategy.value.param[idx], enum: [...(strategy.value.param[idx].enum || [])] };
    show.value = 'edit';
}

// ParamEditor 保存回调
function onSaveParam(data: { name: string; type: ParamType; v: string | number | boolean; enum: string[] }) {
    if (editingIndex.value === -1) {
        // 新建
        strategy.value.param.push({ ...data });
    } else {
        // 编辑已有
        strategy.value.param[editingIndex.value] = { ...data };
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

onBeforeMount( async() => {
    fetchGroupOptions();
    if( props.uuid === "" || props.uuid === undefined) {
        return;  
    };
    const data = await getStrategyDetail(props.uuid);
    if( data === null) {
        ElMessage.error('策略不存在');
        return;
    }
})

</script>

<template>              
    <div style="width: 100%; height: 100%;padding-top: 10px;box-sizing: border-box;">
        <ElRow :gutter="24" style="height: 100%;margin: 0;">
            <ElCol :span="6">
                <div style="height: 100%; width: 100%;"> 
                    <div style="height: calc(60% - 70px);background-color: #eee;border-radius: 5px; padding: 10px;box-sizing: border-box;margin-bottom: 10px;">
                        <div style="height: 30px;width: 100%;"><ElButton style="border: none;" @click="addParam">添加参数</ElButton></div>
                        <div style="height: calc(100% - 30px); display: flex; flex-wrap: wrap; gap: 6px; padding: 4px 0; align-content: flex-start; overflow-y: auto; overflow-x: hidden; box-sizing: border-box;">
                            <ParamBand :name="item.name" :type="item.type" :v="item.v" :change-type="true" :on-delete="deleteParam" :on-click="editParam" v-for="item in strategy?.param" />
                        </div>
                    </div>
                    <div style="height: 40%;background-color: #eee;border-radius: 5px; padding: 10px;box-sizing: border-box;">
                        <div style="height: 30px;width: 100%;"><ElButton style="border: none;" @click="">添加因子</ElButton></div>
                        <ElScrollbar></ElScrollbar>
                    </div>
                    <div style="height: 60px; padding-top: 5px;box-sizing: border-box;">
                        <ElButton type="primary" @click="save">保存</ElButton>  
                        <ElButton type="primary" @click="run">运行</ElButton>
                    </div>
                </div>   
            </ElCol> 
            <ElCol :span="18">
                <ElTabs style="height: 100%" type="card" v-model="show">
                    <ElTabPane label="信息" name="info" style="height: 100%;">
                        <ElForm :model="strategy" label-width="100px" max-width="80%">
                            <ElFormItem label="策略名称">
                                <ElInput v-model="strategy.name" style="width: 240px;" disabled/>
                            </ElFormItem>
                            <ElFormItem label="版本">
                                <ElInput v-model="strategy.version" style="width: 240px;" disabled/>
                            </ElFormItem>
                            <ElFormItem label="分组">
                                <ElSelect v-model="strategy.group" style="width: 240px;" placeholder="请选择分组">
                                    <ElOption v-for="g in groupOptions" :key="g.id" :label="g.name" :value="g.id"/>
                                </ElSelect>
                            </ElFormItem>
                            <ElFormItem label="描述">
                                <ElInput v-model="strategy.description" type="textarea" :auto-size="{minRows: 2, maxRows: 4}" style="width: 400px;"/>
                            </ElFormItem>
                        </ElForm>
                    </ElTabPane>
                    <ElTabPane label="代码" name="code" style="height: 100%;">
                        <Monaco current-language="python" :value="strategy.content" :file-name="`${strategy.name}.py`" 
                        style="height: calc(100% - 10px);border: 0;box-shadow: none;border-radius: 0;" height="90%">
                        </Monaco>
                    </ElTabPane>
                    <ElTabPane label="图表" name="chart" style="height: 100%;">

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