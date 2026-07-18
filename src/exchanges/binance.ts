import { v4 as uuidv4 } from 'uuid';
import CryptoJs from 'crypto-js';
import axios from 'axios';
import { ElMessage } from 'element-plus';

// ws请求
type wsPayload = {
    id: string,
    method: string,
    params?: any[],
}

// ws响应
export type wsResponse = {
    id: string,
    status?: number,
    result?: any,
    error?: {
        code: number,
        msg: string
    },
}

type wsCallback = (data: wsResponse) => any;
type wsEventCallback = (data: eventData) => any;

export type tradeType = 'spot' | 'swap';
export type reqType = 'ws' | 'stream' | 'http';
export type binanceInterval = '1s' | '1m' | '3m' | '5m' | '15m' | '30m' | '1h' | '2h' | '4h' | '6h' | '8h' | '12h' | '1d' | '3d' | '1w' | '1M';

// ws事件返回数据类型
export type eventData = {
    e: string, E: number, s?: string, ps?: string, ct?: string, k?: {
        t: number, T: number, s: string, i: string, f: number, L: number, o: string, c: string, h: string, l: string, v: string, n: number,
        x: boolean, q: string, V: string, Q: string, B: string
    }, o?: any
}

type eventPaload = {
    stream: string,
    data: eventData
}

type exchangeInfoT = {
    serverTime: number, rateLimits: object[],
    symbols: { symbol: string, status: string }[]
}

export class Binance {
    public static readonly urls: Record<reqType, Record<tradeType, string>> = {
        stream: { spot: "wss://stream.binance.com:9443", swap: "wss://fstream.binance.com/market/stream" },
        ws: { spot: "wss://ws-api.binance.com:443/ws-api/v3", swap: "wss://ws-fapi.binance.com/ws-fapi/v1" },
        http: { spot: "https://api.binance.com", swap: "https://fapi.binance.com" }
    }

    private static instance: Binance | null = null;

    public static getInstance(apiKey: string = ""): Binance {
        if (!Binance.instance) {
            Binance.instance = new Binance(apiKey);
        }
        return Binance.instance;
    }

    private exchangeinfoData: Record<tradeType, exchangeInfoT | null> = {spot: null, swap: null};

    private apiKey: string;

    private conns: Record<reqType, Record<tradeType, WebSocket | null>> = {
        stream: { spot: null, swap: null },
        ws: { spot: null, swap: null },
        http: { spot: null, swap: null }
    };
    // 处理ws请求响应的回调函数
    private wsRespHandle: Map<string, wsCallback> = new Map();
    // 处理ws事件响应的回调函数
    private wsEventHandle: Map<string, wsEventCallback> = new Map();

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

    private async httpRequest(url: string, method: "GET" | "POST" = "GET", t: tradeType = 'spot',
        encrypt: boolean = false, data: Record<string, any> = {}) {
        let fullUrl = Binance.urls.http[t] + url + (data ? "?" + this.formatParam(data, encrypt) : "");
        if (encrypt) {
            data['timestamp'] = Date.now();
            data['recvWindow'] = 5000;
        }
        const resp = await axios.request({
            url: fullUrl,
            method: method,
            headers: {
                'Content-Type': 'application/json',
                'X-MBX-APIKEY': this.apiKey,
            },
        });
        if (resp.status !== 200) return null;
        return resp.data;
    }

    public async serverTime(): Promise<number> {
        const data = await this.httpRequest('/api/v3/time');
        if (data) {
            return data.serverTime as number;
        } return 0;
    }

