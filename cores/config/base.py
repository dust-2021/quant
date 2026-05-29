from uuid import uuid4 as uuid
from typing import Optional, Dict, Any, Union
from datetime import datetime, date

noise_time = Union[datetime, date, str, int]

class BaseConfig:
    """
    """
    def __init__(self, name: str, s, **kwargs):
        self.name = name
        self.id = uuid().__str__()
        self.exeArgs: Dict[str, Any] = kwargs



