import array
import asyncio
import time
from abc import ABC, abstractmethod
from collections import OrderedDict
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.errors import APIError
from app.core.http import get_http_client

settings = get_settings()

EMBEDDING_BATCH_CONCURRENCY = 4


class QueryEmbeddingCache:
    """Memory-compact bounded LRU cache with TTL for query embeddings.

    Stores embeddings as 32-bit float arrays (`array('f')`, matching PostgreSQL pgvector
    storage precision) instead of Python `list[float]` to cut memory footprint ~8x on
    memory-constrained containers (e.g. Render 512MB).
    """

    def __init__(self, maxsize: int = 512, ttl_seconds: float = 3600.0) -> None:
        self.maxsize = maxsize
        self.ttl = ttl_seconds
        self._cache: OrderedDict[str, tuple[float, array.array[float]]] = OrderedDict()

    def get(self, key: str) -> list[float] | None:
        now = time.time()
        if key in self._cache:
            ts, emb = self._cache[key]
            if now - ts < self.ttl:
                self._cache.move_to_end(key)
                return list(emb)
            del self._cache[key]
        return None

    def set(self, key: str, value: list[float]) -> None:
        now = time.time()
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = (now, array.array("f", value))
        if len(self._cache) > self.maxsize:
            self._cache.popitem(last=False)

    def clear(self) -> None:
        self._cache.clear()

    def size(self) -> int:
        return len(self._cache)


_query_cache = QueryEmbeddingCache()


def get_query_embedding_cache() -> QueryEmbeddingCache:
    """Access the global query embedding cache singleton."""
    return _query_cache


class BaseEmbeddingProvider(ABC):
    """Abstract base class for text embedding providers."""

    @abstractmethod
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of text strings in batches."""
        pass

    def _query_cache_key(self, cleaned: str) -> str:
        model_name = getattr(self, "model", "default")
        return f"{self.__class__.__name__}:{model_name}:{cleaned.lower()}"

    async def embed_query(self, text: str) -> list[float]:
        """Embed a single query string, checking the in-memory LRU/TTL cache first."""
        cleaned = text.strip()
        if not cleaned:
            return [0.0] * settings.EMBEDDING_DIM

        cache_key = self._query_cache_key(cleaned)
        cached = _query_cache.get(cache_key)
        if cached is not None:
            return cached

        results = await self._compute_embed_query(cleaned)
        _query_cache.set(cache_key, results)
        return results

    async def embed_queries(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple query strings in 1 batched call for cache misses."""
        if not texts:
            return []

        results: list[list[float] | None] = [None] * len(texts)
        missing_indices: list[int] = []
        missing_texts: list[str] = []
        missing_keys: list[str] = []

        for idx, raw in enumerate(texts):
            cleaned = raw.strip()
            if not cleaned:
                results[idx] = [0.0] * settings.EMBEDDING_DIM
                continue
            key = self._query_cache_key(cleaned)
            cached = _query_cache.get(key)
            if cached is not None:
                results[idx] = cached
            else:
                missing_indices.append(idx)
                missing_texts.append(cleaned)
                missing_keys.append(key)

        if missing_texts:
            computed = await self.embed_documents(missing_texts)
            for idx, key, vec in zip(missing_indices, missing_keys, computed, strict=True):
                _query_cache.set(key, vec)
                results[idx] = vec

        return [r if r is not None else [0.0] * settings.EMBEDDING_DIM for r in results]

    async def _compute_embed_query(self, text: str) -> list[float]:
        """Compute query embedding by delegating to embed_documents."""
        results = await self.embed_documents([text])
        if not results:
            return [0.0] * settings.EMBEDDING_DIM
        return results[0]


class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    """OpenAI hosted embeddings via text-embedding-3-small."""

    def __init__(self, api_key: str | None = None, model: str = "text-embedding-3-small"):
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model = model
        self.batch_size = 32

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if not self.api_key:
            raise APIError(
                code="MISSING_API_KEY",
                message="OPENAI_API_KEY is not configured.",
                status_code=500,
            )

        client = get_http_client()
        batches = [texts[i : i + self.batch_size] for i in range(0, len(texts), self.batch_size)]
        sem = asyncio.Semaphore(EMBEDDING_BATCH_CONCURRENCY)

        async def _embed_batch(batch: list[str]) -> list[list[float]]:
            async with sem:
                try:
                    response = await client.post(
                        "https://api.openai.com/v1/embeddings",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        json={"input": batch, "model": self.model},
                        timeout=30.0,
                    )
                except httpx.HTTPError as exc:
                    raise APIError(
                        code="EMBEDDING_ERROR",
                        message=f"OpenAI embedding request failed ({type(exc).__name__}): {exc}",
                        status_code=502,
                    ) from exc
                if response.status_code != 200:
                    raise APIError(
                        code="EMBEDDING_ERROR",
                        message=f"OpenAI embedding failed: {response.text}",
                        status_code=502,
                    )
                data: dict[str, Any] = response.json()
                sorted_items = sorted(data["data"], key=lambda x: x["index"])
                return [item["embedding"] for item in sorted_items]

        batch_results = await asyncio.gather(*(_embed_batch(b) for b in batches))
        return [vec for group in batch_results for vec in group]


