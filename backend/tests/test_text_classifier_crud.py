import asyncio
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

sys.path.append(str(Path(__file__).resolve().parents[1]))

from text_classifier.base_objects import AnnotationSubmit, TaskAnnotation, TaskClass, TaskDefinition
from text_classifier.crud import get_next_text, save_annotations, upsert_task, upsert_text
from text_classifier.database import Base
from text_classifier.db_model import Task


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
