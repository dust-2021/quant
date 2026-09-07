from cores.exchange.binance.base import Interface
import typing as t

class GetPositionSide(Interface[bool]):
    
    url = '/fapi/v1/positionSide/dual'
    sign = True
    method = 'GET'
    market_type = 'futures.um'
    _ip_weight = 30
    
    def __init__(self):
        pass
        
    async def data(self, *args: t.Any, **kwargs: t.Any):
        return {}
    
    
    async def parse(self, data: t.Any):
        return data.get('dualSidePosition', False)

class SetPositionSide(Interface[None]):
    """
    设置合约持仓方向： "true": 双向持仓模式；"false": 单向持仓模式
    """
    url = '/fapi/v1/positionSide/dual'
    sign = True
    method = 'POST'
    market_type = 'futures.um'
    _ip_weight = 1
    
    def __init__(self, to: t.Literal['true', 'false']):
        self.to = to
        
    
    async def data(self, *args: t.Any, **kwargs: t.Any):
        return {'dualSidePosition': self.to}
    
    
    async def parse(self, data: t.Any):
        return None