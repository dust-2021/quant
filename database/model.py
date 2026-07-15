import datetime
import importlib.util
import inspect as insp
from sqlalchemy import Column, Integer, String, Text, PickleType, UniqueConstraint
from .base import DataPeriod, base
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


# =========== 数据中心逻辑表 ===============

class Target(base):
    __tablename__ = "target"

    id = Column(Integer, primary_key=True)
    code = Column(String(255), nullable=False, index=True, comment="标的唯一识别")
    exchange = Column(String(255), nullable=False)

    __table_args__ = (
        UniqueConstraint("code", "exchange", name="code_exchange_unique_idx"),
    )

    def src_table(self, p: DataPeriod) -> str:
        return f"DATA_{self.exchange}_{self.code}_{p.name}"


class Script(base):
    __tablename__ = "script"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, index=True, unique=True)
    content = Column(String(1 << 16))

    @classmethod
    async def load_and_execute(cls, name: str, **context) -> t.Any:
        """加载并执行指定名称的脚本。"""
        async with async_session() as s:
            result = await s.execute(select(cls).filter_by(name=name))
            row = result.first()
        if row is None:
            raise ValueError(f"脚本 '{name}' 不存在")
        script = row[0]
        mod = importlib.util.spec_from_loader(name, loader=None)
        if mod is None:
            raise RuntimeError(f"无法为脚本 '{name}' 创建模块规格")
        mod = importlib.util.module_from_spec(mod)
        for key, val in context.items():
            setattr(mod, key, val)
        try:
            exec(t.cast(str, script.content), mod.__dict__)
        except Exception as e:
            raise RuntimeError(f"执行脚本 '{name}' 时出错: {e}") from e
        func: t.Optional[t.Callable] = getattr(mod, "run", None)
        if func is None:
            raise NotImplementedError(f"脚本 '{name}' 必须定义 run 函数")
        result = func()
        return await result if insp.isawaitable(result) else result


class Exchange(base):
    __tablename__ = "exchange"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, index=True, unique=True)
    