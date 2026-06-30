from sqlalchemy import (
    Column,
    Integer,
    String,
    inspect,
    select,
    text,
    and_,
    UniqueConstraint,
)
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncEngine,
    async_sessionmaker,
    AsyncSession,
)
from sqlalchemy.orm import declarative_base
import typing as t
import pandas as pd
from .model import Config as ConfigModel
from enum import Enum
import importlib.util
import inspect as insp


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


_engine: t.Optional[AsyncEngine] = None
_session: t.Optional[async_sessionmaker[AsyncSession]] = None

base = declarative_base(name="DataCenter")

# ==== MODEL =====


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
        """加载并执行指定名称的脚本。

        Args:
            name: 脚本名称
            **context: 注入到脚本模块的上下文变量

        Returns:
            脚本中 run 函数的返回值

        Raises:
            ValueError: 脚本不存在时抛出
            NotImplementedError: 脚本缺少 run 函数时抛出
        """
        if _session is None:
            raise RuntimeError("数据中心未初始化，请先调用 init_data_center()")
        async with get_session()() as s:
            result = await s.execute(select(cls).filter_by(name=name))
            row = result.first()
        if row is None:
            raise ValueError(f"脚本 '{name}' 不存在")
        script = row[0]
        # 动态加载为模块
        mod = importlib.util.spec_from_loader(name, loader=None)
        if mod is None:
            raise RuntimeError(f"无法为脚本 '{name}' 创建模块规格")
        mod = importlib.util.module_from_spec(mod)
        # 注入上下文
        for key, val in context.items():
            setattr(mod, key, val)
        try:
            exec(t.cast(str, script.content), mod.__dict__)
        except Exception as e:
            raise RuntimeError(f"执行脚本 '{name}' 时出错: {e}") from e
        func: t.Optional[t.Callable[[], t.Union[None, t.Awaitable[None]]]] = getattr(mod, "run", None)
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

    def src_table(self, p: DataPeriod = DataPeriod.HOUR) -> str:
        return f"DATA_{self.exchange}_{self.code}_{p.name}"

    @staticmethod
    async def check_target_table(name: str):
        """检查数据表是否存在，不存在则自动建表。

        表字段 open_time (BIGINT), open/high/low/close/volume (DECIMAL(20,8)),
            close_time (BIGINT), quote_asset_volume (DECIMAL(20,8)),
            number_of_trades (INT), taker_buy_base_asset_volume (DECIMAL(20,8)),
            taker_buy_quote_asset_volume (DECIMAL(20,8)), ignore (INT)
        """
        if _session is None:
            raise ValueError("数据中心未连接")
        if _engine is None:
            raise ValueError("数据中心未连接")
        # 通过 run_sync 使用同步 inspector，避免 greenlet 上下文缺失错误
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
    async with _engine.begin() as conn:
        await conn.run_sync(base.metadata.create_all)


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
