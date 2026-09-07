import typing as t
from cores.exchange.binance.base import Interface, MARKET_TYPE


class Resp(t.TypedDict):
    """API Key 权限响应"""
    ipRestrict: bool
    createTime: int
    enableWithdrawals: bool
    enableInternalTransfer: bool
    permitsUniversalTransfer: bool
    enableVanillaOptions: bool
    enableReading: bool
    enableFutures: bool
    enableMargin: bool
    enableSpotAndMarginTrading: bool
    tradingAuthorityExpirationTime: int


class ApiPermission(Interface[Resp]):
    """
    apikey 拥有的权限
    """
    url = "/sapi/v1/account/apiRestrictions"
    method = "GET"
    sign = True
    market_type = "spot"
    _ip_weight = 1

    def __init__(self):
        pass

    async def data(self, *args: t.Any, **kwargs: t.Any) -> dict[str, t.Any]:
        return {}

    async def parse(self, data: t.Any) -> Resp:
        return t.cast(Resp, data)