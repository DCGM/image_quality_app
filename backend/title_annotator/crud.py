import asyncio
import logging
import json
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import exc, select, update, func, and_, delete, or_

from title_annotator.db_model import RatingRequest, RatingResponse
from title_annotator.database import DBError
from title_annotator import base_objects
from uuid import UUID
from typing import List, Optional, Union


async def add_rating_request(db: AsyncSession, rating_request: base_objects.RatingRequestNew) -> None:
    """ Add a new RatingRequest to the database.

    Args:
        db (AsyncSession): The database session.
        rating_request (base_objects.RatingRequestNew): The RatingRequest object to add.
    Raises:
        DBError: If there is an error adding the RatingRequest to the database.
    """
    try:
        db_request = RatingRequest(
            id=UUID(rating_request.id),
            chunk=rating_request.chunk.model_dump_json(),
            titles_lists=json.dumps([[t.model_dump() for t in titles] for titles in rating_request.titles_lists]),
            ratings_requested=rating_request.ratings_requested,
            ratings_done=rating_request.ratings_done,
            ratings_to_go=rating_request.ratings_to_go,
            rnd_number=func.random(),
            created_at=datetime.utcnow()
        )
        db.add(db_request)
    except exc.SQLAlchemyError as e:
        logging.exception('Failed adding RatingRequest to database.')
        raise DBError('Failed adding RatingRequest to database.') from e


async def get_random_rating_request(db: AsyncSession, user_id: UUID) -> RatingRequest:
    """ Fetch a random RatingRequest from the database that has ratings_to_go > 0 and the user has not rated it yet.

    Args:
        db (AsyncSession): The database session.
        user_id (UUID): The ID of the user requesting the rating task.
    Returns:
        RatingRequest: A random RatingRequest object.
    Raises:
        DBError: If there is an error fetching the RatingRequest from the database.
    """

    try:
        stmt = (
            select(RatingRequest)
            .outerjoin(RatingResponse, and_(
                RatingRequest.id == RatingResponse.request_id,
                RatingResponse.user_id == user_id
            ))
            .where(and_(
                RatingRequest.ratings_to_go > 0,
                RatingResponse.request_id.is_(None)  # No rating by this user
            ))
            .order_by(RatingRequest.rnd_number)
            .limit(1)
        )

        result = await db.execute(stmt)
        db_request = result.scalar_one_or_none()
        if db_request is None:
            raise DBError('No available rating requests found.')

        return base_objects.RatingRequest(
            id=str(db_request.id),
            chunk=base_objects.ChunkImport.model_validate_json(db_request.chunk),
            titles_lists=[[base_objects.TitleImport.model_validate(t) for t in titles]
                for titles in json.loads(db_request.titles_lists)],
            ratings_requested=db_request.ratings_requested,
            ratings_done=db_request.ratings_done,
            ratings_to_go=db_request.ratings_to_go,
            created_at=db_request.created_at
        )

    except exc.SQLAlchemyError as e:
        logging.exception('Failed fetching random RatingRequest from database.')
        raise DBError('Failed fetching random RatingRequest from database.') from e


async def save_rating_response(db: AsyncSession, rating_response: base_objects.RatingResponseNew,
                               user_id: UUID) -> None:
    """ Save a RatingResponse to the database and update the corresponding RatingRequest.

    Args:
        db (AsyncSession): The database session.
        rating_response (base_objects.RatingResponseNew): The RatingResponse object to save.
    Raises:
        DBError: If there is an error saving the RatingResponse to the database.
    """
    try:
        db_response = RatingResponse(
            request_id=UUID(rating_response.request_id),
            user_id=user_id,
            start_time=rating_response.start_time,
            end_time=rating_response.end_time,
            created_at=datetime.utcnow(),
            ratings=json.dumps([sr.model_dump()
                                for sr in rating_response.ratings], default=str)
        )
        db.add(db_response)

        # Update the corresponding RatingRequest
        stmt = (
            update(RatingRequest)
            .where(RatingRequest.id == UUID(rating_response.request_id))
            .values(
                ratings_done=RatingRequest.ratings_done + 1,
                ratings_to_go=RatingRequest.ratings_to_go - 1,
            )
        )
        await db.execute(stmt)

    except exc.SQLAlchemyError as e:
        logging.exception('Failed saving RatingResponse to database.')
        raise DBError('Failed saving RatingResponse to database.') from e




