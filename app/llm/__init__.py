"""
LLM-фабрика — единый синглтон для всего приложения.
Возвращает OllamaClient или LlamaCppClient в зависимости от LLM_BACKEND.
"""
from app.config import config
from app.llm.base_client import BaseLLMClient

_client_instance: BaseLLMClient | None = None


def get_llm_client() -> BaseLLMClient:
    """Получить LLM-клиент (синглтон). Модель грузится один раз."""
    global _client_instance
    if _client_instance is None:
        if config.llm_backend == "llamacpp":
            from app.llm.llamacpp_client import LlamaCppClient
            _client_instance = LlamaCppClient()
        else:
            from app.llm.ollama_client import OllamaClient
            _client_instance = OllamaClient()
    return _client_instance


def reset_llm_client():
    """Сбросить синглтон (для тестов)."""
    global _client_instance
    _client_instance = None
