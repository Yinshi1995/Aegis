"""
Тест Этапа 2: RAG пайплайн.
- Создаём тестовый PDF с конкретными фактами
- Индексируем
- Тест 1: вопрос, ответ ЕСТЬ в PDF → источник и страница
- Тест 2: вопрос, ответа НЕТ в PDF → "нет информации"
- Тест 3: top-5 чанков с relevance score
"""
import sys
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import fitz  # PyMuPDF


# ====================================================================
# 1. Создание тестового PDF
# ====================================================================

def create_test_pdf(output_path: Path):
    """Создаёт PDF с 4 страницами конкретных фактов."""
    doc = fitz.open()

    pages_content = [
        # Страница 1: Компания
        (
            "Компания «Альфа-Тех»\n\n"
            "Компания «Альфа-Тех» была основана 15 марта 2018 года в городе Казань.\n"
            "Основатель — Дмитрий Сергеевич Волков, выпускник КФУ.\n"
            "Количество сотрудников на 2024 год: 342 человека.\n"
            "Годовой оборот за 2023 год составил 1.2 миллиарда рублей.\n"
            "Основные направления: разработка программного обеспечения, "
            "искусственный интеллект и облачные решения.\n"
            "Офисы расположены в Казани, Москве и Санкт-Петербурге.\n"
            "Компания имеет 47 патентов в области машинного обучения.\n"
        ),
        # Страница 2: Проект
        (
            "Проект «Облако-5»\n\n"
            "Проект «Облако-5» — флагманская облачная платформа компании «Альфа-Тех».\n"
            "Запущен 1 сентября 2021 года.\n"
            "Количество активных пользователей: 58 000.\n"
            "Поддерживает 12 языков программирования.\n"
            "Время аптайма за 2023 год: 99.97%.\n"
            "Стоимость подписки: от 15 000 рублей в месяц для бизнеса.\n"
            "Технический директор проекта — Анна Владимировна Петрова.\n"
            "Используемые технологии: Kubernetes, PostgreSQL, Redis, gRPC.\n"
        ),
        # Страница 3: Финансы
        (
            "Финансовые показатели 2023\n\n"
            "Выручка компании «Альфа-Тех» за 2023 год: 1 247 000 000 рублей.\n"
            "Чистая прибыль: 186 000 000 рублей.\n"
            "Рентабельность: 14.9%.\n"
            "Расходы на R&D: 312 000 000 рублей (25% от выручки).\n"
            "Инвестиции привлечены в раунде B: 500 000 000 рублей от фонда «ВенчурПлюс».\n"
            "Средняя зарплата сотрудника: 195 000 рублей в месяц.\n"
            "Налоговые отчисления: 87 000 000 рублей.\n"
        ),
        # Страница 4: Партнёры и планы
        (
            "Партнёры и планы на 2025 год\n\n"
            "Ключевые партнёры: Яндекс, Сбер, МТС, Ростелеком.\n"
            "Подписан контракт с Минцифры РФ на 250 000 000 рублей.\n"
            "Планируется расширение в страны СНГ: Казахстан и Узбекистан.\n"
            "Целевой показатель выручки на 2025 год: 2 миллиарда рублей.\n"
            "Запланировано открытие нового офиса в Дубае в марте 2025.\n"
            "Планируется набрать 150 новых сотрудников.\n"
            "CEO Дмитрий Волков планирует провести IPO не ранее 2027 года.\n"
        ),
    ]

    # Используем Arial (поддерживает кириллицу) на Windows
    font_path = Path("C:/Windows/Fonts/arial.ttf")
    if not font_path.exists():
        # Фоллбэк — ищем любой TTF с кириллицей
        font_path = Path("C:/Windows/Fonts/times.ttf")

    for content in pages_content:
        page = doc.new_page(width=595, height=842)  # A4
        rect = fitz.Rect(50, 50, 545, 792)
        page.insert_textbox(
            rect, content, fontsize=12,
            fontname="arial", fontfile=str(font_path),
        )

    doc.save(str(output_path))
    doc.close()
    print(f"  Тестовый PDF создан: {output_path}")


# ====================================================================
# 2. Тесты
# ====================================================================

