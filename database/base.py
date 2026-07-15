from sqlalchemy import text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from enum import Enum
import os
import typing as t

db_path = os.path.join(os.getcwd(), 'locals', 'quant.db')

async_engine = create_async_engine(f'sqlite+aiosqlite:///{db_path}', echo=False, pool_size=2)

base = declarative_base()

async_session = async_sessionmaker(async_engine, expire_on_commit=False)


class DataPeriod(Enum):
    MINUTE = 60
    HOUR = 3600
    DAY = 86400

    @classmethod
    def from_seconds(cls, seconds: int) -> t.Optional["DataPeriod"]:
        for period in cls:
            if period.value == seconds:
                return period
        return None


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
