import typing as t
from cores.exchange.binance.base import Interface, MARKET_TYPE

    
class SymbolPriceFilter(t.TypedDict):
    """价格过滤器"""
    filterType: t.Literal["PRICE_FILTER"]
    minPrice: str
    maxPrice: str
    tickSize: str

class SymbolLotSizeFilter(t.TypedDict):
    """交易量过滤器"""
    filterType: t.Literal["LOT_SIZE"]
    minQty: str
    maxQty: str
    stepSize: str
    
class SymbolNotionalFilter(t.TypedDict):
    """现货名义值过滤器"""
    filterType: t.Literal["NOTIONAL"]
    minNotional: str
    maxNotional: str

class SymbolMinNotionalFilter(t.TypedDict):
    """期货名义值过滤器"""
    filterType: t.Literal["MIN_NOTIONAL"]
    minNotional: str
    applyToMarket: bool
    avgPriceMins: int
    
class SymbolInfo(t.TypedDict):
    
    symbol: str
    status: str
    baseAsset: str
    baseAssetPrecision: int
    quoteAsset: str
    quoteAssetPrecision: int
    filters: list[SymbolPriceFilter | SymbolLotSizeFilter | SymbolNotionalFilter | SymbolMinNotionalFilter | dict[str, t.Any]]
    
class ExchangeInfoData(t.TypedDict):

    timezone: str
    serverTime: int
    rateLimits: list[dict[str, t.Any]]
    exchangeFilters: list[dict[str, t.Any]]
    symbols: list[SymbolInfo]
    
class ExchangeInfo(Interface[ExchangeInfoData]):
    """
    获取交易所信息接口
    """
    url = "/api/v3/exchangeInfo"
    method = "GET"
    sign = False
    market_type = "spot"
    ip_weight = 20

    def __init__(self):
        pass

    async def data(self, *args: t.Any, **kwargs: t.Any) -> dict[str, t.Any]:
        return {}
    
    async def parse(self, data: t.Any) -> ExchangeInfoData:
        return t.cast(ExchangeInfoData, data)
    
    
    def log(self, info: t.Any) -> None:
        return super().log('exchange info update')

class ExchangeInfoFutures(Interface[ExchangeInfoData]):
    """
    获取期货交易所信息接口
    """
    url = "/fapi/v1/exchangeInfo"
    method = "GET"
    sign = False
    market_type = "futures.um"
    ip_weight = 20

    def __init__(self):
        pass

    async def data(self, *args: t.Any, **kwargs: t.Any) -> dict[str, t.Any]:
        return {}
    
    async def parse(self, data: t.Any) -> ExchangeInfoData:
        return t.cast(ExchangeInfoData, data)
    
    
    def log(self, info: t.Any) -> None:
        return super().log('exchange info future update')