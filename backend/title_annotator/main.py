import os
import logging
import logging.config
import traceback

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles


tags_metadata = [
    {
        "name": "Document",
        "description": "",
    },
    {
        "name": "Image",
        "description": "",
    }
]


app = FastAPI(openapi_tags=tags_metadata, title="Scribble Sense", version="0.1.0", root_path=config.APP_URL_ROOT)


@app.on_event("startup")
async def startup():
    logging.config.dictConfig(config.LOGGING_CONFIG)
    await init_db()


app.include_router(user_route, prefix="/api/user")
app.include_router(document_route, prefix="/api/document")
app.include_router(image_route, prefix="/api/image")
app.include_router(authentication_route, prefix="/api")
app.include_router(authentication_route, prefix="")
app.include_router(news_route, prefix="/api/news")
app.include_router(model_route, prefix="/api/model")
app.include_router(job_route, prefix="/api/job")
app.include_router(training_job_route, prefix="/api/training_job")
app.include_router(import_route, prefix="/api/import")
app.include_router(export_route, prefix="/api/export")
app.include_router(notification_route, prefix="/api/notification")
app.include_router(debug_route, prefix="/api/debug")

if os.path.isdir("scribble_sense/static"):
    app.mount("/", StaticFiles(directory="scribble_sense/static", html=True), name="static")


@app.exception_handler(Exception)
async def unicorn_exception_handler(request: Request, exc: Exception):
    if config.INTERNAL_MAIL_SERVER is not None:
        internal_mail_logger.critical(f'URL: {request.url}\n'
                                      f'METHOD: {request.method}\n'
                                      f'CLIENT: {request.client}\n\n'
                                      f'ERROR: {exc}\n\n'
                                      f'{traceback.format_exc()}',
                                      extra={'subject': f'{config.MODE.upper()} {config.ADMIN_SERVER_NAME} - INTERNAL SERVER ERROR'})
    if isinstance(exc, DBError):
        # DBError exceptions are already logged when they are raised
        return JSONResponse(status_code=400, content={"message": str(exc)})
    else:
        exception_logger.error(f'URL: {request.url}')
        exception_logger.error(f'CLIENT: {request.client}')
        exception_logger.exception(exc)
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
