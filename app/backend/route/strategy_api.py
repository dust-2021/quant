import datetime
import json
import typing as t
import uuid

from aiohttp import web
from sqlalchemy import select

from app.backend.route.execute import execute_strategy, strategy_result
from database.base import async_session
from database.model import Factor, Strategy, StrategyGroup
from utils.middleware.auth import auth
from utils.middleware.type_checker import json_post_checker
from utils.types import AppCode, app_response


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
    factor_infos = (
        [
            {
                "uuid": f.uuid,
                "name": f.name,
                "version": f.version,
                "description": f.description,
                "params": f.params or [],
            }
            for f in factor_details
        ]
        if factor_details
        else []
    )

    return web.json_response(
        app_response(
            data={
                "uuid": strategy[0].uuid,
                "name": strategy[0].name,
                "group": strategy[0].group,
                "version": strategy[0].version,
                "description": strategy[0].description,
                "params": strategy[0].params,
                "factors": factor_uuids,
                "factor_infos": factor_infos,
                "content": strategy[0].content,
            }
        )
    )


@auth(perm=["strategy.read"])
async def get_strategy_group(request: web.Request):
    async with async_session() as s:
        strategy_group = await s.execute(select(StrategyGroup))
        strategy_group = strategy_group.all()
    return web.json_response(
        app_response(
            data=[
                {"id": x[0].id, "name": x[0].name, "description": x[0].description}
                for x in strategy_group
            ]
        )
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
            ).join(Strategy, Strategy.group == StrategyGroup.name, isouter=True)
        )
        strategy_list = strategy_list.all()
    return web.json_response(
        app_response(
            data=[
                {
                    "group_name": strategy[0],
                    "strategy_name": strategy[1],
                    "uuid": strategy[2],
                    "version": strategy[3],
                    "description": strategy[4] or "",
                }
                for strategy in strategy_list
            ]
        )
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
    request: web.Request, data: dict[str, t.Any] | None = None
):
    if data is None:
        return web.json_response(
            app_response(code=AppCode.DATA_INVALID, msg="data is None")
        )
    async with async_session() as s:
        new_uuid = None
        try:
            if data.get("uuid") == "":  # 新增
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
                        app_response(
                            code=AppCode.DATA_INVALID, msg="strategy already exists"
                        )
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
                stra.update_time = int(datetime.datetime.now().timestamp())  # noqa: DTZ005
                stra.group = data.get("group", stra.group)
                stra.description = data.get("description", stra.description)
                stra.params = data.get("params", stra.params)
                stra.factors = json.dumps(data.get("factors", []))
                stra.content = data.get("content", stra.content)
                await s.flush()
        except Exception as e:  # noqa: BLE001
            await s.rollback()
            return web.json_response(
                app_response(code=AppCode.UNKNOWN_ERROR, msg=str(e))
            )
        finally:
            await s.commit()
    return web.json_response(
        app_response(data=new_uuid if data.get("uuid") == "" else True)
    )


