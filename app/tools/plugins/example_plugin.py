"""
Пример плагина — шаблон для создания новых инструментов.
Просто скопируйте этот файл, переименуйте и измените логику.
"""
from app.tools.base import BaseTool, ToolResult


class ExampleTool(BaseTool):
    """Пример инструмента-плагина."""

    name = "example"
    description = (
        "Пример плагина. Демонстрирует структуру инструмента. "
        "Параметры: action (echo|reverse), text."
    )

    async def execute(self, **params) -> ToolResult:
        """
        Демо-действия.

        Параметры:
            action: "echo" | "reverse"
            text: входной текст
        """
        action = params.get("action", "echo")
        text = params.get("text", "")

        if action == "echo":
            return ToolResult(success=True, data=text, source=self.name)

        if action == "reverse":
            return ToolResult(success=True, data=text[::-1], source=self.name)

        return ToolResult(
            success=False,
            error=f"Неизвестное действие: {action}. Доступны: echo, reverse",
            source=self.name,
        )
