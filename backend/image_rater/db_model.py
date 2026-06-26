from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, DateTime, Enum, Float, ForeignKey, Integer, JSON, String, Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from image_rater.database import Base


class TaskType(str, enum.Enum):
    two_forced_choice = "two_forced_choice"
    single_rating = "single_rating"


class PairAlgorithm(str, enum.Enum):
    least_seen = "least_seen"
    swiss = "swiss"
    bradley_terry = "bradley_terry"


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description_md: Mapped[str] = mapped_column(Text, default="")
    instructions_md: Mapped[str] = mapped_column(Text, default="")
    task_type: Mapped[TaskType] = mapped_column(Enum(TaskType), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # 2FC only
    pair_algorithm: Mapped[str | None] = mapped_column(
        String(32), nullable=True, default=PairAlgorithm.least_seen.value
    )
    # single_rating only
    rating_options: Mapped[list | None] = mapped_column(JSON, nullable=True)
    rating_hotkeys: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # scoring
    bonus_multiplier: Mapped[float] = mapped_column(Float, default=1.0)
    # reliability check ratio (fraction of submissions that re-show an already-seen item)
    calib_ratio: Mapped[float] = mapped_column(Float, default=0.15)

    images: Mapped[list[ImageItem]] = relationship("ImageItem", back_populates="task")


class ImageItem(Base):
    __tablename__ = "image_items"

    id: Mapped[str] = mapped_column(String(512), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(64), ForeignKey("tasks.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String(255))
    group_id: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(1024))
    suspended: Mapped[bool] = mapped_column(Boolean, default=False)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)

    task: Mapped[Task] = relationship("Task", back_populates="images")
    ranking: Mapped[ImageRanking | None] = relationship(
        "ImageRanking", back_populates="image", uselist=False
    )


class ImageRanking(Base):
    __tablename__ = "image_rankings"
    __table_args__ = (UniqueConstraint("image_id", "task_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    image_id: Mapped[str] = mapped_column(String(512), ForeignKey("image_items.id"), nullable=False)
    task_id: Mapped[str] = mapped_column(String(64), ForeignKey("tasks.id"), nullable=False)
    score: Mapped[float] = mapped_column(Float, default=1000.0)
    comparisons: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    image: Mapped[ImageItem] = relationship("ImageItem", back_populates="ranking")


class Comparison(Base):
    """A 2-forced-choice comparison result."""
    __tablename__ = "comparisons"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("user.id"), nullable=False)
    task_id: Mapped[str] = mapped_column(String(64), ForeignKey("tasks.id"), nullable=False)
    group_id: Mapped[str] = mapped_column(String(255))
    image_a_id: Mapped[str] = mapped_column(String(512), ForeignKey("image_items.id"), nullable=False)
    image_b_id: Mapped[str] = mapped_column(String(512), ForeignKey("image_items.id"), nullable=False)
    winner_id: Mapped[str | None] = mapped_column(String(512), ForeignKey("image_items.id"), nullable=True)
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    is_reliability_check: Mapped[bool] = mapped_column(Boolean, default=False)
    points_earned: Mapped[float | None] = mapped_column(Float, nullable=True)


class Rating(Base):
    """A single-image rating result."""
    __tablename__ = "ratings"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("user.id"), nullable=False)
    task_id: Mapped[str] = mapped_column(String(64), ForeignKey("tasks.id"), nullable=False)
    image_id: Mapped[str] = mapped_column(String(512), ForeignKey("image_items.id"), nullable=False)
    selected_option: Mapped[str | None] = mapped_column(String(255), nullable=True)
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    is_reliability_check: Mapped[bool] = mapped_column(Boolean, default=False)
    points_earned: Mapped[float | None] = mapped_column(Float, nullable=True)


class UserReliability(Base):
    __tablename__ = "user_reliability"
    __table_args__ = (UniqueConstraint("user_id", "task_id"),)

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("user.id"), nullable=False)
    task_id: Mapped[str] = mapped_column(String(64), ForeignKey("tasks.id"), nullable=False)
    consistency_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    inter_rater_agreement: Mapped[float | None] = mapped_column(Float, nullable=True)
    annotation_count: Mapped[int] = mapped_column(Integer, default=0)
    computed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
