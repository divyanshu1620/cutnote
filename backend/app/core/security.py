import hashlib
import hmac
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
import nh3
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.core.config import get_settings

settings = get_settings()
_password_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)


def hash_password(plain_password: str) -> str:
    return _password_hasher.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return _password_hasher.verify(hashed_password, plain_password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def create_access_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": user_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)).timestamp()),
        "type": "access",
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["sub", "exp", "iat"]},
        )
        if payload.get("type") != "access":
            return None
        return str(payload["sub"])
    except jwt.PyJWTError:
        return None


def sign_review_token(token_id: str, project_id: str, expires_at_ts: int) -> str:
    message = f"{token_id}:{project_id}:{expires_at_ts}".encode("utf-8")
    return hmac.new(
        settings.REVIEW_HMAC_SECRET.encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()


def verify_review_signature(
    token_id: str, project_id: str, expires_at_ts: int, provided_sig: str
) -> bool:
    expected = sign_review_token(token_id, project_id, expires_at_ts)
    return hmac.compare_digest(expected, provided_sig)


def sanitize_text(raw: str, max_length: int = 2000) -> str:
    cleaned = nh3.clean(raw, tags=set())
    cleaned = cleaned.strip()
    return cleaned[:max_length]


def sanitize_display_filename(filename: str) -> str:
    base = filename.replace("\\", "/").split("/")[-1]
    safe = re.sub(r"[^A-Za-z0-9._ -]", "_", base).strip()
    return (safe or "untitled_video")[:180]


def sniff_media_magic_bytes(header: bytes, media_kind: str) -> str | None:
    if len(header) < 12:
        return None

    if media_kind == "video":
        if header[4:8] == b"ftyp":
            brand = header[8:12]
            if brand == b"qt  ":
                return "video/quicktime"
            return "video/mp4"
        if header.startswith(b"\x1a\x45\xdf\xa3"):
            return "video/webm"
        return None

    if media_kind == "audio":
        if header.startswith(b"\x1a\x45\xdf\xa3"):
            return "audio/webm"
        if header.startswith(b"OggS"):
            return "audio/ogg"
        if header.startswith(b"RIFF") and header[8:12] == b"WAVE":
            return "audio/wav"
        if header.startswith((b"ID3", b"\xff\xfb", b"\xff\xf3", b"\xff\xf2")):
            return "audio/mpeg"
        if header[4:8] == b"ftyp":
            return "audio/mp4"
        return None

    return None