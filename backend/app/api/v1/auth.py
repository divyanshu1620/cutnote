import hashlib
import os
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.security import create_access_token, hash_password, verify_password
from app.db.models import User
from app.db.session import get_db
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()

# In-memory short-lived reset store (keyed by sha256(token_or_otp))
_RESET_TOKENS: dict[str, dict] = {}


class ForgotPasswordResponse(BaseModel):
    message: str
    delivery_mode: str


def _send_reset_email(to_email: str, username: str, otp_code: str, reset_link: str) -> bool:
    smtp_host = os.getenv("SMTP_HOST", "").strip()
    smtp_port = int(os.getenv("SMTP_PORT", "587").strip() or "587")
    smtp_user = os.getenv("SMTP_USER", "").strip()
    smtp_pass = os.getenv("SMTP_PASS", "").strip()
    smtp_from = os.getenv("SMTP_FROM", smtp_user).strip()

    if not smtp_host or not smtp_user or not smtp_pass or not smtp_from:
        return False

    msg = EmailMessage()
    msg["Subject"] = "CutNote Password Reset Code & Link"
    msg["From"] = smtp_from
    msg["To"] = to_email
    msg.set_content(
        f"Hi {username},\n\n"
        f"Your CutNote password reset OTP is: {otp_code}\n"
        f"Or open this reset link: {reset_link}\n\n"
        f"This code/link expires in 15 minutes. If you did not request this, ignore this email."
    )

    with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
    return True


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> User:
    normalized_username = payload.username.strip().lower()
    normalized_email = payload.recovery_email.strip().lower() if payload.recovery_email else None

    existing_user = await db.scalar(
        select(User).where(func.lower(User.username) == normalized_username)
    )
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That username is already taken. Choose another one.",
        )

    if normalized_email:
        existing_email = await db.scalar(
            select(User).where(func.lower(User.recovery_email) == normalized_email)
        )
        if existing_email is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This recovery email is already linked to another account.",
            )

    user = User(
        username=normalized_username,
        full_name=payload.full_name.strip(),
        recovery_email=normalized_email,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(str(user.id))
    response.set_cookie(
        key=settings.COOKIE_NAME,
        value=token,
        httponly=True,
        samesite=settings.COOKIE_SAMESITE,
        secure=settings.cookie_secure,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    return user


@router.post("/login", response_model=UserResponse)
async def login(
    payload: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> User:
    normalized_username = payload.username.strip().lower()
    user = await db.scalar(
        select(User).where(func.lower(User.username) == normalized_username)
    )
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    token = create_access_token(str(user.id))
    response.set_cookie(
        key=settings.COOKIE_NAME,
        value=token,
        httponly=True,
        samesite=settings.COOKIE_SAMESITE,
        secure=settings.cookie_secure,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    return user


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
async def forgot_password(
    payload: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> ForgotPasswordResponse:
    ident = payload.identifier.strip().lower()
    user = await db.scalar(
        select(User).where(
            or_(
                func.lower(User.username) == ident,
                func.lower(User.recovery_email) == ident,
            )
        )
    )
    if user is None or not user.recovery_email:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No account with a linked recovery email matched that username or email.",
        )

    otp_code = f"{secrets.randbelow(900000) + 100000}"
    reset_token = secrets.token_urlsafe(24)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

    for code_val in (otp_code, reset_token):
        digest = hashlib.sha256(code_val.encode("utf-8")).hexdigest()
        _RESET_TOKENS[digest] = {
            "user_id": str(user.id),
            "expires_at": expires_at,
        }

    frontend_base = os.getenv("FRONTEND_URL", "https://cutnote-three.vercel.app").rstrip("/")
    reset_link = f"{frontend_base}/login?reset_token={reset_token}"

    sent = _send_reset_email(user.recovery_email, user.username, otp_code, reset_link)
    if not sent:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email service (SMTP_HOST/SMTP_USER/SMTP_PASS) is not configured on the server yet.",
        )

    return ForgotPasswordResponse(
        message=f"Reset link and 6-digit OTP sent to {user.recovery_email}. Valid for 15 minutes.",
        delivery_mode="email",
    )


@router.post("/reset-password", response_model=UserResponse)
async def reset_password(
    payload: ResetPasswordRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> User:
    code_clean = payload.token_or_otp.strip()
    digest = hashlib.sha256(code_clean.encode("utf-8")).hexdigest()
    entry = _RESET_TOKENS.get(digest)

    now = datetime.now(timezone.utc)
    if not entry or entry["expires_at"] <= now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP/reset link.",
        )

    user = await db.scalar(select(User).where(User.id == entry["user_id"]))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    user.hashed_password = hash_password(payload.new_password)
    _RESET_TOKENS.pop(digest, None)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(str(user.id))
    response.set_cookie(
        key=settings.COOKIE_NAME,
        value=token,
        httponly=True,
        samesite=settings.COOKIE_SAMESITE,
        secure=settings.cookie_secure,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> None:
    response.delete_cookie(key=settings.COOKIE_NAME, path="/")


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
