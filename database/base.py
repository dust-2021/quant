import os
import typing as t
from enum import Enum

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.declarative import declarative_base

from config import Config

_main_db_link = (getattr(Config, 'MainDbLink', '') or '').strip()
if _main_db_link:
    async_engine = create_async_engine(_main_db_link, echo=False)
else:
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


async def _sync_trader_column(conn, table: str) -> None:
    """将表中 trader_id 列重命名为 trader（字符串名）。"""
    result = await conn.execute(text(f"select name from sqlite_master where type='table' and name='{table}'"))
    if result.scalar() is None:
        return
    cols = [row[1] for row in (await conn.execute(text(f"PRAGMA table_info({table})"))).fetchall()]
    if "trader_id" in cols and "trader" not in cols:
        await conn.execute(text(f"ALTER TABLE {table} RENAME COLUMN trader_id TO trader"))


async def _sync_account_table(conn):
    """若 account 表为旧结构（缺少 status 列），删除重建（表内无数据）。"""
    result = await conn.execute(text("select name from sqlite_master where type='table' and name='account'"))
    if result.scalar() is None:
        return
    cols = [row[1] for row in (await conn.execute(text("PRAGMA table_info(account)"))).fetchall()]
    if "status" in cols and "encrypt_type" in cols:
        return
    await conn.execute(text("DROP TABLE account"))


async def init_db():
    async with async_engine.begin() as conn:
        # 旧结构 trader_id → trader 重命名迁移
        await _sync_trader_column(conn, 'account')
        await _sync_trader_column(conn, 'signal_record')
        # 同步 account 表结构（旧结构且无数据时删除重建）
        await _sync_account_table(conn)
        await conn.run_sync(base.metadata.create_all)
        # 初始化交易所列表（不存在则添加）
        for exchange_name in Config.Exchanges:
            result = await conn.execute(
                text("select id from exchange where name = :name"),
                {"name": exchange_name},
            )
            if result.scalar() is None:
                await conn.execute(
                    text("insert into exchange (name) values (:name)"),
                    {"name": exchange_name},
                )
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
