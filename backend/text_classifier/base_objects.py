from __future__ import annotations

from datetime import datetime
from typing import Literal
import uuid

from fastapi_users import schemas
from pydantic import BaseModel, Field, model_validator


class UserRead(schemas.BaseUser[uuid.UUID]):
    display_name: str | None = None


class UserCreate(schemas.BaseUserCreate):
    display_name: str | None = None


class UserUpdate(schemas.BaseUserUpdate):
    display_name: str | None = None


class TaskClass(BaseModel):
    id: str
    label_en: str
    label_cs: str
    description: str | None = None


class TaskSamplingConfig(BaseModel):
    calib_ratio_initial: float = Field(default=0.30, ge=0.0, le=1.0)
    calib_initial_count: int = Field(default=20, ge=0)
    calib_ratio_ongoing: float = Field(default=0.10, ge=0.0, le=1.0)
    repeat_probability: float = Field(default=0.20, ge=0.0, le=1.0)
    target_coverage: int = Field(default=3, ge=1)


class TaskDefinition(BaseModel):
    id: str
    name: str
    description_md: str
    multi_choice: bool
    max_choices: int = Field(default=1, ge=1)
    enabled: bool = True
    classes: list[TaskClass] = Field(min_length=1)
    calib_ratio_initial: float = Field(default=0.30, ge=0.0, le=1.0)
    calib_initial_count: int = Field(default=20, ge=0)
    calib_ratio_ongoing: float = Field(default=0.10, ge=0.0, le=1.0)
    repeat_probability: float = Field(default=0.20, ge=0.0, le=1.0)
    target_coverage: int = Field(default=3, ge=1)
    # Read-only: computed at query time, not stored
    current_multiplier: float | None = None

    @model_validator(mode='after')
    def validate_choice_limits(self) -> 'TaskDefinition':
        if not self.multi_choice and self.max_choices != 1:
            raise ValueError('Single-choice tasks must have max_choices set to 1')
        if self.max_choices > len(self.classes):
            raise ValueError('max_choices cannot exceed the number of classes')
        return self


class TaskStatePatch(BaseModel):
    enabled: bool | None = None
    deleted: bool = False


class NextTextRequest(BaseModel):
    task_ids: list[str] = Field(min_length=1, max_length=6)


class NextTextResponse(BaseModel):
    id: str
    text: str
    language: str
    calibration_task_ids: list[str] = Field(default_factory=list)


class TaskAnnotation(BaseModel):
    task_id: str
    selected_classes: list[str]
    start_time: datetime
    end_time: datetime


class AnnotationSubmit(BaseModel):
    text_id: str
    annotations: list[TaskAnnotation]


class AnnotationTypeValue(BaseModel):
    annotation_type: Literal['ground_truth', 'llm']


class BulkAnnotationItem(BaseModel):
    text_id: str
    task_id: str
    selected_classes: list[str]


class LeaderboardEntry(BaseModel):
    user_id: str
    display_name: str
    count: int
    score: float = 0.0
    reliability: float | None = None


class TextItemResponse(BaseModel):
    id: str
    text_preview: str
    language: str
    suspended: bool
    annotation_count: int = 0


class TextListResponse(BaseModel):
    total: int
    items: list[TextItemResponse]


class TextAnnotationEntry(BaseModel):
    annotation_id: str
    user_id: str
    display_name: str
    task_id: str
    selected_classes: list[str]
    annotation_type: str
    created_at: str | None
    points_earned: float | None


class TextPatch(BaseModel):
    suspended: bool


class TaskStats(BaseModel):
    task_id: str
    task_name: str
    count: int


class GlobalStats(BaseModel):
    total_annotations: int
    per_task: list[TaskStats]


class UserReliabilityResponse(BaseModel):
    user_id: str
    display_name: str
    task_id: str
    annotation_count: int
    pairwise_agreement: float | None
    cohens_kappa: float | None
    krippendorffs_alpha: float | None
    ds_sensitivity: float | None
    computed_at: datetime | None


class MyStats(BaseModel):
    total: int
    per_task: dict[str, int]
    score: float
    per_task_score: dict[str, float]
