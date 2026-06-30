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
        const resp = await axios.request<appResponse<T>>({
            url: url, method: method, data: data,
            responseType: 'json',
        })
        if (resp.status !== 200) {
            return { code: resp.status, msg: codeMessage.get(resp.status) || `请求错误码：${resp.status}` } as appResponse<T>;
        };
        data = resp.data as appResponse<T>;
        // 大数据量响应可能未被自动解析为对象，手动兜底
        if (typeof data === 'string') {
            try {
                data = JSON.parse(data) as appResponse<T>;
            } catch {
                return { code: -1, msg: '响应解析失败' } as appResponse<T>;
            }
        }
        if ((data as appResponse<T>).code !== 0) {
            const d = data as appResponse<T>;
            return { code: d.code, msg: d.msg || `返回错误码：${d.code}` } as appResponse<T>;
        }
        return data as appResponse<T>;
    } catch (error) {
        return { code: 500, msg: '服务器内部错误' } as appResponse<T>;
    }
}
