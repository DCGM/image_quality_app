from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from text_classifier.base_objects import UserCreate, UserRead, UserUpdate
from text_classifier.config import config
from text_classifier.database import Base, engine
from text_classifier.routes import admin_route, api_route
from text_classifier.users import auth_backend, fastapi_users

app = FastAPI(title="text-classifier", version="0.1.0")


@app.on_event("startup")
async def startup() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


app.include_router(api_route, prefix='/api')
app.include_router(admin_route, prefix='/api/admin')
app.include_router(fastapi_users.get_auth_router(auth_backend), prefix="/auth/jwt", tags=["auth"])
app.include_router(fastapi_users.get_register_router(UserRead, UserCreate), prefix="/auth", tags=["auth"])
app.include_router(fastapi_users.get_users_router(UserRead, UserUpdate), prefix="/users", tags=["users"])

if not config.PRODUCTION:
    app.add_middleware(CORSMiddleware, allow_origins=[config.ALLOWED_ORIGIN], allow_credentials=True, allow_methods=['*'], allow_headers=['*'])
