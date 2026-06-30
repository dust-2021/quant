from aiohttp import web
from sqlalchemy import select
from database.data_center import get_session, Exchange, Script
from utils.types import app_response, AppCode
from utils.middleware.type_checker import json_post_checker
import typing as t


async def get_exchanges(req: web.Request) -> web.Response:
    """获取数据中心中所有交易所列表"""
    try:
        async with get_session()() as s:
            result = await s.execute(select(Exchange))
            rows = result.all()
        return web.json_response(
            app_response(data=[{"id": r[0].id, "name": r[0].name} for r in rows])
        )
    except RuntimeError as e:
        return web.json_response(
            app_response(code=AppCode.DATA_NOT_READY, msg=str(e))
        )


async def get_scripts(req: web.Request) -> web.Response:
    """获取数据中心中所有脚本列表"""
    try:
        async with get_session()() as s:
            result = await s.execute(select(Script))
            rows = result.all()
        return web.json_response(
            app_response(
                data=[
                    {"id": r[0].id, "name": r[0].name, "content": r[0].content}
                    for r in rows
                ]
            )
        )
    except RuntimeError as e:
        return web.json_response(
            app_response(code=AppCode.DATA_NOT_READY, msg=str(e))
        )


@json_post_checker(necessary_keys={"name": str, "content": str})
async def create_script(req: web.Request, data: t.Optional[t.Dict[str, t.Any]] = None) -> web.Response:
    """新增或更新脚本"""
    if data is None:
        return web.json_response(
            app_response(code=AppCode.DATA_INVALID, msg="缺少请求体")
        )
    try:
        async with get_session()() as s:
            existing = await s.execute(select(Script).filter_by(name=data["name"]))
            row = existing.first()
            if row is not None:
                # 更新已有脚本
                row[0].content = data["content"]
            else:
                s.add(Script(name=data["name"], content=data["content"]))
            await s.commit()
        return web.json_response(app_response(msg="脚本已保存"))
    except RuntimeError as e:
        return web.json_response(
            app_response(code=AppCode.DATA_NOT_READY, msg=str(e))
        )


@json_post_checker(necessary_keys={"name": str}, optional_keys={"params": dict})
async def execute_script(req: web.Request, data: t.Optional[t.Dict[str, t.Any]] = None) -> web.Response:
    """加载并执行数据中心脚本"""
    if data is None:
        return web.json_response(
            app_response(code=AppCode.DATA_INVALID, msg="缺少请求体")
        )
    try:
        result = await Script.load_and_execute(
            data["name"], **(data.get("params") or {})
        )
        return web.json_response(app_response(data=result))
    except Exception as e:
        return web.json_response(
            app_response(code=AppCode.EXECUTE_FAILED, msg=str(e))
        )


@json_post_checker(necessary_keys={"name": str})
async def delete_script(req: web.Request, data: t.Optional[t.Dict[str, t.Any]] = None) -> web.Response:
    """删除脚本"""
    if data is None:
        return web.json_response(
            app_response(code=AppCode.DATA_INVALID, msg="缺少请求体")
        )
    name = data["name"]
    try:
        async with get_session()() as s:
            result = await s.execute(select(Script).filter_by(name=name))
            row = result.first()
            if row is None:
                return web.json_response(
                    app_response(code=AppCode.NOT_FOUND, msg=f"脚本 '{name}' 不存在")
                )
            await s.delete(row[0])
            await s.commit()
        return web.json_response(app_response(msg=f"脚本 '{name}' 已删除"))
    except RuntimeError as e:
        return web.json_response(
            app_response(code=AppCode.DATA_NOT_READY, msg=str(e))
        )


rules = [
    web.route("GET", "/data_center/exchanges", get_exchanges),
    web.route("GET", "/data_center/scripts", get_scripts),
    web.route("POST", "/data_center/script", create_script),
    web.route("POST", "/data_center/script/execute", execute_script),
    web.route("POST", "/data_center/script/delete", delete_script),
]
