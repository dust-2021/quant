import decimal
import typing as t

import numpy as np
import pandas as pd
from loguru import logger

from cores.exchange import Binance, BinaceApi
from database.model import Account
from utils.types import ContextBase


def _calc_market_quantity(
    info: BinaceApi.SymbolInfo,
    notional: decimal.Decimal,
    price: decimal.Decimal,
) -> decimal.Decimal:
    """按合约 LOT_SIZE 规则，用 decimal 计算市价单数量（向下取整到 stepSize）。"""
    for f in info["filters"]:
        if f["filterType"] != "LOT_SIZE":
            continue
        f = t.cast(BinaceApi.SymbolLotSizeFilter, f)
        step = decimal.Decimal(str(f["stepSize"]))
        min_q = decimal.Decimal(str(f["minQty"]))
        max_q = decimal.Decimal(str(f["maxQty"]))
        qty = (notional / price) // step * step
        if qty < min_q:
            raise ValueError(f"计算数量 {qty} 小于最小数量 {min_q}")
        return min(qty, max_q)
    raise ValueError(f"symbol {info['symbol']} 缺少 LOT_SIZE 规则")


def extract_signals(data: pd.DataFrame, signal_name: str) -> list[dict[str, t.Any]]:
    """从带信号列的 DataFrame 中整理各标的最新信号。"""
    signals: list[dict[str, t.Any]] = []
    if data is None or data.empty:
        return signals
    for code, group in data.groupby('code', sort=False):
        group = group.sort_values('open_time')
        last = group.iloc[-1]
        sig = last.get(signal_name, np.nan)
        signals.append({
            'target': code,
            'open_time': int(last['open_time']),
            'close': float(last['close']),
            'signal': None if pd.isna(sig) else float(sig),
        })
    return signals


class TraderInterface:
    """交易执行器接口"""

    name: t.ClassVar[str] = '交易执行器'
    description: t.ClassVar[str] = ''

    def __init__(self, account: Account):
        raise NotImplementedError('this is an abstract class')

    async def check(self) -> bool:
        """执行交易前的检查工作（权限、持仓方向、仓位等）"""
        return False

    async def trade(self, data: pd.DataFrame, ctx: ContextBase, params: dict[str, t.Any]) -> list[t.Any]:
        """整理 DataFrame 信号并执行交易，返回订单列表"""
        return []


