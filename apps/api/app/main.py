from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.middleware import SlowAPIASGIMiddleware
from slowapi.util import get_remote_address
from starlette.middleware.gzip import GZipMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.http import close_http_client, get_http_client
from app.core.logging import setup_logging
from app.db.session import close_db
from app.routers import admin, campaign, chat, documents, health, images, ontology

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


class SecurityHeadersMiddleware:
    """Pure ASGI middleware that injects standard security headers without response buffering."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        base_headers: list[tuple[bytes, bytes]] = [
            (b"x-content-type-options", b"nosniff"),
            (b"x-frame-options", b"DENY"),
            (b"referrer-policy", b"strict-origin-when-cross-origin"),
            (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
        ]
        if settings.ENVIRONMENT == "production":
            base_headers.append(
                (b"strict-transport-security", b"max-age=31536000; includeSubDomains")
            )
        self._headers = tuple(base_headers)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_security_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                existing = {name.lower() for name, _ in headers}
                for name, value in self._headers:
                    if name not in existing:
                        headers.append((name, value))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_security_headers)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for startup and shutdown routines."""
    setup_logging()
    settings.validate_storage_environment()
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

    # Attach rate limiter state
    app.state.limiter = limiter

    # Central error handlers (including RateLimitExceeded)
    register_exception_handlers(app)

    # Pure ASGI IP rate limiting (respects RATE_LIMIT_PER_MINUTE default limit)
    app.add_middleware(SlowAPIASGIMiddleware)

    # Security headers (Pure ASGI, preserves Content-Length & SSE streaming)
    app.add_middleware(SecurityHeadersMiddleware)

    # GZip compression for payloads > 1KB (balanced CPU level 6)
    app.add_middleware(GZipMiddleware, minimum_size=1000, compresslevel=6)

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
    app.include_router(admin.router)

    return app


app = create_app()
