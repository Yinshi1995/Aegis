"""
Автозагрузчик плагинов из папки app/tools/plugins/.
Сканирует все .py файлы, находит классы-наследники BaseTool и регистрирует в реестре.
"""
import importlib
import importlib.util
import inspect
import logging
from pathlib import Path
from app.tools.base import BaseTool, ToolRegistry

logger = logging.getLogger(__name__)

PLUGINS_DIR = Path(__file__).parent / "plugins"


def discover_plugins() -> list[type[BaseTool]]:
    """
    Найти все классы-наследники BaseTool в папке plugins/.

    Возвращает список классов (не экземпляров).
    """
    PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
    found: list[type[BaseTool]] = []

    for py_file in sorted(PLUGINS_DIR.glob("*.py")):
        if py_file.name.startswith("_"):
            continue

        module_name = f"app.tools.plugins.{py_file.stem}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, py_file)
            if spec is None or spec.loader is None:
                logger.warning("Не удалось загрузить спецификацию: %s", py_file)
                continue

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            for _name, obj in inspect.getmembers(module, inspect.isclass):
                if (
                    issubclass(obj, BaseTool)
                    and obj is not BaseTool
                    and not inspect.isabstract(obj)
                ):
                    found.append(obj)
                    logger.info("Плагин найден: %s из %s", obj.name, py_file.name)

        except Exception as e:
            logger.error("Ошибка загрузки плагина %s: %s", py_file.name, e)

    return found


def load_plugins(registry: ToolRegistry) -> int:
    """
    Загрузить все плагины и зарегистрировать в реестре.

    Возвращает количество загруженных плагинов.
    """
    plugins = discover_plugins()
    count = 0
    for plugin_cls in plugins:
        try:
            instance = plugin_cls()
            registry.register(instance)
            count += 1
        except Exception as e:
            logger.error("Ошибка инициализации плагина %s: %s", plugin_cls.name, e)
    logger.info("Загружено плагинов: %d", count)
    return count
