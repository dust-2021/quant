import asyncio
import platform

from aiohttp import web
from loguru import logger

from app.backend.app import generate_app
from database.base import init_db
from database.data_center import init_data_center
from database.model import Config as ConfDb
from jobs import init_jobs
from utils.cache import init_cache
from utils.logger import setup_logging
from utils.scheduler import aSche


async def open_browser():
    if platform.system() == "Windows":
        import webbrowser

        port: int = await ConfDb.get("Port")
        webbrowser.open(f"http://127.0.0.1:{port}")


async def main():
    # 初始化后端数据库
    await init_db()
    # 初始化数据中心
    _ = await init_data_center()
    # 初始化统一缓存接口（配置了 redis 则使用 redis，否则使用 diskcache）
    init_cache(
        host=await ConfDb.get("RedisHost"),
        port=await ConfDb.get("RedisPort"),
        password=await ConfDb.get("RedisPassword"),
        db=await ConfDb.get("RedisDb"),
    )
    # 初始化日志
    setup_logging(
        level=await ConfDb.get("BaseLog"),
        aiohttp_level=await ConfDb.get("WebLog"),
        sqlalchemy_level=await ConfDb.get("SQLAlchemyLog"),
    )

    port: int = await ConfDb.get("Port")
    app = generate_app(await ConfDb.get("MaxHttpPayload"))
    logger.info(f"start app at port:{port}")
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner=runner, host="0.0.0.0", port=port)
    await site.start()
    # 启动定时任务调度器
    # init_jobs()
    # aSche.start()
    # logger.info("scheduler started")
    await open_browser()
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())
