import datetime
from sqlalchemy import Column, Integer, String, Text, PickleType
from .base import base
import uuid
from database.base import async_session
from sqlalchemy import select, and_
from asyncio import locks
import typing as t
from config import Config as ConfigEnum


class Config(base):
    """
    配置表
    """
    
    __tablename__ = "config"
    
    _cache: t.Dict[str, t.Any] = {}
    _cache_lock = locks.Lock()

    id = Column(Integer, primary_key=True)
    key = Column(String(255), nullable=False, index=True, unique=True)
    value = Column(PickleType, nullable=True)
    
    @staticmethod
    async def get(key: str) -> t.Any:
        async with Config._cache_lock:
            if (v := Config._cache.get(key)) is not None:
                return v
            async with async_session() as s:
                config = await s.execute(select(Config.value).where(Config.key == key))
                config = config.scalar()
            Config._cache[key] = config if config is not None else getattr(ConfigEnum, key, None)
            return Config._cache[key]

    @staticmethod
    async def set(key: str, value: t.Any):
            
        async with Config._cache_lock:
            Config._cache[key] = value
            async with async_session() as s:
                config = await s.execute(select(Config).where(Config.key == key))
                config = config.scalar()
                if config is None:
                    config = Config(key=key, value=value)
                    s.add(config)
                else:
                    config.value = value
                await s.commit()
                

class StrategyGroup(base):
    __tablename__ = "strategy_group"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, index=True, unique=True)
    description = Column(Text, nullable=True)


class FactorGroup(base):
    __tablename__ = "factor_group"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, index=True, unique=True)
    description = Column(Text, nullable=True)
    

class Strategy(base):
    __tablename__ = "strategy"

    id = Column(Integer, primary_key=True)
    uuid = Column(String(64), nullable=False, index=True, unique=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False, index=True)
    version = Column(String(255), nullable=False, default="0.0.1", comment="版本")
    create_time = Column(Integer, nullable=False, default=lambda: int(datetime.datetime.now().timestamp()))
    update_time = Column(Integer, nullable=False, onupdate=lambda: int(datetime.datetime.now().timestamp()), default=lambda: int(datetime.datetime.now().timestamp()))
    group = Column(String(255), nullable=False,default="", index=True, comment="分组")
    description = Column(Text, nullable=True)
    factors = Column(String(1 << 16), nullable=False, default="[]", comment="因子uuid的json字符串")
    content = Column(Text, nullable=False, default="", comment="策略内容")
    params = Column(PickleType, comment="参数")
    
    async def exist(self) -> bool:
        async with async_session() as s:
            strategy = await s.execute(select(Strategy.id).where(and_(Strategy.name == self.name, Strategy.version == self.version)))
            return strategy.scalar() is not None
    
    def dump(self):
        pass
    

class Factor(base):
    __tablename__ = "factor"

    id = Column(Integer, primary_key=True)
    uuid = Column(String(64), nullable=False, index=True, unique=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False, index=True)
    version = Column(String(255), nullable=False, default="0.0.1", comment="版本")
    create_time = Column(Integer, nullable=False, default=lambda: int(datetime.datetime.now().timestamp()))
    update_time = Column(Integer, nullable=False, onupdate=lambda: int(datetime.datetime.now().timestamp()), default=lambda: int(datetime.datetime.now().timestamp()))
    description = Column(Text, nullable=True)
    content = Column(Text, nullable=False, default="", comment="因子内容")
    params = Column(PickleType, comment="默认参数")
    group = Column(String(255), nullable=False, default="default", index=True, comment="分组")
    
    @classmethod
    async def load(cls, uuids: list[str]) -> list["Factor"]:
        async with async_session() as s:
            factors = await s.execute(select(Factor).where(Factor.uuid.in_(uuids)))
            factors = factors.scalars().all()
            await s.commit()
            return list(factors)
        

class Calculator(base):
    __tablename__ = "calculator"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, index=True, unique=True)
    create_time = Column(Integer, nullable=False, default=lambda: int(datetime.datetime.now().timestamp()))
    update_time = Column(Integer, nullable=False, onupdate=lambda: int(datetime.datetime.now().timestamp()), default=lambda: int(datetime.datetime.now().timestamp()))
    description = Column(Text, nullable=True)
    content = Column(Text, nullable=False, default="", comment="计算器内容")
    