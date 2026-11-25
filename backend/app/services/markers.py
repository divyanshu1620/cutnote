import csv
import io
from collections.abc import Sequence

from app.db.models import Comment


def seconds_to_timecode(seconds: float, fps: float = 24.0) -> str:
    """Convert float seconds into SMPTE HH:MM:SS:FF timecode."""
    safe_fps = fps if fps and fps > 0 else 24.0
    total_frames = max(0, int(round(seconds * safe_fps)))
    int_fps = max(1, int(round(safe_fps)))

    frames = total_frames % int_fps
    total_seconds = total_frames // int_fps
    secs = total_seconds % 60
    mins = (total_seconds // 60) % 60
    hours = total_seconds // 3600
    return f"{hours:02d}:{mins:02d}:{secs:02d}:{frames:02d}"


def _csv_safe_cell(value: str) -> str:
    """Neutralize CSV formula injection (=, +, -, @) for Excel/NLE safety."""
    cleaned = value.replace("\r", " ").replace("\n", " ").strip()
    if cleaned and cleaned[0] in ("=", "+", "-", "@"):
        return f"'{cleaned}"
    return cleaned


def _comment_label(comment: Comment) -> str:
    if comment.ai_checklist_item:
        return comment.ai_checklist_item
    if comment.body_text:
        return comment.body_text
    if comment.voice_transcript:
        return comment.voice_transcript
    return "Client feedback"


def generate_premiere_csv(comments: Sequence[Comment], fps: float = 24.0) -> str:
    """Generate a valid Adobe Premiere Pro tab/comma-separated marker CSV."""
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["Marker Name", "Description", "In", "Out", "Duration", "Marker Type"])

    for idx, comment in enumerate(comments, start=1):
        tc = seconds_to_timecode(comment.timestamp_seconds, fps)
        marker_name = _csv_safe_cell(f"Note {idx} - {comment.author_name}")
        description = _csv_safe_cell(_comment_label(comment))
        writer.writerow([marker_name, description, tc, tc, "00:00:00:00", "Comment"])

    return output.getvalue()


def generate_resolve_edl(
    project_title: str, comments: Sequence[Comment], fps: float = 24.0
) -> str:
    """Generate a valid DaVinci Resolve CMX 3600 EDL marker file."""
    safe_title = project_title.replace("\r", " ").replace("\n", " ").strip()[:64] or "CUTNOTE"
    lines = [
        f"TITLE: {safe_title}",
        "FCM: NON-DROP FRAME",
        "",
    ]

    for idx, comment in enumerate(comments, start=1):
        tc_in = seconds_to_timecode(comment.timestamp_seconds, fps)
        tc_out = seconds_to_timecode(comment.timestamp_seconds + (1.0 / max(fps, 1.0)), fps)
        note = _comment_label(comment).replace("\r", " ").replace("\n", " ").replace("|", "-")
        author = comment.author_name.replace("|", "-")
        lines.append(f"{idx:03d}  001      V     C        {tc_in} {tc_out} {tc_in} {tc_out}")
        lines.append(f" |C:ResolveColorBlue |M:{author}: {note} |D:1")
        lines.append("")

    return "\n".join(lines)