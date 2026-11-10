import asyncio
import base64
import uuid
from typing import Any

import boto3
from botocore.config import Config

from app.core.config import get_settings
from app.core.errors import APIError
from app.core.logging import logger

settings = get_settings()


def _get_r2_client() -> Any:
    return boto3.client(
        "s3",
        endpoint_url=f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def _upload_to_r2_sync(file_id: str, image_bytes: bytes, content_type: str) -> str:
    client = _get_r2_client()
    client.put_object(
        Bucket=settings.R2_BUCKET_NAME,
        Key=file_id,
        Body=image_bytes,
        ContentType=content_type,
    )
    if settings.R2_PUBLIC_URL:
        base_url = settings.R2_PUBLIC_URL.rstrip("/")
        return f"{base_url}/{file_id}"
    return (
        f"https://{settings.R2_BUCKET_NAME}.{settings.R2_ACCOUNT_ID}."
        f"r2.cloudflarestorage.com/{file_id}"
    )


async def upload_image_to_storage(
    image_bytes: bytes,
    filename: str | None = None,
    content_type: str = "image/png",
) -> str:
    """Upload generated image bytes to Cloudflare R2 or return fallback local data URI."""
    file_id = filename or f"{uuid.uuid4()}.png"

    # 1. Cloudflare R2 check
    is_r2 = settings.STORAGE_PROVIDER == "r2" or (
        settings.STORAGE_PROVIDER == "auto"
        and bool(settings.R2_ACCOUNT_ID)
        and bool(settings.R2_ACCESS_KEY_ID)
        and bool(settings.R2_SECRET_ACCESS_KEY)
    )
    if is_r2:
        try:
            public_url = await asyncio.to_thread(
                _upload_to_r2_sync, file_id, image_bytes, content_type
            )
            logger.info("Uploaded image to Cloudflare R2: %s -> %s", file_id, public_url)
            return public_url
        except Exception as exc:
            logger.error("Cloudflare R2 upload error: %s", exc)
            raise APIError(
                code="STORAGE_UPLOAD_FAILED",
                message=f"Failed to upload image to Cloudflare R2: {exc}",
                status_code=502,
            ) from exc

    # 2. Fallback to inline Base64 data URI
    logger.warning("No remote storage credentials configured. Returning local data URI.")
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:{content_type};base64,{b64}"
