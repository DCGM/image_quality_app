from __future__ import annotations

from sqlalchemy import func, select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from text_classifier import base_objects
from text_classifier.db_model import Annotation, Task, TextItem


async def upsert_task(db: AsyncSession, task: base_objects.TaskDefinition) -> None:
    db_task = await db.get(Task, task.id)
    payload = task.model_dump()
    if db_task is None:
        db.add(Task(**payload))
    else:
        for k, v in payload.items():
            setattr(db_task, k, v)


async def set_task_state(db: AsyncSession, task_id: str, patch: base_objects.TaskStatePatch) -> bool:
    task = await db.get(Task, task_id)
    if task is None:
        return False
    if patch.deleted:
        await db.execute(delete(Task).where(Task.id == task_id))
        return True
    if patch.enabled is not None:
        task.enabled = patch.enabled
    return True


async def list_enabled_tasks(db: AsyncSession) -> list[Task]:
    rows = await db.execute(select(Task).where(Task.enabled.is_(True)).order_by(Task.id))
    return list(rows.scalars().all())


async def get_next_text(db: AsyncSession, user_id, task_ids: list[str]):
    subq = (
        select(Annotation.text_id, func.count(Annotation.id).label("coverage"))
        .where(Annotation.task_id.in_(task_ids))
        .group_by(Annotation.text_id)
        .subquery()
    )
    user_done = select(Annotation.text_id).where(Annotation.user_id == user_id, Annotation.task_id.in_(task_ids)).subquery()
    q = (
        select(TextItem)
        .outerjoin(subq, TextItem.id == subq.c.text_id)
        .where(TextItem.id.not_in(select(user_done.c.text_id)))
        .order_by(func.coalesce(subq.c.coverage, 0).asc(), TextItem.id.asc())
        .limit(1)
    )
    return (await db.execute(q)).scalar_one_or_none()


async def save_annotations(db: AsyncSession, user_id, payload: base_objects.AnnotationSubmit, tasks_map: dict[str, Task]):
    for ann in payload.annotations:
        task = tasks_map[ann.task_id]
        if task.multi_choice:
            if len(ann.selected_classes) > task.max_choices:
                raise ValueError(f"Task {task.id} allows max {task.max_choices} choices")
        elif len(ann.selected_classes) != 1:
            raise ValueError(f"Task {task.id} requires exactly one choice")
        db.add(Annotation(user_id=user_id, text_id=payload.text_id, task_id=ann.task_id,
                          selected_classes=ann.selected_classes, start_time=ann.start_time, end_time=ann.end_time))


async def my_stats(db: AsyncSession, user_id):
    per_task = await db.execute(select(Annotation.task_id, func.count()).where(Annotation.user_id == user_id).group_by(Annotation.task_id))
    totals = {task_id: count for task_id, count in per_task.all()}
    return {"total": sum(totals.values()), "per_task": totals}


async def leaderboard(db: AsyncSession, task_id: str):
    rows = await db.execute(
        select(Annotation.user_id, func.count().label("count"))
        .where(Annotation.task_id == task_id)
        .group_by(Annotation.user_id)
        .order_by(func.count().desc())
        .limit(20)
    )
    return [{"user_id": str(u), "count": c} for u, c in rows.all()]


async def upsert_text(db: AsyncSession, text_id: str, text: str, language: str, raw_json: dict):
    db_text = await db.get(TextItem, text_id)
    if db_text is None:
        db.add(TextItem(id=text_id, text=text, language=language, raw_json=raw_json))
    else:
        db_text.text = text
        db_text.language = language
        db_text.raw_json = raw_json
