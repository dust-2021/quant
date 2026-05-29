<script lang="ts" setup>
import { ref, reactive, watch, computed, nextTick } from 'vue';
import { ElButton, ElForm, ElFormItem, ElInput, ElInputNumber, ElMessage, ElOption, ElSelect, ElSwitch, ElTag, InputInstance } from 'element-plus';
import { ParamType } from '../../store';

export interface ParamData {
    name: string;
    type: ParamType;
    v: string | number | boolean;
    enum: string[];
}

const props = defineProps({
    /** 被编辑的参数，null 表示新建 */
    param: {
        type: Object as () => ParamData | null,
        default: null,
    },
    /** 已存在的参数名列表（排除自身），用于重名校验 */
    existingNames: {
        type: Array as () => string[],
        default: () => [],
    },
});

const emit = defineEmits<{
    (e: 'save', data: ParamData): void;
    (e: 'cancel'): void;
    (e: 'delete', name: string): void;
}>();

const form = reactive<ParamData>({
    name: '',
    type: ParamType.Boolean,
    v: false,
    enum: [],
});
const inputVisible = ref(false);
const enumInput = ref('');
const InputRef = ref<InputInstance>();

// 枚举类型输入框
const showInput = () => {
  inputVisible.value = true
  nextTick(() => {
    InputRef.value!.input!.focus()
  })
}

// 监听外部 param 变化，同步到内部表单
watch(() => props.param, (p) => {
    if (p) {
        form.name = p.name;
        form.type = p.type;
        form.v = p.v;
        form.enum = [...(p.enum || [])];
    } else {
        form.name = '';
        form.type = ParamType.Boolean;
        form.v = false;
        form.enum = [];
    }
    enumInput.value = '';
}, { immediate: true });

const isNew = computed(() => props.param === null);

// 类型切换时重置默认值
function onTypeChange() {
    if (form.type === ParamType.Boolean) form.v = false;
    else if (form.type === ParamType.Number) form.v = 0;
    else form.v = '';
}

function addEnumValue() {
    const val = enumInput.value.trim();
    if (val && !form.enum.includes(val)) {
        form.enum.push(val);
    }
    inputVisible.value = false;
    enumInput.value = '';
}

function removeEnumValue(val: string) {
    form.enum = form.enum.filter(v => v !== val);
    if (form.v === val) {
        form.v = form.enum.length > 0 ? form.enum[0] : '';
    }
}

function handleSave() {
    if (!form.name.trim()) {
        ElMessage.error('参数名不能为空');
        return;
    }
    // 重名校验
    if (props.existingNames.includes(form.name)) {
        ElMessage.error('参数名已存在');
        return;
    }
    emit('save', {
        name: form.name,
        type: form.type,
        v: form.v,
        enum: [...form.enum]
    });
}

function handleDelete() {
    if (props.param) {
        emit('delete', props.param.name);
    }
}
</script>

<template>
    <div class="param-editor">
        <div class="param-editor__header">
            <span class="param-editor__title">{{ isNew ? '新建参数' : '编辑参数' }}</span>
        </div>

        <ElForm label-width="60px" label-position="left" style="max-width: 80%;">
            <ElFormItem label="参数名">
                <ElInput v-model="form.name" placeholder="请输入参数名" style="width: 240px;" />
            </ElFormItem>
            <ElFormItem label="类型">
                <ElSelect v-model="form.type" style="width: 240px;" @change="onTypeChange">
                    <ElOption label="布尔" :value="ParamType.Boolean" />
                    <ElOption label="数字" :value="ParamType.Number" />
                    <ElOption label="字符串" :value="ParamType.String" />
                    <ElOption label="枚举" :value="ParamType.Enum" />
                </ElSelect>
            </ElFormItem>

            <!-- 非枚举类型的默认值 -->
            <ElFormItem label="默认值" v-if="form.type !== ParamType.Enum">
                <ElSwitch v-if="form.type === ParamType.Boolean" v-model="(form as any).v" />
                <ElInputNumber v-else-if="form.type === ParamType.Number" v-model="(form as any).v" style="width: 240px;" />
                <ElInput v-else v-model="(form as any).v" style="width: 240px;" placeholder="请输入默认值" />
            </ElFormItem>

            <!-- 枚举类型 -->
            <template v-if="form.type === ParamType.Enum">
                <ElFormItem label="枚举值">
                    <div style="display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px;">
                        <ElTag v-for="val in form.enum" :key="val" @click="removeEnumValue(val)">
                            {{ val }}
                        </ElTag>
                        <el-input
                        style="width: 80px;"
                        v-if="inputVisible"
                        ref="InputRef"
                        v-model="enumInput"
                        size="small"
                        @keyup.enter="addEnumValue"
                        @blur="addEnumValue"/>
                        <el-button v-else class="button-new-tag" size="small" @click="showInput">
                        + New Tag
                        </el-button>
                    </div>
                </ElFormItem>
                <ElFormItem label="默认值">
                    <ElSelect v-model="(form as any).v" style="width: 240px;">
                        <ElOption v-for="val in form.enum" :key="val" :label="val" :value="val" />
                    </ElSelect>
                </ElFormItem>
            </template>

            <ElFormItem>
                <div style="display: flex; gap: 10px;">
                    <ElButton type="primary" @click="handleSave">保存</ElButton>
                    <ElButton @click="emit('cancel')">取消</ElButton>
                    <ElButton v-if="!isNew" type="danger" plain @click="handleDelete">删除参数</ElButton>
                </div>
            </ElFormItem>
        </ElForm>
    </div>
</template>

<style scoped>
.param-editor {
    height: 100%;
    padding: 16px 20px;
    overflow-y: auto;
    box-sizing: border-box;
}
.param-editor__header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
}
.param-editor__title {
    font-size: 16px;
    font-weight: 600;
    color: #303133;
}
</style>
