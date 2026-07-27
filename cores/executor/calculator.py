import asyncio
import itertools
import traceback
import typing as t
import uuid

import loguru
import pandas as pd

from cores.backtest.runner_loader import Runner_T, get_runner
from database.base import DataPeriod
from database.data_center import load_data
from utils.cache import TaskCache
from utils.scheduler import aSche

from .base import Core

# 多参数键前缀
PREFIX_STRATEGY = "_strategy."
PREFIX_FACTOR = "_factor."

_run_T: t.TypeAlias = t.Callable[[pd.DataFrame], pd.DataFrame]  # noqa: PYI042


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


def _run_task(
    src_raw: dict[str, t.Any],
    data: pd.DataFrame,
    multi_params: dict[str, t.Any],
    runner: Runner_T,
    ctx: dict[str, t.Any],
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
        strategy_name: str = src_raw["strategy"]["name"]
        strategy_params: list[dict[str, t.Any]] = src_raw["strategy"]["params"]
        factors_raw: list[dict[str, t.Any]] = src_raw["factors"]

        # 拆分带前缀的多参数
        strat_overrides, factor_overrides = _split_prefixed_params(multi_params)

        loguru.logger.debug(
            f"start executing strategy {strategy_name} with overrides={multi_params}, task id: {uuid}"
        )

        # 运行因子（使用对应 uuid 的覆盖参数）
        for f_raw in factors_raw:
            f_mod = Core.load_file(f_raw["name"], f_raw["content"])
            if f_mod is None:
                raise ValueError(f"failed to load factor module: {f_raw['name']}")
            func: _run_T | None = getattr(f_mod, "run", None)
            if func is None:
                raise NotImplementedError(f"cant find run function in factor {f_raw['name']}")
            # 合并因子默认参数 + 该因子专属的覆盖参数
            factor_merged = {x["name"]: x["v"] for x in f_raw["params"]}
            factor_merged.update(factor_overrides.get(f_raw.get("uuid", ""), {}))
            setattr(f_mod, "params", factor_merged)  # noqa: B010
            setattr(f_mod, "context", ctx)  # noqa: B010
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
        strategy_mod.__setattr__("params", strategy_merged)
        strategy_mod.__setattr__("context", ctx)
        data = strategy_func(data)

        # 将多参数覆盖值合并到 strategy.params（保留前缀以区分来源）
        for key, val in multi_params.items():
            strategy_merged[key] = val
        strategy_mod.__setattr__("params", strategy_merged)

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

            ctx = {
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
    async def simulation(strategy_uuid: str, target: str | t.Sequence[str] | None, min_line: int = 999, period: DataPeriod = DataPeriod.HOUR,
                         runner_name: str = 'default'
                         ):
        async def f():
            pass

        
        aSche.add_job(f, trigger='cron')