import sys
import json
import asyncio
from pathlib import Path
from uuid import uuid4, UUID
from datetime import datetime, timedelta

import pytest

# Ensure backend root on path
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import exc, select, update, func, and_, delete, or_


from title_annotator.db_model import Base, RatingRequest as ORMRatingRequest, RatingResponse as ORMRatingResponse
from title_annotator import base_objects, ChunkImport, db_model
from tools.common import chunk_to_rating_request


@pytest.mark.asyncio
class TestCrudIntegration:
    async def async_set_up_db(self) -> tuple[str, async_sessionmaker[AsyncSession]]:
        tmp_dir = Path.cwd() / ".pytest_tmp"
        tmp_dir.mkdir(exist_ok=True)
        db_path = tmp_dir / f"test_{uuid4().hex}.db"
        url = f"sqlite+aiosqlite:///{db_path}"
        engine = create_async_engine(url)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_maker = async_sessionmaker(engine, expire_on_commit=False, autoflush=False, autocommit=False)
        return url, session_maker

    def load_titles_from_jsonl(self) -> list[ChunkImport]:
        jsonl_path = Path(__file__).parent / "test_import_data.jsonl"
        assert jsonl_path.exists(), "Fixture JSONL file missing"

        chunks: list[ChunkImport] = []
        with jsonl_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                chunks.append(ChunkImport.model_validate_json(line))

        assert chunks, "No chunks loaded from test_import_data.jsonl"
        return chunks

    async def test_crud_flow(self):
        # Init DB
        _, session_maker = await self.async_set_up_db()

        chunks = self.load_titles_from_jsonl()

        for chunk in chunks:
            rr_new = chunk_to_rating_request(chunk, ratings_requested=1)

        # Use CRUD to insert request
        from title_annotator import crud
        async with session_maker() as session:
            await crud.add_rating_request(session, rr_new)

        # Verify inserted row in ORM directly
        async with session_maker() as session:
            stmt = (
                select(db_model.RatingRequest)
            )
            res = await session.execute(stmt)
            rows = res.fetchall()
            assert len(rows) == 1

        # Fetch random rating request for a user
        user_id = uuid4()
        async with session_maker() as session:
            rr = await crud.get_random_rating_request(session, user_id)

        # Validate pydantic object structure and grouping
        assert isinstance(rr, base_objects.RatingRequest)
        assert rr.chunk.id == rr_new.chunk.id
        assert rr.ratings_requested == 1
        assert rr.titles_lists == rr_new.titles_lists

        ratings = []
        for titles in rr.titles_lists:
            rated_titles = [base_objects.RatedTitle(
                prefered=True,
                is_irrelevant=False,
                is_gibberish=True,
                is_relevant=True,
                **title.model_dump()) for title in titles]
            rating = base_objects.SingleRating(
                titles=rated_titles,
                start_time=datetime.utcnow(),
                end_time=datetime.utcnow())
            ratings.append(rating)

        rating_response = base_objects.RatingResponseNew(
            id=str(uuid4()),
            request_id=rr.id,
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow(),
            ratings=ratings
        )

        async with session_maker() as session:
            await crud.save_rating_response(session, rating_response, user_id)

        # Verify response stored and request counters updated
        async with session_maker() as session:
            stmt = (
                select(db_model.RatingResponse)
            )
            res = await session.execute(stmt)
            rows = res.fetchall()
            assert len(rows) == 1
