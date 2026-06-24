import {defineStore} from 'pinia';
import {ref} from 'vue';

export enum ParamType {
    Number = 'number',
    String = 'string',
    Boolean = 'boolean',
    Enum = 'enum'
}

interface param {
    name: string,
    type: ParamType,
    v: number | string | boolean,
    enum: string[]
}

export type Strategy = {
    uuid: string,
    name: string,
    params: param[],
    version: string,
    factors: string[],
    description: string,
    content: string,
    group: string,
}

export type Factor = {
    uuid: string,
    name: string,
    params: param[],
    version: string,
    description: string,
    content: string,
    group: string,
}

// =========== 策略结果 ===============

export const StrategyResultStore = defineStore('strategyResult', {
    state: () => ({
        data: new Map<string, {}>(),

    }),
    actions: {
        add(name: string, is_multi: boolean = false){

        }
    }
})

// =========== 主题/暗色模式 ===============

export const ThemeStore = defineStore('theme', {
    state: () => ({
        isDark: localStorage.getItem('theme-dark') === 'true',
    }),
    actions: {
        toggle() {
            this.isDark = !this.isDark;
            localStorage.setItem('theme-dark', String(this.isDark));
            this.applyTheme();
        },
        applyTheme() {
            if (this.isDark) {
                document.documentElement.classList.add('dark');
            } else {
                document.documentElement.classList.remove('dark');
            }
        },
        init() {
            this.applyTheme();
        },
    },
})


