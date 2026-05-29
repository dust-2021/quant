import {fetch} from "./base";
import { ElMessage } from 'element-plus';


export async function getSetting<T = any>(name: string) {
    const resp = await fetch(`/api/config/${name}`, 'GET');
    if (resp === null || resp.code !== 0) {
        return null;
    }
    return resp.data as T;
}

export async function setSetting(name: string, value: any): Promise<boolean> {
    const resp = await fetch('/api/config', 'POST', {key: name, value: value});
    if (resp === null || resp.code !== 0) {
        ElMessage.error(`${name} ${value}, ${resp.msg}` || "设置失败");
        return false;
    }
    ElMessage.success(resp.msg || "设置成功");
    return true;
}

export async function restartServer() {
    const resp = await fetch('/api/restart', 'POST');
    return resp.code === 0;
}   