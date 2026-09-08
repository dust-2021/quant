import asyncio
import itertools
import traceback
import typing as t
import uuid

import loguru
import pandas as pd

from cores.backtest.runner_loader import Runner_T, get_runner
from utils.types import ContextBase
from database.base import DataPeriod
from database.data_center import load_data
from utils.cache import TaskCache, get_cache
from utils.scheduler import aSche
from utils.types import CacheName

from .base import Core

# 多参数键前缀
PREFIX_STRATEGY = "_strategy."
PREFIX_FACTOR = "_factor."

_run_T: t.TypeAlias = t.Callable[[pd.DataFrame], pd.DataFrame]  # noqa: PYI042

# Binance K 线返回字段（与 /fapi/v1/klines 顺序一致）
KLINE_COLUMNS: list[str] = [
    "open_time", "open", "high", "low", "close", "volume",
    "close_time", "quote_asset_volume", "number_of_trades",
    "taker_buy_base_asset_volume", "taker_buy_quote_asset_volume", "ignore",
]

def _split_prefixed_params(flat: dict[str, t.Any]) -> tuple[dict[str, t.Any], dict[str, dict[str, t.Any]]]:
    """将带前缀的扁平参数字典拆分为策略参数和因子参数。
    Args:
        flat: {"_strategy.leverage": 1, "_factor.uuid1.window": 5, ...}
    Returns:
        (strategy_overrides: {param: value}, factor_overrides: {uuid: {param: value}})
    """
    strat: dict[str, t.Any] = {}
    factors: dict[str, dict[str, t.Any]] = {}
    for key, val in flat.items():
        if key.startswith(PREFIX_STRATEGY):
            strat[key[len(PREFIX_STRATEGY):]] = val
        elif key.startswith(PREFIX_FACTOR):
            rest = key[len(PREFIX_FACTOR):]
            parts = rest.split(".", 1)
            if len(parts) == 2:
                uuid_str, param = parts
                factors.setdefault(uuid_str, {})[param] = val
    return strat, factors


def _run_pipeline(
    src_raw: dict[str, t.Any],
    data: pd.DataFrame,
    ctx: ContextBase,
    multi_params: dict[str, t.Any],
) -> tuple[object, pd.DataFrame]:
    """运行因子与策略，返回 (strategy_module, 带信号列的 DataFrame)。"""
    strategy_name: str = src_raw["strategy"]["name"]
    strategy_params: list[dict[str, t.Any]] = src_raw["strategy"]["params"]
    factors_raw: list[dict[str, t.Any]] = src_raw["factors"]

    strat_overrides, factor_overrides = _split_prefixed_params(multi_params)

    # 运行因子（使用对应 uuid 的覆盖参数）
    for f_raw in factors_raw:
        f_mod = Core.load_file(f_raw["name"], f_raw["content"])
        if f_mod is None:
            raise ValueError(f"failed to load factor module: {f_raw['name']}")
        func: _run_T | None = getattr(f_mod, "run", None)
        if func is None:
            raise NotImplementedError(f"cant find run function in factor {f_raw['name']}")
        factor_merged = {x["name"]: x["v"] for x in f_raw["params"]}
        factor_merged.update(factor_overrides.get(f_raw.get("uuid", ""), {}))
        t.cast(dict, getattr(f_mod, "params")).update(factor_merged)
        t.cast(dict, getattr(f_mod, "context")).update(ctx)
        data = func(data)

    # 运行策略
    strategy_mod = Core.load_file(strategy_name, src_raw["strategy"]["content"])
    if strategy_mod is None:
        raise ValueError(f"failed to load strategy module: {strategy_name}")
    strategy_func: _run_T | None = getattr(strategy_mod, "run", None)
    if strategy_func is None:
        raise NotImplementedError(f"cant find run function in strategy {strategy_name}")
    strategy_merged = {x["name"]: x["v"] for x in strategy_params}
    strategy_merged.update(strat_overrides)
    t.cast(dict, getattr(strategy_mod, "params")).update(strategy_merged)
    t.cast(dict, getattr(strategy_mod, "context")).update(ctx)
    data = strategy_func(data)

    # 将多参数覆盖值合并到 strategy.params（保留前缀以区分来源）
    for key, val in multi_params.items():
        strategy_merged[key] = val
    strategy_mod.__setattr__("params", strategy_merged)

    return strategy_mod, data


