import json


from sqlalchemy.orm import Mapped, WriteOnlyMapped, mapped_column, relationship, DeclarativeBase
from sqlalchemy import ForeignKey
from sqlalchemy.types import String

from title_annotator.database import Base
from datetime import datetime
import uuid
from random import randint

# converts ORM row object to dict
orm2dict = lambda r: {c.name: getattr(r, c.name) for c in r.__table__.columns}

# converts CORE row object to dict
row2dict = lambda r: dict(r._mapping)


class RatingRequest(Base):
    __tablename__ = 'rating_requests'
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    chunk: Mapped[str] = mapped_column(String)  # JSON serialized ChunkImport
    titles_lists: Mapped[str] = mapped_column(String)  # JSON serialized list of TitleImport
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    ratings_requested: Mapped[int] = mapped_column(default=1)
    ratings_done: Mapped[int] = mapped_column(default=0)
    ratings_to_go: Mapped[int] = mapped_column(default=1)

    rnd_number: Mapped[float] = mapped_column(default=randint(0, 1_000_000) / 1_000_000)


# the request_id and user_id together should be unique and form a composite primary key
class RatingResponse(Base):
    __tablename__ = 'rating_responses'
    request_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('rating_requests.id'), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    start_time: Mapped[datetime]
    end_time: Mapped[datetime]
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    ratings: Mapped[str] = mapped_column(String)  # JSON serialized list of SingleRating