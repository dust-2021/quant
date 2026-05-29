import { createApp } from 'vue';
import App from './renderer/App.vue';
import router from "./route";
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css';
import 'virtual:svg-icons-register';
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import {createPinia} from 'pinia';

const app = createApp(App);
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
    app.component(key, component)
}

app.use(ElementPlus);
app.use(router);
app.use(createPinia());
app.mount('#app');

app.onUnmount(() => {
});