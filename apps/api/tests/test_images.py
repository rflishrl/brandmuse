import datetime
import io
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from PIL import Image

from app.core.errors import APIError
from app.db.models import Generation
from app.providers.image import MockImageProvider, moderate_prompt


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

    # 9:16 (vertical story / reels)
    img_9_16 = await provider.generate_image("Vertical story", aspect_ratio="9:16")
    im1 = Image.open(io.BytesIO(img_9_16))
    assert im1.size == (576, 1024)

    # 16:9 (horizontal banner)
    img_16_9 = await provider.generate_image("Landscape banner", aspect_ratio="16:9")
    im2 = Image.open(io.BytesIO(img_16_9))
    assert im2.size == (1024, 576)


@pytest.mark.asyncio
async def test_post_image_generation_endpoint(
    client: AsyncClient,
    mock_db: AsyncMock,
) -> None:
    """Verify POST /api/images generates image, uploads, and persists record."""
    session_id = str(uuid.uuid4())
    fake_url = "https://pub-brandmuse.r2.dev/test.png"

    mock_db.execute.return_value = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    with (
        patch("app.routers.images.check_session_image_hourly_limit", AsyncMock()),
        patch("app.routers.images.check_and_increment_daily_usage", AsyncMock(return_value=1)),
        patch("app.routers.images.get_image_provider", return_value=MockImageProvider()),
        patch("app.routers.images.upload_image_to_storage", AsyncMock(return_value=fake_url)),
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
        assert data["url"] == fake_url


@pytest.mark.asyncio
async def test_get_gallery_endpoint(
    client: AsyncClient,
    mock_db: AsyncMock,
) -> None:
    """Verify GET /api/images retrieves session's generation gallery."""
    session_id = uuid.uuid4()
    mock_gen = Generation(
        id=uuid.uuid4(),
        session_id=session_id,
        concept_json={"title": "Natural Sanctuary"},
        image_url="https://pub-brandmuse.r2.dev/image1.png",
        provider="mock",
        created_at=datetime.datetime.now(datetime.UTC),
    )

    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = [mock_gen]
    mock_db.execute.return_value = mock_res

    resp = await client.get("/api/images", headers={"X-Session-Id": str(session_id)})

    assert resp.status_code == 200
    data = resp.json()
    assert "generations" in data
    assert len(data["generations"]) == 1
    assert data["generations"][0]["concept_title"] == "Natural Sanctuary"
    assert data["generations"][0]["image_url"] == "https://pub-brandmuse.r2.dev/image1.png"
