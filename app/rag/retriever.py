"""
RAG Retriever — полный пайплайн:
вопрос → эмбеддинг → поиск в ChromaDB → top-k чанков → форматирование контекста.
"""
import logging
from pathlib import Path

from app.config import config
from app.llm.ollama_client import OllamaClient
from app.llm.prompts import RAG_QUERY_TEMPLATE, HALLUCINATION_CHECK_PROMPT, MAIN_SYSTEM_PROMPT
from app.rag.pdf_loader import load_pdf, load_directory, Chunk
from app.rag.vector_store import VectorStore

logger = logging.getLogger(__name__)


class Retriever:
    """Полный RAG-пайплайн: индексация, поиск, генерация ответа с проверкой."""

    def __init__(self, vector_store: VectorStore | None = None):
        self.store = vector_store or VectorStore()
        self.llm = OllamaClient()

    # ------------------------------------------------------------------
    # Индексация
    # ------------------------------------------------------------------

    def index_pdf(
        self,
        pdf_path: Path | str,
        page_range: tuple[int, int] | None = None,
        force_ocr: bool = False,
        show_progress: bool = False,
    ) -> int:
        """Проиндексировать один PDF.

        Args:
            pdf_path: Путь к PDF-файлу.
            page_range: Диапазон страниц (1-based, включительно).
            force_ocr: Принудительно использовать OCR.
            show_progress: Показывать прогресс-бар.

        Returns:
            Количество добавленных чанков.
        """
        pdf_path = Path(pdf_path)
        chunks = load_pdf(
            pdf_path,
            page_range=page_range,
            force_ocr=force_ocr,
            show_progress=show_progress,
        )
        if not chunks:
            logger.warning(f"Нет чанков из {pdf_path}")
            return 0
        return self.store.add_chunks(chunks)

    def index_directory(self, dir_path: Path | str | None = None) -> int:
        """Проиндексировать все PDF из директории.

        Returns:
            Общее количество добавленных чанков.
        """
        chunks = load_directory(dir_path)
        if not chunks:
            return 0
        return self.store.add_chunks(chunks)

    def reindex(self, dir_path: Path | str | None = None) -> int:
        """Полная переиндексация: очистка + загрузка заново."""
        self.store.delete_collection()
        return self.index_directory(dir_path)

    # ------------------------------------------------------------------
    # Поиск
    # ------------------------------------------------------------------

    def search(self, query: str, top_k: int | None = None) -> list[dict]:
        """Поиск релевантных чанков по запросу.

        Returns:
            Список результатов: [{"text": ..., "metadata": {...}, "score": ...}]
        """
        results = self.store.search(query, top_k=top_k)
        # Фильтруем по порогу релевантности
        threshold = config.rag.relevance_threshold
        filtered = [r for r in results if r["score"] >= threshold]
        logger.info(
            f"Поиск '{query[:50]}...': {len(results)} найдено, "
            f"{len(filtered)} прошли порог {threshold}"
        )
        return filtered

    def format_context(self, results: list[dict]) -> str:
        """Форматирует найденные чанки в контекст для LLM.

        Returns:
            Отформатированный контекст с указанием источников.
        """
        if not results:
            return ""

        parts = []
        for r in results:
            meta = r["metadata"]
            source = meta.get("source", "неизвестно")
            page = meta.get("page", "?")
            score = r.get("score", 0)
            parts.append(
                f"---\nИсточник: {source}, стр. {page}, релевантность: {score}\n{r['text']}\n"
            )
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Ответ с RAG
    # ------------------------------------------------------------------

    def ask(self, question: str, top_k: int | None = None) -> dict:
        """Полный RAG-пайплайн: вопрос → поиск → генерация → проверка.

        Returns:
            {
                "answer": str,           # финальный ответ
                "sources": list[dict],   # используемые источники
                "context": str,          # контекст из базы знаний
                "hallucination_check": str,  # результат проверки
                "has_context": bool,     # был ли найден контекст
            }
        """
        # 1. Поиск релевантных чанков
        results = self.search(question, top_k=top_k)
        context = self.format_context(results)
        has_context = bool(context.strip())

        # 2. Формируем промпт
        if has_context:
            user_prompt = RAG_QUERY_TEMPLATE.format(
                context=context,
                question=question,
            )
        else:
            # Контекст не найден — явно сообщаем
            user_prompt = (
                f"Вопрос пользователя: {question}\n\n"
                "В базе знаний НЕТ информации по этому вопросу. "
                "Сообщи пользователю, что в базе знаний нет релевантной информации. "
                "НЕ пытайся ответить из своих знаний."
            )

        # 3. Генерируем ответ
        messages = [
            {"role": "system", "content": MAIN_SYSTEM_PROMPT.replace("{available_tools}", "")},
            {"role": "user", "content": user_prompt},
        ]
        answer = self.llm.chat(messages, temperature=0.1)

        # 4. Проверка на галлюцинации (если был контекст)
        hallucination_check = ""
        if has_context and answer:
            hallucination_check = self._check_hallucination(context, answer)

        # 5. Источники для ответа
        sources = [
            {
                "source": r["metadata"].get("source", ""),
                "page": r["metadata"].get("page", ""),
                "score": r.get("score", 0),
            }
            for r in results
        ]

        return {
            "answer": answer,
            "sources": sources,
            "context": context,
            "hallucination_check": hallucination_check,
            "has_context": has_context,
        }

    def _check_hallucination(self, context: str, answer: str) -> str:
        """Двойная проверка ответа на галлюцинации.

        Отправляет контекст и ответ модели с просьбой оценить достоверность.
        """
        check_prompt = HALLUCINATION_CHECK_PROMPT.format(
            context=context,
            answer=answer,
        )
        messages = [
            {"role": "system", "content": "Ты — проверяющий. Оцени достоверность ответа."},
            {"role": "user", "content": check_prompt},
        ]
        result = self.llm.chat(messages, temperature=0.0)
        return result
