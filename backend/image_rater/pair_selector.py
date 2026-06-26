"""Pair-selection algorithms for 2-forced-choice tasks.

Each algorithm selects a pair of images from the same group that should be
shown to a specific user next.  All algorithms also inject reliability-check
re-shows at the rate specified by ``task.calib_ratio``.
"""
from __future__ import annotations

import math
import random
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from image_rater.db_model import Comparison, ImageItem, ImageRanking, Task


ALGORITHM_DESCRIPTIONS: dict[str, str] = {
    "least_seen": (
        "Shows the pair of images in the group that has been compared the "
        "fewest times. Simple and fair — ensures every pair is seen roughly "
        "equally often."
    ),
    "swiss": (
        "Pairs images with similar win-counts, like a Swiss chess tournament. "
        "Quickly separates the best images from the rest."
    ),
    "bradley_terry": (
        "Uses a Bradley-Terry statistical model to pick the pair whose result "
        "would most reduce uncertainty in the overall ranking. Most "
        "information-efficient but slightly more computationally intensive."
    ),
}


async def get_next_pair(
    db: AsyncSession,
    user_id: str,
    task: Task,
) -> tuple[ImageItem, ImageItem, str, bool] | None:
    """Return ``(image_a, image_b, group_id, is_reliability_check)`` or *None*.

    Selection logic:
    1. With probability ``task.calib_ratio``, attempt a reliability re-show
       (pick a previously seen pair for this user in this task).
    2. Otherwise select a novel pair via the task's configured algorithm.
    3. If neither produces a result, fall back to the other strategy.
    """
    # Try reliability re-show first (probabilistically)
    if random.random() < task.calib_ratio:
        pair = await _pick_reliability_pair(db, user_id, task.id)
        if pair:
            a, b, group_id = pair
            return a, b, group_id, True

    # Novel pair
    pair = await _pick_novel_pair(db, user_id, task)
    if pair:
        a, b, group_id = pair
        return a, b, group_id, False

    # Fall back to any pair (even already seen)
    pair = await _pick_any_pair(db, task.id)
    if pair:
        a, b, group_id = pair
        return a, b, group_id, False

    return None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _active_images_by_group(
    db: AsyncSession, task_id: str
) -> dict[str, list[ImageItem]]:
    result = await db.execute(
        select(ImageItem)
        .where(ImageItem.task_id == task_id, ImageItem.suspended.is_(False))
        .options(selectinload(ImageItem.ranking))
    )
    images = result.scalars().all()
    groups: dict[str, list[ImageItem]] = {}
    for img in images:
        groups.setdefault(img.group_id, []).append(img)
    return groups


async def _seen_pairs(
    db: AsyncSession, user_id: str, task_id: str
) -> set[frozenset[str]]:
    result = await db.execute(
        select(Comparison.image_a_id, Comparison.image_b_id)
        .where(Comparison.user_id == user_id, Comparison.task_id == task_id)
    )
    return {frozenset([a, b]) for a, b in result.all()}


async def _pick_reliability_pair(
    db: AsyncSession, user_id: str, task_id: str
) -> tuple[ImageItem, ImageItem, str] | None:
    """Pick a pair that this user has already seen (for consistency check)."""
    result = await db.execute(
        select(Comparison)
        .where(
            Comparison.user_id == user_id,
            Comparison.task_id == task_id,
            Comparison.is_reliability_check.is_(False),
        )
        .order_by(func.random())
        .limit(1)
    )
    comp = result.scalar_one_or_none()
    if comp is None:
        return None
    a = await db.get(ImageItem, comp.image_a_id)
    b = await db.get(ImageItem, comp.image_b_id)
    if a is None or b is None or a.suspended or b.suspended:
        return None
    return a, b, comp.group_id


async def _pick_any_pair(
    db: AsyncSession, task_id: str
) -> tuple[ImageItem, ImageItem, str] | None:
    groups = await _active_images_by_group(db, task_id)
    valid_groups = [g for g, imgs in groups.items() if len(imgs) >= 2]
    if not valid_groups:
        return None
    group_id = random.choice(valid_groups)
    a, b = random.sample(groups[group_id], 2)
    return a, b, group_id


