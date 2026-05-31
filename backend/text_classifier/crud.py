from __future__ import annotations

import math
import random
import uuid
from datetime import datetime
from typing import Sequence

from sqlalchemy import func, select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from text_classifier import base_objects
from text_classifier.database import User
from text_classifier.db_model import Annotation, AnnotationType, Task, TextItem, UserReliability

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _display_name(dn: str | None, user_id) -> str:
    return dn if dn else str(user_id)[:8]


def _scarcity_multiplier(avg_coverage: float, target_coverage: int) -> float:
    """Returns a value in [1.0, 2.0]: higher when coverage is below target."""
    return 1.0 + max(0.0, 1.0 - avg_coverage / max(target_coverage, 1))


# ---------------------------------------------------------------------------
# Task CRUD
# ---------------------------------------------------------------------------

_TASK_READONLY = {"current_multiplier"}


async def upsert_task(db: AsyncSession, task: base_objects.TaskDefinition) -> None:
    db_task = await db.get(Task, task.id)
    payload = {k: v for k, v in task.model_dump().items() if k not in _TASK_READONLY}
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


async def list_enabled_tasks(db: AsyncSession) -> list[dict]:
    """Return enabled tasks serialised as dicts, with current_multiplier filled in."""
    tasks = await list_tasks(db, enabled_only=True)
    total_texts = (await db.execute(
        select(func.count()).select_from(TextItem).where(TextItem.suspended.is_(False))
    )).scalar_one()
    result = []
    for t in tasks:
        d = {
            'id': t.id, 'name': t.name, 'description_md': t.description_md,
            'multi_choice': t.multi_choice, 'max_choices': t.max_choices, 'enabled': t.enabled,
            'classes': t.classes,
            'calib_ratio_initial': t.calib_ratio_initial, 'calib_initial_count': t.calib_initial_count,
            'calib_ratio_ongoing': t.calib_ratio_ongoing, 'repeat_probability': t.repeat_probability,
            'target_coverage': t.target_coverage,
            'current_multiplier': None,
        }
        if total_texts > 0:
            total_ann = (await db.execute(
                select(func.count()).select_from(Annotation)
                .where(Annotation.task_id == t.id, Annotation.annotation_type == AnnotationType.user)
            )).scalar_one()
            avg_coverage = total_ann / total_texts
            d['current_multiplier'] = _scarcity_multiplier(avg_coverage, t.target_coverage)
        result.append(d)
    return result


async def get_task_multiplier(db: AsyncSession, task_id: str, target_coverage: int) -> float:
    total_texts = (await db.execute(
        select(func.count()).select_from(TextItem).where(TextItem.suspended.is_(False))
    )).scalar_one()
    if total_texts == 0:
        return 1.0
    total_ann = (await db.execute(
        select(func.count()).select_from(Annotation)
        .where(Annotation.task_id == task_id, Annotation.annotation_type == AnnotationType.user)
    )).scalar_one()
    avg_coverage = total_ann / total_texts
    return _scarcity_multiplier(avg_coverage, target_coverage)


# ---------------------------------------------------------------------------
# Text CRUD
# ---------------------------------------------------------------------------

async def upsert_text(db: AsyncSession, text_id: str, text: str, language: str, raw_json: dict):
    db_text = await db.get(TextItem, text_id)
    if db_text is None:
        db.add(TextItem(id=text_id, text=text, language=language, raw_json=raw_json))
    else:
        db_text.text = text
        db_text.language = language
        db_text.raw_json = raw_json


async def list_texts(db: AsyncSession, page: int = 0, q: str = '', page_size: int = 50, task_id: str | None = None) -> dict:
    ann_q = (
        select(Annotation.text_id, func.count().label('ann_count'))
        .where(Annotation.annotation_type == AnnotationType.user)
    )
    if task_id:
        ann_q = ann_q.where(Annotation.task_id == task_id)
    ann_subq = ann_q.group_by(Annotation.text_id).subquery()

    query = (
        select(TextItem, func.coalesce(ann_subq.c.ann_count, 0).label('annotation_count'))
        .outerjoin(ann_subq, TextItem.id == ann_subq.c.text_id)
        .order_by(TextItem.id)
    )
    if q:
        query = query.where(TextItem.text.ilike(f'%{q}%'))
    total_q = select(func.count()).select_from(
        select(TextItem).where(TextItem.text.ilike(f'%{q}%')).subquery() if q
        else TextItem
    )
    total = (await db.execute(total_q)).scalar_one()
    rows = (await db.execute(query.offset(page * page_size).limit(page_size))).all()
    return {
        "total": total,
        "items": [
            {"id": t.id, "text_preview": t.text[:120], "language": t.language, "suspended": t.suspended, "annotation_count": ann_count}
            for t, ann_count in rows
        ],
    }


