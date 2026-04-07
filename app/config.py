"""
Конфигурация проекта.
Читает переменные из .env (если файл есть), иначе использует дефолты.
"""
import os
from pathlib import Path
from dataclasses import dataclass, field

from dotenv import load_dotenv

# Загружаем .env из корня проекта (override=True → .env главнее системных переменных)
_project_root = Path(__file__).parent.parent
load_dotenv(_project_root / ".env", override=True)


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default)


def _env_int(key: str, default: int = 0) -> int:
    return int(os.getenv(key, str(default)))


def _env_float(key: str, default: float = 0.0) -> float:
    return float(os.getenv(key, str(default)))


def _env_bool(key: str, default: bool = False) -> bool:
    return os.getenv(key, str(default)).lower() in ("1", "true", "yes")


@dataclass
class OllamaConfig:
    """Настройки Ollama."""
    base_url: str = field(default_factory=lambda: _env("OLLAMA_BASE_URL", "http://localhost:11434"))
    model: str = field(default_factory=lambda: _env("OLLAMA_MODEL", "qwen2.5:7b"))
    embedding_model: str = field(default_factory=lambda: _env("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text"))
    temperature: float = field(default_factory=lambda: _env_float("OLLAMA_TEMPERATURE", 0.1))
    top_p: float = field(default_factory=lambda: _env_float("OLLAMA_TOP_P", 0.9))
    num_ctx: int = field(default_factory=lambda: _env_int("OLLAMA_NUM_CTX", 8192))
    timeout: int = field(default_factory=lambda: _env_int("OLLAMA_TIMEOUT", 120))


@dataclass
class RAGConfig:
    """Настройки RAG пайплайна."""
    chunk_size: int = field(default_factory=lambda: _env_int("RAG_CHUNK_SIZE", 600))
    chunk_overlap: int = field(default_factory=lambda: _env_int("RAG_CHUNK_OVERLAP", 100))
    top_k: int = field(default_factory=lambda: _env_int("RAG_TOP_K", 5))
    relevance_threshold: float = field(default_factory=lambda: _env_float("RAG_RELEVANCE_THRESHOLD", 0.3))
    collection_name: str = field(default_factory=lambda: _env("RAG_COLLECTION_NAME", "knowledge_base"))
    persist_directory: str = field(default_factory=lambda: _env("RAG_PERSIST_DIR", "./data/chroma_db"))


@dataclass
class DatabaseConfig:
    """Настройки базы данных."""
    db_type: str = field(default_factory=lambda: _env("DATABASE_TYPE", "sqlite"))  # sqlite | postgres
    database_url: str = field(default_factory=lambda: _env("DATABASE_URL", "") or _env("POSTGRES_URL", ""))
    vector_store_type: str = field(default_factory=lambda: _env("VECTOR_STORE_TYPE", "chroma"))  # chroma | pgvector


@dataclass
class SkillsConfig:
    """Настройки системы скиллов."""
    db_path: str = field(default_factory=lambda: _env("SKILLS_DB_PATH", "./data/agent.db"))


@dataclass
class ToolsConfig:
    """Настройки инструментов."""
    browser_timeout: int = field(default_factory=lambda: _env_int("TOOLS_BROWSER_TIMEOUT", 30))
    headless: bool = field(default_factory=lambda: _env_bool("TOOLS_HEADLESS", True))
    whatsapp_session_dir: str = field(default_factory=lambda: _env("TOOLS_WHATSAPP_SESSION", "./data/whatsapp_session"))


@dataclass
class AppConfig:
    """Главная конфигурация."""
    project_root: Path = field(default_factory=lambda: _project_root)
    knowledge_base_dir: str = field(default_factory=lambda: _env("KNOWLEDGE_BASE_DIR", "./knowledge_base"))
    gui_host: str = field(default_factory=lambda: _env("GUI_HOST", "0.0.0.0"))
    gui_port: int = field(default_factory=lambda: _env_int("GUI_PORT", 7860))
    debug: bool = field(default_factory=lambda: _env_bool("DEBUG", True))
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    rag: RAGConfig = field(default_factory=RAGConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    skills: SkillsConfig = field(default_factory=SkillsConfig)
    tools: ToolsConfig = field(default_factory=ToolsConfig)


# Глобальный экземпляр
config = AppConfig()
