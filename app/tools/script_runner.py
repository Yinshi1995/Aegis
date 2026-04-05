"""
Инструмент для запуска Python-скриптов из папки scripts/.
Безопасный: только из scripts/, таймаут 60с, перехват stdout/stderr.
"""
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from app.tools.base import BaseTool, ToolResult
from app.config import config

logger = logging.getLogger(__name__)

SCRIPTS_DIR = config.project_root / "scripts"
MAX_TIMEOUT = 60  # секунд


class ScriptRunnerTool(BaseTool):
    """Запуск Python-скриптов из папки scripts/."""

    name = "script_runner"
    description = (
        "Запускает Python-скрипты из папки scripts/. "
        "Параметры: action (run|list), script (имя файла), args (словарь аргументов). "
        "Скрипт получает args как JSON через stdin. Таймаут 60 секунд."
    )

    def _resolve_script(self, script_name: str) -> Path | None:
        """Безопасно разрешить путь к скрипту — только внутри scripts/."""
        scripts_root = SCRIPTS_DIR.resolve()
        script_path = (scripts_root / script_name).resolve()
        # Защита от path traversal
        try:
            script_path.relative_to(scripts_root)
        except ValueError:
            return None
        if not script_path.suffix == ".py":
            return None
        return script_path

    async def execute(self, **params) -> ToolResult:
        """
        Запустить или перечислить скрипты.

        Параметры:
            action: "run" | "list"
            script: имя .py файла в scripts/ (для action=run)
            args: словарь аргументов, передаётся скрипту как JSON через stdin
            timeout: таймаут в секундах (по умолчанию 60, максимум 60)
        """
        action = params.get("action", "list")

        if action == "list":
            SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
            scripts = []
            for p in sorted(SCRIPTS_DIR.glob("*.py")):
                if p.name.startswith("_"):
                    continue
                # Прочитать первую строку для описания
                desc = ""
                try:
                    first_lines = p.read_text(encoding="utf-8")[:500]
                    if first_lines.startswith('"""'):
                        end = first_lines.find('"""', 3)
                        if end > 0:
                            desc = first_lines[3:end].strip().split("\n")[0]
                    elif first_lines.startswith("#"):
                        desc = first_lines.split("\n")[0].lstrip("# ").strip()
                except Exception:
                    pass
                scripts.append({"name": p.name, "description": desc})
            return ToolResult(success=True, data=scripts, source=self.name)

        if action == "run":
            script_name = params.get("script")
            if not script_name:
                return ToolResult(success=False, error="Не указан script", source=self.name)

            script_path = self._resolve_script(script_name)
            if script_path is None:
                return ToolResult(
                    success=False,
                    error=f"Скрипт не найден или запрещён: {script_name}",
                    source=self.name,
                )
            if not script_path.exists():
                return ToolResult(success=False, error=f"Файл не существует: {script_name}", source=self.name)

            args = params.get("args", {})
            timeout = min(params.get("timeout", MAX_TIMEOUT), MAX_TIMEOUT)
            stdin_data = json.dumps(args, ensure_ascii=False)

            try:
                env = {**os.environ, "PYTHONUTF8": "1"}
                process = await asyncio.create_subprocess_exec(
                    sys.executable, str(script_path),
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(config.project_root),
                    env=env,
                )
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(input=stdin_data.encode("utf-8")),
                    timeout=timeout,
                )
                stdout_text = stdout.decode("utf-8", errors="replace").strip()
                stderr_text = stderr.decode("utf-8", errors="replace").strip()

                if process.returncode == 0:
                    return ToolResult(
                        success=True,
                        data={"stdout": stdout_text, "stderr": stderr_text, "returncode": 0},
                        source=self.name,
                    )
                else:
                    return ToolResult(
                        success=False,
                        error=f"Скрипт завершился с кодом {process.returncode}",
                        data={"stdout": stdout_text, "stderr": stderr_text, "returncode": process.returncode},
                        source=self.name,
                    )
            except asyncio.TimeoutError:
                process.kill()
                return ToolResult(
                    success=False,
                    error=f"Таймаут: скрипт не завершился за {timeout}с",
                    source=self.name,
                )
            except Exception as e:
                return ToolResult(success=False, error=f"Ошибка запуска: {e}", source=self.name)

        return ToolResult(
            success=False,
            error=f"Неизвестное действие: {action}. Доступны: run, list",
            source=self.name,
        )
