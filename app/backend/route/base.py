import asyncio
import os
import sys
import typing as t

from aiohttp import web

from config import BASE_PATH
from database.model import Config
from utils.middleware.auth import auth
from utils.middleware.type_checker import json_post_checker
from utils.types import AppCode, app_response


async def index(req: web.Request):
    return web.FileResponse(os.path.join(BASE_PATH, "static/dist/index.html"))

@auth(["config.read"])
async def get_config(req: web.Request):
    key = req.match_info.get("key")
    if key is None:
        return web.json_response(app_response(code=AppCode.DATA_INVALID, msg="key is required"))
    value = await Config.get(key)
    return web.json_response(app_response(data=value))


@auth(["config.write"])
@json_post_checker(necessary_keys={
    "key": str, "value": object
})
async def set_config(req: web.Request, data: dict[str, t.Any] | None = None):
    if data is None:
        return web.json_response(app_response(code=AppCode.DATA_INVALID, msg="invalid json body"))
    await Config.set(data["key"], data["value"])
    return web.json_response(app_response(msg="config updated"))


def _do_restart():
    """执行进程重启，使用 os.execv 替换当前进程"""
    python = sys.executable
    os.execv(python, [python] + sys.argv)


async def restart_server(req: web.Request):
    """重启后端服务"""
    loop = asyncio.get_event_loop()
    loop.call_later(0.5, _do_restart)
    return web.json_response(app_response(msg="server is restarting"))


rules = [
    web.route("GET", "/", index),
    web.route("GET", "/config/{key}", get_config),
    web.route("POST", "/config", set_config),
    web.route("POST", "/restart", restart_server),
]

