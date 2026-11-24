import datetime
import io
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from httpx import AsyncClient
from PIL import Image

from app.core.config import get_settings
from app.core.errors import APIError
from app.db.models import Generation
from app.providers.image import (
    MockImageProvider,
    download_provider_image,
    encode_webp_variants,
    moderate_prompt,
    validate_image_download_url,
)

settings = get_settings()


def test_moderate_prompt_allowed() -> None:
    """Verify safe prompts pass moderation check."""
    moderate_prompt("Minimalist ceramic vase on wooden dining table in soft daylight")


def test_moderate_prompt_word_boundary_avoids_false_positives() -> None:
    """Verify terms like 'skillful' are allowed even if they contain 'kill' as a substring."""
    moderate_prompt("A skillful ceramic artisan working with skilled precision")


def test_moderate_prompt_blocked() -> None:
    """Verify unsafe prompts are rejected with 400 APIError."""
    with pytest.raises(APIError) as exc_info:
        moderate_prompt("An extreme graphic violence scene with weapons")

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "PROMPT_MODERATION_FAILED"


@pytest.mark.asyncio
async def test_mock_image_provider_generates_valid_png() -> None:
    """Verify MockImageProvider produces valid readable PNG bytes."""
    provider = MockImageProvider()
    img_bytes = await provider.generate_image("A serene living room")

    assert isinstance(img_bytes, bytes)
    assert len(img_bytes) > 0

    img = Image.open(io.BytesIO(img_bytes))
    assert img.size == (1024, 1024)
    assert img.format == "PNG"


@pytest.mark.asyncio
async def test_mock_image_provider_multi_aspect_ratios() -> None:
    """Verify MockImageProvider produces exact pixel dimensions for 9:16 and 16:9."""
    provider = MockImageProvider()

    img_9_16 = await provider.generate_image("Vertical story", aspect_ratio="9:16")
    im1 = Image.open(io.BytesIO(img_9_16))
    assert im1.size == (576, 1024)

    img_16_9 = await provider.generate_image("Landscape banner", aspect_ratio="16:9")
    im2 = Image.open(io.BytesIO(img_16_9))
    assert im2.size == (1024, 576)


def test_encode_webp_variants_resizes_and_outputs_webp() -> None:
    """encode_webp_variants must cap full at 1920px, thumb at 480px, and emit WebP."""
    large_img = Image.new("RGB", (2400, 1200), color=(40, 60, 50))
    buf = io.BytesIO()
    large_img.save(buf, format="PNG")

    full_bytes, thumb_bytes = encode_webp_variants(buf.getvalue())

    with Image.open(io.BytesIO(full_bytes)) as full_out:
        assert full_out.format == "WEBP"
        assert full_out.size == (1920, 960)

    with Image.open(io.BytesIO(thumb_bytes)) as thumb_out:
        assert thumb_out.format == "WEBP"
        assert thumb_out.size == (480, 240)


def test_ssrf_validate_image_download_url() -> None:
    """Allowlisted HTTPS host with public IP passes; private IPs, HTTP, and foreign hosts fail."""
    with patch("app.providers.image._resolve_host_ips", return_value=["104.18.10.20"]):
        assert (
            validate_image_download_url("https://replicate.delivery/pbxt/example.png")
            == "https://replicate.delivery/pbxt/example.png"
        )

    for bad_url in [
        "http://replicate.delivery/a.png",
        "https://evil.example.com/a.png",
        "https://127.0.0.1/a.png",
        "https://user:pass@replicate.delivery/a.png",
        "https://replicate.delivery:8443/a.png",
    ]:
        with pytest.raises(APIError) as exc_info:
            validate_image_download_url(bad_url)
        assert exc_info.value.code == "UNSAFE_IMAGE_URL"

    with patch("app.providers.image._resolve_host_ips", return_value=["169.254.169.254"]):
        with pytest.raises(APIError) as exc_info:
            validate_image_download_url("https://replicate.delivery/pbxt/meta.png")
        assert exc_info.value.code == "UNSAFE_IMAGE_URL"


