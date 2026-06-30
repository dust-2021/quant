from functools import partial
import typing as t
import uuid
import traceback

import loguru

from cores.backtest.runner_loader import get_runner, Runer_T
from .base import Core
import pandas as pd
from database.data_center import DataPeriod, load_data
from utils.cache import TaskCache

def _run_task(
    src_raw: t.Dict[str, t.Any],
    data: pd.DataFrame,
    multi: bool, multi_param: str, runner: Runer_T,
    ctx: t.Dict[str, t.Any],
    uuid: str, v: t.Any = None,
) -> None:
    """
    进程池任务函数（模块级，可被 pickle 序列化）。
    不返回结果，直接将计算结果存入缓存，key 为 uuid。

    所有 DB 查询已在主进程完成，此处仅做纯 CPU 计算：
    从原始字符串加载模块 → 运行因子 → 运行策略 → 回测。

    @param src_raw: Core.prepare_raw() 的返回值
    @param data:    主进程预加载的行情数据
    @param uuid:    任务id
    @param v:       multi_param 的值，仅在 multi 为 True 时使用
    """
    pd.set_option('mode.chained_assignment', None)
    if data.empty:
        TaskCache.set_result(uuid, 'data empty', False)
        loguru.logger.info(f'task {uuid} droped by empty data')
        return
    try:
        strategy_name: str = src_raw['strategy']['name']

        # 从原始字符串重建模块（纯 CPU，无 DB）
        strategy_mod = Core.load_file(strategy_name, src_raw['strategy']['content'])
        if strategy_mod is None:
            raise ValueError(f"failed to load strategy module: {strategy_name}")
        strategy_params: t.List[t.Dict[str, t.Any]] = src_raw['strategy']['params']
            
        factors_raw: t.List[t.Dict[str, t.Any]] = src_raw['factors']
        loguru.logger.info(f"start executing strategy {strategy_name} with multi_param={multi_param}={v}, task id: {uuid}, factors: {[x['name'] for x in factors_raw]}")
        for f_raw in factors_raw:
            f_mod = Core.load_file(f_raw['name'], f_raw['content'])
            if f_mod is None:
                raise ValueError(f"failed to load factor module: {f_raw['name']}")
            func = getattr(f_mod, 'run', None)
            if func is None:
                raise NotImplementedError(f"cant find run function in factor {f_raw['name']}")
            setattr(f_mod, 'params', {x['name']: x['v'] for x in f_raw['params']})
            setattr(f_mod, 'context', ctx)
            func(data)

        strategy_func: t.Optional[t.Callable] = getattr(strategy_mod, 'run', None)
        if strategy_func is None:
            raise NotImplementedError(f"cant find run function in strategy {strategy_name}")
        strategy_mod.__setattr__('params', {x['name']: x['v'] for x in strategy_params})
        strategy_mod.__setattr__('context', ctx)
        if multi:
            strategy_mod.params[multi_param] = v
        strategy_func(data)
        
        # backtest
        result = runner(data, ctx, getattr(strategy_mod, 'params', dict()), multi)
    except Exception as e:
        TaskCache.set_result(uuid, traceback.format_exc(), False)
        loguru.logger.info(f'task {uuid} fialed: {e.__str__()}')
    else:
        TaskCache.set_result(uuid, result)
        loguru.logger.info(f'task {uuid} success')


class Calculator:
    
    def __init__(self):
        raise NotImplementedError("Calculator is an abstract class")
    
    @staticmethod
    async def execute(strategy_uuid: str, start_time: int, end_time: int, target: t.Union[str, t.Sequence[str], None], period: DataPeriod = DataPeriod.HOUR,
                multi: bool = False, multi_param: str = "", multi_values: t.Sequence[t.Any] = [],
                runner_name: str = "default", multi_expression: str = "") -> t.Union[str, t.List[str]]:
        """
         执行策略计算（主进程预处理后立即返回 task_id）。

         strategy_uuid: 策略uuid
         start_time: 开始时间
         end_time: 结束时间
         target: 计算目标
         period: 计算周期
         runner_name: 回测执行器名称
         multi_expression: Python 列表推导式，优先级高于 multi_values
         返回值：单个 task_id（multi=False）或 task_id 列表（multi=True）
        """
        # === 主进程预处理：策略参数 + 行情数据（只做一次，worker 共享） ===
        src_raw = await Core.prepare_raw(strategy_uuid)
        data = await load_data(start_time, end_time, target if target is not None else [], period)
        runner: t.Optional[Runer_T] = await get_runner(runner_name)
        if runner is None:
            raise ValueError(f'加载回测执行器失败：{runner_name}')

        # 推导式优先级高于直接传值
        if multi and multi_expression:
            try:
                safe_builtins = {
                    'range': range, 'len': len, 'int': int, 'float': float,
                    'str': str, 'bool': bool, 'list': list, 'abs': abs,
                    'min': min, 'max': max, 'round': round, 'sum': sum,
                }
                multi_values = eval(multi_expression, {"__builtins__": safe_builtins}, {})
                if not isinstance(multi_values, (list, tuple)):
                    raise ValueError(f"表达式结果必须为列表，实际为: {type(multi_values).__name__}")
            except Exception as e:
                raise ValueError(f"推导式解析失败: {e}") from e

        ctx = {'start_time': start_time, 'end_time': end_time, 'target': target, 'period': period.value}
        if multi:
            ids = [str(uuid.uuid4()) for _ in multi_values]
            task_func = partial(_run_task, src_raw, data, multi, multi_param, runner, ctx)
            Core.map_task(task_func, ids, multi_values)
            return ids
        else:
            task_id = str(uuid.uuid4())
            Core.submit_task(_run_task, src_raw, data, False, multi_param, runner, ctx, task_id)
            return task_id
    
    