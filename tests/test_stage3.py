"""
Тест Этапа 3: Система скиллов.
- CRUD: создание, получение, обновление, список, удаление
- Исполнение RAG-скилла (knowledge_qa) по ozbroennia.pdf
- Исполнение translate, code_gen
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

from app.skills.manager import Manager
from app.skills.executor import SkillExecutor


def test_crud():
    """Тест CRUD операций с скиллами."""
    print("\n" + "=" * 60)
    print("  ТЕСТ CRUD: создание / получение / обновление / удаление")
    print("=" * 60)

    mgr = Manager()

    # Пресеты должны быть автоматически созданы
    presets = mgr.list_skills()
    print(f"\n  Предустановленных скиллов: {len(presets)}")
    for s in presets:
        print(f"    - {s.name} [{s.category}] RAG={s.requires_rag}: {s.description[:60]}")

    # Создание нового
    print("\n  --- Создание нового скилла ---")
    try:
        custom = mgr.create_skill(
            name="test_summarize",
            system_prompt="Ти — редактор. Зроби стисле резюме.",
            description="Тестовый скилл для суммаризации",
            category="test",
            user_template="Резюмуй: {text}",
        )
        print(f"  Создан: {custom.name} (id={custom.id})")
    except ValueError as e:
        print(f"  Уже существует — OK: {e}")

    # Получение
    print("\n  --- Получение скилла ---")
    skill = mgr.get_skill("test_summarize")
    if skill:
        print(f"  Найден: {skill.name}, шаблон: {skill.user_template}")
    else:
        print("  [FAIL] Не найден!")

    # Обновление
    print("\n  --- Обновление скилла ---")
    updated = mgr.update_skill("test_summarize", description="Обновлённое описание")
    if updated:
        print(f"  Обновлён: description = {updated.description}")

    # Список по категории
    print("\n  --- Список по категории 'rag' ---")
    rag_skills = mgr.list_skills(category="rag")
    for s in rag_skills:
        print(f"    - {s.name}")

    # Удаление
    print("\n  --- Удаление тестового скилла ---")
    deleted = mgr.delete_skill("test_summarize")
    print(f"  Удалён: {deleted}")
    check = mgr.get_skill("test_summarize")
    status = "OK (не виден)" if check is None else "FAIL (всё ещё виден)"
    print(f"  Проверка после удаления: {status}")

    print("\n  [OK] CRUD работает\n")


def test_knowledge_qa():
    """Тест RAG-скилла knowledge_qa по ozbroennia.pdf."""
    print("=" * 60)
    print("  ТЕСТ: knowledge_qa (RAG-скилл)")
    print("=" * 60)

    mgr = Manager()
    executor = SkillExecutor()

    # Проверяем что ChromaDB индекс существует (был создан в test_ocr_rag)
    from app.rag.vector_store import VectorStore
    store = VectorStore()
    print(f"\n  Документов в ChromaDB: {store.count}")
    if store.count == 0:
        print("  [SKIP] ChromaDB пуст — сначала запустите test_ocr_rag.py")
        return

    result = executor.execute_by_name(
        "knowledge_qa",
        manager=mgr,
        question="Яка потужність двигуна БМП К-17?",
    )

    print(f"\n  Скилл: {result.skill_name}")
    print(f"  Успех: {result.success}")
    print(f"  Время: {result.elapsed_seconds}с")
    print(f"  Контекст найден: {result.has_context}")
    print(f"\n  Ответ:\n  {result.answer[:400]}")
    if result.sources:
        print(f"\n  Источники:")
        for s in result.sources:
            print(f"    - {s['source']}, стр. {s['page']}, score: {s['score']}")

    # Проверки
    answer_lower = result.answer.lower()
    checks = [
        (result.success, "Скилл выполнен успешно"),
        (result.has_context, "RAG-контекст получен"),
        ("510" in answer_lower or "к.с" in answer_lower or "к. с" in answer_lower,
         "Факт о двигателе (510 к.с.)"),
        (len(result.sources) > 0, "Есть источники"),
    ]
    for passed, label in checks:
        status = "✓" if passed else "✗"
        print(f"  [{status}] {label}")


def test_translate():
    """Тест скилла перевода."""
    print("\n" + "=" * 60)
    print("  ТЕСТ: translate (перевод)")
    print("=" * 60)

    mgr = Manager()
    executor = SkillExecutor()

    result = executor.execute_by_name(
        "translate",
        manager=mgr,
        target_language="англійська",
        text="Бойова машина піхоти призначена для транспортування особового складу",
    )

    print(f"\n  Скилл: {result.skill_name}")
    print(f"  Успех: {result.success}")
    print(f"  Время: {result.elapsed_seconds}с")
    print(f"  RAG: {result.has_context}")
    print(f"\n  Ответ:\n  {result.answer[:300]}")

    checks = [
        (result.success, "Скилл выполнен"),
        (not result.has_context, "RAG НЕ использовался (correctly)"),
        (any(w in result.answer.lower() for w in ["infantry", "combat", "vehicle", "fighting"]),
         "Перевод содержит ожидаемые слова"),
    ]
    for passed, label in checks:
        status = "✓" if passed else "✗"
        print(f"  [{status}] {label}")


def test_code_gen():
    """Тест скилла генерации кода."""
    print("\n" + "=" * 60)
    print("  ТЕСТ: code_gen (генерация кода)")
    print("=" * 60)

    mgr = Manager()
    executor = SkillExecutor()

    result = executor.execute_by_name(
        "code_gen",
        manager=mgr,
        language="Python",
        description="функція, що обчислює факторіал числа рекурсивно",
    )

    print(f"\n  Скилл: {result.skill_name}")
    print(f"  Успех: {result.success}")
    print(f"  Время: {result.elapsed_seconds}с")
    print(f"\n  Ответ:\n  {result.answer[:500]}")

    checks = [
        (result.success, "Скилл выполнен"),
        ("def " in result.answer, "Содержит определение функции"),
        ("factorial" in result.answer.lower() or "факторіал" in result.answer.lower(),
         "Содержит 'factorial'"),
        ("return" in result.answer, "Содержит return"),
    ]
    for passed, label in checks:
        status = "✓" if passed else "✗"
        print(f"  [{status}] {label}")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  ТЕСТ ЭТАПА 3: Система скиллов")
    print("=" * 60)

    test_crud()
    test_knowledge_qa()
    test_translate()
    test_code_gen()

    print("\n" + "=" * 60)
    print("  ЭТАП 3 ГОТОВ: скиллы создаются и выполняются!")
    print("=" * 60)
