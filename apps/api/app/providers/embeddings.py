from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.errors import APIError

settings = get_settings()


class BaseEmbeddingProvider(ABC):
    """Abstract base class for text embedding providers."""

    @abstractmethod
    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of text strings in batches."""
        pass

    @abstractmethod
    async def embed_query(self, text: str) -> list[float]:
        """Embed a single query string."""
        pass


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
        async with httpx.AsyncClient(timeout=30.0) as client:
            for i in range(0, len(texts), self.batch_size):
                batch = texts[i : i + self.batch_size]
                response = await client.post(
                    "https://api.openai.com/v1/embeddings",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={"input": batch, "model": self.model},
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

    async def embed_query(self, text: str) -> list[float]:
        results = await self.embed_documents([text])
        return results[0]


class OllamaEmbeddingProvider(BaseEmbeddingProvider):
    """Local Ollama embeddings via nomic-embed-text or all-minilm."""

    def __init__(self, base_url: str | None = None, model: str = "nomic-embed-text"):
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.model = model

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        all_embeddings: list[list[float]] = []
        async with httpx.AsyncClient(timeout=60.0) as client:
            for text in texts:
                response = await client.post(
                    f"{self.base_url}/api/embeddings",
                    json={"model": self.model, "prompt": text},
                )
                if response.status_code != 200:
                    raise APIError(
                        code="EMBEDDING_ERROR",
                        message=f"Ollama embedding failed: {response.text}",
                        status_code=502,
                    )
                all_embeddings.append(response.json()["embedding"])

        return all_embeddings

    async def embed_query(self, text: str) -> list[float]:
        results = await self.embed_documents([text])
        return results[0]


def get_embedding_provider(name: str | None = None) -> BaseEmbeddingProvider:
    """Factory to retrieve the configured embedding provider."""
    provider_name = (name or settings.EMBEDDING_PROVIDER).lower()
    if provider_name == "openai":
        return OpenAIEmbeddingProvider()
    elif provider_name == "ollama":
        return OllamaEmbeddingProvider()
    else:
        raise ValueError(f"Unsupported embedding provider: {provider_name}")
