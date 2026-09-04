import typing as t
import asyncio
from utils.scheduler import aSche
from apscheduler.triggers.cron import CronTrigger

from tasks.kline import kline

def init_jobs():
    # 最先执行的数据任务
    aSche.add_job(kline, CronTrigger(second=0), id='binance-kline-minute')
    aSche.add_job(kline, CronTrigger(minute=0), id='binance-kline-hour')
    aSche.add_job(kline, CronTrigger(hour=0), id='binance-kline-day')