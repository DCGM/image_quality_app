from fastapi import APIRouter, Request, Response, Depends
from title_annotator.users import auth_backend, current_active_user, fastapi_users
from title_annotator import base_objects
from title_annotator.database import User, get_async_session
from title_annotator.users import current_active_user
from title_annotator.crud import get_random_rating_request, add_rating_request

from sqlalchemy.ext.asyncio import AsyncSession

rating_route = APIRouter()


@rating_route.get("/request",
                  response_model=base_objects.RatingRequest,
                  description='Get random rating request for the current user.')
async def get_rating_request(
    user: User = Depends(current_active_user), db: AsyncSession = Depends(get_async_session)):
    request = get_random_rating_request(db, user.id)
    return request


@rating_route.post("/request",
                   response_model=None,
                   description='Add a new rating request.')
async def post_rating_request(
    rating_request: base_objects.RatingRequestNew,
    user: User = Depends(current_active_user), db: AsyncSession = Depends(get_async_session)):
    if not user.is_superuser:
        return Response(status_code=403, content="Only superusers can add rating requests.")

    try:
        await add_rating_request(db, rating_request)
        await db.commit()
        return Response(status_code=201)
    except Exception as e:
        await db.rollback()
        return Response(status_code=400, content=f"Error adding rating request: {str(e)}")


@rating_route.post("/response",
                   response_model=None,
                   description='Add a new rating response.')
async def add_rating_response(
    rating_response: base_objects.RatingResponseNew,
    user: User = Depends(current_active_user), db: AsyncSession = Depends(get_async_session)):
    try:
        await add_rating_response(db, rating_response, user.id)
        await db.commit()
        return Response(status_code=201)
    except Exception as e:
        await db.rollback()
        return Response(status_code=400, content=f"Error adding rating response: {str(e)}")


