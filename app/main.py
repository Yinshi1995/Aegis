"""
Точка входу додатка — ініціалізація агента, планувальника, запуск GUI.
python -m app.main
"""
import logging
import sys

# ---------------------------------------------------------------------------
# Логування
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("data/agent.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def main():
    """Головна функція запуску."""
    from pathlib import Path

    # Створюємо data/ якщо не існує
    Path("data").mkdir(exist_ok=True)

    logger.info("=" * 60)
    logger.info("  AI Агент — запуск")
    logger.info("=" * 60)

    # ------------------------------------------------------------------
    # 1. Перевірка Ollama
    # ------------------------------------------------------------------
    from app.llm.ollama_client import OllamaClient
    client = OllamaClient()
    if client.is_available():
        models = client.list_models()
        logger.info("Ollama доступна. Моделі: %s", ", ".join(models))
    else:
        logger.warning(
            "⚠️  Ollama НЕДОСТУПНА на %s. "
            "Чат не працюватиме, але GUI відкриється.",
            client.base_url,
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
