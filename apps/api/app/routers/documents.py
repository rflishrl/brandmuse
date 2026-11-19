import uuid

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_session_id
from app.db.repositories import DocumentRepository
from app.db.session import get_db
from app.rag.ingest import ingest_pdf_document
from app.rag.parse import read_and_validate_pdf_stream
from app.schemas.documents import (
    DocumentListResponse,
    DocumentResponse,
    DocumentUploadResponse,
)
from app.services.sample_seed import ensure_sample_brand_seeded

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post(
    "",
    response_model=DocumentUploadResponse,
    operation_id="uploadDocument",
    summary="Upload Brand Guideline PDF",
    description="Streams and validates a guideline PDF (max 10MB, max 40 pages), then indexes it.",
)
async def upload_document(
    file: UploadFile = File(...),
    session_id: uuid.UUID = Depends(get_session_id),
    db: AsyncSession = Depends(get_db),
) -> DocumentUploadResponse:
    """Upload and index a user-provided brand guideline PDF."""
    pdf_bytes = await read_and_validate_pdf_stream(file)
    filename = file.filename or "brand-guideline.pdf"

    doc, chunk_count = await ingest_pdf_document(
        db=db,
        session_id=session_id,
        filename=filename,
        pdf_bytes=pdf_bytes,
        is_sample=False,
    )

    return DocumentUploadResponse(
        document=DocumentResponse(
            id=doc.id,
            filename=doc.filename,
            page_count=doc.page_count,
            is_sample=doc.is_sample,
            created_at=doc.created_at,
        ),
        chunk_count=chunk_count,
    )


@router.post(
    "/sample",
    response_model=DocumentUploadResponse,
    operation_id="loadSampleBrand",
    summary="Load Sample Brand Guideline",
    description="Loads the preloaded sample brand guideline ('Aura Living') for demo interaction.",
)
async def load_sample_brand(
    session_id: uuid.UUID = Depends(get_session_id),
    db: AsyncSession = Depends(get_db),
) -> DocumentUploadResponse:
    """Ensure the shared sample brand guideline is loaded and return its metadata."""
    doc, chunk_count = await ensure_sample_brand_seeded(db, session_id=session_id)

    return DocumentUploadResponse(
        document=DocumentResponse(
            id=doc.id,
            filename=doc.filename,
            page_count=doc.page_count,
            is_sample=True,
            created_at=doc.created_at,
        ),
        chunk_count=chunk_count,
    )


@router.get(
    "",
    response_model=DocumentListResponse,
    operation_id="listDocuments",
    summary="List Brand Guidelines",
    description="Returns guidelines uploaded by the current session plus the shared sample brand.",
)
async def list_documents(
    session_id: uuid.UUID = Depends(get_session_id),
    db: AsyncSession = Depends(get_db),
) -> DocumentListResponse:
    """List session-scoped documents and sample documents."""
    docs = await DocumentRepository.list_for_session(db, session_id)

    return DocumentListResponse(
        documents=[
            DocumentResponse(
                id=d.id,
                filename=d.filename,
                page_count=d.page_count,
                is_sample=d.is_sample,
                created_at=d.created_at,
            )
            for d in docs
        ]
    )