async def set_text_suspended(db: AsyncSession, text_id: str, suspended: bool) -> bool:
    item = await db.get(TextItem, text_id)
    if item is None:
        return False
    item.suspended = suspended
    return True


# ---------------------------------------------------------------------------
# Sampling
# ---------------------------------------------------------------------------

async def _user_annotation_count(db: AsyncSession, user_id, task_id: str) -> int:
    return (await db.execute(
        select(func.count()).select_from(Annotation)
        .where(Annotation.user_id == user_id, Annotation.task_id == task_id)
    )).scalar_one()


async def _pick_calibration_text(
    db: AsyncSession, user_id, calib_task_ids: list[str]
) -> tuple[TextItem | None, list[str]]:
    gt_texts_q = (
        select(Annotation.text_id, func.count(Annotation.task_id).label("gt_count"))
        .where(
            Annotation.annotation_type == AnnotationType.ground_truth,
            Annotation.task_id.in_(calib_task_ids),
        )
        .group_by(Annotation.text_id)
        .subquery()
    )
    user_seen = select(Annotation.text_id).where(
        Annotation.user_id == user_id,
        Annotation.task_id.in_(calib_task_ids),
    ).subquery()
    q = (
        select(TextItem, gt_texts_q.c.gt_count)
        .join(gt_texts_q, TextItem.id == gt_texts_q.c.text_id)
        .where(TextItem.id.not_in(select(user_seen.c.text_id)))
        .where(TextItem.suspended.is_(False))
        .order_by(gt_texts_q.c.gt_count.desc(), TextItem.id.asc())
        .limit(1)
    )
    row = (await db.execute(q)).first()
    if row is None:
        return None, []
    text_item = row[0]
    covered = (await db.execute(
        select(Annotation.task_id)
        .where(
            Annotation.text_id == text_item.id,
            Annotation.annotation_type == AnnotationType.ground_truth,
            Annotation.task_id.in_(calib_task_ids),
        )
    )).scalars().all()
    return text_item, list(covered)


async def _pick_repeat_text(db: AsyncSession, user_id, task_ids: list[str]) -> TextItem | None:
    other_ann = (
        select(Annotation.text_id, func.count(Annotation.id).label("cnt"))
        .where(Annotation.task_id.in_(task_ids), Annotation.user_id != user_id,
               Annotation.annotation_type == AnnotationType.user)
        .group_by(Annotation.text_id)
        .subquery()
    )
    user_seen = select(Annotation.text_id).where(
        Annotation.user_id == user_id, Annotation.task_id.in_(task_ids)
    ).subquery()
    q = (
        select(TextItem)
        .join(other_ann, TextItem.id == other_ann.c.text_id)
        .where(TextItem.id.not_in(select(user_seen.c.text_id)))
        .where(TextItem.suspended.is_(False))
        .order_by(other_ann.c.cnt.asc(), TextItem.id.asc())
        .limit(10)
    )
    rows = (await db.execute(q)).scalars().all()
    if not rows:
        return None
    return random.choice(rows)


async def _pick_new_text(db: AsyncSession, user_id, task_ids: list[str]) -> TextItem | None:
    subq = (
        select(Annotation.text_id, func.count(Annotation.id).label("coverage"))
        .where(Annotation.task_id.in_(task_ids))
        .group_by(Annotation.text_id)
        .subquery()
    )
    user_done = select(Annotation.text_id).where(
        Annotation.user_id == user_id, Annotation.task_id.in_(task_ids)
    ).subquery()
    q = (
        select(TextItem)
        .outerjoin(subq, TextItem.id == subq.c.text_id)
        .where(TextItem.id.not_in(select(user_done.c.text_id)))
        .where(TextItem.suspended.is_(False))
        .order_by(func.coalesce(subq.c.coverage, 0).asc(), TextItem.id.asc())
        .limit(1)
    )
    return (await db.execute(q)).scalar_one_or_none()


