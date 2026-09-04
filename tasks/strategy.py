import typing as t
from database.base import DataPeriod
from datetime import datetime
from task import app


@app.task
def run_all(p: DataPeriod):
    # 理论执行时间
    e_time: int = round(datetime.now().timestamp() * 1000) // p.value * p.value