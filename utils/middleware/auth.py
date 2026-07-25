import typing as t
from functools import wraps
from aiohttp import web
from utils.types import app_response, AppCode
from database.model import Config

def auth(perm: t.Optional[t.Sequence[str]] = None):
    def wrapper(func: t.Callable[[web.Request], t.Awaitable[web.Response]]):
        
        @wraps(func)
        async def wrapped(req: web.Request):
            return await func(req)
            if not await Config.get('Auth'):
                return await func(req)
            # TODO: 检查权限
            token = req.headers.get("Token")
            if token is None:
                return web.json_response(app_response(code=AppCode.TOKEN_INVALID, msg="token is required"), status=401)
            return await func(req)
        
        return wrapped
    return wrapper
