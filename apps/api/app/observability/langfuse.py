import uuid
from typing import Any, Literal

from langchain_core.runnables import RunnableConfig

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
) -> Any | None:
    """Create a Langfuse CallbackHandler lazily with trace context."""
    _ = (session_id, feature, is_sample, metadata)
    if not is_langfuse_enabled():
        return None

    from langfuse.langchain import CallbackHandler
    from langfuse.types import TraceContext

    trace_context = TraceContext(trace_id=trace_id) if trace_id else None
    return CallbackHandler(
        public_key=settings.LANGFUSE_PUBLIC_KEY,
        trace_context=trace_context,
    )


def get_langfuse_runnable_config(
    session_id: uuid.UUID,
    feature: str = "ask",
    trace_id: str | None = None,
    is_sample: bool = False,
    metadata: dict[str, Any] | None = None,
) -> RunnableConfig:
    """Build LangChain RunnableConfig with Langfuse callback and trace metadata attached."""
    session_hash = hash_session_id(str(session_id))
    meta: dict[str, Any] = dict(metadata or {})
    meta["session_hash"] = session_hash
    meta["langfuse_session_id"] = session_hash
    meta["feature"] = feature
    meta["is_sample"] = is_sample
    meta["privacy_mode"] = "full" if (is_sample or settings.TRACE_USER_CONTENT) else "metadata_only"

    handler = get_langfuse_callback(
        session_id=session_id,
        feature=feature,
        trace_id=trace_id,
        is_sample=is_sample,
        metadata=meta,
    )
    if not handler:
        return RunnableConfig(callbacks=[], metadata=meta)
    return RunnableConfig(callbacks=[handler], metadata=meta)


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
        from langfuse import get_client

        client = get_client()
        client.create_event(name=name, metadata=meta, level=level)
    except Exception as exc:
        slogger.warning("langfuse_event_failed", event_name=name, error=str(exc))
