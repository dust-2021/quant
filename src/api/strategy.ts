import {fetch} from "./base";
import {Strategy} from "../store";

interface strategyList {
    group_name: string;
    strategy_name: string;
    uuid: string;
    count: number;
}

export async function getStrategyList() {
    const resp = await fetch<strategyList[]>('/api/strategy/list', 'GET');
    if (resp === null) {
        return [] as strategyList[];
    }
    return resp.data; 
}

export async function getStrategyDetail(uuid: string) {
    const resp = await fetch('/api/strategy/detail', 'GET', {uuid: uuid});
    if (resp === null) {
        return null;
    }
    return resp.data as Strategy;
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