@pytest.mark.asyncio
async def test_download_provider_image_rejects_unsafe_redirect_and_oversize() -> None:
    """download_provider_image blocks cross-host redirects and stream-aborts oversized payloads."""
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _make_stream(status_code: int, headers: dict[str, str], chunks: list[bytes]):
        res = MagicMock()
        res.status_code = status_code
        res.headers = headers

        async def _aiter_bytes(chunk_size: int = 65536):
            _ = chunk_size
            for c in chunks:
                yield c

        res.aiter_bytes = _aiter_bytes
        yield res

    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.stream = MagicMock(
        side_effect=lambda *_a, **_kw: _make_stream(
            302, {"location": "https://evil.example.com/steal.png"}, []
        )
    )

    with patch("app.providers.image._resolve_host_ips", return_value=["104.18.10.20"]):
        with pytest.raises(APIError) as exc_info:
            await download_provider_image(
                "https://replicate.delivery/pbxt/start.png", client=mock_client
            )
        assert exc_info.value.code == "UNSAFE_IMAGE_URL"

    # Oversized chunked payload without Content-Length header must abort mid-stream
    mock_client.stream = MagicMock(
        side_effect=lambda *_a, **_kw: _make_stream(200, {}, [b"x" * 60, b"y" * 60])
    )
    with patch("app.providers.image._resolve_host_ips", return_value=["104.18.10.20"]):
        with pytest.raises(APIError) as exc_info:
            await download_provider_image(
                "https://replicate.delivery/pbxt/big.png",
                client=mock_client,
                max_bytes=100,
            )
        assert exc_info.value.code == "IMAGE_TOO_LARGE"


