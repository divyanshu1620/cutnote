import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MediaMetadata:
    duration_seconds: float
    fps: float


def _parse_fps(rate_str: str | None) -> float:
    if not rate_str or rate_str == "0/0":
        return 24.0
    if "/" in rate_str:
        num, den = rate_str.split("/", 1)
        try:
            den_val = float(den)
            return round(float(num) / den_val, 3) if den_val > 0 else 24.0
        except ValueError:
            return 24.0
    try:
        return round(float(rate_str), 3)
    except ValueError:
        return 24.0


def probe_media(file_path: Path, timeout_seconds: int = 15) -> MediaMetadata:
    """
    Safely inspect video/audio duration and FPS via ffprobe.
    SECURITY: Strictly uses argument list with shell=False (zero command injection risk).
    If ffprobe is not installed in local dev, falls back cleanly to safe defaults.
    """
    ffprobe_bin = shutil.which("ffprobe")
    if not ffprobe_bin:
        return MediaMetadata(duration_seconds=0.0, fps=24.0)

    resolved_path = str(file_path.resolve())
    cmd = [
        ffprobe_bin,
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        resolved_path,
    ]

    result = subprocess.run(
        cmd,
        shell=False,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    if result.returncode != 0 or not result.stdout:
        raise ValueError("Unable to read media metadata. File may be corrupted.")

    data = json.loads(result.stdout)
    duration = float(data.get("format", {}).get("duration", 0.0) or 0.0)

    fps = 24.0
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video":
            fps = _parse_fps(stream.get("avg_frame_rate") or stream.get("r_frame_rate"))
            break

    return MediaMetadata(duration_seconds=round(duration, 3), fps=fps)