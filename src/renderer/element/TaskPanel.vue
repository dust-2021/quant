<template>
  <div
    class="task-panel-wrapper"
    :style="{ top: posY + 'px', right: posX + 'px' }"
  >
    <!-- 悬浮按钮（拖拽手柄） -->
    <ElBadge :value="pendingCount" :hidden="pendingCount === 0" :max="99">
      <div
        class="task-btn"
        :class="{ 'task-btn--dragging': dragging }"
        @mousedown="startDrag"
        @click="togglePanel"
        :title="panelVisible ? '收起任务面板' : '展开任务面板（可拖拽）'"
      >
        <ElIcon :size="22"><CustomIcon name="task" /></ElIcon>
      </div>
    </ElBadge>

    <!-- 展开面板 -->
    <Transition name="panel-slide">
      <div v-if="panelVisible" class="task-panel">
        <div class="panel-header">
          <span class="panel-title">任务列表</span>
          <div class="panel-actions">
            <ElButton size="small" text type="primary" @click="store.clearFinished()" :disabled="!hasFinished">
              清空已完成
            </ElButton>
            <ElButton size="small" text @click="panelVisible = false">
              <ElIcon><Close /></ElIcon>
            </ElButton>
          </div>
        </div>
        <div class="panel-body">
          <div v-if="store.taskList.length === 0" class="empty-tip">暂无任务</div>
          <div v-for="task in store.taskList" :key="task.id" class="task-item">
            <div class="task-status">
              <ElIcon v-if="task.status === 'pending'" class="status-pending" :size="16">
                <Loading />
              </ElIcon>
              <ElIcon v-else-if="task.status === 'success'" class="status-success" :size="16">
                <CircleCheck />
              </ElIcon>
              <ElIcon v-else class="status-failed" :size="16">
                <CircleClose />
              </ElIcon>
            </div>
            <div class="task-info">
              <div class="task-name">{{ task.strategyName || task.id.slice(0, 8) }}</div>
              <div class="task-meta">
                <ElTag v-if="task.status === 'pending'" type="warning" size="small">运行中</ElTag>
                <ElTag v-else-if="task.status === 'success'" type="success" size="small">已完成</ElTag>
                <ElTag v-else type="danger" size="small">失败</ElTag>
                <span v-if="task.subIds" class="task-progress">{{ subProgress(task) }}</span>
                <span class="task-time">{{ formatTime(task.createdAt) }}</span>
              </div>
            </div>
            <div class="task-actions">
              <ElButton
                v-if="task.status !== 'pending'"
                size="small"
                text
                type="primary"
                @click="viewResult(task.id)"
              >查看</ElButton>
              <ElButton size="small" text @click="store.removeTask(task.id)">
                <ElIcon :size="14"><Close /></ElIcon>
              </ElButton>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script lang="ts" setup>
import { ref, computed, onBeforeUnmount } from 'vue';
import { ElBadge, ElIcon, ElButton, ElTag } from 'element-plus';
import { Close, Loading, CircleCheck, CircleClose } from '@element-plus/icons-vue';
import CustomIcon from './CustomIcon.vue';
import { StrategyResultStore } from '../../store';

const store = StrategyResultStore();

const panelVisible = ref(false);

// ======= 拖拽逻辑 =======
const posX = ref(16);   // 距右边缘距离 (px)
const posY = ref(16);   // 距顶部距离 (px)
const dragging = ref(false);

let dragStartX = 0;
let dragStartY = 0;
let dragOrigX = 0;
let dragOrigY = 0;
let hasMoved = false;
const DRAG_THRESHOLD = 3;  // 移动超过此像素才视为拖拽

function startDrag(e: MouseEvent) {
  // 阻止文本选择等默认行为
  e.preventDefault();
  dragging.value = true;
  hasMoved = false;
  dragStartX = e.clientX;
  dragStartY = e.clientY;
  dragOrigX = posX.value;
  dragOrigY = posY.value;
  document.addEventListener('mousemove', onDrag);
  document.addEventListener('mouseup', stopDrag);
}

