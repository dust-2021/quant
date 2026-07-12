from sqlalchemy import select

from cores.executor.calculator import Calculator
from utils.cache import TaskCache
from database.base import DataPeriod
from utils.middleware.type_checker import json_post_checker
from utils.types import AppCode, app_response
from aiohttp import web
import typing as t
from database.model import Calculator as CalculatorModel
from database.base import async_session
import numpy as np


@json_post_checker(necessary_keys={"uuid": str, "start_time": int, "end_time": int},
                   optional_keys={"target": list, "period": int,
                                  "multi": bool, "multi_param": str, "multi_values": list, "runner_name": str,
                                  "multi_expression": str
                                  })
async def execute_strategy(
    request: web.Request, data: t.Optional[t.Dict[str, t.Any]] = None
):
    if data is None:
        return web.json_response(
            app_response(code=AppCode.DATA_INVALID, msg="data is None")
        )
    period = DataPeriod.from_seconds(data.get("period", DataPeriod.HOUR.value))
    if period is None:
        return web.json_response(
            app_response(code=AppCode.DATA_INVALID, msg="invalid period")
        )
    result_id = await Calculator.execute(
        strategy_uuid=data["uuid"],
        start_time=data["start_time"],
        end_time=data["end_time"],
        target=data.get("target"),
        period=period,
        multi=data.get("multi", False),
        multi_param=data.get("multi_param", ""),
        multi_values=data.get("multi_values", []),
        runner_name=data.get("runner_name", "default"),
        multi_expression=data.get("multi_expression", "")
    )
    return web.json_response(app_response(data=result_id))

# NaN 替换为 None，确保 JSON 序列化安全
def _sanitize(v):
    if isinstance(v, float) and np.isnan(v):
        return None
    if isinstance(v, list):
        return [None if isinstance(x, float) and np.isnan(x) else x for x in v]
    return v


async def strategy_result(request: web.Request):
    id = request.match_info["id"]
    if (res := TaskCache.get_result(id)) is None:
        return web.json_response(app_response(code=AppCode.NOT_FOUND, msg="unkown task id or already expire"))
    if not res.success:
        return web.json_response(app_response(code=AppCode.EXECUTE_FAILED, msg=f"task failed: {res.data}"))

    data =  {k: _sanitize(v) for k, v in res.data.items()}
    return web.json_response(app_response(data=data))


async def get_runner_list(request: web.Request):
    async with async_session() as s:
        runners = await s.execute(select(CalculatorModel.name))
        runners = runners.scalars().all()
        await s.commit()
    res = set(runners)
    res.add("default")
    return web.json_response(app_response(data=list(res)))


rules = [
    web.RouteDef("POST", "/execute", execute_strategy, {}),
    web.RouteDef("GET", "/execute/result/{id}", strategy_result, {}),
    web.RouteDef("GET", "/execute/runners", get_runner_list, {}),
]