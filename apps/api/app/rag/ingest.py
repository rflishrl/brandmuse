import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chunk, Document
from app.providers.embeddings import BaseEmbeddingProvider, get_embedding_provider
from app.rag.chunk import chunk_pages
from app.rag.parse import parse_pdf_pages


async def ingest_pdf_document(
    db: AsyncSession,
    session_id: uuid.UUID,
    filename: str,
    pdf_bytes: bytes,
    is_sample: bool = False,
    embedding_provider: BaseEmbeddingProvider | None = None,
) -> tuple[Document, int]:
    """Parse, chunk, embed, and index a PDF document into PostgreSQL."""
    provider = embedding_provider or get_embedding_provider()

    # 1. Parse pages
    pages_data = await parse_pdf_pages(pdf_bytes)

    # 2. Chunk pages (never crossing page boundaries)
    chunks = chunk_pages(pages_data)

    # 3. Embed text chunks in batches
    texts = [c.content for c in chunks]
    embeddings = await provider.embed_documents(texts) if texts else []

    # 4. Save document record
    doc = Document(
        id=uuid.uuid4(),
        session_id=session_id,
        filename=filename,
        page_count=len(pages_data),
        is_sample=is_sample,
    )
    db.add(doc)
    await db.flush()

    # 5. Save chunk records with vector embeddings
    for idx, c in enumerate(chunks):
        embedding_val = embeddings[idx] if idx < len(embeddings) else None
        db_chunk = Chunk(
            id=uuid.uuid4(),
            document_id=doc.id,
            page=c.page,
            chunk_index=c.chunk_index,
            content=c.content,
            embedding=embedding_val,
        )
        db.add(db_chunk)

    await db.commit()
    await db.refresh(doc)

    return doc, len(chunks)
