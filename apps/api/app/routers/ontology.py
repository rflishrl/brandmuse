import datetime
import uuid

from fastapi import APIRouter, Depends, Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import APIError
from app.core.security import get_session_id
from app.db.models import BrandOntology, Document
from app.db.session import get_db
from app.rag.ontology import extract_brand_ontology_from_doc
from app.schemas.ontology import (
    BrandOntologyCertify,
    BrandOntologyData,
    BrandOntologyResponse,
    BrandOntologyUpdate,
)
from app.services.usage import check_and_increment_daily_usage

settings = get_settings()

router = APIRouter(prefix="/api/documents", tags=["ontology"])


async def _get_document_or_404(
    db: AsyncSession,
    document_id: uuid.UUID,
    session_id: uuid.UUID,
) -> Document:
    """Helper to fetch a document and verify session isolation."""
    stmt = select(Document).where(Document.id == document_id)
    res = await db.execute(stmt)
    doc = res.scalar_one_or_none()

    if not doc or (doc.session_id != session_id and not doc.is_sample):
        raise APIError(
            code="DOCUMENT_NOT_FOUND",
            message="Brand guideline document not found or access denied.",
            status_code=404,
        )
    return doc


@router.post(
    "/{document_id}/ontology/extract",
    response_model=BrandOntologyResponse,
    summary="Extract Structured Brand Ontology",
    description=(
        "Analyzes the document's indexed text chunks to extract brand identity, "
        "colors, typography, and DOs/DONTs."
    ),
)
async def extract_ontology(
    document_id: uuid.UUID = Path(..., description="Target document ID"),
    session_id: uuid.UUID = Depends(get_session_id),
    db: AsyncSession = Depends(get_db),
) -> BrandOntologyResponse:
    """Extract brand rules ontology from guideline chunks using structured LLM output."""
    doc = await _get_document_or_404(db, document_id, session_id)

    # Check daily LLM usage limits
    await check_and_increment_daily_usage(db, "llm", settings.DAILY_LLM_LIMIT)

    # Extract structured ontology
    ontology_data = await extract_brand_ontology_from_doc(db, doc, session_id)

    # Upsert BrandOntology row
    stmt = select(BrandOntology).where(BrandOntology.document_id == document_id)
    res = await db.execute(stmt)
    existing_ontology = res.scalar_one_or_none()

    now = datetime.datetime.now(datetime.UTC)

    if existing_ontology:
        existing_ontology.ontology_data = ontology_data.model_dump()
        existing_ontology.is_certified = False
        existing_ontology.certified_at = None
        existing_ontology.certified_by = None
        existing_ontology.updated_at = now
        record = existing_ontology
    else:
        record = BrandOntology(
            id=uuid.uuid4(),
            document_id=document_id,
            ontology_data=ontology_data.model_dump(),
            is_certified=False,
            created_at=now,
            updated_at=now,
        )
        db.add(record)

    await db.commit()
    await db.refresh(record)

    return BrandOntologyResponse(
        id=record.id,
        document_id=record.document_id,
        is_certified=record.is_certified,
        certified_at=record.certified_at,
        certified_by=record.certified_by,
        created_at=record.created_at,
        updated_at=record.updated_at,
        ontology=BrandOntologyData(**record.ontology_data),
    )


@router.get(
    "/{document_id}/ontology",
    response_model=BrandOntologyResponse,
    summary="Get Extracted Brand Ontology",
    description="Retrieves the structured ontology and certified brand rules.",
)
async def get_ontology(
    document_id: uuid.UUID = Path(..., description="Target document ID"),
    session_id: uuid.UUID = Depends(get_session_id),
    db: AsyncSession = Depends(get_db),
) -> BrandOntologyResponse:
    """Get the current brand ontology for a document."""
    await _get_document_or_404(db, document_id, session_id)

    stmt = select(BrandOntology).where(BrandOntology.document_id == document_id)
    res = await db.execute(stmt)
    record = res.scalar_one_or_none()

    if not record:
        raise APIError(
            code="ONTOLOGY_NOT_FOUND",
            message="Brand ontology has not been extracted yet for this document.",
            status_code=404,
        )

    return BrandOntologyResponse(
        id=record.id,
        document_id=record.document_id,
        is_certified=record.is_certified,
        certified_at=record.certified_at,
        certified_by=record.certified_by,
        created_at=record.created_at,
        updated_at=record.updated_at,
        ontology=BrandOntologyData(**record.ontology_data),
    )


@router.put(
    "/{document_id}/ontology",
    response_model=BrandOntologyResponse,
    summary="Update Brand Ontology (Human-in-the-Loop Refinement)",
    description="Allows brand managers to edit and refine colors, typography, and rules.",
)
async def update_ontology(
    payload: BrandOntologyUpdate,
    document_id: uuid.UUID = Path(..., description="Target document ID"),
    session_id: uuid.UUID = Depends(get_session_id),
    db: AsyncSession = Depends(get_db),
) -> BrandOntologyResponse:
    """Update extracted brand ontology data."""
    await _get_document_or_404(db, document_id, session_id)

    stmt = select(BrandOntology).where(BrandOntology.document_id == document_id)
    res = await db.execute(stmt)
    record = res.scalar_one_or_none()

    if not record:
        raise APIError(
            code="ONTOLOGY_NOT_FOUND",
            message="Cannot update ontology: it has not been extracted yet.",
            status_code=404,
        )

    record.ontology_data = payload.ontology.model_dump()
    record.updated_at = datetime.datetime.now(datetime.UTC)

    await db.commit()
    await db.refresh(record)

    return BrandOntologyResponse(
        id=record.id,
        document_id=record.document_id,
        is_certified=record.is_certified,
        certified_at=record.certified_at,
        certified_by=record.certified_by,
        created_at=record.created_at,
        updated_at=record.updated_at,
        ontology=BrandOntologyData(**record.ontology_data),
    )


@router.post(
    "/{document_id}/ontology/certify",
    response_model=BrandOntologyResponse,
    summary="Certify Brand Ontology (Human-in-the-Loop Approval)",
    description="Marks the extracted brand rules as certified and verified by a brand manager.",
)
async def certify_ontology(
    payload: BrandOntologyCertify,
    document_id: uuid.UUID = Path(..., description="Target document ID"),
    session_id: uuid.UUID = Depends(get_session_id),
    db: AsyncSession = Depends(get_db),
) -> BrandOntologyResponse:
    """Certify brand ontology for official grounding and production usage."""
    await _get_document_or_404(db, document_id, session_id)

    stmt = select(BrandOntology).where(BrandOntology.document_id == document_id)
    res = await db.execute(stmt)
    record = res.scalar_one_or_none()

    if not record:
        raise APIError(
            code="ONTOLOGY_NOT_FOUND",
            message="Cannot certify ontology: it has not been extracted yet.",
            status_code=404,
        )

    now = datetime.datetime.now(datetime.UTC)
    record.is_certified = True
    record.certified_at = now
    record.certified_by = payload.certified_by
    record.updated_at = now

    await db.commit()
    await db.refresh(record)

    return BrandOntologyResponse(
        id=record.id,
        document_id=record.document_id,
        is_certified=record.is_certified,
        certified_at=record.certified_at,
        certified_by=record.certified_by,
        created_at=record.created_at,
        updated_at=record.updated_at,
        ontology=BrandOntologyData(**record.ontology_data),
    )
