import asyncio
import base64
import hashlib
import hmac
import time
import typing as t

import aiohttp
from loguru import logger

from utils.cache import get_cache
from utils.types import CacheName
from cores.exchange.binance.base import Interface, MARKET_TYPE
from cores.exchange.binance.api.basic.exchange_info import ExchangeInfo, ExchangeInfoData, ExchangeInfoFutures, SymbolInfo, SymbolLotSizeFilter, SymbolMinNotionalFilter, SymbolNotionalFilter, SymbolPriceFilter

request_T = t.TypeVar('request_T')


class Binance:
    base_url: t.Mapping[MARKET_TYPE, str] = {
        "spot": "https://api.binance.com",
        "futures.um": "https://fapi.binance.com",
        "futures.cm": "https://dapi.binance.com",
    }
    ip_weight_cost: int = 0

    def __init__(self, api_key: str, api_secret: str = '', 
                 encrypt_t: t.Literal['hmac', 'ed25519', 'rsa'] = 'hmac') -> None:
        self.api_key = api_key
        self.api_secret = api_secret
        self.encrypt_t = encrypt_t
        self.session = aiohttp.ClientSession(headers={"X-MBX-APIKEY": self.api_key} if self.api_key else {})
        self.uid_weight_cost: int = 0

    def _sign(self, msg: str) -> str:
        if self.encrypt_t == 'hmac':
            return hmac.new(
                self.api_secret.encode(), msg.encode(), digestmod=hashlib.sha256
            ).hexdigest()
        if self.encrypt_t == 'ed25519':
            return self._sign_ed25519(msg)
        if self.encrypt_t == 'rsa':
            return self._sign_rsa(msg)
        raise ValueError(f'unsupported encrypt type: {self.encrypt_t}')

    def _sign_ed25519(self, msg: str) -> str:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        private_key = Ed25519PrivateKey.from_private_bytes(base64.b64decode(self.api_secret))
        return base64.b64encode(private_key.sign(msg.encode())).decode()

    def _sign_rsa(self, msg: str) -> str:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
        private_key = t.cast(
            RSAPrivateKey,
            serialization.load_pem_private_key(self.api_secret.encode(), password=None),
        )
        signature = private_key.sign(msg.encode(), padding.PKCS1v15(), hashes.SHA256())
        return base64.b64encode(signature).decode()

    def _formatter(self, data: dict[str, t.Any], sign: bool = False) -> str:
        if sign and self.api_key == '':
            raise ValueError('binance without api key')
        if sign:
            data['recvWindow'] = 5000
            data['timestamp'] = int(time.time()) * 1000
        if len(data) == 0:
            return ""
        query = '&'.join([f'{k}={v}' for k, v in data.items()])
        if not sign:
            return f'?{query}'
        return f"?{query}&signature={self._sign(query)}"
        

    async def request(
        self, interface: Interface[request_T]
    ) -> tuple[bool, request_T]:
        if interface.sign and self.api_key == '':
            raise ValueError('binance without api key')
        
        self.session.headers.update({"X-MBX-APIKEY": self.api_key} if self.api_key else {})
        url = f"{self.base_url[interface.market_type]}{interface.url}{self._formatter(await interface.data(self), interface.sign)}"
        ip_w, uid_w = interface.weight()
        self.ip_weight_cost += ip_w
        self.uid_weight_cost += uid_w
        if self.uid_weight_cost > 6000 or self.ip_weight_cost > 1200:
            logger.warning(f"Binance API weight limit exceeded: uid_weight_cost={self.uid_weight_cost}, ip_weight_cost={self.ip_weight_cost}")
        resp = await self.session.request(interface.method, url)
        self._update_api_limit_cache(interface.market_type, resp)
        if resp.status != 200:
            # TODO: 超过ip频率限制
            if resp.status == 429 or resp.status == 418:
                pass
            logger.error(f"Binance API request failed for {interface.url}: {resp.status} {await resp.text()}")
            return False, t.cast(request_T, {})
        data = await resp.json()
        interface.log(data)
        return True, await interface.parse(data)

    def _update_api_limit_cache(self, market_type: MARKET_TYPE, resp: aiohttp.ClientResponse) -> None:
        """把响应头中的限频用量写入缓存（JSON 格式，key: Binance_Api_Limit::{market_type}）。"""
        try:
            data = {
                'usedWeight1m': resp.headers.get('X-MBX-USED-WEIGHT-1M'),
                'orderCount10s': resp.headers.get('X-MBX-ORDER-COUNT-10S'),
                'orderCount1m': resp.headers.get('X-MBX-ORDER-COUNT-1M'),
            }
            data = {k: (int(v) if v is not None else None) for k, v in data.items()}
            if all(v is None for v in data.values()):
                return
            key = f'{CacheName.Binance_Api_Limit.value}::{market_type}'
            get_cache().set(key, data)
        except Exception:  # noqa: BLE001
            pass
    
    async def requests(
        self, interfaces: list[Interface[request_T]]
    ) -> list[tuple[bool, request_T]]:
        tasks = [self.request(interface) for interface in interfaces]
        return await asyncio.gather(*tasks)

    
    
    async def exchange_info(self) -> ExchangeInfoData:
        info: ExchangeInfoData | None = get_cache().get(CacheName.Binance_ExchangeInfo.value)
        if info is None:
            f, new_info = await self.request(ExchangeInfo())
            if not f:
                logger.error("Failed to fetch Binance exchange info")
                raise ValueError("Failed to fetch Binance exchange info")
            get_cache().set(CacheName.Binance_ExchangeInfo.value, new_info)
            logger.info("Binance exchange info cached")
            return new_info
        return info
    
    async def exchange_info_futures(self) -> ExchangeInfoData:
        info: ExchangeInfoData | None = get_cache().get(CacheName.Binance_ExchangeInfo_Future.value)
        if info is None:
            f, new_info = await self.request(ExchangeInfoFutures())
            if not f:
                logger.error("Failed to fetch Binance futures exchange info")
                raise ValueError("Failed to fetch Binance futures exchange info")
            get_cache().set(CacheName.Binance_ExchangeInfo_Future.value, new_info)
            logger.info("Binance futures exchange info cached")
            return new_info
        return info

    async def symbol_info(self, symbol: str = "BTCUSDT") -> SymbolInfo:
        info = await self.exchange_info()
        symbols = info["symbols"]
        for item in symbols:
            if item["symbol"] == symbol:
                return item
        else:
            raise ValueError(f"Binance exchange info does not contain {symbol} symbol")
        
    async def symbol_info_futures(self, symbol: str = "BTCUSDT") -> SymbolInfo:
        info = await self.exchange_info_futures()
        symbols = info["symbols"]
        for item in symbols:
            if item["symbol"] == symbol:
                return item
        else:
            raise ValueError(f"Binance futures exchange info does not contain {symbol} symbol")