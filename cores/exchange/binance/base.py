import typing as t

MARKET_TYPE = t.Literal["spot", "futures.um", "futures.cm"]

result_T = t.TypeVar('result_T', bound=t.Any)

class Interface(t.Generic[result_T]):
    
    url: str
    ip_weight: int = 0
    uid_weight: int = 0
    method: t.Literal["GET", "POST", "DELETE", "PUT"] = "GET"
    sign: bool = False
    market_type: MARKET_TYPE = "spot"

    def __init__(self):
        raise NotImplementedError("this is an abstract class, please implement it in subclass")
    
    async def data(self, *args, **kwargs) -> dict[str, t.Any]:
        """
        请求数据
        """
        return {}
    
    async def parse(self, data: t.Any) -> result_T:
        """
        解析返回数据
        """
        return data
