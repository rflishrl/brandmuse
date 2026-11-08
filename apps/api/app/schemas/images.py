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
        description="Aspect ratio for image generation (1:1 for Feed, 9:16 for Stories/Reels, 16:9 for Banner)",
        pattern="^(1:1|9:16|16:9)$",
    )
    negative_prompt: str | None = Field(
        default=None,
        description="Custom or brand-specific negative prompt restrictions",
        max_length=500,
    )


class ImageGenerateResponse(BaseModel):
    """Result of image generation including permanent public Supabase Storage URL."""

    id: uuid.UUID = Field(..., description="Unique generation record identifier")
    url: str = Field(..., description="Permanent public HTTPS URL of the generated asset")


class GenerationItem(BaseModel):
    """Persisted generation record item for gallery views."""

    id: uuid.UUID = Field(..., description="Generation ID")
    concept_title: str = Field(..., description="Associated concept title")
    concept_json: dict[str, Any] = Field(
        default_factory=dict,
        description="Stored concept metadata",
    )
    image_url: str = Field(..., description="Permanent public image URL")
    provider: str = Field(..., description="Image provider used, e.g. stability or replicate")
    created_at: datetime.datetime = Field(..., description="Timestamp of generation")


class GalleryResponse(BaseModel):
    """List of all generated assets created within the active session."""

    generations: list[GenerationItem] = Field(
        default=[],
        description="All image generations belonging to this session",
    )
