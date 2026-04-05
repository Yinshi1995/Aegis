"""
Инструмент для автоматизации браузера через Playwright.
Позволяет открывать страницы, извлекать текст, делать скриншоты, кликать элементы.
"""
import logging
from pathlib import Path
from app.tools.base import BaseTool, ToolResult
from app.config import config

logger = logging.getLogger(__name__)


class BrowserTool(BaseTool):
    """Браузер-автоматизация через Playwright."""

    name = "browser"
    description = (
        "Управляет браузером: открывает URL, извлекает текст страницы, "
        "делает скриншоты, кликает по элементам. "
        "Параметры: action (open|get_text|screenshot|click|close), "
        "url, selector, path."
    )

    def __init__(self):
        self._playwright = None
        self._browser = None
        self._page = None

    async def _ensure_browser(self):
        """Ленивая инициализация браузера."""
        if self._page is not None:
            return
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise RuntimeError(
                "playwright не установлен. Выполните: pip install playwright && playwright install chromium"
            )
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=config.tools.headless
        )
        self._page = await self._browser.new_page()
        logger.info("Браузер запущен (headless=%s)", config.tools.headless)

    async def _close_browser(self):
        """Закрыть браузер и освободить ресурсы."""
        if self._page:
            await self._page.close()
            self._page = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        logger.info("Браузер закрыт")

    async def execute(self, **params) -> ToolResult:
        """
        Выполнить действие в браузере.

        Параметры:
            action: "open" | "get_text" | "screenshot" | "click" | "close"
            url: URL для открытия (action=open)
            selector: CSS-селектор элемента (action=click|get_text)
            path: путь для сохранения скриншота (action=screenshot)
        """
        action = params.get("action", "")

        if action == "close":
            await self._close_browser()
            return ToolResult(success=True, data="Браузер закрыт", source=self.name)

        if action == "open":
            url = params.get("url")
            if not url:
                return ToolResult(success=False, error="Не указан url", source=self.name)
            await self._ensure_browser()
            response = await self._page.goto(url, wait_until="domcontentloaded", timeout=config.tools.browser_timeout * 1000)
            status = response.status if response else "unknown"
            title = await self._page.title()
            return ToolResult(
                success=True,
                data={"title": title, "url": self._page.url, "status": status},
                source=self.name,
            )

        if action == "get_text":
            await self._ensure_browser()
            selector = params.get("selector")
            if selector:
                el = await self._page.query_selector(selector)
                if not el:
                    return ToolResult(success=False, error=f"Элемент не найден: {selector}", source=self.name)
                text = await el.inner_text()
            else:
                text = await self._page.inner_text("body")
            # Ограничиваем длину текста для LLM
            max_len = params.get("max_length", 8000)
            if len(text) > max_len:
                text = text[:max_len] + f"\n\n... (обрезано, всего {len(text)} символов)"
            return ToolResult(success=True, data=text, source=self.name)

        if action == "screenshot":
            await self._ensure_browser()
            path = params.get("path", "./data/screenshot.png")
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            await self._page.screenshot(path=path, full_page=params.get("full_page", False))
            return ToolResult(success=True, data={"saved": str(path)}, source=self.name)

        if action == "click":
            selector = params.get("selector")
            if not selector:
                return ToolResult(success=False, error="Не указан selector", source=self.name)
            await self._ensure_browser()
            await self._page.click(selector, timeout=config.tools.browser_timeout * 1000)
            return ToolResult(success=True, data=f"Клик по {selector}", source=self.name)

        return ToolResult(
            success=False,
            error=f"Неизвестное действие: {action}. Доступны: open, get_text, screenshot, click, close",
            source=self.name,
        )
