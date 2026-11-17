import uuid
from typing import Any, Literal

from langfuse import get_client
from langfuse.langchain import CallbackHandler
from langfuse.types import TraceContext

from app.core.config import get_settings
from app.core.logging import hash_session_id, slogger

settings = get_settings()


def is_langfuse_enabled() -> bool:
    """Check if Langfuse credentials are configured."""
    return bool(settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY)


def get_langfuse_callback(
    session_id: uuid.UUID,
    feature: str = "ask",
    trace_id: str | None = None,
    is_sample: bool = False,
    metadata: dict[str, Any] | None = None,
) -> CallbackHandler | None:
    """Create a Langfuse CallbackHandler with session hash, tags, and privacy enforcement."""
    if not is_langfuse_enabled():
        return None

    meta = metadata or {}
    meta["session_hash"] = hash_session_id(str(session_id))
    meta["feature"] = feature
    meta["is_sample"] = is_sample
    meta["privacy_mode"] = "full" if (is_sample or settings.TRACE_USER_CONTENT) else "metadata_only"

    trace_context = TraceContext(trace_id=trace_id) if trace_id else None

    handler = CallbackHandler(
        public_key=settings.LANGFUSE_PUBLIC_KEY,
        trace_context=trace_context,
    )

    return handler


def get_trace_url(trace_id: str | None) -> str | None:
    """Generate public trace link if LANGFUSE_PUBLIC_URL is configured."""
    if not trace_id or not settings.LANGFUSE_PUBLIC_URL:
        return None
    return f"{settings.LANGFUSE_PUBLIC_URL.rstrip('/')}/trace/{trace_id}"


def record_langfuse_event(
    name: str,
    session_id: uuid.UUID,
    metadata: dict[str, Any] | None = None,
    level: Literal["DEBUG", "DEFAULT", "WARNING", "ERROR"] = "DEFAULT",
) -> None:
    """Record a non-blocking Langfuse metadata event without exposing user content."""
    if not is_langfuse_enabled():
        return

    meta = dict(metadata or {})
    meta["session_hash"] = hash_session_id(str(session_id))
    meta["privacy_mode"] = "full" if settings.TRACE_USER_CONTENT else "metadata_only"

    try:
        client = get_client()
        client.create_event(name=name, metadata=meta, level=level)
    except Exception as exc:
        slogger.warning("langfuse_event_failed", event_name=name, error=str(exc))
