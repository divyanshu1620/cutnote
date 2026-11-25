from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_owned_project
from app.core.security import sanitize_display_filename
from app.db.models import Comment, Project
from app.db.session import get_db
from app.services.markers import generate_premiere_csv, generate_resolve_edl

router = APIRouter(prefix="/projects", tags=["exports"])


@router.get("/{project_id}/export/premiere-csv")
async def export_premiere_csv(
    project: Project = Depends(get_owned_project),
    db: AsyncSession = Depends(get_db),
) -> Response:
    result = await db.execute(
        select(Comment)
        .where(Comment.project_id == project.id)
        .order_by(Comment.timestamp_seconds.asc(), Comment.created_at.asc())
    )
    comments = list(result.scalars().all())
    csv_content = generate_premiere_csv(comments, fps=project.fps)
    safe_name = sanitize_display_filename(project.title).replace(" ", "_")

    return Response(
        content=csv_content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}_premiere_markers.csv"'},
    )


@router.get("/{project_id}/export/resolve-edl")
async def export_resolve_edl(
    project: Project = Depends(get_owned_project),
    db: AsyncSession = Depends(get_db),
) -> Response:
    result = await db.execute(
        select(Comment)
        .where(Comment.project_id == project.id)
        .order_by(Comment.timestamp_seconds.asc(), Comment.created_at.asc())
    )
    comments = list(result.scalars().all())
    edl_content = generate_resolve_edl(project.title, comments, fps=project.fps)
    safe_name = sanitize_display_filename(project.title).replace(" ", "_")

    return Response(
        content=edl_content,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}_resolve_markers.edl"'},
    )