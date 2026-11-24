from collections.abc import Callable
from typing import Any, cast

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings

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


# Shared IP-based rate limiter with reverse-proxy support
limiter = Limiter(
    key_func=get_client_ip,
    default_limits=[f"{settings.RATE_LIMIT_PER_MINUTE}/minute"],
)


def exempt_rate_limit[F: Callable[..., Any]](func: F) -> F:
    """Typed wrapper around slowapi's untyped `limiter.exempt` decorator."""
    return cast(F, limiter.exempt(func))  # type: ignore[no-untyped-call]
