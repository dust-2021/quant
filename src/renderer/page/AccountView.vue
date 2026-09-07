<template>
    <div class="account-view">
        <div class="panel-header">
            <h3>账号列表</h3>
            <ElButton type="primary" size="small" @click="openCreateDialog">新增账号</ElButton>
        </div>

        <div class="content-card">
            <ElScrollbar v-loading="loading">
                <ElTable :data="accounts" stripe style="width: 100%;">
                    <ElTableColumn prop="name" label="名称" min-width="120" />
                    <ElTableColumn prop="exchange" label="交易所" width="100" />
                    <ElTableColumn label="策略" min-width="140">
                        <template #default="{ row }">
                            <span>{{ strategyNameMap[row.strategy_uuid] || '-' }}</span>
                        </template>
                    </ElTableColumn>
                    <ElTableColumn label="状态" width="80" align="center">
                        <template #default="{ row }">
                            <ElButton v-if="row.status === 0" circle size="small" type="success" plain title="执行中，点击暂停" @click="toggleStatus(row)">
                                <ElIcon><VideoPlay /></ElIcon>
                            </ElButton>
                            <ElButton v-else circle size="small" type="info" plain title="已暂停，点击启动" @click="toggleStatus(row)">
                                <ElIcon><VideoPause /></ElIcon>
                            </ElButton>
                        </template>
                    </ElTableColumn>
                    <ElTableColumn label="周期" width="120" align="center">
                        <template #default="{ row }">
                            <ElSelect v-model="row.period" size="small" style="width: 90px;" @change="handlePeriodChange(row)">
                                <ElOption v-for="p in periodOptions" :key="p.value" :label="p.label" :value="p.value" />
                            </ElSelect>
                        </template>
                    </ElTableColumn>
                    <ElTableColumn label="标的" min-width="220">
                        <template #default="{ row }">
                            <ElSelect v-model="row.targets" size="small" multiple filterable allow-create default-first-option
                                :reserve-keyword="false" placeholder="输入/选择标的" style="width: 100%;"
                                @change="handleTargetChange(row)">
                                <ElOption v-for="t in row.targets" :key="t" :label="t" :value="t" />
                            </ElSelect>
                        </template>
                    </ElTableColumn>
                    <ElTableColumn label="操作" width="140" align="center" fixed="right">
                        <template #default="{ row }">
                            <ElButton size="small" type="primary" link @click="openEditDialog(row)">编辑</ElButton>
                            <ElButton size="small" type="danger" link @click="handleDelete(row)">删除</ElButton>
                        </template>
                    </ElTableColumn>
                </ElTable>
                <ElEmpty v-if="!loading && !accounts.length" description="暂无账号数据" />
            </ElScrollbar>
        </div>

        <!-- 新增账号弹窗 -->
        <ElDialog v-model="showCreateDialog" title="新增账号" width="560px" :close-on-click-modal="false">
            <ElForm :model="createForm" label-width="120px">
                <ElFormItem label="账号名称" required>
                    <ElInput v-model="createForm.name" placeholder="请输入账号名称" style="width: 100%;" />
                </ElFormItem>
                <ElFormItem label="交易所" required>
                    <ElSelect v-model="createForm.exchange" placeholder="选择交易所" style="width: 100%;" filterable>
                        <ElOption v-for="ex in exchangeOptions" :key="ex.id" :label="ex.name" :value="ex.name" />
                    </ElSelect>
                </ElFormItem>
                <ElFormItem label="API Key">
                    <ElInput v-model="createForm.api_key" placeholder="请输入 API Key（可选）" style="width: 100%;" />
                </ElFormItem>
                <ElFormItem label="API Secret">
                    <ElInput v-model="createForm.api_secret" type="password" show-password placeholder="请输入 API Secret（可选）" style="width: 100%;" />
                </ElFormItem>
                <ElFormItem label="API Passphrase">
                    <ElInput v-model="createForm.api_passphrase" type="password" show-password placeholder="可选" style="width: 100%;" />
                </ElFormItem>
                <ElFormItem label="加密方式">
                    <ElSelect v-model="createForm.encrypt_type" style="width: 160px;">
                        <ElOption v-for="e in encryptTypeOptions" :key="e.value" :label="e.label" :value="e.value" />
                    </ElSelect>
                </ElFormItem>
                <ElFormItem label="绑定策略">
                    <ElSelect v-model="createForm.strategy_uuid" placeholder="选择策略（可选）" clearable filterable style="width: 100%;">
                        <ElOption v-for="s in strategyOptions" :key="s.value" :label="s.label" :value="s.value" />
                    </ElSelect>
                </ElFormItem>
                <ElFormItem label="执行器 ID">
                    <ElInput v-model="createForm.trader_id" type="number" placeholder="可选" style="width: 100%;" />
                </ElFormItem>
                <ElFormItem label="执行周期">
                    <ElSelect v-model="createForm.period" style="width: 160px;">
                        <ElOption v-for="p in periodOptions" :key="p.value" :label="p.label" :value="p.value" />
                    </ElSelect>
                </ElFormItem>
                <ElFormItem label="标的">
                    <ElSelect v-model="createForm.targets" multiple filterable allow-create default-first-option
                        :reserve-keyword="false" placeholder="输入标的，如 BTCUSDT" style="width: 100%;">
                        <ElOption v-for="t in createForm.targets" :key="t" :label="t" :value="t" />
                    </ElSelect>
                </ElFormItem>
            </ElForm>
            <template #footer>
                <ElButton @click="showCreateDialog = false">取消</ElButton>
                <ElButton type="primary" :loading="saving" @click="handleCreate">确定</ElButton>
            </template>
        </ElDialog>

        <!-- 编辑账号弹窗 -->
        <ElDialog v-model="showEditDialog" title="编辑账号" width="560px" :close-on-click-modal="false">
            <ElForm :model="editForm" label-width="120px">
                <ElFormItem label="账号名称" required>
                    <ElInput v-model="editForm.name" placeholder="请输入账号名称" style="width: 100%;" />
                </ElFormItem>
                <ElFormItem label="交易所" required>
                    <ElSelect v-model="editForm.exchange" placeholder="选择交易所" style="width: 100%;" filterable>
                        <ElOption v-for="ex in exchangeOptions" :key="ex.id" :label="ex.name" :value="ex.name" />
                    </ElSelect>
                </ElFormItem>
                <ElFormItem label="API Key" required>
                    <ElInput v-model="editForm.api_key" placeholder="请输入 API Key" style="width: 100%;" />
                </ElFormItem>
                <ElFormItem label="API Secret" required>
                    <ElInput v-model="editForm.api_secret" type="password" show-password placeholder="请输入 API Secret" style="width: 100%;" />
                </ElFormItem>
                <ElFormItem label="API Passphrase">
                    <ElInput v-model="editForm.api_passphrase" type="password" show-password placeholder="可选" style="width: 100%;" />
                </ElFormItem>
                <ElFormItem label="加密方式">
                    <ElSelect v-model="editForm.encrypt_type" style="width: 160px;">
                        <ElOption v-for="e in encryptTypeOptions" :key="e.value" :label="e.label" :value="e.value" />
                    </ElSelect>
                </ElFormItem>
                <ElFormItem label="绑定策略">
                    <ElSelect v-model="editForm.strategy_uuid" placeholder="选择策略（可选）" clearable filterable style="width: 100%;">
                        <ElOption v-for="s in strategyOptions" :key="s.value" :label="s.label" :value="s.value" />
                    </ElSelect>
                </ElFormItem>
                <ElFormItem label="执行器 ID">
                    <ElInput v-model="editForm.trader_id" type="number" placeholder="可选" style="width: 100%;" />
                </ElFormItem>
            </ElForm>
            <template #footer>
                <ElButton @click="showEditDialog = false">取消</ElButton>
                <ElButton type="primary" :loading="saving" @click="handleUpdate">确定</ElButton>
            </template>
        </ElDialog>
    </div>
