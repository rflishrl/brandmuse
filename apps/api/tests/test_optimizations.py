import time

import pytest

from app.core.http import close_http_client, get_http_client
from app.providers.embeddings import (
    BaseEmbeddingProvider,
    QueryEmbeddingCache,
    get_query_embedding_cache,
)


def test_query_embedding_cache_get_set() -> None:
    cache = QueryEmbeddingCache(maxsize=3, ttl_seconds=10.0)
    assert cache.get("key1") is None

    cache.set("key1", [0.1, 0.2, 0.3])
    cached = cache.get("key1")
    assert cached == pytest.approx([0.1, 0.2, 0.3], rel=1e-6)
    assert cache.size() == 1


def test_query_embedding_cache_ttl_expiration() -> None:
    cache = QueryEmbeddingCache(maxsize=10, ttl_seconds=0.01)
    cache.set("expire_key", [1.0, 2.0])
    time.sleep(0.02)
    assert cache.get("expire_key") is None


def test_query_embedding_cache_lru_eviction() -> None:
    cache = QueryEmbeddingCache(maxsize=2, ttl_seconds=60.0)
    cache.set("k1", [1.0])
    cache.set("k2", [2.0])
    # k1 and k2 are present
    assert cache.get("k1") == [1.0]  # moves k1 to most recently used
    cache.set("k3", [3.0])  # should evict k2, not k1

    assert cache.get("k2") is None
    assert cache.get("k1") == [1.0]
    assert cache.get("k3") == [3.0]


class SampleCachedProvider(BaseEmbeddingProvider):
    def __init__(self) -> None:
        self.model = "test-model"
        self.embed_docs_call_count = 0

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.embed_docs_call_count += 1
        return [[0.5] * 1536 for _ in texts]


@pytest.mark.asyncio
async def test_embed_query_hits_cache() -> None:
    provider = SampleCachedProvider()
    global_cache = get_query_embedding_cache()
    global_cache.clear()

    # First call: computes via embed_documents
    res1 = await provider.embed_query("Brand Primary Color")
    assert provider.embed_docs_call_count == 1
    assert len(res1) == 1536

    # Second call (same query, case-insensitive): served from memory cache without computing
    res2 = await provider.embed_query("brand primary color")
    assert provider.embed_docs_call_count == 1
    assert res1 == res2


@pytest.mark.asyncio
async def test_http_client_singleton_and_close() -> None:
    client1 = get_http_client()
    client2 = get_http_client()
    assert client1 is client2
    assert not client1.is_closed

    await close_http_client()
    assert client1.is_closed

    # Calling get_http_client again creates a fresh one
    client3 = get_http_client()
    assert not client3.is_closed
    await close_http_client()


@pytest.mark.asyncio
async def test_gemini_embedding_provider_uses_current_model_header_and_mrl_dim() -> None:
    from unittest.mock import AsyncMock, MagicMock, patch

    import httpx

    from app.providers.embeddings import GeminiEmbeddingProvider

    provider = GeminiEmbeddingProvider(api_key="  test-gemini-key  ", model="gemini-embedding-001")
    assert provider.model == "models/gemini-embedding-001"
    assert provider.api_key == "test-gemini-key"

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {"embeddings": [{"values": [0.1] * 1536}]}

    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("app.providers.embeddings.get_http_client", return_value=mock_client):
        vectors = await provider.embed_documents(["Brand guideline text"])

    assert len(vectors) == 1
    assert len(vectors[0]) == 1536
    call_args = mock_client.post.call_args
    assert call_args.args[0] == (
        "https://generativelanguage.googleapis.com/v1beta/"
        "models/gemini-embedding-001:batchEmbedContents"
    )
    assert call_args.kwargs["headers"] == {"x-goog-api-key": "test-gemini-key"}
    assert call_args.kwargs["json"]["requests"][0]["outputDimensionality"] == 1536
