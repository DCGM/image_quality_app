"""Database access layer (CRUD)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from image_rater.base_objects import (
    ComparisonSubmit, GlobalStats, ImageItemResponse, ImageListResponse,
    ImageRankingResponse, LeaderboardEntry, MyStats, RatingSubmit, TaskCreate,
    TaskRead, TaskStats, TaskUpdate, UserReliabilityResponse,
    ComparisonRecord, RatingRecord, PaginatedComparisons, PaginatedRatings,
)
from image_rater.database import DBError, User
from image_rater.db_model import (
    Comparison, ImageItem, ImageRanking, Rating, Task, UserReliability,
)
from image_rater.scoring import compute_points, update_elo


def _image_url(task_id: str, filename: str) -> str:
    return f"/images/{task_id}/{filename}"


def _image_response(img: ImageItem) -> ImageItemResponse:
    return ImageItemResponse(
        id=img.id,
        task_id=img.task_id,
        filename=img.filename,
        group_id=img.group_id,
        url=_image_url(img.task_id, img.filename),
        suspended=img.suspended,
        width=img.width,
        height=img.height,
    )


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

async def list_enabled_tasks(db: AsyncSession) -> list[Task]:
    result = await db.execute(select(Task).where(Task.enabled.is_(True)))
    return list(result.scalars().all())


async def list_all_tasks(db: AsyncSession) -> list[Task]:
    result = await db.execute(select(Task))
    return list(result.scalars().all())


async def get_task(db: AsyncSession, task_id: str) -> Task | None:
    return await db.get(Task, task_id)


async def upsert_task(db: AsyncSession, data: TaskCreate) -> Task:
    existing = await db.get(Task, data.id)
    if existing is None:
        task = Task(**data.model_dump())
        db.add(task)
        return task
    for k, v in data.model_dump().items():
        setattr(existing, k, v)
    return existing


async def update_task(db: AsyncSession, task_id: str, data: TaskUpdate) -> Task:
    task = await db.get(Task, task_id)
    if task is None:
        raise DBError(f"Task {task_id!r} not found")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(task, k, v)
    return task


async def patch_task_state(
    db: AsyncSession,
    task_id: str,
    enabled: bool | None,
    deleted: bool | None,
    bonus_multiplier: float | None,
) -> None:
    task = await db.get(Task, task_id)
    if task is None:
        raise DBError(f"Task {task_id!r} not found")
    if enabled is not None:
        task.enabled = enabled
    if bonus_multiplier is not None:
        task.bonus_multiplier = bonus_multiplier
    if deleted:
        await db.delete(task)


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------

async def list_images(
    db: AsyncSession,
    task_id: str,
    page: int = 1,
    page_size: int = 50,
    q: str | None = None,
) -> ImageListResponse:
    stmt = select(ImageItem).where(ImageItem.task_id == task_id)
    if q:
        stmt = stmt.where(ImageItem.filename.ilike(f"%{q}%"))
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    items = [_image_response(img) for img in result.scalars().all()]
    return ImageListResponse(total=total, items=items)


async def patch_image(db: AsyncSession, image_id: str, suspended: bool) -> None:
    img = await db.get(ImageItem, image_id)
    if img is None:
        raise DBError(f"Image {image_id!r} not found")
    img.suspended = suspended


async def get_rankings(db: AsyncSession, task_id: str) -> list[ImageRankingResponse]:
    result = await db.execute(
        select(ImageItem, ImageRanking)
        .join(ImageRanking, ImageRanking.image_id == ImageItem.id, isouter=True)
        .where(ImageItem.task_id == task_id, ImageItem.suspended.is_(False))
        .order_by(ImageRanking.score.desc())
    )
    rows = result.all()
    out = []
    for img, ranking in rows:
        out.append(ImageRankingResponse(
            image_id=img.id,
            filename=img.filename,
            url=_image_url(img.task_id, img.filename),
            score=ranking.score if ranking else 1000.0,
            comparisons=ranking.comparisons if ranking else 0,
            wins=ranking.wins if ranking else 0,
        ))
    return out


# ---------------------------------------------------------------------------
# Submissions
# ---------------------------------------------------------------------------

async def _get_user_reliability(
    db: AsyncSession, user_id: str, task_id: str
) -> UserReliability | None:
    result = await db.execute(
        select(UserReliability).where(
            UserReliability.user_id == user_id,
            UserReliability.task_id == task_id,
        )
    )
    return result.scalar_one_or_none()


async def save_comparison(
    db: AsyncSession,
    user_id: str,
    payload: ComparisonSubmit,
    task: Task,
    is_reliability_check: bool = False,
) -> float:
    if payload.winner_id not in (payload.image_a_id, payload.image_b_id):
        raise ValueError("winner_id must be one of image_a_id or image_b_id")

    rel = await _get_user_reliability(db, user_id, payload.task_id)
    points = compute_points(
        task,
        rel.consistency_score if rel else None,
        rel.inter_rater_agreement if rel else None,
    )

    img_a = await db.get(ImageItem, payload.image_a_id)
    img_b = await db.get(ImageItem, payload.image_b_id)
    if img_a is None or img_b is None:
        raise DBError("Image not found")

    comp = Comparison(
        user_id=user_id,
        task_id=payload.task_id,
        group_id=img_a.group_id,
        image_a_id=payload.image_a_id,
        image_b_id=payload.image_b_id,
        winner_id=payload.winner_id,
        start_time=payload.start_time,
        end_time=payload.end_time,
        created_at=datetime.now(timezone.utc),
        is_reliability_check=is_reliability_check,
        points_earned=points,
    )
    db.add(comp)

    # Update Elo rankings
    loser_id = payload.image_b_id if payload.winner_id == payload.image_a_id else payload.image_a_id
    r_winner = await db.execute(
        select(ImageRanking).where(
            ImageRanking.image_id == payload.winner_id,
            ImageRanking.task_id == payload.task_id,
        )
    )
    r_loser = await db.execute(
        select(ImageRanking).where(
            ImageRanking.image_id == loser_id,
            ImageRanking.task_id == payload.task_id,
        )
    )
    winner_ranking = r_winner.scalar_one_or_none()
    loser_ranking = r_loser.scalar_one_or_none()
    if winner_ranking and loser_ranking:
        update_elo(winner_ranking, loser_ranking)

    return points


async def save_rating(
    db: AsyncSession,
    user_id: str,
    payload: RatingSubmit,
    task: Task,
    is_reliability_check: bool = False,
) -> float:
    # Validate option
    if task.rating_options and payload.selected_option not in task.rating_options:
        raise ValueError(
            f"Unknown option {payload.selected_option!r}. "
            f"Valid: {task.rating_options}"
        )

    rel = await _get_user_reliability(db, user_id, payload.task_id)
    points = compute_points(
        task,
        rel.consistency_score if rel else None,
        rel.inter_rater_agreement if rel else None,
    )

    img = await db.get(ImageItem, payload.image_id)
    if img is None:
        raise DBError("Image not found")

    rating = Rating(
        user_id=user_id,
        task_id=payload.task_id,
        image_id=payload.image_id,
        selected_option=payload.selected_option,
        start_time=payload.start_time,
        end_time=payload.end_time,
        created_at=datetime.now(timezone.utc),
        is_reliability_check=is_reliability_check,
        points_earned=points,
    )
    db.add(rating)
    return points


# ---------------------------------------------------------------------------
# Stats & Leaderboard
# ---------------------------------------------------------------------------

async def my_stats(db: AsyncSession, user_id: str) -> MyStats:
    # Comparisons
    comp_result = await db.execute(
        select(Comparison.task_id, func.count(Comparison.id), func.sum(Comparison.points_earned))
        .where(Comparison.user_id == user_id)
        .group_by(Comparison.task_id)
    )
    total_comps = 0
    per_task_comps: dict[str, int] = {}
    total_score = 0.0
    for task_id, cnt, pts in comp_result.all():
        per_task_comps[task_id] = cnt
        total_comps += cnt
        total_score += pts or 0.0

    # Ratings
    rating_result = await db.execute(
        select(Rating.task_id, func.count(Rating.id), func.sum(Rating.points_earned))
        .where(Rating.user_id == user_id)
        .group_by(Rating.task_id)
    )
    total_ratings = 0
    per_task_ratings: dict[str, int] = {}
    for task_id, cnt, pts in rating_result.all():
        per_task_ratings[task_id] = cnt
        total_ratings += cnt
        total_score += pts or 0.0

    return MyStats(
        total_comparisons=total_comps,
        total_ratings=total_ratings,
        score=round(total_score, 2),
        per_task_comparisons=per_task_comps,
        per_task_ratings=per_task_ratings,
    )


async def global_stats(db: AsyncSession) -> GlobalStats:
    comp_result = await db.execute(
        select(Task.id, Task.name, func.count(Comparison.id))
        .join(Comparison, Comparison.task_id == Task.id, isouter=True)
        .group_by(Task.id)
    )
    rating_result = await db.execute(
        select(Task.id, func.count(Rating.id))
        .join(Rating, Rating.task_id == Task.id, isouter=True)
        .group_by(Task.id)
    )
    rating_by_task: dict[str, int] = {row.id: row[1] for row in rating_result.all()}

    per_task = []
    total_comps = 0
    total_ratings = 0
    for row in comp_result.all():
        task_id, task_name, comp_count = row
        rc = rating_by_task.get(task_id, 0)
        per_task.append(TaskStats(
            task_id=task_id, task_name=task_name,
            comparison_count=comp_count or 0, rating_count=rc,
        ))
        total_comps += comp_count or 0
        total_ratings += rc

    return GlobalStats(
        total_comparisons=total_comps,
        total_ratings=total_ratings,
        per_task=per_task,
    )


async def leaderboard_overall(
    db: AsyncSession,
    since_days: int | None = None,
) -> list[LeaderboardEntry]:
    from sqlalchemy import case
    from datetime import timedelta

    cutoff = None
    if since_days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)

    # Combine comparisons + ratings scores per user
    comp_stmt = select(
        Comparison.user_id,
        func.count(Comparison.id).label("cnt"),
        func.coalesce(func.sum(Comparison.points_earned), 0).label("pts"),
    )
    if cutoff:
        comp_stmt = comp_stmt.where(Comparison.created_at >= cutoff)
    comp_stmt = comp_stmt.group_by(Comparison.user_id)

    rating_stmt = select(
        Rating.user_id,
        func.count(Rating.id).label("cnt"),
        func.coalesce(func.sum(Rating.points_earned), 0).label("pts"),
    )
    if cutoff:
        rating_stmt = rating_stmt.where(Rating.created_at >= cutoff)
    rating_stmt = rating_stmt.group_by(Rating.user_id)

    comp_res = await db.execute(comp_stmt)
    rating_res = await db.execute(rating_stmt)

    user_counts: dict[str, int] = {}
    user_scores: dict[str, float] = {}
    for user_id, cnt, pts in comp_res.all():
        uid = str(user_id)
        user_counts[uid] = user_counts.get(uid, 0) + cnt
        user_scores[uid] = user_scores.get(uid, 0.0) + float(pts)
    for user_id, cnt, pts in rating_res.all():
        uid = str(user_id)
        user_counts[uid] = user_counts.get(uid, 0) + cnt
        user_scores[uid] = user_scores.get(uid, 0.0) + float(pts)

    # Get display names
    all_user_ids = list(user_counts.keys())
    if not all_user_ids:
        return []

    user_result = await db.execute(
        select(User.id, User.display_name, User.email).where(User.id.in_(all_user_ids))
    )
    user_info: dict[str, tuple[str | None, str]] = {
        str(row.id): (row.display_name, row.email) for row in user_result.all()
    }

    # Get reliability averages
    rel_result = await db.execute(
        select(UserReliability.user_id, UserReliability.consistency_score,
               UserReliability.inter_rater_agreement)
        .where(UserReliability.user_id.in_(all_user_ids))
    )
    rel_by_user: dict[str, list[float]] = {}
    for uid, cs, ira in rel_result.all():
        vals = [v for v in (cs, ira) if v is not None]
        if vals:
            rel_by_user.setdefault(str(uid), []).extend(vals)

    entries = []
    for uid, count in user_counts.items():
        display, email = user_info.get(uid, (None, uid))
        rel_vals = rel_by_user.get(uid, [])
        reliability = sum(rel_vals) / len(rel_vals) if rel_vals else None
        entries.append(LeaderboardEntry(
            user_id=uid,
            display_name=display or email,
            count=count,
            score=round(user_scores.get(uid, 0.0), 2),
            reliability=round(reliability, 3) if reliability is not None else None,
        ))

    return sorted(entries, key=lambda e: e.score, reverse=True)


async def leaderboard_for_task(
    db: AsyncSession,
    task_id: str,
    since_days: int | None = None,
) -> list[LeaderboardEntry]:
    from datetime import timedelta
    cutoff = None
    if since_days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)

    comp_stmt = select(
        Comparison.user_id,
        func.count(Comparison.id).label("cnt"),
        func.coalesce(func.sum(Comparison.points_earned), 0).label("pts"),
    ).where(Comparison.task_id == task_id)
    if cutoff:
        comp_stmt = comp_stmt.where(Comparison.created_at >= cutoff)
    comp_stmt = comp_stmt.group_by(Comparison.user_id)

    rating_stmt = select(
        Rating.user_id,
        func.count(Rating.id).label("cnt"),
        func.coalesce(func.sum(Rating.points_earned), 0).label("pts"),
    ).where(Rating.task_id == task_id)
    if cutoff:
        rating_stmt = rating_stmt.where(Rating.created_at >= cutoff)
    rating_stmt = rating_stmt.group_by(Rating.user_id)

    comp_res = await db.execute(comp_stmt)
    rating_res = await db.execute(rating_stmt)

    user_counts: dict[str, int] = {}
    user_scores: dict[str, float] = {}
    for user_id, cnt, pts in comp_res.all():
        uid = str(user_id)
        user_counts[uid] = user_counts.get(uid, 0) + cnt
        user_scores[uid] = user_scores.get(uid, 0.0) + float(pts)
    for user_id, cnt, pts in rating_res.all():
        uid = str(user_id)
        user_counts[uid] = user_counts.get(uid, 0) + cnt
        user_scores[uid] = user_scores.get(uid, 0.0) + float(pts)

    if not user_counts:
        return []

    all_user_ids = list(user_counts.keys())
    user_result = await db.execute(
        select(User.id, User.display_name, User.email).where(User.id.in_(all_user_ids))
    )
    user_info = {str(r.id): (r.display_name, r.email) for r in user_result.all()}

    rel_result = await db.execute(
        select(UserReliability.user_id, UserReliability.consistency_score,
               UserReliability.inter_rater_agreement)
        .where(UserReliability.user_id.in_(all_user_ids), UserReliability.task_id == task_id)
    )
    rel_by_user: dict[str, list[float]] = {}
    for uid, cs, ira in rel_result.all():
        vals = [v for v in (cs, ira) if v is not None]
        if vals:
            rel_by_user.setdefault(str(uid), []).extend(vals)

    entries = []
    for uid, count in user_counts.items():
        display, email = user_info.get(uid, (None, uid))
        rel_vals = rel_by_user.get(uid, [])
        reliability = sum(rel_vals) / len(rel_vals) if rel_vals else None
        entries.append(LeaderboardEntry(
            user_id=uid,
            display_name=display or email,
            count=count,
            score=round(user_scores.get(uid, 0.0), 2),
            reliability=round(reliability, 3) if reliability is not None else None,
        ))
    return sorted(entries, key=lambda e: e.score, reverse=True)


async def get_reliability_records(
    db: AsyncSession,
) -> list[UserReliabilityResponse]:
    result = await db.execute(select(UserReliability))
    records = result.scalars().all()

    user_ids = list({str(r.user_id) for r in records})
    user_result = await db.execute(
        select(User.id, User.display_name, User.email).where(User.id.in_(user_ids))
    )
    user_info = {str(r.id): (r.display_name, r.email) for r in user_result.all()}

    out = []
    for r in records:
        display, email = user_info.get(str(r.user_id), (None, str(r.user_id)))
        out.append(UserReliabilityResponse(
            user_id=str(r.user_id),
            display_name=display or email,
            task_id=r.task_id,
            annotation_count=r.annotation_count,
            consistency_score=r.consistency_score,
            inter_rater_agreement=r.inter_rater_agreement,
            computed_at=r.computed_at,
        ))
    return out


async def list_comparisons(
    db: AsyncSession,
    task_id: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> PaginatedComparisons:
    stmt = select(Comparison, User.display_name, User.email).join(
        User, User.id == Comparison.user_id, isouter=True
    )
    if task_id:
        stmt = stmt.where(Comparison.task_id == task_id)
    count_result = await db.execute(
        select(func.count()).select_from(stmt.subquery())
    )
    total = count_result.scalar_one()
    stmt = stmt.order_by(Comparison.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)

    items = []
    for comp, display_name, email in result.all():
        items.append(ComparisonRecord(
            id=comp.id,
            user_id=str(comp.user_id),
            display_name=display_name or email,
            task_id=comp.task_id,
            group_id=comp.group_id,
            image_a_id=comp.image_a_id,
            image_b_id=comp.image_b_id,
            winner_id=comp.winner_id,
            is_reliability_check=comp.is_reliability_check,
            points_earned=comp.points_earned,
            created_at=comp.created_at,
        ))
    return PaginatedComparisons(total=total, items=items)


async def list_ratings(
    db: AsyncSession,
    task_id: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> PaginatedRatings:
    stmt = select(Rating, User.display_name, User.email).join(
        User, User.id == Rating.user_id, isouter=True
    )
    if task_id:
        stmt = stmt.where(Rating.task_id == task_id)
    count_result = await db.execute(
        select(func.count()).select_from(stmt.subquery())
    )
    total = count_result.scalar_one()
    stmt = stmt.order_by(Rating.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)

    items = []
    for rating, display_name, email in result.all():
        items.append(RatingRecord(
            id=rating.id,
            user_id=str(rating.user_id),
            display_name=display_name or email,
            task_id=rating.task_id,
            image_id=rating.image_id,
            selected_option=rating.selected_option,
            is_reliability_check=rating.is_reliability_check,
            points_earned=rating.points_earned,
            created_at=rating.created_at,
        ))
    return PaginatedRatings(total=total, items=items)
