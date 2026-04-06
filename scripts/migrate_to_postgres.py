"""
Миграция данных из SQLite + ChromaDB → PostgreSQL + pgvector.
Запускать вручную при переезде на Postgres:

    python -m scripts.migrate_to_postgres

Предварительно:
  - PostgreSQL запущен, DATABASE_URL задан в .env
  - pip install pgvector psycopg2-binary
"""
import sys
import logging
from pathlib import Path

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.config import config
from app.skills.models import Base as SkillsBase, Skill

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def migrate_skills(pg_url: str, sqlite_path: str):
    """Копирует скиллы из SQLite в PostgreSQL."""
    logger.info("=== Миграция скиллов ===")

    # Источник — SQLite
    src_engine = create_engine(f"sqlite:///{sqlite_path}")
    SrcSession = sessionmaker(bind=src_engine)

    # Приёмник — PostgreSQL
    dst_engine = create_engine(pg_url)
    SkillsBase.metadata.create_all(dst_engine)
    DstSession = sessionmaker(bind=dst_engine)

    with SrcSession() as src_sess, DstSession() as dst_sess:
        skills = src_sess.query(Skill).all()
        logger.info(f"Найдено скиллов в SQLite: {len(skills)}")

        migrated = 0
        for skill in skills:
            # Проверяем, нет ли уже в Postgres
            existing = dst_sess.query(Skill).filter_by(name=skill.name).first()
            if existing:
                logger.info(f"  Скилл '{skill.name}' уже существует — пропускаем")
                continue

            new_skill = Skill(
                name=skill.name,
                description=skill.description,
                category=skill.category,
                system_prompt=skill.system_prompt,
                user_template=skill.user_template,
                script_path=skill.script_path,
                script_params_schema=skill.script_params_schema,
                requires_rag=skill.requires_rag,
                temperature=skill.temperature,
                created_at=skill.created_at,
                updated_at=skill.updated_at,
                is_active=skill.is_active,
            )
            dst_sess.add(new_skill)
            migrated += 1

        dst_sess.commit()
        logger.info(f"Мигрировано скиллов: {migrated}")


def migrate_vectors(pg_url: str, chroma_dir: str, collection_name: str):
    """Копирует чанки из ChromaDB в pgvector."""
    logger.info("=== Миграция векторов (ChromaDB → pgvector) ===")

    import chromadb

    chroma_path = Path(chroma_dir)
    if not chroma_path.is_absolute():
        chroma_path = config.project_root / chroma_path

    if not chroma_path.exists():
        logger.warning(f"Директория ChromaDB не найдена: {chroma_path}")
        return

    client = chromadb.PersistentClient(path=str(chroma_path))

    try:
        collection = client.get_collection(collection_name)
    except Exception:
        logger.warning(f"Коллекция '{collection_name}' не найдена в ChromaDB")
        return

    total = collection.count()
    logger.info(f"Документов в ChromaDB: {total}")
    if total == 0:
        return

    # Получаем все данные из ChromaDB
    data = collection.get(include=["documents", "metadatas", "embeddings"])

    # Подключаемся к PostgreSQL
    engine = create_engine(pg_url)
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS embeddings (
                id SERIAL PRIMARY KEY,
                content TEXT NOT NULL,
                source VARCHAR(500),
                page INTEGER,
                chunk_index INTEGER DEFAULT 0,
                embedding vector(768),
                created_at TIMESTAMP DEFAULT NOW()
            )
        """))
        conn.commit()

    migrated = 0
    with engine.connect() as conn:
        for i in range(len(data["ids"])):
            doc = data["documents"][i] if data["documents"] else ""
            meta = data["metadatas"][i] if data["metadatas"] else {}
            emb = data["embeddings"][i] if data["embeddings"] else None

            if not emb:
                logger.warning(f"  Пропускаем документ без эмбеддинга: {data['ids'][i]}")
                continue

            emb_str = "[" + ",".join(str(x) for x in emb) + "]"

            conn.execute(
                text("""
                    INSERT INTO embeddings (content, source, page, chunk_index, embedding)
                    VALUES (:content, :source, :page, :chunk_index, :embedding)
                """),
                {
                    "content": doc,
                    "source": meta.get("source", ""),
                    "page": meta.get("page", 0),
                    "chunk_index": meta.get("chunk_index", 0),
                    "embedding": emb_str,
                },
            )
            migrated += 1

            if migrated % 100 == 0:
                conn.commit()
                logger.info(f"  Мигрировано: {migrated}/{total}")

        conn.commit()

    # Создаём индекс
    if migrated > 0:
        with engine.connect() as conn:
            try:
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS embeddings_embedding_idx
                    ON embeddings USING ivfflat (embedding vector_cosine_ops)
                    WITH (lists = 100)
                """))
                conn.commit()
                logger.info("ivfflat-индекс создан")
            except Exception as e:
                logger.warning(f"Не удалось создать индекс: {e}")

    logger.info(f"Мигрировано векторов: {migrated}")


def main():
    pg_url = config.database.database_url
    if not pg_url:
        logger.error(
            "DATABASE_URL / POSTGRES_URL не задан в .env. "
            "Укажите URL PostgreSQL для миграции."
        )
        sys.exit(1)

    sqlite_path = Path(config.skills.db_path)
    if not sqlite_path.is_absolute():
        sqlite_path = config.project_root / sqlite_path

    logger.info(f"Источник SQLite: {sqlite_path}")
    logger.info(f"Приёмник PostgreSQL: {pg_url.split('@')[-1]}")

    # Миграция скиллов
    if sqlite_path.exists():
        migrate_skills(pg_url, str(sqlite_path))
    else:
        logger.warning(f"SQLite файл не найден: {sqlite_path}")

    # Миграция векторов
    migrate_vectors(
        pg_url,
        config.rag.persist_directory,
        config.rag.collection_name,
    )

    logger.info("=== Миграция завершена ===")


if __name__ == "__main__":
    main()
