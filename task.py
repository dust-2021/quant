"""Celery 应用实例。

broker 使用本地 rabbitmq，任务结果存放在本地 redis 的 1 号数据库。
"""
from celery import Celery

from config import Config

app = Celery(
    'quant',
    broker=Config.CeleryBroker,
    backend=Config.CeleryBackend,
    include=['tasks.kline', 'tasks.strategy'],
)

app.conf.update(
    task_serializer='pickle',
    result_serializer='pickle',
    accept_content=['pickle', 'json'],
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    result_expires=3600,
)
