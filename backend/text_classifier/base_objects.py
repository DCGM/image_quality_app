from __future__ import annotations

from datetime import datetime
import uuid

from fastapi_users import schemas
from pydantic import BaseModel, Field


class UserRead(schemas.BaseUser[uuid.UUID]):
    pass


class UserCreate(schemas.BaseUserCreate):
    pass


class UserUpdate(schemas.BaseUserUpdate):
    pass


class TaskClass(BaseModel):
    id: str
    label_en: str
    label_cs: str


class TaskDefinition(BaseModel):
    id: str
    name: str
    description_md: str
    multi_choice: bool
    max_choices: int = 1
    enabled: bool = True
    classes: list[TaskClass]


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
