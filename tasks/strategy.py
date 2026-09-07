import asyncio
import decimal
import json
import typing as t

from celery import Task, chord
from loguru import logger
from sqlalchemy import select

from cores.exchange import Binance
from cores.exchange.binance.api.basic.api_permission import ApiPermission
from cores.exchange.binance.api.basic.exchange_info import SymbolInfo, SymbolLotSizeFilter
from cores.exchange.binance.api.um.balance import Balance
from cores.exchange.binance.api.um.leverage import SetLeverage
from cores.exchange.binance.api.um.position import PositionRisk
from cores.exchange.binance.api.um.position_side import GetPositionSide, SetPositionSide
from cores.exchange.binance.api.um.trade import UMTrade
from cores.executor.calculator import Calculator
from database.base import DataPeriod, async_session
from database.model import Account, SignalRecord
from task import app


@app.task
def check(account_id: int) -> int:
    """校验账户 API 权限、设置单向持仓、获取合约仓位。"""

    async def func():
        async with async_session() as s:
            acc = (await s.execute(select(Account).filter_by(id=account_id))).scalar()
        if acc is None:
            raise ValueError(f"account {account_id} not found")
        exchange = t.cast(str, acc.exchange)
        if exchange != 'binance':
            raise ValueError(f"unsupported exchange: {exchange}")

        encrypt_t = t.cast(t.Literal['hmac', 'ed25519', 'rsa'], acc.encrypt_type or 'hmac')
        b = Binance(t.cast(str, acc.api_key), t.cast(str, acc.api_secret), encrypt_t)
        try:
            # 1. 权限检查
            ok, perm = await b.request(ApiPermission())
            if not ok:
                raise ValueError("api key 权限检查请求失败")
            if not (perm.get('enableFutures') and perm.get('enableReading')):
                raise ValueError("api key 缺少合约或读取权限")

            # 2. 持仓方向检查并设置为单向
            ok, dual = await b.request(GetPositionSide())
            if not ok:
                raise ValueError("获取持仓方向失败")
            if dual:
                ok, _ = await b.request(SetPositionSide('false'))
                if not ok:
                    raise ValueError("设置单向持仓失败")

            # 3. 合约仓位获取
            ok, positions = await b.request(PositionRisk())
            if not ok:
                raise ValueError("获取合约仓位失败")
            logger.info(f"check account {t.cast(str, acc.name)} ok, positions={len(positions)}")
        finally:
            await b.session.close()
        return account_id

    return asyncio.run(func())


@app.task
def run_one(account_id: int, e_time: int, p: DataPeriod):
    """执行单个账户绑定的策略（实盘）。"""

    async def func():
        async with async_session() as s:
            acc = (await s.execute(select(Account).filter_by(id=account_id))).scalar()
        if acc is None:
            logger.warning(f"account {account_id} not found, skip")
            return None
        strategy_uuid = t.cast(str | None, acc.strategy_uuid)
        if not strategy_uuid:
            logger.warning(f"account {t.cast(str, acc.name)} has no strategy bound, skip")
            return None
        target_raw = t.cast(str, acc.target)
        targets = json.loads(target_raw) if target_raw else []
        exchange = t.cast(str, acc.exchange)
        signals = await Calculator.living_run(strategy_uuid, exchange, targets, p, e_time)

        # 记录信号
        trader_id = t.cast(int | None, acc.trader_id)
        records = [
            SignalRecord(
                exchange=exchange,
                account_id=account_id,
                strategy_uuid=strategy_uuid,
                period=p.value,
                target=str(sig.get('target')),
                excute_strict_time=e_time,
                trader_id=trader_id,
                signal=sig,
            )
            for sig in (signals or [])
        ]
        if records:
            async with async_session() as s:
                s.add_all(records)
                await s.commit()
            logger.info(f"recorded {len(records)} signals for account {t.cast(str, acc.name)}")

        return signals

    return asyncio.run(func())


def _calc_market_quantity(info: SymbolInfo, notional: decimal.Decimal, price: decimal.Decimal) -> decimal.Decimal:
    """按合约 LOT_SIZE 规则，用 decimal 计算市价单数量（向下取整到 stepSize）。"""
    for f in info["filters"]:
        if f["filterType"] != "LOT_SIZE":
            continue
        f = t.cast(SymbolLotSizeFilter, f)
        step = decimal.Decimal(str(f["stepSize"]))
        min_q = decimal.Decimal(str(f["minQty"]))
        max_q = decimal.Decimal(str(f["maxQty"]))
        qty = (notional / price) // step * step
        if qty < min_q:
            raise ValueError(f"计算数量 {qty} 小于最小数量 {min_q}")
        return min(qty, max_q)
    raise ValueError(f"symbol {info['symbol']} 缺少 LOT_SIZE 规则")


