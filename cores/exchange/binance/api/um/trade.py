from __future__ import annotations

from cores.exchange.binance.base import Interface
from cores.exchange.binance.api import SymbolLotSizeFilter, SymbolMinNotionalFilter, SymbolPriceFilter

import decimal
import typing as t

if t.TYPE_CHECKING:
    from cores.exchange.binance.binance import Binance


class UMTrade(Interface[dict[str, t.Any]]):
    """
    下单接口
    """
    url = "/fapi/v1/order"
    method = "POST"
    sign = True
    market_type = "futures.um"

    def __init__(self, symbol: str, side: t.Literal["BUY", "SELL"], quantity: float, price: float | None = None,
                 order_uid: str | None = None):
        self.symbol = symbol
        self.side = side
        self.type_ = "MARKET"  # Default to MARKET order
        self.quantity = decimal.Decimal(str(quantity))
        self.price = decimal.Decimal(str(price)) if price is not None else None
        if order_uid and len(order_uid) > 36:
            raise 
        self.order_uid = order_uid

    async def data(self, binance: Binance) -> dict[str, t.Any]:
        infos = await binance.symbol_info_futures(self.symbol)
        for filter in infos["filters"]:
            if filter["filterType"] == "LOT_SIZE":
                filter = t.cast(SymbolLotSizeFilter, filter)
                step_size = decimal.Decimal(filter["stepSize"])
                self.quantity = self.quantity // step_size * step_size
                if self.quantity < decimal.Decimal(filter["minQty"]) or self.quantity > decimal.Decimal(filter["maxQty"]):
                    raise ValueError("Order quantity is out of range")

            if filter["filterType"] == "PRICE_FILTER" and self.price is not None:
                filter = t.cast(SymbolPriceFilter, filter)
                tick_size = decimal.Decimal(filter["tickSize"])
                if self.price is not None:
                    self.price = self.price // tick_size * tick_size
            elif filter["filterType"] == "MIN_NOTIONAL" and self.price is not None: # 合约名义值过滤器
                filter = t.cast(SymbolMinNotionalFilter, filter)
                min_notional = decimal.Decimal(filter["minNotional"])
                if self.quantity * self.price < min_notional:
                    raise ValueError("Order quantity is too small")
        data = {
            "symbol": self.symbol,
            "side": self.side,
            "type": self.type_,
            "quantity": self.quantity.__str__(),
        }
        if self.price is not None:
            data["type"] = "LIMIT"
            data["price"] = self.price.__str__()
        if self.order_uid is not None:
            data["newClientOrderId"] = self.order_uid
        return data