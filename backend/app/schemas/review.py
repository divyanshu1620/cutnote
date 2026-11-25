from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CommentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    author_name: str = Field(min_length=1, max_length=80)
    timestamp_seconds: float = Field(ge=0.0)
    body_text: str = Field(min_length=1, max_length=2000)


class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    author_name: str
    timestamp_seconds: float
    body_text: str | None
    voice_transcript: str | None
    ai_checklist_item: str | None
    is_resolved: bool
    created_at: datetime


class ReviewProjectResponse(BaseModel):
    project_id: str
    title: str
    duration_seconds: float
    fps: float
    comments: list[CommentResponse]