from contextlib import asynccontextmanager

from app.api.v1 import auth as auth_router
from app.api.v1 import projects as projects_router
from app.api.v1 import auth as auth_router
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.api.v1 import auth as auth_router
from app.api.v1 import exports as exports_router
from app.api.v1 import projects as projects_router
from app.api.v1 import review as review_router

from app.core.config import get_settings
from app.core.limiter import limiter
from app.db.base import Base
from app.db.session import engine
from app.middleware.security import (
    CSRFOriginMiddleware,
    PayloadSizeLimitMiddleware,
    SecurityHeadersMiddleware,
)

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.ENVIRONMENT == "development":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    docs_url="/docs" if settings.ENVIRONMENT == "development" else None,
    redoc_url=None,
    openapi_url="/openapi.json" if settings.ENVIRONMENT == "development" else None,
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-Requested-With"],
)
app.add_middleware(CSRFOriginMiddleware)
app.add_middleware(PayloadSizeLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, __: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})

app.include_router(auth_router.router, prefix="/api/v1")
app.include_router(projects_router.router, prefix="/api/v1")
app.include_router(review_router.router, prefix="/api/v1")
app.include_router(exports_router.router, prefix="/api/v1")
@app.get("/health", tags=["system"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}