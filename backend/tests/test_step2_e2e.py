import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.v1 import projects as projects_module
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.services.ffmpeg import MediaMetadata
from app.services.storage import LocalDiskStorage, get_storage


@pytest_asyncio.fixture
async def test_env(tmp_path, monkeypatch):
    """Isolated SQLite DB + temp storage for clean, repeatable tests."""
    db_file = tmp_path / "test_cutnote.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db():
        async with session_factory() as session:
            yield session

    test_storage = LocalDiskStorage(tmp_path / "storage")

    # Mock ffprobe so tests pass identically whether ffprobe is installed or not
    monkeypatch.setattr(
        projects_module,
        "probe_media",
        lambda _: MediaMetadata(duration_seconds=60.0, fps=24.0),
    )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_storage] = lambda: test_storage

    yield

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_idor_and_unauthorized_access_blocked(test_env):
    transport = ASGITransport(app=app)

    # 1. Unauthenticated request must return 401
    async with AsyncClient(transport=transport, base_url="http://test") as anon:
        res = await anon.get("/api/v1/projects")
        assert res.status_code == 401

    # 2. User A registers and creates a project
    async with AsyncClient(transport=transport, base_url="http://test") as client_a:
        reg_a = await client_a.post(
            "/api/v1/auth/register",
            json={
                "email": "editor_a@cutnote.dev",
                "password": "StrongPassword123!",
                "full_name": "Editor A",
            },
        )
        assert reg_a.status_code == 201

        init_res = await client_a.post(
            "/api/v1/projects/uploads/init",
            json={
                "title": "Client Commercial Cut 1",
                "filename": "commercial.mp4",
                "expected_size_bytes": 1024,
            },
        )
        assert init_res.status_code == 201
        project_id = init_res.json()["project_id"]

    # 3. User B registers and tries to access/export User A's project -> must be 403 Forbidden
    async with AsyncClient(transport=transport, base_url="http://test") as client_b:
        reg_b = await client_b.post(
            "/api/v1/auth/register",
            json={
                "email": "editor_b@cutnote.dev",
                "password": "StrongPassword123!",
                "full_name": "Editor B",
            },
        )
        assert reg_b.status_code == 201

        idor_get = await client_b.get(f"/api/v1/projects/{project_id}")
        assert idor_get.status_code == 403

        idor_export = await client_b.get(f"/api/v1/projects/{project_id}/export/premiere-csv")
        assert idor_export.status_code == 403


@pytest.mark.asyncio
async def test_malicious_file_upload_rejected(test_env):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "sec@cutnote.dev",
                "password": "StrongPassword123!",
                "full_name": "Sec Tester",
            },
        )

        # Bad extension must be rejected at init
        bad_ext = await client.post(
            "/api/v1/projects/uploads/init",
            json={
                "title": "Evil",
                "filename": "malware.exe",
                "expected_size_bytes": 500,
            },
        )
        assert bad_ext.status_code == 400

        # Spoofed .mp4 containing shell script must be rejected by magic-byte check
        init_res = await client.post(
            "/api/v1/projects/uploads/init",
            json={
                "title": "Spoofed Video",
                "filename": "fake.mp4",
                "expected_size_bytes": 64,
            },
        )
        session_id = init_res.json()["session_id"]

        spoofed_chunk = await client.post(
            f"/api/v1/projects/uploads/{session_id}/chunk",
            files={"chunk": ("fake.mp4", b"#!/bin/bash\nwhoami\n", "video/mp4")},
        )
        assert spoofed_chunk.status_code == 400
        assert "signature" in spoofed_chunk.json()["detail"].lower()


@pytest.mark.asyncio
async def test_core_flow_upload_review_comment_and_marker_export(test_env):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as editor:
        # 1. Register editor
        reg = await editor.post(
            "/api/v1/auth/register",
            json={
                "email": "flow@cutnote.dev",
                "password": "StrongPassword123!",
                "full_name": "Main Editor",
            },
        )
        assert reg.status_code == 201

        # 2. Init + chunk upload (valid MP4 magic bytes) + complete
        valid_mp4 = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00" + b"\x00" * 128
        init_res = await editor.post(
            "/api/v1/projects/uploads/init",
            json={
                "title": "Brand Reel v1",
                "filename": "brand_reel.mp4",
                "expected_size_bytes": len(valid_mp4),
            },
        )
        session_id = init_res.json()["session_id"]
        project_id = init_res.json()["project_id"]

        chunk_res = await editor.post(
            f"/api/v1/projects/uploads/{session_id}/chunk",
            files={"chunk": ("brand_reel.mp4", valid_mp4, "video/mp4")},
        )
        assert chunk_res.status_code == 200

        complete_res = await editor.post(f"/api/v1/projects/uploads/{session_id}/complete")
        assert complete_res.status_code == 200
        assert complete_res.json()["status"] == "ready"

        # 3. Generate HMAC review link
        link_res = await editor.post(
            f"/api/v1/projects/{project_id}/review-links",
            json={"expires_in_hours": 48},
        )
        assert link_res.status_code == 201
        review_token = link_res.json()["review_token"]

        # 4. No-login client leaves timestamped comment (with XSS payload to verify sanitization)
        async with AsyncClient(transport=transport, base_url="http://test") as client_guest:
            comment_res = await client_guest.post(
                f"/api/v1/review/{review_token}/comments",
                json={
                    "author_name": "Client Rahul",
                    "timestamp_seconds": 14.5,
                    "body_text": "<script>alert(1)</script>Reduce background music",
                },
            )
            assert comment_res.status_code == 201
            assert comment_res.json()["body_text"] == "Reduce background music"

        # 5. Export Premiere Pro CSV & DaVinci Resolve EDL
        csv_res = await editor.get(f"/api/v1/projects/{project_id}/export/premiere-csv")
        assert csv_res.status_code == 200
        assert "Marker Name,Description,In,Out,Duration,Marker Type" in csv_res.text
        assert "Reduce background music" in csv_res.text
        assert "00:00:14:12" in csv_res.text  # 14.5s @ 24fps = 14s + 12 frames

        edl_res = await editor.get(f"/api/v1/projects/{project_id}/export/resolve-edl")
        assert edl_res.status_code == 200
        assert "TITLE: Brand Reel v1" in edl_res.text
        assert "Reduce background music" in edl_res.text