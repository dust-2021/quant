import typing as t

from aiohttp import web
from sqlalchemy import select

from database.base import async_session
from database.model import Calculator as CalculatorModel
from utils.middleware.type_checker import json_post_checker
from utils.types import AppCode, app_response


async def get_calculators(request: web.Request):
    """获取所有算子列表"""
    async with async_session() as s:
        result = await s.execute(select(CalculatorModel).order_by(CalculatorModel.id))
        rows = result.scalars().all()
    return web.json_response(app_response(data=[
        {"id": r.id, "name": r.name, "description": r.description or "",
         "content": r.content or "", "create_time": r.create_time, "update_time": r.update_time}
        for r in rows
    ]))


@json_post_checker(necessary_keys={"name": str, "content": str}, optional_keys={"description": str})
async def save_calculator(request: web.Request, data: dict[str, t.Any] | None = None):
    """新增或更新算子"""
    if data is None:
        return web.json_response(app_response(code=AppCode.DATA_INVALID, msg="缺少请求体"))
    if data["name"] == "default":
        return web.json_response(app_response(code=AppCode.DATA_INVALID, msg="default 算子不可修改"))
    async with async_session() as s:
        existing = (await s.execute(select(CalculatorModel).filter_by(name=data["name"]))).scalar()
        if existing is not None:
            existing.content = data["content"]
            existing.description = data.get("description", existing.description)
        else:
            s.add(CalculatorModel(
                name=data["name"],
                content=data["content"],
                description=data.get("description", ""),
            ))
        await s.commit()
    return web.json_response(app_response(msg="算子已保存"))


@json_post_checker(necessary_keys={"name": str})
async def delete_calculator(request: web.Request, data: dict[str, t.Any] | None = None):
    """删除算子"""
    if data is None:
        return web.json_response(app_response(code=AppCode.DATA_INVALID, msg="缺少请求体"))
    if data["name"] == "default":
        return web.json_response(app_response(code=AppCode.DATA_INVALID, msg="default 算子不可删除"))
    async with async_session() as s:
        calc = (await s.execute(select(CalculatorModel).filter_by(name=data["name"]))).scalar()
        if calc is None:
            return web.json_response(app_response(code=AppCode.NOT_FOUND, msg=f"算子 '{data['name']}' 不存在"))
        await s.delete(calc)
        await s.commit()
    return web.json_response(app_response(msg=f"算子 '{data['name']}' 已删除"))


rules = [
    web.RouteDef("GET", "/calculator/list", get_calculators, {}),
    web.RouteDef("POST", "/calculator/save", save_calculator, {}),
    web.RouteDef("POST", "/calculator/delete", delete_calculator, {}),
]
