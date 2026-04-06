"""
Точка входу додатка — ініціалізація агента, планувальника, запуск GUI.
python -m app.main
"""
import logging
import sys

# ---------------------------------------------------------------------------
# Логування
# ---------------------------------------------------------------------------

_handlers = [logging.StreamHandler(sys.stdout)]
try:
    from pathlib import Path as _P
    _P("data").mkdir(exist_ok=True)
    _handlers.append(logging.FileHandler("data/agent.log", encoding="utf-8"))
except OSError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=_handlers,
)
logger = logging.getLogger(__name__)


def main():
    """Головна функція запуску."""
    from pathlib import Path

    # data/ вже створено в logging setup
    Path("data").mkdir(exist_ok=True)

    logger.info("=" * 60)
    logger.info("  AI Агент — запуск")
    logger.info("=" * 60)

    # ------------------------------------------------------------------
    # 0. Ініціалізація бази даних (створення таблиць)
    # ------------------------------------------------------------------
    try:
        from app.db.database import init_db
        init_db()
    except Exception as e:
        logger.error("Помилка ініціалізації БД: %s", e)

    # ------------------------------------------------------------------
    # 1. Перевірка LLM-бекенду
    # ------------------------------------------------------------------
    from app.llm import get_llm_client
    from app.config import config as app_config

    client = get_llm_client()
    backend_name = app_config.llm_backend
    if client.is_available():
        models = client.list_models()
        logger.info("%s доступна. Моделі: %s", backend_name, ", ".join(models))
    else:
        logger.warning(
            "⚠️  %s НЕДОСТУПНА. "
            "Чат не працюватиме, але GUI відкриється.",
            backend_name,
        )

    # ------------------------------------------------------------------
    # 2. Ініціалізація агента
    # ------------------------------------------------------------------
    agent = None
    try:
        from app.agent import Agent
        agent = Agent()
        logger.info("Агент ініціалізовано: модель=%s", agent.llm.model)
    except Exception as e:
        logger.error("Помилка ініціалізації агента: %s", e)

    # ------------------------------------------------------------------
    # 3. Ініціалізація планувальника
    # ------------------------------------------------------------------
    scheduler_runner = None
    task_manager = None
    try:
        from app.scheduler.manager import TaskManager
        from app.scheduler.runner import SchedulerRunner

        task_manager = TaskManager()
        scheduler_runner = SchedulerRunner(task_manager=task_manager)
        scheduler_runner.start()
        logger.info("Планувальник запущено")
    except Exception as e:
        logger.error("Помилка ініціалізації планувальника: %s", e)

    # ------------------------------------------------------------------
    # 4. Запуск GUI
    # ------------------------------------------------------------------
    from app.gui.interface import create_interface, set_agent, set_scheduler, APP_CSS
    from app.config import config

    if agent:
        set_agent(agent)
    if scheduler_runner and task_manager:
        set_scheduler(scheduler_runner, task_manager)

    demo = create_interface()

    logger.info("Запуск Gradio на %s:%d", config.gui_host, config.gui_port)

    theme = "soft"

    try:
        demo.launch(
            server_name=config.gui_host,
            server_port=config.gui_port,
            share=False,
            show_error=True,
            theme=theme,
            css=APP_CSS,
        )
    except KeyboardInterrupt:
        logger.info("Зупинка по Ctrl+C")
    finally:
        if scheduler_runner and scheduler_runner.is_running:
            scheduler_runner.stop()
            logger.info("Планувальник зупинено")
        logger.info("Завершено")


if __name__ == "__main__":
    main()