@auth(perm=["strategy.write"])
@json_post_checker(
    necessary_keys={"name": str},
    optional_keys={"description": str},
)
async def create_strategy_group(
    request: web.Request, data: dict[str, t.Any] | None = None
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
            return web.json_response(
                app_response(
                    data={
                        "id": group.id,
                        "name": group.name,
                        "description": group.description,
                    }
                )
            )
        except Exception as e:  # noqa: BLE001
            await s.rollback()
            return web.json_response(
                app_response(code=AppCode.UNKNOWN_ERROR, msg=str(e))
            )


@auth(perm=["strategy.write"])
@json_post_checker(necessary_keys={"name": str})
async def delete_strategy_group(
    request: web.Request, data: dict[str, t.Any] | None = None
):
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
            group = await s.execute(select(StrategyGroup).filter_by(name=group_name))
            group = group.scalar()
            if group is not None:
                await s.delete(group)

            await s.commit()
            return web.json_response(app_response(data=True))
        except Exception as e:  # noqa: BLE001
            await s.rollback()
            return web.json_response(
                app_response(code=AppCode.UNKNOWN_ERROR, msg=str(e))
            )


@auth(perm=["strategy.write"])
@json_post_checker(necessary_keys={"uuid": str})
async def delete_strategy(
    request: web.Request, data: dict[str, t.Any] | None = None
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
        except Exception as e:  # noqa: BLE001
            await s.rollback()
            return web.json_response(
                app_response(code=AppCode.UNKNOWN_ERROR, msg=str(e))
            )


@auth(perm=["strategy.write"])
@json_post_checker(
    necessary_keys={
        "result_uuid": str,
        "name": str,
        "strategy_uid": str,
        "strategy_version": str,
        "exec_start_time": int,
        "exec_end_time": int,
        "period": int,
        "metrics": object,
    }
)
async def save_result(
    request: web.Request, data: dict[str, t.Any] | None = None
):
    """保存回测结果"""
    if data is None:
        return web.json_response(
            app_response(code=AppCode.DATA_INVALID, msg="data is None")
        )
    try:
        async with async_session() as s:
            from database.model import StrategyResult as SR

            # 将 metrics 转为 JSON 字符串
            metrics_str = (
                data["metrics"]
                if isinstance(data["metrics"], str)
                else json.dumps(data["metrics"])
            )
            result = SR(
                uuid=data["result_uuid"],
                name=data["name"],
                strategy_uid=data["strategy_uid"],
                strategy_version=data["strategy_version"],
                strategy_params=data.get("strategy_params"),
                factor_snapshots=data.get("factor_snapshots"),
                exec_start_time=data["exec_start_time"],
                exec_end_time=data["exec_end_time"],
                period=data["period"],
                targets=data.get("targets"),
                runner_name=data.get("runner_name", "default"),
                metrics=metrics_str,
                trade_data=data.get("trade_data"),
                chart_data=data.get("chart_data"),
                multi_param_keys=data.get("multi_param_keys"),
                multi_results=data.get("multi_results"),
            )
            s.add(result)
            await s.commit()
        return web.json_response(app_response(data={"uuid": data["result_uuid"]}))
    except Exception as e:  # noqa: BLE001
        return web.json_response(app_response(code=AppCode.UNKNOWN_ERROR, msg=str(e)))


async def list_results(request: web.Request):
    """获取策略的所有保存结果"""
    strategy_uid = request.match_info.get("uuid", "")
    if not strategy_uid:
        return web.json_response(
            app_response(code=AppCode.DATA_INVALID, msg="缺少 strategy_uid")
        )
    try:
        from database.model import StrategyResult as SR

        async with async_session() as s:
            results = await s.execute(
                select(SR)
                .filter_by(strategy_uid=strategy_uid)
                .order_by(SR.create_time.desc())
                .limit(50)
            )
            rows = results.scalars().all()
        return web.json_response(
            app_response(
                data=[
                    {
                        "uuid": r.uuid,
                        "name": r.name,
                        "strategy_version": r.strategy_version,
                        "exec_start_time": r.exec_start_time,
                        "exec_end_time": r.exec_end_time,
                        "period": r.period,
                        "runner_name": r.runner_name,
                        "create_time": r.create_time,
                        "multi_param_keys": r.multi_param_keys,
                    }
                    for r in rows
                ]
            )
        )
    except Exception as e:  # noqa: BLE001
        return web.json_response(app_response(code=AppCode.UNKNOWN_ERROR, msg=str(e)))


async def get_saved_result(request: web.Request):
    """获取单个保存结果的完整数据"""
    result_uuid = request.match_info.get("result_uuid", "")
    if not result_uuid:
        return web.json_response(
            app_response(code=AppCode.DATA_INVALID, msg="缺少 result_uuid")
        )
    try:
        from database.model import StrategyResult as SR

        async with async_session() as s:
            row = (await s.execute(select(SR).filter_by(uuid=result_uuid))).scalar()
        if row is None:
            return web.json_response(
                app_response(code=AppCode.NOT_FOUND, msg="结果不存在")
            )
        return web.json_response(
            app_response(
                data={
                    "uuid": row.uuid,
                    "name": row.name,
                    "strategy_uid": row.strategy_uid,
                    "strategy_version": row.strategy_version,
                    "strategy_params": row.strategy_params,
                    "factor_snapshots": row.factor_snapshots,
                    "exec_start_time": row.exec_start_time,
                    "exec_end_time": row.exec_end_time,
                    "period": row.period,
                    "targets": row.targets,
                    "runner_name": row.runner_name,
                    "metrics": json.loads(row.metrics)
                    if isinstance(row.metrics, str)
                    else row.metrics,
                    "trade_data": row.trade_data,
                    "chart_data": row.chart_data,
                    "multi_param_keys": row.multi_param_keys,
                    "multi_results": row.multi_results,
                    "create_time": row.create_time,
                }
            )
        )
    except Exception as e:  # noqa: BLE001
        return web.json_response(app_response(code=AppCode.UNKNOWN_ERROR, msg=str(e)))


@auth(perm=["strategy.write"])
@json_post_checker(necessary_keys={"result_uuid": str})
async def delete_result(
    request: web.Request, data: dict[str, t.Any] | None = None
):
    """删除保存的回测结果"""
    if data is None:
        return web.json_response(
            app_response(code=AppCode.DATA_INVALID, msg="data is None")
        )
    try:
        from database.model import StrategyResult as SR

        async with async_session() as s:
            row = (
                await s.execute(select(SR).filter_by(uuid=data["result_uuid"]))
            ).scalar()
            if row is None:
                return web.json_response(
                    app_response(code=AppCode.NOT_FOUND, msg="结果不存在")
                )
            await s.delete(row)
            await s.commit()
        return web.json_response(app_response(data=True))
    except Exception as e:  # noqa: BLE001
        return web.json_response(app_response(code=AppCode.UNKNOWN_ERROR, msg=str(e)))


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
    web.RouteDef("POST", "/strategy/result/save", save_result, {}),
    web.RouteDef("POST", "/strategy/result/delete", delete_result, {}),
    web.RouteDef("GET", "/strategy/{uuid}/results", list_results, {}),
    web.RouteDef("GET", "/strategy/result/saved/{result_uuid}", get_saved_result, {}),
]
