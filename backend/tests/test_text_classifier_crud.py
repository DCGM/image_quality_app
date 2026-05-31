import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

sys.path.append(str(Path(__file__).resolve().parents[1]))

from text_classifier.base_objects import AnnotationSubmit, TaskAnnotation, TaskClass, TaskDefinition, TaskStatePatch
from text_classifier.crud import (
    bulk_upsert_annotations, get_next_text, get_reliability, global_stats,
    leaderboard, leaderboard_overall, list_enabled_tasks, list_tasks, list_texts,
    my_stats, save_annotations, set_annotation_type, set_task_state, set_text_suspended,
    upsert_task, upsert_text,
)
from text_classifier.database import Base
from text_classifier.db_model import Annotation, AnnotationType, Task, UserReliability

_PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"


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

            text, calib_ids = await get_next_text(db, uuid4(), ['style'])
            assert text is not None
            assert isinstance(calib_ids, list)
            tasks_map = {'style': await db.get(Task, 'style')}
            uid = uuid4()
            payload = AnnotationSubmit(text_id='t1', annotations=[TaskAnnotation(task_id='style', selected_classes=['formal'], start_time=datetime.utcnow(), end_time=datetime.utcnow())])
            points = await save_annotations(db, uid, payload, tasks_map)
            assert 'style' in points
            assert points['style'] >= 1.0

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
            nxt, calib_ids = await get_next_text(db, uuid4(), ['t'])
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


def test_save_annotations_returns_points():
    """save_annotations returns a points dict with float >= 1.0 for user annotations."""
    async def _run():
        engine, Session = _make_engine_and_session()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as db:
            task = TaskDefinition(
                id='pts', name='Points', description_md='d', multi_choice=False,
                max_choices=1, enabled=True,
                classes=[TaskClass(id='a', label_en='A', label_cs='a')],
            )
            await upsert_task(db, task)
            await upsert_text(db, 'tx', 'hello', 'eng', {'id': 'tx', 'text': 'hello', 'language': 'eng'})
            await db.commit()
            tasks_map = {'pts': await db.get(Task, 'pts')}
            now = datetime.utcnow()
            payload = AnnotationSubmit(
                text_id='tx',
                annotations=[TaskAnnotation(task_id='pts', selected_classes=['a'], start_time=now, end_time=now)],
            )
            points = await save_annotations(db, uuid4(), payload, tasks_map)
            assert isinstance(points, dict)
            assert 'pts' in points
            assert points['pts'] == 1.0  # first annotator: A=0, base=1, delta=0
        await engine.dispose()

    asyncio.run(_run())


def test_bulk_gt_annotations_and_calibration_path():
    """GT annotations are stored correctly; calibration path returns GT-covered text."""
    from text_classifier.base_objects import BulkAnnotationItem

    async def _run():
        engine, Session = _make_engine_and_session()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as db:
            task = TaskDefinition(
                id='cal', name='Cal', description_md='d', multi_choice=False,
                max_choices=1, enabled=True,
                classes=[TaskClass(id='x', label_en='X', label_cs='x')],
                calib_ratio_initial=1.0,  # always request calibration
                calib_initial_count=0,    # treat every annotation as ongoing
                calib_ratio_ongoing=1.0,
            )
            await upsert_task(db, task)
            await upsert_text(db, 'gt_txt', 'ground truth text', 'eng', {'id': 'gt_txt', 'text': 'ground truth text', 'language': 'eng'})
            await db.commit()

            # Upload a GT annotation
            admin_id = uuid4()
            items = [BulkAnnotationItem(text_id='gt_txt', task_id='cal', selected_classes=['x'])]
            count = await bulk_upsert_annotations(db, items, AnnotationType.ground_truth, admin_id)
            await db.commit()
            assert count == 1

            # A new user should get the calibration text
            user_id = uuid4()
            text, calib_ids = await get_next_text(db, user_id, ['cal'])
            assert text is not None
            assert text.id == 'gt_txt'
            assert 'cal' in calib_ids
        await engine.dispose()

    asyncio.run(_run())


