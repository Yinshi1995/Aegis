"""
Инструмент для работы с файловой системой.
Чтение, запись файлов, листинг директорий — в пределах проекта.
"""
import logging
from pathlib import Path
from app.tools.base import BaseTool, ToolResult
from app.config import config

logger = logging.getLogger(__name__)

# Разрешённые корневые директории (относительно project_root)
ALLOWED_ROOTS = {"knowledge_base", "data", "scripts"}


class FileManagerTool(BaseTool):
    """Работа с файлами проекта (чтение, запись, листинг)."""

    name = "file_manager"
    description = (
        "Работает с файлами: читает, записывает, перечисляет содержимое директорий. "
        "Ограничен папками knowledge_base/, data/, scripts/. "
        "Параметры: action (read|write|list|info), path, content."
    )

    def _resolve_safe(self, rel_path: str) -> Path | None:
        """Разрешить путь безопасно — только внутри разрешённых корней."""
        project_root = config.project_root
        resolved = (project_root / rel_path).resolve()
        # Проверяем, что путь внутри одного из разрешённых корней
        for root_name in ALLOWED_ROOTS:
            allowed = (project_root / root_name).resolve()
            try:
                resolved.relative_to(allowed)
                return resolved
            except ValueError:
                continue
        return None

    async def execute(self, **params) -> ToolResult:
        """
        Действия с файлами.

        Параметры:
            action: "read" | "write" | "list" | "info"
            path: относительный путь от корня проекта (например "knowledge_base/doc.pdf")
            content: текст для записи (action=write)
            encoding: кодировка (по умолчанию utf-8)
        """
        action = params.get("action", "")
        rel_path = params.get("path", "")
        encoding = params.get("encoding", "utf-8")

        if not rel_path:
            return ToolResult(success=False, error="Не указан path", source=self.name)

        safe_path = self._resolve_safe(rel_path)
        if safe_path is None:
            return ToolResult(
                success=False,
                error=f"Доступ запрещён: {rel_path}. Разрешены: {', '.join(sorted(ALLOWED_ROOTS))}",
                source=self.name,
            )

        if action == "list":
            if not safe_path.is_dir():
                return ToolResult(success=False, error=f"Не директория: {rel_path}", source=self.name)
            items = []
            for p in sorted(safe_path.iterdir()):
                items.append({
                    "name": p.name,
                    "type": "dir" if p.is_dir() else "file",
                    "size": p.stat().st_size if p.is_file() else None,
                })
            return ToolResult(success=True, data=items, source=self.name)

        if action == "read":
            if not safe_path.is_file():
                return ToolResult(success=False, error=f"Файл не найден: {rel_path}", source=self.name)
            max_size = params.get("max_size", 100_000)  # 100KB
            size = safe_path.stat().st_size
            if size > max_size:
                return ToolResult(
                    success=False,
                    error=f"Файл слишком большой: {size} байт (лимит {max_size})",
                    source=self.name,
                )
            text = safe_path.read_text(encoding=encoding)
            return ToolResult(success=True, data=text, source=self.name)

        if action == "write":
            content = params.get("content")
            if content is None:
                return ToolResult(success=False, error="Не указан content", source=self.name)
            safe_path.parent.mkdir(parents=True, exist_ok=True)
            safe_path.write_text(content, encoding=encoding)
            logger.info("Записан файл: %s (%d байт)", safe_path, len(content))
            return ToolResult(
                success=True,
                data={"path": str(safe_path), "size": len(content)},
                source=self.name,
            )

        if action == "info":
            if not safe_path.exists():
                return ToolResult(success=False, error=f"Не найден: {rel_path}", source=self.name)
            stat = safe_path.stat()
            return ToolResult(
                success=True,
                data={
                    "path": str(safe_path),
                    "type": "dir" if safe_path.is_dir() else "file",
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                },
                source=self.name,
            )

        return ToolResult(
            success=False,
            error=f"Неизвестное действие: {action}. Доступны: read, write, list, info",
            source=self.name,
        )
