<script lang="ts" setup>
import { ref, computed, onBeforeMount } from 'vue';
import { ElCard, ElTable, ElTableColumn, ElTag, ElButton, ElEmpty, ElScrollbar, ElMessage, ElMessageBox, ElDialog, ElForm, ElFormItem, ElInput } from 'element-plus';
import { useRouter } from 'vue-router';
import { getStrategyList, getStrategyGroup, createStrategyGroup, deleteStrategyGroup } from '../../api/strategy';
import { Strategy } from '../../store';

interface StrategyItem {
    group_name: string;
    strategy_name: string;
    uuid: string;
    version: string;
    description: string;
}

interface StrategyVersion {
    uuid: string;
    version: string;
    description: string;
}

interface StrategyNameGroup {
    name: string;
    versions: StrategyVersion[];
    versionCount: number;
}

interface GroupInfo {
    name: string;
    description: string;
    strategies: StrategyNameGroup[];
    totalCount: number;
}

const router = useRouter();
const groups = ref<GroupInfo[]>([]);
const selectedGroup = ref<GroupInfo | null>(null);
const loading = ref(false);

// 版本选择对话框
const showVersionDialog = ref(false);
const versionDialogStrategy = ref<StrategyNameGroup | null>(null);

function openVersionDialog(strategy: StrategyNameGroup) {
    versionDialogStrategy.value = strategy;
    showVersionDialog.value = true;
}

function selectVersion(uuid: string) {
    showVersionDialog.value = false;
    router.push({ name: 'Strategy', params: { uuid } });
}

async function refreshGroups() {
    const [list, groupInfos] = await Promise.all([
        getStrategyList(),
        getStrategyGroup(),
    ]);
    groups.value = buildGroups(groupInfos, list || []);
}

function buildGroups(
    groupInfos: { id: string; name: string; description: string }[],
    strategyList: StrategyItem[]
): GroupInfo[] {
    const result: GroupInfo[] = [];
    for (const gi of groupInfos) {
        // 筛选属于该分组且有效的策略（过滤左联产生的空行）
        const groupItems = strategyList.filter(
            item => item.group_name === gi.name && item.uuid && item.strategy_name
        );
        // 按 strategy_name 聚合版本
        const nameMap = new Map<string, StrategyVersion[]>();
        for (const item of groupItems) {
            const versions = nameMap.get(item.strategy_name) || [];
            versions.push({ uuid: item.uuid, version: item.version, description: item.description || '' });
            nameMap.set(item.strategy_name, versions);
        }
        const strategies: StrategyNameGroup[] = [];
        for (const [strategyName, versions] of nameMap) {
            strategies.push({
                name: strategyName,
                versions,
                versionCount: versions.length,
            });
        }
        result.push({
            name: gi.name,
            description: gi.description || '',
            strategies,
            totalCount: groupItems.length,
        });
    }
    return result;
}

// 新增分组对话框
const showCreateDialog = ref(false);
const newGroupForm = ref({ name: '', description: '' });
const creating = ref(false);

async function handleCreateGroup() {
    if (!newGroupForm.value.name.trim()) {
        ElMessage.error('分组名称不能为空');
        return;
    }
    creating.value = true;
    try {
        const resp = await createStrategyGroup(newGroupForm.value.name.trim(), newGroupForm.value.description.trim());
        if (resp.code === 0) {
            ElMessage.success('分组创建成功');
            showCreateDialog.value = false;
            newGroupForm.value = { name: '', description: '' };
            // 刷新分组列表
            await refreshGroups();
        } else {
            ElMessage.error(resp.msg || '创建失败');
        }
    } finally {
        creating.value = false;
    }
}

onBeforeMount(async () => {
    loading.value = true;
    try {
        await refreshGroups();
    } finally {
        loading.value = false;
    }
});

// 删除分组
const deletingGroup = ref(false);

