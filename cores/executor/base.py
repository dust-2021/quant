from concurrent.futures import ProcessPoolExecutor
import os
import typing as t
from types import ModuleType
import importlib.util
import pandas as pd
from database.base import sync_session, db_path
from database.model import Strategy, Factor, Config
import sqlite3
from dask import dataframe as dd
from dask.delayed import delayed


class BaseExecutor():
    """
    """
    name: str = 'base'
    _pool = ProcessPoolExecutor(max_workers=os.cpu_count() or 1, max_tasks_per_child=1)
    _result: t.Dict[str, t.Any] = {}
    db_conn: sqlite3.Connection = sqlite3.connect(db_path)
    
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
        except Exception as e:
            return None
        return mod
    
    @staticmethod
    def load_strategy(strategy: str) -> ModuleType | None:
        """
        加载策略
        """
        with sync_session() as s:
            stra = s.query(Strategy).filter(Strategy.name == strategy).first()
            if stra is None:
                return None
            factor = stra.factors.split(',')
            factors = s.query(Factor).filter(Factor.name.in_(stra.factors.split(','))).all()
            if set(factor) != set([x.name for x in factors]):
                return None
    
    def load_data(self) -> pd.DataFrame:
        query = """
        select * from data where time >= ? and time <= ?
        """
        data = pd.read_sql_query(query, self.db_conn, params=self.time)
        
        return data
    
    def __init__(self, strategy: str, time: t.Tuple[int, int], factors: t.Optional[t.Sequence[str]] = None):
        self.strategy = strategy
        self.time = time
        self.factors = factors
        self.context: t.Dict[str, t.Any] = {}
    
    def _run(self, *args) -> t.Any:
        data = self.load_data()
        stra = self.load_file(self.strategy, self.strategy)
        if stra is None:
            return None
        setattr(stra, 'context', self.context)
        try:
            func = getattr(stra, 'run')
            if not callable(func):
                return None
            return func(data, *args)
        except Exception:
            return None
        
    def get_result(self, uuid: str) -> t.Any:
        return self._result.get(uuid, None)
    
    def __call__(self, args: t.Sequence[t.Tuple[t.Any]]) -> t.Any:
        if len(args) == 0:
            return []
        if self._pool is None:
            raise NotImplementedError("server mode not support")
        return self._pool.map(self._run, [(self, *x) for x in args])


class CTAExecutor(BaseExecutor):
    """
    """
    name: str = 'cta'
    
    def __init__(self):
        pass
