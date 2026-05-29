from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
import os

db_path = os.path.join(os.getcwd(), 'locals', 'quant.db')

async_engine = create_async_engine(f'sqlite+aiosqlite:///{db_path}', echo=True, pool_size=5)
sync_engine = create_engine(f'sqlite:///{db_path}', echo=True, pool_size=10)

base = declarative_base()

async_session = async_sessionmaker(async_engine, expire_on_commit=False)

sync_session = sessionmaker(sync_engine, expire_on_commit=False)
async def init_db():
    async with async_engine.begin() as conn:
        await conn.run_sync(base.metadata.create_all)
