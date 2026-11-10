import uuid

from fastapi import APIRouter, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import APIError
from app.core.security import get_session_id
from app.db.models import Document
from app.db.repositories import DocumentRepository, OntologyRepository
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
    for_mutation: bool = False,
) -> Document:
    """Helper delegating to DocumentRepository for document retrieval and access validation."""
    return await DocumentRepository.get_by_id(
        db, document_id, session_id=session_id, for_mutation=for_mutation
    )


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
    doc = await _get_document_or_404(db, document_id, session_id, for_mutation=True)

    # Check daily LLM usage limits
    await check_and_increment_daily_usage(db, "llm", settings.DAILY_LLM_LIMIT)

    # Extract structured ontology
    ontology_data = await extract_brand_ontology_from_doc(db, doc, session_id)

    # Upsert BrandOntology record via repository
    record = await OntologyRepository.upsert(
        db=db,
        document_id=document_id,
        ontology_data=ontology_data.model_dump(),
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
    await _get_document_or_404(db, document_id, session_id, for_mutation=False)

    record = await OntologyRepository.get_by_document_id(db, document_id)

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
    await _get_document_or_404(db, document_id, session_id, for_mutation=True)

    record = await OntologyRepository.update_data(
        db=db,
        document_id=document_id,
        ontology_data=payload.ontology.model_dump(),
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
    await _get_document_or_404(db, document_id, session_id, for_mutation=True)

    record = await OntologyRepository.certify(
        db=db,
        document_id=document_id,
        certified_by=payload.certified_by,
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
