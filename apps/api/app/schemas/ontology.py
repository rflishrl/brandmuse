import datetime
import uuid
from typing import Literal

from pydantic import BaseModel, Field


class ColorToken(BaseModel):
    """Structured brand color definition."""

    name: str = Field(..., description="Color name (e.g., 'Terracotta Brown', 'Forest Green')")
    hex: str = Field(
        ...,
        description="Hexadecimal color code (e.g., '#222B27')",
        pattern=r"^#[0-9a-fA-F]{6}$",
    )
    role: Literal["primary", "secondary", "accent", "background", "text", "other"] = Field(
        default="primary",
        description="Functional role in the design system",
    )
    usage_notes: str | None = Field(
        default=None,
        description="Restrictions or guidelines for this color (e.g. 'Packaging only, never text')",
    )
    page: int | None = Field(
        default=None,
        description="Page number in guideline where color is defined",
    )


class TypographyToken(BaseModel):
    """Structured brand typography rule."""

    font_family: str = Field(
        ..., description="Font family name (e.g., 'Inter', 'Playfair Display')"
    )
    role: Literal["primary", "secondary", "accent", "body", "headline", "caption"] = Field(
        default="body",
        description="Typographic hierarchy level",
    )
    weights: list[str] = Field(
        default_factory=list,
        description="Permitted font weights (e.g., ['Regular (400)', 'Bold (700)'])",
    )
    usage_notes: str | None = Field(
        default=None,
        description="Usage rules (e.g., 'All-caps for subheadings only, line-height 1.4')",
    )
    page: int | None = Field(
        default=None,
        description="Page number where typography rule is documented",
    )


class BrandIdentity(BaseModel):
    """Core identity and voice attributes of the brand."""

    brand_name: str = Field(..., description="Official brand name")
    tagline: str | None = Field(default=None, description="Official tagline or slogan")
    mission_or_purpose: str | None = Field(
        default=None,
        description="Core mission, purpose, or brand philosophy",
    )
    target_audience: str | None = Field(
        default=None,
        description="Primary target demographic or customer persona",
    )
    tone_attributes: list[str] = Field(
        default_factory=list,
        description="Key tone of voice descriptors (e.g., ['Empathetic', 'Minimalist'])",
    )


class BrandRuleItem(BaseModel):
    """Atomic DO or DON'T constraint in the brand guideline."""

    category: Literal[
        "logo", "color", "typography", "imagery", "tone_of_voice", "channel_restriction", "general"
    ] = Field(..., description="Rule category")
    type: Literal["do", "dont", "guideline"] = Field(
        ...,
        description="'do' for mandatory, 'dont' for prohibitions, 'guideline' for recommendations",
    )
    rule: str = Field(
        ...,
        description="Clear, actionable rule description (e.g., 'Never rotate the logo mark')",
    )
    reasoning: str | None = Field(
        default=None,
        description="Brand reasoning or context behind this rule",
    )
    page: int | None = Field(
        default=None,
        description="Page number in brand guideline containing this rule",
    )


class ChannelRule(BaseModel):
    """Channel-specific requirements and prohibitions."""

    channel: str = Field(
        ...,
        description="Marketing channel name (e.g., 'Instagram', 'Packaging', 'Billboard')",
    )
    dos: list[str] = Field(default_factory=list, description="Permitted or recommended practices")
    donts: list[str] = Field(
        default_factory=list, description="Prohibited practices for this channel"
    )


class BrandOntologyData(BaseModel):
    """Complete structured brand ontology extracted from guideline documentation."""

    identity: BrandIdentity = Field(..., description="Brand identity and voice")
    colors: list[ColorToken] = Field(
        default_factory=list,
        description="Brand color palette and hex codes",
    )
    typography: list[TypographyToken] = Field(
        default_factory=list,
        description="Typography standards and fonts",
    )
    rules: list[BrandRuleItem] = Field(
        default_factory=list,
        description="Catalog of atomic DOs, DONTs, and restrictions",
    )
    channel_rules: list[ChannelRule] = Field(
        default_factory=list,
        description="Channel-specific rules and constraints",
    )


class BrandOntologyResponse(BaseModel):
    """API response model for a document's brand ontology."""

    id: uuid.UUID
    document_id: uuid.UUID
    is_certified: bool
    certified_at: datetime.datetime | None = None
    certified_by: str | None = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    ontology: BrandOntologyData


class BrandOntologyUpdate(BaseModel):
    """Payload for human-in-the-loop editing of extracted ontology."""

    ontology: BrandOntologyData


class BrandOntologyCertify(BaseModel):
    """Payload to certify the ontology for team production use."""

    certified_by: str = Field(
        default="Brand Manager",
        description="Name or role of the certifying human expert",
        min_length=2,
        max_length=100,
    )
