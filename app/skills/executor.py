"""
Исполнение скиллов: загрузка → подстановка переменных → (RAG) → Ollama → (скрипт) → результат.
"""
import logging
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.config import config
from app.llm.ollama_client import OllamaClient
from app.skills.models import Skill

logger = logging.getLogger(__name__)


@dataclass
class SkillResult:
    """Результат исполнения скилла."""
    skill_name: str
    answer: str
    success: bool = True
    error: str | None = None
    elapsed_seconds: float = 0.0
    # RAG-данные (если requires_rag)
    sources: list[dict] = field(default_factory=list)
    context: str = ""
    has_context: bool = False
    # Скрипт
    script_output: str | None = None


class SkillExecutor:
    """Исполнитель скиллов — собирает промпт, RAG-контекст, вызывает LLM."""

    def __init__(self, retriever=None):
        """
        Args:
            retriever: Экземпляр Retriever (для скиллов с requires_rag=True).
                       Если None — создаётся лениво при первом RAG-запросе.
        """
        self._retriever = retriever
        self._llm = OllamaClient()

    @property
    def retriever(self):
        """Ленивая инициализация Retriever."""
        if self._retriever is None:
            from app.rag.retriever import Retriever
            self._retriever = Retriever()
        return self._retriever

    def execute(self, skill: Skill, **kwargs) -> SkillResult:
        """Исполнить скилл.

        Args:
            skill: Объект Skill из БД.
            **kwargs: Переменные для подстановки в user_template.

        Returns:
            SkillResult с ответом и метаданными.
        """
        start = time.time()
        skill_name = skill.name

        try:
            # 1. Подстановка переменных в шаблон
            user_message = self._render_template(skill.user_template, kwargs)
            logger.info(f"Скилл '{skill_name}': шаблон → '{user_message[:80]}...'")

            # 2. RAG-контекст (если нужен)
            rag_data = {}
            if skill.requires_rag:
                rag_data = self._get_rag_context(user_message)
                if rag_data.get("context"):
                    # Оборачиваем сообщение контекстом из базы
                    user_message = self._wrap_with_context(user_message, rag_data["context"])

            # 3. Вызов LLM
            temperature = skill.temperature if skill.temperature is not None else None
            messages = [
                {"role": "system", "content": skill.system_prompt},
                {"role": "user", "content": user_message},
            ]
            answer = self._llm.chat(messages, temperature=temperature)

            # 4. Скрипт (если есть)
            script_output = None
            if skill.script_path:
                script_output = self._run_script(skill.script_path, answer, kwargs)

            elapsed = time.time() - start
            logger.info(f"Скилл '{skill_name}' выполнен за {elapsed:.1f}с")

            return SkillResult(
                skill_name=skill_name,
                answer=answer,
                success=True,
                elapsed_seconds=round(elapsed, 2),
                sources=rag_data.get("sources", []),
                context=rag_data.get("context", ""),
                has_context=rag_data.get("has_context", False),
                script_output=script_output,
            )

        except Exception as e:
            elapsed = time.time() - start
            logger.error(f"Ошибка скилла '{skill_name}': {e}")
            return SkillResult(
                skill_name=skill_name,
                answer="",
                success=False,
                error=str(e),
                elapsed_seconds=round(elapsed, 2),
            )

    def execute_by_name(self, skill_name: str, manager, **kwargs) -> SkillResult:
        """Исполнить скилл по имени (загружает из менеджера).

        Args:
            skill_name: Имя скилла.
            manager: Экземпляр Manager.
            **kwargs: Переменные для шаблона.

        Returns:
            SkillResult.
        """
        skill = manager.get_skill(skill_name)
        if not skill:
            return SkillResult(
                skill_name=skill_name,
                answer="",
                success=False,
                error=f"Скилл '{skill_name}' не найден",
            )
        return self.execute(skill, **kwargs)

    # ------------------------------------------------------------------
    # Внутренние методы
    # ------------------------------------------------------------------

    def _render_template(self, template: str, variables: dict) -> str:
        """Подстановка переменных в шаблон.

        Пропущенные переменные остаются как {имя} — не ломаем шаблон.
        """
        if not template:
            # Если шаблона нет — собираем из всех переменных
            return " ".join(str(v) for v in variables.values())

        try:
            # Безопасная подстановка: только указанные ключи
            result = template
            for key, value in variables.items():
                placeholder = "{" + key + "}"
                result = result.replace(placeholder, str(value))
            return result
        except Exception as e:
            logger.warning(f"Ошибка подстановки шаблона: {e}")
            return template

    def _get_rag_context(self, query: str) -> dict:
        """Получает RAG-контекст для запроса.

        Returns:
            {"context": str, "sources": list, "has_context": bool}
        """
        try:
            results = self.retriever.search(query)
            context = self.retriever.format_context(results)
            sources = [
                {
                    "source": r["metadata"].get("source", ""),
                    "page": r["metadata"].get("page", ""),
                    "score": r.get("score", 0),
                }
                for r in results
            ]
            return {
                "context": context,
                "sources": sources,
                "has_context": bool(context.strip()),
            }
        except Exception as e:
            logger.error(f"Ошибка RAG: {e}")
            return {"context": "", "sources": [], "has_context": False}

    def _wrap_with_context(self, user_message: str, context: str) -> str:
        """Оборачивает сообщение RAG-контекстом."""
        return (
            f"[КОНТЕКСТ ІЗ БАЗИ ЗНАНЬ]\n{context}\n[КІНЕЦЬ КОНТЕКСТУ]\n\n"
            f"Питання: {user_message}\n\n"
            "Інструкція: Відповідай ТІЛЬКИ на основі контексту вище. "
            "Якщо відповіді немає — скажи прямо. Вказуй джерело."
        )

    def _run_script(self, script_path: str, llm_answer: str, params: dict) -> str | None:
        """Запуск внешнего скрипта.

        Передаёт ответ LLM через stdin, параметры через аргументы.
        """
        path = Path(script_path)
        if not path.exists():
            logger.warning(f"Скрипт не найден: {script_path}")
            return None

        try:
            result = subprocess.run(
                ["python", str(path)],
                input=llm_answer,
                capture_output=True,
                text=True,
                timeout=config.tools.browser_timeout,
                cwd=str(config.project_root),
            )
            if result.returncode != 0:
                logger.error(f"Скрипт ошибка: {result.stderr[:200]}")
                return f"[Ошибка скрипта: {result.stderr[:200]}]"
            return result.stdout
        except subprocess.TimeoutExpired:
            logger.error(f"Скрипт таймаут: {script_path}")
            return "[Ошибка: таймаут скрипта]"
        except Exception as e:
            logger.error(f"Ошибка запуска скрипта: {e}")
            return f"[Ошибка: {e}]"
