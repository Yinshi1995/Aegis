"""
Оркестратор — мозг агента.
Маршрутизация запросов: RAG / SKILL / TOOL / CHAT.
Связывает OllamaClient, Retriever, SkillManager, SkillExecutor, ToolRegistry.
"""
import json
import logging
import re
import time
from dataclasses import dataclass, field

from app.config import config
from app.llm import get_llm_client
from app.llm.prompts import (
    MAIN_SYSTEM_PROMPT,
    RAG_QUERY_TEMPLATE,
    HALLUCINATION_CHECK_PROMPT,
)
from app.rag.retriever import Retriever
from app.skills.manager import Manager
from app.skills.executor import SkillExecutor
from app.tools import register_all_tools
from app.tools.base import registry

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Промпт классификации намерения
# ------------------------------------------------------------------

INTENT_PROMPT = """Классифицируй запрос пользователя. Ответь ОДНИМ словом: SKILL, TOOL, RAG или CHAT.

Правила:
- SKILL — если просят выполнить навык: перевод, генерация кода, анализ документа
- TOOL — если нужно действие во внешней среде: открыть сайт, прочитать файл, запустить скрипт, отправить сообщение
- RAG — если вопрос по базе знаний, документам, фактам из PDF
- CHAT — обычный разговор, приветствие, вопросы общего характера

Доступные скиллы: {skills}
Доступные инструменты: {tools}

Запрос: {message}

Ответ (одно слово):"""

# ------------------------------------------------------------------
# Промпт выбора скилла
# ------------------------------------------------------------------

SKILL_SELECT_PROMPT = """Какой скилл лучше подходит для запроса? Ответь ТОЛЬКО именем скилла, одним словом.

Доступные скиллы:
{skills_desc}

Запрос: {message}

Имя скилла:"""

# ------------------------------------------------------------------
# Промпт выбора инструмента
# ------------------------------------------------------------------

TOOL_SELECT_PROMPT = """Какой инструмент нужен и с какими параметрами? Ответь СТРОГО в JSON.

Доступные инструменты:
{tools_desc}

Запрос пользователя: {message}

Ответь JSON: {{"tool": "имя", "params": {{...}}}}"""


# ------------------------------------------------------------------
# AgentResponse
# ------------------------------------------------------------------

@dataclass
class AgentResponse:
    """Результат обработки сообщения агентом."""
    text: str
    intent: str  # RAG / SKILL / TOOL / CHAT
    sources: list[dict] = field(default_factory=list)
    skill_used: str | None = None
    tool_used: str | None = None
    execution_time: float = 0.0


# ------------------------------------------------------------------
# Agent
# ------------------------------------------------------------------

