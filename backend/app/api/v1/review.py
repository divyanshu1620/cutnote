import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.limiter import limiter
from app.core.security import (
    sanitize_text,
    sniff_media_magic_bytes,
    verify_review_signature,
)
from app.db.models import Comment, Project, ReviewLink
from app.db.session import get_db
from app.schemas.review import CommentCreateRequest, CommentResponse, ReviewProjectResponse
from app.services.storage import StorageBackend, get_storage
from app.services.transcription import transcribe_voice_note

router = APIRouter(prefix="/review", tags=["review"])
settings = get_settings()

AUDIO_EXT_MAP = {
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/wav": ".wav",
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
}


async def _verify_review_link(review_token: str, db: AsyncSession) -> tuple[ReviewLink, Project]:
    """Cryptographically verifies token_id.hmac_signature and checks expiry/revocation."""
    if "." not in review_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid review link.")

    token_id, provided_sig = review_token.split(".", 1)
    result = await db.execute(select(ReviewLink).where(ReviewLink.token_id == token_id))
    link = result.scalar_one_or_none()
    if not link or link.is_revoked:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Review link is invalid or revoked.")

    expires_at = link.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Review link has expired.")

    expires_ts = int(expires_at.timestamp())
    if not verify_review_signature(link.token_id, link.project_id, expires_ts, provided_sig):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid review link signature.")

    proj_result = await db.execute(select(Project).where(Project.id == link.project_id))
    project = proj_result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    return link, project


@router.get("/{review_token}", response_model=ReviewProjectResponse)
@limiter.limit("60/minute")
async def get_review_session(
    request: Request,
    review_token: str,
    db: AsyncSession = Depends(get_db),
) -> ReviewProjectResponse:
    _, project = await _verify_review_link(review_token, db)
    comments_res = await db.execute(
        select(Comment)
        .where(Comment.project_id == project.id)
        .order_by(Comment.timestamp_seconds.asc(), Comment.created_at.asc())
    )
    comments = list(comments_res.scalars().all())
    return ReviewProjectResponse(
        project_id=project.id,
        title=project.title,
        duration_seconds=project.duration_seconds,
        fps=project.fps,
        comments=[CommentResponse.model_validate(c) for c in comments],
    )


@router.get("/{review_token}/video")
@limiter.limit("60/minute")
async def stream_review_video(
    request: Request,
    review_token: str,
    db: AsyncSession = Depends(get_db),
    storage: StorageBackend = Depends(get_storage),
) -> FileResponse:
    _, project = await _verify_review_link(review_token, db)
    try:
        video_path = storage.get_local_path(project.storage_key)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video file not found.") from exc

    return FileResponse(path=video_path, media_type=project.mime_type)


@router.post("/{review_token}/comments", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
async def create_text_comment(
    request: Request,
    review_token: str,
    payload: CommentCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> Comment:
    link, project = await _verify_review_link(review_token, db)

    comment = Comment(
        project_id=project.id,
        review_link_id=link.id,
        author_name=sanitize_text(payload.author_name, max_length=80) or "Client",
        timestamp_seconds=round(payload.timestamp_seconds, 3),
        body_text=sanitize_text(payload.body_text, max_length=2000),
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return comment


@router.post("/{review_token}/voice-comments", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("15/minute")
async def create_voice_comment(
    request: Request,
    review_token: str,
    author_name: str = Form(..., min_length=1, max_length=80),
    timestamp_seconds: float = Form(..., ge=0.0),
    transcript_mode: str = Form("hinglish"),
    audio: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    storage: StorageBackend = Depends(get_storage),
) -> Comment:
    link, project = await _verify_review_link(review_token, db)

    data = await audio.read()
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty audio file.")
    if len(data) > settings.MAX_VOICE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Voice note exceeds maximum allowed size.",
        )

    detected_mime = sniff_media_magic_bytes(data[:32], media_kind="audio")
    if not detected_mime:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or spoofed audio file signature.",
        )

    ext = AUDIO_EXT_MAP.get(detected_mime, ".webm")
    voice_key = f"voice_{uuid.uuid4().hex}{ext}"
    storage.write_bytes(voice_key, data)
    voice_path = storage.get_local_path(voice_key)

    transcript, checklist_item = transcribe_voice_note(
        voice_path,
        timestamp_seconds,
        mode=transcript_mode,
    )

    comment = Comment(
        project_id=project.id,
        review_link_id=link.id,
        author_name=sanitize_text(author_name, max_length=80) or "Client",
        timestamp_seconds=round(timestamp_seconds, 3),
        voice_storage_key=voice_key,
        voice_transcript=transcript,
        ai_checklist_item=checklist_item,
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return comment


@router.get("/{review_token}/comments/{comment_id}/audio")
async def stream_voice_note(
    review_token: str,
    comment_id: str,
    db: AsyncSession = Depends(get_db),
    storage: StorageBackend = Depends(get_storage),
) -> FileResponse:
    _, project = await _verify_review_link(review_token, db)
    res = await db.execute(
        select(Comment).where(Comment.id == comment_id, Comment.project_id == project.id)
    )
    comment = res.scalar_one_or_none()
    if not comment or not comment.voice_storage_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Voice note not found.")

    try:
        voice_path = storage.get_local_path(comment.voice_storage_key)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio file not found.") from exc

    return FileResponse(path=voice_path, media_type="audio/webm")


@router.patch("/{review_token}/comments/{comment_id}/resolve", response_model=CommentResponse)
async def toggle_resolve_comment(
    review_token: str,
    comment_id: str,
    db: AsyncSession = Depends(get_db),
) -> Comment:
    _, project = await _verify_review_link(review_token, db)
    res = await db.execute(
        select(Comment).where(Comment.id == comment_id, Comment.project_id == project.id)
    )
    comment = res.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found.")

    comment.is_resolved = not comment.is_resolved
    await db.commit()
    await db.refresh(comment)
    return comment


@router.delete("/{review_token}/comments/{comment_id}", status_code=status.HTTP_200_OK)
async def delete_comment(
    review_token: str,
    comment_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    _, project = await _verify_review_link(review_token, db)
    res = await db.execute(
        select(Comment).where(Comment.id == comment_id, Comment.project_id == project.id)
    )
    comment = res.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found.")

    await db.delete(comment)
    await db.commit()
    return {"status": "deleted"}