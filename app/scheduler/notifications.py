"""
Уведомления при выполнении / ошибке задач.
Заглушка — логирует события. В будущем: Telegram, email, WhatsApp.
"""
import logging
from app.scheduler.models import ScheduledTask

logger = logging.getLogger(__name__)


def on_task_complete(task: ScheduledTask, result: str):
    """Вызывается после успешного выполнения задачи."""
    logger.info(
        "[NOTIFICATION] Задача '%s' выполнена. Результат: %s",
        task.name,
        result[:200] if result else "(пусто)",
    )
    # TODO: Telegram-бот: send_message(chat_id, f"✅ {task.name}: {result[:500]}")
    # TODO: Email: send_email(subject=f"Task {task.name} OK", body=result)
    # TODO: WhatsApp: whatsapp.send(phone, result)


def on_task_error(task: ScheduledTask, error: str):
    """Вызывается при ошибке выполнения задачи."""
    logger.error(
        "[NOTIFICATION] Задача '%s' ОШИБКА: %s",
        task.name,
        error[:500],
    )
    # TODO: Telegram-бот: send_message(chat_id, f"❌ {task.name}: {error[:500]}")
    # TODO: Email: send_email(subject=f"Task {task.name} FAILED", body=error)
