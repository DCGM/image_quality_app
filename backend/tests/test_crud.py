"""Integration tests for CRUD operations and API routes."""
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from image_rater.base_objects import ComparisonSubmit, RatingSubmit, TaskCreate
from image_rater.crud import (
    get_rankings, global_stats, leaderboard_overall, my_stats,
    save_comparison, save_rating, upsert_task,
)
from image_rater.database import Base
from image_rater.db_model import ImageItem, ImageRanking, Task, TaskType


def _engine_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _setup_2fc_task(db):
    task = TaskCreate(
        id="quality",
        name="Quality",
        description_md="desc",
        instructions_md="instructions",
        task_type="two_forced_choice",
        pair_algorithm="least_seen",
        calib_ratio=0.0,
    )
    t = await upsert_task(db, task)
    for i in range(3):
        item = ImageItem(
            id=f"quality/img_{i}.jpg",
            task_id="quality",
            filename=f"img_{i}.jpg",
            group_id="scene",
            file_path=f"/tmp/img_{i}.jpg",
        )
        db.add(item)
        ranking = ImageRanking(image_id=item.id, task_id="quality")
        db.add(ranking)
    await db.commit()
    return t


async def _setup_rating_task(db):
    task = TaskCreate(
        id="sharpness",
        name="Sharpness",
        description_md="desc",
        instructions_md="instructions",
        task_type="single_rating",
        rating_options=["Low", "Medium", "High"],
        calib_ratio=0.0,
    )
    t = await upsert_task(db, task)
    item = ImageItem(
        id="sharpness/img_0.jpg",
        task_id="sharpness",
        filename="img_0.jpg",
        group_id="scene",
        file_path="/tmp/img_0.jpg",
    )
    db.add(item)
    await db.commit()
    return t


def test_save_comparison_awards_points():
    async def _run():
        engine, Session = _engine_session()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with Session() as db:
            task = await _setup_2fc_task(db)

        async with Session() as db:
            task = await db.get(Task, "quality")
            payload = ComparisonSubmit(
                task_id="quality",
                image_a_id="quality/img_0.jpg",
                image_b_id="quality/img_1.jpg",
                winner_id="quality/img_0.jpg",
                start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc),
            )
            points = await save_comparison(db, "user-1", payload, task)
            await db.commit()

        assert points > 0

        await engine.dispose()

    asyncio.run(_run())


def test_save_comparison_updates_elo():
    async def _run():
        engine, Session = _engine_session()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with Session() as db:
            await _setup_2fc_task(db)

        async with Session() as db:
            task = await db.get(Task, "quality")
            payload = ComparisonSubmit(
                task_id="quality",
                image_a_id="quality/img_0.jpg",
                image_b_id="quality/img_1.jpg",
                winner_id="quality/img_0.jpg",
                start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc),
            )
            await save_comparison(db, "user-1", payload, task)
            await db.commit()

        async with Session() as db:
            rankings = await get_rankings(db, "quality")

        winner = next(r for r in rankings if r.image_id == "quality/img_0.jpg")
        loser = next(r for r in rankings if r.image_id == "quality/img_1.jpg")
        assert winner.score > 1000.0
        assert loser.score < 1000.0
        assert winner.wins == 1

        await engine.dispose()

    asyncio.run(_run())


def test_save_comparison_invalid_winner():
    async def _run():
        engine, Session = _engine_session()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with Session() as db:
            await _setup_2fc_task(db)

        async with Session() as db:
            task = await db.get(Task, "quality")
            payload = ComparisonSubmit(
                task_id="quality",
                image_a_id="quality/img_0.jpg",
                image_b_id="quality/img_1.jpg",
                winner_id="quality/img_2.jpg",  # NOT one of the pair
                start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc),
            )
            try:
                await save_comparison(db, "user-1", payload, task)
                assert False, "Should have raised ValueError"
            except ValueError:
                pass

        await engine.dispose()

    asyncio.run(_run())


def test_save_rating_validates_option():
    async def _run():
        engine, Session = _engine_session()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with Session() as db:
            await _setup_rating_task(db)

        async with Session() as db:
            task = await db.get(Task, "sharpness")
            payload = RatingSubmit(
                task_id="sharpness",
                image_id="sharpness/img_0.jpg",
                selected_option="VeryHigh",  # Not in options
                start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc),
            )
            try:
                await save_rating(db, "user-1", payload, task)
                assert False, "Should have raised ValueError"
            except ValueError:
                pass

        await engine.dispose()

    asyncio.run(_run())


def test_save_rating_valid():
    async def _run():
        engine, Session = _engine_session()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with Session() as db:
            await _setup_rating_task(db)

        async with Session() as db:
            task = await db.get(Task, "sharpness")
            payload = RatingSubmit(
                task_id="sharpness",
                image_id="sharpness/img_0.jpg",
                selected_option="High",
                start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc),
            )
            points = await save_rating(db, "user-1", payload, task)
            await db.commit()

        assert points > 0

        await engine.dispose()

    asyncio.run(_run())


def test_my_stats_and_global_stats():
    async def _run():
        engine, Session = _engine_session()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with Session() as db:
            await _setup_2fc_task(db)

        async with Session() as db:
            task = await db.get(Task, "quality")
            payload = ComparisonSubmit(
                task_id="quality",
                image_a_id="quality/img_0.jpg",
                image_b_id="quality/img_1.jpg",
                winner_id="quality/img_0.jpg",
                start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc),
            )
            await save_comparison(db, "user-1", payload, task)
            await db.commit()

        async with Session() as db:
            stats = await my_stats(db, "user-1")
            assert stats.total_comparisons == 1
            assert stats.score > 0

            g_stats = await global_stats(db)
            assert g_stats.total_comparisons == 1

        await engine.dispose()

    asyncio.run(_run())
