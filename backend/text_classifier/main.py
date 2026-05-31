import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_users.exceptions import UserAlreadyExists

from text_classifier.base_objects import UserCreate, UserRead, UserUpdate
from text_classifier.config import config
from text_classifier.database import Base, engine, get_async_session
from text_classifier.routes import admin_route, api_route
from text_classifier.users import auth_backend, fastapi_users, get_user_db, get_user_manager

_RELIABILITY_INTERVAL_SECONDS = 30 * 60  # 30 minutes


async def create_admin_user() -> None:
    """Create the admin superuser on first startup if it doesn't exist yet."""
    try:
        async for session in get_async_session():
            async for user_db in get_user_db(session):
                async for user_manager in get_user_manager(user_db):
                    user = await user_manager.create(
                        UserCreate(
                            email=config.ADMIN,
                            password=config.ADMIN_PASSWORD,
                            is_superuser=True,
                        )
                    )
                    print(f"Admin user created: {user.email}")
    except UserAlreadyExists:
        pass


async def _reliability_loop() -> None:
    """Background loop: recompute IRR metrics every 30 minutes."""
    from text_classifier.reliability import run_reliability_job
    while True:
        await asyncio.sleep(_RELIABILITY_INTERVAL_SECONDS)
        try:
            async for session in get_async_session():
                await run_reliability_job(session)
                await session.commit()
        except Exception as exc:
            print(f"[reliability] error: {exc}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await create_admin_user()
    task = asyncio.create_task(_reliability_loop())
    yield
    task.cancel()


app = FastAPI(title="text-classifier", version="0.1.0", lifespan=lifespan)

app.include_router(api_route, prefix='/api')
app.include_router(admin_route, prefix='/api/admin')
app.include_router(fastapi_users.get_auth_router(auth_backend), prefix="/auth/jwt", tags=["auth"])
app.include_router(fastapi_users.get_register_router(UserRead, UserCreate), prefix="/auth", tags=["auth"])
app.include_router(fastapi_users.get_users_router(UserRead, UserUpdate), prefix="/users", tags=["users"])

if not config.PRODUCTION:
    app.add_middleware(CORSMiddleware, allow_origins=[config.ALLOWED_ORIGIN], allow_credentials=True, allow_methods=['*'], allow_headers=['*'])
