"""Compute user reliability scores.

Two metrics:
* ``consistency_score`` – fraction of re-shown items answered the same way.
* ``inter_rater_agreement`` – fraction of comparisons/ratings matching the
  majority vote of other users on the same pair/image.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from image_rater.db_model import Comparison, Rating, Task, UserReliability


# ---------------------------------------------------------------------------
# Per-user per-task helpers
# ---------------------------------------------------------------------------

async def _compute_comparison_reliability(
    db: AsyncSession, user_id: str, task_id: str
) -> tuple[float | None, float | None, int]:
    """Return (consistency, inter_rater, count) for comparisons."""
    result = await db.execute(
        select(Comparison).where(
            Comparison.user_id == user_id,
            Comparison.task_id == task_id,
            Comparison.winner_id.isnot(None),
        )
    )
    comps = result.scalars().all()
    if not comps:
        return None, None, 0

    count = len(comps)

    # Consistency: re-shown pairs
    normal = {frozenset([c.image_a_id, c.image_b_id]): c.winner_id
              for c in comps if not c.is_reliability_check}
    re_shown = [c for c in comps if c.is_reliability_check]
    if re_shown:
        consistent = sum(
            1 for c in re_shown
            if normal.get(frozenset([c.image_a_id, c.image_b_id])) == c.winner_id
        )
        consistency = consistent / len(re_shown)
    else:
        consistency = None

    # Inter-rater: majority vote on same pair
    # Gather all decisions on each pair from all users
    all_result = await db.execute(
        select(Comparison).where(
            Comparison.task_id == task_id,
            Comparison.winner_id.isnot(None),
            Comparison.is_reliability_check.is_(False),
        )
    )
    all_comps = all_result.scalars().all()
    pair_votes: dict[frozenset, Counter] = {}
    for c in all_comps:
        key = frozenset([c.image_a_id, c.image_b_id])
        pair_votes.setdefault(key, Counter())[c.winner_id] += 1

    user_comps_normal = [c for c in comps if not c.is_reliability_check]
    if user_comps_normal:
        agreed = 0
        total_with_majority = 0
        for c in user_comps_normal:
            key = frozenset([c.image_a_id, c.image_b_id])
            votes = pair_votes.get(key, Counter())
            if len(votes) < 2:  # only one vote (the user's own), skip
                continue
            majority = votes.most_common(1)[0][0]
            total_with_majority += 1
            if c.winner_id == majority:
                agreed += 1
        inter_rater = agreed / total_with_majority if total_with_majority > 0 else None
    else:
        inter_rater = None

    return consistency, inter_rater, count


async def _compute_rating_reliability(
    db: AsyncSession, user_id: str, task_id: str
) -> tuple[float | None, float | None, int]:
    """Return (consistency, inter_rater, count) for single-image ratings."""
    result = await db.execute(
        select(Rating).where(
            Rating.user_id == user_id,
            Rating.task_id == task_id,
            Rating.selected_option.isnot(None),
        )
    )
    ratings = result.scalars().all()
    if not ratings:
        return None, None, 0

    count = len(ratings)

    normal = {r.image_id: r.selected_option for r in ratings if not r.is_reliability_check}
    re_shown = [r for r in ratings if r.is_reliability_check]
    if re_shown:
        consistent = sum(
            1 for r in re_shown if normal.get(r.image_id) == r.selected_option
        )
        consistency = consistent / len(re_shown)
    else:
        consistency = None

    # Inter-rater
    all_result = await db.execute(
        select(Rating).where(
            Rating.task_id == task_id,
            Rating.selected_option.isnot(None),
            Rating.is_reliability_check.is_(False),
        )
    )
    all_ratings = all_result.scalars().all()
    image_votes: dict[str, Counter] = {}
    for r in all_ratings:
        image_votes.setdefault(r.image_id, Counter())[r.selected_option] += 1

    user_normal = [r for r in ratings if not r.is_reliability_check]
    if user_normal:
        agreed = 0
        total_with_majority = 0
        for r in user_normal:
            votes = image_votes.get(r.image_id, Counter())
            if len(votes) < 2:
                continue
            majority = votes.most_common(1)[0][0]
            total_with_majority += 1
            if r.selected_option == majority:
                agreed += 1
        inter_rater = agreed / total_with_majority if total_with_majority > 0 else None
    else:
        inter_rater = None

    return consistency, inter_rater, count


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def run_reliability_job(db: AsyncSession) -> None:
    """Recompute reliability for all (user, task) pairs and upsert results."""
    # Gather distinct (user_id, task_id) pairs from both tables
    comp_result = await db.execute(
        select(Comparison.user_id, Comparison.task_id).distinct()
    )
    rating_result = await db.execute(
        select(Rating.user_id, Rating.task_id).distinct()
    )
    pairs: set[tuple[str, str]] = set()
    for row in comp_result.all():
        pairs.add((str(row.user_id), row.task_id))
    for row in rating_result.all():
        pairs.add((str(row.user_id), row.task_id))

    task_types: dict[str, str] = {}
    tasks_result = await db.execute(select(Task.id, Task.task_type))
    for row in tasks_result.all():
        task_types[row.id] = row.task_type

    now = datetime.now(timezone.utc)

    for user_id, task_id in pairs:
        task_type = task_types.get(task_id, "two_forced_choice")
        if task_type == "two_forced_choice":
            consistency, inter_rater, count = await _compute_comparison_reliability(
                db, user_id, task_id
            )
        else:
            consistency, inter_rater, count = await _compute_rating_reliability(
                db, user_id, task_id
            )

        existing = await db.execute(
            select(UserReliability).where(
                UserReliability.user_id == user_id,
                UserReliability.task_id == task_id,
            )
        )
        rec = existing.scalar_one_or_none()
        if rec is None:
            rec = UserReliability(user_id=user_id, task_id=task_id)
            db.add(rec)
        rec.consistency_score = consistency
        rec.inter_rater_agreement = inter_rater
        rec.annotation_count = count
        rec.computed_at = now

    await db.flush()
