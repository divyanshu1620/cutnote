import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_owned_project
from app.core.config import get_settings
from app.core.limiter import limiter
from app.core.security import (
    sanitize_display_filename,
    sanitize_text,
    sign_review_token,
    sniff_media_magic_bytes,
)
from app.db.models import Project, ProjectStatus, ReviewLink, UploadSession, User
from app.db.session import get_db
from app.schemas.projects import (
    ProjectResponse,
    ReviewLinkCreateRequest,
    ReviewLinkResponse,
    UploadChunkResponse,
    UploadInitRequest,
    UploadInitResponse,
)
from app.services.ffmpeg import probe_media
from app.services.storage import StorageBackend, get_storage

router = APIRouter(prefix="/projects", tags=["projects"])
settings = get_settings()

ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm"}


@router.post("/uploads/init", response_model=UploadInitResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
async def init_upload(
    request: Request,
    payload: UploadInitRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UploadInitResponse:
    if payload.expected_size_bytes > settings.MAX_VIDEO_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Video exceeds maximum allowed file size.",
        )

    safe_display_name = sanitize_display_filename(payload.filename)
    ext = Path(safe_display_name).suffix.lower()
    if ext not in ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported video extension. Allowed: .mp4, .mov, .webm",
        )

    storage_key = f"vid_{uuid.uuid4().hex}{ext}"

    project = Project(
        owner_id=current_user.id,
        title=sanitize_text(payload.title, max_length=160),
        storage_key=storage_key,
        original_filename=safe_display_name,
        mime_type="application/octet-stream",
        file_size_bytes=0,
        status=ProjectStatus.UPLOADING,
    )
    db.add(project)
    await db.flush()

    upload_session = UploadSession(
        project_id=project.id,
        owner_id=current_user.id,
        expected_size_bytes=payload.expected_size_bytes,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=6),
    )
    db.add(upload_session)
    await db.commit()
    await db.refresh(upload_session)

    return UploadInitResponse(
        session_id=upload_session.id,
        project_id=project.id,
        max_chunk_size_bytes=settings.MAX_CHUNK_SIZE_BYTES,
    )


@router.post("/uploads/{session_id}/chunk", response_model=UploadChunkResponse)
@limiter.limit("120/minute")
async def upload_chunk(
    request: Request,
    session_id: str,
    chunk: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: StorageBackend = Depends(get_storage),
) -> UploadChunkResponse:
    result = await db.execute(select(UploadSession).where(UploadSession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload session not found.")
    if session.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this upload.")
    if session.is_completed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Upload already completed.")

    data = await chunk.read()
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty chunk.")
    if len(data) > settings.MAX_CHUNK_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Chunk exceeds maximum chunk size.",
        )

    new_total = session.received_bytes + len(data)
    if new_total > settings.MAX_VIDEO_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Total upload exceeds maximum allowed video size.",
        )

    proj_result = await db.execute(select(Project).where(Project.id == session.project_id))
    project = proj_result.scalar_one()

    # Validate magic bytes strictly on the very first chunk
    if session.received_bytes == 0:
        detected_mime = sniff_media_magic_bytes(data[:32], media_kind="video")
        if not detected_mime:
            project.status = ProjectStatus.FAILED
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or spoofed video file signature.",
            )
        project.mime_type = detected_mime

    written_size = storage.append_chunk(project.storage_key, data)
    session.received_bytes = written_size
    session.chunk_count += 1
    project.file_size_bytes = written_size
    await db.commit()

    return UploadChunkResponse(
        session_id=session.id,
        received_bytes=session.received_bytes,
        expected_size_bytes=session.expected_size_bytes,
        chunk_count=session.chunk_count,
    )


@router.post("/uploads/{session_id}/complete", response_model=ProjectResponse)
@limiter.limit("20/minute")
async def complete_upload(
    request: Request,
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: StorageBackend = Depends(get_storage),
) -> Project:
    result = await db.execute(select(UploadSession).where(UploadSession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Upload session not found.")
    if session.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this upload.")
    if session.received_bytes <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No data uploaded.")

    proj_result = await db.execute(select(Project).where(Project.id == session.project_id))
    project = proj_result.scalar_one()

    try:
        file_path = storage.get_local_path(project.storage_key)
        meta = probe_media(file_path)
    except Exception as exc:
        storage.delete(project.storage_key)
        project.status = ProjectStatus.FAILED
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to inspect uploaded video.",
        ) from exc

    if meta.duration_seconds > settings.MAX_VIDEO_DURATION_SECONDS:
        storage.delete(project.storage_key)
        project.status = ProjectStatus.FAILED
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Video duration exceeds maximum allowed limit.",
        )

    project.duration_seconds = meta.duration_seconds
    project.fps = meta.fps
    project.status = ProjectStatus.READY
    session.is_completed = True
    current_user.usage_count += 1
    await db.commit()
    await db.refresh(project)
    return project


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Project]:
    result = await db.execute(
        select(Project)
        .where(Project.owner_id == current_user.id)
        .order_by(Project.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project: Project = Depends(get_owned_project),
) -> Project:
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project: Project = Depends(get_owned_project),
    db: AsyncSession = Depends(get_db),
    storage: StorageBackend = Depends(get_storage),
) -> None:
    storage.delete(project.storage_key)
    await db.delete(project)
    await db.commit()


@router.post("/{project_id}/review-links", response_model=ReviewLinkResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
async def create_review_link(
    request: Request,
    payload: ReviewLinkCreateRequest,
    project: Project = Depends(get_owned_project),
    db: AsyncSession = Depends(get_db),
) -> ReviewLinkResponse:
    expires_at = datetime.now(timezone.utc) + timedelta(hours=payload.expires_in_hours)
    link = ReviewLink(project_id=project.id, expires_at=expires_at)
    db.add(link)
    await db.commit()
    await db.refresh(link)

    expires_ts = int(expires_at.timestamp())
    sig = sign_review_token(link.token_id, project.id, expires_ts)
    return ReviewLinkResponse(
        id=link.id,
        project_id=project.id,
        review_token=f"{link.token_id}.{sig}",
        expires_at=link.expires_at,
    )