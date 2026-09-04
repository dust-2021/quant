from cores.exchange.binance.base import Interface
import typing as t

class SetLeverage(Interface[bool]):
    """
    设置杠杆倍数
    """
    _ip_weight = 1
    _uid_weight = 1
    url = "/fapi/v1/leverage"
    method = "POST"
    sign = True
    market_type = "futures.um"

    def __init__(self, symbol: str, leverage: int):
        self.symbol = symbol
        self.leverage = leverage

    async def data(self) -> dict[str, t.Any]:
        return {
            "symbol": self.symbol,
            "leverage": self.leverage
        }

    async def parse(self, data: t.Any) -> bool:
        return data.get("leverage", 0) == self.leverage