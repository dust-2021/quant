from sqlalchemy import select

from database.base import async_session
from database.model import Strategy

from .base import toolManager


@toolManager()
async def find_strategy(self, uuid: str) -> Strategy | None:
    """
    根据策略uuid从数据库中查找策略
    
    Args:
        uuid (str): 策略的uuid
    Returns:
        Strategy | None: 如果找到策略，返回Strategy的orm对象，否则返回None
    """
    async with async_session() as s:
        res = await s.execute(select(Strategy).filter_by(uuid=uuid))
        return res.scalar()


@toolManager()
def modify(uuid: str, **kwargs) -> None:
    """
    修改策略信息
    @params uuid: str
    @params kwargs: dict
    """

    async def _modify():
        async with async_session() as s:
            res = await s.execute(select(Strategy).filter_by(uuid=uuid))
            strategy = res.scalar()
            if strategy is None:
                return
            for k, v in kwargs.items():
                if hasattr(strategy, k):
                    setattr(strategy, k, v)
            await s.commit()

    import asyncio

    asyncio.create_task(_modify())
