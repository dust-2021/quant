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
        path: '/strategy/view',
        components: {main: () => import("./renderer/page/StrategyView.vue")},
        name: 'StrategyView',
    },
    {
        path: '/setting',
        components: {main: () => import("./renderer/page/Setting.vue")},
        name: 'Setting',
    },
    {
        path: '/factor/modify/:uuid',
        components: {main: () => import("./renderer/page/Factor.vue")},
        name: 'Factor',
        props: true
    },
    {
        path: '/factor/create',
        components: {main: () => import("./renderer/page/Factor.vue")},
        name: 'CreateFactor',
        props: true
    },
    {
        path: '/factor/view',
        components: {main: () => import("./renderer/page/FactorView.vue")},
        name: 'FactorView',
    },
    {
        path: '/calculator',
        components: {},
        name: 'Calculator'
    },
    {
        path: '/dataCenter',
        components: {main: () => import("./renderer/page/DataCenter.vue")},
        name: 'DataCenter'
    }
];
const router = createRouter({
    history: createWebHashHistory(),
    routes
})
export default router;