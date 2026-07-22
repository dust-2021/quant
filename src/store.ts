import {defineStore} from 'pinia';
import {ref} from 'vue';
import {fetch} from './api/base';

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

export interface TaskItem {
    id: string;
    strategyName: string;
    status: 'pending' | 'success' | 'failed';
    createdAt: number;
    data?: taskResult;
    error?: string;
    /** 多参数并行时的参数键列表（带前缀，如 ["_strategy.leverage", "_factor.uuid.window"]） */
    multiParamKeys?: string[];
    /** 多参数并行时的子任务 ID 列表 */
    subIds?: string[];
    /** 子任务状态：subId → status */
    subStatus?: Record<string, 'pending' | 'success' | 'failed'>;
    /** 子任务错误信息：subId → error msg */
    subErrors?: Record<string, string>;
}

export interface taskResult {
    startTime: number,
    endTime: number,
    target: string[],
    period: number,
    params: Record<string, any>,
    liquidation: number | null,
    data: string | null, // dataframe的json字符串，多参数执行时不返回计算数据
    premium: number,
    netValue: number,
    annualizedRateOfReturn: number,
    monthlyRateOfReturn: number,
    maximumDrawdown: number,
    tradeCount: number,
    winRate: number | null,
    maximumProfit: number,
    maximumLoss: number,
    averageProfitLossRatio: number,
    tradeData: string, // 交易df的json字符串
}

/** 根据子任务状态汇总组状态 */
function aggregateStatus(subStatus: Record<string, 'pending' | 'success' | 'failed'>): 'pending' | 'success' | 'failed' {
    const values = Object.values(subStatus);
    if (values.some(s => s === 'failed')) return 'failed';
    if (values.every(s => s === 'success')) return 'success';
    return 'pending';
}

export const StrategyResultStore = defineStore('strategyResult', {
    state: () => ({
        tasks: new Map<string, TaskItem>(),
        _pollTimer: null as ReturnType<typeof setInterval> | null,
        _polling: false,
    }),
    getters: {
        taskList(state): TaskItem[] {
            return Array.from(state.tasks.values()).sort((a, b) => b.createdAt - a.createdAt);
        },
        hasRunning(): boolean {
            return Array.from(this.tasks.values()).some(t => t.status === 'pending');
        },
    },
    actions: {
        /** 添加任务到列表并开始轮询。
         *  ids 为数组时视为同一任务的多个子任务，合并为一个组任务存储，
         *  所有子任务完成后组任务视为完成，任意子任务失败组任务视为失败。
         */
        addTasks(ids: string | string[], strategyName: string = '', runnerName: string = '', multiParamKeys?: string[], strategyUid?: string, strategyVersion?: string, factorSnapshots?: any[]) {
            const meta = { strategyName, runnerName: runnerName || 'default', multiParamKeys: multiParamKeys || [], strategyUid: strategyUid || '', strategyVersion: strategyVersion || '', factorSnapshots: factorSnapshots || [] };
            if (Array.isArray(ids)) {
                const groupId = ids[0];
                const subStatus: Record<string, 'pending'> = {};
                for (const subId of ids) { subStatus[subId] = 'pending'; }
                sessionStorage.setItem(`task_${groupId}`, JSON.stringify({ ...meta, subIds: ids }));
                if (!this.tasks.has(groupId)) {
                    this.tasks.set(groupId, {
                        id: groupId,
                        strategyName,
                        status: 'pending',
                        createdAt: Date.now(),
                        multiParamKeys: multiParamKeys || [],
                        subIds: ids,
                        subStatus,
                    });
                }
            } else {
                sessionStorage.setItem(`task_${ids}`, JSON.stringify(meta));
                if (!this.tasks.has(ids)) {
                    this.tasks.set(ids, {
                        id: ids,
                        strategyName,
                        status: 'pending',
                        createdAt: Date.now(),
                    });
                }
            }
            this._startPolling();
        },

        /** 移除单个任务 */
        removeTask(id: string) {
            this.tasks.delete(id);
            if (this.tasks.size === 0) {
                this._stopPolling();
            }
        },

        /** 清空已完成/失败的任务 */
        clearFinished() {
            for (const [id, task] of this.tasks) {
                if (task.status !== 'pending') {
                    this.tasks.delete(id);
                }
            }
            if (this.tasks.size === 0) {
                this._stopPolling();
            }
        },

        /** 轮询所有 pending 任务 */
        async _pollResults() {
            const pendingTasks = Array.from(this.tasks.values()).filter(t => t.status === 'pending');
            if (pendingTasks.length === 0) {
                this._stopPolling();
                return;
            }
            for (const task of pendingTasks) {
                if (task.subIds && task.subStatus) {
                    // 组任务：轮询所有子任务
                    await this._pollGroupTask(task);
                } else {
                    // 单任务：直接轮询
                    await this._pollSingleTask(task);
                }
            }
            // 检查是否还有 pending 任务
            const stillPending = Array.from(this.tasks.values()).some(t => t.status === 'pending');
            if (!stillPending) {
                this._stopPolling();
            }
        },

        /** 轮询单个子任务 */
        async _pollSingleTask(task: TaskItem) {
            try {
                const resp = await fetch<any>(`/api/execute/result/${task.id}`, 'GET');
                if (resp.code === 0) {
                    this.tasks.set(task.id, { ...task, status: 'success', data: resp.data });
                } else if (resp.code === 2) {
                    // NOT_FOUND — 仍在运行，保持 pending
                } else {
                    this.tasks.set(task.id, { ...task, status: 'failed', error: resp.msg || `未知错误 (code: ${resp.code})` });
                }
            } catch {
                // 网络错误，保持 pending 等下次轮询
            }
        },

        /** 轮询组任务的所有子任务 */
        async _pollGroupTask(task: TaskItem) {
            if (!task.subIds || !task.subStatus) return;
            let changed = false;
            if (!task.subErrors) task.subErrors = {};
            for (let i = 0; i < task.subIds.length; i++) {
                const subId = task.subIds[i];
                if (task.subStatus[subId] !== 'pending') continue;
                try {
                    const resp = await fetch<any>(`/api/execute/result/${subId}`, 'GET');
                    if (resp.code === 0) {
                        task.subStatus[subId] = 'success';
                        changed = true;
                    } else if (resp.code === 2) {
                        // 仍在运行
                    } else {
                        task.subStatus[subId] = 'failed';
                        task.subErrors[subId] = resp.msg || `未知错误 (code: ${resp.code})`;
                        changed = true;
                    }
                } catch {
                    // 网络错误
                }
            }
            if (!changed) return;
            const newStatus = aggregateStatus(task.subStatus);
            const errorEntry = Object.entries(task.subStatus).find(([, s]) => s === 'failed');
            if (errorEntry && newStatus === 'failed') {
                const failedId = errorEntry[0];
                task.error = task.subErrors?.[failedId] || `子任务 ${failedId.slice(0, 8)} 执行失败`;
            }
            this.tasks.set(task.id, {
                ...task,
                status: newStatus,
            });
        },

        _startPolling() {
            if (this._pollTimer) return;
            this._pollTimer = setInterval(() => {
                this._pollResults();
            }, 3000);
            // 立即执行一次
            this._pollResults();
        },

        _stopPolling() {
            if (this._pollTimer) {
                clearInterval(this._pollTimer);
                this._pollTimer = null;
            }
        },
    },
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