def test_leaderboard_includes_score():
    """Leaderboard rows include count and score."""
    async def _run():
        engine, Session = _make_engine_and_session()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as db:
            task = TaskDefinition(
                id='lb2', name='LB2', description_md='d', multi_choice=False,
                max_choices=1, enabled=True,
                classes=[TaskClass(id='z', label_en='Z', label_cs='z')],
            )
            await upsert_task(db, task)
            await upsert_text(db, 'lb_txt', 'some text', 'eng', {'id': 'lb_txt', 'text': 'some text', 'language': 'eng'})
            await db.commit()
            uid = uuid4()
            tasks_map = {'lb2': await db.get(Task, 'lb2')}
            now = datetime.utcnow()
            await save_annotations(db, uid, AnnotationSubmit(
                text_id='lb_txt',
                annotations=[TaskAnnotation(task_id='lb2', selected_classes=['z'], start_time=now, end_time=now)],
            ), tasks_map)
            await db.commit()
            lb = await leaderboard(db, 'lb2')
            assert len(lb) == 1
            assert 'score' in lb[0]
            assert lb[0]['count'] == 1
            assert lb[0]['score'] >= 1.0
            lb_all = await leaderboard_overall(db)
            assert len(lb_all) == 1
            assert 'score' in lb_all[0]
        await engine.dispose()

    asyncio.run(_run())


def test_my_stats_includes_score():
    """my_stats returns total, per_task, score, per_task_score."""
    from text_classifier.crud import my_stats

    async def _run():
        engine, Session = _make_engine_and_session()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as db:
            task = TaskDefinition(
                id='ms', name='MS', description_md='d', multi_choice=False,
                max_choices=1, enabled=True,
                classes=[TaskClass(id='q', label_en='Q', label_cs='q')],
            )
            await upsert_task(db, task)
            await upsert_text(db, 'ms_txt', 'text', 'eng', {'id': 'ms_txt', 'text': 'text', 'language': 'eng'})
            await db.commit()
            uid = uuid4()
            tasks_map = {'ms': await db.get(Task, 'ms')}
            now = datetime.utcnow()
            await save_annotations(db, uid, AnnotationSubmit(
                text_id='ms_txt',
                annotations=[TaskAnnotation(task_id='ms', selected_classes=['q'], start_time=now, end_time=now)],
            ), tasks_map)
            await db.commit()
            stats = await my_stats(db, uid)
            assert stats['total'] == 1
            assert stats['per_task']['ms'] == 1
            assert 'score' in stats
            assert 'per_task_score' in stats
            assert stats['score'] >= 1.0
        await engine.dispose()

    asyncio.run(_run())


def test_list_enabled_tasks_includes_multiplier():
    """list_enabled_tasks returns dicts with current_multiplier populated."""
    async def _run():
        engine, Session = _make_engine_and_session()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as db:
            task = TaskDefinition(
                id='mult', name='Mult', description_md='d', multi_choice=False,
                max_choices=1, enabled=True,
                classes=[TaskClass(id='a', label_en='A', label_cs='a')],
                target_coverage=3,
            )
            await upsert_task(db, task)
            await upsert_text(db, 'mx', 'text', 'eng', {'id': 'mx', 'text': 'text', 'language': 'eng'})
            await db.commit()
            tasks = await list_enabled_tasks(db)
            assert len(tasks) == 1
            assert 'current_multiplier' in tasks[0]
            # 1 text, 0 user annotations => avg_coverage=0 => multiplier=2.0
            assert tasks[0]['current_multiplier'] == 2.0
        await engine.dispose()

    asyncio.run(_run())


def test_gt_feedback_via_get_gt_for_text_tasks():
    """get_gt_for_text_tasks returns selected_classes keyed by task_id."""
    from text_classifier.crud import get_gt_for_text_tasks
    from text_classifier.base_objects import BulkAnnotationItem

    async def _run():
        engine, Session = _make_engine_and_session()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as db:
            task = TaskDefinition(
                id='fb', name='FB', description_md='d', multi_choice=False,
                max_choices=1, enabled=True,
                classes=[TaskClass(id='yes', label_en='Yes', label_cs='ano')],
            )
            await upsert_task(db, task)
            await upsert_text(db, 'fbt', 'text', 'eng', {'id': 'fbt', 'text': 'text', 'language': 'eng'})
            await db.commit()
            admin_id = uuid4()
            items = [BulkAnnotationItem(text_id='fbt', task_id='fb', selected_classes=['yes'])]
            await bulk_upsert_annotations(db, items, AnnotationType.ground_truth, admin_id)
            await db.commit()
            gt = await get_gt_for_text_tasks(db, 'fbt', ['fb'])
            assert gt == {'fb': ['yes']}
            # Non-existent task returns empty
            gt2 = await get_gt_for_text_tasks(db, 'fbt', ['other'])
            assert gt2 == {}
        await engine.dispose()

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# set_task_state: enable / disable / delete
# ---------------------------------------------------------------------------