class BaseTrader(TraderInterface):
    name = 'default'
    description = '默认执行器：单标的、1倍杠杆，按USDT 95%市价开/补仓，反向先平仓'

    def __init__(self, account: Account):
        self.account = account
        self._order_counter = 0

    def _binance(self) -> Binance:
        encrypt_t = t.cast(t.Literal['hmac', 'ed25519', 'rsa'], self.account.encrypt_type or 'hmac')
        return Binance(
            t.cast(str, self.account.api_key),
            t.cast(str, self.account.api_secret),
            encrypt_t,
        )
        
    def _orderid(self, ctx: ContextBase) -> str:
        """生成唯一订单 id（36 位，满足币安 newClientOrderId ≤ 36 位限制）。

        结构（共 36 位，含 3 个分隔短横线）：
          [0:7]    账号 id，7 位十进制（取后 7 位，左补 0）
          [7]      分隔符 '-'
          [8:16]   策略 uuid 前 8 位（不哈希，便于与策略对照）
          [16]     分隔符 '-'
          [17:28]  严格执行时间整除周期的序列值，11 位（取后 11 位，左补 0）
          [28]     分隔符 '-'
          [29:36]  订单计数器，7 位十进制（绑定 trader 对象，每次下单自增）
        """
        account_part = f"{t.cast(int, self.account.id) % 10 ** 7:07d}"
        strategy_part = str(ctx.get('strategy_uuid') or '')[:8].ljust(8, '0')
        e_time = int(ctx.get('excute_strict_time') or 0)
        period = int(ctx.get('period') or 1)
        time_part = str(e_time // period)[-11:].rjust(11, '0')
        self._order_counter += 1
        counter_part = f"{self._order_counter % 10 ** 7:07d}"
        return f"{account_part}-{strategy_part}-{time_part}-{counter_part}"

    async def check(self) -> bool:
        b = self._binance()
        try:
            # 1. 权限检查
            ok, perm = await b.request(BinaceApi.ApiPermission())
            if not ok:
                return False
            if not (perm.get('enableFutures')
                    and perm.get('enableSpotAndMarginTrading')
                    and perm.get('permitsUniversalTransfer')):
                return False
            return True
        finally:
            await b.session.close()
            

    async def trade(self, data: pd.DataFrame, ctx: ContextBase, params: dict[str, t.Any]) -> list[t.Any]:
        signal_name = str(params.get('signal_name', 'signal'))
        signals = extract_signals(data, signal_name)
        # 默认执行器只支持单个标的的信号
        if len(signals) > 1:
            raise ValueError(f"默认交易执行器只允许一个标的的信号，当前收到 {len(signals)} 个")
        if not signals:
            return []

        sig = signals[0]
        signal = sig.get('signal')
        if signal is None:
            logger.info(f"trade: account {t.cast(str, self.account.name)} 信号为维持，跳过")
            return []
        signal_val = int(signal)
        symbol = str(sig['target'])
        price = decimal.Decimal(str(sig.get('close') or 0))
        if price <= 0:
            raise ValueError(f"{symbol} 无有效价格")

        b = self._binance()
        leverage = int(params.get('leverage') or 1)
        orders: list[t.Any] = []
        try:
            # 1. 查询交易对信息
            info = await b.symbol_info_futures(symbol)

            # 2. 查询当前持仓方向
            ok, pos_list = await b.request(BinaceApi.PositionRisk(symbol))
            if not ok:
                raise ValueError(f"{symbol} 查询持仓失败")
            pos_amt = decimal.Decimal(0)
            for p in pos_list:
                if p.get('symbol') == symbol:
                    pos_amt = decimal.Decimal(str(p.get('positionAmt', '0')))
                    break
            pos_dir = 1 if pos_amt > 0 else (-1 if pos_amt < 0 else 0)
            side: t.Literal['BUY', 'SELL'] = 'BUY' if signal_val > 0 else 'SELL'

            # 3. 平仓信号
            if signal_val == 0:
                if pos_amt == 0:
                    logger.info(f"{symbol} 无持仓，无需平仓")
                    return orders
                close_side: t.Literal['BUY', 'SELL'] = 'SELL' if pos_amt > 0 else 'BUY'
                return await self._close(b, symbol, close_side, abs(pos_amt), ctx)

            # 4. 信号反向 → 先平仓、再开仓（两步操作）
            if pos_dir != 0 and pos_dir != signal_val:
                close_side: t.Literal['BUY', 'SELL'] = 'SELL' if pos_dir > 0 else 'BUY'
                orders += await self._close(b, symbol, close_side, abs(pos_amt), ctx)
                orders += await self._open(b, info, symbol, side, price, ctx, leverage)
                return orders

            # 5. 无持仓 → 开仓；同向 → 补仓
            if pos_dir == 0:
                orders += await self._open(b, info, symbol, side, price, ctx, leverage)
            else:
                orders += await self._add(b, info, symbol, side, price, ctx)
            return orders
        finally:
            await b.session.close()

    async def _calc_market_quantity_by_usdt(
        self, b: Binance, info: BinaceApi.SymbolInfo, symbol: str, price: decimal.Decimal,
    ) -> decimal.Decimal | None:
        """查询 USDT 可用资金，按 95% 计算市价数量；余额不足返回 None。"""
        ok, balances = await b.request(BinaceApi.Balance())
        if not ok:
            raise ValueError(f"{symbol} 查询资产失败")
        usdt = decimal.Decimal(0)
        for bal in balances:
            if bal.get('asset') == 'USDT':
                usdt = decimal.Decimal(str(bal.get('availableBalance', '0')))
                break
        notional = usdt * decimal.Decimal('0.95')
        if notional <= 0:
            return None
        return _calc_market_quantity(info, notional, price)

    async def _ensure_open_ready(self, b: Binance, symbol: str, leverage: int) -> None:
        """开仓前准备：设置杠杆，并确保单向持仓模式。"""
        ok, _ = await b.request(BinaceApi.SetLeverage(symbol, leverage))
        if not ok:
            logger.warning(f"{symbol} 设置杠杆为 {leverage} 失败")

        ok, dual = await b.request(BinaceApi.GetPositionSide())
        if not ok:
            raise ValueError(f"{symbol} 获取持仓方向失败")
        if dual:
            ok, _ = await b.request(BinaceApi.SetPositionSide('false'))
            if not ok:
                raise ValueError(f"{symbol} 设置单向持仓失败")

    async def _open(
        self, b: Binance, info: BinaceApi.SymbolInfo, symbol: str,
        side: t.Literal['BUY', 'SELL'], price: decimal.Decimal, ctx: ContextBase,
        leverage: int = 1,
    ) -> list[t.Any]:
        """开仓：无持仓时按 USDT 可用资金 95% 市价建仓。"""
        await self._ensure_open_ready(b, symbol, leverage)
        qty = await self._calc_market_quantity_by_usdt(b, info, symbol, price)
        if qty is None:
            logger.warning(f"{symbol} USDT 可用余额不足，跳过开仓")
            return []
        ok, resp = await b.request(BinaceApi.UMTrade(symbol, side, float(qty), order_uid=self._orderid(ctx)))
        if not ok:
            raise ValueError(f"{symbol} 开仓失败: {resp}")
        logger.info(f"trade 开仓: {symbol} {side} qty={qty} (名义 {qty * price})")
        return [{'symbol': symbol, 'side': side, 'quantity': float(qty), 'order': resp, 'action': 'open'}]

    async def _close(
        self, b: Binance, symbol: str, side: t.Literal['BUY', 'SELL'],
        qty: decimal.Decimal, ctx: ContextBase,
    ) -> list[t.Any]:
        """平仓：按给定方向市价平掉指定数量。"""
        if qty <= 0:
            return []
        ok, resp = await b.request(BinaceApi.UMTrade(symbol, side, float(qty), order_uid=self._orderid(ctx)))
        if not ok:
            raise ValueError(f"{symbol} 平仓失败: {resp}")
        logger.info(f"trade 平仓: {symbol} {side} qty={qty}")
        return [{'symbol': symbol, 'side': side, 'quantity': float(qty), 'order': resp, 'action': 'close'}]

    async def _add(
        self, b: Binance, info: BinaceApi.SymbolInfo, symbol: str,
        side: t.Literal['BUY', 'SELL'], price: decimal.Decimal, ctx: ContextBase,
    ) -> list[t.Any]:
        """补仓：同向已有持仓时按 USDT 可用资金 95% 市价加仓。"""
        qty = await self._calc_market_quantity_by_usdt(b, info, symbol, price)
        if qty is None:
            logger.warning(f"{symbol} USDT 可用余额不足，跳过补仓")
            return []
        ok, resp = await b.request(BinaceApi.UMTrade(symbol, side, float(qty), order_uid=self._orderid(ctx)))
        if not ok:
            raise ValueError(f"{symbol} 补仓失败: {resp}")
        logger.info(f"trade 补仓: {symbol} {side} qty={qty} (名义 {qty * price})")
        return [{'symbol': symbol, 'side': side, 'quantity': float(qty), 'order': resp, 'action': 'add'}]
    
    
    def split_order(self):
        pass