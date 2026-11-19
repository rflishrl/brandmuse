"""Idempotent seeding service for the shared Aura Living sample brand guideline."""

import asyncio
import uuid
from pathlib import Path

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.db.models import Document
from app.db.repositories import DocumentRepository
from app.rag.ingest import ingest_pdf_document

SAMPLE_BRAND_FILENAME = "Aura Living - Brand Guidelines.pdf"
SAMPLE_SYSTEM_SESSION_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

_sample_seed_lock = asyncio.Lock()


def get_sample_pdf_path() -> Path | None:
    """Locate the single canonical sample PDF bundled inside app/assets."""
    asset_path = Path(__file__).resolve().parents[1] / "assets" / "sample-brand-guideline.pdf"
    if asset_path.is_file():
        return asset_path
    return None


async def ensure_sample_brand_seeded(
    db: AsyncSession,
    session_id: uuid.UUID = SAMPLE_SYSTEM_SESSION_ID,
) -> tuple[Document, int]:
    """Ensure the shared sample brand document exists, guarding against concurrent races."""
    existing = await DocumentRepository.get_sample_document(db)
    if existing:
        return existing, 0

    async with _sample_seed_lock:
        existing = await DocumentRepository.get_sample_document(db)
        if existing:
            return existing, 0

        sample_path = get_sample_pdf_path()
        if sample_path is None:
            raise APIError(
                code="SAMPLE_NOT_FOUND",
                message="Sample brand guideline PDF is missing from repository.",
                status_code=404,
            )

        pdf_bytes = sample_path.read_bytes()

        try:
            return await ingest_pdf_document(
                db=db,
                session_id=session_id,
                filename=SAMPLE_BRAND_FILENAME,
                pdf_bytes=pdf_bytes,
                is_sample=True,
            )
        except IntegrityError:
            # Another worker/process won the race on uq_documents_single_sample
            await db.rollback()
            existing = await DocumentRepository.get_sample_document(db)
            if existing:
                return existing, 0
            raise
