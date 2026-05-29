
<template>
  <!-- 整体布局容器，使用 flex 实现并排 -->
  <div class="layout-container">
    <!-- 左侧菜单区域 -->
    <el-menu
      :collapse="isCollapse"
      :collapse-transition="false" 
      class="menu"
      :style="{ width: menuWidth }" 
    >
      <!-- 菜单项... -->
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
        <el-menu-item index="2-2"><el-icon><CustomIcon name="list" /></el-icon><span>策略列表</span></el-menu-item>
      </el-sub-menu>
      <el-menu-item index="3">
        <el-icon><CustomIcon name="factor" /></el-icon>
        <template #title>
            <span>因子</span>
        </template>
        </el-menu-item>
      <el-menu-item index="4" @click="router.push({name: 'Setting'})">
        <el-icon><CustomIcon name="setting" /></el-icon>
        <template #title>
            <span>设置</span>
        </template>
      </el-menu-item>
    </el-menu>

    <!-- 右侧主要内容区域 -->
    <div class="main-content" :style="{ marginLeft: menuWidth }">
      <!-- 页面内容展示区 -->
      <router-view name="main" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { HomeFilled, Document, Expand, Fold, Eleme } from '@element-plus/icons-vue'
import { ElIcon, ElMenuItem } from 'element-plus'
import { useRouter } from 'vue-router'
import CustomIcon from './element/CustomIcon.vue'
import { el } from 'element-plus/es/locales.mjs'

const router = useRouter()
// 定义折叠状态
const isCollapse = ref(false)

// 切换折叠状态的方法
const toggleCollapse = () => {
  isCollapse.value = !isCollapse.value
}

// 根据折叠状态计算菜单宽度
// 通常 Element Plus 菜单折叠后宽度为 64px，展开时可根据设计设定，如 200px
const menuWidth = computed(() => {
  return isCollapse.value ? '64px' : '200px'
})
</script>

<style scoped>
.layout-container {
  display: flex;
  min-height: 100vh;
}

.menu {
  position: fixed;
  left: 0;
  top: 0;
  bottom: 0;
  transition: width 0.3s ease; 
  overflow-y: auto;
}

.main-content {
  flex: 1; 
  transition: margin-left 0.3s ease; 
}
</style>