function onDrag(e: MouseEvent) {
  const dx = dragStartX - e.clientX;  // 注意：posX 是距右边缘，鼠标左移 dx 为正
  const dy = e.clientY - dragStartY;
  if (Math.abs(dx) > DRAG_THRESHOLD || Math.abs(dy) > DRAG_THRESHOLD) {
    hasMoved = true;
  }
  // 限制在可视区域内
  const newX = Math.max(0, Math.min(dragOrigX + dx, window.innerWidth - 60));
  const newY = Math.max(0, Math.min(dragOrigY + dy, window.innerHeight - 60));
  posX.value = newX;
  posY.value = newY;
}

function stopDrag() {
  dragging.value = false;
  document.removeEventListener('mousemove', onDrag);
  document.removeEventListener('mouseup', stopDrag);
}

function togglePanel() {
  // 拖拽中不触发 click 展开/收起
  if (hasMoved) return;
  panelVisible.value = !panelVisible.value;
}

onBeforeUnmount(() => {
  document.removeEventListener('mousemove', onDrag);
  document.removeEventListener('mouseup', stopDrag);
});
// ======= 拖拽逻辑结束 =======

const pendingCount = computed(() =>
  store.taskList.filter(t => t.status === 'pending').length
);

const hasFinished = computed(() =>
  store.taskList.some(t => t.status !== 'pending')
);

function formatTime(ts: number): string {
  const d = new Date(ts);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function viewResult(id: string) {
  panelVisible.value = false;
  window.open(`/#/strategy/result?id=${encodeURIComponent(id)}`, '_blank');
}

function subProgress(task: typeof store.taskList[number]): string {
  if (!task.subStatus) return '';
  const total = Object.keys(task.subStatus).length;
  const done = Object.values(task.subStatus).filter(s => s !== 'pending').length;
  return `${done}/${total}`;
}
</script>

<style scoped>
.task-panel-wrapper {
  position: fixed;
  z-index: 1000;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8px;
  user-select: none;
}

.task-btn {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: var(--el-bg-color-overlay);
  border: 1px solid var(--el-border-color);
  box-shadow: 0 2px 16px rgba(0, 0, 0, 0.12), 0 0 0 1px rgba(0, 0, 0, 0.04);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: grab;
  transition: transform 0.2s, box-shadow 0.2s, border-color 0.2s;
  color: var(--el-text-color-primary);
  backdrop-filter: blur(8px);
}
.task-btn:hover {
  transform: scale(1.08);
  border-color: var(--el-color-primary-light-3);
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.18), 0 0 0 1px var(--el-color-primary-light-5);
}
.task-btn--dragging {
  cursor: grabbing;
  transform: scale(1.12);
  border-color: var(--el-color-primary);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.25), 0 0 0 2px var(--el-color-primary-light-5);
}

.task-panel {
  width: 360px;
  max-height: 480px;
  background: var(--el-bg-color-overlay);
  border: 1px solid var(--el-border-color);
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.12), 0 2px 8px rgba(0, 0, 0, 0.08);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  backdrop-filter: blur(12px);
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  background: var(--el-fill-color-light);
}
.panel-title {
  font-weight: 600;
  font-size: 15px;
}
.panel-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.panel-body {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}
.empty-tip {
  text-align: center;
  color: var(--el-text-color-secondary);
  padding: 32px 0;
  font-size: 14px;
}

.task-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  transition: background 0.15s;
}
.task-item:hover {
  background: var(--el-fill-color-light);
}

.task-status {
  flex-shrink: 0;
}
.status-pending {
  color: var(--el-color-warning);
  animation: spin 1.5s linear infinite;
}
.status-success {
  color: var(--el-color-success);
}
.status-failed {
  color: var(--el-color-danger);
}

.task-info {
  flex: 1;
  min-width: 0;
}
.task-name {
  font-size: 13px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.task-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
}
.task-time {
  font-size: 11px;
  color: var(--el-text-color-secondary);
}
.task-progress {
  font-size: 11px;
  color: var(--el-color-primary);
  font-weight: 500;
}

.task-actions {
  flex-shrink: 0;
  display: flex;
  align-items: center;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* 面板滑入动画 */
.panel-slide-enter-active,
.panel-slide-leave-active {
  transition: all 0.25s ease;
}
.panel-slide-enter-from,
.panel-slide-leave-to {
  opacity: 0;
  transform: translateY(-12px) scale(0.96);
}
</style>
