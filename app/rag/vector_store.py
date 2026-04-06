"""
Операции с векторным стором — ChromaDB (дефолт) или pgvector.
Фабрика get_vector_store() возвращает нужную реализацию по конфигу.
"""
import logging
from pathlib import Path
import chromadb

from app.config import config
from app.rag.pdf_loader import Chunk
from app.rag.embeddings import get_embedding, get_embeddings_batch

logger = logging.getLogger(__name__)


def get_vector_store():
    """Фабрика: возвращает ChromaVectorStore или PgVectorStore в зависимости от VECTOR_STORE_TYPE."""
    if config.database.vector_store_type == "pgvector":
        from app.rag.vector_store_pgvector import PgVectorStore
        return PgVectorStore()
    return VectorStore()


class VectorStore:
    """Обёртка над ChromaDB для хранения и поиска чанков."""

    def __init__(
        self,
        collection_name: str | None = None,
        persist_directory: str | None = None,
    ):
        self.collection_name = collection_name or config.rag.collection_name
        persist_dir = persist_directory or config.rag.persist_directory

        # Абсолютный путь
        persist_path = Path(persist_dir)
        if not persist_path.is_absolute():
            persist_path = config.project_root / persist_path
        persist_path.mkdir(parents=True, exist_ok=True)

        self._client = chromadb.PersistentClient(path=str(persist_path))
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},  # косинусное расстояние
        )
        logger.info(
            f"VectorStore инициализирован: коллекция '{self.collection_name}', "
            f"документов: {self._collection.count()}"
        )

    @property
    def count(self) -> int:
        """Количество документов в коллекции."""
        return self._collection.count()

    def add_chunks(self, chunks: list[Chunk]) -> int:
        """Добавить чанки в коллекцию.

        Args:
            chunks: Список Chunk с текстом и метаданными.

        Returns:
            Количество добавленных документов.
        """
        if not chunks:
            return 0

        texts = [c.text for c in chunks]
        metadatas = [c.metadata for c in chunks]
        ids = [
            f"{c.metadata.get('source', 'unknown')}_{c.metadata.get('page', 0)}_{c.metadata.get('chunk_index', i)}"
            for i, c in enumerate(chunks)
        ]

        # Генерируем эмбеддинги
        logger.info(f"Генерация эмбеддингов для {len(texts)} чанков...")
        embeddings = get_embeddings_batch(texts)

        if len(embeddings) != len(texts):
            logger.error(
                f"Несовпадение: {len(texts)} текстов, {len(embeddings)} эмбеддингов"
            )
            return 0

        # Добавляем в ChromaDB (пачками, чтобы не превысить лимиты)
        batch_size = 100
        added = 0
        for i in range(0, len(texts), batch_size):
            end = min(i + batch_size, len(texts))
            self._collection.add(
                ids=ids[i:end],
                documents=texts[i:end],
                metadatas=metadatas[i:end],
                embeddings=embeddings[i:end],
            )
            added += end - i

        logger.info(f"Добавлено {added} чанков в коллекцию '{self.collection_name}'")
        return added

    def search(
        self,
        query: str,
        top_k: int | None = None,
    ) -> list[dict]:
        """Поиск по запросу — возвращает top-k ближайших чанков.

        Args:
            query: Текст запроса.
            top_k: Количество результатов (по умолчанию из конфига).

        Returns:
            Список словарей: [{"text": ..., "metadata": {...}, "score": ...}, ...]
            score — косинусное расстояние (меньше = ближе, 0 = идеал).
        """
        top_k = top_k or config.rag.top_k

        # Эмбеддинг запроса
        query_embedding = get_embedding(query)
        if not query_embedding:
            logger.error("Не удалось получить эмбеддинг запроса")
            return []

        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        # Преобразуем в удобный формат
        search_results = []
        if results and results["documents"]:
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                # ChromaDB cosine distance: 0 = идентичные, 2 = противоположные
                # Конвертируем в similarity score: 1 - distance/2 (0..1)
                similarity = 1.0 - dist / 2.0
                search_results.append({
                    "text": doc,
                    "metadata": meta,
                    "score": round(similarity, 4),
                    "distance": round(dist, 4),
                })

        return search_results

    def delete_collection(self):
        """Удалить коллекцию (для пересоздания индекса)."""
        self._client.delete_collection(self.collection_name)
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(f"Коллекция '{self.collection_name}' очищена")

    def get_sources(self) -> list[str]:
        """Получить список уникальных источников в коллекции."""
        all_meta = self._collection.get(include=["metadatas"])
        sources = set()
        if all_meta and all_meta["metadatas"]:
            for meta in all_meta["metadatas"]:
                src = meta.get("source", "")
                if src:
                    sources.add(src)
        return sorted(sources)