def test_task_state_patch():
    async def _run():
        engine, Session = _make_engine_and_session()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as db:
            task = TaskDefinition(
                id='sp', name='SP', description_md='d', multi_choice=False,
                max_choices=1, enabled=True,
                classes=[TaskClass(id='a', label_en='A', label_cs='a')],
            )
            await upsert_task(db, task)
            await db.commit()

            # Disable
            ok = await set_task_state(db, 'sp', TaskStatePatch(enabled=False))
            await db.commit()
            assert ok
            t = await db.get(Task, 'sp')
            assert t.enabled is False

            # Re-enable
            ok = await set_task_state(db, 'sp', TaskStatePatch(enabled=True))
            await db.commit()
            assert ok
            t = await db.get(Task, 'sp')
            assert t.enabled is True

            # Delete
            ok = await set_task_state(db, 'sp', TaskStatePatch(deleted=True))
            await db.commit()
            assert ok
            t = await db.get(Task, 'sp')
            assert t is None

            # Non-existent task returns False
            ok = await set_task_state(db, 'no_such_task', TaskStatePatch(enabled=False))
            assert not ok
        await engine.dispose()

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# list_tasks with enabled_only filter
# ---------------------------------------------------------------------------

def test_list_tasks_enabled_only():
    async def _run():
        engine, Session = _make_engine_and_session()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as db:
            for tid, enabled in [('t_on', True), ('t_off', False)]:
                await upsert_task(db, TaskDefinition(
                    id=tid, name=tid, description_md='d', multi_choice=False,
                    max_choices=1, enabled=enabled,
                    classes=[TaskClass(id='x', label_en='X', label_cs='x')],
                ))
            await db.commit()

            all_tasks = await list_tasks(db)
            assert len(all_tasks) == 2

            enabled_tasks = await list_tasks(db, enabled_only=True)
            assert len(enabled_tasks) == 1
            assert enabled_tasks[0].id == 't_on'
        await engine.dispose()

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# upsert_task updates an existing task
# ---------------------------------------------------------------------------

def test_upsert_task_updates_existing():
    async def _run():
        engine, Session = _make_engine_and_session()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as db:
            base = TaskDefinition(
                id='up', name='Old', description_md='old desc', multi_choice=False,
                max_choices=1, enabled=True,
                classes=[TaskClass(id='a', label_en='A', label_cs='a')],
            )
            await upsert_task(db, base)
            await db.commit()

            updated = TaskDefinition(
                id='up', name='New', description_md='new desc', multi_choice=False,
                max_choices=1, enabled=False,
                classes=[TaskClass(id='b', label_en='B', label_cs='b')],
            )
            await upsert_task(db, updated)
            await db.commit()

            t = await db.get(Task, 'up')
            assert t.name == 'New'
            assert t.description_md == 'new desc'
            assert t.enabled is False
        await engine.dispose()

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Multi-choice annotation stored correctly
# ---------------------------------------------------------------------------

def test_multi_choice_annotation_stored():
    async def _run():
        engine, Session = _make_engine_and_session()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as db:
            task = TaskDefinition(
                id='mc', name='MC', description_md='d', multi_choice=True, max_choices=2,
                enabled=True,
                classes=[
                    TaskClass(id='a', label_en='A', label_cs='a'),
                    TaskClass(id='b', label_en='B', label_cs='b'),
                    TaskClass(id='c', label_en='C', label_cs='c'),
                ],
            )
            await upsert_task(db, task)
            await upsert_text(db, 'mc_txt', 'text', 'eng', {'id': 'mc_txt'})
            await db.commit()
            uid = uuid4()
            tasks_map = {'mc': await db.get(Task, 'mc')}
            now = datetime.utcnow()
            payload = AnnotationSubmit(
                text_id='mc_txt',
                annotations=[TaskAnnotation(
                    task_id='mc', selected_classes=['a', 'b'],
                    start_time=now, end_time=now,
                )],
            )
            await save_annotations(db, uid, payload, tasks_map)
            await db.commit()

            from sqlalchemy import select as sa_select
            ann = (await db.execute(
                sa_select(Annotation).where(Annotation.user_id == uid)
            )).scalar_one()
            assert sorted(ann.selected_classes) == ['a', 'b']
        await engine.dispose()

    asyncio.run(_run())


