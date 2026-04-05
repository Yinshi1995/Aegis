"""
Тест Этапа 1: проверяем config, database, ollama_client.
"""
import sys
from pathlib import Path

# Добавляем корень проекта в PATH
sys.path.insert(0, str(Path(__file__).parent))

from app.config import config
from app.db.database import init_db, get_db
from app.llm.ollama_client import OllamaClient


def test_config():
    """Проверка конфигурации."""
    print("=== Тест config ===")
    print(f"  Модель: {config.ollama.model}")
    print(f"  Embedding: {config.ollama.embedding_model}")
    print(f"  БД: {config.skills.db_path}")
    print(f"  Температура: {config.ollama.temperature}")
    print("  [OK] Config загружен\n")


def test_database():
    """Проверка БД."""
    print("=== Тест database ===")
    engine = init_db()
    session = get_db()
    # Простая проверка — сессия работает
    result = session.execute(
        __import__("sqlalchemy").text("SELECT name FROM sqlite_master WHERE type='table'")
    )
    tables = [row[0] for row in result]
    print(f"  Таблицы: {tables}")
    session.close()
    print("  [OK] БД работает\n")


def test_ollama():
    """Проверка Ollama."""
    print("=== Тест Ollama ===")
    client = OllamaClient()

    # 1. Доступность
    available = client.is_available()
    print(f"  Доступна: {available}")
    if not available:
        print("  [FAIL] Ollama недоступна! Запустите: ollama serve")
        return False

    # 2. Модели
    models = client.list_models()
    print(f"  Модели: {models}")

    # 3. Проверка модели
    exists = client.model_exists()
    print(f"  Модель {client.model} установлена: {exists}")

    # 4. Простой generate
    print("  Отправляю тестовый запрос (generate)...")
    resp = client.generate("Скажи 'привет' одним словом.", system="Отвечай кратко.")
    print(f"  Ответ: {resp[:200]}")

    # 5. Чат
    print("  Отправляю тестовый запрос (chat)...")
    messages = [
        {"role": "system", "content": "Ты полезный ассистент. Отвечай кратко."},
        {"role": "user", "content": "Сколько будет 2+2?"},
    ]
    resp2 = client.chat(messages)
    print(f"  Ответ: {resp2[:200]}")

    print("  [OK] Ollama работает\n")
    return True


if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("  ТЕСТ ЭТАПА 1: Фундамент")
    print("=" * 50 + "\n")

    test_config()
    test_database()
    ok = test_ollama()

    if ok:
        print("=" * 50)
        print("  ЭТАП 1 ГОТОВ: Ollama отвечает!")
        print("=" * 50)
    else:
        print("  ЭТАП 1: есть проблемы, см. выше")
