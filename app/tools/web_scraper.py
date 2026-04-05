"""
Инструмент для скрапинга веб-страниц.
Извлекает структурированные данные: заголовки, ссылки, таблицы, мета-теги.
"""
import logging
from app.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class WebScraperTool(BaseTool):
    """Извлечение структурированных данных со страниц."""

    name = "web_scraper"
    description = (
        "Скрапит веб-страницы: извлекает заголовки, ссылки, таблицы, мета-теги, "
        "основной текст. Параметры: action (extract_text|extract_links|extract_tables"
        "|extract_meta), url."
    )

    async def execute(self, **params) -> ToolResult:
        """
        Скрапить страницу.

        Параметры:
            action: "extract_text" | "extract_links" | "extract_tables" | "extract_meta"
            url: URL страницы
            selector: CSS-селектор для ограничения области (опционально)
        """
        action = params.get("action", "extract_text")
        url = params.get("url")
        if not url:
            return ToolResult(success=False, error="Не указан url", source=self.name)

        try:
            import httpx
            from bs4 import BeautifulSoup
        except ImportError:
            return ToolResult(
                success=False,
                error="Требуются пакеты: pip install httpx beautifulsoup4",
                source=self.name,
            )

        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                resp.raise_for_status()
        except httpx.HTTPError as e:
            return ToolResult(success=False, error=f"HTTP ошибка: {e}", source=self.name)

        soup = BeautifulSoup(resp.text, "html.parser")
        selector = params.get("selector")
        root = soup.select_one(selector) if selector else soup

        if not root:
            return ToolResult(success=False, error=f"Селектор не найден: {selector}", source=self.name)

        if action == "extract_text":
            # Убираем скрипты и стили
            for tag in root.find_all(["script", "style", "nav", "footer"]):
                tag.decompose()
            text = root.get_text(separator="\n", strip=True)
            max_len = params.get("max_length", 8000)
            if len(text) > max_len:
                text = text[:max_len] + f"\n\n... (обрезано, всего {len(text)} символов)"
            return ToolResult(success=True, data=text, source=self.name)

        if action == "extract_links":
            links = []
            for a in root.find_all("a", href=True):
                href = a["href"]
                label = a.get_text(strip=True)[:100]
                if href.startswith(("http", "//")):
                    links.append({"href": href, "text": label})
            return ToolResult(success=True, data=links, source=self.name)

        if action == "extract_tables":
            tables = []
            for table in root.find_all("table"):
                rows = []
                for tr in table.find_all("tr"):
                    cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                    if cells:
                        rows.append(cells)
                if rows:
                    tables.append(rows)
            return ToolResult(success=True, data=tables, source=self.name)

        if action == "extract_meta":
            meta = {
                "title": soup.title.string if soup.title else None,
                "description": None,
                "keywords": None,
                "og": {},
            }
            for tag in soup.find_all("meta"):
                name = tag.get("name", "").lower()
                prop = tag.get("property", "").lower()
                content = tag.get("content", "")
                if name == "description":
                    meta["description"] = content
                elif name == "keywords":
                    meta["keywords"] = content
                elif prop.startswith("og:"):
                    meta["og"][prop] = content
            return ToolResult(success=True, data=meta, source=self.name)

        return ToolResult(
            success=False,
            error=f"Неизвестное действие: {action}. Доступны: extract_text, extract_links, extract_tables, extract_meta",
            source=self.name,
        )
