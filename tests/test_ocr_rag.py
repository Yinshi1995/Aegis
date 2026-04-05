"""Тест OCR RAG: индексация стр. 49-51 ozbroennia.pdf + поиск."""
import sys
import shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

from app.rag.retriever import Retriever
from app.rag.vector_store import VectorStore

# Очистим ChromaDB
chroma_dir = Path("./data/chroma_db")
if chroma_dir.exists():
    shutil.rmtree(chroma_dir)

pdf = Path("./knowledge_base/ozbroennia.pdf")

# Индексация страниц 49-51
print("\n=== Индексация страниц 49-51 с OCR ===")
retriever = Retriever()
count = retriever.index_pdf(pdf, page_range=(49, 51), show_progress=True)
print(f"Проиндексировано чанков: {count}")

# Тест 1: вопрос про БМП К-17
print("\n" + "=" * 60)
print("ТЕСТ: Вопрос про БМП К-17")
print("=" * 60)
q = "Яка потужність двигуна БМП К-17 та яка його максимальна швидкість?"
print(f"Запрос: {q}\n")

result = retriever.ask(q)
print(f"Ответ:\n{result['answer']}\n")
print("Источники:")
for s in result["sources"]:
    print(f"  - {s['source']}, стр. {s['page']}, score: {s['score']}")

# Тест 2: вопрос, ответа нет
print("\n" + "=" * 60)
print("ТЕСТ: Вопрос без ответа")
print("=" * 60)
q2 = "Який рецепт борщу найкращий?"
print(f"Запрос: {q2}\n")
result2 = retriever.ask(q2)
print(f"Ответ:\n{result2['answer']}\n")
print(f"Контекст найден: {result2['has_context']}")

# Тест 3: raw search
print("\n" + "=" * 60)
print("Raw search: калібр гармати")
print("=" * 60)
raw = retriever.store.search("калібр гармати БМП", top_k=3)
for i, r in enumerate(raw):
    m = r["metadata"]
    print(f"  #{i+1} score={r['score']:.4f} | {m.get('source')}, стр. {m.get('page')}")
    print(f"       {r['text'][:150]}...")
    print()

print("=== OCR RAG тест завершён ===")
