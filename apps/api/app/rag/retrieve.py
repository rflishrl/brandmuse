import asyncio
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import Chunk
from app.providers.embeddings import BaseEmbeddingProvider, get_embedding_provider
from app.rag.query import build_fts_query_expression, expand_query_for_retrieval
from app.rag.rrf import FusedResult, RankedItem, reciprocal_rank_fusion

settings = get_settings()


async def search_vector_chunks(
    db: AsyncSession,
    document_id: uuid.UUID,
    query_embedding: list[float],
    limit: int = 20,
) -> list[RankedItem]:
    """Retrieve top-K chunks via vector cosine distance using HNSW index."""
    # Distance: 0 = identical, 2 = opposite. Similarity: 1 - (distance / 2)
    distance_col = Chunk.embedding.cosine_distance(query_embedding).label("distance")
    stmt = (
        select(Chunk, distance_col)
        .where(Chunk.document_id == document_id)
        .where(Chunk.embedding.is_not(None))
        .order_by(distance_col.asc())
        .limit(limit)
    )

    result = await db.execute(stmt)
    ranked_items: list[RankedItem] = []
    for chunk, distance in result.all():
        similarity = max(0.0, 1.0 - float(distance))
        ranked_items.append(
            RankedItem(
                item_id=str(chunk.id),
                score=round(similarity, 4),
                metadata={
                    "page": chunk.page,
                    "chunk_index": chunk.chunk_index,
                    "content": chunk.content,
                },
            )
        )
    return ranked_items


async def search_keyword_chunks(
    db: AsyncSession,
    document_id: uuid.UUID,
    query_text: str,
    limit: int = 20,
    fts_config: str | None = None,
) -> list[RankedItem]:
    """Retrieve top-K chunks via Postgres tsvector full-text search using GIN index."""
    config_name = fts_config or settings.FTS_CONFIG

    # Use websearch_to_tsquery with keyword expansion for high-recall brand search
    fts_expr = build_fts_query_expression(query_text)
    ts_query = func.websearch_to_tsquery(config_name, fts_expr)
    rank_col = func.ts_rank_cd(Chunk.tsv, ts_query).label("rank")

    stmt = (
        select(Chunk, rank_col)
        .where(Chunk.document_id == document_id)
        .where(Chunk.tsv.op("@@")(ts_query))
        .order_by(rank_col.desc())
        .limit(limit)
    )

    result = await db.execute(stmt)
    ranked_items: list[RankedItem] = []
    for chunk, rank in result.all():
        ranked_items.append(
            RankedItem(
                item_id=str(chunk.id),
                score=round(float(rank), 4),
                metadata={
                    "page": chunk.page,
                    "chunk_index": chunk.chunk_index,
                    "content": chunk.content,
                },
            )
        )
    return ranked_items


async def hybrid_retrieve(
    db: AsyncSession,
    document_id: uuid.UUID,
    query_text: str,
    top_k: int = 5,
    embedding_provider: BaseEmbeddingProvider | None = None,
) -> list[FusedResult]:
    """Execute concurrent vector & FTS queries and merge using Reciprocal Rank Fusion."""
    provider = embedding_provider or get_embedding_provider()

    # Expand query for vector search to bridge cross-lingual and colloquial phrasing
    expanded_vector_query = expand_query_for_retrieval(query_text)
    query_embedding = await provider.embed_query(expanded_vector_query)

    # Run vector and full-text searches concurrently
    vector_results, keyword_results = await asyncio.gather(
        search_vector_chunks(db, document_id, query_embedding, limit=20),
        search_keyword_chunks(db, document_id, query_text, limit=20),
    )

    # Fuse with RRF (k=60)
    fused = reciprocal_rank_fusion(vector_results, keyword_results, k=60)
    return fused[:top_k]
