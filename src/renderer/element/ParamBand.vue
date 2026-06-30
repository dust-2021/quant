<script lang="ts" setup>
import { PropType, ref, watch, computed } from 'vue';
import {ParamType} from '../../store';
import { ElCol, ElIcon, ElInput, ElInputNumber, ElOption, ElRow, ElSelect, ElSwitch, ElText } from 'element-plus';
import { Delete } from '@element-plus/icons-vue';
import { useRouter } from 'vue-router';
import CustomIcon from './CustomIcon.vue';

const router = useRouter();
const props = defineProps({
    name: {
        type: String,   
        required: true,
    },
    type: {
        type: String as PropType<ParamType>,
        required: true,
    },
    v: {
        type: [String, Number, Boolean] as PropType<string | number | boolean>,
        required: true,
    },
    enums: {
        type: Array as PropType<string[]>,
        default: () => []   
    },
    changeType: {
        type: Boolean,
        default: false,
    },
    onDelete: {
        type: Function as PropType<(name: string) => void>,
        default: () => {}
    },
    onClick: {
        type: Function as PropType<(name: string) => void>,
        default: () => {}
    }
})

const param = ref<{name: string, type: ParamType, v: string | number | boolean, enum: string[]}>({ 
    name: "", type: ParamType.String, v: "", enum: []
});

// 监听 props 变化，保持本地状态同步
watch(
  () => [props.name, props.type, props.v, props.enums],
  () => {
    param.value = {
      name: props.name,
      type: props.type,
      v: props.v,
      enum: [...(props.enums || [])]
    };
  },
  { immediate: true }
);

const displayValue = computed(() => {
    switch (param.value.type) {
        case ParamType.Boolean:
            return String(Boolean(param.value.v));
        case ParamType.Number:
            return String(param.value.v);
        case ParamType.String:
        case ParamType.Enum:
        default:
            return param.value.v === null || param.value.v === undefined ? '' : String(param.value.v);
    }
});

// 根据参数类型显示不同的图标
const typePic = computed(() => {
    switch (param.value.type) {
        case ParamType.Boolean:
            return 'boolean';
        case ParamType.Number:
            return 'number';
        case ParamType.String:
            return 'string';
        case ParamType.Enum:
            return 'enum';
        default:
            return 'string';
    }
})

</script>

<style scoped>
.param-band-card {
    position: relative;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    height: 32px;
    padding: 0 8px;
    border-radius: 6px;
    background: var(--bg-tag);
    border: 1px solid var(--border-tag);
    box-sizing: border-box;
    transition: all 0.2s ease;
    flex-shrink: 0;
    cursor: pointer;
}
.param-band-card:hover {
    border-color: #409eff;
    background: var(--bg-tag-hover);
    box-shadow: 0 1px 4px rgba(64, 158, 255, 0.15);
}
.param-band-card:hover .param-band-delete {
    opacity: 1;
}

/* 删除按钮 */
.param-band-delete {
    position: absolute;
    top: -6px;
    right: -6px;
    width: 16px;
    height: 16px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #f56c6c;
    color: #fff;
    border-radius: 50%;
    cursor: pointer;
    opacity: 0;
    transition: opacity 0.2s ease;
    z-index: 1;
}
.param-band-delete:hover {
    background: #e04545;
    transform: scale(1.15);
}

/* 类型图标 */
.param-band-type {
    display: flex;
    align-items: center;
    font-size: 14px;
    color: var(--text-secondary);
    flex-shrink: 0;
}

/* 参数名 - 高亮 */
.param-band-name {
    max-width: 80px;
    flex-shrink: 1;
    font-size: 13px;
    font-weight: 700;
    color: #3370ff;
    overflow: hidden;
}

/* 分隔符 */
.param-band-sep {
    color: #c0c4cc;
    font-size: 12px;
    flex-shrink: 0;
}

/* 参数值 */
.param-band-value {
    max-width: 60px;
    flex-shrink: 1;
    font-size: 12px;
    color: #606266;
    overflow: hidden;
}
</style>

<template>
    <div class="param-band-card" @click="props.onClick?.(props.name)">
        <!-- 删除按钮 -->
        <div class="param-band-delete" @click.stop="props.onDelete?.(props.name)">
            <ElIcon :size="12"><Delete /></ElIcon>
        </div>
        <!-- 类型图标 -->
        <div class="param-band-type">
            <CustomIcon :name="typePic"></CustomIcon>
        </div>
        <!-- 参数名（高亮） -->
        <div class="param-band-name">
            <ElText :truncated="true" line-clamp="1">{{ param.name }}</ElText>
        </div>
        <!-- 分隔 -->
        <span class="param-band-sep">·</span>
        <!-- 参数值 -->
        <div class="param-band-value">
            <ElText :truncated="true" line-clamp="1">{{ displayValue }}</ElText>
        </div>
    </div>
</template>