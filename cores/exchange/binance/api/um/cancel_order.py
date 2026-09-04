from cores.exchange.binance.base import Interface, MARKET_TYPE
import typing as t

class CancelOrder(Interface[bool]):
    """
    取消全部订单接口
    """
    _ip_weight = 1
    url = "/fapi/v1/allOpenOrders"
    method = "DELETE"
    sign = True
    market_type = "futures.um"

    def __init__(self):
        pass

    async def parse(self, data: t.Any) -> bool:
        return data.get("status", "") == "CANCELED"