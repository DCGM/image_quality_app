"""Tests for image_store.py — ZIP extraction and group_id parsing."""
import asyncio
import io
import sys
import tempfile
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from image_rater.database import Base
from image_rater.db_model import Task, TaskType
from image_rater.image_store import _parse_group_id, ingest_zip


# ---------------------------------------------------------------------------
# _parse_group_id
# ---------------------------------------------------------------------------

def test_parse_group_id_underscore():
    assert _parse_group_id("groupA_01.jpg") == "groupA"


def test_parse_group_id_dash():
    assert _parse_group_id("photo-003.png") == "photo"


def test_parse_group_id_no_suffix():
    assert _parse_group_id("standalone.jpg") == "standalone"


def test_parse_group_id_multi_part():
    assert _parse_group_id("scene_night_042.jpg") == "scene_night"


# ---------------------------------------------------------------------------
# ingest_zip
# ---------------------------------------------------------------------------

def _make_zip(filenames: list[str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name in filenames:
            # 1x1 white PNG
            import struct, zlib
            def png_1x1():
                def chunk(name, data):
                    c = name + data
                    return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)
                sig = b'\x89PNG\r\n\x1a\n'
                ihdr = chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0))
                idat = chunk(b'IDAT', zlib.compress(b'\x00\xff\xff\xff'))
                iend = chunk(b'IEND', b'')
                return sig + ihdr + idat + iend
            zf.writestr(name, png_1x1())
    return buf.getvalue()


def test_ingest_zip_creates_records():
    async def _run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        Session = async_sessionmaker(engine, expire_on_commit=False)

        with tempfile.TemporaryDirectory() as tmpdir:
            async with Session() as db:
                task = Task(
                    id="quality",
                    name="Quality",
                    description_md="",
                    instructions_md="",
                    task_type=TaskType.two_forced_choice,
                )
                db.add(task)
                await db.commit()

            async with Session() as db:
                zip_bytes = _make_zip(["sceneA_01.png", "sceneA_02.png", "sceneB_01.png"])
                count = await ingest_zip(db, "quality", zip_bytes, tmpdir)
                await db.commit()

            assert count == 3

            from image_rater.db_model import ImageItem
            from sqlalchemy import select
            async with Session() as db:
                result = await db.execute(select(ImageItem).where(ImageItem.task_id == "quality"))
                items = result.scalars().all()
            assert len(items) == 3
            groups = {item.group_id for item in items}
            assert "sceneA" in groups
            assert "sceneB" in groups

        await engine.dispose()

    asyncio.run(_run())


def test_ingest_zip_upserts():
    async def _run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        Session = async_sessionmaker(engine, expire_on_commit=False)

        with tempfile.TemporaryDirectory() as tmpdir:
            async with Session() as db:
                task = Task(
                    id="quality",
                    name="Quality",
                    description_md="",
                    instructions_md="",
                    task_type=TaskType.two_forced_choice,
                )
                db.add(task)
                await db.commit()

            async with Session() as db:
                zip_bytes = _make_zip(["img_01.png"])
                count1 = await ingest_zip(db, "quality", zip_bytes, tmpdir)
                await db.commit()

            async with Session() as db:
                count2 = await ingest_zip(db, "quality", zip_bytes, tmpdir)
                await db.commit()

            assert count1 == 1
            assert count2 == 1  # upsert — no duplicates

            from image_rater.db_model import ImageItem
            from sqlalchemy import select
            async with Session() as db:
                result = await db.execute(select(ImageItem))
                items = result.scalars().all()
            assert len(items) == 1

        await engine.dispose()

    asyncio.run(_run())
