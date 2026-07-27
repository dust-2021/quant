from database.base import async_session
from database.model import Strategy
from sqlalchemy import select
from .base import toolMeta


class FindStrategy(metaclass=toolMeta):
    """
    """
    async def __call__(self, uuid: str) -> Strategy | None:
        """
        根据策略uuid查询
        @oarams uuid: str
        """
        async with async_session() as s:
            res = await s.execute(select(Strategy).filter_by(uuid=uuid))
            return res.scalar()
        
