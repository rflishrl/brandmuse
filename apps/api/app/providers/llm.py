from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from app.core.config import get_settings
from app.core.errors import APIError
from app.core.http import get_http_client

settings = get_settings()

# Cache ChatOpenAI instances keyed by (provider, model, base_url, api_key, temp, max_tokens,
# streaming, http_client_id) to reuse connection pools and avoid per-call client instantiation.
_llm_cache: dict[tuple[str, str, str, str, float, int, bool, int], BaseChatModel] = {}


def get_llm(
    streaming: bool = True,
    temperature: float = 0.2,
    max_tokens: int = 1000,
) -> BaseChatModel:
    """Retrieve a cached, connection-pooled LLM provider instance (OpenAI, Gemini, or Ollama)."""
    provider = settings.LLM_PROVIDER.lower()

    if provider == "openai":
        if not settings.OPENAI_API_KEY:
            raise APIError(
                code="MISSING_API_KEY",
                message="OPENAI_API_KEY is not configured.",
                status_code=500,
            )
        http_client = get_http_client()
        cache_key = (
            "openai",
            "gpt-4o-mini",
            "",
            settings.OPENAI_API_KEY,
            temperature,
            max_tokens,
            streaming,
            id(http_client),
        )
        cached = _llm_cache.get(cache_key)
        if cached is not None:
            return cached
        instance = ChatOpenAI(
            model="gpt-4o-mini",
            api_key=SecretStr(settings.OPENAI_API_KEY),
            temperature=temperature,
            max_completion_tokens=max_tokens,
            streaming=streaming,
            http_async_client=http_client,
        )
        if len(_llm_cache) > 64:
            _llm_cache.clear()
        _llm_cache[cache_key] = instance
        return instance

    if provider == "gemini":
        gemini_key = settings.GEMINI_API_KEY.strip()
        if not gemini_key:
            raise APIError(
                code="MISSING_API_KEY",
                message="GEMINI_API_KEY is not configured.",
                status_code=500,
            )
        model_name = settings.GEMINI_MODEL.strip()
        base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
        http_client = get_http_client()
        cache_key = (
            "gemini",
            model_name,
            base_url,
            gemini_key,
            temperature,
            max_tokens,
            streaming,
            id(http_client),
        )
        cached = _llm_cache.get(cache_key)
        if cached is not None:
            return cached
        instance = ChatOpenAI(
            model=model_name,
            base_url=base_url,
            api_key=SecretStr(gemini_key),
            temperature=temperature,
            max_completion_tokens=max_tokens,
            streaming=streaming,
            http_async_client=http_client,
        )
        if len(_llm_cache) > 64:
            _llm_cache.clear()
        _llm_cache[cache_key] = instance
        return instance

    if provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model="llama3.2",
            base_url=settings.OLLAMA_BASE_URL,
            temperature=temperature,
            num_predict=max_tokens,
        )

    raise ValueError(f"Unsupported LLM provider: {provider}")
