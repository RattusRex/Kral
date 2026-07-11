from datetime import date, time
from typing import Literal

from pydantic import BaseModel, Field


class RecruitmentCreate(BaseModel):
    project_id: int | None = None
    real_date: date
    game_date: date
    start_time: time
    duration: str = Field(min_length=1, max_length=100)
    location: str = Field(min_length=1, max_length=300)
    quest: str = Field(min_length=1, max_length=2000)
    notes: str = Field(default="", max_length=2000)


class ApplicationCreate(BaseModel):
    character_id: int


class ParticipantSelection(BaseModel):
    application_ids: list[int] = Field(min_length=1, max_length=100)


class RecruitmentStatusUpdate(BaseModel):
    status: Literal["upcoming", "completed"]
