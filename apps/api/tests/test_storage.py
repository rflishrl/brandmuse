from unittest.mock import MagicMock, patch

import pytest

from app.core.config import get_settings
from app.core.errors import APIError
from app.providers.storage import upload_image_to_storage

settings = get_settings()


@pytest.mark.asyncio
async def test_upload_image_fallback_data_uri() -> None:
    """When no storage credentials configured, should return base64 data URI."""
    with patch.object(settings, "STORAGE_PROVIDER", "local"):
        result = await upload_image_to_storage(b"fake-image-bytes", filename="test.png")
        assert result.startswith("data:image/png;base64,")


@pytest.mark.asyncio
async def test_upload_image_to_r2_success() -> None:
    """When R2 is configured, should call boto3 put_object and return R2 public URL."""
    mock_s3 = MagicMock()
    with (
        patch.object(settings, "STORAGE_PROVIDER", "r2"),
        patch.object(settings, "R2_ACCOUNT_ID", "fake-account"),
        patch.object(settings, "R2_ACCESS_KEY_ID", "fake-key"),
        patch.object(settings, "R2_SECRET_ACCESS_KEY", "fake-secret"),
        patch.object(settings, "R2_BUCKET_NAME", "brandmuse-images"),
        patch.object(settings, "R2_PUBLIC_URL", "https://pub-brandmuse.r2.dev"),
        patch("app.providers.storage._get_r2_client", return_value=mock_s3),
    ):
        result = await upload_image_to_storage(b"png-bytes", filename="hero.png")
        assert result == "https://pub-brandmuse.r2.dev/hero.png"
        mock_s3.put_object.assert_called_once_with(
            Bucket="brandmuse-images",
            Key="hero.png",
            Body=b"png-bytes",
            ContentType="image/png",
        )


@pytest.mark.asyncio
async def test_upload_image_to_r2_failure() -> None:
    """When R2 client raises exception, should raise APIError."""
    mock_s3 = MagicMock()
    mock_s3.put_object.side_effect = Exception("AWS S3 connection failed")
    with (
        patch.object(settings, "STORAGE_PROVIDER", "r2"),
        patch.object(settings, "R2_ACCOUNT_ID", "fake-account"),
        patch.object(settings, "R2_ACCESS_KEY_ID", "fake-key"),
        patch.object(settings, "R2_SECRET_ACCESS_KEY", "fake-secret"),
        patch("app.providers.storage._get_r2_client", return_value=mock_s3),
    ):
        with pytest.raises(APIError) as exc_info:
            await upload_image_to_storage(b"png-bytes", filename="hero.png")
        assert exc_info.value.code == "STORAGE_UPLOAD_FAILED"
