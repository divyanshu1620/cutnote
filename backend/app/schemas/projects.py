from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UploadInitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=160)
    filename: str = Field(min_length=1, max_length=255)
    expected_size_bytes: int = Field(gt=0)


class UploadInitResponse(BaseModel):
    session_id: str
    project_id: str
    max_chunk_size_bytes: int


class UploadChunkResponse(BaseModel):
    session_id: str
    received_bytes: int
    expected_size_bytes: int
    chunk_count: int


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    original_filename: str
    mime_type: str
    file_size_bytes: int
    duration_seconds: float
    fps: float
    status: str
    created_at: datetime


class ReviewLinkCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expires_in_hours: int = Field(default=72, ge=1, le=720)


class ReviewLinkResponse(BaseModel):
    id: str
    project_id: str
    review_token: str
    expires_at: datetime