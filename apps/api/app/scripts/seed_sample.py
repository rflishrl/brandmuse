"""Idempotent CLI script to pre-seed the shared sample brand guideline."""

import asyncio
import logging

from app.core.logging import setup_logging
from app.db.session import async_session_factory, close_db
from app.services.sample_seed import ensure_sample_brand_seeded

logger = logging.getLogger(__name__)


async def seed_sample() -> None:
    """Seed the shared sample brand guideline if it does not already exist."""
    setup_logging()
    try:
        async with async_session_factory() as db:
            doc, chunk_count = await ensure_sample_brand_seeded(db)
            if chunk_count > 0:
                logger.info(
                    "Seeded sample brand guideline '%s' (id=%s, chunks=%d).",
                    doc.filename,
                    doc.id,
                    chunk_count,
                )
            else:
                logger.info(
                    "Sample brand guideline '%s' already exists (id=%s); skipped.",
                    doc.filename,
                    doc.id,
                )
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(seed_sample())