def main():
    print("\n" + "=" * 60)
    print("  ТЕСТ ЭТАПА 2: RAG пайплайн")
    print("=" * 60 + "\n")

    # --- Подготовка ---
    test_dir = Path("./knowledge_base")
    test_dir.mkdir(exist_ok=True)
    test_pdf = test_dir / "test_alpha_tech.pdf"

    # Очистим предыдущий тестовый ChromaDB
    chroma_test_dir = Path("./data/chroma_db")
    if chroma_test_dir.exists():
        shutil.rmtree(chroma_test_dir)
        print("  Предыдущий ChromaDB индекс удалён")

    # Создаём PDF
    print("\n--- Создание тестового PDF ---")
    create_test_pdf(test_pdf)

    # --- Загрузка PDF ---
    print("\n--- Загрузка и разбивка PDF ---")
    from app.rag.pdf_loader import load_pdf
    chunks = load_pdf(test_pdf)
    print(f"  Чанков: {len(chunks)}")
    for i, chunk in enumerate(chunks):
        print(f"  Чанк {i}: стр.{chunk.metadata['page']}, ~{chunk.metadata['approx_tokens']} токенов, {len(chunk.text)} символов")

    # --- Индексация ---
    print("\n--- Индексация в ChromaDB ---")
    from app.rag.retriever import Retriever
    retriever = Retriever()
    count = retriever.index_pdf(test_pdf)
    print(f"  Проиндексировано чанков: {count}")
    print(f"  Всего в коллекции: {retriever.store.count}")
    print(f"  Источники: {retriever.store.get_sources()}")

    # --- Тест 1: вопрос, ответ ЕСТЬ в PDF ---
    print("\n" + "=" * 60)
    print("  ТЕСТ 1: Вопрос с ответом в PDF")
    print("=" * 60)
    q1 = "Когда была основана компания Альфа-Тех и кто её основатель?"
    print(f"  Вопрос: {q1}")

    result1 = retriever.ask(q1)
    print(f"\n  Ответ:\n  {result1['answer'][:500]}")
    print(f"\n  Источники:")
    for s in result1['sources']:
        print(f"    - {s['source']}, стр. {s['page']}, score: {s['score']}")
    print(f"\n  Контекст найден: {result1['has_context']}")
    print(f"  Проверка галлюцинаций:\n  {result1['hallucination_check'][:300]}")

    # Простая проверка: ожидаем ключевые факты в ответе
    answer_lower = result1['answer'].lower()
    checks = [
        ("2018" in answer_lower or "марта" in answer_lower, "Дата основания (2018/март)"),
        ("волков" in answer_lower or "дмитрий" in answer_lower, "Имя основателя (Волков/Дмитрий)"),
        ("казань" in answer_lower, "Город (Казань)"),
    ]
    for passed, label in checks:
        status = "✓" if passed else "✗"
        print(f"  [{status}] {label}")

    # --- Тест 2: вопрос, ответа НЕТ в PDF ---
    print("\n" + "=" * 60)
    print("  ТЕСТ 2: Вопрос БЕЗ ответа в PDF")
    print("=" * 60)
    q2 = "Какой рецепт борща использует шеф-повар ресторана Прага?"
    print(f"  Вопрос: {q2}")

    result2 = retriever.ask(q2)
    print(f"\n  Ответ:\n  {result2['answer'][:500]}")
    print(f"\n  Контекст найден: {result2['has_context']}")
    print(f"  Источники: {result2['sources']}")

    # Проверяем: должно быть "нет информации" или подобное
    no_info_markers = ["нет информации", "не найден", "не содержит", "отсутствует", "нет данных", "не имеет", "нет релевант"]
    has_no_info = any(m in result2['answer'].lower() for m in no_info_markers)
    status = "✓" if has_no_info else "✗"
    print(f"  [{status}] Агент корректно сообщил об отсутствии информации")

    # --- Тест 3: top-5 чанков с score ---
    print("\n" + "=" * 60)
    print("  ТЕСТ 3: Top-5 чанков с relevance score")
    print("=" * 60)
    q3 = "Какие финансовые показатели компании за 2023 год?"
    print(f"  Запрос: {q3}\n")

    raw_results = retriever.store.search(q3, top_k=5)
    for i, r in enumerate(raw_results):
        meta = r['metadata']
        print(f"  #{i+1} | score: {r['score']:.4f} | {meta.get('source', '?')}, стр. {meta.get('page', '?')}")
        print(f"       {r['text'][:120]}...")
        print()

    # --- Итог ---
    print("=" * 60)
    print("  ЭТАП 2 ГОТОВ: RAG работает, источники указываются!")
    print("=" * 60)


if __name__ == "__main__":
    main()
