import csv
import io
from collections.abc import Sequence

from app.db.models import Comment
from app.services.transcription import translate_to_english


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


def _original_text(comment: Comment) -> str:
    if comment.ai_checklist_item:
        return comment.ai_checklist_item.strip()
    if comment.voice_transcript:
        return comment.voice_transcript.strip()
    if comment.body_text:
        return comment.body_text.strip()
    return "Client feedback"


def _english_text(comment: Comment, original: str) -> str:
    current_display = (comment.voice_transcript or comment.body_text or original).strip()
    if current_display and current_display != original:
        return current_display
    return translate_to_english(original) or original


def generate_premiere_csv(comments: Sequence[Comment], fps: float = 24.0) -> str:
    """Generate a valid Adobe Premiere Pro marker CSV including Original and English."""
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        ["Marker Name", "Description", "Original", "English", "In", "Out", "Duration", "Marker Type"]
    )

    for idx, comment in enumerate(comments, start=1):
        tc = seconds_to_timecode(comment.timestamp_seconds, fps)
        original = _original_text(comment)
        english = _english_text(comment, original)
        combined_desc = f"EN: {english} | Original: {original}"
        marker_name = _csv_safe_cell(f"Note {idx} - {comment.author_name}")
        writer.writerow(
            [
                marker_name,
                _csv_safe_cell(combined_desc),
                _csv_safe_cell(original),
                _csv_safe_cell(english),
                tc,
                tc,
                "00:00:00:00",
                "Comment",
            ]
        )

    return output.getvalue()


def generate_resolve_edl(
    project_title: str, comments: Sequence[Comment], fps: float = 24.0
) -> str:
    """Generate a valid DaVinci Resolve CMX 3600 EDL marker file including Original and English."""
    safe_title = project_title.replace("\r", " ").replace("\n", " ").strip()[:64] or "CUTNOTE"
    lines = [
        f"TITLE: {safe_title}",
        "FCM: NON-DROP FRAME",
        "",
    ]

    for idx, comment in enumerate(comments, start=1):
        tc_in = seconds_to_timecode(comment.timestamp_seconds, fps)
        tc_out = seconds_to_timecode(comment.timestamp_seconds + (1.0 / max(fps, 1.0)), fps)
        original = _original_text(comment).replace("\r", " ").replace("\n", " ").replace("|", "-")
        english = _english_text(comment, original).replace("\r", " ").replace("\n", " ").replace("|", "-")
        author = comment.author_name.replace("|", "-")
        lines.append(f"{idx:03d}  001      V     C        {tc_in} {tc_out} {tc_in} {tc_out}")
        lines.append(f" |C:ResolveColorBlue |M:{author}: EN: {english} | Original: {original} |D:1")
        lines.append("")

    return "\n".join(lines)