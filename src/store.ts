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
    param: param[],
    version: string,
    factors: Factor[],
    description: string,
    content: string,
    group: string,
}

export type Factor = {
    uuid: string,
    name: string,
    param: param[],
    output: number | string | boolean,
    version: string,
    description: string,
    content: string
}

export const StrategyStore = defineStore('strategy',
    {
        state: () => ({
                data: new Map<string, Strategy>(),
                
            }),
        getters: {

        },
        actions: {

        }
    }
)

// =========== 策略结果 ===============

export const StrategyResultStore = defineStore('strategyResult', {
    state: () => ({
        status: new Map<string, boolean>(),
        result: new Map<string, any>(),
        check: (): boolean => {return true},
    }),

})