class Agent:
    """Главный оркестратор — связывает все компоненты в единого агента."""

    def __init__(self):
        """Инициализация всех подсистем."""
        # LLM
        self.llm = get_llm_client()

        # RAG
        self.retriever = Retriever()

        # Скиллы
        self.skill_manager = Manager()
        self.skill_executor = SkillExecutor(retriever=self.retriever)

        # Инструменты
        register_all_tools()
        self.tool_registry = registry

        # История чата
        self._history: list[dict] = []

        logger.info(
            "Агент инициализирован: модель=%s, скиллов=%d, инструментов=%d",
            self.llm.model,
            len(self.skill_manager.get_skill_names()),
            len(self.tool_registry.names),
        )

    # ------------------------------------------------------------------
    # Главный метод
    # ------------------------------------------------------------------

    async def process_message(self, user_message: str) -> AgentResponse:
        """Обработать сообщение пользователя.

        1. Классифицировать намерение (SKILL / TOOL / RAG / CHAT)
        2. Маршрутизировать к нужному обработчику
        3. Сохранить в историю
        4. Вернуть AgentResponse
        """
        start = time.time()
        user_message = user_message.strip()

        # Добавляем сообщение пользователя в историю
        self._history.append({"role": "user", "content": user_message})

        try:
            # 1. Определяем намерение
            intent = self._classify_intent(user_message)
            logger.info("Намерение: %s для '%s'", intent, user_message[:60])

            # 2. Маршрутизация
            if intent == "RAG":
                response = self._handle_rag(user_message)
            elif intent == "SKILL":
                response = await self._handle_skill(user_message)
            elif intent == "TOOL":
                response = await self._handle_tool(user_message)
            else:
                response = self._handle_chat(user_message)

            response.intent = intent
            response.execution_time = round(time.time() - start, 2)

            # 3. Сохраняем ответ в историю
            self._history.append({"role": "assistant", "content": response.text})

            return response

        except Exception as e:
            elapsed = round(time.time() - start, 2)
            logger.error("Ошибка обработки: %s", e)
            error_response = AgentResponse(
                text=f"Произошла ошибка: {e}",
                intent="ERROR",
                execution_time=elapsed,
            )
            self._history.append({"role": "assistant", "content": error_response.text})
            return error_response

    # ------------------------------------------------------------------
    # Классификация намерения
    # ------------------------------------------------------------------

    def _classify_intent(self, message: str) -> str:
        """Определить намерение: RAG, SKILL, TOOL или CHAT."""
        skills_list = ", ".join(self.skill_manager.get_skill_names())
        tools_list = ", ".join(self.tool_registry.names)

        prompt = INTENT_PROMPT.format(
            skills=skills_list,
            tools=tools_list,
            message=message,
        )

        raw = self.llm.generate(prompt, temperature=0.0, max_tokens=10)
        raw = raw.strip().upper()

        # Извлекаем первое валидное слово
        for token in re.split(r"[\s,.;:!?]+", raw):
            if token in ("RAG", "SKILL", "TOOL", "CHAT"):
                return token

        logger.warning("Не удалось определить намерение из '%s', fallback → CHAT", raw)
        return "CHAT"

    # ------------------------------------------------------------------
    # Обработчик RAG
    # ------------------------------------------------------------------

    def _handle_rag(self, message: str) -> AgentResponse:
        """Ответ на вопрос по базе знаний."""
        rag_result = self.retriever.ask(message)

        answer = rag_result["answer"]
        sources = rag_result.get("sources", [])

        # Если была проверка на галлюцинации — парсим результат
        hallucination_check = rag_result.get("hallucination_check", "")
        if hallucination_check:
            corrected = self._parse_hallucination_check(hallucination_check)
            if corrected:
                answer = corrected

        return AgentResponse(
            text=answer,
            intent="RAG",
            sources=sources,
        )

    def _parse_hallucination_check(self, check_text: str) -> str | None:
        """Извлечь скорректированный ответ из проверки галлюцинаций."""
        try:
            # Пробуем найти JSON в ответе
            match = re.search(r"\{[^{}]*\}", check_text, re.DOTALL)
            if match:
                data = json.loads(match.group())
                if not data.get("verified", True) and data.get("corrected_answer"):
                    logger.info("Галлюцинация обнаружена, используем скорректированный ответ")
                    return data["corrected_answer"]
        except (json.JSONDecodeError, KeyError):
            pass
        return None

    # ------------------------------------------------------------------
    # Обработчик SKILL
    # ------------------------------------------------------------------

    async def _handle_skill(self, message: str) -> AgentResponse:
        """Определить скилл и выполнить его."""
        # 1. Определяем какой скилл
        skill_name = self._select_skill(message)
        skill = self.skill_manager.get_skill(skill_name) if skill_name else None

        if not skill:
            # Fallback — попробуем как чат
            logger.warning("Скилл '%s' не найден, fallback → CHAT", skill_name)
            return self._handle_chat(message)

        # 2. Извлекаем параметры из сообщения
        params = self._extract_skill_params(skill, message)

        # 3. Выполняем
        result = self.skill_executor.execute(skill, **params)

        if result.success:
            return AgentResponse(
                text=result.answer,
                intent="SKILL",
                skill_used=skill_name,
                sources=result.sources,
            )
        else:
            return AgentResponse(
                text=f"Ошибка скилла '{skill_name}': {result.error}",
                intent="SKILL",
                skill_used=skill_name,
            )

    def _select_skill(self, message: str) -> str | None:
        """Определить подходящий скилл для запроса."""
        skills = self.skill_manager.list_skills()
        if not skills:
            return None

        skills_desc = "\n".join(f"- {s.name}: {s.description}" for s in skills)
        prompt = SKILL_SELECT_PROMPT.format(
            skills_desc=skills_desc,
            message=message,
        )

        raw = self.llm.generate(prompt, temperature=0.0, max_tokens=20)
        raw = raw.strip().lower()

        # Ищем имя скилла в ответе
        skill_names = self.skill_manager.get_skill_names()
        for name in skill_names:
            if name in raw:
                return name

        # Fuzzy: первое слово ответа
        first_word = re.split(r"[\s,.;:!?]+", raw)[0] if raw else ""
        if first_word in skill_names:
            return first_word

        logger.warning("Не удалось определить скилл из '%s'", raw)
        return skill_names[0] if skill_names else None

    def _extract_skill_params(self, skill, message: str) -> dict:
        """Извлечь параметры скилла из сообщения пользователя.

        Использует шаблон скилла для определения нужных переменных.
        """
        import re as _re
        template = skill.user_template or ""
        placeholders = _re.findall(r"\{(\w+)\}", template)

        if not placeholders:
            # Нет плейсхолдеров — весь текст как параметр
            return {"text": message, "question": message, "topic": message}

        # Для translate: ищем "на <язык>: <текст>"
        if "target_language" in placeholders and "text" in placeholders:
            lang_match = _re.search(
                r"(?:на|to|in)\s+(английский|English|русский|Russian|украинский|Ukrainian|немецкий|German|французский|French|испанский|Spanish)",
                message,
                _re.IGNORECASE,
            )
            lang = lang_match.group(1) if lang_match else "English"
            # Текст после двоеточия или последней части
            text_match = _re.search(r"[:\-]\s*(.+)$", message)
            text = text_match.group(1).strip() if text_match else message
            return {"target_language": lang, "text": text}

        # Для code_gen: "на <язык>: <описание>"
        if "language" in placeholders and "description" in placeholders:
            lang_match = _re.search(
                r"(?:на|in|using)\s+(Python|JavaScript|TypeScript|Go|Rust|Java|C\+\+|C#)",
                message,
                _re.IGNORECASE,
            )
            lang = lang_match.group(1) if lang_match else "Python"
            desc_match = _re.search(r"[:\-]\s*(.+)$", message)
            desc = desc_match.group(1).strip() if desc_match else message
            return {"language": lang, "description": desc}

        # Общий fallback — заполняем все плейсхолдеры текстом сообщения
        return {p: message for p in placeholders}

    # ------------------------------------------------------------------
    # Обработчик TOOL
    # ------------------------------------------------------------------

    async def _handle_tool(self, message: str) -> AgentResponse:
        """Определить инструмент, выполнить, обработать результат."""
        # 1. Определяем инструмент и параметры
        tool_call = self._select_tool(message)

        if not tool_call:
            logger.warning("Не удалось определить инструмент, fallback → CHAT")
            return self._handle_chat(message)

        tool_name = tool_call.get("tool", "")
        params = tool_call.get("params", {})

        tool = self.tool_registry.get(tool_name)
        if not tool:
            logger.warning("Инструмент '%s' не найден, fallback → CHAT", tool_name)
            return self._handle_chat(message)

        # 2. Выполняем инструмент
        result = await tool.safe_execute(timeout=config.tools.browser_timeout, **params)

        # 3. Если нужно — обрабатываем результат через LLM
        if result.success:
            # Формируем человеческий ответ на основе результата инструмента
            answer = self._summarize_tool_result(message, tool_name, result.data)
        else:
            answer = f"Инструмент '{tool_name}' вернул ошибку: {result.error}"

        return AgentResponse(
            text=answer,
            intent="TOOL",
            tool_used=tool_name,
        )

    def _select_tool(self, message: str) -> dict | None:
        """Определить какой инструмент вызвать и с какими параметрами."""
        tools_desc = self.tool_registry.list_descriptions()
        prompt = TOOL_SELECT_PROMPT.format(
            tools_desc=tools_desc,
            message=message,
        )

        raw = self.llm.generate(prompt, temperature=0.0, max_tokens=200)
        raw = raw.strip()

        # Извлекаем JSON из ответа
        try:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                data = json.loads(match.group())
                if "tool" in data:
                    logger.info("Выбран инструмент: %s, params=%s", data["tool"], data.get("params"))
                    return data
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("Не удалось разобрать ответ инструмента: %s → %s", raw[:100], e)

        return None

    def _summarize_tool_result(self, original_message: str, tool_name: str, data) -> str:
        """Сформировать человеческий ответ по результату инструмента."""
        data_str = json.dumps(data, ensure_ascii=False, default=str) if not isinstance(data, str) else data

        # Если результат короткий — вернуть как есть
        if len(data_str) < 500:
            return f"Результат ({tool_name}):\n{data_str}"

        # Длинные результаты — через LLM
        prompt = (
            f"Пользователь запросил: {original_message}\n\n"
            f"Инструмент '{tool_name}' вернул:\n{data_str[:4000]}\n\n"
            "Сформируй краткий, полезный ответ для пользователя."
        )
        return self.llm.generate(prompt, temperature=0.1)

    # ------------------------------------------------------------------
    # Обработчик CHAT
    # ------------------------------------------------------------------

    def _handle_chat(self, message: str) -> AgentResponse:
        """Обычный чат с историей."""
        system = MAIN_SYSTEM_PROMPT.replace(
            "{available_tools}",
            self.tool_registry.list_descriptions(),
        )

        # Берём последние N сообщений из истории для контекста
        max_history = 20
        recent = self._history[-max_history:]

        messages = [{"role": "system", "content": system}] + recent
        answer = self.llm.chat(messages)

        return AgentResponse(text=answer, intent="CHAT")

    # ------------------------------------------------------------------
    # История
    # ------------------------------------------------------------------

    def clear_history(self):
        """Очистить историю чата."""
        self._history.clear()
        logger.info("История чата очищена")

    def get_history(self) -> list[dict]:
        """Вернуть историю чата."""
        return list(self._history)
