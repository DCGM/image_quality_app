import os
import logging
import logging.config
import traceback

from fastapi import FastAPI, Request, Depends, FastAPI
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from title_annotator.database import User, init_db, DBError
from title_annotator.base_objects import UserCreate, UserRead, UserUpdate
from title_annotator.users import auth_backend, current_active_user, fastapi_users
from title_annotator.config import config

from contextlib import asynccontextmanager

from title_annotator.routes import rating_route


tags_metadata = [
    {
        "name": "Rating",
        "description": "",
    }
]

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Not needed if you setup a migration system like Alembic
    await init_db()
    yield


app = FastAPI(openapi_tags=tags_metadata, title="Scribble Sense", version="0.1.0", lifespan=lifespan)  #, root_path=config.APP_URL_ROOT)

app.include_router(rating_route, prefix="/api/rating", tags=["Rating"])

app.include_router(
    fastapi_users.get_auth_router(auth_backend), prefix="/auth/jwt", tags=["auth"]
)
app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_reset_password_router(),
    prefix="/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_verify_router(UserRead),
    prefix="/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/users",
    tags=["users"],
)

if os.path.isdir("scribble_sense/static"):
    app.mount("/", StaticFiles(directory="scribble_sense/static", html=True), name="static")


@app.exception_handler(Exception)
async def unicorn_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, DBError):
        # DBError exceptions are already logged when they are raised
        return JSONResponse(status_code=400, content={"message": str(exc)})
    else:
        logging.error(f'URL: {request.url}, METHOD: {request.method}, CLIENT: {request.client}, ERROR: {exc}\n{traceback.format_exc()}')
        return Response(status_code=500)


if config.PRODUCTION:
    logging.warning(f'PRODUCTION')
else:
    logging.warning(f'DEVELOPMENT')
    app.add_middleware(
         CORSMiddleware,
         allow_origins=["http://localhost:9000"],
         allow_credentials=True,
         allow_methods=["*"],
         allow_headers=["*"],
     )
