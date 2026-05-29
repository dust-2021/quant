import datetime
import json
from database.model import Strategy, StrategyGroup
from database.base import async_session
from utils.middleware.auth import auth
from utils.middleware.type_checker import json_post_checker
from aiohttp import web
from utils.types import app_response, AppCode
from sqlalchemy import select, func
import typing as t
import uuid


@auth(perm=["strategy.read"])
async def get_strategy(request: web.Request):
    async with async_session() as s:
        strategy = await s.execute(
            select(Strategy).filter_by(name=request.match_info["name"])
        )
        strategy = strategy.all()
    if strategy.__len__() == 0:
        return web.json_response(
            app_response(code=AppCode.NOT_FOUND, msg="strategy not found")
        )
    return web.json_response(app_response(data=[x[0].to_dict() for x in strategy]))


@auth(perm=["strategy.read"])
async def get_strategy_group(request: web.Request):
    async with async_session() as s:
        strategy_group = await s.execute(select(StrategyGroup))
        strategy_group = strategy_group.all()
    return web.json_response(
        app_response(data=[x[0].to_dict() for x in strategy_group])
    )


@auth(perm=["strategy.read"])
async def get_strategy_list(request: web.Request):
    async with async_session() as s:
        strategy_list = await s.execute(
            select(
                StrategyGroup.name.label("group_name"),
                Strategy.name.label("strategy_name"),
                Strategy.uuid,
                func.count(Strategy.id).alias("count"),
            )
            .join(StrategyGroup, Strategy.group == StrategyGroup.id)
            .group_by(Strategy.name)
        )
        strategy_list = strategy_list.all()
    return web.json_response(
        app_response(data=[strategy.to_dict() for strategy in strategy_list])
    )


@auth(perm=["strategy.write"])
@json_post_checker(
    necessary_keys={"version": str, "name": str, "group": str},
    optional_keys={
        "uuid": str,
        "description": str,
        "params": dict,
        "factors": list,
        "content": str,
        "factor_params": dict,
    },
)
async def update_strategy(
    request: web.Request, data: t.Optional[t.Dict[str, t.Any]] = None
):
    if data is None:
        return web.json_response(
            app_response(code=AppCode.DATA_INVALID, msg="data is None")
        )
    async with async_session() as s:
        try:
            if data.get("uuid") == "": # 新增
                stra = Strategy(
                    uuid=uuid.uuid4().hex,
                    group=data.get("group"),
                    name=data.get("name"),
                    version=data.get("version"),
                    description=data.get("description", ""),
                    params=data.get("params", {}),
                    factors=json.dumps(data.get("factors", [])),
                    content=data.get("content", ""),
                )
                s.add(stra)
            else:
                resp = await s.execute(select(Strategy).filter_by(uuid=data["uuid"]))
                resp = resp.first()
                if resp is None:
                    return web.json_response(
                        app_response(code=AppCode.NOT_FOUND, msg="strategy not found")
                    )
                stra = resp[0]
                stra.update_time = int(datetime.datetime.now().timestamp())
                stra.name = data.get("name", stra.name)
                stra.description = data.get("description", stra.description)
                stra.params = data.get("params", stra.params)
                stra.factors = json.dumps(data.get("factors", []))
                stra.content = data.get("content", stra.content)
                await s.flush()
        except Exception as e:
            await s.rollback()
            return web.json_response(
                app_response(code=AppCode.UNKNOWN_ERROR, msg=str(e))
            )
        finally:
            await s.commit()
    return web.json_response(app_response(data=True))


@json_post_checker(necessary_keys={"name": str, "version": str})
async def execute_strategy(
    request: web.Request, data: t.Optional[t.Dict[str, t.Any]] = None
):
    if data is None:
        return web.json_response(
            app_response(code=AppCode.DATA_INVALID, msg="data is None")
        )
    return web.json_response(app_response(data=uuid.uuid4().hex))


async def strategy_result(request: web.Request):
    id = request.match_info["id"]
    return web.json_response(app_response(data=id))


rules = [
    web.RouteDef("GET", "/strategy/{name}", get_strategy, {}),
    web.RouteDef("GET", "/strategy/group", get_strategy_group, {}),
    web.RouteDef("GET", "/strategy/list", get_strategy_list, {}),
    web.RouteDef("POST", "/strategy/update", update_strategy, {}),
    web.RouteDef("POST", "/strategy/execute", execute_strategy, {}),
    web.RouteDef("GET", "/strategy/result/{id}", strategy_result, {}),
]
