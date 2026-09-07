from cores.exchange.binance.base import Interface
import typing as t

from loguru import logger

class Kline(Interface[list[list[t.Any]]]):
    """
    获取K线数据
    """
    _ip_weight = 10
    url = "/fapi/v1/klines"
    method = "GET"
    sign = False
    market_type = "futures.um"

    def __init__(self, symbol: str, 
                 interval: t.Literal["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M"], 
                 start_time: int | None = None, end_time: int | None = None, 
                 limit: int  = 500):
        self.symbol = symbol
        self.interval = interval
        self.start_time = start_time
        self.end_time = end_time
        self.limit = limit

    async def data(self, *args: t.Any, **kwargs: t.Any) -> dict[str, t.Any]:
        data: dict[str, t.Any] = {
            "symbol": self.symbol,
            "interval": self.interval,
        }
        if self.start_time is not None:
            data["startTime"] = self.start_time
        if self.end_time is not None:
            data["endTime"] = self.end_time
        if self.limit is not None:
            data["limit"] = self.limit
        return data

    async def parse(self, data: t.Any) -> list[list[t.Any]]:
        return data

    def log(self, info: t.Any) -> None:
        """K 线返回数据量大，仅记录条数，不打印原始数据。"""
        count = len(info) if isinstance(info, list) else '?'
        logger.log(
            'INFO',
            f'binance api: {self.url}, symbol: {self.symbol}, bars: {count}, '
            f'weight cost: ip-{self._ip_weight}, uid-{self._uid_weight}',
        )