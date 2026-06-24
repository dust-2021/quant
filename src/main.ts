import { createApp } from 'vue';
import App from './renderer/App.vue';
import router from "./route";
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css';
import 'element-plus/theme-chalk/dark/css-vars.css'
import 'virtual:svg-icons-register';
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import {createPinia} from 'pinia';
import { ThemeStore } from './store';

const app = createApp(App);
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
    app.component(key, component)
}

app.use(ElementPlus);
app.use(router);
app.use(createPinia());
app.mount('#app');

// 初始化主题
const themeStore = ThemeStore();
themeStore.init();

app.onUnmount(() => {
});