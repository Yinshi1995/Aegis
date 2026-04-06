"""
Подключение к БД (SQLite или PostgreSQL) и управление сессиями.
Создаёт все таблицы при инициализации.
"""
from pathlib import Path
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from app.skills.models import Base as SkillsBase
from app.scheduler.models import Base as SchedulerBase
from app.config import config
import logging

logger = logging.getLogger(__name__)


def _get_db_path() -> Path:
    """Возвращает абсолютный путь к файлу БД (для SQLite), создаёт директорию если нужно."""
    db_path = Path(config.skills.db_path)
    if not db_path.is_absolute():
        db_path = config.project_root / db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


def _is_postgres() -> bool:
    """Проверяет, используется ли PostgreSQL."""
    return config.database.db_type == "postgres"


def get_engine():
    """Создаёт и возвращает SQLAlchemy engine (SQLite или PostgreSQL)."""
    if _is_postgres():
        database_url = config.database.database_url
        if not database_url:
            raise ValueError(
                "DATABASE_TYPE=postgres, но DATABASE_URL / POSTGRES_URL не задан"
            )
        engine = create_engine(
            database_url,
            echo=config.debug,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )
        logger.info(f"Подключение к PostgreSQL: {database_url.split('@')[-1]}")
        return engine

    # SQLite (дефолт)
    db_path = _get_db_path()
    engine = create_engine(
        f"sqlite:///{db_path}",
        echo=config.debug,
        pool_pre_ping=True,
    )

    # WAL-режим для лучшей конкурентности
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


def init_db(engine=None):
    """Создаёт все таблицы в БД."""
    if engine is None:
        engine = get_engine()

    # Для PostgreSQL — создаём расширение pgvector если нужно
    if _is_postgres() and config.database.vector_store_type == "pgvector":
        try:
            with engine.connect() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                conn.commit()
                logger.info("PostgreSQL: расширение vector активировано")
        except Exception as e:
            logger.warning(f"Не удалось создать расширение vector: {e}")

    SkillsBase.metadata.create_all(engine)
    SchedulerBase.metadata.create_all(engine)
    db_label = (
        config.database.database_url.split("@")[-1]
        if _is_postgres()
        else str(_get_db_path())
    )
    logger.info(f"БД инициализирована: {db_label}")
    return engine


def get_session_factory(engine=None) -> sessionmaker:
    """Возвращает фабрику сессий."""
    if engine is None:
        engine = get_engine()
    return sessionmaker(bind=engine, expire_on_commit=False)


# Ленивая инициализация глобальных объектов
_engine = None
_session_factory = None


def get_db() -> Session:
    """Получить сессию БД (для использования в with-блоке)."""
    global _engine, _session_factory
    if _engine is None:
        _engine = init_db()
        _session_factory = get_session_factory(_engine)
    return _session_factory()
