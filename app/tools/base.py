"""
Базовый класс инструментов и реестр.
Каждый инструмент (браузер, WhatsApp, скрапер и т.д.) наследуется от BaseTool.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
import asyncio
import logging

logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    """Результат выполнения инструмента."""
    success: bool
    data: Any = None
    error: str | None = None
    source: str = ""  # какой инструмент вернул результат


class BaseTool(ABC):
    """Базовый класс для всех инструментов агента."""

    name: str = "base_tool"
    description: str = "Базовый инструмент"

    @abstractmethod
    async def execute(self, **params) -> ToolResult:
        """Выполнить действие. Переопределяется в каждом инструменте."""
        ...

    async def safe_execute(self, timeout: int = 30, **params) -> ToolResult:
        """Обёртка с таймаутом и обработкой ошибок."""
        try:
            result = await asyncio.wait_for(
                self.execute(**params),
                timeout=timeout,
            )
            return result
        except asyncio.TimeoutError:
            logger.error(f"Инструмент {self.name}: таймаут ({timeout}с)")
            return ToolResult(success=False, error=f"Таймаут: {timeout}с", source=self.name)
        except Exception as e:
            logger.error(f"Инструмент {self.name}: ошибка — {e}")
            return ToolResult(success=False, error=str(e), source=self.name)

    def to_description(self) -> str:
        """Описание для LLM — чтобы модель знала, когда использовать инструмент."""
        return f"- **{self.name}**: {self.description}"


class ToolRegistry:
    """Реестр всех доступных инструментов."""

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool):
        """Зарегистрировать инструмент."""
        self._tools[tool.name] = tool
        logger.info(f"Инструмент зарегистрирован: {tool.name}")

    def get(self, name: str) -> BaseTool | None:
        """Получить инструмент по имени."""
        return self._tools.get(name)

    def list_descriptions(self) -> str:
        """Описания всех инструментов для вставки в промпт."""
        return "\n".join(t.to_description() for t in self._tools.values())

    @property
    def names(self) -> list[str]:
        return list(self._tools.keys())


# Глобальный реестр
registry = ToolRegistry()
