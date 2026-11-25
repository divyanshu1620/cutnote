import os
import re
import unicodedata
from pathlib import Path

import httpx

from app.core.security import sanitize_text

GROQ_TRANSCRIBE_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_CHAT_MODELS = ["llama-3.1-8b-instant", "openai/gpt-oss-120b"]


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


def _has_non_latin(text: str) -> bool:
    for ch in text:
        if ch.isalpha():
            name = unicodedata.name(ch, "")
            if "LATIN" not in name:
                return True
    return False


def _call_groq_chat(api_key: str, system_prompt: str, user_text: str, temperature: float = 0.0) -> str:
    for model_name in GROQ_CHAT_MODELS:
        try:
            response = httpx.post(
                GROQ_CHAT_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model_name,
                    "temperature": temperature,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_text},
                    ],
                },
                timeout=20.0,
            )
            if response.status_code >= 400:
                print(
                    f"[Groq Chat Warning] model={model_name} status={response.status_code} body={response.text}",
                    flush=True,
                )
                continue

            data = response.json()
            choices = data.get("choices") or []
            if choices:
                raw_out = str((choices[0].get("message") or {}).get("content", "")).strip()
                raw_out = re.sub(r"<think>.*?</think>", "", raw_out, flags=re.DOTALL).strip()
                raw_out = raw_out.strip('"').strip("'").strip()
                if raw_out:
                    return sanitize_text(raw_out, max_length=1000)
        except Exception as exc:
            print(f"[Groq Chat Error] model={model_name}: {type(exc).__name__}: {exc}", flush=True)
            continue

    return ""


def _to_hinglish_latin(text: str) -> str:
    """
    Converts spoken Hindi/Hinglish text into Romanized Hinglish:
    Hindi words written ONLY in English (Latin) letters (e.g. 'kahan ja rahe ho').
    """
    cleaned = sanitize_text(text, max_length=1000).strip()
    if not cleaned:
        return ""

    api_key = _get_groq_api_key()
    if not api_key:
        print("[Hinglish Error]: GROQ_API_KEY is missing", flush=True)
        return cleaned

    system_prompt = (
        "You convert Hindi or Hinglish speech text into Hinglish written strictly in English (Latin) alphabet letters.\n"
        "Rules:\n"
        "1. Write every Hindi word using English letters (A-Z, a-z). Example: 'कहां जा रहे हो?' -> 'kahan ja rahe ho'.\n"
        "2. Do NOT translate Hindi into English meaning (do NOT turn 'kahan ja rahe ho' into 'where are you going'). Keep Hindi words as Hindi spelled in English letters.\n"
        "3. NEVER output Devanagari, Hindi script, Urdu/Arabic script, or any non-Latin letters.\n"
        "4. Return ONLY the final Hinglish text with no quotes, labels, or explanations."
    )

    converted = _call_groq_chat(api_key, system_prompt, cleaned, temperature=0.0)
    if converted and not _has_non_latin(converted):
        return converted

    # Second strict retry if non-Latin characters still remain
    retry_prompt = (
        "Rewrite the following text using ONLY basic English letters a-z, spaces, and basic punctuation (, . ? !). "
        "Keep Hindi words in Hinglish spelling like 'kahan ja rahe ho', 'yahan cut lagao'. "
        "Zero non-English script characters allowed. Output only the text."
    )
    retried = _call_groq_chat(api_key, retry_prompt, converted or cleaned, temperature=0.0)
    if retried:
        return retried

    return converted or cleaned


def transcribe_voice_note(file_path: Path, timestamp_seconds: float) -> tuple[str, str]:
    """
    Transcribes voice note via Groq Whisper and returns Romanized Hinglish
    (English letters, Hindi words) as (transcript, original_backup).
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
                    "prompt": "kahan ja rahe ho, yahan cut lagao, audio kam karo, ye clip trim kar do.",
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
    """Translates feedback/Hinglish/Hindi text into clear, natural English."""
    cleaned = sanitize_text(source_text, max_length=1000).strip()
    if not cleaned:
        return ""

    api_key = _get_groq_api_key()
    if not api_key:
        print("[Translate Error]: GROQ_API_KEY is missing", flush=True)
        return cleaned

    system_prompt = (
        "Translate the given Hindi or Hinglish video editing feedback into clear, natural English. "
        "Return ONLY the English translation with no quotes or extra explanation."
    )
    translated = _call_groq_chat(api_key, system_prompt, cleaned, temperature=0.2)
    return translated or cleaned
