import datetime
import uuid
from typing import Any

from pydantic import BaseModel, Field


class ImageGenerateRequest(BaseModel):
    """Request payload to synthesize an image asset using Stable Diffusion."""

    image_prompt: str = Field(
        ...,
        description="Detailed visual prompt describing the scene",
        min_length=5,
        max_length=1000,
    )
    concept_title: str = Field(
        ...,
        description="Associated creative concept title",
        min_length=1,
        max_length=200,
    )
    concept_json: dict[str, Any] = Field(
        default_factory=dict,
        description="Full concept metadata object for gallery persistence",
    )
    aspect_ratio: str = Field(
        default="1:1",
        description="Aspect ratio (1:1 Feed, 9:16 Stories/Reels, 16:9 Banner)",
        pattern="^(1:1|9:16|16:9)$",
    )
    negative_prompt: str | None = Field(
        default=None,
        description="Custom or brand-specific negative prompt restrictions",
        max_length=500,
    )


class ImageGenerateResponse(BaseModel):
    """Result of image generation including permanent public storage URL."""

    id: uuid.UUID = Field(..., description="Unique generation record identifier")
    url: str = Field(..., description="Permanent public HTTPS URL of the generated asset")
    thumbnail_url: str | None = Field(
        default=None,
        description="Static thumbnail WebP URL for compact previews",
    )


class GenerationItem(BaseModel):
    """Persisted generation record item for gallery views."""

    id: uuid.UUID = Field(..., description="Generation ID")
    concept_title: str = Field(..., description="Associated concept title")
    concept_json: dict[str, Any] = Field(
        default_factory=dict,
        description="Stored concept metadata",
    )
    image_url: str = Field(..., description="Permanent public image URL")
    thumbnail_url: str | None = Field(
        default=None,
        description="Static thumbnail WebP URL for gallery grid cards",
    )
    provider: str = Field(..., description="Image provider used, e.g. stability or replicate")
    size_bytes: int | None = Field(
        default=None,
        description="Total stored WebP size in bytes across full and thumbnail variants",
    )
    created_at: datetime.datetime = Field(..., description="Timestamp of generation")


class GalleryResponse(BaseModel):
    """Paginated list of generated assets created within the active session."""

    generations: list[GenerationItem] = Field(
        default=[],
        description="Image generations belonging to this session",
    )
    limit: int = Field(default=24, description="Page size applied to this response")
    offset: int = Field(default=0, description="Pagination offset applied to this response")
    has_more: bool = Field(default=False, description="Whether additional records exist")


class AdminUsageResponse(BaseModel):
    """Operational storage and daily quota telemetry for administrators."""

    bucket: str = Field(..., description="Configured Cloudflare R2 bucket name")
    prefix: str = Field(..., description="Configured R2 key prefix for BrandMuse")
    used_bytes: int = Field(..., description="Sum of recorded size_bytes in generations")
    quota_bytes: int = Field(..., description="Configured R2_APP_QUOTA_MB in bytes")
    percent_used: float = Field(..., description="Percentage of BrandMuse quota consumed")
    total_generations: int = Field(..., description="Total generation rows in database")
    legacy_unknown_size_count: int = Field(
        ..., description="Rows without recorded size_bytes pending backfill/migration"
    )
    daily_image_count: int = Field(..., description="Images generated today")
    daily_llm_count: int = Field(..., description="LLM calls recorded today")
