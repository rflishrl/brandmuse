import io
import json
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from PIL import Image

from app.core.config import get_settings
from app.db.models import Generation
from scripts.migrate_images_to_shared_bucket import (
    migrate_single_generation,
    parse_args,
    run_migration,
    validate_legacy_source_url,
)

settings = get_settings()


def _make_png_bytes(size: tuple[int, int] = (600, 600)) -> bytes:
    img = Image.new("RGB", size, color=(34, 43, 39))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_parse_args_defaults_to_dry_run() -> None:
    args = parse_args(["--source-host", "pub-old.r2.dev"])
    assert args.apply is False
    assert args.dry_run is True
    assert args.concurrency == 4


def test_validate_legacy_source_url_restricts_host_and_scheme() -> None:
    assert (
        validate_legacy_source_url("https://pub-old.r2.dev/sess/1.png", "pub-old.r2.dev")
        == "https://pub-old.r2.dev/sess/1.png"
    )
    for bad in [
        "http://pub-old.r2.dev/sess/1.png",
        "https://evil.example.com/sess/1.png",
        "https://pub-old.r2.dev:8443/sess/1.png",
    ]:
        with pytest.raises(ValueError):
            validate_legacy_source_url(bad, "pub-old.r2.dev")


@pytest.mark.asyncio
async def test_migrate_single_generation_dry_run_and_apply() -> None:
    gen_id = uuid.uuid4()
    session_id = uuid.uuid4()
    png_bytes = _make_png_bytes()
    old_url = f"https://pub-old.r2.dev/{session_id}/img.png"

    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=httpx.Response(200, content=png_bytes))

    with (
        patch.object(settings, "MEDIA_OWNER_SECRET", "mig-secret"),
        patch("scripts.migrate_images_to_shared_bucket.put_object_sync") as mock_put,
    ):
        dry_res = await migrate_single_generation(
            gen_id=gen_id,
            session_id=session_id,
            old_url=old_url,
            current_size_bytes=None,
            allowed_host="pub-old.r2.dev",
            prefix="brandmuse-dev",
            apply=False,
            client=mock_client,
            session_factory=None,
        )
        assert dry_res.status == "dry_run"
        assert dry_res.new_key is not None
        assert dry_res.new_key.startswith("brandmuse-dev/generations/")
        assert dry_res.new_key.endswith(f"/{gen_id}.webp")
        assert dry_res.thumb_key is not None and dry_res.thumb_key.endswith("-thumb.webp")
        assert dry_res.bytes_before == len(png_bytes)
        assert dry_res.bytes_after > 0
        mock_put.assert_not_called()

        # Apply mode updates DB and uploads dual WebP variants without deleting old bucket
        fake_row = Generation(
            id=gen_id,
            session_id=session_id,
            concept_json={"title": "Old"},
            image_url=old_url,
            provider="mock",
            size_bytes=None,
        )
        fake_db = AsyncMock()
        fake_db.get = AsyncMock(return_value=fake_row)
        fake_db.commit = AsyncMock()

        class _FakeSessionCtx:
            async def __aenter__(self) -> AsyncMock:
                return fake_db

            async def __aexit__(self, *_args: object) -> None:
                return None

        apply_res = await migrate_single_generation(
            gen_id=gen_id,
            session_id=session_id,
            old_url=old_url,
            current_size_bytes=None,
            allowed_host="pub-old.r2.dev",
            prefix="brandmuse-dev",
            apply=True,
            client=mock_client,
            session_factory=lambda: _FakeSessionCtx(),  # type: ignore[arg-type, return-value]
        )
        assert apply_res.status == "migrated"
        assert mock_put.call_count == 2
        assert fake_row.image_url == apply_res.new_key
        assert fake_row.size_bytes == apply_res.bytes_after

        # Idempotent skip when already migrated
        skip_res = await migrate_single_generation(
            gen_id=gen_id,
            session_id=session_id,
            old_url=str(apply_res.new_key),
            current_size_bytes=apply_res.bytes_after,
            allowed_host="pub-old.r2.dev",
            prefix="brandmuse-dev",
            apply=True,
            client=mock_client,
            session_factory=None,
        )
        assert skip_res.status == "skipped"


@pytest.mark.asyncio
async def test_run_migration_writes_map_file(tmp_path: Path) -> None:
    gen_id = uuid.uuid4()
    session_id = uuid.uuid4()
    old_url = f"https://pub-old.r2.dev/{session_id}/one.png"
    candidate = Generation(
        id=gen_id,
        session_id=session_id,
        concept_json={"title": "Legacy"},
        image_url=old_url,
        provider="stability",
        size_bytes=None,
    )

    fake_res = MagicMock()
    fake_res.scalars.return_value.all.return_value = [candidate]
    fake_db = AsyncMock()
    fake_db.execute = AsyncMock(return_value=fake_res)

    class _FakeSessionCtx:
        async def __aenter__(self) -> AsyncMock:
            return fake_db

        async def __aexit__(self, *_args: object) -> None:
            return None

    fake_engine = MagicMock()
    fake_engine.dispose = AsyncMock()

    map_path = tmp_path / "map.json"
    png_bytes = _make_png_bytes()

    with (
        patch.object(settings, "ENVIRONMENT", "development"),
        patch.object(settings, "STORAGE_PROVIDER", "r2"),
        patch.object(settings, "R2_BUCKET_NAME", "brandmuse"),
        patch.object(settings, "R2_KEY_PREFIX", "brandmuse-dev"),
        patch.object(settings, "MEDIA_OWNER_SECRET", "mig-secret"),
        patch(
            "scripts.migrate_images_to_shared_bucket.create_async_engine",
            return_value=fake_engine,
        ),
        patch(
            "scripts.migrate_images_to_shared_bucket.async_sessionmaker",
            return_value=lambda: _FakeSessionCtx(),
        ),
        patch(
            "httpx.AsyncClient.get",
            AsyncMock(return_value=httpx.Response(200, content=png_bytes)),
        ),
    ):
        summary = await run_migration(
            source_host="pub-old.r2.dev",
            apply=False,
            map_file=map_path,
        )

    assert summary["dry_run"] is True
    assert summary["total_candidates"] == 1
    assert summary["succeeded"] == 1
    assert summary["failed"] == 0
    mapping = json.loads(map_path.read_text(encoding="utf-8"))
    assert old_url in mapping
    assert mapping[old_url]["new_key"].startswith("brandmuse-dev/generations/")
