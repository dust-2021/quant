from database.model import  Factor
from database.base import async_session
from utils.middleware.auth import auth
from aiohttp import web
from utils.types import app_response, AppCode
from sqlalchemy import select


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


rules = [web.RouteDef("GET", "/factors/search", search_factor, {})]
