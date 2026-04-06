"""
Альтернативный векторный стор — pgvector (PostgreSQL).
Тот же интерфейс, что у ChromaDB VectorStore.
"""
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.config import config
from app.rag.pdf_loader import Chunk
from app.rag.embeddings import get_embedding, get_embeddings_batch

logger = logging.getLogger(__name__)

# SQL для создания таблицы и индекса
_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS embeddings (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    source VARCHAR(500),
    page INTEGER,
    chunk_index INTEGER DEFAULT 0,
    embedding vector(768),
    created_at TIMESTAMP DEFAULT NOW()
);
"""

_CREATE_INDEX_SQL = """
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes WHERE indexname = 'embeddings_embedding_idx'
    ) THEN
        -- ivfflat требует минимум 1 строку; создаём только если есть данные
        IF (SELECT COUNT(*) FROM embeddings) > 0 THEN
            CREATE INDEX embeddings_embedding_idx
            ON embeddings USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100);
        END IF;
    END IF;
END
$$;
"""


class PgVectorStore:
    """Векторный стор на PostgreSQL + pgvector."""

    def __init__(self, database_url: str | None = None):
        self._database_url = database_url or config.database.database_url
        if not self._database_url:
            raise ValueError("DATABASE_URL не задан для PgVectorStore")

        self._engine = create_engine(
            self._database_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )
        self._Session = sessionmaker(bind=self._engine)
        self._ensure_table()
        logger.info(
            f"PgVectorStore инициализирован, документов: {self.count}"
        )

    def _ensure_table(self):
        """Создаёт расширение vector, таблицу и индекс если их нет."""
        with self._engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.execute(text(_CREATE_TABLE_SQL))
            conn.commit()

    def _ensure_index(self):
        """Создаёт ivfflat-индекс (если есть данные и индекса ещё нет)."""
        with self._engine.connect() as conn:
            conn.execute(text(_CREATE_INDEX_SQL))
            conn.commit()

    @property
    def count(self) -> int:
        """Количество документов в таблице."""
        with self._engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM embeddings"))
            return result.scalar() or 0

    def add_chunks(self, chunks: list[Chunk]) -> int:
        """Добавить чанки в pgvector.

        Args:
            chunks: Список Chunk с текстом и метаданными.

        Returns:
            Количество добавленных документов.
        """
        if not chunks:
            return 0

        texts = [c.text for c in chunks]

        logger.info(f"Генерация эмбеддингов для {len(texts)} чанков...")
        embeddings = get_embeddings_batch(texts)

        if len(embeddings) != len(texts):
            logger.error(
                f"Несовпадение: {len(texts)} текстов, {len(embeddings)} эмбеддингов"
            )
            return 0

        added = 0
        batch_size = 100
        with self._Session() as session:
            for i in range(0, len(chunks), batch_size):
                batch_chunks = chunks[i:i + batch_size]
                batch_embeddings = embeddings[i:i + batch_size]

                for chunk, emb in zip(batch_chunks, batch_embeddings):
                    emb_str = "[" + ",".join(str(x) for x in emb) + "]"
                    session.execute(
                        text("""
                            INSERT INTO embeddings (content, source, page, chunk_index, embedding)
                            VALUES (:content, :source, :page, :chunk_index, :embedding)
                        """),
                        {
                            "content": chunk.text,
                            "source": chunk.metadata.get("source", ""),
                            "page": chunk.metadata.get("page", 0),
                            "chunk_index": chunk.metadata.get("chunk_index", 0),
                            "embedding": emb_str,
                        },
                    )
                    added += 1

                session.commit()

        logger.info(f"Добавлено {added} чанков в pgvector")
        self._ensure_index()
        return added

    def search(self, query: str, top_k: int | None = None) -> list[dict]:
        """Поиск по запросу — возвращает top-k ближайших чанков.

        Args:
            query: Текст запроса.
            top_k: Количество результатов.

        Returns:
            Список словарей: [{"text": ..., "metadata": {...}, "score": ...}, ...]
            score — косинусное сходство (1 = идентичные, 0 = ортогональные).
        """
        top_k = top_k or config.rag.top_k

        query_embedding = get_embedding(query)
        if not query_embedding:
            logger.error("Не удалось получить эмбеддинг запроса")
            return []

        emb_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        with self._engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT content, source, page, chunk_index,
                           1 - (embedding <=> :query_vec::vector) AS score
                    FROM embeddings
                    ORDER BY embedding <=> :query_vec::vector
                    LIMIT :top_k
                """),
                {"query_vec": emb_str, "top_k": top_k},
            )
            rows = result.fetchall()

        search_results = []
        for row in rows:
            search_results.append({
                "text": row.content,
                "metadata": {
                    "source": row.source or "",
                    "page": row.page or 0,
                    "chunk_index": row.chunk_index or 0,
                },
                "score": round(float(row.score), 4),
                "distance": round(1.0 - float(row.score), 4),
            })

        return search_results

    def delete_collection(self):
        """Очистить таблицу embeddings (аналог удаления коллекции)."""
        with self._engine.connect() as conn:
            conn.execute(text("TRUNCATE TABLE embeddings"))
            conn.commit()
        logger.info("Таблица embeddings очищена")

    def get_sources(self) -> list[str]:
        """Получить список уникальных источников."""
        with self._engine.connect() as conn:
            result = conn.execute(
                text("SELECT DISTINCT source FROM embeddings WHERE source IS NOT NULL AND source != '' ORDER BY source")
            )
            return [row[0] for row in result.fetchall()]
