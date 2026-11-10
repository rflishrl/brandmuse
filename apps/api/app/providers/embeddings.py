import time
from abc import ABC, abstractmethod
from collections import OrderedDict
from typing import Any

from app.core.config import get_settings
from app.core.errors import APIError
from app.core.http import get_http_client

settings = get_settings()


class QueryEmbeddingCache:
    """Thread-safe in-memory bounded LRU cache with TTL for query embeddings.

    Prevents redundant external API calls for repeated or similar user queries,
    saving network latency, CPU usage, and external AI token budget.
    """

    def __init__(self, maxsize: int = 1024, ttl_seconds: float = 3600.0) -> None:
        self.maxsize = maxsize
        self.ttl = ttl_seconds
        self._cache: OrderedDict[str, tuple[float, list[float]]] = OrderedDict()

    def get(self, key: str) -> list[float] | None:
        now = time.time()
        if key in self._cache:
            ts, emb = self._cache[key]
            if now - ts < self.ttl:
                self._cache.move_to_end(key)
                return emb
            del self._cache[key]
        return None

    def set(self, key: str, value: list[float]) -> None:
        now = time.time()
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = (now, value)
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

    async def embed_query(self, text: str) -> list[float]:
        """Embed a single query string, checking the in-memory LRU/TTL cache first."""
        cleaned = text.strip()
        if not cleaned:
            return [0.0] * settings.EMBEDDING_DIM

        model_name = getattr(self, "model", "default")
        cache_key = f"{self.__class__.__name__}:{model_name}:{cleaned.lower()}"
        cached = _query_cache.get(cache_key)
        if cached is not None:
            return cached

        results = await self._compute_embed_query(cleaned)
        _query_cache.set(cache_key, results)
        return results

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

        all_embeddings: list[list[float]] = []
        client = get_http_client()
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            response = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"input": batch, "model": self.model},
                timeout=30.0,
            )
            if response.status_code != 200:
                raise APIError(
                    code="EMBEDDING_ERROR",
                    message=f"OpenAI embedding failed: {response.text}",
                    status_code=502,
                )
            data: dict[str, Any] = response.json()
            sorted_items = sorted(data["data"], key=lambda x: x["index"])
            all_embeddings.extend([item["embedding"] for item in sorted_items])

        return all_embeddings


class OllamaEmbeddingProvider(BaseEmbeddingProvider):
    """Local Ollama embeddings via nomic-embed-text or all-minilm."""

    def __init__(self, base_url: str | None = None, model: str = "nomic-embed-text"):
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model = model

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        all_embeddings: list[list[float]] = []
        client = get_http_client()
        for text in texts:
            response = await client.post(
                f"{self.base_url}/api/embeddings",
                json={"model": self.model, "prompt": text},
                timeout=60.0,
            )
            if response.status_code != 200:
                raise APIError(
                    code="EMBEDDING_ERROR",
                    message=f"Ollama embedding failed: {response.text}",
                    status_code=502,
                )
            all_embeddings.append(response.json()["embedding"])

        return all_embeddings


class GeminiEmbeddingProvider(BaseEmbeddingProvider):
    """Google Gemini hosted embeddings via text-embedding-004 with zero-padding to target dim."""

    def __init__(self, api_key: str | None = None, model: str = "models/text-embedding-004"):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model = model
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

        all_embeddings: list[list[float]] = []
        target_dim = settings.EMBEDDING_DIM
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/"
            f"models/text-embedding-004:batchEmbedContents?key={self.api_key}"
        )

        client = get_http_client()
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            payload = {
                "requests": [
                    {
                        "model": self.model,
                        "content": {"parts": [{"text": t}]},
                    }
                    for t in batch
                ]
            }
            response = await client.post(url, json=payload, timeout=30.0)
            if response.status_code != 200:
                raise APIError(
                    code="EMBEDDING_ERROR",
                    message=f"Gemini embedding API failed: {response.text}",
                    status_code=502,
                )
            data = response.json()
            for item in data.get("embeddings", []):
                values: list[float] = item.get("values", [])
                # Zero-pad to target_dim if smaller (e.g. 768 to 1536 preserves cosine distance)
                if len(values) < target_dim:
                    values = values + [0.0] * (target_dim - len(values))
                elif len(values) > target_dim:
                    values = values[:target_dim]
                all_embeddings.append(values)

        return all_embeddings


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
