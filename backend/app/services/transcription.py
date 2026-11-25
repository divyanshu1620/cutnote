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


def transcribe_voice_note(
    file_path: Path,
    timestamp_seconds: float,
    mode: str = "hinglish",
) -> tuple[str, str]:
    """
    Transcribes a voice note using Groq Whisper.
    mode: 'hinglish' | 'english' | 'hindi'
    """
    api_key = _get_groq_api_key()
    if not api_key:
        print("[Transcription Error]: GROQ_API_KEY is missing in environment and .env", flush=True)
        return "", ""

    normalized_mode = (mode or "hinglish").strip().lower()
    form_data: dict[str, str] = {
        "model": "whisper-large-v3-turbo",
        "response_format": "json",
    }

    if normalized_mode == "english":
        form_data["language"] = "en"
    elif normalized_mode == "hindi":
        form_data["language"] = "hi"
        form_data["prompt"] = "यह वीडियो एडिटिंग फीडबैक है।"
    else:
        # Hinglish: Roman script bias with mixed Hindi-English video edit words
        form_data["prompt"] = (
            "Editor note in Hinglish: bhai is cut ko trim karo, background music kam karo, "
            "transition smooth rakho, pata nahi kya ho raha hai yahan."
        )

    transcript = ""
    try:
        with open(file_path, "rb") as audio_file:
            response = httpx.post(
                GROQ_TRANSCRIBE_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                data=form_data,
                files={"file": (file_path.name, audio_file, "audio/webm")},
                timeout=30.0,
            )
            if response.status_code >= 400:
                print(
                    f"[Transcription Error]: Groq HTTP {response.status_code} -> {response.text}",
                    flush=True,
                )
                return "", ""

            data = response.json()
            transcript = sanitize_text(str(data.get("text", "")), max_length=1000)
    except Exception as exc:
        print(f"[Transcription Error]: {type(exc).__name__}: {exc}", flush=True)
        return "", ""

    return transcript, ""