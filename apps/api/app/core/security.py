import uuid

from fastapi import Header

from app.core.errors import APIError


def get_session_id(
    x_session_id: str | None = Header(
        default=None,
        alias="X-Session-Id",
        description="Client session identifier as UUID",
    ),
) -> uuid.UUID:
    """Validate and return the X-Session-Id header as a UUID."""
    if not x_session_id:
        raise APIError(
            code="MISSING_SESSION_ID",
            message="X-Session-Id header is required.",
            status_code=400,
        )

    try:
        return uuid.UUID(x_session_id)
    except ValueError as exc:
        raise APIError(
            code="INVALID_SESSION_ID",
            message="X-Session-Id header must be a valid UUID.",
            status_code=400,
        ) from exc


def get_optional_session_id(
    x_session_id: str | None = Header(
        default=None,
        alias="X-Session-Id",
        description="Optional client session identifier as UUID",
    ),
) -> uuid.UUID | None:
    """Validate and return the X-Session-Id header if present."""
    if not x_session_id:
        return None
    try:
        return uuid.UUID(x_session_id)
    except ValueError as exc:
        raise APIError(
            code="INVALID_SESSION_ID",
            message="X-Session-Id header must be a valid UUID.",
            status_code=400,
        ) from exc
