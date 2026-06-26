from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from image_rater import crud
from image_rater.base_objects import (
    ComparisonSubmit, GlobalStats, ImageItemResponse, ImageListResponse,
    ImagePatch, ImageRankingResponse, LeaderboardEntry, MyStats,
    NextImageResponse, NextPairResponse, PaginatedComparisons, PaginatedRatings,
    RatingSubmit, TaskCreate, TaskRead, TaskStatePatch, TaskUpdate,
    UserReliabilityResponse,
)
from image_rater.config import config
from image_rater.database import get_async_session
from image_rater.db_model import Task
from image_rater.image_selector import get_next_image
from image_rater.image_store import ingest_zip
from image_rater.pair_selector import ALGORITHM_DESCRIPTIONS, get_next_pair
from image_rater.reliability import run_reliability_job
from image_rater.users import current_active_user
from image_rater.database import User

api_route = APIRouter(tags=["api"])
admin_route = APIRouter(tags=["admin"])


def _require_admin(user: User = Depends(current_active_user)) -> User:
    if not user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
    return user


def _image_url_base(task_id: str, filename: str) -> str:
    return f"/images/{task_id}/{filename}"


# ---------------------------------------------------------------------------
# Public — Tasks
# ---------------------------------------------------------------------------

@api_route.get("/tasks", response_model=list[TaskRead])
async def get_tasks(
    db: AsyncSession = Depends(get_async_session),
    _user: User = Depends(current_active_user),
):
    tasks = await crud.list_enabled_tasks(db)
    return [TaskRead.model_validate(t) for t in tasks]


