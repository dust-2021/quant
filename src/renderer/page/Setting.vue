<script setup lang="ts">
import { ElForm, ElFormItem, ElInput, ElMessage, ElMessageBox, ElScrollbar, ElButton, ElIcon, ElSwitch, ElRow, ElCol, ElSelect, ElOption, ElTooltip } from 'element-plus';
import { getSetting, setSetting, restartServer } from '../../api/setting';
import { ref, onBeforeMount } from 'vue';

const dataCenterLink = ref<string>('');

const baseLog = ref<string>('INFO');
const webLog = ref<string>('INFO');
const sqlalchemyLog = ref<string>('WARNING');
const auth = ref<boolean>(false);

const logLevels = ['DEBUG', 'INFO', 'WARNING', 'ERROR'];

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
    dataCenterLink.value = await getSetting('DataCenterLink') || '';

    baseLog.value = await getSetting('BaseLog') || 'INFO';
    webLog.value = await getSetting('WebLog') || 'INFO';
    sqlalchemyLog.value = await getSetting('SQLAlchemyLog') || 'WARNING';
    auth.value = (await getSetting('Auth') || 'false') === 'true';

    proxyAddress.value = await getSetting('ProxyAddress') || '';
    proxyPort.value = Number(await getSetting('ProxyPort')) || 0;
    availableProxy.value = (await getSetting('AvailableProxy') || 'false') === 'true';
});

</script>

<template>
    <div style="padding: 20px;">
        <ElRow>
            <ElCol :span="12">
                <h2>静态设置</h2>
                <ElForm label-width="120px" label-position="left" style="max-width: 80%;">
                    <ElFormItem label="数据库链接">
                        <ElTooltip content="存储历史数据的数据库链接，格式为：dialect+driver://username:password@host:port/database">
                            <ElInput style="width: 400px;" v-model="dataCenterLink" type="text" :rows="2" @change="setSetting('DataCenterLink', dataCenterLink)"/>
                        </ElTooltip>
                    </ElFormItem>
                    <ElFormItem label="基础日志">
                        <ElSelect v-model="baseLog" style="width: 140px;" @change="setSetting('BaseLog', baseLog)">
                            <ElOption v-for="lv in logLevels" :key="lv" :label="lv" :value="lv" />
                        </ElSelect>
                    </ElFormItem>
                    <ElFormItem label="Web 日志">
                        <ElSelect v-model="webLog" style="width: 140px;" @change="setSetting('WebLog', webLog)">
                            <ElOption v-for="lv in logLevels" :key="lv" :label="lv" :value="lv" />
                        </ElSelect>
                    </ElFormItem>
                    <ElFormItem label="SQL 日志">
                        <ElSelect v-model="sqlalchemyLog" style="width: 140px;" @change="setSetting('SQLAlchemyLog', sqlalchemyLog)">
                            <ElOption v-for="lv in logLevels" :key="lv" :label="lv" :value="lv" />
                        </ElSelect>
                    </ElFormItem>
                    <ElFormItem label="权限认证">
                        <ElSwitch v-model="auth" @change="setSetting('Auth', auth)"></ElSwitch>
                    </ElFormItem>
                </ElForm>
            </ElCol>
            <ElCol :span="12">
                <h2>动态设置</h2>
                <ElScrollbar>
        <ElForm label-width="120px" label-position="left" style="max-width: 80%;">
            <ElFormItem label="网络代理">
                <ElSwitch v-model="availableProxy" @change="setSetting('AvailableProxy', availableProxy)"></ElSwitch>
            </ElFormItem>
            <ElFormItem label="代理地址">
                <ElTooltip content="代理地址，用于访问互联网">
                    <ElInput style="width: 240px;" v-model="proxyAddress" type="text" @change="setSetting('ProxyAddress', proxyAddress)"  />
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
            </ElCol>
        </ElRow>
        
    </div>
</template>