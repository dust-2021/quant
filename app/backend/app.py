from aiohttp import web
from app.backend.route.strategy_api import rules as strategy_router
from app.backend.route.base import rules as base_router
from app.backend.route.factor_api import rules as factor_router
from app.backend.route.execute import rules as execute_router
from app.backend.route.data_center import rules as data_center_router
from app.backend.route.calculator_api import rules as calculator_router
from config import BASE_PATH
import os


def generate_app() -> web.Application:
    app = web.Application(client_max_size=50 * 1024 * 1024)  # 50MB

    # 首页路由 - 保持不变
    index_routes = [r for r in base_router if r.path == '/']
    app.add_routes(index_routes)

    # API 子应用 - 统一添加 /api 前缀
    api = web.Application(client_max_size=50 * 1024 * 1024)  # 50MB
    api_routes = [r for r in base_router if r.path != '/']
    api.add_routes(api_routes)
    api.add_routes(strategy_router)
    api.add_routes(factor_router)
    api.add_routes(execute_router)
    api.add_routes(data_center_router)
    api.add_routes(calculator_router)
    app.add_subapp('/api', api)

    app.router.add_static("/static", os.path.join(BASE_PATH, "static"))
    # vue 静态资源
    app.router.add_static("/assets", os.path.join(BASE_PATH, "static/dist/assets"))
    return app
