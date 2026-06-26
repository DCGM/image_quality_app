import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi_users.exceptions import UserAlreadyExists

from image_rater.base_objects import UserCreate, UserRead, UserUpdate
from image_rater.config import config
from image_rater.database import Base, engine, get_async_session
from image_rater.routes import admin_route, api_route
from image_rater.users import auth_backend, fastapi_users, get_user_db, get_user_manager

_RELIABILITY_INTERVAL_SECONDS = 30 * 60  # 30 minutes


async def create_admin_user() -> None:
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
    from image_rater.reliability import run_reliability_job
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
    # Ensure static images directory exists
    Path(config.STATIC_DIR, "images").mkdir(parents=True, exist_ok=True)
    await create_admin_user()
    task = asyncio.create_task(_reliability_loop())
    yield
    task.cancel()


app = FastAPI(title="image-rater", version="1.0.0", lifespan=lifespan)

# Static image files — no auth required
static_images_path = Path(config.STATIC_DIR) / "images"
static_images_path.mkdir(parents=True, exist_ok=True)
app.mount("/images", StaticFiles(directory=str(static_images_path)), name="images")

app.include_router(api_route, prefix="/api")
app.include_router(admin_route, prefix="/api/admin")
app.include_router(
    fastapi_users.get_auth_router(auth_backend), prefix="/auth/jwt", tags=["auth"]
)
app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate), prefix="/auth", tags=["auth"]
)
app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate), prefix="/users", tags=["users"]
)

if not config.PRODUCTION:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[config.ALLOWED_ORIGIN],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
