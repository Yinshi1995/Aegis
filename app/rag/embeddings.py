"""
Генерация эмбеддингов через Ollama (nomic-embed-text).
Обёртка над OllamaClient.embed / embed_batch.
"""
import logging
from app.llm.ollama_client import OllamaClient
from app.config import config

logger = logging.getLogger(__name__)

# Глобальный клиент (создаётся лениво)
_client: OllamaClient | None = None


def _get_client() -> OllamaClient:
    """Возвращает общий экземпляр OllamaClient."""
    global _client
    if _client is None:
        _client = OllamaClient()
    return _client


def get_embedding(text: str) -> list[float]:
    """Получить эмбеддинг одного текста.

    Args:
        text: Входной текст.

    Returns:
        Вектор эмбеддинга (list[float]).
    """
    client = _get_client()
    embedding = client.embed(text, model=config.ollama.embedding_model)
    if not embedding:
        logger.warning(f"Пустой эмбеддинг для текста длиной {len(text)}")
    return embedding


def get_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """Получить эмбеддинги для списка текстов (batch).

    Args:
        texts: Список строк.

    Returns:
        Список векторов эмбеддингов.
    """
    if not texts:
        return []

    client = _get_client()

    # Ollama поддерживает batch, но ограничим размер пачки
    batch_size = 50
    all_embeddings = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        embeddings = client.embed_batch(batch, model=config.ollama.embedding_model)

        if len(embeddings) != len(batch):
            logger.warning(
                f"Batch эмбеддинг: ожидалось {len(batch)}, получено {len(embeddings)}"
            )
            # Фоллбэк — по одному
            for text in batch:
                emb = client.embed(text, model=config.ollama.embedding_model)
                all_embeddings.append(emb)
        else:
            all_embeddings.extend(embeddings)

        logger.debug(f"Эмбеддинги: {i + len(batch)}/{len(texts)}")

    return all_embeddings


def embedding_dimension() -> int:
    """Узнать размерность эмбеддинга (нужно для ChromaDB).

    Returns:
        Размерность вектора.
    """
    test_emb = get_embedding("test")
    return len(test_emb) if test_emb else 0
