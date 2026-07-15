import { v4 as uuidv4 } from 'uuid';
import {ref} from 'vue';
import CryptoJs from 'crypto-js';
import axios from 'axios';

// ws请求
type wsPayload = {
    id: string,
    method: string,
    params?: any[],
}

// ws响应
export type wsResponse = {
    id: string,
    status: number,
    result?: any,
    error?: {
        code: number,
        msg: string
    },
}

// ws事件返回数据类型
export type eventResponse = {
    e: string, E: number, s?: string, k?: {
        t: number, T: number, s: string, i: string, f: number, L: number, o: string, c: string, h: string, l: string, v: string, n: number,
        x: boolean, q: string, V: string, Q: string, B: string
    }, o?: any
}

export class Binance {
    public static readonly httpUrl: string = "https://api.binance.com";
    public static readonly wsUrl: string = "wss://stream.binance.com/ws";

    private static instance: Binance | null = null;

    public static getInstance(apiKey: string = ""): Binance {
        if (!Binance.instance) {
            Binance.instance = new Binance(apiKey);
        }
        return Binance.instance;
    }

    public apiKey: string;

    private connection: WebSocket | null = null;
    private subscribedStreams: Set<string> = new Set();
    private wsRespHandle: Map<string, (data: wsResponse) => void> = new Map();
    private wsEventHandle: Map<string, (data: eventResponse) => void> = new Map();

    private constructor(apiKey: string = "") {
        this.apiKey = apiKey;
    }

    private formatParam(record: Record<string, any>, signature: boolean = false): string {
        let query = "";
        for (const key in record) {
            if (record[key] === undefined || record[key] === null) {
                continue;
            }
            if (query) {
                query += "&";
            }
            query += `${key}=${encodeURIComponent(record[key])}`;
        }
        if (signature) {
            const signatureValue = CryptoJs.HmacSHA256(query, this.apiKey).toString(CryptoJs.enc.Hex);
            query += `&signature=${signatureValue}`;
        }
        return query;
    }

    private async httpRequest(url: string, method: "GET" | "POST" = "GET", encrypt: boolean = false, data: Record<string, any> = {}): Promise<any> {
        let fullUrl = Binance.httpUrl + url + (data ? "?" + this.formatParam(data, encrypt) : "");
        if(encrypt){
            data['timestamp'] = Date.now();
            data['recvWindow'] = 5000;
        }
        return axios.request({
            url: fullUrl,
            method: method,
            headers: {
                'Content-Type': 'application/json',
                'X-MBX-APIKEY': this.apiKey,
            },
        }).then(response => {
            return response.data;
        }).catch(error => {
            console.error("HTTP request error:", error);
            throw error;
        });
    }

    public async positions(): Promise<{}[]> {

        return [];
    }

    // ============= ws =====================

    public connect() {
        if (this.connection && this.connection.readyState === WebSocket.OPEN) {
            return;
        }
        this.connection = new WebSocket(Binance.wsUrl);
        this.connection.onmessage = this.handleMessage.bind(this);
    }

    public disconnect() {
        if (this.connection) {
            this.connection.close();
            this.connection = null;
            this.subscribedStreams.clear();
            this.wsRespHandle.clear();
        }
    }

    private async handleEvent(data: eventResponse) {
        const eventType = data.e;
    }

    private async handleMessage(event: MessageEvent) {
        if (event.data === 'ping') {
            this.connection?.send('pong');
            return;
        }
        const data: wsResponse | eventResponse = JSON.parse(event.data);
        if ('e' in data) {
            await this.handleEvent(data);
            return;
        }
        const cb = this.wsRespHandle.get(data.id);
        if (cb) {
            cb(data);
        }
    }

    private send(payload: wsPayload, cb?: (data: wsResponse) => void) {
        if (!this.connection || this.connection.readyState !== WebSocket.OPEN) {
            throw new Error("WebSocket connection is not open.");
        }
        this.connection.send(JSON.stringify(payload));
        if (cb) {
            this.wsRespHandle.set(payload.id, cb);
        }
    }

    public subscribe(stream: string, cb: (data: wsResponse) => void) {
        if (!this.connection || this.connection.readyState !== WebSocket.OPEN) {
            this.connect();
        }
        this.send({id: uuidv4(), method: "SUBSCRIBE", params: [stream]}, (data: wsResponse) => {
            this.subscribedStreams.add(stream);
            this.wsRespHandle.set(stream, cb);
        });
        
    }
}