def _run_task(
    src_raw: dict[str, t.Any],
    data: pd.DataFrame,
    multi_params: dict[str, t.Any],
    runner: Runner_T,
    ctx: ContextBase,
    uuid: str,
) -> None:
    """
    进程池任务函数（模块级，可被 pickle 序列化）。
    multi_params 使用带前缀的扁平键：
      - "_strategy.{param}" → 策略参数覆盖
      - "_factor.{uuid}.{param}" → 因子参数覆盖
    """
    pd.set_option("mode.chained_assignment", None)
    if data.empty:
        TaskCache.set_result(uuid, "data empty", False)
        loguru.logger.warning(f"task {uuid} droped by empty data")
        return
    try:
        loguru.logger.debug(
            f"start executing strategy {src_raw['strategy']['name']} with overrides={multi_params}, task id: {uuid}"
        )
        strategy_mod, data = _run_pipeline(src_raw, data, ctx, multi_params)
        # backtest
        result = runner(data, ctx, getattr(strategy_mod, "params", {}), multi_params.__len__() != 0)
    except Exception as e:  # noqa: BLE001
        TaskCache.set_result(uuid, traceback.format_exc(), False)
        loguru.logger.error(f"task {uuid} failed: {e.__str__()}")
    else:
        TaskCache.set_result(uuid, result)
        loguru.logger.debug(f"task {uuid} success")