async def _pick_novel_pair(
    db: AsyncSession, user_id: str, task: Task
) -> tuple[ImageItem, ImageItem, str] | None:
    groups = await _active_images_by_group(db, task.id)
    seen = await _seen_pairs(db, user_id, task.id)

    algorithm = task.pair_algorithm or "least_seen"
    if algorithm == "bradley_terry":
        return await _bradley_terry_pair(db, groups, seen, task.id)
    if algorithm == "swiss":
        return _swiss_pair(groups, seen)
    return _least_seen_pair(groups, seen)


def _least_seen_pair(
    groups: dict[str, list[ImageItem]],
    seen: set[frozenset[str]],
) -> tuple[ImageItem, ImageItem, str] | None:
    """Return the unseen pair that belongs to a group where comparisons are fewest."""
    best: tuple[ImageItem, ImageItem, str] | None = None
    best_seen_count = float("inf")

    for group_id, imgs in groups.items():
        if len(imgs) < 2:
            continue
        for i in range(len(imgs)):
            for j in range(i + 1, len(imgs)):
                pair_key = frozenset([imgs[i].id, imgs[j].id])
                if pair_key in seen:
                    continue
                # Approximate "least seen" as minimum of individual comparison counts
                count_i = (imgs[i].ranking.comparisons if imgs[i].ranking else 0)
                count_j = (imgs[j].ranking.comparisons if imgs[j].ranking else 0)
                total = count_i + count_j
                if total < best_seen_count:
                    best_seen_count = total
                    best = imgs[i], imgs[j], group_id

    return best


def _swiss_pair(
    groups: dict[str, list[ImageItem]],
    seen: set[frozenset[str]],
) -> tuple[ImageItem, ImageItem, str] | None:
    """Pair images with similar win ratios."""
    best: tuple[ImageItem, ImageItem, str] | None = None
    best_score = float("inf")

    for group_id, imgs in groups.items():
        if len(imgs) < 2:
            continue
        # Sort by win ratio
        def win_ratio(img: ImageItem) -> float:
            r = img.ranking
            if r is None or r.comparisons == 0:
                return 0.5
            return r.wins / r.comparisons

        sorted_imgs = sorted(imgs, key=win_ratio, reverse=True)
        for i in range(len(sorted_imgs) - 1):
            pair_key = frozenset([sorted_imgs[i].id, sorted_imgs[i + 1].id])
            if pair_key in seen:
                continue
            diff = abs(win_ratio(sorted_imgs[i]) - win_ratio(sorted_imgs[i + 1]))
            if diff < best_score:
                best_score = diff
                best = sorted_imgs[i], sorted_imgs[i + 1], group_id

    return best


async def _bradley_terry_pair(
    db: AsyncSession,
    groups: dict[str, list[ImageItem]],
    seen: set[frozenset[str]],
    task_id: str,
) -> tuple[ImageItem, ImageItem, str] | None:
    """Pick the pair whose comparison would give the most information (max Fisher info)."""
    result = await db.execute(
        select(ImageRanking).where(ImageRanking.task_id == task_id)
    )
    rankings: dict[str, ImageRanking] = {r.image_id: r for r in result.scalars().all()}

    best: tuple[ImageItem, ImageItem, str] | None = None
    best_info = -1.0

    for group_id, imgs in groups.items():
        if len(imgs) < 2:
            continue
        scores = {img.id: math.exp(rankings[img.id].score / 400.0) if img.id in rankings else 1.0
                  for img in imgs}
        for i in range(len(imgs)):
            for j in range(i + 1, len(imgs)):
                pair_key = frozenset([imgs[i].id, imgs[j].id])
                if pair_key in seen:
                    continue
                si = scores[imgs[i].id]
                sj = scores[imgs[j].id]
                # Fisher information of the BT model for this pair
                p = si / (si + sj)
                info = p * (1 - p)  # variance of Bernoulli
                if info > best_info:
                    best_info = info
                    best = imgs[i], imgs[j], group_id

    return best
