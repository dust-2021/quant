<script lang="ts" setup>
import { ref, computed, onBeforeMount } from 'vue';
import { ElCard, ElTag, ElButton, ElEmpty, ElScrollbar, ElMessage, ElMessageBox, ElDialog, ElForm, ElFormItem, ElInput } from 'element-plus';
import { useRouter } from 'vue-router';
import { getFactorList, getFactorGroup, createFactorGroup, deleteFactorGroup } from '../../api/factor';

interface FactorItem {
    group_name: string;
    factor_name: string;
    uuid: string;
    version: string;
    description: string;
}

interface FactorVersion {
    uuid: string;
    version: string;
    description: string;
}

interface FactorNameGroup {
    name: string;
    versions: FactorVersion[];
    versionCount: number;
}

interface GroupInfo {
    name: string;
    description: string;
    factors: FactorNameGroup[];
    totalCount: number;
}

const router = useRouter();
const groups = ref<GroupInfo[]>([]);
const selectedGroup = ref<GroupInfo | null>(null);
const loading = ref(false);

// 版本选择对话框
const showVersionDialog = ref(false);
const versionDialogFactor = ref<FactorNameGroup | null>(null);

function openVersionDialog(factor: FactorNameGroup) {
    versionDialogFactor.value = factor;
    showVersionDialog.value = true;
}

function selectVersion(uuid: string) {
    showVersionDialog.value = false;
    router.push({ name: 'Factor', params: { uuid } });
}

async function refreshGroups() {
    const [list, groupInfos] = await Promise.all([
        getFactorList(),
        getFactorGroup(),
    ]);
    groups.value = buildGroups(groupInfos, list || []);
}

function buildGroups(
    groupInfos: { id: string; name: string; description: string }[],
    factorList: FactorItem[]
): GroupInfo[] {
    const result: GroupInfo[] = [];
    for (const gi of groupInfos) {
        const groupItems = factorList.filter(
            item => item.group_name === gi.name && item.uuid && item.factor_name
        );
        const nameMap = new Map<string, FactorVersion[]>();
        for (const item of groupItems) {
            const versions = nameMap.get(item.factor_name) || [];
            versions.push({ uuid: item.uuid, version: item.version, description: item.description || '' });
            nameMap.set(item.factor_name, versions);
        }
        const factors: FactorNameGroup[] = [];
        for (const [factorName, versions] of nameMap) {
            factors.push({
                name: factorName,
                versions,
                versionCount: versions.length,
            });
        }
        result.push({
            name: gi.name,
            description: gi.description || '',
            factors,
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
        const resp = await createFactorGroup(newGroupForm.value.name.trim(), newGroupForm.value.description.trim());
        if (resp.code === 0) {
            ElMessage.success('分组创建成功');
            showCreateDialog.value = false;
            newGroupForm.value = { name: '', description: '' };
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
            `确定要删除分组「${groupName}」吗？分组内 ${selectedGroup.value.totalCount} 个因子将移至 default 分组。`,
            '删除分组',
            { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
        );
    } catch {
        return;
    }
    deletingGroup.value = true;
    try {
        const resp = await deleteFactorGroup(groupName);
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
    <div class="factor-view">
        <!-- 左侧：分组列表 -->
        <div class="left-panel">
            <div class="panel-header">
                <span>因子分组</span>
                <ElButton size="small" type="primary" @click="showCreateDialog = true">新增分组</ElButton>
            </div>
            <ElScrollbar>
                <div class="group-list" v-if="displayGroups.length > 0">
                    <ElCard
                        v-for="group in displayGroups"
                        :key="group.name"
                        class="group-card"
                        :class="{ active: selectedGroup?.name === group.name }"
                        shadow="hover"
                        @click="selectGroup(group)"
                    >
                        <div class="group-card__header">
                            <span class="group-card__name">{{ group.name }}</span>
                            <ElTag size="small" type="info" effect="plain">{{ group.totalCount }} 个因子</ElTag>
                        </div>
                        <div class="group-card__desc" v-if="group.description">{{ group.description }}</div>
                        <div class="group-card__desc" v-else style="color: var(--text-secondary);">暂无描述</div>
                    </ElCard>
                </div>
                <ElEmpty v-if="!loading && displayGroups.length === 0" description="暂无因子分组" />
            </ElScrollbar>
        </div>

        <!-- 右侧：因子详情 -->
        <div class="right-panel">
            <template v-if="selectedGroup">
                <div class="panel-header">
                    <span>{{ selectedGroup.name }} — 因子列表</span>
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
                    <div class="factor-list" v-loading="loading">
                        <template v-if="selectedGroup.factors.length > 0">
                            <ElCard
                                v-for="item in selectedGroup.factors"
                                :key="item.name"
                                class="factor-card"
                                shadow="hover"
                            >
                                <div class="factor-card__header">
                                    <span class="factor-card__name">{{ item.name }}</span>
                                    <ElTag size="small" type="info" effect="plain">{{ item.versionCount }} 个版本</ElTag>
                                </div>
                                <div class="factor-card__actions">
                                    <ElButton v-if="item.versionCount === 1" size="small" type="primary" @click="selectVersion(item.versions[0].uuid)">
                                        查看
                                    </ElButton>
                                    <ElButton v-else size="small" type="primary" @click="openVersionDialog(item)">
                                        选择版本
                                    </ElButton>
                                </div>
                            </ElCard>
                        </template>
                        <ElEmpty v-else-if="!loading" description="暂无因子" />
                    </div>
                </ElScrollbar>
            </template>
            <div v-else class="right-placeholder">
                <ElEmpty description="请从左侧选择一个因子分组" />
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
        <ElDialog v-model="showVersionDialog" :title="`选择版本 — ${versionDialogFactor?.name}`" width="420px">
            <div class="version-list" v-if="versionDialogFactor">
                <div
                    v-for="v in versionDialogFactor.versions"
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
.factor-view {
    display: flex;
    gap: 12px;
    height: 100%;
    box-sizing: border-box;
    padding: 12px;
    background-color: var(--bg-page);
}

/* ===== 左侧面板 ===== */
.left-panel {
    width: 300px;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    background-color: var(--bg-card);
    border-radius: 8px;
    padding: 12px;
    min-height: 0;
}

.left-panel :deep(.el-scrollbar) {
    flex: 1;
    min-height: 0;
}

.panel-header {
    font-size: 15px;
    font-weight: 600;
    color: var(--text-primary);
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 8px;
}

.group-list {
    padding: 2px;
}

.group-card {
    cursor: pointer;
    margin-bottom: 8px;
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
}
.group-card.active {
    border-color: var(--el-color-primary);
    box-shadow: 0 0 0 1px var(--el-color-primary);
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
    border-radius: 8px;
    padding: 12px;
    min-width: 0;
    min-height: 0;
}

.right-panel :deep(.el-scrollbar) {
    flex: 1;
    min-height: 0;
}

.right-placeholder {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
}

.factor-list {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: 12px;
    padding: 2px;
}

.factor-card__header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 10px;
}
.factor-card__name {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
}
.factor-card__actions {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
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
