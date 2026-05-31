from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text as SQLText, UniqueConstraint
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column

from text_classifier.database import Base


class AnnotationType(str, enum.Enum):
    user = "user"
    ground_truth = "ground_truth"
    llm = "llm"


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description_md: Mapped[str] = mapped_column(SQLText, nullable=False)
    multi_choice: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    max_choices: Mapped[int] = mapped_column(default=1, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    classes: Mapped[list[dict]] = mapped_column(JSON, nullable=False)
    # Sampling configuration
    calib_ratio_initial: Mapped[float] = mapped_column(Float, default=0.30, nullable=False, server_default='0.3')
    calib_initial_count: Mapped[int] = mapped_column(Integer, default=20, nullable=False, server_default='20')
    calib_ratio_ongoing: Mapped[float] = mapped_column(Float, default=0.10, nullable=False, server_default='0.1')
    repeat_probability: Mapped[float] = mapped_column(Float, default=0.20, nullable=False, server_default='0.2')
    target_coverage: Mapped[int] = mapped_column(Integer, default=3, nullable=False, server_default='3')


class TextItem(Base):
    __tablename__ = "texts"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    text: Mapped[str] = mapped_column(SQLText, nullable=False)
    language: Mapped[str] = mapped_column(String, nullable=False)
    raw_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    suspended: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default='0')


class Annotation(Base):
    __tablename__ = "annotations"
    __table_args__ = (UniqueConstraint("user_id", "text_id", "task_id", "annotation_type", name="uq_annotation_user_text_task_type"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id"), nullable=False)
    text_id: Mapped[str] = mapped_column(ForeignKey("texts.id"), nullable=False)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    selected_classes: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    annotation_type: Mapped[AnnotationType] = mapped_column(
        Enum(AnnotationType, native_enum=False),
        default=AnnotationType.user,
        nullable=False,
        server_default=AnnotationType.user.value,
    )
    weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False, server_default='1.0')
    points_earned: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)


class UserReliability(Base):
    __tablename__ = "user_reliability"
    __table_args__ = (UniqueConstraint("user_id", "task_id", name="uq_reliability_user_task"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id"), nullable=False)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    pairwise_agreement: Mapped[float | None] = mapped_column(Float, nullable=True)
    cohens_kappa: Mapped[float | None] = mapped_column(Float, nullable=True)
    krippendorffs_alpha: Mapped[float | None] = mapped_column(Float, nullable=True)
    ds_sensitivity: Mapped[float | None] = mapped_column(Float, nullable=True)
    annotation_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    computed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
