import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import get_session_id
from app.db.models import Generation
from app.db.session import get_db
from app.providers.image import get_image_provider, moderate_prompt
from app.providers.storage import upload_image_to_storage
from app.schemas.images import (
    GalleryResponse,
    GenerationItem,
    ImageGenerateRequest,
    ImageGenerateResponse,
)
from app.services.usage import (
    check_and_increment_daily_usage,
    check_session_image_hourly_limit,
)

settings = get_settings()

router = APIRouter(prefix="/api/images", tags=["images"])


@router.post(
    "",
    response_model=ImageGenerateResponse,
    operation_id="generateImage",
    summary="Generate Stable Diffusion visual asset for a campaign concept",
)
async def generate_image(
    payload: ImageGenerateRequest,
    session_id: uuid.UUID = Depends(get_session_id),
    db: AsyncSession = Depends(get_db),
) -> ImageGenerateResponse:
    """Generate image with safety moderation, rate limits, and Supabase Storage persistence."""
    # 1. Enforce safety checks
    moderate_prompt(payload.image_prompt)

    # 2. Check rate limits (session hourly limit & global daily quota)
    await check_session_image_hourly_limit(db, session_id, limit=5)
    await check_and_increment_daily_usage(db, "image", settings.DAILY_IMAGE_LIMIT)

    # 3. Generate image bytes
    provider = get_image_provider()
    image_bytes = await provider.generate_image(
        payload.image_prompt,
        aspect_ratio=payload.aspect_ratio,
        negative_prompt=payload.negative_prompt,
    )

    # 4. Upload to persistent Supabase Storage
    filename = f"{session_id}/{uuid.uuid4()}.png"
    image_url = await upload_image_to_storage(image_bytes, filename=filename)

    # 5. Persist generation record
    concept_data = {
        "title": payload.concept_title,
        "aspect_ratio": payload.aspect_ratio,
        **payload.concept_json,
    }
    generation = Generation(
        id=uuid.uuid4(),
        session_id=session_id,
        concept_json=concept_data,
        image_url=image_url,
        provider=settings.IMAGE_PROVIDER,
    )
    db.add(generation)
    await db.commit()
    await db.refresh(generation)

    return ImageGenerateResponse(id=generation.id, url=generation.image_url)


@router.get(
    "",
    response_model=GalleryResponse,
    operation_id="getGallery",
    summary="Retrieve all generated assets for the active user session",
)
async def get_gallery(
    session_id: uuid.UUID = Depends(get_session_id),
    db: AsyncSession = Depends(get_db),
) -> GalleryResponse:
    """List all images generated within the current isolated session ordered newest first."""
    stmt = (
        select(Generation)
        .where(Generation.session_id == session_id)
        .order_by(Generation.created_at.desc())
    )
    result = await db.execute(stmt)
    generations = result.scalars().all()

    items = [
        GenerationItem(
            id=gen.id,
            concept_title=str(gen.concept_json.get("title", "Campaign Asset")),
            concept_json=gen.concept_json,
            image_url=gen.image_url,
            provider=gen.provider,
            created_at=gen.created_at,
        )
        for gen in generations
    ]

    return GalleryResponse(generations=items)
