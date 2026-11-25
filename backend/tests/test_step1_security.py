import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import (
    sanitize_display_filename,
    sanitize_text,
    sign_review_token,
    sniff_media_magic_bytes,
    verify_review_signature,
)
from app.main import app


@pytest.mark.asyncio
async def test_security_headers_and_cors_block():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/health")
        assert res.status_code == 200
        assert res.headers["x-content-type-options"] == "nosniff"
        assert res.headers["x-frame-options"] == "DENY"
        assert "frame-ancestors 'none'" in res.headers["content-security-policy"]

        csrf_res = await client.post(
            "/health", headers={"Origin": "https://evil-clone.example"}
        )
        assert csrf_res.status_code == 403


@pytest.mark.asyncio
async def test_oversized_payload_rejected_with_413():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/health",
            content=b"x" * (1024 * 1024 + 64),
            headers={"Content-Type": "application/json"},
        )
        assert res.status_code == 413


def test_magic_bytes_rejects_spoofed_script_and_accepts_valid_mp4():
    fake_mp4 = b"#!/bin/bash\nrm -rf /\n"
    assert sniff_media_magic_bytes(fake_mp4, "video") is None

    valid_mp4_header = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00"
    assert sniff_media_magic_bytes(valid_mp4_header, "video") == "video/mp4"


def test_xss_sanitization_and_path_traversal_defense():
    dirty = '<script>alert("xss")</script>Reduce music at 00:14'
    assert sanitize_text(dirty) == "Reduce music at 00:14"

    traversal = "../../etc/passwd;rm -rf.mp4"
    safe_name = sanitize_display_filename(traversal)
    assert "/" not in safe_name
    assert "\\" not in safe_name
    assert ".." not in safe_name


def test_hmac_review_token_tamper_detection():
    sig = sign_review_token("tok-123", "proj-456", 1900000000)
    assert verify_review_signature("tok-123", "proj-456", 1900000000, sig) is True
    assert verify_review_signature("tok-123", "proj-999", 1900000000, sig) is False
    assert verify_review_signature("tok-123", "proj-456", 1900000001, sig) is False