from __future__ import annotations

from datetime import datetime
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


class TaskDefinition(BaseModel):
    id: str
    name: str
    description_md: str
    multi_choice: bool
    max_choices: int = Field(default=1, ge=1)
    enabled: bool = True
    classes: list[TaskClass] = Field(min_length=1)

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


class TaskAnnotation(BaseModel):
    task_id: str
    selected_classes: list[str]
    start_time: datetime
    end_time: datetime


class AnnotationSubmit(BaseModel):
    text_id: str
    annotations: list[TaskAnnotation]


class LeaderboardEntry(BaseModel):
    user_id: str
    display_name: str
    count: int


class TextItemResponse(BaseModel):
    id: str
    text_preview: str
    language: str
    suspended: bool


class TextListResponse(BaseModel):
    total: int
    items: list[TextItemResponse]


class TextPatch(BaseModel):
    suspended: bool


class TaskStats(BaseModel):
    task_id: str
    task_name: str
    count: int


class GlobalStats(BaseModel):
    total_annotations: int
    per_task: list[TaskStats]
