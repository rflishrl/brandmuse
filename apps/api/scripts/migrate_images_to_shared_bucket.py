"""Migrate legacy PNG generation images from old r2.dev bucket to shared WebP keys.

Usage (from apps/api):
    uv run python scripts/migrate_images_to_shared_bucket.py --source-host pub-xxx.r2.dev
    uv run python scripts/migrate_images_to_shared_bucket.py --source-host pub-xxx.r2.dev --apply
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Allow running directly via `uv run python scripts/migrate_images_to_shared_bucket.py`
API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.core.config import get_settings  # noqa: E402
from app.core.logging import setup_logging, slogger  # noqa: E402
from app.db.models import Generation  # noqa: E402
from app.providers.image import MAX_PROVIDER_DOWNLOAD_BYTES, encode_webp_variants  # noqa: E402
from app.providers.storage import (  # noqa: E402
    build_generation_keys,
    delete_objects_sync,
    put_object_sync,
)


@dataclass
class MigrationItemResult:
    """Outcome for a single generation row."""

    generation_id: str
    old_url: str
    new_key: str | None = None
    thumb_key: str | None = None
    bytes_before: int = 0
    bytes_after: int = 0
    status: str = "pending"  # migrated | dry_run | skipped | failed
    error: str | None = None


def validate_legacy_source_url(url: str, allowed_host: str) -> str:
    """Ensure legacy download URL strictly uses HTTPS on the explicitly allowed old host."""
    normalized_allowed = allowed_host.strip().lower().rstrip(".")
    if not normalized_allowed:
        raise ValueError("--source-host must be a non-empty hostname.")

    parts = urlsplit(url)
    if parts.scheme.lower() != "https" or not parts.hostname:
        raise ValueError(f"Legacy URL must use HTTPS: {url!r}")
    if parts.username or parts.password or parts.port not in (None, 443):
        raise ValueError(f"Legacy URL contains disallowed credentials or port: {url!r}")

    host = parts.hostname.lower().rstrip(".")
    if host != normalized_allowed:
        raise ValueError(
            f"Legacy URL host {host!r} does not match --source-host {normalized_allowed!r}."
        )
    return url


async def download_legacy_image(
    client: httpx.AsyncClient,
    url: str,
    allowed_host: str,
    max_bytes: int = MAX_PROVIDER_DOWNLOAD_BYTES,
) -> bytes:
    """Download legacy image strictly from allowed_host without following cross-host redirects."""
    current_url = validate_legacy_source_url(url, allowed_host)
    res = await client.get(current_url, timeout=30.0, follow_redirects=False)
    if res.status_code != 200:
        raise RuntimeError(f"HTTP {res.status_code} downloading legacy image {current_url}")
    if len(res.content) > max_bytes:
        raise ValueError(f"Legacy image exceeds {max_bytes} bytes")
    return res.content


async def migrate_single_generation(
    *,
    gen_id: uuid.UUID,
    session_id: uuid.UUID,
    old_url: str,
    current_size_bytes: int | None,
    allowed_host: str,
    prefix: str,
    apply: bool,
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession] | None,
) -> MigrationItemResult:
    """Process one generation row idempotently."""
    # Already migrated to key with recorded size
    if not old_url.startswith(("http://", "https://")) and current_size_bytes is not None:
        return MigrationItemResult(
            generation_id=str(gen_id),
            old_url=old_url,
            new_key=old_url,
            status="skipped",
        )

    if old_url.startswith("data:"):
        return MigrationItemResult(
            generation_id=str(gen_id),
            old_url=old_url[:40],
            status="skipped",
        )

    try:
        raw_bytes = await download_legacy_image(client, old_url, allowed_host)
        full_webp, thumb_webp = await asyncio.to_thread(encode_webp_variants, raw_bytes)
        full_key, thumb_key = build_generation_keys(session_id, image_id=gen_id, prefix=prefix)
        total_after = len(full_webp) + len(thumb_webp)

        if not apply:
            slogger.info(
                "migration_dry_run_item",
                generation_id=str(gen_id),
                new_key=full_key,
                bytes_before=len(raw_bytes),
                bytes_after=total_after,
            )
            return MigrationItemResult(
                generation_id=str(gen_id),
                old_url=old_url,
                new_key=full_key,
                thumb_key=thumb_key,
                bytes_before=len(raw_bytes),
                bytes_after=total_after,
                status="dry_run",
            )

        await asyncio.to_thread(put_object_sync, full_key, full_webp, "image/webp")
        try:
            await asyncio.to_thread(put_object_sync, thumb_key, thumb_webp, "image/webp")
        except Exception:
            await asyncio.to_thread(delete_objects_sync, [full_key])
            raise

        if session_factory is None:
            raise RuntimeError("session_factory is required when apply=True")

        try:
            async with session_factory() as db:
                row = await db.get(Generation, gen_id)
                if row is not None:
                    row.image_url = full_key
                    row.size_bytes = total_after
                    await db.commit()
        except Exception:
            await asyncio.to_thread(delete_objects_sync, [full_key, thumb_key])
            raise

        slogger.info(
            "migration_applied_item",
            generation_id=str(gen_id),
            new_key=full_key,
            bytes_before=len(raw_bytes),
            bytes_after=total_after,
        )
        return MigrationItemResult(
            generation_id=str(gen_id),
            old_url=old_url,
            new_key=full_key,
            thumb_key=thumb_key,
            bytes_before=len(raw_bytes),
            bytes_after=total_after,
            status="migrated",
        )
    except Exception as exc:
        slogger.error(
            "migration_item_failed",
            generation_id=str(gen_id),
            old_url=old_url,
            error=str(exc),
        )
        return MigrationItemResult(
            generation_id=str(gen_id),
            old_url=old_url,
            status="failed",
            error=str(exc),
        )


async def run_migration(
    *,
    source_host: str,
    apply: bool = False,
    concurrency: int = 4,
    limit: int | None = None,
    map_file: Path = Path("migration_map.json"),
) -> dict[str, Any]:
    """Run idempotent legacy image migration against MIGRATION_DATABASE_URL."""
    settings = get_settings()
    settings.validate_storage_environment()
    prefix = settings.normalized_r2_prefix

    db_url = settings.effective_migration_db_url
    engine = create_async_engine(db_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    existing_map: dict[str, Any] = {}
    if map_file.exists():
        try:
            loaded = json.loads(map_file.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                existing_map = loaded
        except Exception:
            existing_map = {}

    try:
        async with session_factory() as db:
            stmt = (
                select(Generation)
                .where(
                    or_(
                        Generation.image_url.like("http%"),
                        Generation.size_bytes.is_(None),
                    )
                )
                .order_by(Generation.created_at.asc(), Generation.id.asc())
            )
            if limit is not None:
                stmt = stmt.limit(limit)
            res = await db.execute(stmt)
            candidates = list(res.scalars().all())

        semaphore = asyncio.Semaphore(max(1, min(concurrency, 10)))

        async with httpx.AsyncClient() as client:

            async def _bounded(gen: Generation) -> MigrationItemResult:
                async with semaphore:
                    return await migrate_single_generation(
                        gen_id=gen.id,
                        session_id=gen.session_id,
                        old_url=gen.image_url,
                        current_size_bytes=gen.size_bytes,
                        allowed_host=source_host,
                        prefix=prefix,
                        apply=apply,
                        client=client,
                        session_factory=session_factory if apply else None,
                    )

            results = await asyncio.gather(*(_bounded(g) for g in candidates))

        for item in results:
            if item.new_key and item.old_url.startswith("http"):
                existing_map[item.old_url] = {
                    "generation_id": item.generation_id,
                    "new_key": item.new_key,
                    "thumb_key": item.thumb_key,
                    "bytes_before": item.bytes_before,
                    "bytes_after": item.bytes_after,
                    "status": item.status,
                }

        map_file.parent.mkdir(parents=True, exist_ok=True)
        map_file.write_text(json.dumps(existing_map, indent=2), encoding="utf-8")

        summary = {
            "dry_run": not apply,
            "bucket": settings.R2_BUCKET_NAME,
            "prefix": prefix,
            "total_candidates": len(candidates),
            "succeeded": sum(1 for r in results if r.status in ("migrated", "dry_run")),
            "skipped": sum(1 for r in results if r.status == "skipped"),
            "failed": sum(1 for r in results if r.status == "failed"),
            "bytes_before": sum(r.bytes_before for r in results),
            "bytes_after": sum(r.bytes_after for r in results),
            "map_file": str(map_file),
        }
        return summary
    finally:
        await engine.dispose()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Migrate legacy PNG images from old r2.dev host to dual WebP keys in R2."
    )
    parser.add_argument(
        "--source-host",
        required=True,
        help="Exact hostname of the old public R2 bucket (e.g. pub-xxx.r2.dev).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Perform actual R2 uploads and DB updates. Omit for default --dry-run.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Simulate conversion and report sizes without modifying R2 or DB (default).",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=4,
        help="Max concurrent downloads/uploads (1..10, default 4).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional max number of candidate rows to process.",
    )
    parser.add_argument(
        "--map-file",
        type=Path,
        default=Path("migration_map.json"),
        help="Output JSON path mapping oldUrl -> newKey.",
    )
    return parser.parse_args(argv)


def main() -> None:
    setup_logging()
    args = parse_args()
    summary = asyncio.run(
        run_migration(
            source_host=args.source_host,
            apply=bool(args.apply),
            concurrency=args.concurrency,
            limit=args.limit,
            map_file=args.map_file,
        )
    )
    print(json.dumps(summary, indent=2))
    if summary["failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
