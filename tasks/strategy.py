import asyncio
import json
import typing as t

from celery import Task
from loguru import logger
from sqlalchemy import select

from cores.executor.calculator import Calculator
from cores.trader import get_trader, extract_signals
from database.base import DataPeriod, async_session
from database.model import Account, SignalRecord
from task import app
from utils.types import ContextBase


@app.task
def run_one(account_id: int, e_time: int, p: DataPeriod):
    """执行单个账户绑定的策略（实盘）：并行校验账户与生成信号，再执行交易。"""

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

        trader = get_trader(t.cast(str, acc.trader) or 'default')(acc)

        ctx: ContextBase = {
            "is_living": True,
            "strategy_uuid": strategy_uuid,
            "exchange": exchange,
            "target": targets,
            "period": t.cast(t.Literal[60, 3600, 86400], p.value),
            "excute_strict_time": e_time,
        }

        # 1. 并行执行：账户校验 + 信号生成（返回 DataFrame 与策略参数）
        ok, (data, params) = await asyncio.gather(
            trader.check(),
            Calculator.living_run(ctx),
        )
        if not ok:
            raise ValueError(f"account {t.cast(str, acc.name)} check failed")

        # 2. 记录信号
        sigs = extract_signals(data, str(ctx.get('signal_name', 'signal')))
        records = [
            SignalRecord(
                exchange=exchange,
                account_id=account_id,
                strategy_uuid=strategy_uuid,
                period=p.value,
                target=str(sig.get('target')),
                excute_strict_time=e_time,
                trader=t.cast(str | None, acc.trader),
                signal=sig,
            )
            for sig in sigs
        ]
        if records:
            async with async_session() as s:
                s.add_all(records)
                await s.commit()
            logger.info(f"recorded {len(records)} signals for account {t.cast(str, acc.name)}")

        # 3. 执行交易
        return await trader.trade(data, ctx, params)

    return asyncio.run(func())


@app.task(ignore_result=True)
def run_all(p: DataPeriod, exchange: str, e_time: int):
    """交易所数据执行完成后，仅执行选定该交易所的账户策略。
    """

    async def func():
        async with async_session() as s:
            accounts = (await s.execute(
                select(Account).filter(
                    Account.exchange == exchange,
                    Account.status == 0,
                    Account.period == p.value,
                )
            )).scalars().all()
        for acc in accounts:
            logger.info(f"dispatch strategy for account {t.cast(str, acc.name)} (exchange={exchange}, e_time={e_time})")
            t.cast(Task, run_one).delay(acc.id, e_time, p)

    asyncio.run(func())