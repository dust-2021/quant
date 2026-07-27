import enum
import typing as t

import pandas as pd

from .base import Core


class BaseFactorType(enum.Enum):
    OPEN = 'open'
    CLOSE = 'close'
    HIGH = 'high'
    LOW = 'low'
    VOL = 'vol'
    

class Factor:
    def __init__(self, name: str, content: str, **kwargs) -> None:
        self.name = name
        self.mod = Core.load_file(name, content)
        self.mod.__setattr__('context', kwargs)

    def __call__(self, data: pd.DataFrame):
        func: t.Callable | None = getattr(self.mod, 'run', None)
        if func is None:
            raise NotImplementedError("factor must have a run function")
        return func(data)