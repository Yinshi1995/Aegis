"""
Инструменты агента — регистрация встроенных + автозагрузка плагинов.
"""
import logging
from app.tools.base import registry
from app.tools.browser import BrowserTool
from app.tools.web_scraper import WebScraperTool
from app.tools.file_manager import FileManagerTool
from app.tools.whatsapp import WhatsAppTool
from app.tools.script_runner import ScriptRunnerTool
from app.tools.plugin_loader import load_plugins

logger = logging.getLogger(__name__)

_initialized = False


def register_all_tools() -> None:
    """Зарегистрировать все встроенные инструменты + загрузить плагины."""
    global _initialized
    if _initialized:
        return

    # Встроенные инструменты
    builtin = [
        BrowserTool(),
        WebScraperTool(),
        FileManagerTool(),
        WhatsAppTool(),
        ScriptRunnerTool(),
    ]
    for tool in builtin:
        registry.register(tool)

    # Плагины из app/tools/plugins/
    load_plugins(registry)

    _initialized = True
    logger.info(
        "Все инструменты зарегистрированы: %s",
        ", ".join(registry.names),
    )