@api_route.get("/tasks/{task_id}", response_model=TaskRead)
async def get_task(
    task_id: str,
    db: AsyncSession = Depends(get_async_session),
    _user: User = Depends(current_active_user),
):
    task = await crud.get_task(db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskRead.model_validate(task)


@api_route.get("/algorithms", response_model=dict[str, str])
async def get_algorithms(_user: User = Depends(current_active_user)):
    """Return descriptions of all available pair-selection algorithms."""
    return ALGORITHM_DESCRIPTIONS


# ---------------------------------------------------------------------------
# Public — Next item to annotate
# ---------------------------------------------------------------------------

@api_route.post("/tasks/{task_id}/next-pair", response_model=NextPairResponse | None)
async def next_pair(
    task_id: str,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    task = await crud.get_task(db, task_id)
    if task is None or not task.enabled:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.task_type != "two_forced_choice":
        raise HTTPException(status_code=400, detail="Task is not a 2-forced-choice task")

    result = await get_next_pair(db, str(user.id), task)
    if result is None:
        return None
    img_a, img_b, group_id, is_rel = result
    return NextPairResponse(
        task_id=task_id,
        image_a_id=img_a.id,
        image_b_id=img_b.id,
        image_a_url=_image_url_base(task_id, img_a.filename),
        image_b_url=_image_url_base(task_id, img_b.filename),
        group_id=group_id,
        is_reliability_check=is_rel,
    )


@api_route.post("/tasks/{task_id}/next-image", response_model=NextImageResponse | None)
async def next_image(
    task_id: str,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    task = await crud.get_task(db, task_id)
    if task is None or not task.enabled:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.task_type != "single_rating":
        raise HTTPException(status_code=400, detail="Task is not a single-rating task")

    result = await get_next_image(db, str(user.id), task)
    if result is None:
        return None
    img, is_rel = result
    return NextImageResponse(
        task_id=task_id,
        image_id=img.id,
        image_url=_image_url_base(task_id, img.filename),
        group_id=img.group_id,
        is_reliability_check=is_rel,
    )


# ---------------------------------------------------------------------------
# Public — Submit annotations
# ---------------------------------------------------------------------------

@api_route.post("/comparisons", response_model=dict)
async def submit_comparison(
    payload: ComparisonSubmit,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    task = await crud.get_task(db, payload.task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    try:
        points = await crud.save_comparison(db, str(user.id), payload, task)
    except (ValueError, Exception) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await db.commit()
    return {"points": round(points, 3)}


@api_route.post("/ratings", response_model=dict)
async def submit_rating(
    payload: RatingSubmit,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    task = await crud.get_task(db, payload.task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    try:
        points = await crud.save_rating(db, str(user.id), payload, task)
    except (ValueError, Exception) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await db.commit()
    return {"points": round(points, 3)}


# ---------------------------------------------------------------------------
# Public — Stats & Leaderboard
# ---------------------------------------------------------------------------

@api_route.get("/stats/me", response_model=MyStats)
async def stats_me(
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
):
    return await crud.my_stats(db, str(user.id))


@api_route.get("/stats/global", response_model=GlobalStats)
async def stats_global(
    db: AsyncSession = Depends(get_async_session),
    _user: User = Depends(current_active_user),
):
    return await crud.global_stats(db)


@api_route.get("/stats/leaderboard", response_model=list[LeaderboardEntry])
async def leaderboard(
    since_days: int | None = Query(None),
    db: AsyncSession = Depends(get_async_session),
    _user: User = Depends(current_active_user),
):
    return await crud.leaderboard_overall(db, since_days)


@api_route.get("/stats/leaderboard/{task_id}", response_model=list[LeaderboardEntry])
async def leaderboard_task(
    task_id: str,
    since_days: int | None = Query(None),
    db: AsyncSession = Depends(get_async_session),
    _user: User = Depends(current_active_user),
):
    return await crud.leaderboard_for_task(db, task_id, since_days)


# ---------------------------------------------------------------------------
# Admin — Tasks
# ---------------------------------------------------------------------------

@admin_route.get("/tasks", response_model=list[TaskRead])
async def admin_list_tasks(
    db: AsyncSession = Depends(get_async_session),
    _admin: User = Depends(_require_admin),
):
    tasks = await crud.list_all_tasks(db)
    return [TaskRead.model_validate(t) for t in tasks]


@admin_route.post("/tasks", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
async def admin_create_task(
    data: TaskCreate,
    db: AsyncSession = Depends(get_async_session),
    _admin: User = Depends(_require_admin),
):
    task = await crud.upsert_task(db, data)
    await db.commit()
    await db.refresh(task)
    return TaskRead.model_validate(task)


@admin_route.put("/tasks/{task_id}", response_model=TaskRead)
async def admin_update_task(
    task_id: str,
    data: TaskUpdate,
    db: AsyncSession = Depends(get_async_session),
    _admin: User = Depends(_require_admin),
):
    try:
        task = await crud.update_task(db, task_id, data)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    await db.commit()
    await db.refresh(task)
    return TaskRead.model_validate(task)


@admin_route.patch("/tasks/{task_id}")
async def admin_patch_task(
    task_id: str,
    patch: TaskStatePatch,
    db: AsyncSession = Depends(get_async_session),
    _admin: User = Depends(_require_admin),
):
    try:
        await crud.patch_task_state(
            db, task_id, patch.enabled, patch.deleted, patch.bonus_multiplier
        )
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    await db.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Admin — Images
# ---------------------------------------------------------------------------

@admin_route.post("/tasks/{task_id}/upload-images")
async def admin_upload_images(
    task_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_async_session),
    _admin: User = Depends(_require_admin),
):
    task = await crud.get_task(db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only ZIP files are accepted")
    data = await file.read()
    try:
        count = await ingest_zip(db, task_id, data, config.STATIC_DIR)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await db.commit()
    return {"imported": count}


@admin_route.get("/tasks/{task_id}/images", response_model=ImageListResponse)
async def admin_list_images(
    task_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    q: str | None = Query(None),
    db: AsyncSession = Depends(get_async_session),
    _admin: User = Depends(_require_admin),
):
    return await crud.list_images(db, task_id, page, page_size, q)


@admin_route.patch("/images/{image_id:path}")
async def admin_patch_image(
    image_id: str,
    patch: ImagePatch,
    db: AsyncSession = Depends(get_async_session),
    _admin: User = Depends(_require_admin),
):
    try:
        await crud.patch_image(db, image_id, patch.suspended)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    await db.commit()
    return {"ok": True}


@admin_route.get("/tasks/{task_id}/rankings", response_model=list[ImageRankingResponse])
async def admin_rankings(
    task_id: str,
    db: AsyncSession = Depends(get_async_session),
    _admin: User = Depends(_require_admin),
):
    return await crud.get_rankings(db, task_id)


# ---------------------------------------------------------------------------
# Admin — Comparisons & Ratings
# ---------------------------------------------------------------------------

@admin_route.get("/comparisons", response_model=PaginatedComparisons)
async def admin_comparisons(
    task_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_async_session),
    _admin: User = Depends(_require_admin),
):
    return await crud.list_comparisons(db, task_id, page, page_size)


@admin_route.get("/ratings", response_model=PaginatedRatings)
async def admin_ratings(
    task_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_async_session),
    _admin: User = Depends(_require_admin),
):
    return await crud.list_ratings(db, task_id, page, page_size)


# ---------------------------------------------------------------------------
# Admin — Stats & Reliability
# ---------------------------------------------------------------------------

@admin_route.get("/stats", response_model=GlobalStats)
async def admin_stats(
    db: AsyncSession = Depends(get_async_session),
    _admin: User = Depends(_require_admin),
):
    return await crud.global_stats(db)


@admin_route.get("/reliability", response_model=list[UserReliabilityResponse])
async def admin_reliability(
    db: AsyncSession = Depends(get_async_session),
    _admin: User = Depends(_require_admin),
):
    return await crud.get_reliability_records(db)


@admin_route.post("/reliability/recompute")
async def admin_recompute_reliability(
    db: AsyncSession = Depends(get_async_session),
    _admin: User = Depends(_require_admin),
):
    await run_reliability_job(db)
    await db.commit()
    return {"ok": True}
