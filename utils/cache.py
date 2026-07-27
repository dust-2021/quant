import os
import typing as t
from collections import namedtuple

from diskcache import Cache

from config import BASE_PATH

TaskResult = namedtuple('TaskResult', ['success', 'data'])

class TaskCache:
    _cache = Cache(os.path.join(BASE_PATH, 'locals/task.db'))
    
    @classmethod
    def set_result(cls, id: str, value: t.Any, success=True):
        cls._cache.set(f'result-{id}', value=TaskResult(success, value), expire=3600)
        
    @classmethod
    def get_result(cls, id: str) -> TaskResult | None:
        return t.cast(TaskResult | None, cls._cache.get(f'result-{id}'))