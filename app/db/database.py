"""
Подключение к SQLite и управление сессиями.
Создаёт все таблицы при инициализации.
"""
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from app.skills.models import Base
from app.config import config
import logging

logger = logging.getLogger(__name__)


def _get_db_path() -> Path:
    """Возвращает абсолютный путь к файлу БД, создаёт директорию если нужно."""
    db_path = Path(config.skills.db_path)
    if not db_path.is_absolute():
        db_path = config.project_root / db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


def get_engine():
    """Создаёт и возвращает SQLAlchemy engine."""
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
    Base.metadata.create_all(engine)
    logger.info(f"БД инициализирована: {_get_db_path()}")
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
