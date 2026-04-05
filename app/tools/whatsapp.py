"""
Заглушка для WhatsApp-интеграции.
Реальная реализация будет добавлена позже через Playwright + WhatsApp Web.
"""
import logging
from app.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class WhatsAppTool(BaseTool):
    """WhatsApp-интеграция (заглушка)."""

    name = "whatsapp"
    description = (
        "Отправляет и читает сообщения WhatsApp. "
        "Параметры: action (send|read|status), phone, message. "
        "ВНИМАНИЕ: сейчас это заглушка, реальная интеграция будет позже."
    )

    async def execute(self, **params) -> ToolResult:
        """
        WhatsApp действия (заглушка).

        Параметры:
            action: "send" | "read" | "status"
            phone: номер телефона
            message: текст сообщения (для send)
        """
        action = params.get("action", "status")

        if action == "status":
            return ToolResult(
                success=True,
                data={"status": "stub", "message": "WhatsApp интеграция ещё не реализована"},
                source=self.name,
            )

        if action == "send":
            phone = params.get("phone")
            message = params.get("message")
            if not phone or not message:
                return ToolResult(success=False, error="Нужны phone и message", source=self.name)
            logger.warning("WhatsApp send — заглушка. phone=%s, len=%d", phone, len(message))
            return ToolResult(
                success=False,
                error="WhatsApp интеграция ещё не реализована. Сообщение НЕ отправлено.",
                source=self.name,
            )

        if action == "read":
            return ToolResult(
                success=False,
                error="WhatsApp интеграция ещё не реализована.",
                source=self.name,
            )

        return ToolResult(
            success=False,
            error=f"Неизвестное действие: {action}. Доступны: send, read, status",
            source=self.name,
        )