</template>

<script setup lang="ts">
import { ref, onBeforeMount } from 'vue'
import { ElTable, ElTableColumn, ElButton, ElIcon, ElSelect, ElOption, ElDialog, ElForm, ElFormItem, ElInput, ElMessage, ElMessageBox, ElEmpty, ElScrollbar } from 'element-plus'
import { VideoPlay, VideoPause } from '@element-plus/icons-vue'
import { getAccounts, createAccount, updateAccount, deleteAccount, setAccountStatus } from '../../api/account'
import { getExchanges, type ExchangeItem } from '../../api/dataCenter'
import { getStrategyList } from '../../api/strategy'

interface AccountRow {
    id: number
    name: string
    exchange: string
    api_key: string
    api_secret: string
    api_passphrase: string | null
    encrypt_type: string
    strategy_uuid: string | null
    status: number
    trader_id: number | null
    period: number
    target: string
    targets: string[]
}

const accounts = ref<AccountRow[]>([])
const exchangeOptions = ref<ExchangeItem[]>([])
const strategyOptions = ref<{ value: string; label: string }[]>([])
const strategyNameMap = ref<Record<string, string>>({})
const loading = ref(false)
const saving = ref(false)

const periodOptions = [
    { label: '1 分钟', value: 60 },
    { label: '1 小时', value: 3600 },
    { label: '1 天', value: 86400 },
]

const encryptTypeOptions = [
    { label: 'HMAC SHA256', value: 'hmac' },
    { label: 'Ed25519', value: 'ed25519' },
]

function parseTargets(target: string): string[] {
    try {
        const arr = JSON.parse(target)
        return Array.isArray(arr) ? arr : []
    } catch {
        return []
    }
}

async function refresh() {
    loading.value = true
    try {
        const list = await getAccounts()
        accounts.value = list.map(a => ({ ...a, targets: parseTargets(a.target) }))
    } finally {
        loading.value = false
    }
}

async function loadExchanges() {
    exchangeOptions.value = await getExchanges()
}

async function loadStrategies() {
    const list = (await getStrategyList()) || []
    strategyOptions.value = list.map(s => ({
        value: s.uuid,
        label: `${s.strategy_name} (${s.version})`,
    }))
    strategyNameMap.value = {}
    for (const s of list) {
        strategyNameMap.value[s.uuid] = s.strategy_name
    }
}

