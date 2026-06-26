"""Tests for pair_selector.py — all three algorithms."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from image_rater.database import Base
from image_rater.db_model import ImageItem, ImageRanking, Task, TaskType
from image_rater.pair_selector import (
    _least_seen_pair,
    _swiss_pair,
    get_next_pair,
)


def _make_item(id: str, group: str, score: float = 1000.0, comps: int = 0, wins: int = 0) -> ImageItem:
    item = ImageItem(
        id=id, task_id="t", filename=f"{id}.jpg",
        group_id=group, file_path=f"/tmp/{id}.jpg",
    )
    item.ranking = ImageRanking(
        image_id=id, task_id="t",
        score=score, comparisons=comps, wins=wins,
    )
    return item


def test_least_seen_prefers_fewer_comparisons():
    imgs = [
        _make_item("a", "g", comps=5),
        _make_item("b", "g", comps=2),
        _make_item("c", "g", comps=10),
    ]
    groups = {"g": imgs}
    result = _least_seen_pair(groups, set())
    assert result is not None
    a, b, group_id = result
    # The pair with fewest total comparisons should be (b, a) or (b, c)
    assert b.id == "b" or a.id == "b"


def test_swiss_pairs_similar_win_ratios():
    imgs = [
        _make_item("top", "g", comps=10, wins=9),
        _make_item("mid", "g", comps=10, wins=5),
        _make_item("low", "g", comps=10, wins=1),
    ]
    groups = {"g": imgs}
    result = _swiss_pair(groups, set())
    assert result is not None
    a, b, _ = result
    # Swiss should not pair top with low if better options exist
    pair_ids = {a.id, b.id}
    assert pair_ids != {"top", "low"}


def test_least_seen_skips_seen_pairs():
    imgs = [_make_item("a", "g"), _make_item("b", "g"), _make_item("c", "g")]
    groups = {"g": imgs}
    seen = {frozenset(["a", "b"]), frozenset(["a", "c"])}
    result = _least_seen_pair(groups, seen)
    assert result is not None
    a, b, _ = result
    assert frozenset([a.id, b.id]) == frozenset(["b", "c"])


def test_no_pair_when_all_seen():
    imgs = [_make_item("a", "g"), _make_item("b", "g")]
    groups = {"g": imgs}
    seen = {frozenset(["a", "b"])}
    result = _least_seen_pair(groups, seen)
    assert result is None


def test_get_next_pair_integration():
    async def _run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        Session = async_sessionmaker(engine, expire_on_commit=False)

        async with Session() as db:
            task = Task(
                id="quality",
                name="Quality",
                description_md="",
                instructions_md="",
                task_type=TaskType.two_forced_choice,
                pair_algorithm="least_seen",
                calib_ratio=0.0,  # No re-shows in this test
            )
            db.add(task)
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

            result = await get_next_pair(db, "user-uuid-123", task)
            assert result is not None
            img_a, img_b, group_id, is_rel = result
            assert group_id == "scene"
            assert not is_rel
            assert img_a.id != img_b.id

        await engine.dispose()

    asyncio.run(_run())
