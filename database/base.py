from sqlalchemy import text, Column, Integer, String, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select
from enum import Enum
import os
import typing as t
import importlib.util
import inspect as insp

db_path = os.path.join(os.getcwd(), 'locals', 'quant.db')

async_engine = create_async_engine(f'sqlite+aiosqlite:///{db_path}', echo=False, pool_size=2)

base = declarative_base()

async_session = async_sessionmaker(async_engine, expire_on_commit=False)


class DataPeriod(Enum):
    SECOND = 1
    MINUTE = 60
    HOUR = 3600
    DAY = 86400

    @classmethod
    def from_seconds(cls, seconds: int) -> t.Optional["DataPeriod"]:
        for period in cls:
            if period.value == seconds:
                return period
        return None


# ===== 数据中心逻辑模型 =====

class Exchange(base):
    __tablename__ = "exchange"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, index=True, unique=True)


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

async def init_db():
    async with async_engine.begin() as conn:
        await conn.run_sync(base.metadata.create_all)
        # 检查默认分组是否存在，不存在则创建
        result = await conn.execute(
            text("select id from strategy_group where name = 'default'")
        )
        row = result.fetchone()
        if row is None:
            await conn.execute(
                text("insert into strategy_group (name, description) values ('default', '默认分组')")
            )
        result = await conn.execute(
            text("select id from factor_group where name = 'default'")
        )
        row = result.fetchone()
        if row is None:
            await conn.execute(
                text("insert into factor_group (name, description) values ('default', '默认分组')")
            )
        result = await conn.execute(
            text("select id from calculator where name = 'default'")
        )
        row = result.fetchone()
        if row is None:
            await conn.execute(
                text("insert into calculator (name, description, content, create_time, update_time) values ('default', '单标的单边全仓持仓的通用回测算子', '', strftime('%s','now'), strftime('%s','now'))")
            )
        await conn.commit()
