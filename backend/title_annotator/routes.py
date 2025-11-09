from fastapi import APIRouter, Request, Response
import base_objects


rating_route = APIRouter()


@rating_route.get("/rating_request",
                  response_model=base_objects.RatingRequest,
                  tags=["User"], description='Delete an image from a topic.')
async def get_rating_request(
    user_token: TokenUser = Depends(get_user_info), db: AsyncSession = Depends(get_async_session)):

