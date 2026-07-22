from typing import Any
from database.base import async_session
from database.model import Strategy
from sqlalchemy import select
from .base import toolMeta


class FindStrategy(metaclass=toolMeta):
    """
    """
    async def __call__(self, uuid: str) -> Any:
        """
        
        """
        async with async_session() as s:
            res = await s.execute(select(Strategy).filter_by(uuid=uuid))
            res.scalars().fetchall()
        
