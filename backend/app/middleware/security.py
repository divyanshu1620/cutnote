from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import get_settings

settings = get_settings()

STATE_CHANGING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
UPLOAD_PATH_PREFIXES = ("/api/v1/projects/uploads", "/api/v1/review/")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), geolocation=(), microphone=(self)"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "media-src 'self' blob:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self';"
        )
        if settings.ENVIRONMENT == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains; preload"
            )
        return response


class PayloadSizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                size = int(content_length)
            except ValueError:
                return JSONResponse(
                    status_code=400, content={"detail": "Invalid Content-Length header."}
                )

            is_upload_route = request.url.path.startswith(UPLOAD_PATH_PREFIXES)
            limit = (
                settings.MAX_CHUNK_SIZE_BYTES
                if is_upload_route
                else settings.MAX_JSON_BODY_BYTES
            )
            if size > limit:
                return JSONResponse(
                    status_code=413,
                    content={"detail": "Payload exceeds maximum allowed size."},
                )
        return await call_next(request)


class CSRFOriginMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method in STATE_CHANGING_METHODS:
            origin = request.headers.get("origin")
            if origin and origin not in settings.ALLOWED_ORIGINS:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Cross-origin request blocked."},
                )
        return await call_next(request)