async function handleDeleteGroup() {
    if (!selectedGroup.value) return;
    const groupName = selectedGroup.value.name;
    if (groupName === 'default') {
        ElMessage.error('不能删除默认分组');
        return;
    }
    try {
        await ElMessageBox.confirm(
            `确定要删除分组「${groupName}」吗？分组内 ${selectedGroup.value.totalCount} 个策略将移至 default 分组。`,
            '删除分组',
            { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
        );
    } catch {
        return; // 用户取消
    }
    deletingGroup.value = true;
    try {
        const resp = await deleteStrategyGroup(groupName);
        if (resp.code === 0) {
            ElMessage.success('分组已删除');
            selectedGroup.value = null;
            await refreshGroups();
        } else {
            ElMessage.error(resp.msg || '删除失败');
        }
    } finally {
        deletingGroup.value = false;
    }
}

function selectGroup(group: GroupInfo) {
    selectedGroup.value = group;
}

const displayGroups = computed(() => groups.value);
</script>

<template>
    <div class="strategy-view">
        <!-- 左侧：分组列表 -->
        <div class="left-panel">
            <div class="panel-header">
                <span>策略分组</span>
                <ElButton size="small" type="primary" @click="showCreateDialog = true">新增分组</ElButton>
            </div>
            <ElScrollbar>
                <div class="group-list" v-if="displayGroups.length > 0">
                    <div
                        v-for="group in displayGroups"
                        :key="group.name"
                        class="group-card"
                        :class="{ active: selectedGroup?.name === group.name }"
                        @click="selectGroup(group)"
                    >
                        <div class="group-card__header">
                            <span class="group-card__name">{{ group.name }}</span>
                            <ElTag size="small" type="info" effect="plain">{{ group.totalCount }} 个策略</ElTag>
                        </div>
                        <div class="group-card__desc" v-if="group.description">{{ group.description }}</div>
                        <div class="group-card__desc" v-else style="color: var(--text-secondary);">暂无描述</div>
                    </div>
                </div>
                <ElEmpty v-if="!loading && displayGroups.length === 0" description="暂无策略分组" />
            </ElScrollbar>
        </div>

        <!-- 右侧：策略详情 -->
        <div class="right-panel">
            <template v-if="selectedGroup">
                <div class="panel-header">
                    <span>{{ selectedGroup.name }} — 策略列表</span>
                    <ElButton
                        v-if="selectedGroup.name !== 'default'"
                        size="small"
                        type="danger"
                        :loading="deletingGroup"
                        @click="handleDeleteGroup"
                    >
                        删除分组
                    </ElButton>
                </div>
                <ElScrollbar>
                    <ElTable
                        :data="selectedGroup.strategies"
                        style="width: 100%;"
                        v-loading="loading"
                        stripe
                    >
                        <ElTableColumn prop="name" label="策略名称" min-width="160">
                            <template #default="{ row }">
                                <span class="strategy-name-link">{{ row.name }}</span>
                            </template>
                        </ElTableColumn>
                        <ElTableColumn label="版本数" width="100" align="center">
                            <template #default="{ row }">
                                <ElTag size="small" type="info" effect="plain">{{ row.versionCount }} 个版本</ElTag>
                            </template>
                        </ElTableColumn>
                        <ElTableColumn label="操作" width="100" fixed="right">
                            <template #default="{ row }">
                                <ElButton v-if="row.versionCount === 1" size="small" text type="primary" @click.stop="selectVersion(row.versions[0].uuid)">
                                    查看
                                </ElButton>
                                <ElButton v-else size="small" text type="primary" @click.stop="openVersionDialog(row)">
                                    选择版本
                                </ElButton>
                            </template>
                        </ElTableColumn>
                    </ElTable>
                </ElScrollbar>
            </template>
            <div v-else class="right-placeholder">
                <ElEmpty description="请从左侧选择一个策略分组" />
            </div>
        </div>

        <!-- 新增分组对话框 -->
        <ElDialog v-model="showCreateDialog" title="新增分组" width="420px" :close-on-click-modal="false">
            <ElForm :model="newGroupForm" label-width="80px">
                <ElFormItem label="分组名称" required>
                    <ElInput v-model="newGroupForm.name" placeholder="请输入分组名称" maxlength="50" />
                </ElFormItem>
                <ElFormItem label="描述">
                    <ElInput v-model="newGroupForm.description" type="textarea" :autosize="{ minRows: 2, maxRows: 4 }" placeholder="请输入分组描述（可选）" maxlength="200" />
                </ElFormItem>
            </ElForm>
            <template #footer>
                <ElButton @click="showCreateDialog = false">取消</ElButton>
                <ElButton type="primary" :loading="creating" @click="handleCreateGroup">确定</ElButton>
            </template>
        </ElDialog>

        <!-- 版本选择对话框 -->
        <ElDialog v-model="showVersionDialog" :title="`选择版本 — ${versionDialogStrategy?.name}`" width="420px">
            <div class="version-list" v-if="versionDialogStrategy">
                <div
                    v-for="v in versionDialogStrategy.versions"
                    :key="v.uuid"
                    class="version-item"
                    @click="selectVersion(v.uuid)"
                >
                    <div class="version-item__header">
                        <span class="version-item__label">版本 {{ v.version }}</span>
                        <span class="version-item__uuid">{{ v.uuid }}</span>
                    </div>
                    <div class="version-item__desc" v-if="v.description">{{ v.description }}</div>
                </div>
            </div>
            <template #footer>
                <ElButton @click="showVersionDialog = false">取消</ElButton>
            </template>
        </ElDialog>
    </div>
</template>

<style scoped>
.strategy-view {
    display: flex;
    height: 100%;
    box-sizing: border-box;
}

/* ===== 左侧面板 ===== */
.left-panel {
    width: 300px;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    border-right: 1px solid var(--border-tag, #e4e7ed);
    background-color: var(--bg-card);
}

.panel-header {
    padding: 14px 16px;
    font-size: 15px;
    font-weight: 600;
    color: var(--text-primary);
    border-bottom: 1px solid var(--border-tag, #e4e7ed);
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.group-list {
    padding: 8px;
}

.group-card {
    padding: 12px;
    margin-bottom: 8px;
    border-radius: 8px;
    border: 1px solid var(--border-tag, #e4e7ed);
    cursor: pointer;
    transition: all 0.2s ease;
    background-color: var(--bg-card);
}
.group-card:hover {
    border-color: #409eff;
    box-shadow: 0 2px 8px rgba(64, 158, 255, 0.12);
}
.group-card.active {
    border-color: #409eff;
    background-color: var(--bg-tag-hover, #ecf5ff);
}

.group-card__header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 6px;
}
.group-card__name {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
}
.group-card__desc {
    font-size: 12px;
    color: var(--text-regular);
    line-height: 1.5;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

/* ===== 右侧面板 ===== */
.right-panel {
    flex: 1;
    display: flex;
    flex-direction: column;
    background-color: var(--bg-card);
    min-width: 0;
}

.right-placeholder {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
}

.strategy-name-link {
    color: #409eff;
    cursor: pointer;
}
.strategy-name-link:hover {
    text-decoration: underline;
}

/* ===== 版本选择对话框 ===== */
.version-list {
    max-height: 300px;
    overflow-y: auto;
}
.version-item {
    padding: 10px 12px;
    border-radius: 6px;
    cursor: pointer;
    transition: background-color 0.15s;
}
.version-item:hover {
    background-color: var(--bg-tag-hover, #ecf5ff);
}
.version-item__header {
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.version-item__label {
    font-size: 14px;
    font-weight: 500;
    color: var(--text-primary);
}
.version-item__uuid {
    font-size: 12px;
    font-family: monospace;
    color: var(--text-secondary);
}
.version-item__desc {
    margin-top: 6px;
    font-size: 12px;
    color: var(--text-regular);
    line-height: 1.5;
}
</style>
