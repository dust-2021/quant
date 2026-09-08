from cores.exchange.binance.base import Interface
import typing as t

class BalanceResp(t.TypedDict):
    """
    
    """
    accountAlias: str
    asset: str # 资金币种
    balance: str
    crossWalletBalance: str
    crossUnPnl: str
    availableBalance: str # 可用资金
    maxWithdrawAmount: str # 可划转资金
    marginAvailable: bool
    updateTime: int

class Balance(Interface[list[BalanceResp]]):
    """
    合约资产信息
    """
    url = '/fapi/v2/balance'
    _ip_weight = 5
    sign = True
    market_type = 'futures.um'

    def __init__(self):
        pass

    async def data(self, *args: t.Any, **kwargs: t.Any) -> dict[str, t.Any]:
        return {}

    async def parse(self, data: t.Any) -> list[BalanceResp]:
        return t.cast(list[BalanceResp], data)