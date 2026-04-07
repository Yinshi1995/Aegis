"""
Абстрактный базовый класс для LLM-клиентов.
OllamaClient наследует этот интерфейс.
"""
from abc import ABC, abstractmethod
from typing import Generator


class BaseLLMClient(ABC):
    """Единый интерфейс для всех LLM-бэкендов."""

    # Имя текущей модели (устанавливается в подклассе)
    model: str = ""

    @abstractmethod
    def is_available(self) -> bool:
        """Проверяет, доступен ли бэкенд."""
        ...

    @abstractmethod
    def list_models(self) -> list[str]:
        """Список доступных моделей."""
        ...

    @abstractmethod
    def chat(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float | None = None,
    ) -> str:
        """Чат с историей. messages = [{'role': ..., 'content': ...}]."""
        ...

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system: str = "",
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Генерация по промпту (без истории)."""
        ...

    @abstractmethod
    def embed(self, text: str, model: str | None = None) -> list[float]:
        """Получить эмбеддинг для текста."""
        ...

    @abstractmethod
    def embed_batch(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        """Получить эмбеддинги для списка текстов."""
        ...

    def chat_stream(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float | None = None,
    ) -> Generator[str, None, None]:
        """Стриминг ответа. По умолчанию — fallback на chat()."""
        yield self.chat(messages, model=model, temperature=temperature)
