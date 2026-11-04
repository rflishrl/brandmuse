from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """Detailed error payload."""

    code: str = Field(
        ...,
        description="Machine-readable error code",
        examples=["INVALID_SESSION_ID"],
    )
    message: str = Field(
        ...,
        description="Human-readable error explanation",
        examples=["Session ID must be a valid UUID"],
    )


class ErrorEnvelope(BaseModel):
    """Standard API error response wrapper."""

    error: ErrorDetail
