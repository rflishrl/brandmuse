import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.core.config import Settings, get_settings
from app.core.errors import APIError
from app.providers.storage import (
    IMMUTABLE_CACHE_CONTROL,
    StoragePrefixError,
    _get_r2_client,
    build_generation_keys,
    delete_objects_sync,
    head_object_sync,
    hmac_owner_id,
    list_objects_sync,
    media_variant_url,
    public_media_url,
    put_object_sync,
    upload_image_to_storage,
    upload_image_variants_to_storage,
)

settings = get_settings()


@pytest.mark.asyncio
async def test_upload_image_fallback_data_uri() -> None:
    """When storage provider is local, should return base64 data URI and 0 R2 bytes."""
    with patch.object(settings, "STORAGE_PROVIDER", "local"):
        result = await upload_image_to_storage(b"fake-image-bytes", filename="brandmuse-dev/a.webp")
        assert result.startswith("data:image/webp;base64,")

        stored, full_url, thumb_url, size_bytes = await upload_image_variants_to_storage(
            b"full-bytes", b"thumb-bytes", session_id=uuid.uuid4()
        )
        assert stored.startswith("data:image/webp;base64,")
        assert full_url == stored
        assert thumb_url == stored
        assert size_bytes == 0


@pytest.mark.asyncio
async def test_upload_image_variants_to_r2_success() -> None:
    """R2 uploads must enforce prefix, immutable CacheControl, WebP ContentType, and keys."""
    mock_s3 = MagicMock()
    session_id = uuid.uuid4()
    with (
        patch.object(settings, "STORAGE_PROVIDER", "r2"),
        patch.object(settings, "R2_ACCOUNT_ID", "fake-account"),
        patch.object(settings, "R2_ACCESS_KEY_ID", "fake-key"),
        patch.object(settings, "R2_SECRET_ACCESS_KEY", "fake-secret"),
        patch.object(settings, "R2_BUCKET_NAME", "brandmuse"),
        patch.object(settings, "R2_KEY_PREFIX", "brandmuse-dev"),
        patch.object(settings, "R2_PUBLIC_URL", "https://media.example.com"),
        patch.object(settings, "MEDIA_OWNER_SECRET", "unit-test-secret"),
        patch("app.providers.storage._get_r2_client", return_value=mock_s3),
    ):
        stored_key, full_url, thumb_url, total_bytes = await upload_image_variants_to_storage(
            b"full-webp",
            b"thumb-webp",
            session_id=session_id,
        )

        assert stored_key.startswith("brandmuse-dev/generations/")
        assert stored_key.endswith(".webp")
        assert str(session_id) not in stored_key
        assert full_url == f"https://media.example.com/{stored_key}"
        assert thumb_url == full_url.replace(".webp", "-thumb.webp")
        assert total_bytes == len(b"full-webp") + len(b"thumb-webp")
        assert mock_s3.put_object.call_count == 2

        first_call = mock_s3.put_object.call_args_list[0].kwargs
        assert first_call["Bucket"] == "brandmuse"
        assert first_call["Key"] == stored_key
        assert first_call["ContentType"] == "image/webp"
        assert first_call["CacheControl"] == IMMUTABLE_CACHE_CONTROL


@pytest.mark.asyncio
async def test_upload_image_to_r2_failure_cleans_up_partial_upload() -> None:
    """When thumbnail upload fails after full upload, should best-effort delete full key."""
    mock_s3 = MagicMock()
    mock_s3.put_object.side_effect = [None, Exception("Thumb upload failed")]
    with (
        patch.object(settings, "STORAGE_PROVIDER", "r2"),
        patch.object(settings, "R2_ACCOUNT_ID", "fake-account"),
        patch.object(settings, "R2_ACCESS_KEY_ID", "fake-key"),
        patch.object(settings, "R2_SECRET_ACCESS_KEY", "fake-secret"),
        patch.object(settings, "R2_BUCKET_NAME", "brandmuse"),
        patch.object(settings, "R2_KEY_PREFIX", "brandmuse-dev"),
        patch("app.providers.storage._get_r2_client", return_value=mock_s3),
    ):
        with pytest.raises(APIError) as exc_info:
            await upload_image_variants_to_storage(
                b"full-webp", b"thumb-webp", session_id=uuid.uuid4()
            )
        assert exc_info.value.code == "STORAGE_UPLOAD_FAILED"
        mock_s3.delete_object.assert_called_once()


