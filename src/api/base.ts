import axios from 'axios';

export interface appResponse<T = any> {
    code: number;
    msg?: string;
    data?: T;
}

const codeMessage: Map<number, string> = new Map([
    [200, '服务器成功返回请求的数据。'],
    [201, '新建或修改数据成功。'],
    [403, '拒绝访问。'],
]);

export async function fetch<T = any>(url: string, method: "GET" | "POST" = "GET", data?: any): Promise<appResponse<T>> {
    try {
        const resp =  await axios.request<appResponse<T>>({
        url: url, method: method, data: data,
    })
    if (resp.status !== 200) {
        return {code: resp.status, msg: codeMessage.get(resp.status) || '未知错误'} as appResponse<T>;
    }
    data = resp.data as appResponse<T>;
        if (data.code !== 0) {
            return {code: data.code, msg: data.msg || '未知错误'} as appResponse<T>;
        }
        return data;
    } catch (error) {
        return {code: 500, msg: '服务器内部错误'} as appResponse<T>;
    }
}
