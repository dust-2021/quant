import {fetch} from "./base";
import {Factor} from "../store";

interface FactorListItem {
    group_name: string;
    factor_name: string;
    uuid: string;
    version: string;
    description: string;
}

export async function getFactorList() {
    const resp = await fetch<FactorListItem[]>('/api/factor/list', 'GET');
    if (resp === null) {
        return [] as FactorListItem[];
    }
    return resp.data;
}

export async function getFactorDetail(uuid: string) {
    const resp = await fetch(`/api/factor/${uuid}`, 'GET');
    if (resp === null) {
        return null;
    }
    return resp.data as Factor;
}

export async function updateFactor(params: Factor) {
    return await fetch('/api/factor/update', 'POST', params);
}

export async function deleteFactor(uuid: string) {
    return await fetch('/api/factor/delete', 'POST', { uuid });
}

export async function getFactorGroup() {
    const resp = await fetch<{id: string, name: string, description: string}[]>('/api/factor/group', 'GET');
    if (resp === null || resp.code !== 0) {
        return [] as {id: string, name: string, description: string}[];
    }
    return resp.data as {id: string, name: string, description: string}[];
}

export async function createFactorGroup(name: string, description: string = '') {
    return await fetch<{id: string, name: string, description: string}>('/api/factor/group/create', 'POST', { name, description });
}

export async function deleteFactorGroup(name: string) {
    return await fetch('/api/factor/group/delete', 'POST', { name });
}