async def get_next_text(
    db: AsyncSession, user_id, task_ids: list[str]
) -> tuple[TextItem | None, list[str]]:
    """Returns (text_item, calibration_task_ids)."""
    tasks: Sequence[Task] = (await db.execute(
        select(Task).where(Task.id.in_(task_ids))
    )).scalars().all()
    task_map = {t.id: t for t in tasks}

    calib_task_ids: list[str] = []
    for tid in task_ids:
        task = task_map.get(tid)
        if task is None:
            continue
        user_count = await _user_annotation_count(db, user_id, tid)
        ratio = (
            task.calib_ratio_initial
            if user_count < task.calib_initial_count
            else task.calib_ratio_ongoing
        )
        if random.random() < ratio:
            calib_task_ids.append(tid)

    if calib_task_ids:
        text, covered = await _pick_calibration_text(db, user_id, calib_task_ids)
        if text is not None:
            return text, covered

    max_repeat_prob = max(
        (task_map[tid].repeat_probability for tid in task_ids if tid in task_map),
        default=0.2,
    )
    if random.random() < max_repeat_prob:
        text = await _pick_repeat_text(db, user_id, task_ids)
        if text is not None:
            return text, []

    text = await _pick_new_text(db, user_id, task_ids)
    return text, []


# ---------------------------------------------------------------------------
# Points calculation
# ---------------------------------------------------------------------------

async def _compute_points(
    db: AsyncSession, user_id, text_id: str, task: Task, selected_classes: list[str]
) -> float:
    total_texts = (await db.execute(
        select(func.count()).select_from(TextItem).where(TextItem.suspended.is_(False))
    )).scalar_one()
    total_ann = (await db.execute(
        select(func.count()).select_from(Annotation)
        .where(Annotation.task_id == task.id, Annotation.annotation_type == AnnotationType.user)
    )).scalar_one()
    avg_coverage = total_ann / max(total_texts, 1)
    mult = _scarcity_multiplier(avg_coverage, task.target_coverage)
    K = 30.0 * mult

    rel_row = (await db.execute(
        select(UserReliability)
        .where(UserReliability.user_id == user_id, UserReliability.task_id == task.id)
    )).scalar_one_or_none()
    E = rel_row.pairwise_agreement if (rel_row and rel_row.pairwise_agreement is not None) else 0.5

    gt = (await db.execute(
        select(Annotation.selected_classes)
        .where(
            Annotation.text_id == text_id,
            Annotation.task_id == task.id,
            Annotation.annotation_type == AnnotationType.ground_truth,
        )
    )).scalar_one_or_none()

    if gt is not None:
        A = 1.0 if set(selected_classes) == set(gt) else 0.0
    else:
        existing = (await db.execute(
            select(Annotation.selected_classes, Annotation.weight)
            .where(
                Annotation.text_id == text_id,
                Annotation.task_id == task.id,
                Annotation.user_id != user_id,
                Annotation.annotation_type == AnnotationType.user,
            )
        )).all()
        if existing:
            class_weights: dict[str, float] = {}
            total_weight = sum(w for _, w in existing)
            for sc, w in existing:
                for cls in sc:
                    class_weights[cls] = class_weights.get(cls, 0.0) + w
            if total_weight > 0:
                best = max(class_weights, key=class_weights.__getitem__)
                A = (class_weights.get(best, 0.0) / total_weight) if best in selected_classes else 0.0
            else:
                A = 0.0
        else:
            A = 0.0

    base = 1.0
    delta = K * (A - E)
    return base + max(0.0, delta)


# ---------------------------------------------------------------------------
# Annotation CRUD
# ---------------------------------------------------------------------------

