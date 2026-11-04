import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.core.security import get_session_id
from app.db.models import Document
from app.db.session import get_db
from app.rag.ingest import ingest_pdf_document
from app.rag.parse import read_and_validate_pdf_stream
from app.schemas.documents import (
    DocumentListResponse,
    DocumentResponse,
    DocumentUploadResponse,
)

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
    # Check if a sample document already exists
    stmt = select(Document).where(Document.is_sample.is_(True)).limit(1)
    result = await db.execute(stmt)
    existing_sample = result.scalar_one_or_none()

    if existing_sample:
        return DocumentUploadResponse(
            document=DocumentResponse(
                id=existing_sample.id,
                filename=existing_sample.filename,
                page_count=existing_sample.page_count,
                is_sample=True,
                created_at=existing_sample.created_at,
            ),
            chunk_count=0,
        )

    # Locate sample PDF on disk
    sample_path = Path(__file__).resolve().parents[4] / "samples" / "sample-brand-guideline.pdf"
    if not sample_path.exists():
        raise APIError(
            code="SAMPLE_NOT_FOUND",
            message="Sample brand guideline PDF is missing from repository.",
            status_code=404,
        )

    with open(sample_path, "rb") as f:
        pdf_bytes = f.read()

    doc, chunk_count = await ingest_pdf_document(
        db=db,
        session_id=session_id,
        filename="Aura Living - Brand Guidelines.pdf",
        pdf_bytes=pdf_bytes,
        is_sample=True,
    )

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
    stmt = (
        select(Document)
        .where(or_(Document.session_id == session_id, Document.is_sample.is_(True)))
        .order_by(Document.created_at.desc())
    )
    result = await db.execute(stmt)
    docs = result.scalars().all()

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
