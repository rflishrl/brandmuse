import datetime
import uuid

from pydantic import BaseModel, Field


class DocumentResponse(BaseModel):
    """Document representation schema."""

    id: uuid.UUID = Field(..., description="Unique document ID")
    filename: str = Field(..., description="Original filename of the guideline")
    page_count: int = Field(..., description="Total pages extracted from the PDF")
    is_sample: bool = Field(..., description="Whether this is the preloaded sample brand guideline")
    created_at: datetime.datetime = Field(..., description="Timestamp of document ingestion")


class DocumentUploadResponse(BaseModel):
    """Response returned upon successful PDF upload and ingestion."""

    document: DocumentResponse = Field(..., description="Ingested document details")
    chunk_count: int = Field(..., description="Total indexed text chunks created")


class DocumentListResponse(BaseModel):
    """List of documents accessible in the current session."""

    documents: list[DocumentResponse] = Field(
        ..., description="Session guidelines plus sample brand"
    )
