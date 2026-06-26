"""Image selection for single-rating tasks.

Selects which image to show a user next, balancing coverage and reliability
re-checks.
"""
from __future__ import annotations

import random

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from image_rater.db_model import ImageItem, Rating, Task


async def get_next_image(
    db: AsyncSession,
    user_id: str,
    task: Task,
) -> tuple[ImageItem, bool] | None:
    """Return ``(image, is_reliability_check)`` or *None* if nothing to show."""
    # Reliability re-show
    if random.random() < task.calib_ratio:
        img = await _pick_reliability_image(db, user_id, task.id)
        if img:
            return img, True

    # Novel image (least rated by this user)
    img = await _pick_novel_image(db, user_id, task.id)
    if img:
        return img, False

    # Fall back to any unsuspended image
    img = await _pick_any_image(db, task.id)
    if img:
        return img, False

    return None


async def _pick_reliability_image(
    db: AsyncSession, user_id: str, task_id: str
) -> ImageItem | None:
    result = await db.execute(
        select(Rating.image_id)
        .where(
            Rating.user_id == user_id,
            Rating.task_id == task_id,
            Rating.is_reliability_check.is_(False),
        )
        .order_by(func.random())
        .limit(1)
    )
    image_id = result.scalar_one_or_none()
    if image_id is None:
        return None
    img = await db.get(ImageItem, image_id)
    if img is None or img.suspended:
        return None
    return img


async def _pick_novel_image(
    db: AsyncSession, user_id: str, task_id: str
) -> ImageItem | None:
    # Images rated by this user
    seen_sub = select(Rating.image_id).where(
        Rating.user_id == user_id, Rating.task_id == task_id
    )
    result = await db.execute(
        select(ImageItem)
        .where(
            ImageItem.task_id == task_id,
            ImageItem.suspended.is_(False),
            ImageItem.id.not_in(seen_sub),
        )
        .order_by(func.random())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _pick_any_image(db: AsyncSession, task_id: str) -> ImageItem | None:
    result = await db.execute(
        select(ImageItem)
        .where(ImageItem.task_id == task_id, ImageItem.suspended.is_(False))
        .order_by(func.random())
        .limit(1)
    )
    return result.scalar_one_or_none()
