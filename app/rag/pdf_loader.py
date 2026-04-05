"""
Загрузка и парсинг PDF через PyMuPDF.
OCR-фолбэк через pytesseract для битых/зашифрованных PDF.
Разбивка на чанки с перекрытием, сохранение метаданных (файл, страница).
"""
import fitz  # PyMuPDF
import logging
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Tuple

from app.config import config

logger = logging.getLogger(__name__)

# Tesseract настройки
TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
TESSDATA_DIR = Path(__file__).parent.parent.parent / "data" / "tessdata"
OCR_LANGUAGES = "ukr+rus"
OCR_DPI = 200
# Минимальная доля кириллических символов для «нормального» текста
CYRILLIC_THRESHOLD = 0.30


@dataclass
class Chunk:
    """Один чанк текста из PDF."""
    text: str
    metadata: dict = field(default_factory=dict)
    # metadata: {"source": "file.pdf", "page": 3, "chunk_index": 0, "ocr": False}


# ------------------------------------------------------------------
# OCR утилиты
# ------------------------------------------------------------------

def _cyrillic_ratio(text: str) -> float:
    """Доля кириллических символов в тексте (0.0 – 1.0)."""
    if not text or not text.strip():
        return 0.0
    alpha_chars = [c for c in text if c.isalpha()]
    if not alpha_chars:
        return 0.0
    cyrillic = sum(1 for c in alpha_chars if re.match(r'[а-яА-ЯіІїЇєЄґҐёЁ]', c))
    return cyrillic / len(alpha_chars)


def _is_text_broken(text: str) -> bool:
    """Проверяет, «битый» ли текст (мало кириллицы при наличии символов)."""
    if not text or len(text.strip()) < 20:
        return True
    ratio = _cyrillic_ratio(text)
    logger.debug(f"Кириллическая доля: {ratio:.2%}")
    return ratio < CYRILLIC_THRESHOLD


def _setup_tesseract():
    """Настраивает pytesseract — путь к бинарнику и tessdata."""
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
    import os
    if TESSDATA_DIR.exists():
        os.environ["TESSDATA_PREFIX"] = str(TESSDATA_DIR)
    return pytesseract


def _ocr_page(page: fitz.Page, dpi: int = OCR_DPI) -> str:
    """Растеризует страницу PDF и распознаёт текст через OCR.

    Args:
        page: Страница PyMuPDF.
        dpi: Разрешение растеризации.

    Returns:
        Распознанный текст.
    """
    from PIL import Image
    import io

    pytesseract = _setup_tesseract()

    # Растеризация через PyMuPDF (без внешнего pdftoppm)
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)

    # Конвертируем в PIL Image
    img_data = pix.tobytes("png")
    image = Image.open(io.BytesIO(img_data))

    # OCR
    text = pytesseract.image_to_string(image, lang=OCR_LANGUAGES)
    return text.strip()


# ------------------------------------------------------------------
# Извлечение текста
# ------------------------------------------------------------------

def _detect_extraction_method(pdf_path: Path, sample_pages: int = 3) -> str:
    """Определяет метод извлечения: 'text' (обычный) или 'ocr' (фолбэк).

    Проверяет первые sample_pages страниц — если текст битый, нужен OCR.
    """
    doc = fitz.open(str(pdf_path))
    total_pages = len(doc)
    check_pages = min(sample_pages, total_pages)

    broken_count = 0
    for i in range(check_pages):
        text = doc[i].get_text("text").strip()
        if _is_text_broken(text):
            broken_count += 1

    doc.close()

    method = "ocr" if broken_count > check_pages / 2 else "text"
    logger.info(
        f"{pdf_path.name}: проверено {check_pages} стр., "
        f"битых: {broken_count} → метод: {method}"
    )
    return method


