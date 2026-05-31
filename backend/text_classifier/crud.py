from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from text_classifier import base_objects
from text_classifier.database import User
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


async def list_tasks(db: AsyncSession, *, enabled_only: bool = False) -> list[Task]:
    query = select(Task).order_by(Task.id)
    if enabled_only:
        query = query.where(Task.enabled.is_(True))
    rows = await db.execute(query)
    return list(rows.scalars().all())


async def list_enabled_tasks(db: AsyncSession) -> list[Task]:
    return await list_tasks(db, enabled_only=True)


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
        .where(TextItem.suspended.is_(False))
        .order_by(func.coalesce(subq.c.coverage, 0).asc(), TextItem.id.asc())
        .limit(1)
    )
    return (await db.execute(q)).scalar_one_or_none()


async def save_annotations(db: AsyncSession, user_id, payload: base_objects.AnnotationSubmit, tasks_map: dict[str, Task]):
    for ann in payload.annotations:
        task = tasks_map[ann.task_id]
        selected = ann.selected_classes
        allowed_classes = {item['id'] for item in task.classes}
        unknown_classes = sorted(set(selected) - allowed_classes)
        if unknown_classes:
            raise ValueError(f"Task {task.id} has unknown classes: {', '.join(unknown_classes)}")
        if task.multi_choice:
            if not selected:
                raise ValueError(f"Task {task.id} requires at least one choice")
            if len(selected) > task.max_choices:
                raise ValueError(f"Task {task.id} allows max {task.max_choices} choices")
        elif len(selected) != 1:
            raise ValueError(f"Task {task.id} requires exactly one choice")
        db.add(Annotation(user_id=user_id, text_id=payload.text_id, task_id=ann.task_id,
                          selected_classes=selected, start_time=ann.start_time, end_time=ann.end_time))


async def my_stats(db: AsyncSession, user_id):
    per_task = await db.execute(select(Annotation.task_id, func.count()).where(Annotation.user_id == user_id).group_by(Annotation.task_id))
    totals = {task_id: count for task_id, count in per_task.all()}
    return {"total": sum(totals.values()), "per_task": totals}


def _display_name(dn: str | None, user_id) -> str:
    return dn if dn else str(user_id)[:8]


async def leaderboard(db: AsyncSession, task_id: str, since: datetime | None = None) -> list[dict]:
    q = (
        select(Annotation.user_id, func.count().label("count"), User.display_name)
        .outerjoin(User, User.id == Annotation.user_id)
        .where(Annotation.task_id == task_id)
    )
    if since:
        q = q.where(Annotation.created_at >= since)
    q = q.group_by(Annotation.user_id, User.display_name).order_by(func.count().desc()).limit(20)
    rows = await db.execute(q)
    return [{"user_id": str(u), "display_name": _display_name(dn, u), "count": c} for u, c, dn in rows.all()]


async def leaderboard_overall(db: AsyncSession, since: datetime | None = None) -> list[dict]:
    q = (
        select(Annotation.user_id, func.count().label("count"), User.display_name)
        .outerjoin(User, User.id == Annotation.user_id)
    )
    if since:
        q = q.where(Annotation.created_at >= since)
    q = q.group_by(Annotation.user_id, User.display_name).order_by(func.count().desc()).limit(20)
    rows = await db.execute(q)
    return [{"user_id": str(u), "display_name": _display_name(dn, u), "count": c} for u, c, dn in rows.all()]


async def global_stats(db: AsyncSession) -> dict:
    task_rows = await db.execute(
        select(Annotation.task_id, Task.name, func.count(Annotation.id).label("count"))
        .join(Task, Task.id == Annotation.task_id)
        .group_by(Annotation.task_id, Task.name)
        .order_by(func.count(Annotation.id).desc())
    )
    total_row = await db.execute(select(func.count()).select_from(Annotation))
    return {
        "total_annotations": total_row.scalar_one(),
        "per_task": [{"task_id": tid, "task_name": name, "count": c} for tid, name, c in task_rows.all()],
    }


async def list_texts(db: AsyncSession, page: int = 0, q: str = '', page_size: int = 50) -> dict:
    query = select(TextItem).order_by(TextItem.id)
    if q:
        query = query.where(TextItem.text.ilike(f'%{q}%'))
    total_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(total_q)).scalar_one()
    rows = (await db.execute(query.offset(page * page_size).limit(page_size))).scalars().all()
    return {
        "total": total,
        "items": [{"id": t.id, "text_preview": t.text[:120], "language": t.language, "suspended": t.suspended} for t in rows],
    }


async def set_text_suspended(db: AsyncSession, text_id: str, suspended: bool) -> bool:
    item = await db.get(TextItem, text_id)
    if item is None:
        return False
    item.suspended = suspended
    return True


async def upsert_text(db: AsyncSession, text_id: str, text: str, language: str, raw_json: dict):
    db_text = await db.get(TextItem, text_id)
    if db_text is None:
        db.add(TextItem(id=text_id, text=text, language=language, raw_json=raw_json))
    else:
        db_text.text = text
        db_text.language = language
        db_text.raw_json = raw_json



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


async def list_tasks(db: AsyncSession, *, enabled_only: bool = False) -> list[Task]:
    query = select(Task).order_by(Task.id)
    if enabled_only:
        query = query.where(Task.enabled.is_(True))
    rows = await db.execute(query)
    return list(rows.scalars().all())


async def list_enabled_tasks(db: AsyncSession) -> list[Task]:
    return await list_tasks(db, enabled_only=True)




