import asyncio
import base64
import hashlib
import hmac
import uuid
from functools import lru_cache
from typing import Any

import boto3
from botocore.config import Config

from app.core.config import get_settings
from app.core.errors import APIError
from app.core.logging import logger, slogger

settings = get_settings()

IMMUTABLE_CACHE_CONTROL = "public, max-age=31536000, immutable"
THUMB_VARIANT_WIDTH = 480
FULL_VARIANT_WIDTH = 1920
ALLOWED_VARIANT_WIDTHS: tuple[int, ...] = (THUMB_VARIANT_WIDTH, FULL_VARIANT_WIDTH)


class StoragePrefixError(ValueError):
    """Raised when an object key or prefix escapes the configured R2_KEY_PREFIX."""


def _active_prefix(prefix: str | None = None) -> str:
    raw = settings.normalized_r2_prefix if prefix is None else prefix.strip().strip("/")
    if not raw or ".." in raw.split("/"):
        raise StoragePrefixError("R2_KEY_PREFIX must be a non-empty safe prefix.")
    return raw


def validate_storage_key(key: str, prefix: str | None = None) -> str:
    """Validate that an R2 object key stays strictly inside the configured app prefix."""
    active_prefix = _active_prefix(prefix)
    if not key or key.startswith("/") or "\\" in key:
        raise StoragePrefixError(f"Invalid storage key: {key!r}")
    segments = key.split("/")
    if any(seg in ("", ".", "..") for seg in segments):
        raise StoragePrefixError(f"Unsafe path segment in storage key: {key!r}")
    if not key.startswith(f"{active_prefix}/"):
        raise StoragePrefixError(
            f"Storage key {key!r} is outside allowed prefix {active_prefix + '/'!r}."
        )
    return key


def validate_list_prefix(list_prefix: str | None = None, prefix: str | None = None) -> str:
    """Validate that list_objects_v2 prefix is strictly scoped under the app prefix."""
    active_prefix = _active_prefix(prefix)
    if list_prefix is None or list_prefix.strip("/") == active_prefix:
        return f"{active_prefix}/"
    cleaned = list_prefix.strip()
    if cleaned.startswith("/") or "\\" in cleaned:
        raise StoragePrefixError(f"Invalid list prefix: {list_prefix!r}")
    segments = [seg for seg in cleaned.split("/") if seg]
    if any(seg in (".", "..") for seg in segments):
        raise StoragePrefixError(f"Unsafe segment in list prefix: {list_prefix!r}")
    if not cleaned.startswith(f"{active_prefix}/"):
        raise StoragePrefixError(
            f"List prefix {list_prefix!r} is outside allowed prefix {active_prefix + '/'!r}."
        )
    return cleaned


