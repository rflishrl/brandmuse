from langchain_core.language_models.chat_models import BaseChatModel
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from app.core.config import get_settings
from app.core.errors import APIError

settings = get_settings()


def get_llm(
    streaming: bool = True,
    temperature: float = 0.2,
    max_tokens: int = 1000,
) -> BaseChatModel:
    """Retrieve the configured LLM provider instance (OpenAI or Ollama)."""
    provider = settings.LLM_PROVIDER.lower()

    if provider == "openai":
        if not settings.OPENAI_API_KEY:
            raise APIError(
                code="MISSING_API_KEY",
                message="OPENAI_API_KEY is not configured.",
                status_code=500,
            )
        return ChatOpenAI(
            model="gpt-4o-mini",
            api_key=SecretStr(settings.OPENAI_API_KEY),
            temperature=temperature,
            max_completion_tokens=max_tokens,
            streaming=streaming,
        )
    elif provider == "ollama":
        return ChatOllama(
            model="llama3.2",
            base_url=settings.OLLAMA_BASE_URL,
            temperature=temperature,
            num_predict=max_tokens,
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")