@app.task
def trade(results: list[t.Any], account_id: int):
    """默认交易执行器：单标的、1倍杠杆，按 USDT 可用资金 95% 市价开/补仓，反向先平仓。"""

    async def func():
        async with async_session() as s:
            acc = (await s.execute(select(Account).filter_by(id=account_id))).scalar()
        if acc is None:
            raise ValueError(f"account {account_id} not found")
        exchange = t.cast(str, acc.exchange)
        if exchange != 'binance':
            raise NotImplementedError(f"unsupported exchange: {exchange}")

        signals: list[dict[str, t.Any]] = (
            results[1] if len(results) > 1 and isinstance(results[1], list) else []
        )
        if not signals:
            logger.warning(f"trade: account {t.cast(str, acc.name)} 无信号，跳过")
            return None
        if len(signals) > 1:
            raise ValueError(f"默认交易执行器只允许一个标的的信号，当前收到 {len(signals)} 个")

        sig = signals[0]
        signal = sig.get('signal')
        if signal is None:
            logger.info(f"trade: account {t.cast(str, acc.name)} 信号为维持，跳过")
            return None
        signal_val = int(signal)
        symbol = str(sig['target'])
        price = decimal.Decimal(str(sig.get('close') or 0))
        if price <= 0:
            raise ValueError(f"{symbol} 无有效价格")

        encrypt_t = t.cast(t.Literal['hmac', 'ed25519', 'rsa'], acc.encrypt_type or 'hmac')
        b = Binance(t.cast(str, acc.api_key), t.cast(str, acc.api_secret), encrypt_t)
        orders: list[dict[str, t.Any]] = []
        try:
            # 1. 尝试设置杠杆为 1
            ok, _ = await b.request(SetLeverage(symbol, 1))
            if not ok:
                logger.warning(f"{symbol} 设置杠杆为 1 失败")

            info = await b.symbol_info_futures(symbol)

            # 2. 查询当前持仓
            ok, pos_list = await b.request(PositionRisk(symbol))
            if not ok:
                raise ValueError(f"{symbol} 查询持仓失败")
            pos_amt = decimal.Decimal(0)
            for p in pos_list:
                if p.get('symbol') == symbol:
                    pos_amt = decimal.Decimal(str(p.get('positionAmt', '0')))
                    break

            # 3. 平仓信号
            if signal_val == 0:
                if pos_amt == 0:
                    logger.info(f"{symbol} 无持仓，无需平仓")
                    return orders
                side: t.Literal['BUY', 'SELL'] = 'SELL' if pos_amt > 0 else 'BUY'
                qty = abs(pos_amt)
                ok, resp = await b.request(UMTrade(symbol, side, float(qty)))
                if not ok:
                    raise ValueError(f"{symbol} 平仓失败: {resp}")
                orders.append({'symbol': symbol, 'side': side, 'quantity': float(qty), 'order': resp})
                logger.info(f"trade 平仓: {symbol} {side} qty={qty}")
                return orders

            # 4. 方向相反 → 先平仓
            pos_dir = 1 if pos_amt > 0 else (-1 if pos_amt < 0 else 0)
            if pos_dir != 0 and pos_dir != signal_val:
                close_side: t.Literal['BUY', 'SELL'] = 'SELL' if pos_dir > 0 else 'BUY'
                close_qty = abs(pos_amt)
                ok, resp = await b.request(UMTrade(symbol, close_side, float(close_qty)))
                if not ok:
                    raise ValueError(f"{symbol} 平仓失败: {resp}")
                orders.append({'symbol': symbol, 'side': close_side, 'quantity': float(close_qty), 'order': resp})
                logger.info(f"trade 反向平仓: {symbol} {close_side} qty={close_qty}")

            # 5. 开仓/补仓：查询 USDT 可用资产，取 95% 向下取整
            ok, balances = await b.request(Balance())
            if not ok:
                raise ValueError(f"{symbol} 查询资产失败")
            usdt = decimal.Decimal(0)
            for bal in balances:
                if bal.get('asset') == 'USDT':
                    usdt = decimal.Decimal(str(bal.get('availableBalance', '0')))
                    break
            notional = usdt * decimal.Decimal('0.95')
            if notional <= 0:
                logger.warning(f"{symbol} USDT 可用余额不足，跳过")
                return orders

            qty = _calc_market_quantity(info, notional, price)
            side = 'BUY' if signal_val > 0 else 'SELL'
            ok, resp = await b.request(UMTrade(symbol, side, float(qty)))
            if not ok:
                raise ValueError(f"{symbol} 开仓失败: {resp}")
            orders.append({'symbol': symbol, 'side': side, 'quantity': float(qty), 'order': resp})
            logger.info(f"trade 开仓/补仓: {symbol} {side} qty={qty} (名义 {qty * price})")
        finally:
            await b.session.close()
        return orders

    return asyncio.run(func())


@app.task(ignore_result=True)
def run_all(results: list[t.Any], p: DataPeriod, exchange: str, e_time: int):
    """交易所数据执行完成后，仅执行选定该交易所的账户策略。

    results: chain(group(kline), run_all) 会将本任务作为 chord 回调，
             第一个位置参数为前置 group 各任务的结果列表，此处不使用。
    """

    async def func():
        async with async_session() as s:
            accounts = (await s.execute(
                select(Account).filter(Account.exchange == exchange, Account.status == 0)
            )).scalars().all()
        for acc in accounts:
            logger.info(f"dispatch check+strategy for account {t.cast(str, acc.name)} (exchange={exchange}, e_time={e_time})")
            chord(
                [t.cast(Task, check).s(acc.id), t.cast(Task, run_one).s(acc.id, e_time, p)],
                t.cast(Task, trade).s(acc.id),
            ).apply_async()

    asyncio.run(func())