async def save_annotations(
    db: AsyncSession,
    user_id,
    payload: base_objects.AnnotationSubmit,
    tasks_map: dict[str, Task],
    annotation_type: AnnotationType = AnnotationType.user,
) -> dict[str, float]:
    points: dict[str, float] = {}
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

        pts = None
        if annotation_type == AnnotationType.user:
            pts = await _compute_points(db, user_id, payload.text_id, task, selected)
            points[ann.task_id] = pts

        db.add(Annotation(
            user_id=user_id,
            text_id=payload.text_id,
            task_id=ann.task_id,
            selected_classes=selected,
            start_time=ann.start_time,
            end_time=ann.end_time,
            annotation_type=annotation_type,
            points_earned=pts,
        ))
    return points


async def bulk_upsert_annotations(
    db: AsyncSession,
    items: list[base_objects.BulkAnnotationItem],
    annotation_type: AnnotationType,
    submitter_user_id: uuid.UUID,
) -> int:
    count = 0
    now = datetime.utcnow()
    for item in items:
        existing = (await db.execute(
            select(Annotation).where(
                Annotation.user_id == submitter_user_id,
                Annotation.text_id == item.text_id,
                Annotation.task_id == item.task_id,
                Annotation.annotation_type == annotation_type,
            )
        )).scalar_one_or_none()
        if existing:
            existing.selected_classes = item.selected_classes
        else:
            db.add(Annotation(
                user_id=submitter_user_id,
                text_id=item.text_id,
                task_id=item.task_id,
                selected_classes=item.selected_classes,
                start_time=now,
                end_time=now,
                annotation_type=annotation_type,
            ))
        count += 1
    return count


async def set_annotation_type(
    db: AsyncSession, annotation_id: uuid.UUID, annotation_type: AnnotationType
) -> bool:
    ann = await db.get(Annotation, annotation_id)
    if ann is None:
        return False
    ann.annotation_type = annotation_type
    return True


async def get_gt_for_text_tasks(
    db: AsyncSession, text_id: str, task_ids: list[str]
) -> dict[str, list[str]]:
    rows = (await db.execute(
        select(Annotation.task_id, Annotation.selected_classes)
        .where(
            Annotation.text_id == text_id,
            Annotation.task_id.in_(task_ids),
            Annotation.annotation_type == AnnotationType.ground_truth,
        )
    )).all()
    return {tid: sc for tid, sc in rows}


# ---------------------------------------------------------------------------
# Stats & leaderboard
# ---------------------------------------------------------------------------

async def my_stats(db: AsyncSession, user_id) -> dict:
    per_task_q = await db.execute(
        select(
            Annotation.task_id,
            func.count(),
            func.coalesce(func.sum(Annotation.points_earned), 0),
        )
        .where(Annotation.user_id == user_id, Annotation.annotation_type == AnnotationType.user)
        .group_by(Annotation.task_id)
    )
    rows = per_task_q.all()
    totals = {task_id: count for task_id, count, _ in rows}
    scores = {task_id: float(score) for task_id, _, score in rows}
    return {
        "total": sum(totals.values()),
        "per_task": totals,
        "score": sum(scores.values()),
        "per_task_score": scores,
    }


async def leaderboard(db: AsyncSession, task_id: str, since: datetime | None = None) -> list[dict]:
    rel_subq = (
        select(UserReliability.user_id, UserReliability.pairwise_agreement)
        .where(UserReliability.task_id == task_id)
        .subquery()
    )
    q = (
        select(
            Annotation.user_id,
            func.count().label("count"),
            func.coalesce(func.sum(Annotation.points_earned), 0).label("score"),
            User.display_name,
            rel_subq.c.pairwise_agreement,
        )
        .outerjoin(User, User.id == Annotation.user_id)
        .outerjoin(rel_subq, rel_subq.c.user_id == Annotation.user_id)
        .where(Annotation.task_id == task_id, Annotation.annotation_type == AnnotationType.user)
    )
    if since:
        q = q.where(Annotation.created_at >= since)
    q = (q.group_by(Annotation.user_id, User.display_name, rel_subq.c.pairwise_agreement)
         .order_by(func.sum(Annotation.points_earned).desc().nulls_last(), func.count().desc())
         .limit(20))
    rows = await db.execute(q)
    return [
        {"user_id": str(u), "display_name": _display_name(dn, u), "count": c, "score": float(s),
         "reliability": float(pa) if pa is not None else None}
        for u, c, s, dn, pa in rows.all()
    ]


