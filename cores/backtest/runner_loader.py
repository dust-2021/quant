import typing as t

import pandas as pd
from sqlalchemy import select

from cores.executor.base import Core
from database.base import async_session
from database.model import Calculator as CalculatorModel
from utils.types import Runner_Res

from .runners.default import run as default_runner

Runner_T: t.TypeAlias = t.Callable[[pd.DataFrame, dict[str, t.Any], dict[str, t.Any], bool], Runner_Res]

async def get_runner(name: str) -> Runner_T | None:
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