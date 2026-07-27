import asyncio
import platform

from aiohttp import web
from loguru import logger

from app.backend.app import generate_app
from cores.agent.base import MyAgent
from database.base import init_db
from database.data_center import init_data_center
from database.model import Config as ConfDb
from utils.logger import setup_logging


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
    # 初始化日志
    setup_logging(
        level=await ConfDb.get("BaseLog"),
        aiohttp_level=await ConfDb.get("WebLog"),
        sqlalchemy_level=await ConfDb.get("SQLAlchemyLog"),
    )
    # 初始化agent
    _ = MyAgent("")

    port: int = await ConfDb.get("Port")
    app = generate_app(await ConfDb.get("MaxHttpPayload"))
    logger.info(f"start app at port:{port}")
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner=runner, host="127.0.0.1", port=port)
    await site.start()
    await open_browser()
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())