async def leaderboard_overall(db: AsyncSession, since: datetime | None = None) -> list[dict]:
    avg_rel_subq = (
        select(UserReliability.user_id, func.avg(UserReliability.pairwise_agreement).label("avg_reliability"))
        .group_by(UserReliability.user_id)
        .subquery()
    )
    q = (
        select(
            Annotation.user_id,
            func.count().label("count"),
            func.coalesce(func.sum(Annotation.points_earned), 0).label("score"),
            User.display_name,
            avg_rel_subq.c.avg_reliability,
        )
        .outerjoin(User, User.id == Annotation.user_id)
        .outerjoin(avg_rel_subq, avg_rel_subq.c.user_id == Annotation.user_id)
        .where(Annotation.annotation_type == AnnotationType.user)
    )
    if since:
        q = q.where(Annotation.created_at >= since)
    q = (q.group_by(Annotation.user_id, User.display_name, avg_rel_subq.c.avg_reliability)
         .order_by(func.sum(Annotation.points_earned).desc().nulls_last(), func.count().desc())
         .limit(20))
    rows = await db.execute(q)
    return [
        {"user_id": str(u), "display_name": _display_name(dn, u), "count": c, "score": float(s),
         "reliability": float(ar) if ar is not None else None}
        for u, c, s, dn, ar in rows.all()
    ]


async def global_stats(db: AsyncSession) -> dict:
    task_rows = await db.execute(
        select(Annotation.task_id, Task.name, func.count(Annotation.id).label("count"))
        .join(Task, Task.id == Annotation.task_id)
        .where(Annotation.annotation_type == AnnotationType.user)
        .group_by(Annotation.task_id, Task.name)
        .order_by(func.count(Annotation.id).desc())
    )
    total_row = await db.execute(
        select(func.count()).select_from(Annotation)
        .where(Annotation.annotation_type == AnnotationType.user)
    )
    return {
        "total_annotations": total_row.scalar_one(),
        "per_task": [{"task_id": tid, "task_name": name, "count": c} for tid, name, c in task_rows.all()],
    }


async def get_text_annotations(
    db: AsyncSession, text_id: str, task_id: str | None = None
) -> list[dict]:
    q = (
        select(Annotation, User.display_name)
        .outerjoin(User, User.id == Annotation.user_id)
        .where(Annotation.text_id == text_id)
    )
    if task_id:
        q = q.where(Annotation.task_id == task_id)
    q = q.order_by(Annotation.task_id, Annotation.annotation_type, Annotation.created_at)
    rows = (await db.execute(q)).all()
    return [
        {
            "annotation_id": str(ann.id),
            "user_id": str(ann.user_id),
            "display_name": _display_name(dn, ann.user_id),
            "task_id": ann.task_id,
            "selected_classes": ann.selected_classes,
            "annotation_type": ann.annotation_type.value,
            "created_at": ann.created_at.isoformat() if ann.created_at else None,
            "points_earned": float(ann.points_earned) if ann.points_earned is not None else None,
        }
        for ann, dn in rows
    ]


# ---------------------------------------------------------------------------
# User reliability queries
# ---------------------------------------------------------------------------

async def get_reliability(
    db: AsyncSession, user_id=None, task_id: str | None = None
) -> list[dict]:
    q = select(UserReliability, User.display_name).outerjoin(User, User.id == UserReliability.user_id)
    if user_id is not None:
        q = q.where(UserReliability.user_id == user_id)
    if task_id is not None:
        q = q.where(UserReliability.task_id == task_id)
    rows = (await db.execute(q)).all()
    return [
        {
            "user_id": str(r.user_id),
            "display_name": _display_name(dn, r.user_id),
            "task_id": r.task_id,
            "annotation_count": r.annotation_count,
            "pairwise_agreement": r.pairwise_agreement,
            "cohens_kappa": r.cohens_kappa,
            "krippendorffs_alpha": r.krippendorffs_alpha,
            "ds_sensitivity": r.ds_sensitivity,
            "computed_at": r.computed_at,
        }
        for r, dn in rows
    ]