// ===== 行内状态切换 =====
async function toggleStatus(row: any) {
    const newStatus = row.status === 0 ? 1 : 0
    const ok = await setAccountStatus(row.id, newStatus)
    if (ok) {
        row.status = newStatus
    } else {
        await refresh()
    }
}

async function handlePeriodChange(row: any) {
    const ok = await updateAccount({ id: row.id, period: row.period })
    if (!ok) await refresh()
}

async function handleTargetChange(row: any) {
    const target = JSON.stringify(row.targets || [])
    const ok = await updateAccount({ id: row.id, target })
    if (ok) {
        row.target = target
    } else {
        await refresh()
    }
}

// ===== 新增 =====
const showCreateDialog = ref(false)
const createForm = ref({
    name: '',
    exchange: '',
    api_key: '',
    api_secret: '',
    api_passphrase: '',
    encrypt_type: 'hmac',
    strategy_uuid: '',
    trader_id: null as number | null,
    period: 60,
    targets: [] as string[],
})

function openCreateDialog() {
    createForm.value = {
        name: '', exchange: '', api_key: '', api_secret: '', api_passphrase: '',
        encrypt_type: 'hmac', strategy_uuid: '', trader_id: null, period: 60, targets: [],
    }
    showCreateDialog.value = true
}

async function handleCreate() {
    if (!createForm.value.name.trim() || !createForm.value.exchange.trim()) {
        ElMessage.warning('请填写名称和交易所')
        return
    }
    saving.value = true
    try {
        const ok = await createAccount({
            name: createForm.value.name.trim(),
            exchange: createForm.value.exchange.trim(),
            api_key: createForm.value.api_key.trim(),
            api_secret: createForm.value.api_secret.trim(),
            api_passphrase: createForm.value.api_passphrase || null,
            encrypt_type: createForm.value.encrypt_type,
            strategy_uuid: createForm.value.strategy_uuid || null,
            trader_id: createForm.value.trader_id,
            period: createForm.value.period,
            target: JSON.stringify(createForm.value.targets || []),
        })
        if (ok) {
            showCreateDialog.value = false
            await refresh()
        }
    } finally {
        saving.value = false
    }
}

// ===== 编辑 =====
const showEditDialog = ref(false)
const editForm = ref({
    id: 0,
    name: '',
    exchange: '',
    api_key: '',
    api_secret: '',
    api_passphrase: '',
    encrypt_type: 'hmac',
    strategy_uuid: '',
    trader_id: null as number | null,
})

function openEditDialog(row: any) {
    editForm.value = {
        id: row.id,
        name: row.name,
        exchange: row.exchange,
        api_key: row.api_key,
        api_secret: row.api_secret,
        api_passphrase: row.api_passphrase || '',
        encrypt_type: row.encrypt_type || 'hmac',
        strategy_uuid: row.strategy_uuid || '',
        trader_id: row.trader_id,
    }
    showEditDialog.value = true
}

async function handleUpdate() {
    if (!editForm.value.name.trim() || !editForm.value.exchange.trim() ||
        !editForm.value.api_key.trim() || !editForm.value.api_secret.trim()) {
        ElMessage.warning('请填写名称、交易所、API Key 和 API Secret')
        return
    }
    saving.value = true
    try {
        const ok = await updateAccount({
            id: editForm.value.id,
            name: editForm.value.name.trim(),
            exchange: editForm.value.exchange.trim(),
            api_key: editForm.value.api_key.trim(),
            api_secret: editForm.value.api_secret.trim(),
            api_passphrase: editForm.value.api_passphrase || null,
            encrypt_type: editForm.value.encrypt_type,
            strategy_uuid: editForm.value.strategy_uuid || null,
            trader_id: editForm.value.trader_id,
        })
        if (ok) {
            showEditDialog.value = false
            await refresh()
        }
    } finally {
        saving.value = false
    }
}

// ===== 删除 =====
async function handleDelete(row: any) {
    if (row.status === 0) {
        ElMessage.warning('账号处于执行中状态，请先暂停后再删除')
        return
    }
    try {
        await ElMessageBox.confirm(`确定要删除账号「${row.name}」吗？`, '删除账号', {
            confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning',
        })
    } catch {
        return
    }
    const ok = await deleteAccount(row.id)
    if (ok) await refresh()
}

onBeforeMount(() => {
    refresh()
    loadExchanges()
    loadStrategies()
})
</script>

<style scoped>
.account-view {
    padding: 16px;
    box-sizing: border-box;
    height: 100%;
    display: flex;
    flex-direction: column;
    gap: 12px;
    overflow: hidden;
    background-color: var(--bg-page);
}

.panel-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-shrink: 0;
}

.panel-header h3 {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
}

.content-card {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    background-color: var(--bg-card);
    border-radius: 8px;
    padding: 12px;
    box-sizing: border-box;
}

.content-card :deep(.el-scrollbar) {
    flex: 1;
    min-height: 0;
}
</style>
