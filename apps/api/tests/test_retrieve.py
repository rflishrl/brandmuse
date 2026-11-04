import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.models import Chunk
from app.providers.embeddings import BaseEmbeddingProvider
from app.rag.retrieve import hybrid_retrieve


class DummyEmbeddingProvider(BaseEmbeddingProvider):
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * 1536 for _ in texts]

    async def embed_query(self, _text: str) -> list[float]:
        return [0.1] * 1536


@pytest.mark.asyncio
async def test_hybrid_retrieve_merges_vector_and_keyword() -> None:
    """Verify hybrid_retrieve combines vector and keyword results with scores."""
    doc_id = uuid.uuid4()
    chunk1_id = uuid.uuid4()
    chunk2_id = uuid.uuid4()

    chunk1 = Chunk(
        id=chunk1_id,
        document_id=doc_id,
        page=1,
        chunk_index=0,
        content="Our primary tone is calm and articulate.",
    )
    chunk2 = Chunk(
        id=chunk2_id,
        document_id=doc_id,
        page=2,
        chunk_index=1,
        content="Forbidden words include revolutionary and disruption.",
    )

    mock_db = AsyncMock()

    # First execute call -> vector search results: (chunk, distance)
    # distance = 0.1 -> similarity = 0.90
    vector_rows = [(chunk1, 0.1), (chunk2, 0.3)]
    mock_vector_result = MagicMock()
    mock_vector_result.all.return_value = vector_rows

    # Second execute call -> keyword search results: (chunk, rank)
    keyword_rows = [(chunk2, 0.8), (chunk1, 0.2)]
    mock_keyword_result = MagicMock()
    mock_keyword_result.all.return_value = keyword_rows

    mock_db.execute.side_effect = [mock_vector_result, mock_keyword_result]

    dummy_provider = DummyEmbeddingProvider()
    results = await hybrid_retrieve(
        db=mock_db,
        document_id=doc_id,
        query_text="tone of voice",
        top_k=5,
        embedding_provider=dummy_provider,
    )

    assert len(results) == 2
    # Verify both chunks retrieved with fused scores and individual retriever metrics
    ids = [r.item_id for r in results]
    assert str(chunk1_id) in ids
    assert str(chunk2_id) in ids

    # Check that individual scores and ranks were properly tracked
    r1 = next(r for r in results if r.item_id == str(chunk1_id))
    assert r1.vector_score == 0.90
    assert r1.keyword_score == 0.2
    assert r1.vector_rank == 1
    assert r1.keyword_rank == 2
    assert r1.metadata["page"] == 1
