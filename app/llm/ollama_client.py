"""
Клиент для работы с Ollama API.
Поддерживает: чат, генерацию, эмбеддинги, проверку доступности.
"""
import httpx
import logging
from typing import Generator

from app.config import config
from app.llm.base_client import BaseLLMClient

logger = logging.getLogger(__name__)


class OllamaClient(BaseLLMClient):
    """Клиент Ollama — общение с локальной LLM."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        embedding_model: str | None = None,
        temperature: float | None = None,
    ):
        self.base_url = (base_url or config.ollama.base_url).rstrip("/")
        self.model = model or config.ollama.model
        self.embedding_model = embedding_model or config.ollama.embedding_model
        self.temperature = temperature if temperature is not None else config.ollama.temperature
        self.timeout = config.ollama.timeout

    # ------------------------------------------------------------------
    # Проверка соединения
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Проверяет, доступен ли сервер Ollama."""
        try:
            resp = httpx.get(f"{self.base_url}/api/tags", timeout=5)
            return resp.status_code == 200
        except httpx.ConnectError:
            logger.error("Ollama недоступна — сервер не отвечает")
            return False

    def list_models(self) -> list[str]:
        """Список установленных моделей."""
        try:
            resp = httpx.get(f"{self.base_url}/api/tags", timeout=5)
            resp.raise_for_status()
            data = resp.json()
            return [m["name"] for m in data.get("models", [])]
        except Exception as e:
            logger.error(f"Ошибка получения списка моделей: {e}")
            return []

    def model_exists(self, model_name: str | None = None) -> bool:
        """Проверяет, установлена ли модель."""
        name = model_name or self.model
        models = self.list_models()
        # Сравниваем с учётом того, что модель может быть 'qwen2.5:7b' или 'qwen2.5:7b-latest'
        return any(name in m or m.startswith(name.split(":")[0]) for m in models)

    # ------------------------------------------------------------------
    # Генерация (одиночный запрос)
    # ------------------------------------------------------------------

    def generate(
        self,
        prompt: str,
        system: str = "",
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Отправляет промпт и возвращает ответ целиком."""
        model = model or self.model
        temp = temperature if temperature is not None else self.temperature

        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temp,
                "top_p": config.ollama.top_p,
                "num_ctx": config.ollama.num_ctx,
            },
        }
        if system:
            payload["system"] = system
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        try:
            resp = httpx.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            response_text = data.get("response", "")
            logger.debug(f"Ollama generate: {len(response_text)} символов")
            return response_text
        except httpx.TimeoutException:
            logger.error(f"Таймаут генерации ({self.timeout}с)")
            return "[Ошибка: таймаут генерации]"
        except Exception as e:
            logger.error(f"Ошибка генерации: {e}")
            return f"[Ошибка: {e}]"

    # ------------------------------------------------------------------
    # Чат (с историей сообщений)
    # ------------------------------------------------------------------

    def chat(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float | None = None,
    ) -> str:
        """Чат с историей. messages = [{'role': 'user'/'assistant'/'system', 'content': '...'}]."""
        model = model or self.model
        temp = temperature if temperature is not None else self.temperature

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temp,
                "top_p": config.ollama.top_p,
                "num_ctx": config.ollama.num_ctx,
            },
        }

        try:
            resp = httpx.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            content = data.get("message", {}).get("content", "")
            logger.debug(f"Ollama chat: {len(content)} символов")
            return content
        except httpx.TimeoutException:
            logger.error(f"Таймаут чата ({self.timeout}с)")
            return "[Ошибка: таймаут чата]"
        except Exception as e:
            logger.error(f"Ошибка чата: {e}")
            return f"[Ошибка: {e}]"

    # ------------------------------------------------------------------
    # Стриминг (генератор)
    # ------------------------------------------------------------------

    def chat_stream(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float | None = None,
    ) -> Generator[str, None, None]:
        """Стриминг ответа — для GUI (Gradio Chatbot)."""
        model = model or self.model
        temp = temperature if temperature is not None else self.temperature

        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temp,
                "top_p": config.ollama.top_p,
                "num_ctx": config.ollama.num_ctx,
            },
        }

        try:
            with httpx.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.timeout,
            ) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line:
                        continue
                    import json
                    chunk = json.loads(line)
                    token = chunk.get("message", {}).get("content", "")
                    if token:
                        yield token
        except Exception as e:
            logger.error(f"Ошибка стриминга: {e}")
            yield f"[Ошибка: {e}]"

    # ------------------------------------------------------------------
    # Эмбеддинги
    # ------------------------------------------------------------------

    def embed(self, text: str, model: str | None = None) -> list[float]:
        """Получить эмбеддинг для текста."""
        model = model or self.embedding_model

        payload = {
            "model": model,
            "input": text,
        }

        try:
            resp = httpx.post(
                f"{self.base_url}/api/embed",
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            embeddings = data.get("embeddings", [[]])
            if embeddings and len(embeddings) > 0:
                return embeddings[0]
            return []
        except Exception as e:
            logger.error(f"Ошибка получения эмбеддинга: {e}")
            return []

    def embed_batch(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        """Получить эмбеддинги для нескольких текстов."""
        model = model or self.embedding_model

        payload = {
            "model": model,
            "input": texts,
        }

        try:
            resp = httpx.post(
                f"{self.base_url}/api/embed",
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("embeddings", [])
        except Exception as e:
            logger.error(f"Ошибка batch-эмбеддинга: {e}")
            return []
