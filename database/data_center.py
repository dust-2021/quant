from sqlalchemy import (
    inspect,
    select,
    text,
    and_,
)
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncEngine,
    async_sessionmaker,
    AsyncSession,
)
import typing as t
import pandas as pd
from .model import Config as ConfigModel
from .base import Target, DataPeriod


_engine: t.Optional[AsyncEngine] = None
_session: t.Optional[async_sessionmaker[AsyncSession]] = None


async def check_target_table(name: str):
    """检查数据表是否存在，不存在则自动建表。"""
    if _session is None:
        raise ValueError("数据中心未连接")
    if _engine is None:
        raise ValueError("数据中心未连接")
    async with _engine.connect() as conn:
        has = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).has_table(name)
        )
    if has:
        return
    ddl = text(f"""
        CREATE TABLE "{name}" (
            id SERIAL PRIMARY KEY,
            open_time BIGINT NOT NULL UNIQUE,
            open DECIMAL(20,8) DEFAULT 0,
            high DECIMAL(20,8) DEFAULT 0,
            low DECIMAL(20,8) DEFAULT 0,
            close DECIMAL(20,8) DEFAULT 0,
            volume DECIMAL(20,8) DEFAULT 0,
            close_time BIGINT DEFAULT 0,
            quote_asset_volume DECIMAL(20,8) DEFAULT 0,
            number_of_trades INT DEFAULT 0,
            taker_buy_base_asset_volume DECIMAL(20,8) DEFAULT 0,
            taker_buy_quote_asset_volume DECIMAL(20,8) DEFAULT 0,
            "ignore" INT DEFAULT 0
        )
    """)
    async with _engine.begin() as conn:
        await conn.execute(ddl)
        await conn.execute(
            text(
                f'CREATE INDEX IF NOT EXISTS idx_{name}_open_time ON "{name}" (open_time);'
            )
        )


# ==================


async def init_data_center():
    """显式的初始化函数，在启动时调用一次"""
    global _engine, _session
    db_path = await ConfigModel.get("DataCenterLink")
    if not db_path:
        return
    _engine = create_async_engine(str(db_path), pool_size=10)
    _session = async_sessionmaker(bind=_engine)


def get_session() -> async_sessionmaker[AsyncSession]:
    """纯 getter，不再有副作用"""
    if _session is None:
        raise RuntimeError("数据中心未初始化，请先调用 init_data_center()")
    return _session


async def load_data(
    s: int, e: int, target: t.Sequence[str], p: DataPeriod = DataPeriod.HOUR
) -> pd.DataFrame:
    """从数据中心加载数据，检查每个数据表是否存在，存在则查询并拼接为 DataFrame。

    Args:
        s: 起始时间（Unix 时间戳）
        e: 结束时间（Unix 时间戳）
        target: 目标标的序列
        p: 数据周期

    Returns:
        拼接后的 DataFrame，表字段作为列名；若无数据则返回空 DataFrame。

    Raises:
        ValueError: 任一数据表不存在时抛出。
    """
    s -= s % p.value
    e -= e % p.value
    target_s: t.Set[str] = set(target)
    if _engine is None:
        raise ValueError("数据中心未链接")
    async with get_session()() as session:
        resp = (
            await session.execute(
                select(Target).filter(
                    and_(
                        Target.code.in_(target_s),
                        Target.exchange == await ConfigModel.get("Exchange"),
                    )
                )
            )
            if len(target) != 0
            else await session.execute(
                # 全量选取
                select(Target).filter(
                    Target.exchange == await ConfigModel.get("Exchange")
                )
            )
        )
        code_tables: t.List[t.Tuple[str, str]] = [(t.cast(str, x.code), x.src_table(p)) for x in resp.scalars().all()]

        # 检查每个表是否存在（兼容 SQLite / PostgreSQL / MySQL 等）
        async with _engine.connect() as conn:
            for _, table_name in code_tables:
                has = await conn.run_sync(
                    lambda sync_conn, tn=table_name: inspect(sync_conn).has_table(tn)
                )
                if not has:
                    raise ValueError(f"数据表 '{table_name}' 在数据中心中不存在")

        # 查询各表数据并拼接
        frames: t.List[pd.DataFrame] = []
        for code, table_name in code_tables:
            # 使用引擎方言正确引用表名，兼容不同数据库
            query = f'SELECT * FROM "{table_name}" WHERE open_time >= :start_time AND open_time <= :end_time'
            result = await session.execute(
                text(query),
                {"start_time": s, "end_time": e},
            )
            rows = result.all()
            if rows:
                df = pd.DataFrame(rows, columns=list(result.keys()))
                # 将 DECIMAL 列转为 float，方便 DataFrame 数值计算
                decimal_cols = [
                    "open", "high", "low", "close", "volume",
                    "quote_asset_volume", "taker_buy_base_asset_volume",
                    "taker_buy_quote_asset_volume",
                ]
                for col in decimal_cols:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors="coerce").astype(float)
                df['code'] = code
                frames.append(df)

        if not frames:
            return pd.DataFrame()

        return pd.concat(frames, ignore_index=True)
