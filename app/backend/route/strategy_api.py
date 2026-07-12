import datetime
import json
from app.backend.route.execute import execute_strategy, strategy_result
from database.model import Strategy, StrategyGroup, Factor
from database.base import async_session
from utils.middleware.auth import auth
from utils.middleware.type_checker import json_post_checker
from aiohttp import web
from utils.types import app_response, AppCode
from sqlalchemy import select
import typing as t
import uuid


@auth(perm=["strategy.read"])
async def get_strategy(request: web.Request):
    async with async_session() as s:
        strategy = await s.execute(
            select(Strategy).filter_by(uuid=request.match_info["uuid"])
        )
        strategy = strategy.first()
    if strategy is None:
        return web.json_response(
            app_response(code=AppCode.NOT_FOUND, msg="strategy not found")
        )

    # 解析因子UUID列表
    factor_uuids = json.loads(strategy[0].factors) if strategy[0].factors else []
    # 加载因子详情
    factor_details = await Factor.load(factor_uuids) if factor_uuids else []
    factor_infos = [{
        "uuid": f.uuid,
        "name": f.name,
        "version": f.version,
        "description": f.description,
    } for f in factor_details] if factor_details else []

    return web.json_response(app_response(data={
        "uuid": strategy[0].uuid,
        "name": strategy[0].name,
        "group": strategy[0].group,
        "version": strategy[0].version,
        "description": strategy[0].description,
        "params": strategy[0].params,
        "factors": factor_uuids,
        "factor_infos": factor_infos,
        "content": strategy[0].content,
    }))


@auth(perm=["strategy.read"])
async def get_strategy_group(request: web.Request):
    async with async_session() as s:
        strategy_group = await s.execute(select(StrategyGroup))
        strategy_group = strategy_group.all()
    return web.json_response(
        app_response(data=[{'id': x[0].id, 'name': x[0].name, 'description': x[0].description} for x in strategy_group])
    )


@auth(perm=["strategy.read"])
async def get_strategy_list(request: web.Request):
    async with async_session() as s:
        strategy_list = await s.execute(
            select(
                StrategyGroup.name.label("group_name"),
                Strategy.name.label("strategy_name"),
                Strategy.uuid,
                Strategy.version,
                Strategy.description,
            )
            .join(Strategy, Strategy.group == StrategyGroup.name, isouter=True)
        )
        strategy_list = strategy_list.all()
    return web.json_response(
        app_response(data=[{'group_name': strategy[0], 'strategy_name': strategy[1], 'uuid': strategy[2], 'version': strategy[3], 'description': strategy[4] or ''} for strategy in strategy_list])
    )


