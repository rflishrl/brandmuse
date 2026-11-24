"""Idempotent seeding service for the shared Aura Living sample brand guideline."""

import asyncio
import uuid
from pathlib import Path

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.db.models import BrandOntology, Document
from app.db.repositories import DocumentRepository, OntologyRepository
from app.rag.ingest import ingest_pdf_document
from app.rag.ontology import extract_brand_ontology_from_doc

SAMPLE_BRAND_FILENAME = "Aura Living - Brand Guidelines.pdf"
SAMPLE_CERTIFIED_BY = "Aura Living Official Guidelines"
SAMPLE_SYSTEM_SESSION_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

_sample_seed_lock = asyncio.Lock()
_sample_ontology_lock = asyncio.Lock()


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

        # Release read transaction before disk I/O, PDF parsing, and embedding API calls
        await db.rollback()
        pdf_bytes = await asyncio.to_thread(sample_path.read_bytes)

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


async def ensure_sample_ontology_seeded(
    db: AsyncSession,
    doc: Document,
    session_id: uuid.UUID = SAMPLE_SYSTEM_SESSION_ID,
) -> BrandOntology:
    """Ensure the read-only sample brand document has its canonical certified ontology."""
    existing = await OntologyRepository.get_by_document_id(db, doc.id)
    if existing:
        return existing

    async with _sample_ontology_lock:
        existing = await OntologyRepository.get_by_document_id(db, doc.id)
        if existing:
            return existing

        ontology_data = await extract_brand_ontology_from_doc(db, doc, session_id)
        try:
            return await OntologyRepository.upsert(
                db=db,
                document_id=doc.id,
                ontology_data=ontology_data.model_dump(),
                is_certified=True,
                certified_by=SAMPLE_CERTIFIED_BY,
            )
        except IntegrityError:
            await db.rollback()
            existing = await OntologyRepository.get_by_document_id(db, doc.id)
            if existing:
                return existing
            raise
