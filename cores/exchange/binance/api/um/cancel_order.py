from cores.exchange.binance.base import Interface, MARKET_TYPE
import typing as t

class CancelOrder(Interface[bool]):
    """
    取消订单接口
    """
    ip_weight = 1
    url = "/papi/v1/um/allOpenOrders"
    method = "DELETE"
    sign = True
    market_type = "futures.um"

    def __init__(self, symbol: str, order_id: int):
        self.symbol = symbol
        self.order_id = order_id

    async def data(self) -> dict[str, t.Any]:
        return {
            "symbol": self.symbol,
            "orderId": self.order_id
        }

    async def parse(self, data: t.Any) -> bool:
        return data.get("status", "") == "CANCELED"