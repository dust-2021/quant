import asyncio
from datetime import datetime
import typing as t
from celery import Task
from database.base import DataPeriod
from task import app
from cores.exchange import Binance, BinaceApi
from utils.cache import get_cache
from utils.types import CacheName
from loguru import logger


@app.task(ignore_result=True)
def cache_binance_kline(symbol: list[str], interval: t.Literal['1m', '1h', '1d']) -> None:
    """拉取并缓存 Binance K 线数据。"""

    async def func():
        b = Binance('')
        try:
            datas = await b.requests([BinaceApi.Kline(s, interval=interval) for s in symbol])
            
            cache = get_cache()
            for s, resp in zip(symbol, datas):
                if not resp[0]:
                    logger.error(f'binance kline symbol:{s}, period: {interval} failed: {resp[1]}')
                    continue
                cache.set(f'{CacheName.Binance_Kline.value}::{interval}::{s}', resp[1])
        finally:
            await b.session.close()

    asyncio.run(func())

@app.task(ignore_result=True)
def kline(p: DataPeriod):
    interval: str = '1m'
    if p == DataPeriod.HOUR:
        interval = '1h'
    elif p == DataPeriod.DAY:
        interval = '1d'
    for s in []:
        t.cast(Task, cache_binance_kline).delay(s, interval)