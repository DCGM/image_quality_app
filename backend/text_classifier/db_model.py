from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text as SQLText, UniqueConstraint
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column

from text_classifier.database import Base


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description_md: Mapped[str] = mapped_column(SQLText, nullable=False)
    multi_choice: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    max_choices: Mapped[int] = mapped_column(default=1, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    classes: Mapped[list[dict]] = mapped_column(JSON, nullable=False)


class TextItem(Base):
    __tablename__ = "texts"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    text: Mapped[str] = mapped_column(SQLText, nullable=False)
    language: Mapped[str] = mapped_column(String, nullable=False)
    raw_json: Mapped[dict] = mapped_column(JSON, nullable=False)


class Annotation(Base):
    __tablename__ = "annotations"
    __table_args__ = (UniqueConstraint("user_id", "text_id", "task_id", name="uq_annotation_user_text_task"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id"), nullable=False)
    text_id: Mapped[str] = mapped_column(ForeignKey("texts.id"), nullable=False)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    selected_classes: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
