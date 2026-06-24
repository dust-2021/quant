import datetime
from database.model import Factor, FactorGroup
from database.base import async_session
from utils.middleware.auth import auth
from utils.middleware.type_checker import json_post_checker
from aiohttp import web
from utils.types import app_response, AppCode
from sqlalchemy import select
import typing as t
import uuid


@auth(perm=["factor.read"])
async def search_factor(requset: web.Request) -> web.Response:
    keyword = requset.query.get("keyword", "")
    if keyword == "":
        return web.json_response(
            app_response(code=AppCode.DATA_INVALID, msg="keyword is required")
        )
    async with async_session() as s:
        factors = await s.execute(
            select(Factor.name, Factor.version).where(Factor.name.like(f"%{keyword}%"))
        )
        factors = factors.all()
    return web.json_response(
        app_response(data=[{"name": x[0], "version": x[1]} for x in factors])
    )


@auth(perm=["factor.read"])
async def get_factor(request: web.Request):
    async with async_session() as s:
        factor = await s.execute(
            select(Factor).filter_by(uuid=request.match_info["uuid"])
        )
        factor = factor.first()
    if factor is None:
        return web.json_response(
            app_response(code=AppCode.NOT_FOUND, msg="factor not found")
        )
    return web.json_response(app_response(data={
        "uuid": factor[0].uuid,
        "name": factor[0].name,
        "version": factor[0].version,
        "group": factor[0].group or "default",
        "description": factor[0].description or "",
        "params": factor[0].params or [],
        "content": factor[0].content or "",
    }))


@auth(perm=["factor.write"])
@json_post_checker(
    necessary_keys={"version": str, "name": str, "group": str},
    optional_keys={
        "uuid": str,
        "description": str,
        "params": list,
        "content": str,
    },
)
async def update_factor(
    request: web.Request, data: t.Optional[t.Dict[str, t.Any]] = None
):
    if data is None:
        return web.json_response(
            app_response(code=AppCode.DATA_INVALID, msg="data is None")
        )
    async with async_session() as s:
        try:
            if not data.get("uuid"):
                # 新增
                fac = Factor(
                    uuid=uuid.uuid4().hex,
                    name=data.get("name"),
                    version=data.get("version"),
                    group=data.get("group", "default"),
                    description=data.get("description", ""),
                    params=data.get("params", []),
                    content=data.get("content", ""),
                )
                s.add(fac)
            else:
                resp = await s.execute(select(Factor).filter_by(uuid=data["uuid"]))
                resp = resp.first()
                if resp is None:
                    return web.json_response(
                        app_response(code=AppCode.NOT_FOUND, msg="factor not found")
                    )
                fac = resp[0]
                fac.update_time = int(datetime.datetime.now().timestamp())
                fac.name = data.get("name", fac.name)
                fac.group = data.get("group", fac.group)
                fac.description = data.get("description", fac.description)
                fac.params = data.get("params", fac.params)
                fac.content = data.get("content", fac.content)
                await s.flush()
        except Exception as e:
            await s.rollback()
            return web.json_response(
                app_response(code=AppCode.UNKNOWN_ERROR, msg=str(e))
            )
        finally:
            await s.commit()
    return web.json_response(app_response(data=True))


@auth(perm=["factor.read"])
async def get_factor_list(request: web.Request):
    async with async_session() as s:
        factor_list = await s.execute(
            select(
                FactorGroup.name.label("group_name"),
                Factor.name.label("factor_name"),
                Factor.uuid,
                Factor.version,
                Factor.description,
            )
            .join(Factor, Factor.group == FactorGroup.name, isouter=True)
        )
        factor_list = factor_list.all()
    return web.json_response(
        app_response(data=[{
            'group_name': f[0],
            'factor_name': f[1],
            'uuid': f[2],
            'version': f[3],
            'description': f[4] or '',
        } for f in factor_list])
    )


@auth(perm=["factor.write"])
@json_post_checker(necessary_keys={"uuid": str})
async def delete_factor(
    request: web.Request, data: t.Optional[t.Dict[str, t.Any]] = None
):
    if data is None:
        return web.json_response(
            app_response(code=AppCode.DATA_INVALID, msg="data is None")
        )
    async with async_session() as s:
        try:
            resp = await s.execute(select(Factor).filter_by(uuid=data["uuid"]))
            fac = resp.scalar()
            if fac is None:
                return web.json_response(
                    app_response(code=AppCode.NOT_FOUND, msg="因子不存在")
                )
            await s.delete(fac)
            await s.commit()
            return web.json_response(app_response(data=True))
        except Exception as e:
            await s.rollback()
            return web.json_response(
                app_response(code=AppCode.UNKNOWN_ERROR, msg=str(e))
            )


@auth(perm=["factor.read"])
async def get_factor_group(request: web.Request):
    async with async_session() as s:
        factor_group = await s.execute(select(FactorGroup))
        factor_group = factor_group.all()
    return web.json_response(
        app_response(data=[{'id': x[0].id, 'name': x[0].name, 'description': x[0].description} for x in factor_group])
    )


@auth(perm=["factor.write"])
@json_post_checker(
    necessary_keys={"name": str},
    optional_keys={"description": str},
)
async def create_factor_group(
    request: web.Request, data: t.Optional[t.Dict[str, t.Any]] = None
):
    if data is None:
        return web.json_response(
            app_response(code=AppCode.DATA_INVALID, msg="data is None")
        )
    async with async_session() as s:
        try:
            existing = await s.execute(
                select(FactorGroup).filter_by(name=data["name"])
            )
            if existing.scalar() is not None:
                return web.json_response(
                    app_response(code=AppCode.DATA_INVALID, msg="分组名已存在")
                )
            group = FactorGroup(
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


@auth(perm=["factor.write"])
@json_post_checker(necessary_keys={"name": str})
async def delete_factor_group(request: web.Request, data: t.Optional[t.Dict[str, t.Any]] = None):
    """删除分组，并将该分组下所有因子移到 default 分组"""
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
                select(FactorGroup).filter_by(name="default")
            )
            if default_group.scalar() is None:
                s.add(FactorGroup(name="default", description="默认分组"))
                await s.flush()

            # 将该分组下所有因子的 group 改为 default
            await s.execute(
                Factor.__table__.update()
                .where(Factor.group == group_name)
                .values(group="default")
            )

            # 删除分组
            group = await s.execute(
                select(FactorGroup).filter_by(name=group_name)
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


rules = [
    web.RouteDef("GET", "/factor/search", search_factor, {}),
    web.RouteDef("GET", "/factor/list", get_factor_list, {}),
    web.RouteDef("GET", "/factor/group", get_factor_group, {}),
    web.RouteDef("POST", "/factor/group/create", create_factor_group, {}),
    web.RouteDef("POST", "/factor/group/delete", delete_factor_group, {}),
    web.RouteDef("GET", "/factor/{uuid}", get_factor, {}),
    web.RouteDef("POST", "/factor/update", update_factor, {}),
    web.RouteDef("POST", "/factor/delete", delete_factor, {}),
]
