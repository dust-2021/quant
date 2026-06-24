<template>
  <!-- 整体布局容器，使用 flex 实现并排 -->
  <div class="layout-container">
    <!-- 左侧边栏 -->
    <div class="sidebar" :style="{ width: menuWidth }">
      <el-menu
        :collapse="isCollapse"
        :collapse-transition="false"
        class="menu"
      >
        <el-menu-item index="0" @click="toggleCollapse">
          <el-icon><CustomIcon name="menuUnfold" v-if="isCollapse" /><CustomIcon name="menuFold" v-else /></el-icon>
        </el-menu-item>
        <el-menu-item index="1" @click="router.push({name: 'IndexCover'})">
          <el-icon><CustomIcon name="main" /></el-icon>
          <template #title>首页</template>
        </el-menu-item>
        <el-sub-menu index="2">
          <template #title>
            <el-icon><CustomIcon name="strategy" /></el-icon>
            <span>策略</span>
          </template>
          <el-menu-item index="2-1" @click="router.push({name: 'CreateStrategy'})"><el-icon><CustomIcon name="add" /></el-icon><span>添加策略</span></el-menu-item>
          <el-menu-item index="2-2" @click="router.push({name: 'StrategyView'})"><el-icon><CustomIcon name="list" /></el-icon><span>策略列表</span></el-menu-item>
        </el-sub-menu>
        <el-sub-menu index="3">
          <template #title>
            <el-icon><CustomIcon name="factor" /></el-icon>
            <span>因子</span>
          </template>
          <el-menu-item index="3-1" @click="router.push({name: 'CreateFactor'})"><el-icon><CustomIcon name="add" /></el-icon><span>添加因子</span></el-menu-item>
          <el-menu-item index="3-2" @click="router.push({name: 'FactorView'})"><el-icon><CustomIcon name="list" /></el-icon><span>因子列表</span></el-menu-item>
        </el-sub-menu>
        <el-menu-item index="4">
          <template #title>
            <ElIcon><CustomIcon name="calculator"></CustomIcon></ElIcon>
            <span>算子</span>
          </template>
        </el-menu-item>
        <ElMenuItem index="5" @click="router.push({name: 'DataCenter'})">
          <template #title>
            <ElIcon><CustomIcon name="data"></CustomIcon></ElIcon>
            <span>数据中心</span>
          </template>
        </ElMenuItem>
        <el-menu-item index="6" @click="router.push({name: 'Setting'})">
          <el-icon><CustomIcon name="setting" /></el-icon>
          <template #title><span>设置</span></template>
        </el-menu-item>
      </el-menu>

      <!-- 主题切换：固定在侧边栏底端 -->
      <div class="theme-toggle" @click="toggleTheme">
        <el-icon>
          <CustomIcon name="moon" v-if="!themeStore.isDark" />
          <CustomIcon name="sunny" v-else/>
        </el-icon>
        <span v-show="!isCollapse" class="theme-toggle__text">
          {{ themeStore.isDark ? '浅色模式' : '深色模式' }}
        </span>
      </div>
    </div>

    <!-- 右侧主要内容区域 -->
    <div class="main-content" :style="{ marginLeft: menuWidth }">
      <router-view name="main" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { HomeFilled, Document, Expand, Fold, Eleme } from '@element-plus/icons-vue'
import { ElIcon, ElMenuItem } from 'element-plus'
import { useRouter } from 'vue-router'
import CustomIcon from './element/CustomIcon.vue'
import { ThemeStore } from '../store'

const router = useRouter()
const themeStore = ThemeStore()

// 定义折叠状态
const isCollapse = ref(false)

// 切换折叠状态的方法
const toggleCollapse = () => {
  isCollapse.value = !isCollapse.value
}

// 切换暗色模式
const toggleTheme = () => {
  themeStore.toggle()
}

// 根据折叠状态计算菜单宽度
const menuWidth = computed(() => {
  return isCollapse.value ? '64px' : '200px'
})

onMounted(() => {
  themeStore.init()
})
</script>

<style scoped>
.layout-container {
  display: flex;
  min-height: 100vh;
}

/* 侧边栏：flex 列，菜单撑满，主题按钮固定底部 */
.sidebar {
  position: fixed;
  left: 0;
  top: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  transition: width 0.3s ease;
  z-index: 100;
}

.menu {
  flex: 1;
  overflow-y: auto;
  border-right: none;
}

.theme-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 56px;
  cursor: pointer;
  border-top: 1px solid var(--border-menu, #e6e6e6);
  color: var(--text-menu, #303133);
  transition: background-color 0.2s, color 0.2s;
  flex-shrink: 0;
}
.theme-toggle:hover {
  background-color: var(--bg-menu-hover, #f5f7fa);
}
.theme-toggle__text {
  margin-left: 8px;
  font-size: 14px;
}

.main-content {
  flex: 1;
  transition: margin-left 0.3s ease;
}
</style>