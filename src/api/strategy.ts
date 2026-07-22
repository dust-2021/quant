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

/** 保存策略回测结果 */
export async function saveStrategyResult(data: {
    result_uuid: string; name: string; strategy_uid: string;
    strategy_version: string; strategy_params?: any; factor_snapshots?: any[];
    exec_start_time: number; exec_end_time: number; period: number;
    targets?: string[]; runner_name?: string;
    metrics: Record<string, any>; trade_data?: string; chart_data?: string;
    multi_param_keys?: string[]; multi_results?: any[];
}) {
    return await fetch('/api/strategy/result/save', 'POST', data);
}

/** 获取策略的所有保存结果 */
export interface SavedResultItem {
    uuid: string; name: string; strategy_version: string;
    exec_start_time: number; exec_end_time: number; period: number;
    runner_name: string; create_time: number; multi_param_keys: string[] | null;
}
export async function getSavedResults(strategyUuid: string): Promise<SavedResultItem[]> {
    const resp = await fetch<SavedResultItem[]>(`/api/strategy/${strategyUuid}/results`, 'GET');
    if (resp === null || resp.code !== 0) return [];
    return resp.data || [];
}

/** 获取单个保存结果的完整数据 */
export async function getSavedResultDetail(resultUuid: string): Promise<any> {
    const resp = await fetch<any>(`/api/strategy/result/saved/${resultUuid}`, 'GET');
    if (resp === null || resp.code !== 0) return null;
    return resp.data;
}

/** 删除保存的回测结果 */
export async function deleteSavedResult(resultUuid: string) {
    return await fetch('/api/strategy/result/delete', 'POST', { result_uuid: resultUuid });
}