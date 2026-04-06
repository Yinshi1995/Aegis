"""
LLM-клиент на базе llama-cpp-python.
Загружает GGUF-модели локально, без Ollama.
"""
import logging
from pathlib import Path
from typing import Generator

from app.config import config
from app.llm.base_client import BaseLLMClient

logger = logging.getLogger(__name__)


class LlamaCppClient(BaseLLMClient):
    """Клиент llama-cpp-python — локальный инференс GGUF-моделей."""

    def __init__(self):
        self._cfg = config.llamacpp
        self.model = Path(self._cfg.model_path).stem  # имя файла без расширения
        self._model = None       # Llama — ленивая загрузка
        self._embed_model = None  # Llama для эмбеддингов — ленивая загрузка

    # ------------------------------------------------------------------
    # Ленивая загрузка моделей
    # ------------------------------------------------------------------

    def _resolve_path(self, path_str: str) -> Path:
        """Решает путь — абсолютный или относительно корня проекта."""
        p = Path(path_str)
        if not p.is_absolute():
            p = config.project_root / p
        return p

    def _get_model(self):
        """Загружает chat-модель при первом обращении."""
        if self._model is None:
            from llama_cpp import Llama

            model_path = self._resolve_path(self._cfg.model_path)
            if not model_path.exists():
                raise FileNotFoundError(
                    f"GGUF-модель не найдена: {model_path}\n"
                    f"Скачайте модель и укажите путь в LLAMACPP_MODEL_PATH"
                )

            logger.info("Загрузка chat-модели: %s (GPU layers: %d)", model_path.name, self._cfg.n_gpu_layers)
            self._model = Llama(
                model_path=str(model_path),
                n_gpu_layers=self._cfg.n_gpu_layers,
                n_ctx=self._cfg.n_ctx,
                chat_format=self._cfg.chat_format,
                verbose=config.debug,
            )
            logger.info("Chat-модель загружена: %s", model_path.name)
        return self._model

    def _get_embed_model(self):
        """Загружает модель эмбеддингов при первом обращении."""
        if self._embed_model is None:
            from llama_cpp import Llama

            embed_path = self._resolve_path(self._cfg.embed_model_path)
            if not embed_path.exists():
                raise FileNotFoundError(
                    f"GGUF-модель эмбеддингов не найдена: {embed_path}\n"
                    f"Скачайте модель и укажите путь в LLAMACPP_EMBED_MODEL_PATH"
                )

            logger.info("Загрузка embed-модели: %s", embed_path.name)
            self._embed_model = Llama(
                model_path=str(embed_path),
                n_gpu_layers=self._cfg.n_gpu_layers,
                embedding=True,
                verbose=False,
            )
            logger.info("Embed-модель загружена: %s", embed_path.name)
        return self._embed_model

    # ------------------------------------------------------------------
    # BaseLLMClient interface
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Проверяет, существуют ли файлы .gguf по путям из конфига."""
        chat_path = self._resolve_path(self._cfg.model_path)
        embed_path = self._resolve_path(self._cfg.embed_model_path)
        return chat_path.exists() and embed_path.exists()

    def list_models(self) -> list[str]:
        """Список всех .gguf файлов в ./models/."""
        models_dir = config.project_root / "models"
        if not models_dir.exists():
            return []
        return sorted(f.name for f in models_dir.glob("*.gguf"))

    def generate(
        self,
        prompt: str,
        system: str = "",
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Генерация по промпту."""
        temp = temperature if temperature is not None else config.ollama.temperature
        max_tok = max_tokens or 1024

        try:
            llm = self._get_model()

            full_prompt = prompt
            if system:
                full_prompt = f"{system}\n\n{prompt}"

            result = llm(
                full_prompt,
                max_tokens=max_tok,
                temperature=temp,
                stop=["<|im_end|>", "<|endoftext|>"],
            )
            text = result["choices"][0]["text"].strip()
            logger.debug("LlamaCpp generate: %d символов", len(text))
            return text
        except Exception as e:
            logger.error("Ошибка генерации LlamaCpp: %s", e)
            return f"[Ошибка: {e}]"

    def chat(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float | None = None,
    ) -> str:
        """Чат с историей сообщений."""
        temp = temperature if temperature is not None else config.ollama.temperature

        try:
            llm = self._get_model()
            result = llm.create_chat_completion(
                messages=messages,
                temperature=temp,
            )
            content = result["choices"][0]["message"]["content"].strip()
            logger.debug("LlamaCpp chat: %d символов", len(content))
            return content
        except Exception as e:
            logger.error("Ошибка чата LlamaCpp: %s", e)
            return f"[Ошибка: {e}]"

    def chat_stream(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float | None = None,
    ) -> Generator[str, None, None]:
        """Стриминг ответа чата."""
        temp = temperature if temperature is not None else config.ollama.temperature

        try:
            llm = self._get_model()
            stream = llm.create_chat_completion(
                messages=messages,
                temperature=temp,
                stream=True,
            )
            for chunk in stream:
                delta = chunk["choices"][0].get("delta", {})
                token = delta.get("content", "")
                if token:
                    yield token
        except Exception as e:
            logger.error("Ошибка стриминга LlamaCpp: %s", e)
            yield f"[Ошибка: {e}]"

    def embed(self, text: str, model: str | None = None) -> list[float]:
        """Получить эмбеддинг для текста."""
        try:
            llm = self._get_embed_model()
            result = llm.embed(text)
            # llama-cpp-python embed() возвращает list[float] или list[list[float]]
            if result and isinstance(result[0], list):
                return result[0]
            return result
        except Exception as e:
            logger.error("Ошибка эмбеддинга LlamaCpp: %s", e)
            return []

    def embed_batch(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        """Получить эмбеддинги для списка текстов."""
        if not texts:
            return []

        try:
            llm = self._get_embed_model()
            # llama-cpp-python поддерживает batch через embed()
            all_embeddings = []
            for text in texts:
                emb = llm.embed(text)
                if emb and isinstance(emb[0], list):
                    all_embeddings.append(emb[0])
                else:
                    all_embeddings.append(emb)
            return all_embeddings
        except Exception as e:
            logger.error("Ошибка batch-эмбеддинга LlamaCpp: %s", e)
            return []