class Calculator:
    MAX_CARTESIAN = 1000

    # 表达式求值安全内置函数
    _SAFE_BUILTINS: t.ClassVar = {
        "range": range, "len": len, "int": int, "float": float,
        "str": str, "bool": bool, "list": list, "abs": abs,
        "min": min, "max": max, "round": round, "sum": sum,
    }

    def __init__(self):
        raise NotImplementedError("Calculator is an abstract class")

    @staticmethod
    def _cartesian_product(multi_params: dict[str, list[t.Any]]) -> list[dict[str, t.Any]]:
        """计算笛卡尔积，返回扁平键组合列表。"""
        if not multi_params:
            return [{}]
        keys = list(multi_params.keys())
        values = [multi_params[k] for k in keys]
        combos = list(itertools.product(*values))
        return [dict(zip(keys, combo)) for combo in combos]

    @staticmethod
    async def async_task(
        strategy_uuid: str,
        start_time: int,
        end_time: int,
        target: str | t.Sequence[str] | None,
        period: DataPeriod = DataPeriod.HOUR,
        multi_params: dict[str, list[t.Any]] | None = None,
        multi_expressions: dict[str, str] | None = None,
        runner_name: str = "default",
        exchange: str | None = None
    ):
        """
        无等待任务。
        multi_params:   {"_strategy.param": [v1, v2], "_factor.uuid.param": [v3, v4], ...}
        multi_expressions: {"_strategy.param": "range(1,10)", ...} 优先级高于 multi_params 同名键
        """
        if multi_params is None:
            multi_params = {}
        if multi_expressions is None:
            multi_expressions = {}

        # 解析表达式，覆盖 multi_params 中同名键的值
        merged: dict[str, list[t.Any]] = dict(multi_params)
        for key, expr in multi_expressions.items():
            try:
                result = eval(expr, {"__builtins__": Calculator._SAFE_BUILTINS}, {})
                if not isinstance(result, (list, tuple)):
                    raise TypeError(f"表达式结果必须为列表，实际为: {type(result).__name__}")
                merged[key] = list(result)
            except Exception as e:
                raise ValueError(f"参数 '{key}' 表达式解析失败: {e}") from e

        combos = Calculator._cartesian_product(merged)
        combo_count = len(combos)
        if combo_count > Calculator.MAX_CARTESIAN:
            raise ValueError(
                f"参数组合数 {combo_count} 超过上限 {Calculator.MAX_CARTESIAN}，请减少参数或取值"
            )

        # TODO: 非本地部署时使用mq实现
        if combo_count <= 1:
            ids = str(uuid.uuid4())
            asyncio.create_task(
                Calculator.execute(
                    ids, strategy_uuid, start_time, end_time, target, period,
                    runner_name=runner_name, multi_params=combos[0] if combos else {}, exchange=exchange
                )
            )
            return ids

        ids = [str(uuid.uuid4()) for _ in range(combo_count)]
        asyncio.create_task(
            Calculator.execute(
                ids, strategy_uuid, start_time, end_time, target, period,
                runner_name=runner_name, multi_params_list=combos, exchange=exchange
            )
        )
        return ids

    @staticmethod
    async def execute(
        ids: str | list[str],
        strategy_uuid: str,
        start_time: int,
        end_time: int,
        target: str | t.Sequence[str] | None,
        period: DataPeriod = DataPeriod.HOUR,
        runner_name: str = "default",
        multi_params: dict[str, t.Any] | None = None,
        multi_params_list: list[dict[str, t.Any]] | None = None,
        exchange: str | None = None
    ):
        """执行策略计算（主进程预处理后立即返回 task_id）。"""
        try:
            src_raw = await Core.prepare_raw(strategy_uuid)
            data = await load_data(
                start_time, end_time, target if target is not None else [], period, exchange=exchange
            )
            runner: Runner_T | None = await get_runner(runner_name)
            if runner is None:
                raise ValueError(f"加载回测执行器失败：{runner_name}")

            ctx: ContextBase = {
                "is_living": False,
                "start_time": start_time,
                "end_time": end_time,
                "target": target,
                "period": period.value,
            }

            if multi_params_list:
                for id, params in zip(t.cast(list, ids), multi_params_list):
                    Core.submit_task(
                        _run_task, src_raw, data, params, runner, ctx, id
                    )
            else:
                Core.submit_task(
                    _run_task, src_raw, data, multi_params or {}, runner, ctx, ids
                )
        except Exception as e:  # noqa: BLE001
            if isinstance(ids, str):
                TaskCache.set_result(ids, f"task-{ids} prepare data failed:{e.__str__()}", False)
            else:
                for id in ids:
                    TaskCache.set_result(id, f"task-{id} prepare data failed:{e.__str__()}", False)
                    
    
    @staticmethod
    def _load_living_data(exchange: str, targets: t.Sequence[str], period: DataPeriod) -> pd.DataFrame:
        """从缓存读取实盘原始数据（Binance K 线），拼接为与回测一致的 DataFrame。"""
        if exchange != 'binance':
            raise NotImplementedError(f"unsupported exchange: {exchange}")
        cache = get_cache()
        interval = {
            DataPeriod.MINUTE: '1m',
            DataPeriod.HOUR: '1h',
            DataPeriod.DAY: '1d',
        }[period]
        frames: list[pd.DataFrame] = []
        for sym in targets:
            key = f'{CacheName.Binance_Kline.value}::{interval}::{sym}'
            raw = cache.get(key)
            if not raw:
                loguru.logger.warning(f"living_run: cache miss {key}")
                continue
            df = pd.DataFrame(raw, columns=KLINE_COLUMNS)
            for col in ('open', 'high', 'low', 'close', 'volume', 'quote_asset_volume',
                        'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume'):
                df[col] = pd.to_numeric(df[col], errors='coerce').astype(float)
            for col in ('open_time', 'close_time', 'number_of_trades', 'ignore'):
                df[col] = pd.to_numeric(df[col], errors='coerce').astype('int64')
            df['code'] = sym
            frames.append(df)
        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, ignore_index=True)

    @staticmethod
    async def living_run(ctx: ContextBase) -> tuple[pd.DataFrame, dict[str, t.Any]]:
        """实盘策略执行：从缓存读取原始数据，运行因子+策略，返回 (带信号列的 DataFrame, 策略参数)。"""
        strategy_uuid = t.cast(str, ctx.get('strategy_uuid'))
        exchange = t.cast(str, ctx.get('exchange', ''))
        target = ctx.get('target')
        period = DataPeriod(t.cast(int, ctx.get('period', DataPeriod.HOUR.value)))
        e_time = t.cast(int, ctx.get('excute_strict_time', 0))

        src_raw = await Core.prepare_raw(strategy_uuid)

        targets: list[str] = [target] if isinstance(target, str) else list(target or [])
        data = Calculator._load_living_data(exchange, targets, period)
        if data.empty:
            loguru.logger.warning(
                f"living_run: no cached data, exchange={exchange} targets={targets} period={period.name}"
            )
            return data, {}

        pipeline_ctx: ContextBase = {
            'is_living': True,
            'target': target,
            'period': t.cast(t.Literal[60, 3600, 86400], period.value),
            'excute_strict_time': e_time,
        }

        strategy_mod, data = _run_pipeline(src_raw, data, pipeline_ctx, {})
        params: dict[str, t.Any] = t.cast(dict, getattr(strategy_mod, 'params', {}))
        return data, params