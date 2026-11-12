from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check response schema."""

    status: Literal["ok", "degraded", "error"] = Field(
        ...,
        description="Overall service status ('ok', 'degraded', 'error')",
        examples=["ok"],
    )
    database: str = Field(
        ...,
        description="Database connectivity status",
        examples=["connected"],
    )
    providers: dict[str, str] = Field(
        ...,
        description="Active AI and storage providers",
        examples=[{"llm": "gemini", "embeddings": "gemini", "image": "mock"}],
    )