@pytest.mark.asyncio
async def test_post_image_generation_endpoint(
    client: AsyncClient,
    mock_db: AsyncMock,
) -> None:
    """Verify POST /api/images converts WebP, uploads variants, and persists record."""
    session_id = str(uuid.uuid4())
    stored_key = "brandmuse-dev/generations/abc123/test.webp"
    full_url = f"https://media.example.com/{stored_key}"
    thumb_url = f"https://media.example.com/{stored_key.replace('.webp', '-thumb.webp')}"

    mock_db.execute.return_value = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    increment_mock = AsyncMock(return_value=1)

    with (
        patch("app.routers.images.check_session_image_hourly_limit", AsyncMock()),
        patch("app.routers.images.check_daily_usage_available", AsyncMock()),
        patch("app.routers.images.check_app_storage_quota", AsyncMock(return_value=(0, 1024))),
        patch("app.routers.images.check_and_increment_daily_usage", increment_mock),
        patch("app.routers.images.get_image_provider", return_value=MockImageProvider()),
        patch(
            "app.routers.images.upload_image_variants_to_storage",
            AsyncMock(return_value=(stored_key, full_url, thumb_url, 1234)),
        ),
    ):
        resp = await client.post(
            "/api/images",
            headers={"X-Session-Id": session_id},
            json={
                "image_prompt": "Warm minimalist interior with terracotta vase and linen curtains",
                "concept_title": "Warm Sanctuary",
                "concept_json": {"mood": "serene"},
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert data["url"] == full_url
        assert data["thumbnail_url"] == thumb_url
        increment_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_post_image_db_failure_cleans_r2_and_skips_daily_counter(
    client: AsyncClient,
) -> None:
    """When DB persistence fails after upload, cleanup R2 objects and do not consume daily quota."""
    session_id = str(uuid.uuid4())
    stored_key = "brandmuse-dev/generations/abc123/orphan.webp"
    delete_mock = AsyncMock()
    increment_mock = AsyncMock()

    with (
        patch("app.routers.images.check_session_image_hourly_limit", AsyncMock()),
        patch("app.routers.images.check_daily_usage_available", AsyncMock()),
        patch("app.routers.images.check_app_storage_quota", AsyncMock(return_value=(0, 1024))),
        patch("app.routers.images.get_image_provider", return_value=MockImageProvider()),
        patch(
            "app.routers.images.upload_image_variants_to_storage",
            AsyncMock(
                return_value=(
                    stored_key,
                    f"https://media.example.com/{stored_key}",
                    f"https://media.example.com/{stored_key.replace('.webp', '-thumb.webp')}",
                    500,
                )
            ),
        ),
        patch(
            "app.routers.images.GenerationRepository.create",
            AsyncMock(side_effect=RuntimeError("DB insert failed")),
        ),
        patch("app.routers.images.delete_storage_objects", delete_mock),
        patch("app.routers.images.check_and_increment_daily_usage", increment_mock),
    ):
        with pytest.raises(RuntimeError, match="DB insert failed"):
            await client.post(
                "/api/images",
                headers={"X-Session-Id": session_id},
                json={
                    "image_prompt": "Warm minimalist interior with terracotta vase",
                    "concept_title": "Warm Sanctuary",
                },
            )

        delete_mock.assert_awaited_once_with(
            [stored_key, "brandmuse-dev/generations/abc123/orphan-thumb.webp"]
        )
        increment_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_gallery_endpoint_dual_read_and_pagination(
    client: AsyncClient,
    mock_db: AsyncMock,
) -> None:
    """Verify GET /api/images supports dual-read (new key + legacy URL) and pagination."""
    session_id = uuid.uuid4()
    new_gen = Generation(
        id=uuid.uuid4(),
        session_id=session_id,
        concept_json={"title": "Natural Sanctuary"},
        image_url="brandmuse/generations/owner1/img1.webp",
        provider="mock",
        size_bytes=4200,
        created_at=datetime.datetime.now(datetime.UTC),
    )
    legacy_gen = Generation(
        id=uuid.uuid4(),
        session_id=session_id,
        concept_json={"title": "Legacy Asset"},
        image_url="https://pub-brandmuse.r2.dev/image1.png",
        provider="stability",
        size_bytes=None,
        created_at=datetime.datetime.now(datetime.UTC),
    )

    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = [new_gen, legacy_gen]
    mock_db.execute.return_value = mock_res

    with patch.object(settings, "R2_PUBLIC_URL", "https://media.example.com"):
        resp = await client.get(
            "/api/images?limit=1&offset=0",
            headers={"X-Session-Id": str(session_id)},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["has_more"] is True
    assert data["limit"] == 1
    assert data["offset"] == 0
    assert len(data["generations"]) == 1
    assert (
        data["generations"][0]["image_url"]
        == "https://media.example.com/brandmuse/generations/owner1/img1.webp"
    )
    assert (
        data["generations"][0]["thumbnail_url"]
        == "https://media.example.com/brandmuse/generations/owner1/img1-thumb.webp"
    )
    assert data["generations"][0]["size_bytes"] == 4200

    # Also test legacy row direct read when returned
    mock_res.scalars.return_value.all.return_value = [legacy_gen]
    with patch.object(settings, "R2_PUBLIC_URL", "https://media.example.com"):
        resp2 = await client.get("/api/images", headers={"X-Session-Id": str(session_id)})
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["has_more"] is False
    assert data2["generations"][0]["image_url"] == "https://pub-brandmuse.r2.dev/image1.png"
    assert data2["generations"][0]["thumbnail_url"] == "https://pub-brandmuse.r2.dev/image1.png"


@pytest.mark.asyncio
async def test_admin_usage_endpoint(
    client: AsyncClient,
    mock_db: AsyncMock,
) -> None:
    """Verify GET /api/admin/usage checks ADMIN_TOKEN safely and reports quota usage."""
    with patch.object(settings, "ADMIN_TOKEN", ""):
        resp_unconfigured = await client.get("/api/admin/usage")
        assert resp_unconfigured.status_code == 503

    with patch.object(settings, "ADMIN_TOKEN", "super-secret-admin-token"):
        resp_missing = await client.get("/api/admin/usage")
        assert resp_missing.status_code == 401

        resp_wrong = await client.get(
            "/api/admin/usage", headers={"Authorization": "Bearer wrong-token"}
        )
        assert resp_wrong.status_code == 401

        counter_res = MagicMock()
        counter_res.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = counter_res

        with (
            patch(
                "app.routers.admin.GenerationRepository.get_storage_usage_stats",
                AsyncMock(return_value=(1024 * 1024 * 512, 10, 2)),
            ),
            patch.object(settings, "R2_BUCKET_NAME", "brandmuse"),
            patch.object(settings, "R2_KEY_PREFIX", "brandmuse"),
            patch.object(settings, "R2_APP_QUOTA_MB", 2048),
        ):
            resp_ok = await client.get(
                "/api/admin/usage",
                headers={"Authorization": "Bearer super-secret-admin-token"},
            )

        assert resp_ok.status_code == 200
        body = resp_ok.json()
        assert body["bucket"] == "brandmuse"
        assert body["prefix"] == "brandmuse"
        assert body["used_bytes"] == 1024 * 1024 * 512
        assert body["quota_bytes"] == 1024 * 1024 * 2048
        assert body["percent_used"] == 25.0
        assert body["total_generations"] == 10
        assert body["legacy_unknown_size_count"] == 2
