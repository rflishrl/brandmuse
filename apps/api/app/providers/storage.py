import base64
import uuid

import httpx

from app.core.config import get_settings
from app.core.errors import APIError
from app.core.logging import logger

settings = get_settings()


async def upload_image_to_storage(
    image_bytes: bytes,
    filename: str | None = None,
    content_type: str = "image/png",
) -> str:
    """Upload generated image bytes to Supabase Storage and return permanent public URL."""
    file_id = filename or f"{uuid.uuid4()}.png"

    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        logger.warning("Supabase Storage credentials not configured. Returning local data URI.")
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        return f"data:{content_type};base64,{b64}"

    supabase_url = settings.SUPABASE_URL.rstrip("/")
    bucket = settings.SUPABASE_STORAGE_BUCKET
    upload_url = f"{supabase_url}/storage/v1/object/{bucket}/{file_id}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            upload_url,
            headers={
                "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
                "Content-Type": content_type,
                "x-upsert": "true",
            },
            content=image_bytes,
        )

        if response.status_code not in (200, 201):
            raise APIError(
                code="STORAGE_UPLOAD_FAILED",
                message=f"Failed to upload image to Supabase Storage: {response.text}",
                status_code=502,
            )

    permanent_public_url = f"{supabase_url}/storage/v1/object/public/{bucket}/{file_id}"
    return permanent_public_url
