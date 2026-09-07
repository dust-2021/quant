import typing as t
from celery import Task

from utils.scheduler import aSche
from apscheduler.triggers.cron import CronTrigger

from config import Config
from database.base import DataPeriod

from tasks.kline import kline, update_binance_exchange_info


def dispatch_kline(p: DataPeriod) -> None:
    """通过 celery 异步发送 kline 任务，任务在 worker 执行，不在当前服务端执行。"""
    for exchange in Config.Exchanges:
        t.cast(Task, kline).delay(p, exchange)


def dispatch_update_exchange_info() -> None:
    """每小时更新一次 Binance 现货与合约交易对信息。"""
    t.cast(Task, update_binance_exchange_info).delay()


def init_jobs():
    # 定时拉取 kline 数据，kline 完成后由 kline 任务链式触发策略任务
    aSche.add_job(dispatch_kline, CronTrigger(second=0), id='binance-kline-minute', args=(DataPeriod.MINUTE, ))
    aSche.add_job(dispatch_kline, CronTrigger(minute=0), id='binance-kline-hour', args=(DataPeriod.HOUR, ))
    aSche.add_job(dispatch_kline, CronTrigger(hour=0), id='binance-kline-day', args=(DataPeriod.DAY, ))
    # 每小时最后一分钟第三十秒更新交易对信息（现货+合约）
    aSche.add_job(dispatch_update_exchange_info, CronTrigger(minute=59, second=30), id='binance-exchange-info')