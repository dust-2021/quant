import {createRouter, createWebHashHistory, RouteRecordRaw} from "vue-router";
import IndexCover from "./renderer/page/IndexCover.vue";

const routes: RouteRecordRaw[] = [
    {
        path: '/',
        components: {main: IndexCover},
        name: 'IndexCover',
    },
    {
        path: '/strategy/modify/:uuid',
        components: {main: () => import("./renderer/page/Strategy.vue")},
        name: 'Strategy',
        props: true
    },
    {
        path: '/strategy/create',
        components: {main: () => import("./renderer/page/Strategy.vue")},
        name: 'CreateStrategy',
        props: true
    },
    {
        path: '/setting',
        components: {main: () => import("./renderer/page/Setting.vue")},
        name: 'Setting',
    }
];
const router = createRouter({
    history: createWebHashHistory(),
    routes
})
export default router;