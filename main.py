from loguru import logger
from app.backend.app import generate_app
import platform
from aiohttp import web
import asyncio
from config import Config
from database.model import Config as ConfDb
from database.base import init_db
from utils.logger import setup_logging

async def open_browser():
    if platform.system() == "Windows":
        import webbrowser
        port: int = await ConfDb.get(Config.Port)
        webbrowser.open(f'http://127.0.0.1:{port}')

async def main():
    await init_db()
    setup_logging(
        level=await ConfDb.get(Config.BaseLog),
        aiohttp_level=await ConfDb.get(Config.WebLog),
        sqlalchemy_level=await ConfDb.get(Config.SQLAlchemyLog),
    )
    port: int = await ConfDb.get(Config.Port)
    app = generate_app()
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
