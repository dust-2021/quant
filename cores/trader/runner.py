import typing as t
from cores.executor.base import Core

from apscheduler.schedulers.asyncio import AsyncIOScheduler

class TradeRuner:
    """"""
    
    def __init__(self, exchange: str, strategy_uid: str, period: str, symbol: str):
        self.exchange = exchange
        self.strategy_uid = strategy_uid
        self.period = period
        self.symbol = symbol
        
    async def load_data(self):
        """加载数据"""
        strategy = await Core.prepare_raw(self.strategy_uid)
        if not strategy:
            raise ValueError(f"策略 {self.strategy_uid} 不存在")
        
        
    async def run(self):
        pass