@auth(perm=["strategy.write"])
@json_post_checker(
    necessary_keys={"version": str, "name": str, "group": str},
    optional_keys={
        "uuid": str,
        "description": str,
        "params": list,
        "factors": list,
        "content": str,
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
        new_uuid = None
        try:
            if data.get("uuid") == "": # 新增
                new_uuid = uuid.uuid4().hex
                stra = Strategy(
                    uuid=new_uuid,
                    group=data.get("group"),
                    name=data.get("name"),
                    version=data.get("version"),
                    description=data.get("description", ""),
                    params=data.get("params", []),
                    factors=json.dumps(data.get("factors", [])),
                    content=data.get("content", ""),
                )
                if await stra.exist():
                    return web.json_response(
                        app_response(code=AppCode.DATA_INVALID, msg="strategy already exists")
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
                stra.group = data.get("group", stra.group)
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
    return web.json_response(app_response(data=new_uuid if data.get("uuid") == "" else True))


@auth(perm=["strategy.write"])
@json_post_checker(
    necessary_keys={"name": str},
    optional_keys={"description": str},
)
async def create_strategy_group(
    request: web.Request, data: t.Optional[t.Dict[str, t.Any]] = None
):
    if data is None:
        return web.json_response(
            app_response(code=AppCode.DATA_INVALID, msg="data is None")
        )
    async with async_session() as s:
        try:
            # 检查分组名是否已存在
            existing = await s.execute(
                select(StrategyGroup).filter_by(name=data["name"])
            )
            if existing.scalar() is not None:
                return web.json_response(
                    app_response(code=AppCode.DATA_INVALID, msg="分组名已存在")
                )
            group = StrategyGroup(
                name=data["name"],
                description=data.get("description", ""),
            )
            s.add(group)
            await s.commit()
            return web.json_response(app_response(data={
                "id": group.id,
                "name": group.name,
                "description": group.description,
            }))
        except Exception as e:
            await s.rollback()
            return web.json_response(
                app_response(code=AppCode.UNKNOWN_ERROR, msg=str(e))
            )


@auth(perm=["strategy.write"])
@json_post_checker(necessary_keys={"name": str})
async def delete_strategy_group(request: web.Request, data: t.Optional[t.Dict[str, t.Any]] = None):
    """删除分组，并将该分组下所有策略移到 default 分组"""
    if data is None:
        return web.json_response(
            app_response(code=AppCode.DATA_INVALID, msg="data is None")
        )
    group_name = data["name"]
    if group_name == "default":
        return web.json_response(
            app_response(code=AppCode.DATA_INVALID, msg="不能删除默认分组")
        )
    async with async_session() as s:
        try:
            # 确保 default 分组存在
            default_group = await s.execute(
                select(StrategyGroup).filter_by(name="default")
            )
            if default_group.scalar() is None:
                s.add(StrategyGroup(name="default", description="默认分组"))
                await s.flush()

            # 将该分组下所有策略的 group 改为 default
            await s.execute(
                Strategy.__table__.update()
                .where(Strategy.group == group_name)
                .values(group="default")
            )

            # 删除分组
            group = await s.execute(
                select(StrategyGroup).filter_by(name=group_name)
            )
            group = group.scalar()
            if group is not None:
                await s.delete(group)

            await s.commit()
            return web.json_response(app_response(data=True))
        except Exception as e:
            await s.rollback()
            return web.json_response(
                app_response(code=AppCode.UNKNOWN_ERROR, msg=str(e))
            )


@auth(perm=["strategy.write"])
@json_post_checker(necessary_keys={"uuid": str})
async def delete_strategy(
    request: web.Request, data: t.Optional[t.Dict[str, t.Any]] = None
):
    if data is None:
        return web.json_response(
            app_response(code=AppCode.DATA_INVALID, msg="data is None")
        )
    async with async_session() as s:
        try:
            resp = await s.execute(select(Strategy).filter_by(uuid=data["uuid"]))
            stra = resp.scalar()
            if stra is None:
                return web.json_response(
                    app_response(code=AppCode.NOT_FOUND, msg="策略不存在")
                )
            await s.delete(stra)
            await s.commit()
            return web.json_response(app_response(data=True))
        except Exception as e:
            await s.rollback()
            return web.json_response(
                app_response(code=AppCode.UNKNOWN_ERROR, msg=str(e))
            )


rules = [
    web.RouteDef("GET", "/strategy/{uuid}", get_strategy, {}),
    web.RouteDef("GET", "/strategy/group", get_strategy_group, {}),
    web.RouteDef("POST", "/strategy/group/create", create_strategy_group, {}),
    web.RouteDef("POST", "/strategy/group/delete", delete_strategy_group, {}),
    web.RouteDef("GET", "/strategy/list", get_strategy_list, {}),
    web.RouteDef("POST", "/strategy/update", update_strategy, {}),
    web.RouteDef("POST", "/strategy/delete", delete_strategy, {}),
    web.RouteDef("POST", "/strategy/execute", execute_strategy, {}),
    web.RouteDef("GET", "/strategy/result/{id}", strategy_result, {}),
]
