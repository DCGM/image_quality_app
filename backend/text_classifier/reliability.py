"""
Reliability computation module.

Computes pairwise agreement, Cohen's kappa, and Krippendorff's alpha per user
per task, then stores results in the UserReliability table.
"""
from __future__ import annotations

import itertools
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

try:
    import krippendorff
    _HAS_KRIPPENDORFF = True
except ImportError:
    _HAS_KRIPPENDORFF = False

try:
    from sklearn.metrics import cohen_kappa_score
    _HAS_SKLEARN = True
except ImportError:
    _HAS_SKLEARN = False

from text_classifier.db_model import Annotation, AnnotationType, Task, UserReliability


# ---------------------------------------------------------------------------
# Per-annotation collection
# ---------------------------------------------------------------------------

def _annotation_key(selected_classes: list[str]) -> str:
    """Canonical string for a set of selected classes."""
    return "|".join(sorted(selected_classes))


async def _collect_annotations(
    db: AsyncSession, task_id: str
) -> dict[str, dict[Any, str]]:
    """
    Returns {text_id: {user_id: annotation_key}} for user annotations only.
    Only includes texts annotated by ≥2 users.
    """
    rows = (await db.execute(
        select(Annotation.text_id, Annotation.user_id, Annotation.selected_classes)
        .where(
            Annotation.task_id == task_id,
            Annotation.annotation_type == AnnotationType.user,
        )
    )).all()

    by_text: dict[str, dict[Any, str]] = defaultdict(dict)
    for text_id, user_id, selected_classes in rows:
        by_text[text_id][user_id] = _annotation_key(selected_classes)

    return {tid: anns for tid, anns in by_text.items() if len(anns) >= 2}


# ---------------------------------------------------------------------------
# Agreement computation
# ---------------------------------------------------------------------------

def _pairwise_agreement(user_annotations: dict[str, dict[Any, str]], user_id) -> float | None:
    """Fraction of shared texts where this user agrees with at least one other."""
    agree = 0
    total = 0
    for text_id, anns in user_annotations.items():
        if user_id not in anns:
            continue
        others = [v for uid, v in anns.items() if uid != user_id]
        if not others:
            continue
        total += 1
        if anns[user_id] in others:
            agree += 1
    if total == 0:
        return None
    return agree / total


def _cohens_kappa(
    user_annotations: dict[str, dict[Any, str]], user_id
) -> float | None:
    """Average pairwise Cohen's kappa between this user and all others."""
    if not _HAS_SKLEARN:
        return None
    kappas: list[float] = []
    other_users: set[Any] = set()
    for anns in user_annotations.values():
        other_users.update(uid for uid in anns if uid != user_id)

    for other_id in other_users:
        shared = [
            (anns[user_id], anns[other_id])
            for anns in user_annotations.values()
            if user_id in anns and other_id in anns
        ]
        if len(shared) < 2:
            continue
        y1, y2 = zip(*shared)
        try:
            k = cohen_kappa_score(y1, y2)
            kappas.append(k)
        except Exception:
            continue
    if not kappas:
        return None
    return float(np.mean(kappas))


def _krippendorffs_alpha(
    user_annotations: dict[str, dict[Any, str]], user_id
) -> float | None:
    """Krippendorff's alpha including this user vs all texts they annotated."""
    if not _HAS_KRIPPENDORFF:
        return None
    other_users: set[Any] = set()
    for anns in user_annotations.values():
        other_users.update(uid for uid in anns if uid != user_id)

    all_users = [user_id] + sorted(other_users)
    texts = [
        tid for tid, anns in user_annotations.items()
        if user_id in anns
    ]
    if not texts or len(all_users) < 2:
        return None

    # Build reliability data matrix: rows = raters, cols = units
    # Missing values represented as np.nan
    matrix = np.full((len(all_users), len(texts)), np.nan)
    # Build a category → int mapping
    categories: dict[str, int] = {}
    idx = 0
    for tid in texts:
        anns = user_annotations[tid]
        for uid, key in anns.items():
            if key not in categories:
                categories[key] = idx
                idx += 1

    for r_idx, uid in enumerate(all_users):
        for c_idx, tid in enumerate(texts):
            key = user_annotations[tid].get(uid)
            if key is not None:
                matrix[r_idx, c_idx] = categories[key]

    try:
        alpha = krippendorff.alpha(reliability_data=matrix, level_of_measurement="nominal")
        return float(alpha)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Main job
# ---------------------------------------------------------------------------

async def run_reliability_job(db: AsyncSession) -> None:
    """Compute reliability metrics for all users on all tasks and upsert results."""
    tasks = (await db.execute(select(Task))).scalars().all()
    now = datetime.now(timezone.utc)

    for task in tasks:
        user_annotations = await _collect_annotations(db, task.id)
        if not user_annotations:
            continue

        # Collect all user IDs who annotated this task
        user_ids: set[Any] = set()
        for anns in user_annotations.values():
            user_ids.update(anns.keys())

        for user_id in user_ids:
            count = sum(1 for anns in user_annotations.values() if user_id in anns)
            if count < 5:
                # Not enough data for meaningful stats
                continue

            pa = _pairwise_agreement(user_annotations, user_id)
            ck = _cohens_kappa(user_annotations, user_id)
            ka = _krippendorffs_alpha(user_annotations, user_id)

            existing = (await db.execute(
                select(UserReliability)
                .where(UserReliability.user_id == user_id, UserReliability.task_id == task.id)
            )).scalar_one_or_none()

            if existing:
                existing.pairwise_agreement = pa
                existing.cohens_kappa = ck
                existing.krippendorffs_alpha = ka
                existing.annotation_count = count
                existing.computed_at = now
            else:
                db.add(UserReliability(
                    user_id=user_id,
                    task_id=task.id,
                    pairwise_agreement=pa,
                    cohens_kappa=ck,
                    krippendorffs_alpha=ka,
                    annotation_count=count,
                    computed_at=now,
                ))
