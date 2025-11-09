import logging
from contextlib import asynccontextmanager
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import exc, select, update, delete, or_
from title_annotator.database import DBError
from title_annotator.db import db_model as model
from title_annotator import base_objects

from typing import List, Union

logger = logging.getLogger(__name__)


async def get_all(db: AsyncSession, model_class: base_objects.BaseModel, table: model.Base, limit: int = 1000) -> List[model.Base]:
    try:
        async with db.begin():
            db_objects = select(table).order_by(table.created_date.desc()).limit(limit)
            db_objects = await db.execute(db_objects)
            db_objects = db_objects.unique().scalars()
            return [model_class.model_validate(obj) for obj in db_objects]
    except exc.SQLAlchemyError as e:
        logger.exception(f'Failed fetching objects from database.')
        raise DBError(f'Failed fetching objects from database.') from e


async def get(db: AsyncSession, model_class: base_objects.BaseModel, table: model.Base, id: UUID) -> model.Base:
    try:
        async with db.begin():
            db_object = select(table).where(table.id == id)
            db_object = await db.execute(db_object)
            db_object = db_object.unique().scalar()
            if db_object is None:
                raise exc.SQLAlchemyError
            return model_class.model_validate(db_object)
    except exc.SQLAlchemyError as e:
        logging.exception(f'Failed fetching object from database. Object does not exist. ID={id}')
        raise DBError(f'Failed fetching object from database. Object does not exist. ID={id}') from e


async def get_or_none(db: AsyncSession, model_class: base_objects.BaseModel, table: model.Base, id: UUID) -> Union[model.Base, None]:
    try:
        async with db.begin():
            db_object = select(table).where(table.id == id)
            db_object = await db.execute(db_object)
            db_object = db_object.unique().scalar()
            if db_object is None:
                return None
            return model_class.model_validate(db_object)
    except exc.SQLAlchemyError as e:
        logging.exception(f'Failed fetching object from database. ID={id}')
        raise DBError(f'Failed fetching object from database. ID={id}') from e


async def new(db: AsyncSession, obj: dict, table: model.Base):
    try:
        async with db.begin():
            db_obj = table(**obj)
            db.add(db_obj)
            await db.commit()
    except exc.SQLAlchemyError as e:
        logging.exception(f'Failed adding object to database. Could be that the object already exists. ID={obj["id"]}')
        raise DBError(f'Failed adding object to database. Could be that the object already exists. ID={obj["id"]}') from e


async def update_obj(db: AsyncSession, obj: base_objects.BaseModel, table: model.Base, exclude_none=True):
    try:
        async with db.begin():
            data = obj.model_dump(exclude={'id'}, exclude_none=exclude_none)
            stm = (update(table).where(table.id == obj.id).values(data))
            await db.execute(stm)
    except exc.SQLAlchemyError as e:
        logging.exception(f'Failed updating object in database.')
        raise DBError(f'Failed updating object in database.') from e


async def delete_obj(db: AsyncSession, id: UUID, table: model.Base):
    try:
        async with db.begin():
            stm = (delete(table).where(table.id == id))
            await db.execute(stm)
    except exc.SQLAlchemyError as e:
        logging.exception(f'Failed deleting object in database. Object probably does not exist. ID={id}')
        raise DBError(f'Failed deleting object in database. Object probably does not exist. ID={id}') from e



