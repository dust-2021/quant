from cores.exchange.binance.base import Interface
import typing as t


class PositionResp(t.TypedDict):
    """合约持仓信息"""
    symbol: str
    positionSide: str
    positionAmt: str
    entryPrice: str
    breakEvenPrice: str
    markPrice: str
    unRealizedProfit: str
    liquidationPrice: str
    isolatedMargin: str
    notional: str
    marginType: str
    isolatedWallet: str
    isAutoAddMargin: str
    leverage: str
    maxNotionalValue: str
    updateTime: int


class PositionRisk(Interface[list[PositionResp]]):
    """获取当前账户的持仓信息。"""
    url = '/fapi/v2/positionRisk'
    _ip_weight = 5
    sign = True
    market_type = 'futures.um'

    def __init__(self, symbol: str | None = None) -> None:
        self.symbol = symbol

    async def data(self, *args: t.Any, **kwargs: t.Any) -> dict[str, t.Any]:
        if self.symbol:
            return {'symbol': self.symbol}
        return {}

    async def parse(self, data: t.Any) -> list[PositionResp]:
        return t.cast(list[PositionResp], data)