import json
import os
import subprocess
from glob import glob


from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker, AsyncEngine
from sqlalchemy import select, update, bindparam

from title_annotator.config import config
from typing import AsyncGenerator

import logging


global_engine = None
global_async_session_maker = None

logger = logging.getLogger(__name__)


async def init_db() -> None:
    from db_model import Base
    db_async_engine = create_async_engine(config.DATABASE_URL)
    async with db_async_engine.begin() as db_async_connection:
        await db_async_connection.run_sync(Base.metadata.create_all)


# Dependency
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    global global_engine, global_async_session_maker
    if global_engine is None:
        global_engine = create_async_engine(config.DATABASE_URL,
                                            pool_pre_ping=True,
                                            pool_size=10,
                                            max_overflow=30)
        global_async_session_maker = async_sessionmaker(global_engine,
                                                        expire_on_commit=False,
                                                        autocommit=False,
                                                        autoflush=False)
    async with global_async_session_maker() as session:
        yield session


class DBError(Exception):
    pass