class OllamaEmbeddingProvider(BaseEmbeddingProvider):
    """Local Ollama embeddings via nomic-embed-text or all-minilm."""

    def __init__(self, base_url: str | None = None, model: str = "nomic-embed-text"):
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model = model

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        client = get_http_client()
        # Prefer Ollama's native batch endpoint (/api/embed); fall back to legacy /api/embeddings.
        try:
            batch_res = await client.post(
                f"{self.base_url}/api/embed",
                json={"model": self.model, "input": texts},
                timeout=60.0,
            )
            if batch_res.status_code == 200:
                payload = batch_res.json()
                embeddings = payload.get("embeddings")
                if isinstance(embeddings, list) and len(embeddings) == len(texts):
                    return embeddings
            elif batch_res.status_code != 404:
                raise APIError(
                    code="EMBEDDING_ERROR",
                    message=f"Ollama embedding failed: {batch_res.text}",
                    status_code=502,
                )
        except httpx.HTTPError as exc:
            raise APIError(
                code="EMBEDDING_ERROR",
                message=f"Ollama embedding request failed ({type(exc).__name__}): {exc}",
                status_code=502,
            ) from exc

        all_embeddings: list[list[float]] = []
        for text in texts:
            try:
                response = await client.post(
                    f"{self.base_url}/api/embeddings",
                    json={"model": self.model, "prompt": text},
                    timeout=60.0,
                )
            except httpx.HTTPError as exc:
                raise APIError(
                    code="EMBEDDING_ERROR",
                    message=f"Ollama embedding request failed ({type(exc).__name__}): {exc}",
                    status_code=502,
                ) from exc
            if response.status_code != 200:
                raise APIError(
                    code="EMBEDDING_ERROR",
                    message=f"Ollama embedding failed: {response.text}",
                    status_code=502,
                )
            all_embeddings.append(response.json()["embedding"])

        return all_embeddings


class GeminiEmbeddingProvider(BaseEmbeddingProvider):
    """Google Gemini hosted embeddings via gemini-embedding-001 with MRL dimensionality."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = (api_key or settings.GEMINI_API_KEY).strip()
        raw_model = (model or settings.GEMINI_EMBEDDING_MODEL).strip()
        self.model = raw_model if raw_model.startswith("models/") else f"models/{raw_model}"
        self.batch_size = 32

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if not self.api_key:
            raise APIError(
                code="MISSING_API_KEY",
                message="GEMINI_API_KEY is not configured.",
                status_code=500,
            )

        target_dim = settings.EMBEDDING_DIM
        url = f"https://generativelanguage.googleapis.com/v1beta/{self.model}:batchEmbedContents"
        client = get_http_client()
        batches = [texts[i : i + self.batch_size] for i in range(0, len(texts), self.batch_size)]
        sem = asyncio.Semaphore(EMBEDDING_BATCH_CONCURRENCY)

        async def _embed_batch(batch: list[str]) -> list[list[float]]:
            async with sem:
                payload = {
                    "requests": [
                        {
                            "model": self.model,
                            "content": {"parts": [{"text": t}]},
                            "outputDimensionality": target_dim,
                        }
                        for t in batch
                    ]
                }
                try:
                    response = await client.post(
                        url,
                        headers={"x-goog-api-key": self.api_key},
                        json=payload,
                        timeout=30.0,
                    )
                except httpx.HTTPError as exc:
                    raise APIError(
                        code="EMBEDDING_ERROR",
                        message=f"Gemini embedding request failed ({type(exc).__name__}): {exc}",
                        status_code=502,
                    ) from exc
                if response.status_code != 200:
                    raise APIError(
                        code="EMBEDDING_ERROR",
                        message=f"Gemini embedding API failed: {response.text}",
                        status_code=502,
                    )
                data = response.json()
                out: list[list[float]] = []
                for item in data.get("embeddings", []):
                    values: list[float] = item.get("values", [])
                    if len(values) < target_dim:
                        values = values + [0.0] * (target_dim - len(values))
                    elif len(values) > target_dim:
                        values = values[:target_dim]
                    out.append(values)
                return out

        batch_results = await asyncio.gather(*(_embed_batch(b) for b in batches))
        return [vec for group in batch_results for vec in group]


def get_embedding_provider(name: str | None = None) -> BaseEmbeddingProvider:
    """Factory to retrieve the configured embedding provider."""
    provider_name = (name or settings.EMBEDDING_PROVIDER).lower()
    if provider_name == "openai":
        return OpenAIEmbeddingProvider()
    elif provider_name == "gemini":
        return GeminiEmbeddingProvider()
    elif provider_name == "ollama":
        return OllamaEmbeddingProvider()
    else:
        raise ValueError(f"Unsupported embedding provider: {provider_name}")
