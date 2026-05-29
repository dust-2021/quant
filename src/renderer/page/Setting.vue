<script setup lang="ts">
import { ElForm, ElFormItem, ElInput, ElMessage, ElMessageBox, ElScrollbar, ElButton, ElIcon, ElSwitch } from 'element-plus';
import { getSetting, setSetting, restartServer } from '../../api/setting';
import { ref, onBeforeMount } from 'vue';

const proxyAddress = ref<string>('');
const proxyPort = ref<number>(0);
const availableProxy = ref<boolean>(false);

async function handleRestart() {
    try {
        await ElMessageBox.confirm('确定要重启后端服务吗？', '确认重启', {
            confirmButtonText: '确定',
            cancelButtonText: '取消',
            type: 'warning',
        });
        const flag = await restartServer();
        if (flag) {
            ElMessage.success('后端服务正在重启，页面即将刷新...');
            // 等待 2 秒后刷新页面，给后端足够时间启动
            setTimeout(() => {
                window.location.reload();
            }, 2000);
        } else {
            ElMessage.error('重启失败');
        }
    } catch {
        // 用户取消操作
    }
}

onBeforeMount(async () => {
    proxyAddress.value = await getSetting('ProxyAddress') || '';
    proxyPort.value = Number(await getSetting('ProxyPort')) || 0;
    availableProxy.value = (await getSetting('AvailableProxy') || 'false') === 'true';
});

</script>

<template>
    <div style="padding: 20px;">
        <ElScrollbar>
        <ElForm label-width="120px" label-position="left" style="max-width: 80%;">
            <ElFormItem label="网络代理">
                <ElSwitch v-model="availableProxy" @change="setSetting('AvailableProxy', availableProxy)"></ElSwitch>
            </ElFormItem>
            <ElFormItem label="代理地址">
                <ElTooltip content="代理地址，用于访问互联网">
                    <ElInput style="width: 240px;" v-model="proxyAddress" type="text" @change="setSetting('ProxyAddress', proxyAddress)" />
                </ElTooltip>
            </ElFormItem>
            <ElFormItem label="代理端口">
                <ElTooltip content="代理端口，用于访问互联网">
                    <ElInput style="width: 120px;" type="number" v-model="proxyPort" @change="setSetting('ProxyPort', proxyPort)" />
                </ElTooltip>
            </ElFormItem>
            <ElFormItem label="系统管理">
                <ElButton type="danger" @click="handleRestart">重启后端服务</ElButton>
            </ElFormItem>
        </ElForm>
    </ElScrollbar>
    </div>
</template>