def test_save_annotations_max_choices_exceeded():
    async def _run():
        engine, Session = _make_engine_and_session()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as db:
            task = TaskDefinition(
                id='mx2', name='MX2', description_md='d', multi_choice=True, max_choices=1,
                enabled=True,
                classes=[
                    TaskClass(id='a', label_en='A', label_cs='a'),
                    TaskClass(id='b', label_en='B', label_cs='b'),
                ],
            )
            await upsert_task(db, task)
            await upsert_text(db, 'mx2_txt', 'text', 'eng', {'id': 'mx2_txt'})
            await db.commit()
            tasks_map = {'mx2': await db.get(Task, 'mx2')}
            now = datetime.utcnow()
            payload = AnnotationSubmit(
                text_id='mx2_txt',
                annotations=[TaskAnnotation(
                    task_id='mx2', selected_classes=['a', 'b'],
                    start_time=now, end_time=now,
                )],
            )
            try:
                await save_annotations(db, uuid4(), payload, tasks_map)
            except ValueError as exc:
                assert 'max 1 choices' in str(exc)
            else:
                raise AssertionError('Exceeding max_choices should raise ValueError')
        await engine.dispose()

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# bulk_upsert_annotations is idempotent (upsert on duplicate)
# ---------------------------------------------------------------------------

def test_repeat_annotation_upserts():
    """Calling bulk_upsert_annotations twice for the same item updates, not duplicates."""
    from text_classifier.base_objects import BulkAnnotationItem
    from sqlalchemy import select as sa_select, func

    async def _run():
        engine, Session = _make_engine_and_session()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as db:
            await upsert_task(db, TaskDefinition(
                id='rep', name='Rep', description_md='d', multi_choice=False,
                max_choices=1, enabled=True,
                classes=[
                    TaskClass(id='x', label_en='X', label_cs='x'),
                    TaskClass(id='y', label_en='Y', label_cs='y'),
                ],
            ))
            await upsert_text(db, 'rep_t', 'text', 'eng', {'id': 'rep_t'})
            await db.commit()

            admin_id = uuid4()
            item = BulkAnnotationItem(text_id='rep_t', task_id='rep', selected_classes=['x'])
            await bulk_upsert_annotations(db, [item], AnnotationType.ground_truth, admin_id)
            await db.commit()

            # Update the same item
            item2 = BulkAnnotationItem(text_id='rep_t', task_id='rep', selected_classes=['y'])
            await bulk_upsert_annotations(db, [item2], AnnotationType.ground_truth, admin_id)
            await db.commit()

            # Still only 1 annotation row
            n = (await db.execute(
                sa_select(func.count()).select_from(Annotation)
                .where(Annotation.annotation_type == AnnotationType.ground_truth)
            )).scalar_one()
            assert n == 1

            # Classes updated to ['y']
            ann = (await db.execute(sa_select(Annotation))).scalar_one()
            assert ann.selected_classes == ['y']
        await engine.dispose()

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# set_annotation_type
# ---------------------------------------------------------------------------

def test_set_annotation_type():
    from sqlalchemy import select as sa_select

    async def _run():
        engine, Session = _make_engine_and_session()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as db:
            await upsert_task(db, TaskDefinition(
                id='sat', name='SAT', description_md='d', multi_choice=False,
                max_choices=1, enabled=True,
                classes=[TaskClass(id='v', label_en='V', label_cs='v')],
            ))
            await upsert_text(db, 'sat_t', 'text', 'eng', {'id': 'sat_t'})
            await db.commit()
            uid = uuid4()
            tasks_map = {'sat': await db.get(Task, 'sat')}
            now = datetime.utcnow()
            await save_annotations(db, uid, AnnotationSubmit(
                text_id='sat_t',
                annotations=[TaskAnnotation(task_id='sat', selected_classes=['v'], start_time=now, end_time=now)],
            ), tasks_map)
            await db.commit()

            ann = (await db.execute(sa_select(Annotation))).scalar_one()
            assert ann.annotation_type == AnnotationType.user

            ok = await set_annotation_type(db, ann.id, AnnotationType.ground_truth)
            await db.commit()
            assert ok

            ann = await db.get(Annotation, ann.id)
            assert ann.annotation_type == AnnotationType.ground_truth

            # Non-existent ID returns False
            ok = await set_annotation_type(db, uuid4(), AnnotationType.user)
            assert not ok
        await engine.dispose()

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# get_reliability returns rows after run_reliability_job
# ---------------------------------------------------------------------------

