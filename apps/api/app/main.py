from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.middleware.gzip import GZipMiddleware

from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.http import close_http_client, get_http_client
from app.core.logging import setup_logging
from app.db.session import close_db
from app.routers import campaign, chat, documents, health, images, ontology

settings = get_settings()

def get_client_ip(request: Request) -> str:
    """Extract client IP respecting Cloudflare and reverse-proxy headers with fallback."""
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip and cf_ip.strip():
        return cf_ip.strip()
    x_forwarded = request.headers.get("X-Forwarded-For")
    if x_forwarded and x_forwarded.strip():
        return x_forwarded.split(",")[0].strip()
    return get_remote_address(request)


# Initialize IP-based rate limiter with reverse-proxy support
limiter = Limiter(
    key_func=get_client_ip,
    default_limits=[f"{settings.RATE_LIMIT_PER_MINUTE}/minute"],
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds standard security headers to all responses."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if settings.ENVIRONMENT == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for startup and shutdown routines."""
    setup_logging()
    get_http_client()
    yield
    await close_http_client()
    await close_db()


def create_app() -> FastAPI:
    """FastAPI application factory."""
    app = FastAPI(
        title="BrandMuse API",
        version="0.1.0",
        description="FastAPI Backend for BrandMuse - AI Brand Assistant for Creative Teams",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Attach rate limiter state and exception handler
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

    # Central error handlers
    register_exception_handlers(app)

    # Security headers
    app.add_middleware(SecurityHeadersMiddleware)

    # GZip compression for JSON payloads > 1KB
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["X-Session-Id", "Content-Type", "Authorization", "Accept"],
    )

    # Register routers
    app.include_router(health.router)
    app.include_router(documents.router)
    app.include_router(chat.router)
    app.include_router(campaign.router)
    app.include_router(images.router)
    app.include_router(ontology.router)

    return app


app = create_app()
