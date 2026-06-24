import typing as t
from .runners.default import run as default_runner
import pandas as pd
from database.base import sync_session
from database.model import Calculator as CalculatorModel
from cores.executor.base import Core

Runer_T: t.TypeAlias = t.Callable[[pd.DataFrame, t.Dict[str, t.Any], t.Dict[str, t.Any]], t.Any]

def get_runner(name: str) -> t.Optional[Runer_T]:
    if name == 'default':
        return default_runner
    with sync_session() as s:
        calc = s.query(CalculatorModel).filter(CalculatorModel.name == name).first()
        if calc is None:
            return None
        content: str = t.cast(str, calc.content)
    mod = Core.load_file(name, content)
    if mod is None:
        return None
    return getattr(mod, "run", None)