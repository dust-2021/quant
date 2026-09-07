import asyncio
import typing as t
from datetime import datetime

from celery import Task, chain, group
from loguru import logger
from sqlalchemy import select

from cores.exchange import Binance, BinaceApi
from database.base import DataPeriod, async_session
from database.model import Config, Target
from task import app
from utils.cache import get_cache
from utils.types import CacheName


@app.task(ignore_result=True)
def cache_binance_kline(symbol: str, interval: t.Literal['1m', '1h', '1d'], e_time: int, period_ms: int) -> None:
    """拉取并缓存单个 symbol 的 Binance K 线数据。"""

    async def func():
        # 动态读取实盘K线数量（默认1000），按理论运行时间向前推算 start_time
        limit: int = int(await Config.get("KlineCount") or 1000)
        start_time: int = e_time - limit * period_ms
        b = Binance('')
        try:
            f, resp = await b.request(
                BinaceApi.Kline(symbol, interval=interval, start_time=start_time, limit=limit)
            )
            if not f:
                logger.error(f'binance kline symbol:{symbol}, period: {interval} failed: {resp}')
                return
            cache = get_cache()
            cache.set(f'{CacheName.Binance_Kline.value}::{interval}::{symbol}', resp)
        finally:
            await b.session.close()

    asyncio.run(func())


@app.task(ignore_result=True)
def kline(p: DataPeriod, exchange: str = 'binance'):
    """分发 kline 拉取任务，全部完成后触发对应交易所的策略任务。"""
    from tasks.strategy import run_all

    # 启动时计算当前的理论运行时间（对齐到周期边界，单位毫秒），逐级传入后续任务
    e_time: int = (round(datetime.now().timestamp() * 1000) // (p.value * 1000)) * (p.value * 1000)

    interval: str = '1m'
    if p == DataPeriod.HOUR:
        interval = '1h'
    elif p == DataPeriod.DAY:
        interval = '1d'

    async def load_symbols() -> list[str]:
        async with async_session() as s:
            codes = (await s.execute(select(Target.code).filter_by(exchange=exchange))).scalars().all()
        return list(codes)

    symbols = asyncio.run(load_symbols())
    if not symbols:
        symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']
    period_ms: int = p.value * 1000
    # 并发拉取所有标的的 kline，全部完成后执行该交易所的策略任务
    g = group(t.cast(Task, cache_binance_kline).s(s, interval, e_time, period_ms) for s in symbols)
    chain(g, t.cast(Task, run_all).s(p, exchange, e_time)).apply_async()


@app.task(ignore_result=True)
def update_binance_exchange_info():
    """更新 Binance 现货与合约交易对信息。"""

    async def func():
        b = Binance('')
        try:
            f, info = await b.request(BinaceApi.ExchangeInfo())
            if f:
                get_cache().set(CacheName.Binance_ExchangeInfo.value, info)
                logger.info(f"binance spot exchange info updated, symbols={len(info['symbols'])}")
            else:
                logger.error(f"binance spot exchange info update failed: {info}")

            f, fut_info = await b.request(BinaceApi.ExchangeInfoFutures())
            if f:
                get_cache().set(CacheName.Binance_ExchangeInfo_Future.value, fut_info)
                logger.info(f"binance futures exchange info updated, symbols={len(fut_info['symbols'])}")
            else:
                logger.error(f"binance futures exchange info update failed: {fut_info}")
        finally:
            await b.session.close()

    asyncio.run(func())