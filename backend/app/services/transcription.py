import os
from pathlib import Path

import httpx

from app.core.security import sanitize_text

GROQ_TRANSCRIBE_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_CHAT_MODEL = "llama-3.3-70b-versatile"


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


def _to_hinglish_latin(text: str) -> str:
    """
    Converts spoken Hindi/Hinglish text into clean Romanized Hinglish
    written strictly in English (Latin) letters (e.g. 'bhai yahan cut lagao').
    """
    cleaned = sanitize_text(text, max_length=1000).strip()
    if not cleaned:
        return ""

    api_key = _get_groq_api_key()
    if not api_key:
        print("[Hinglish Error]: GROQ_API_KEY is missing", flush=True)
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
                "temperature": 0.0,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Convert the input text into natural Hinglish written ONLY in English (Latin) letters. "
                            "Keep Hindi words as Hindi spelled in English letters (for example: 'yahan cut lagao', "
                            "'audio thoda kam karo', 'ye part trim kar do'). "
                            "Do NOT output Devanagari, Arabic, Urdu, or any non-Latin script. "
                            "Do NOT translate into a full English sentence; preserve the spoken Hindi/Hinglish phrasing. "
                            "Return ONLY the final Hinglish string."
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
                f"[Hinglish Error]: Groq HTTP {response.status_code} -> {response.text}",
                flush=True,
            )
            return cleaned

        data = response.json()
        choices = data.get("choices") or []
        content = ""
        if choices:
            content = str((choices[0].get("message") or {}).get("content", ""))
        result = sanitize_text(content.strip().strip('"'), max_length=1000)
        return result or cleaned
    except Exception as exc:
        print(f"[Hinglish Error]: {type(exc).__name__}: {exc}", flush=True)
        return cleaned


def transcribe_voice_note(file_path: Path, timestamp_seconds: float) -> tuple[str, str]:
    """
    Transcribes voice note via Groq Whisper (language='hi') and returns
    clean Romanized Hinglish (English letters) as (transcript, original_backup).
    """
    api_key = _get_groq_api_key()
    if not api_key:
        print("[Transcription Error]: GROQ_API_KEY is missing", flush=True)
        return "", ""

    try:
        with open(file_path, "rb") as audio_file:
            response = httpx.post(
                GROQ_TRANSCRIBE_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                data={
                    "model": "whisper-large-v3-turbo",
                    "language": "hi",
                    "response_format": "json",
                    "prompt": "Hinglish video editing feedback: haan bhai yahan cut lagao, audio kam karo, clip trim karo.",
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
            hinglish_text = _to_hinglish_latin(raw_text)
            return hinglish_text, hinglish_text
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
