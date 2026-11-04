import uuid

from pydantic import BaseModel, Field


class Concept(BaseModel):
    """A generated marketing campaign concept grounded in brand guidelines."""

    title: str = Field(..., description="Catchy campaign headline or concept title")
    caption: str = Field(..., description="Social/ad copywriting caption aligned with brand voice")
    hashtags: list[str] = Field(
        default=[],
        description="Relevant campaign hashtags (3 to 5 tags)",
    )
    visual_direction: str = Field(
        ...,
        description="Art direction notes detailing lighting, color mood, and scene composition",
    )
    image_prompt: str = Field(
        ...,
        description=(
            "Optimized Stable Diffusion prompt describing the scene in pure visual tokens. "
            "Never include rendered text, watermarks, or celebrity names."
        ),
    )
    brand_rules_used: list[str] = Field(
        default=[],
        description="Specific brand guideline rules and colors incorporated into this concept",
    )


class CampaignOutput(BaseModel):
    """Structured LLM output containing exactly 3 distinct campaign directions."""

    concepts: list[Concept] = Field(
        ...,
        description="List of exactly 3 distinct creative concepts",
        min_length=3,
        max_length=3,
    )


class CampaignBrief(BaseModel):
    """User input brief for generating on-brand campaign concepts."""

    product: str = Field(
        ...,
        description="The product, service, or initiative being launched or promoted",
        min_length=2,
        max_length=200,
    )
    audience: str = Field(
        ...,
        description="Target customer demographic or persona",
        min_length=2,
        max_length=200,
    )
    channel: str = Field(
        ...,
        description="Target primary channel, e.g. Instagram, LinkedIn, Outdoor, or Email",
        min_length=2,
        max_length=100,
    )
    mood: str = Field(
        ...,
        description="Desired campaign mood or angle, e.g. serene, bold, playful, or minimalist",
        min_length=2,
        max_length=100,
    )


class CampaignRequest(BaseModel):
    """Incoming request to generate 3 brand-aligned creative concepts."""

    document_id: uuid.UUID = Field(..., description="Target brand guideline document ID")
    brief: CampaignBrief = Field(..., description="Campaign brief requirements")


class CampaignResponse(BaseModel):
    """Response containing 3 creative concepts with guideline citations and trace link."""

    concepts: list[Concept] = Field(..., description="Generated campaign concepts")
    brand_rules_used: list[str] = Field(
        default=[],
        description="Aggregated brand guideline rules applied across the concepts",
    )
    trace_url: str | None = Field(
        default=None,
        description="Direct URL to Langfuse trace for auditability",
    )