def test_prefix_guard_rejects_outside_prefix() -> None:
    """All storage operations must reject keys or prefixes outside R2_KEY_PREFIX."""
    mock_s3 = MagicMock()
    with (
        patch.object(settings, "R2_KEY_PREFIX", "brandmuse"),
        patch("app.providers.storage._get_r2_client", return_value=mock_s3),
    ):
        with pytest.raises(StoragePrefixError):
            put_object_sync("sinarberkah/generations/1/a.webp", b"x")
        with pytest.raises(StoragePrefixError):
            delete_objects_sync(["brandmuse/../other/a.webp"])
        with pytest.raises(StoragePrefixError):
            head_object_sync("desa-pendil/img.webp")
        with pytest.raises(StoragePrefixError):
            list_objects_sync("other-app/")
        with pytest.raises(StoragePrefixError):
            list_objects_sync("")

        list_objects_sync()
        mock_s3.list_objects_v2.assert_called_once_with(
            Bucket=settings.R2_BUCKET_NAME,
            Prefix="brandmuse/",
            MaxKeys=1000,
        )


def test_public_media_url_and_variant_url() -> None:
    """Verify public_media_url and media_variant_url handle keys, legacy URLs, and whitelists."""
    with patch.object(settings, "R2_PUBLIC_URL", "https://media.example.com/"):
        key = "brandmuse/generations/abc123/item.webp"
        assert public_media_url(key) == "https://media.example.com/brandmuse/generations/abc123/item.webp"
        assert (
            media_variant_url(key, 480)
            == "https://media.example.com/brandmuse/generations/abc123/item-thumb.webp"
        )
        assert (
            media_variant_url(key, 1920)
            == "https://media.example.com/brandmuse/generations/abc123/item.webp"
        )

        # Dual-read legacy URLs unchanged
        legacy_url = "https://pub-legacy.r2.dev/raw-session/img.png"
        assert public_media_url(legacy_url) == legacy_url
        assert media_variant_url(legacy_url, 480) == legacy_url

        # Arbitrary width rejected
        with pytest.raises(ValueError):
            media_variant_url(key, 500)


def test_hmac_owner_id_hides_session_and_changes_on_secret_rotation() -> None:
    """Owner segment must be deterministic HMAC and never expose raw session UUID."""
    sid = uuid.uuid4()
    with (
        patch.object(settings, "MEDIA_OWNER_SECRET", "secret-one"),
        patch.object(settings, "R2_KEY_PREFIX", "brandmuse"),
    ):
        owner1 = hmac_owner_id(sid)
        full_key, thumb_key = build_generation_keys(sid)
        assert len(owner1) == 16
        assert str(sid) not in full_key
        assert full_key.startswith(f"brandmuse/generations/{owner1}/")
        assert thumb_key.endswith("-thumb.webp")

    with patch.object(settings, "MEDIA_OWNER_SECRET", "secret-two"):
        owner2 = hmac_owner_id(sid)
        assert owner2 != owner1


def test_r2_client_disables_default_when_supported_checksums() -> None:
    """boto3 client for R2 must enforce when_required checksum settings."""
    with (
        patch.object(settings, "R2_ACCOUNT_ID", "acc"),
        patch.object(settings, "R2_ACCESS_KEY_ID", "key"),
        patch.object(settings, "R2_SECRET_ACCESS_KEY", "sec"),
    ):
        client = _get_r2_client()
        assert client._client_config.request_checksum_calculation == "when_required"
        assert client._client_config.response_checksum_validation == "when_required"


def test_validate_storage_environment_guard() -> None:
    """Non-production R2 requires '-dev' prefix; production requires non-dev prefix and secret."""
    bad_dev = Settings(
        ENVIRONMENT="development",
        STORAGE_PROVIDER="r2",
        R2_BUCKET_NAME="brandmuse",
        R2_KEY_PREFIX="brandmuse",
    )
    with pytest.raises(ValueError, match="-dev"):
        bad_dev.validate_storage_environment()

    good_dev = Settings(
        ENVIRONMENT="development",
        STORAGE_PROVIDER="r2",
        R2_BUCKET_NAME="brandmuse",
        R2_KEY_PREFIX="brandmuse-dev",
    )
    good_dev.validate_storage_environment()

    bad_prod_prefix = Settings(
        ENVIRONMENT="production",
        STORAGE_PROVIDER="r2",
        R2_BUCKET_NAME="brandmuse",
        R2_KEY_PREFIX="brandmuse-dev",
        MEDIA_OWNER_SECRET="prod-secret",
    )
    with pytest.raises(ValueError):
        bad_prod_prefix.validate_storage_environment()

    bad_prod_secret = Settings(
        ENVIRONMENT="production",
        STORAGE_PROVIDER="r2",
        R2_BUCKET_NAME="brandmuse",
        R2_KEY_PREFIX="brandmuse",
        MEDIA_OWNER_SECRET="",
    )
    with pytest.raises(ValueError, match="MEDIA_OWNER_SECRET"):
        bad_prod_secret.validate_storage_environment()
