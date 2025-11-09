import json
import os
import subprocess
from glob import glob

from collections.abc import AsyncGenerator
from collections.abc import AsyncGenerator

import fastapi_users
from fastapi import Depends
from fastapi_users.db import SQLAlchemyBaseUserTableUUID, SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker, AsyncEngine
from sqlalchemy import select, update, bindparam
from sqlalchemy.orm import DeclarativeBase

from title_annotator.config import config
from typing import AsyncGenerator
import contextlib

import logging


global_engine = None
global_async_session_maker = None

logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass

class User(SQLAlchemyBaseUserTableUUID, Base):
    pass


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


async def init_db() -> None:
    db_async_engine = create_async_engine(config.DATABASE_URL)
    async with db_async_engine.begin() as db_async_connection:
        await db_async_connection.run_sync(Base.metadata.create_all)

        user_db = SQLAlchemyUserDatabase(User, db_async_engine)
        from title_annotator.users import get_user_manager
        from title_annotator.base_objects import UserCreate

    get_async_session_cm = contextlib.asynccontextmanager(get_async_session)
    get_user_db_cm = contextlib.asynccontextmanager(get_user_db)
    get_user_manager_cm = contextlib.asynccontextmanager(get_user_manager)

    async with get_async_session_cm() as session:
        async with get_user_db_cm(session) as user_db:
            async with get_user_manager_cm(user_db) as user_manager:
                try:
                    await user_manager.get_by_email(config.ADMIN)
                except fastapi_users.exceptions.UserNotExists:
                    # If your UserCreate includes is_superuser, set it here.
                    # In the "full example", UserCreate = BaseUserCreate (email & password only),
                    # so we create first, then elevate with an update (see below).
                    user = await user_manager.create(
                        UserCreate(email=config.ADMIN, password=config.ADMIN_PASSWORD)
                        # If your UserCreate *does* include flags, you can pass them
                        # and set safe=False: user_manager.create(..., safe=False)
                    )

                    # Elevate to superuser if your schema doesn't include it:
                    await user_manager.user_db.update(user, {"is_superuser": True, "is_active": True})
                    # Optional: mark verified too
                    # await user_manager.user_db.update(user, {"is_verified": True})

                    print("✅ Initial admin created:", config.ADMIN)


async def get_user_db(session: AsyncSession = Depends(get_async_session)):
    yield SQLAlchemyUserDatabase(session, User)

class DBError(Exception):
    pass
