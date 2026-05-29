import typing as t
import enum
import pandas as pd

class BaseFactorType(enum.Enum):
    OPEN = 'open'
    CLOSE = 'close'
    HIGH = 'high'
    LOW = 'low'
    VOL = 'vol'
    

class Factor:
    def __init__(self, name: str, ) -> None:
        self.name = name
        
    
    def __call__(self, data: pd.DataFrame):
        pass