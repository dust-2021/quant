import {fetch} from "./base";
import {Strategy} from "../store";

interface strategyList {
    group_name: string;
    strategy_name: string;
    uuid: string;
    version: string;
    description: string;
}

export async function getStrategyList() {
    const resp = await fetch<strategyList[]>('/api/strategy/list', 'GET');
    if (resp === null) {
        return [] as strategyList[];
    }
    return resp.data; 
}

export async function getStrategyDetail(uuid: string) {
    const resp = await fetch(`/api/strategy/${uuid}`, 'GET');
    if (resp === null) {
        return null;
    }
    return resp.data as {uuid: string, name: string, group: string, version: string, description: string, params: any[], factors: string[], factor_infos: {uuid: string, name: string, version: string, description: string}[], content: string};
}

export async function updateStrategy(params: Strategy) {
    return await fetch('/api/strategy/update', 'POST', params);
}

export async function getStrategyGroup() {
    const resp = await fetch<{id: string, name: string, description: string}[]>('/api/strategy/group', 'GET');
    if (resp === null || resp.code !== 0) {
        return [] as {id: string, name: string, description: string}[];
    }
    return resp.data as {id: string, name: string, description: string}[];
}

export async function createStrategyGroup(name: string, description: string = '') {
    return await fetch<{id: string, name: string, description: string}>('/api/strategy/group/create', 'POST', { name, description });
}

export async function deleteStrategyGroup(name: string) {
    return await fetch('/api/strategy/group/delete', 'POST', { name });
}

export async function deleteStrategy(uuid: string) {
    return await fetch('/api/strategy/delete', 'POST', { uuid });
}

/** 执行策略回测 
 * @param params.uuid 策略uuid
 * @param params.start_time 回测开始时间戳，单位秒
 * @param params.end_time 回测结束时间戳，单位秒
 * @param params.target 回测标的列表，默认为空表示不筛选，使用所有标的
 * @param params.period 回测周期，默认为1天，单位秒
 * @param params.runner_name 回测执行器名称，默认为"default"
 * @param params.multi_params 多参数回测：{"_strategy.param": [v1], "_factor.uuid.param": [v2]}
 * @param params.multi_expressions Python列表推导式：{"_strategy.param": "range(1,10)"}，优先级高于 multi_params 同名键
 * @return 回测结果id
*/
export async function executeStrategy(params: {
    uuid: string;
    start_time: number;
    end_time: number;
    target?: string[];
    period?: number;
    runner_name?: string;
    multi_params?: Record<string, (string | number | boolean)[]>;
    multi_expressions?: Record<string, string>;
}) {
    console.log('executeStrategy params:', params);
    return await fetch<string | string[]>('/api/strategy/execute', 'POST', params);
}

/** 获取回测执行器列表 */
export async function getRunnerList() {
    const resp = await fetch<string[]>('/api/execute/runners', 'GET');
    if (resp === null || resp.code !== 0) {
        return [] as string[];
    }
    return resp.data as string[];
}