def extract_text_by_page(
    pdf_path: Path,
    page_range: Tuple[int, int] | None = None,
    force_ocr: bool = False,
    show_progress: bool = False,
) -> list[dict]:
    """Извлекает текст из PDF постранично с автодетектом OCR.

    Args:
        pdf_path: Путь к PDF.
        page_range: Диапазон страниц (1-based, включительно), напр. (49, 51).
        force_ocr: Принудительно использовать OCR.
        show_progress: Показать прогресс-бар (tqdm).

    Returns:
        Список словарей: [{"page": 1, "text": "...", "source": "file.pdf", "ocr": False}, ...]
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF не найден: {pdf_path}")

    # Определяем метод
    use_ocr = force_ocr or _detect_extraction_method(pdf_path) == "ocr"
    if use_ocr:
        logger.info(f"Используется OCR для {pdf_path.name}")

    pages = []
    try:
        doc = fitz.open(str(pdf_path))
        total = len(doc)

        # Определяем диапазон страниц
        if page_range:
            start_page = max(0, page_range[0] - 1)  # 1-based → 0-based
            end_page = min(total, page_range[1])
        else:
            start_page = 0
            end_page = total

        page_indices = range(start_page, end_page)

        # Прогресс-бар
        if show_progress:
            from tqdm import tqdm
            page_indices = tqdm(
                page_indices,
                desc=f"{'OCR' if use_ocr else 'Извлечение'} {pdf_path.name}",
                unit="стр.",
            )

        for page_num in page_indices:
            page = doc[page_num]

            if use_ocr:
                text = _ocr_page(page)
            else:
                text = page.get_text("text").strip()

            if text:
                pages.append({
                    "page": page_num + 1,  # 1-based
                    "text": text,
                    "source": pdf_path.name,
                    "ocr": use_ocr,
                })

        doc.close()
        logger.info(
            f"PDF загружен: {pdf_path.name}, страниц с текстом: {len(pages)}"
            f" (метод: {'OCR' if use_ocr else 'text'})"
        )
    except Exception as e:
        logger.error(f"Ошибка при чтении PDF {pdf_path}: {e}")
        raise

    return pages


def _approx_token_count(text: str) -> int:
    """Приблизительный подсчёт токенов (1 токен ≈ 4 символа для русского/английского)."""
    return len(text) // 4


def split_text_into_chunks(
    text: str,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[str]:
    """Разбивает текст на чанки по количеству токенов с перекрытием.

    Args:
        text: Исходный текст.
        chunk_size: Максимальный размер чанка в токенах (по умолчанию из конфига).
        chunk_overlap: Перекрытие между чанками в токенах.

    Returns:
        Список строк-чанков.
    """
    chunk_size = chunk_size or config.rag.chunk_size
    chunk_overlap = chunk_overlap or config.rag.chunk_overlap

    # Переводим токены в символы (приблизительно)
    char_chunk_size = chunk_size * 4
    char_overlap = chunk_overlap * 4

    if len(text) <= char_chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + char_chunk_size

        # Ищем ближайший конец предложения для аккуратного разделения
        if end < len(text):
            # Ищем точку, перенос строки или конец абзаца в последних 20% чанка
            search_start = end - char_chunk_size // 5
            best_break = -1
            for sep in ["\n\n", ".\n", ". ", ";\n", "\n"]:
                pos = text.rfind(sep, search_start, end)
                if pos > best_break:
                    best_break = pos + len(sep)

            if best_break > start:
                end = best_break

        chunk_text = text[start:end].strip()
        if chunk_text:
            chunks.append(chunk_text)

        # Сдвигаем с учётом перекрытия
        start = end - char_overlap
        if start <= chunks[-1] if not chunks else 0:
            start = end  # Защита от бесконечного цикла

    return chunks


def load_pdf(
    pdf_path: Path,
    page_range: Tuple[int, int] | None = None,
    force_ocr: bool = False,
    show_progress: bool = False,
) -> list[Chunk]:
    """Загружает PDF и возвращает список чанков с метаданными.

    Args:
        pdf_path: Путь к PDF-файлу.
        page_range: Диапазон страниц (1-based, включительно).
        force_ocr: Принудительно использовать OCR.
        show_progress: Показывать прогресс-бар.

    Returns:
        Список Chunk с текстом и метаданными.
    """
    pages = extract_text_by_page(
        pdf_path,
        page_range=page_range,
        force_ocr=force_ocr,
        show_progress=show_progress,
    )
    all_chunks = []
    chunk_index = 0

    for page_data in pages:
        page_chunks = split_text_into_chunks(page_data["text"])
        for chunk_text in page_chunks:
            chunk = Chunk(
                text=chunk_text,
                metadata={
                    "source": page_data["source"],
                    "page": page_data["page"],
                    "chunk_index": chunk_index,
                    "approx_tokens": _approx_token_count(chunk_text),
                    "ocr": page_data.get("ocr", False),
                },
            )
            all_chunks.append(chunk)
            chunk_index += 1

    logger.info(
        f"PDF {pdf_path.name}: {len(pages)} страниц → {len(all_chunks)} чанков"
    )
    return all_chunks


def load_directory(dir_path: Path | str | None = None) -> list[Chunk]:
    """Загружает все PDF из директории.

    Args:
        dir_path: Путь к директории (по умолчанию knowledge_base из конфига).

    Returns:
        Список всех чанков из всех PDF.
    """
    if dir_path is None:
        dir_path = Path(config.knowledge_base_dir)
    else:
        dir_path = Path(dir_path)

    if not dir_path.is_absolute():
        dir_path = config.project_root / dir_path

    if not dir_path.exists():
        logger.warning(f"Директория не найдена: {dir_path}")
        return []

    all_chunks = []
    pdf_files = sorted(dir_path.glob("*.pdf"))

    if not pdf_files:
        logger.warning(f"PDF файлы не найдены в {dir_path}")
        return []

    for pdf_file in pdf_files:
        try:
            chunks = load_pdf(pdf_file)
            all_chunks.extend(chunks)
        except Exception as e:
            logger.error(f"Ошибка загрузки {pdf_file}: {e}")

    logger.info(f"Загружено {len(all_chunks)} чанков из {len(pdf_files)} PDF")
    return all_chunks