def hmac_owner_id(session_id: uuid.UUID | str) -> str:
    """Compute non-reversible short owner hash from X-Session-Id."""
    secret = settings.MEDIA_OWNER_SECRET
    if not secret:
        if settings.ENVIRONMENT == "production":
            raise ValueError("MEDIA_OWNER_SECRET must be set in production.")
        secret = "brandmuse-dev-owner-secret"
    digest = hmac.new(
        secret.encode("utf-8"),
        str(session_id).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return digest[:16]


def build_generation_keys(
    session_id: uuid.UUID | str,
    image_id: uuid.UUID | None = None,
    prefix: str | None = None,
) -> tuple[str, str]:
    """Build guarded (full_key, thumb_key) pair for a generated WebP image."""
    active_prefix = _active_prefix(prefix)
    owner = hmac_owner_id(session_id)
    uid = str(image_id or uuid.uuid4())
    full_key = validate_storage_key(
        f"{active_prefix}/generations/{owner}/{uid}.webp", active_prefix
    )
    thumb_key = validate_storage_key(
        f"{active_prefix}/generations/{owner}/{uid}-thumb.webp", active_prefix
    )
    return full_key, thumb_key


def derive_thumb_key(key: str) -> str | None:
    """Derive the static -thumb.webp sibling key for a stored .webp object key."""
    if key.endswith("-thumb.webp"):
        return key
    if key.endswith(".webp"):
        return f"{key[:-5]}-thumb.webp"
    return None


def public_media_url(key_or_url: str) -> str:
    """Build absolute HTTPS media URL from storage key while supporting legacy absolute URLs."""
    if key_or_url.startswith(("http://", "https://", "data:")):
        return key_or_url
    clean_key = key_or_url.lstrip("/")
    if settings.R2_PUBLIC_URL:
        base_url = settings.R2_PUBLIC_URL.rstrip("/")
        return f"{base_url}/{clean_key}"
    return (
        f"https://{settings.R2_BUCKET_NAME}.{settings.R2_ACCOUNT_ID}."
        f"r2.cloudflarestorage.com/{clean_key}"
    )


def media_variant_url(key_or_url: str, width: int) -> str:
    """Return static WebP variant URL for whitelisted widths (480 thumb, 1920 full)."""
    if width not in ALLOWED_VARIANT_WIDTHS:
        raise ValueError(
            f"Unsupported media width {width}. Allowed widths: {ALLOWED_VARIANT_WIDTHS}"
        )
    if key_or_url.startswith(("http://", "https://", "data:")):
        return key_or_url
    if width <= THUMB_VARIANT_WIDTH:
        thumb_key = derive_thumb_key(key_or_url)
        if thumb_key:
            return public_media_url(thumb_key)
    return public_media_url(key_or_url)


@lru_cache(maxsize=1)
def _build_r2_client(account_id: str, access_key: str, secret_key: str) -> Any:
    return boto3.client(
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(
            signature_version="s3v4",
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
            max_pool_connections=16,
        ),
        region_name="auto",
    )


def _get_r2_client() -> Any:
    return _build_r2_client(
        settings.R2_ACCOUNT_ID,
        settings.R2_ACCESS_KEY_ID,
        settings.R2_SECRET_ACCESS_KEY,
    )


def put_object_sync(
    key: str,
    image_bytes: bytes,
    content_type: str = "image/webp",
    cache_control: str = IMMUTABLE_CACHE_CONTROL,
) -> str:
    """Put a single object into R2 enforcing prefix guard and immutable cache headers."""
    safe_key = validate_storage_key(key)
    client = _get_r2_client()
    client.put_object(
        Bucket=settings.R2_BUCKET_NAME,
        Key=safe_key,
        Body=image_bytes,
        ContentType=content_type,
        CacheControl=cache_control,
    )
    return safe_key


def delete_objects_sync(keys: list[str]) -> list[str]:
    """Delete objects from R2 enforcing prefix guard on every key (batched when >1)."""
    if not keys:
        return []
    safe_keys = [validate_storage_key(k) for k in keys]
    client = _get_r2_client()
    if len(safe_keys) == 1:
        client.delete_object(Bucket=settings.R2_BUCKET_NAME, Key=safe_keys[0])
    else:
        for i in range(0, len(safe_keys), 1000):
            batch = safe_keys[i : i + 1000]
            client.delete_objects(
                Bucket=settings.R2_BUCKET_NAME,
                Delete={"Objects": [{"Key": k} for k in batch], "Quiet": True},
            )
    return safe_keys


def head_object_sync(key: str) -> dict[str, Any]:
    """Read object metadata from R2 enforcing prefix guard."""
    safe_key = validate_storage_key(key)
    client = _get_r2_client()
    result: dict[str, Any] = client.head_object(Bucket=settings.R2_BUCKET_NAME, Key=safe_key)
    return result


def list_objects_sync(
    prefix: str | None = None,
    max_keys: int = 1000,
    continuation_token: str | None = None,
) -> dict[str, Any]:
    """List objects in R2 strictly scoped under R2_KEY_PREFIX."""
    safe_prefix = validate_list_prefix(prefix)
    client = _get_r2_client()
    kwargs: dict[str, Any] = {
        "Bucket": settings.R2_BUCKET_NAME,
        "Prefix": safe_prefix,
        "MaxKeys": max_keys,
    }
    if continuation_token:
        kwargs["ContinuationToken"] = continuation_token
    result: dict[str, Any] = client.list_objects_v2(**kwargs)
    return result


async def delete_storage_objects(keys: list[str]) -> None:
    """Best-effort async deletion of R2 objects (e.g. cleanup after failed DB write)."""
    if not keys or not settings.is_r2_active:
        return
    try:
        safe_keys = await asyncio.to_thread(delete_objects_sync, keys)
        slogger.info("r2_objects_deleted", keys=safe_keys, bucket=settings.R2_BUCKET_NAME)
    except Exception as exc:
        slogger.error("r2_delete_failed", keys=keys, error=str(exc))


async def upload_image_variants_to_storage(
    full_bytes: bytes,
    thumb_bytes: bytes,
    session_id: uuid.UUID | str,
    content_type: str = "image/webp",
) -> tuple[str, str, str, int]:
    """Upload full and thumb WebP variants to R2 or return local data URI fallback.

    Returns (stored_key_or_data_uri, public_full_url, public_thumb_url, r2_total_bytes).
    """
    if settings.is_r2_active:
        full_key, thumb_key = build_generation_keys(session_id)
        full_res, thumb_res = await asyncio.gather(
            asyncio.to_thread(put_object_sync, full_key, full_bytes, content_type),
            asyncio.to_thread(put_object_sync, thumb_key, thumb_bytes, content_type),
            return_exceptions=True,
        )

        if isinstance(full_res, BaseException) or isinstance(thumb_res, BaseException):
            cleanup_keys: list[str] = []
            if not isinstance(full_res, BaseException):
                cleanup_keys.append(full_key)
            if not isinstance(thumb_res, BaseException):
                cleanup_keys.append(thumb_key)
            if cleanup_keys:
                await delete_storage_objects(cleanup_keys)

            failed_exc: BaseException = (
                full_res
                if isinstance(full_res, BaseException)
                else (
                    thumb_res
                    if isinstance(thumb_res, BaseException)
                    else RuntimeError("R2 upload failed")
                )
            )
            failed_key = full_key if isinstance(full_res, BaseException) else thumb_key
            logger.error("Cloudflare R2 upload error: %s", failed_exc)
            slogger.error("r2_upload_failed", key=failed_key, error=str(failed_exc))
            raise APIError(
                code="STORAGE_UPLOAD_FAILED",
                message=f"Failed to upload image to Cloudflare R2: {failed_exc}",
                status_code=502,
            ) from failed_exc

        total_bytes = len(full_bytes) + len(thumb_bytes)
        full_url = public_media_url(full_key)
        thumb_url = public_media_url(thumb_key)
        slogger.info(
            "r2_object_uploaded",
            full_key=full_key,
            thumb_key=thumb_key,
            size_bytes=total_bytes,
            bucket=settings.R2_BUCKET_NAME,
        )
        return full_key, full_url, thumb_url, total_bytes

    logger.warning("No remote storage credentials configured. Returning local data URI.")
    b64 = base64.b64encode(full_bytes).decode("utf-8")
    data_uri = f"data:{content_type};base64,{b64}"
    return data_uri, data_uri, data_uri, 0


async def upload_image_to_storage(
    image_bytes: bytes,
    filename: str | None = None,
    content_type: str = "image/webp",
) -> str:
    """Upload single image object to R2 (prefix-guarded) or return local data URI."""
    if settings.is_r2_active:
        prefix = _active_prefix()
        raw_key = filename or f"{prefix}/generations/legacy/{uuid.uuid4()}.webp"
        safe_key = validate_storage_key(raw_key, prefix)
        try:
            await asyncio.to_thread(put_object_sync, safe_key, image_bytes, content_type)
            public_url = public_media_url(safe_key)
            logger.info("Uploaded image to Cloudflare R2: %s -> %s", safe_key, public_url)
            return public_url
        except Exception as exc:
            logger.error("Cloudflare R2 upload error: %s", exc)
            raise APIError(
                code="STORAGE_UPLOAD_FAILED",
                message=f"Failed to upload image to Cloudflare R2: {exc}",
                status_code=502,
            ) from exc

    logger.warning("No remote storage credentials configured. Returning local data URI.")
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:{content_type};base64,{b64}"
