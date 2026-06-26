from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from fastapi_users import schemas
from pydantic import BaseModel, field_validator


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class UserRead(schemas.BaseUser[uuid.UUID]):
    display_name: str | None = None


class UserCreate(schemas.BaseUserCreate):
    display_name: str | None = None


class UserUpdate(schemas.BaseUserUpdate):
    display_name: str | None = None


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

class TaskCreate(BaseModel):
    id: str
    name: str
    description_md: str = ""
    instructions_md: str = ""
    task_type: Literal["two_forced_choice", "single_rating"]
    pair_algorithm: str | None = "least_seen"
    rating_options: list[str] | None = None
    rating_hotkeys: list[str] | None = None
    bonus_multiplier: float = 1.0
    calib_ratio: float = 0.15


class TaskUpdate(BaseModel):
    name: str | None = None
    description_md: str | None = None
    instructions_md: str | None = None
    task_type: Literal["two_forced_choice", "single_rating"] | None = None
    pair_algorithm: str | None = None
    rating_options: list[str] | None = None
    rating_hotkeys: list[str] | None = None
    bonus_multiplier: float | None = None
    calib_ratio: float | None = None


class TaskRead(BaseModel):
    id: str
    name: str
    description_md: str
    instructions_md: str
    task_type: str
    enabled: bool
    pair_algorithm: str | None
    rating_options: list[str] | None
    rating_hotkeys: list[str] | None
    bonus_multiplier: float
    calib_ratio: float

    class Config:
        from_attributes = True


class TaskStatePatch(BaseModel):
    enabled: bool | None = None
    deleted: bool | None = None
    bonus_multiplier: float | None = None


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------

class ImageItemResponse(BaseModel):
    id: str
    task_id: str
    filename: str
    group_id: str
    url: str
    suspended: bool
    width: int | None
    height: int | None

    class Config:
        from_attributes = True


class ImageListResponse(BaseModel):
    total: int
    items: list[ImageItemResponse]


class ImagePatch(BaseModel):
    suspended: bool


# ---------------------------------------------------------------------------
# Next pair / next image (what to annotate next)
# ---------------------------------------------------------------------------

class NextPairResponse(BaseModel):
    task_id: str
    image_a_id: str
    image_b_id: str
    image_a_url: str
    image_b_url: str
    group_id: str
    is_reliability_check: bool


class NextImageResponse(BaseModel):
    task_id: str
    image_id: str
    image_url: str
    group_id: str
    is_reliability_check: bool


# ---------------------------------------------------------------------------
# Submissions
# ---------------------------------------------------------------------------

class ComparisonSubmit(BaseModel):
    task_id: str
    image_a_id: str
    image_b_id: str
    winner_id: str
    start_time: datetime
    end_time: datetime


class RatingSubmit(BaseModel):
    task_id: str
    image_id: str
    selected_option: str
    start_time: datetime
    end_time: datetime

    @field_validator("selected_option")
    @classmethod
    def option_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("selected_option must not be empty")
        return v


# ---------------------------------------------------------------------------
# Rankings
# ---------------------------------------------------------------------------

class ImageRankingResponse(BaseModel):
    image_id: str
    filename: str
    url: str
    score: float
    comparisons: int
    wins: int

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Comparisons & Ratings (admin list)
# ---------------------------------------------------------------------------

class ComparisonRecord(BaseModel):
    id: str
    user_id: str
    display_name: str | None
    task_id: str
    group_id: str
    image_a_id: str
    image_b_id: str
    winner_id: str | None
    is_reliability_check: bool
    points_earned: float | None
    created_at: datetime

    class Config:
        from_attributes = True


class RatingRecord(BaseModel):
    id: str
    user_id: str
    display_name: str | None
    task_id: str
    image_id: str
    selected_option: str | None
    is_reliability_check: bool
    points_earned: float | None
    created_at: datetime

    class Config:
        from_attributes = True


class PaginatedComparisons(BaseModel):
    total: int
    items: list[ComparisonRecord]


class PaginatedRatings(BaseModel):
    total: int
    items: list[RatingRecord]


# ---------------------------------------------------------------------------
# Stats & Leaderboard
# ---------------------------------------------------------------------------

class LeaderboardEntry(BaseModel):
    user_id: str
    display_name: str | None
    count: int
    score: float
    reliability: float | None = None


class TaskStats(BaseModel):
    task_id: str
    task_name: str
    comparison_count: int
    rating_count: int


class GlobalStats(BaseModel):
    total_comparisons: int
    total_ratings: int
    per_task: list[TaskStats]


class MyStats(BaseModel):
    total_comparisons: int
    total_ratings: int
    score: float
    per_task_comparisons: dict[str, int]
    per_task_ratings: dict[str, int]


# ---------------------------------------------------------------------------
# Reliability
# ---------------------------------------------------------------------------

class UserReliabilityResponse(BaseModel):
    user_id: str
    display_name: str | None
    task_id: str
    annotation_count: int
    consistency_score: float | None
    inter_rater_agreement: float | None
    computed_at: datetime | None

    class Config:
        from_attributes = True
