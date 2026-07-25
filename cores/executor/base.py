from concurrent.futures import ProcessPoolExecutor
import json
import os
import typing as t
from types import ModuleType
import importlib.util
from database.base import async_session
from database.model import Strategy, Factor
from utils.logger import setup_logging
from sqlalchemy import select


class Core():
    """
    """
    _pool = ProcessPoolExecutor(max_workers=os.cpu_count() or 1, max_tasks_per_child=100, initializer=setup_logging)
    
    @staticmethod
    def load_file(name: str, content: str) -> ModuleType | None:
        """
        加载策略字符串为模块
        """
        mod = importlib.util.spec_from_loader(name, loader=None)
        if mod is None:
            return None
        mod = importlib.util.module_from_spec(mod)
        try:
            exec(content, mod.__dict__)
        except Exception:
            return None
        return mod

    @staticmethod
    async def prepare_raw(strategy_uuid: str) -> t.Dict[str, t.Any]:
        """
        准备策略原始数据（可被 pickle 序列化，用于进程池传递）。
        仅查询数据库获取策略/因子的源码和参数，不加载为模块对象。

        Returns:
            {
                'strategy': {'name': str, 'content': str, 'params': list},
                'factors': [{'name': str, 'content': str, 'params': list}, ...]
            }
        """
        async with async_session() as s:
            stra = (await s.execute(select(Strategy).filter(Strategy.uuid == strategy_uuid))).scalar()
            if stra is None:
                raise ValueError(f"strategy {strategy_uuid} not found")
            factor_uuids: t.List[str] = json.loads(t.cast(str, stra.factors))
            factors = (await s.execute(select(Factor).filter(Factor.uuid.in_(factor_uuids)))).scalars().all()
            if set(factor_uuids) != set([x.uuid for x in factors]):
                raise ValueError(f"factors {factor_uuids} not found")
            
            factors_map: t.Dict[str, Factor] = {str(x.uuid): x for x in factors}

        factor_src: t.List[t.Dict[str, t.Any]] = []
        for u in factor_uuids:
            f = factors_map.get(u)
            if f is None:
                raise ValueError(f'因子未找到，uuid-{u}')
            factor_src.append({
                    'name': f.name,
                    'uuid': f.uuid,
                    'content': f.content,
                    'params': t.cast(list, f.params),
                })
        
        return {
            'strategy': {
                'name': stra.name,
                'content': stra.content,
                'params': t.cast(list, stra.params),
            },
            'factors': factor_src
        }
    
    def __init__(self):
        pass
    
    @classmethod
    def submit_task(cls, f: t.Callable, *args, **kwargs):
        """
        提交策略计算任务，返回任务id
        """
        cls._pool.submit(f, *args, **kwargs)