def test_run_reliability_job_and_get_reliability():
    """
    After multiple users annotate the same texts, run_reliability_job populates
    UserReliability rows with valid pairwise_agreement values.
    """
    from text_classifier.reliability import run_reliability_job
    from sqlalchemy import select as sa_select

    async def _run():
        engine, Session = _make_engine_and_session()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as db:
            task = TaskDefinition(
                id='irr', name='IRR', description_md='d', multi_choice=False,
                max_choices=1, enabled=True,
                classes=[
                    TaskClass(id='pos', label_en='Pos', label_cs='pos'),
                    TaskClass(id='neg', label_en='Neg', label_cs='neg'),
                ],
            )
            await upsert_task(db, task)
            # Create 10 texts
            text_ids = [f'irr_t{i}' for i in range(10)]
            for tid in text_ids:
                await upsert_text(db, tid, f'text {tid}', 'eng', {'id': tid})
            await db.commit()

            # Two users annotate all 10 texts (user_a agrees with user_b on 8/10)
            user_a, user_b = uuid4(), uuid4()
            agree_pattern = ['pos', 'pos', 'pos', 'pos', 'pos', 'pos', 'pos', 'pos', 'neg', 'neg']
            disagree_b    = ['pos', 'pos', 'pos', 'pos', 'pos', 'pos', 'pos', 'pos', 'pos', 'pos']
            now = datetime.utcnow()
            for i, tid in enumerate(text_ids):
                db.add(Annotation(
                    user_id=user_a, text_id=tid, task_id='irr',
                    selected_classes=[agree_pattern[i]],
                    start_time=now, end_time=now, annotation_type=AnnotationType.user,
                ))
                db.add(Annotation(
                    user_id=user_b, text_id=tid, task_id='irr',
                    selected_classes=[disagree_b[i]],
                    start_time=now, end_time=now, annotation_type=AnnotationType.user,
                ))
            await db.commit()

            await run_reliability_job(db)
            await db.commit()

            # Both users should have a UserReliability row
            rows = (await db.execute(
                sa_select(UserReliability).where(UserReliability.task_id == 'irr')
            )).scalars().all()
            assert len(rows) == 2

            # Pairwise agreement: user_a agreed with user_b on 8/10 = 0.8
            row_a = next(r for r in rows if r.user_id == user_a)
            assert row_a.pairwise_agreement is not None
            assert abs(row_a.pairwise_agreement - 0.8) < 1e-9
            assert row_a.annotation_count == 10

            # get_reliability returns the same data
            rel = await get_reliability(db)
            assert len(rel) == 2
            rel_a = next(r for r in rel if r['user_id'] == str(user_a))
            assert abs(rel_a['pairwise_agreement'] - 0.8) < 1e-9

            # Filter by user_id
            rel_filtered = await get_reliability(db, user_id=user_a)
            assert len(rel_filtered) == 1
            assert rel_filtered[0]['user_id'] == str(user_a)

            # Filter by task_id
            rel_task = await get_reliability(db, task_id='irr')
            assert len(rel_task) == 2
        await engine.dispose()

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# load_prompts against real prompts directory
# ---------------------------------------------------------------------------

def test_prompt_import_persistence():
    """load_prompts loads all .md files; upsert_task persists them to DB."""
    import pytest
    from text_classifier.prompt_parser import load_prompts

    async def _run():
        if not _PROMPTS_DIR.exists():
            pytest.skip(f'Prompts directory not found: {_PROMPTS_DIR}')

        engine, Session = _make_engine_and_session()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as db:
            prompts = load_prompts(_PROMPTS_DIR)
            assert len(prompts) > 0, 'Expected at least one prompt file'

            for p in prompts:
                td = TaskDefinition(**p)
                await upsert_task(db, td)
            await db.commit()

            tasks = await list_tasks(db)
            task_ids = {t.id for t in tasks}
            prompt_ids = {p['id'] for p in prompts}
            assert prompt_ids == task_ids, 'All loaded prompts should be in DB'

            # Each task has at least one class
            for t in tasks:
                assert len(t.classes) >= 1, f'Task {t.id} has no classes'
        await engine.dispose()

    asyncio.run(_run())

