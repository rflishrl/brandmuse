import asyncio
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import APIError
from app.core.logging import hash_session_id, slogger
from app.core.security import get_session_id
from app.db.repositories import GenerationRepository
from app.db.session import get_db
from app.observability.langfuse import record_langfuse_event
from app.providers.image import encode_webp_variants, get_image_provider, moderate_prompt
from app.providers.storage import (
    THUMB_VARIANT_WIDTH,
    delete_storage_objects,
    derive_thumb_key,
    media_variant_url,
    public_media_url,
    upload_image_variants_to_storage,
)
from app.schemas.images import (
    GalleryResponse,
    GenerationItem,
    ImageGenerateRequest,
    ImageGenerateResponse,
)
from app.services.usage import (
    check_and_increment_daily_usage,
    check_app_storage_quota,
    check_daily_usage_available,
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
    """Generate WebP image variants with safety moderation, quota checks, and R2 persistence."""
    moderate_prompt(payload.image_prompt)

    await check_session_image_hourly_limit(
        db, session_id, limit=settings.SESSION_IMAGE_HOURLY_LIMIT
    )
    await check_daily_usage_available(db, "image", settings.DAILY_IMAGE_LIMIT)
    used_bytes, quota_bytes = await check_app_storage_quota(db, settings.R2_APP_QUOTA_MB)

    # Release DB read transaction before slow image generation, WebP encoding, and R2 upload
    await db.rollback()

    provider = get_image_provider()
    raw_bytes = await provider.generate_image(
        payload.image_prompt,
        aspect_ratio=payload.aspect_ratio,
        negative_prompt=payload.negative_prompt,
    )
    full_webp_bytes, thumb_webp_bytes = await asyncio.to_thread(encode_webp_variants, raw_bytes)

    planned_r2_bytes = len(full_webp_bytes) + len(thumb_webp_bytes) if settings.is_r2_active else 0
    if used_bytes + planned_r2_bytes > quota_bytes:
        slogger.warning(
            "storage_quota_exceeded",
            used_bytes=used_bytes,
            additional_bytes=planned_r2_bytes,
            quota_bytes=quota_bytes,
        )
        raise APIError(
            code="STORAGE_QUOTA_EXCEEDED",
            message=(
                "Image generation is temporarily paused while demo storage capacity "
                "is being refreshed. Please try again later."
            ),
            status_code=429,
        )

    stored_value, public_url, thumb_url, stored_bytes = await upload_image_variants_to_storage(
        full_webp_bytes,
        thumb_webp_bytes,
        session_id=session_id,
    )

    concept_data = {
        "title": payload.concept_title,
        "aspect_ratio": payload.aspect_ratio,
        **payload.concept_json,
    }
    try:
        generation = await GenerationRepository.create(
            db=db,
            session_id=session_id,
            concept_data=concept_data,
            image_url=stored_value,
            provider=settings.IMAGE_PROVIDER,
            size_bytes=stored_bytes,
        )
    except Exception as exc:
        slogger.error(
            "generation_db_save_failed",
            session_hash=hash_session_id(str(session_id)),
            error=str(exc),
        )
        if not stored_value.startswith(("http://", "https://", "data:")):
            cleanup_keys = [stored_value]
            thumb_key = derive_thumb_key(stored_value)
            if thumb_key:
                cleanup_keys.append(thumb_key)
            await delete_storage_objects(cleanup_keys)
        raise

    await check_and_increment_daily_usage(db, "image", settings.DAILY_IMAGE_LIMIT)

    slogger.info(
        "image_generated",
        session_hash=hash_session_id(str(session_id)),
        generation_id=str(generation.id),
        provider=settings.IMAGE_PROVIDER,
        aspect_ratio=payload.aspect_ratio,
        size_bytes=stored_bytes,
        r2_active=settings.is_r2_active,
    )
    record_langfuse_event(
        name="image_generated",
        session_id=session_id,
        metadata={
            "generation_id": str(generation.id),
            "provider": settings.IMAGE_PROVIDER,
            "aspect_ratio": payload.aspect_ratio,
            "size_bytes": stored_bytes,
            "storage": "r2" if settings.is_r2_active else "local",
        },
    )

    return ImageGenerateResponse(
        id=generation.id,
        url=public_url,
        thumbnail_url=thumb_url,
    )


@router.get(
    "",
    response_model=GalleryResponse,
    operation_id="getGallery",
    summary="Retrieve paginated generated assets for the active user session",
)
async def get_gallery(
    limit: int = Query(default=24, ge=1, le=100, description="Max items per page"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    session_id: uuid.UUID = Depends(get_session_id),
    db: AsyncSession = Depends(get_db),
) -> GalleryResponse:
    """List paginated images generated within the current isolated session ordered newest first."""
    rows = await GenerationRepository.list_for_session(
        db, session_id, limit=limit + 1, offset=offset
    )
    has_more = len(rows) > limit
    generations = rows[:limit]

    items = [
        GenerationItem(
            id=gen.id,
            concept_title=str(gen.concept_json.get("title", "Campaign Asset")),
            concept_json=gen.concept_json,
            image_url=public_media_url(gen.image_url),
            thumbnail_url=media_variant_url(gen.image_url, THUMB_VARIANT_WIDTH),
            provider=gen.provider,
            size_bytes=gen.size_bytes,
            created_at=gen.created_at,
        )
        for gen in generations
    ]

    return GalleryResponse(
        generations=items,
        limit=limit,
        offset=offset,
        has_more=has_more,
    )
