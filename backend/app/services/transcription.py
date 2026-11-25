import os
from pathlib import Path

import httpx

from app.core.security import sanitize_text

GROQ_TRANSCRIBE_URL = "https://api.groq.com/openai/v1/audio/transcriptions"


def _get_groq_api_key() -> str:
    """Reads GROQ_API_KEY from environment or backend/.env file."""
    key = os.getenv("GROQ_API_KEY", "").strip()
    if key:
        return key

    env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("GROQ_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def transcribe_voice_note(file_path: Path, timestamp_seconds: float) -> tuple[str, str]:
    """
    Transcribes a voice note using Groq Whisper (Hindi/English).
    Returns empty strings silently if API key is missing or transcription fails.
    """
    api_key = _get_groq_api_key()
    if not api_key:
        return "", ""

    transcript = ""
    try:
        with open(file_path, "rb") as audio_file:
            response = httpx.post(
                GROQ_TRANSCRIBE_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                data={
                    "model": "whisper-large-v3-turbo",
                    "response_format": "json",
                },
                files={"file": (file_path.name, audio_file, "audio/webm")},
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            transcript = sanitize_text(str(data.get("text", "")), max_length=1000)
    except Exception as exc:
        print(f"[Transcription Error]: {exc}")
        return "", ""

    return transcript, ""