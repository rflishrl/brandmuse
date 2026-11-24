import uuid
from typing import Any

from sqlalchemy import func, literal, select, union_all
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
    """Retrieve top-K chunks via vector cosine distance without over-fetching embeddings."""
    distance_col = Chunk.embedding.cosine_distance(query_embedding).label("distance")
    stmt = (
        select(Chunk.id, Chunk.page, Chunk.chunk_index, Chunk.content, distance_col)
        .where(Chunk.document_id == document_id)
        .where(Chunk.embedding.is_not(None))
        .order_by(distance_col.asc())
        .limit(limit)
    )

    result = await db.execute(stmt)
    ranked_items: list[RankedItem] = []
    for row in result.all():
        chunk_id, page, chunk_index, content, distance = row
        similarity = max(0.0, 1.0 - float(distance))
        ranked_items.append(
            RankedItem(
                item_id=str(chunk_id),
                score=round(similarity, 4),
                metadata={
                    "page": page,
                    "chunk_index": chunk_index,
                    "content": content,
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
    """Retrieve top-K chunks via Postgres FTS without over-fetching vector columns."""
    config_name = fts_config or settings.FTS_CONFIG
    fts_expr = build_fts_query_expression(query_text)
    if not fts_expr:
        return []

    ts_query = func.websearch_to_tsquery(config_name, fts_expr)
    rank_col = func.ts_rank_cd(Chunk.tsv, ts_query).label("rank")

    stmt = (
        select(Chunk.id, Chunk.page, Chunk.chunk_index, Chunk.content, rank_col)
        .where(Chunk.document_id == document_id)
        .where(Chunk.tsv.op("@@")(ts_query))
        .order_by(rank_col.desc())
        .limit(limit)
    )

    result = await db.execute(stmt)
    ranked_items: list[RankedItem] = []
    for row in result.all():
        chunk_id, page, chunk_index, content, rank = row
        ranked_items.append(
            RankedItem(
                item_id=str(chunk_id),
                score=round(float(rank), 4),
                metadata={
                    "page": page,
                    "chunk_index": chunk_index,
                    "content": content,
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
    query_embedding: list[float] | None = None,
    fts_config: str | None = None,
) -> list[FusedResult]:
    """Execute combined single-RTT vector + FTS CTE query and merge with Reciprocal Rank Fusion.

    Avoids concurrent operations on a single SQLAlchemy AsyncSession and avoids
    fetching Chunk.embedding / Chunk.tsv columns over the wire.
    """
    if query_embedding is None:
        provider = embedding_provider or get_embedding_provider()
        expanded_vector_query = expand_query_for_retrieval(query_text)
        query_embedding = await provider.embed_query(expanded_vector_query)

    candidate_limit = 20
    config_name = fts_config or settings.FTS_CONFIG
    fts_expr = build_fts_query_expression(query_text)

    distance_col = Chunk.embedding.cosine_distance(query_embedding)
    vec_cte = (
        select(
            Chunk.id.label("id"),
            Chunk.page.label("page"),
            Chunk.chunk_index.label("chunk_index"),
            Chunk.content.label("content"),
            distance_col.label("metric"),
            literal("vector").label("source"),
        )
        .where(Chunk.document_id == document_id)
        .where(Chunk.embedding.is_not(None))
        .order_by(distance_col.asc())
        .limit(candidate_limit)
        .cte("vec")
    )

    if fts_expr:
        ts_query = func.websearch_to_tsquery(config_name, fts_expr)
        rank_col = func.ts_rank_cd(Chunk.tsv, ts_query)
        kw_cte = (
            select(
                Chunk.id.label("id"),
                Chunk.page.label("page"),
                Chunk.chunk_index.label("chunk_index"),
                Chunk.content.label("content"),
                rank_col.label("metric"),
                literal("keyword").label("source"),
            )
            .where(Chunk.document_id == document_id)
            .where(Chunk.tsv.op("@@")(ts_query))
            .order_by(rank_col.desc())
            .limit(candidate_limit)
            .cte("kw")
        )
        stmt: Any = union_all(select(vec_cte), select(kw_cte))
    else:
        stmt = select(vec_cte)

    result = await db.execute(stmt)

    vector_results: list[RankedItem] = []
    keyword_results: list[RankedItem] = []

    for row in result.all():
        chunk_id, page, chunk_index, content, metric, source = row
        metadata = {
            "page": page,
            "chunk_index": chunk_index,
            "content": content,
        }
        if source == "vector":
            similarity = max(0.0, 1.0 - float(metric))
            vector_results.append(
                RankedItem(
                    item_id=str(chunk_id),
                    score=round(similarity, 4),
                    metadata=metadata,
                )
            )
        else:
            keyword_results.append(
                RankedItem(
                    item_id=str(chunk_id),
                    score=round(float(metric), 4),
                    metadata=metadata,
                )
            )

    # Ensure deterministic descending order within each branch before RRF ranking
    vector_results.sort(key=lambda item: item.score, reverse=True)
    keyword_results.sort(key=lambda item: item.score, reverse=True)

    fused = reciprocal_rank_fusion(vector_results, keyword_results, k=60)
    return fused[:top_k]