    /**
     * 获取交易对信息（节选）
     * 全字段数据如下：
     * {
  "timezone": "UTC",
  "serverTime": 1565246363776,
  "rateLimits": [
    {
      "rateLimitType": "REQUEST_WEIGHT",
      "interval": "MINUTE",
      "intervalNum": 1,
      "limit": 6000
    },
    {
      "rateLimitType": "ORDERS",
      "interval": "DAY",
      "intervalNum": 1,
      "limit": 160000
    },
    {
      "rateLimitType": "RAW_REQUESTS",
      "interval": "MINUTE",
      "intervalNum": 5,
      "limit": 61000
    }
  ],
  "exchangeFilters": [],
  "symbols": [
    {
      "symbol": "ETHBTC",
      "status": "TRADING",
      "baseAsset": "ETH",
      "baseAssetPrecision": 8,
      "quoteAsset": "BTC",
      "quotePrecision": 8,
      "quoteAssetPrecision": 8,
      "baseCommissionPrecision": 8,
      "quoteCommissionPrecision": 8,
      "orderTypes": [
        "LIMIT LIMIT_MAKER MARKET STOP_LOSS STOP_LOSS_LIMIT TAKE_PROFIT TAKE_PROFIT_LIMIT"
      ],
      "icebergAllowed": true,
      "ocoAllowed": true,
      "otoAllowed": true,
      "opoAllowed": true,
      "quoteOrderQtyMarketAllowed": true,
      "allowTrailingStop": false,
      "cancelReplaceAllowed": false,
      "amendAllowed": false,
      "pegInstructionsAllowed": true,
      "isSpotTradingAllowed": true,
      "isMarginTradingAllowed": true,
      "filters": [],
      "permissions": [],
      "permissionSets": [
        [
          "SPOT",
          "MARGIN"
        ]
      ],
      "defaultSelfTradePreventionMode": "NONE",
      "allowedSelfTradePreventionModes": [
        "NONE"
      ]
    }
  ]
}
     * @param t 
     * @returns 
     */
    public async exchangeInfo(t: tradeType) {
        if (this.exchangeinfoData[t]) return this.exchangeinfoData[t];
        let url = t === 'spot' ? '/api/v3/exchangeInfo' : '';
        const resp = await this.httpRequest(url, 'GET', t);
        this.exchangeinfoData[t] = resp;
        return resp as {
            serverTime: number, rateLimits: object[],
            symbols: { symbol: string, status: string }[]
        };
    }

    // 数据顺序：开盘时间，开，高，低，收，成交量，收盘时间，成交额，成交笔，taker量，taker额，ignore
    public async historyKline(symbol: string, interval: binanceInterval, s: number, e: number, t: tradeType): Promise<(number | string)[][]> {
        let url = t === 'spot' ? '/api/v3/klines' : '/fapi/v1/klines';
        const resp = await this.httpRequest(url, 'GET', t, false, { "symbol": symbol, "interval": interval, "startTime": s, "endTime": e });
        if (resp) return resp as (number | string)[][];
        return [];
    }

    // ============= ws =====================

    public connect(t: tradeType, wst: 'stream' | 'ws'): Promise<void> {
        if (this.conns[wst][t] !== null && this.conns[wst][t].readyState === WebSocket.OPEN) {
            return Promise.resolve();
        }
        const conn = new WebSocket(Binance.urls[wst][t]);
        conn.onmessage = this.handleWs.bind(this, t, wst);
        this.conns[wst][t] = conn;
        return new Promise((resolve, reject) => {
            conn.onopen = () => resolve();
            conn.onerror = (e) => {
                ElMessage({ type: 'error', message: `WebSocket 连接失败` });
                reject(e);
            };
        });
    }

    public disconnect(t: tradeType, wst: 'stream' | 'ws') {
        if (this.conns[wst][t] !== null) {
            this.conns[wst][t].close();
            this.conns[wst][t] = null;
        }
    }

    private async handleWs(t: tradeType, wst: 'stream' | 'ws', event: MessageEvent) {
        if (event.data === 'ping') {
            this.conns[wst][t]?.send('pong');
            return;
        }
        const data: eventPaload | wsResponse = JSON.parse(event.data);
        // 处理ws响应报文
        if ('id' in data) {
            const cb = this.wsRespHandle.get(data.id);
            this.wsRespHandle.delete(data.id);
            if (cb) cb(data);
            return;
        }

        const handle = this.wsEventHandle.get(data.stream);
        if (handle) {
            handle(data.data);
        }
    }

    private async send(t: tradeType, wst: 'stream' | 'ws', payload: wsPayload, cb?: wsCallback) {
        if (this.conns[wst][t] === null || this.conns[wst][t].readyState !== WebSocket.OPEN) { ElMessage({ type: "error", message: "链接未建立" }); return };
        this.conns[wst][t].send(JSON.stringify(payload));
        if (cb) {
            this.wsRespHandle.set(payload.id, cb);
        }
    }

    public async subscribeKline(key: string, t: tradeType = 'spot', handle: wsEventCallback, cb?: wsCallback) {
        await this.connect(t, 'stream');
        await this.send(t, 'stream', { id: uuidv4(), method: "SUBSCRIBE", params: [key] }, (data: wsResponse) => {
            if (cb) cb(data);
            if (data.status === undefined || data.status === 200) {
                this.wsEventHandle.set(key, handle);
                return;
            }
        });

    }

    public async unsubscribe(keys: string[], t: tradeType) {
        if (keys.length === 0) return;
        await this.send(t, 'stream', { id: uuidv4(), method: "UNSUBSCRIBE", params: keys });
    }
}