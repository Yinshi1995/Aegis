"""Быстрый тест OCR на страницах 49-51 ozbroennia.pdf."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

from app.rag.pdf_loader import extract_text_by_page

pdf = Path("./knowledge_base/ozbroennia.pdf")
print("Запускаю OCR для страниц 49-51...")
pages = extract_text_by_page(pdf, page_range=(49, 51), show_progress=True)

for p in pages:
    page_num = p["page"]
    ocr_flag = p["ocr"]
    text = p["text"]
    print(f"\n=== СТРАНИЦА {page_num} (OCR: {ocr_flag}) ===")
    print(f"Длина: {len(text)} символов")
    print(text[:600])
    print("...")
