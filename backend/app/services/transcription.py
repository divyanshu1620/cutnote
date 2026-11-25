import os
from pathlib import Path

import httpx

from app.core.security import sanitize_text

GROQ_TRANSCRIBE_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_CHAT_MODEL = "openai/gpt-oss-120b"


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


def _to_roman_script(text: str) -> str:
    """
    Converts text into English/Latin letters (Roman script) while keeping
    the spoken language/words (e.g. 'haan', 'bhai cut yahan se karo').
    """
    cleaned = sanitize_text(text, max_length=1000).strip()
    if not cleaned:
        return ""

    api_key = _get_groq_api_key()
    if not api_key:
        print("[Roman Script Error]: GROQ_API_KEY is missing", flush=True)
        return cleaned

    try:
        response = httpx.post(
            GROQ_CHAT_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": GROQ_CHAT_MODEL,
                "temperature": 0.1,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Convert the given text into English/Latin alphabet (Roman script) ONLY. "
                            "Do not translate into another language and do not use Devanagari or non-Latin scripts. "
                            "Write spoken Hindi/Hinglish words using English letters (for example 'haan', 'nahi', "
                            "'yahan thodi dikkat aa rakhi hai'). Keep English words as English. "
                            "Return ONLY the converted text with no quotes or notes."
                        ),
                    },
                    {
                        "role": "user",
                        "content": cleaned,
                    },
                ],
            },
            timeout=20.0,
        )
        if response.status_code >= 400:
            print(
                f"[Roman Script Error]: Groq HTTP {response.status_code} -> {response.text}",
                flush=True,
            )
            return cleaned

        data = response.json()
        choices = data.get("choices") or []
        content = ""
        if choices:
            content = str((choices[0].get("message") or {}).get("content", ""))
        converted = sanitize_text(content.strip().strip('"'), max_length=1000)
        return converted or cleaned
    except Exception as exc:
        print(f"[Roman Script Error]: {type(exc).__name__}: {exc}", flush=True)
        return cleaned


def transcribe_voice_note(file_path: Path, timestamp_seconds: float) -> tuple[str, str]:
    """
    Transcribes a voice note using Groq Whisper and normalizes default transcript
    into English/Latin letters (Roman script).
    Returns (roman_transcript, original_roman_backup).
    """
    api_key = _get_groq_api_key()
    if not api_key:
        print("[Transcription Error]: GROQ_API_KEY is missing in environment and .env", flush=True)
        return "", ""

    try:
        with open(file_path, "rb") as audio_file:
            response = httpx.post(
                GROQ_TRANSCRIBE_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                data={
                    "model": "whisper-large-v3-turbo",
                    "response_format": "json",
                    "prompt": (
                        "Video editing feedback in Hindi, Hinglish, or English. "
                        "Examples: haan bhai yahan cut lagao, audio kam karo, transition smooth rakho."
                    ),
                },
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
            raw_text = sanitize_text(str(data.get("text", "")), max_length=1000)
            roman_text = _to_roman_script(raw_text)
            return roman_text, roman_text
    except Exception as exc:
        print(f"[Transcription Error]: {type(exc).__name__}: {exc}", flush=True)
        return "", ""


def translate_to_english(source_text: str) -> str:
    """Translates feedback/transcript text into clear, natural English."""
    cleaned = sanitize_text(source_text, max_length=1000).strip()
    if not cleaned:
        return ""

    api_key = _get_groq_api_key()
    if not api_key:
        print("[Translate Error]: GROQ_API_KEY is missing", flush=True)
        return cleaned

    try:
        response = httpx.post(
            GROQ_CHAT_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": GROQ_CHAT_MODEL,
                "temperature": 0.2,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Translate the given video editing feedback or transcript into clear, natural English. "
                            "Preserve the exact meaning. Return ONLY the English translation with no quotes "
                            "or extra explanation."
                        ),
                    },
                    {
                        "role": "user",
                        "content": cleaned,
                    },
                ],
            },
            timeout=20.0,
        )
        if response.status_code >= 400:
            print(
                f"[Translate Error]: Groq HTTP {response.status_code} -> {response.text}",
                flush=True,
            )
            return cleaned

        data = response.json()
        choices = data.get("choices") or []
        content = ""
        if choices:
            content = str((choices[0].get("message") or {}).get("content", ""))
        translated = sanitize_text(content.strip().strip('"'), max_length=1000)
        return translated or cleaned
    except Exception as exc:
        print(f"[Translate Error]: {type(exc).__name__}: {exc}", flush=True)
        return cleaned