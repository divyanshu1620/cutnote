import re
from pydantic import BaseModel, EmailStr, Field, field_validator

BLOCKED_EMAIL_DOMAINS = {
    "example.com",
    "test.com",
    "fake.com",
    "invalid.com",
    "mailinator.com",
    "tempmail.com",
    "10minutemail.com",
    "guerrillamail.com",
    "sharklasers.com",
    "yopmail.com",
}


def validate_real_email(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().lower()
    if not cleaned:
        return None
    if "@" not in cleaned or "." not in cleaned.split("@", 1)[1]:
        raise ValueError("Please enter a valid email address.")
    local_part, domain = cleaned.split("@", 1)
    if len(local_part) < 2 or local_part in {"test", "fake", "asdf", "abc", "user", "admin", "none", "null"}:
        raise ValueError("Please enter your real email address, not a placeholder.")
    if domain in BLOCKED_EMAIL_DOMAINS or domain.endswith(".test") or domain.endswith(".invalid") or domain.endswith(".local"):
        raise ValueError("Please enter a real email provider address (fake or disposable emails are not allowed).")
    if not re.match(r"^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$", cleaned):
        raise ValueError("Please enter a valid email address.")
    return cleaned


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(min_length=6, max_length=128)
    full_name: str = Field(min_length=2, max_length=100)
    recovery_email: EmailStr | str | None = None

    @field_validator("recovery_email", mode="before")
    @classmethod
    def check_recovery_email(cls, v):
        if v is None or v == "":
            return None
        return validate_real_email(str(v))


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=1, max_length=128)


class ForgotPasswordRequest(BaseModel):
    identifier: str = Field(min_length=3, max_length=255)


class ResetPasswordRequest(BaseModel):
    token_or_otp: str = Field(min_length=4, max_length=255)
    new_password: str = Field(min_length=6, max_length=128)


class UserResponse(BaseModel):
    id: str
    username: str
    full_name: str
    recovery_email: str | None = None

    model_config = {"from_attributes": True}
