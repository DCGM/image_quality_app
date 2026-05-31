import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

sys.path.append(str(Path(__file__).resolve().parents[1]))

from text_classifier.base_objects import AnnotationSubmit, TaskAnnotation, TaskClass, TaskDefinition
from text_classifier.crud import (
    get_next_text, global_stats, leaderboard, leaderboard_overall, list_texts,
    save_annotations, set_text_suspended, upsert_task, upsert_text,
)
from text_classifier.database import Base
from text_classifier.db_model import Annotation, Task


def test_task_text_and_annotation_flow():
    async def _run():
        engine = create_async_engine('sqlite+aiosqlite:///:memory:')
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        Session = async_sessionmaker(engine, expire_on_commit=False)
        async with Session() as db:
            task = TaskDefinition(
                id='style', name='Style', description_md='desc', multi_choice=False,
                max_choices=1, enabled=True, classes=[TaskClass(id='formal', label_en='Formal', label_cs='formální')]
            )
            await upsert_task(db, task)
            await upsert_text(db, 't1', 'hello', 'eng', {'id': 't1', 'text': 'hello', 'language': 'eng'})
            await db.commit()

            nxt = await get_next_text(db, uuid4(), ['style'])
            assert nxt is not None
            tasks_map = {'style': await db.get(Task, 'style')}
            payload = AnnotationSubmit(text_id='t1', annotations=[TaskAnnotation(task_id='style', selected_classes=['formal'], start_time=datetime.utcnow(), end_time=datetime.utcnow())])
            await save_annotations(db, uuid4(), payload, tasks_map)

        await engine.dispose()

    asyncio.run(_run())


def test_multi_choice_limits_and_unknown_classes_are_validated():
    async def _run():
        engine = create_async_engine('sqlite+aiosqlite:///:memory:')
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        Session = async_sessionmaker(engine, expire_on_commit=False)
        async with Session() as db:
            task = TaskDefinition(
                id='mode', name='Mode', description_md='desc', multi_choice=True, max_choices=2,
                enabled=True,
                classes=[
                    TaskClass(id='record', label_en='Record', label_cs='záznamový'),
                    TaskClass(id='description', label_en='Description', label_cs='popisný'),
                ],
            )
            await upsert_task(db, task)
            await db.commit()
            tasks_map = {'mode': await db.get(Task, 'mode')}
            payload = AnnotationSubmit(
                text_id='t1',
                annotations=[TaskAnnotation(task_id='mode', selected_classes=['record', 'bad'], start_time=datetime.utcnow(), end_time=datetime.utcnow())],
            )
            try:
                await save_annotations(db, uuid4(), payload, tasks_map)
            except ValueError as exc:
                assert 'unknown classes: bad' in str(exc)
            else:
                raise AssertionError('Unknown class should fail')

        await engine.dispose()

    asyncio.run(_run())


def _make_engine_and_session():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    Session = async_sessionmaker(engine, expire_on_commit=False)
    return engine, Session


def test_suspended_text_excluded_from_next():
    async def _run():
        engine, Session = _make_engine_and_session()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as db:
            task = TaskDefinition(
                id='t', name='T', description_md='d', multi_choice=False, max_choices=1,
                enabled=True, classes=[TaskClass(id='a', label_en='A', label_cs='a')],
            )
            await upsert_task(db, task)
            await upsert_text(db, 'txt1', 'hello', 'eng', {'id': 'txt1', 'text': 'hello', 'language': 'eng'})
            await db.commit()
            await set_text_suspended(db, 'txt1', True)
            await db.commit()
            nxt = await get_next_text(db, uuid4(), ['t'])
            assert nxt is None, 'Suspended text should not be returned'
        await engine.dispose()

    asyncio.run(_run())


def test_text_list_and_suspension():
    async def _run():
        engine, Session = _make_engine_and_session()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as db:
            await upsert_text(db, 'a', 'apple', 'eng', {'id': 'a', 'text': 'apple', 'language': 'eng'})
            await upsert_text(db, 'b', 'banana', 'eng', {'id': 'b', 'text': 'banana', 'language': 'eng'})
            await db.commit()
            result = await list_texts(db)
            assert result['total'] == 2
            assert all(not item['suspended'] for item in result['items'])
            await set_text_suspended(db, 'a', True)
            await db.commit()
            result = await list_texts(db)
            suspended = [i for i in result['items'] if i['id'] == 'a']
            assert suspended[0]['suspended'] is True
        await engine.dispose()

    asyncio.run(_run())


def test_leaderboard_since_filter():
    async def _run():
        engine, Session = _make_engine_and_session()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as db:
            task = TaskDefinition(
                id='s', name='S', description_md='d', multi_choice=False, max_choices=1,
                enabled=True, classes=[TaskClass(id='x', label_en='X', label_cs='x')],
            )
            await upsert_task(db, task)
            await upsert_text(db, 't1', 'hi', 'eng', {'id': 't1', 'text': 'hi', 'language': 'eng'})
            await db.commit()
            uid = uuid4()
            tasks_map = {'s': await db.get(Task, 's')}
            past_time = datetime(2020, 1, 1, tzinfo=timezone.utc)
            payload = AnnotationSubmit(
                text_id='t1',
                annotations=[TaskAnnotation(task_id='s', selected_classes=['x'], start_time=past_time, end_time=past_time)],
            )
            await save_annotations(db, uid, payload, tasks_map)
            await db.commit()
            # Override created_at to past
            ann = (await db.execute(Annotation.__table__.select())).first()
            await db.execute(
                Annotation.__table__.update().where(Annotation.__table__.c.id == ann.id).values(created_at=datetime(2020, 1, 1))
            )
            await db.commit()
            # All-time: should have 1 entry
            lb_all = await leaderboard(db, 's')
            assert len(lb_all) == 1
            # Filtered to last 7 days: should be empty
            recent = datetime.now(timezone.utc) - timedelta(days=7)
            lb_recent = await leaderboard(db, 's', since=recent)
            assert len(lb_recent) == 0
        await engine.dispose()

    asyncio.run(_run())


def test_global_stats():
    async def _run():
        engine, Session = _make_engine_and_session()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as db:
            task = TaskDefinition(
                id='g', name='G', description_md='d', multi_choice=False, max_choices=1,
                enabled=True, classes=[TaskClass(id='y', label_en='Y', label_cs='y')],
            )
            await upsert_task(db, task)
            await upsert_text(db, 'tx', 'text', 'eng', {'id': 'tx', 'text': 'text', 'language': 'eng'})
            await db.commit()
            tasks_map = {'g': await db.get(Task, 'g')}
            now = datetime.utcnow()
            payload = AnnotationSubmit(
                text_id='tx',
                annotations=[TaskAnnotation(task_id='g', selected_classes=['y'], start_time=now, end_time=now)],
            )
            await save_annotations(db, uuid4(), payload, tasks_map)
            await db.commit()
            stats = await global_stats(db)
            assert stats['total_annotations'] == 1
            assert stats['per_task'][0]['task_id'] == 'g'
            assert stats['per_task'][0]['count'] == 1
        await engine.dispose()

    asyncio.run(_run())

