import uuid
from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """Chat message history entry."""

    role: Literal["user", "assistant"] = Field(..., description="Message author role")
    content: str = Field(..., description="Text content of the message", max_length=4000)


class ChatRequest(BaseModel):
    """Incoming user chat query for guideline grounded Q&A."""

    document_id: uuid.UUID = Field(..., description="Target brand guideline document ID")
    message: str = Field(
        ...,
        description="User question regarding brand guidelines",
        min_length=1,
        max_length=2000,
    )
    history: list[ChatMessage] = Field(
        default=[],
        description="Recent conversation turns (max 10)",
        max_length=10,
    )
    mode: Literal["auto", "strict", "creative"] = Field(
        default="auto",
        description="Execution mode: auto (balanced), strict (rules only), creative (exploratory)",
    )


class CitationItem(BaseModel):
    """Citation provenance for retrieved document chunk."""

    page: int = Field(..., description="Guideline page number")
    chunk_index: int = Field(..., description="Unique chunk index within the document")
    snippet: str = Field(..., description="Short text snippet supporting the answer")
    rrf_score: float = Field(..., description="Reciprocal Rank Fusion score")
    vector_score: float | None = Field(default=None, description="Vector cosine similarity score")
    keyword_score: float | None = Field(default=None, description="Full-text ts_rank score")


class ChatFinalPayload(BaseModel):
    """Final Server-Sent Event payload containing citations and Langfuse trace link."""

    citations: list[CitationItem] = Field(..., description="Retrieved chunk citations")
    trace_url: str | None = Field(default=None, description="Direct URL to Langfuse trace")
