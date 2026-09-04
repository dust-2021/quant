from cores.exchange.binance.api.basic.exchange_info import Interface


import typing as t


class BNBBurn(Interface[bool]):
    """
    bnb抵扣手续费
    """
    _ip_weight = 30
    url = "/fapi/v1/feeBurn"
    method = "GET"
    sign = True
    market_type = "futures.um"

    def __init__(self, fee_burn: bool):
        self.fee_burn = fee_burn

    async def data(self) -> dict[str, t.Any]:
        return {
        }

    async def parse(self, data: t.Any) -> bool:
        return data.get("feeBurn", False)

class SetBNBBurn(Interface[bool]):
    """
    设置bnb抵扣手续费
    """
    ip_weight = 1
    url = "/fapi/v1/feeBurn"
    method = "POST"
    sign = True
    market_type = "futures.um"

    def __init__(self, fee_burn: bool):
        self.fee_burn = fee_burn

    async def data(self) -> dict[str, t.Any]:
        return {
            "feeBurn": str(self.fee_burn).lower()
        }

    async def parse(self, data: t.Any) -> bool:
        return data.get("feeBurn", False)