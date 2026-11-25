import os
import re
from pathlib import Path

import httpx

from app.core.security import sanitize_text

GROQ_TRANSCRIBE_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_CHAT_MODEL = "llama-3.3-70b-versatile"

_DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")

_DEVANAGARI_MAP: dict[str, str] = {
    "अ": "a",
    "आ": "aa",
    "इ": "i",
    "ई": "ee",
    "उ": "u",
    "ऊ": "oo",
    "ऋ": "ri",
    "ए": "e",
    "ऐ": "ai",
    "ओ": "o",
    "औ": "au",
    "क": "ka",
    "ख": "kha",
    "ग": "ga",
    "घ": "gha",
    "ङ": "nga",
    "च": "cha",
    "छ": "chha",
    "ज": "ja",
    "झ": "jha",
    "ञ": "nya",
    "ट": "ta",
    "ठ": "tha",
    "ड": "da",
    "ढ": "dha",
    "ण": "na",
    "त": "ta",
    "थ": "tha",
    "द": "da",
    "ध": "dha",
    "न": "na",
    "प": "pa",
    "फ": "pha",
    "ब": "ba",
    "भ": "bha",
    "म": "ma",
    "य": "ya",
    "र": "ra",
    "ल": "la",
    "व": "va",
    "श": "sha",
    "ष": "shha",
    "स": "sa",
    "ह": "ha",
    "ा": "aa",
    "ि": "i",
    "ी": "ee",
    "ु": "u",
    "ू": "oo",
    "ृ": "ri",
    "े": "e",
    "ै": "ai",
    "ो": "o",
    "ौ": "au",
    "ं": "n",
    "ः": "h",
    "ँ": "n",
    "्": "",
    "।": ".",
    "॥": ".",
    "०": "0",
    "१": "1",
    "२": "2",
    "३": "3",
    "४": "4",
    "५": "5",
    "६": "6",
    "७": "7",
    "८": "8",
    "९": "9",
}


def _transliterate_devanagari_fallback(text: str) -> str:
    if not _DEVANAGARI_RE.search(text):
        return text
    out: list[str] = []
    for ch in text:
        if ch in _DEVANAGARI_MAP:
            out.append(_DEVANAGARI_MAP[ch])
        else:
            out.append(ch)
    cleaned = re.sub(r"\s+", " ", "".join(out)).strip()
    return cleaned


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
        print("[Roman Script Error]: GROQ_API_KEY missing, using fallback", flush=True)
        return _transliterate_devanagari_fallback(cleaned)

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
            return _transliterate_devanagari_fallback(cleaned)

        data = response.json()
        choices = data.get("choices") or []
        content = ""
        if choices:
            content = str((choices[0].get("message") or {}).get("content", ""))
        converted = sanitize_text(content.strip().strip('"'), max_length=1000)
        if _DEVANAGARI_RE.search(converted):
            converted = _transliterate_devanagari_fallback(converted)
        return converted or _transliterate_devanagari_fallback(cleaned)
    except Exception as exc:
        print(f"[Roman Script Error]: {type(exc).__name__}: {exc}", flush=True)
        return _transliterate_devanagari_fallback(cleaned)


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
        return _transliterate_devanagari_fallback(cleaned)

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
            return _transliterate_devanagari_fallback(cleaned)

        data = response.json()
        choices = data.get("choices") or []
        content = ""
        if choices:
            content = str((choices[0].get("message") or {}).get("content", ""))
        translated = sanitize_text(content.strip().strip('"'), max_length=1000)
        return translated or _transliterate_devanagari_fallback(cleaned)
    except Exception as exc:
        print(f"[Translate Error]: {type(exc).__name__}: {exc}", flush=True)
        return _transliterate_devanagari_fallback(cleaned)