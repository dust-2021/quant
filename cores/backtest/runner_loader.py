import typing as t
from .runners.default import run as default_runner
import pandas as pd
from database.base import async_session
from database.model import Calculator as CalculatorModel
from cores.executor.base import Core
from sqlalchemy import select

Runer_T: t.TypeAlias = t.Callable[[pd.DataFrame, t.Dict[str, t.Any], t.Dict[str, t.Any], t.Dict[str, t.Any]], t.Any]

async def get_runner(name: str) -> t.Optional[Runer_T]:
    if name == 'default':
        return default_runner
    async with async_session() as s:
        calc = (await s.execute(select(CalculatorModel).filter(CalculatorModel.name == name))).scalar()
        if calc is None:
            return None
        content: str = t.cast(str, calc.content)
    mod = Core.load_file(name, content)
    if mod is None:
        return None
    return getattr(mod, "run", None)