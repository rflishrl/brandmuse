import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.providers.embeddings import BaseEmbeddingProvider
from app.rag.retrieve import hybrid_retrieve


class DummyEmbeddingProvider(BaseEmbeddingProvider):
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * 1536 for _ in texts]

    async def embed_query(self, _text: str) -> list[float]:
        return [0.1] * 1536


@pytest.mark.asyncio
async def test_hybrid_retrieve_merges_vector_and_keyword() -> None:
    """Verify hybrid_retrieve runs a single combined CTE query and merges scores with RRF."""
    doc_id = uuid.uuid4()
    chunk1_id = uuid.uuid4()
    chunk2_id = uuid.uuid4()

    mock_db = AsyncMock()

    # Single combined CTE execute call returns (id, page, chunk_index, content, metric, source)
    # Vector metric is cosine distance (0.1 -> similarity 0.90), keyword metric is ts_rank_cd
    combined_rows = [
        (chunk1_id, 1, 0, "Our primary tone is calm and articulate.", 0.1, "vector"),
        (chunk2_id, 2, 1, "Forbidden words include revolutionary and disruption.", 0.3, "vector"),
        (chunk2_id, 2, 1, "Forbidden words include revolutionary and disruption.", 0.8, "keyword"),
        (chunk1_id, 1, 0, "Our primary tone is calm and articulate.", 0.2, "keyword"),
    ]
    mock_result = MagicMock()
    mock_result.all.return_value = combined_rows
    mock_db.execute.return_value = mock_result

    dummy_provider = DummyEmbeddingProvider()
    results = await hybrid_retrieve(
        db=mock_db,
        document_id=doc_id,
        query_text="tone of voice",
        top_k=5,
        embedding_provider=dummy_provider,
    )

    # Executed in exactly 1 DB round trip (no SET LOCAL, no concurrent AsyncSession gather)
    assert mock_db.execute.await_count == 1
    assert len(results) == 2
    ids = [r.item_id for r in results]
    assert str(chunk1_id) in ids
    assert str(chunk2_id) in ids

    r1 = next(r for r in results if r.item_id == str(chunk1_id))
    assert r1.vector_score == 0.90
    assert r1.keyword_score == 0.2
    assert r1.vector_rank == 1
    assert r1.keyword_rank == 2
    assert r1.metadata["page"] == 1


def test_query_expansion_bilingual_and_colloquial() -> None:
    """Verify expand_query_for_retrieval and build_fts_query_expression extract domain keywords."""
    from app.rag.query import build_fts_query_expression, expand_query_for_retrieval

    # Indonesian colloquial question
    query = "apa warna primer brand ini?"
    expanded = expand_query_for_retrieval(query)
    assert "color" in expanded
    assert "primary" in expanded

    fts_expr = build_fts_query_expression(query)
    assert "color" in fts_expr
    assert "primary" in fts_expr
    assert "or" in fts_expr

    # English query with stop words
    en_query = "what is the permitted logo clearspace?"
    en_expanded = expand_query_for_retrieval(en_query)
    assert "logo" in en_expanded
    en_fts = build_fts_query_expression(en_query)
    assert "clearspace" in en_fts or "logo" in en_fts
