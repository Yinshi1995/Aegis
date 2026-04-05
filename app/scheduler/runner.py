"""
Движок планировщика — запускает задачи по расписанию через APScheduler.
"""
import asyncio
import logging
import re
import threading
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.scheduler.manager import TaskManager
from app.scheduler.models import ScheduledTask
from app.scheduler.notifications import on_task_complete, on_task_error

logger = logging.getLogger(__name__)

# Регулярка для парсинга интервалов: "30s", "5m", "2h", "1d"
INTERVAL_RE = re.compile(r"^(\d+)\s*(s|m|h|d)$", re.IGNORECASE)

INTERVAL_UNITS = {
    "s": "seconds",
    "m": "minutes",
    "h": "hours",
    "d": "days",
}


def parse_interval(value: str) -> dict:
    """Парсинг строки интервала в kwargs для IntervalTrigger."""
    match = INTERVAL_RE.match(value.strip())
    if not match:
        raise ValueError(f"Невалидный интервал: '{value}'. Формат: 30s, 5m, 2h, 1d")
    amount = int(match.group(1))
    unit = INTERVAL_UNITS[match.group(2).lower()]
    return {unit: amount}


def parse_schedule(task: ScheduledTask):
    """Создать APScheduler trigger из задачи."""
    stype = task.schedule_type
    svalue = task.schedule_value.strip()

    if stype == "interval":
        kwargs = parse_interval(svalue)
        return IntervalTrigger(**kwargs)

    elif stype == "cron":
        fields = svalue.split()
        if len(fields) == 5:
            # стандартный cron: minute hour day month day_of_week
            return CronTrigger(
                minute=fields[0],
                hour=fields[1],
                day=fields[2],
                month=fields[3],
                day_of_week=fields[4],
            )
        elif len(fields) == 6:
            # с секундами: second minute hour day month day_of_week
            return CronTrigger(
                second=fields[0],
                minute=fields[1],
                hour=fields[2],
                day=fields[3],
                month=fields[4],
                day_of_week=fields[5],
            )
        else:
            raise ValueError(f"Невалидный cron: '{svalue}'. Формат: min hour day month dow")

    elif stype == "once":
        dt = datetime.strptime(svalue, "%Y-%m-%d %H:%M")
        return DateTrigger(run_date=dt)

    else:
        raise ValueError(f"Неизвестный schedule_type: {stype}")


class SchedulerRunner:
    """Движок планировщика задач."""

    def __init__(self, task_manager: TaskManager | None = None):
        self.task_manager = task_manager or TaskManager()
        self._scheduler = BackgroundScheduler()
        self._running = False
        # Ленивые ссылки на компоненты агента (загружаются при первом вызове)
        self._agent = None
        self._skill_executor = None
        self._skill_manager = None

    @property
    def is_running(self) -> bool:
        return self._running

    # ------------------------------------------------------------------
    # Запуск / остановка
    # ------------------------------------------------------------------

    def start(self):
        """Запустить планировщик."""
        if self._running:
            logger.warning("Планировщик уже запущен")
            return

        # Загружаем активные задачи
        tasks = self.task_manager.list_tasks(active_only=True)
        for task in tasks:
            self._add_job(task)

        self._scheduler.start()
        self._running = True
        logger.info("Планировщик запущен, задач: %d", len(tasks))

    def stop(self):
        """Остановить планировщик."""
        if not self._running:
            return
        self._scheduler.shutdown(wait=False)
        self._running = False
        logger.info("Планировщик остановлен")

    def reload(self):
        """Перезагрузить все задачи (после изменений в БД)."""
        if self._running:
            self._scheduler.remove_all_jobs()
            tasks = self.task_manager.list_tasks(active_only=True)
            for task in tasks:
                self._add_job(task)
            logger.info("Задачи перезагружены: %d", len(tasks))

    # ------------------------------------------------------------------
    # Управление задачами
    # ------------------------------------------------------------------

    def _add_job(self, task: ScheduledTask):
        """Добавить задачу в APScheduler."""
        try:
            trigger = parse_schedule(task)
            self._scheduler.add_job(
                func=self._execute_task,
                trigger=trigger,
                args=[task.name],
                id=f"task_{task.name}",
                name=task.name,
                replace_existing=True,
                misfire_grace_time=60,
            )
            logger.info(
                "Задача добавлена: %s (%s: %s)",
                task.name, task.schedule_type, task.schedule_value,
            )
        except Exception as e:
            logger.error("Ошибка добавления задачи %s: %s", task.name, e)

    # ------------------------------------------------------------------
    # Выполнение задачи
    # ------------------------------------------------------------------

    def _execute_task(self, task_name: str):
        """Выполнить задачу (вызывается APScheduler)."""
        task = self.task_manager.get_task(task_name)
        if not task or not task.is_active:
            logger.warning("Задача %s не найдена или неактивна", task_name)
            return

        logger.info("Выполняю задачу: %s (тип: %s)", task_name, task.action_type)
        action_config = task.get_action_config()

        try:
            result = self._dispatch_action(task.action_type, action_config)
            self.task_manager.record_run(task_name, success=True, result=result)
            on_task_complete(task, result)
            logger.info("Задача %s выполнена: %s", task_name, result[:100])

        except Exception as e:
            error_msg = str(e)
            logger.error("Ошибка задачи %s: %s", task_name, error_msg)
            self.task_manager.record_run(task_name, success=False, error=error_msg)
            on_task_error(task, error_msg)

            # Retry: перезапуск при on_error=retry
            if task.on_error == "retry":
                logger.info("Повторная попытка задачи %s...", task_name)
                try:
                    result = self._dispatch_action(task.action_type, action_config)
                    self.task_manager.record_run(task_name, success=True, result=result)
                except Exception as e2:
                    self.task_manager.record_run(task_name, success=False, error=str(e2))

    def _dispatch_action(self, action_type: str, action_config: dict) -> str:
        """Выполнить действие по типу."""
        if action_type == "skill":
            return self._run_skill(action_config)
        elif action_type == "tool":
            return self._run_tool(action_config)
        elif action_type == "script":
            return self._run_script(action_config)
        elif action_type == "message":
            return self._run_message(action_config)
        else:
            raise ValueError(f"Неизвестный action_type: {action_type}")

    # ------------------------------------------------------------------
    # Диспатч по типам действий
    # ------------------------------------------------------------------

    def _run_skill(self, cfg: dict) -> str:
        """Выполнить скилл."""
        from app.skills.manager import Manager
        from app.skills.executor import SkillExecutor

        if not self._skill_manager:
            self._skill_manager = Manager()
        if not self._skill_executor:
            self._skill_executor = SkillExecutor()

        skill_name = cfg.get("skill", "")
        params = cfg.get("params", {})
        result = self._skill_executor.execute_by_name(skill_name, self._skill_manager, **params)
        if result.success:
            return result.answer
        raise RuntimeError(f"Скилл '{skill_name}' ошибка: {result.error}")

    def _run_tool(self, cfg: dict) -> str:
        """Выполнить инструмент."""
        from app.tools import register_all_tools
        from app.tools.base import registry

        register_all_tools()
        tool_name = cfg.get("tool", "")
        params = cfg.get("params", {})

        tool = registry.get(tool_name)
        if not tool:
            raise ValueError(f"Инструмент '{tool_name}' не найден")

        # Запускаем async в sync-контексте
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(tool.safe_execute(**params))
        finally:
            loop.close()

        if result.success:
            return str(result.data)
        raise RuntimeError(f"Инструмент '{tool_name}' ошибка: {result.error}")

    def _run_script(self, cfg: dict) -> str:
        """Запустить скрипт."""
        from app.tools.script_runner import ScriptRunnerTool

        runner = ScriptRunnerTool()
        script = cfg.get("script", "")
        args = cfg.get("args", {})

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                runner.safe_execute(action="run", script=script, args=args)
            )
        finally:
            loop.close()

        if result.success:
            return str(result.data)
        raise RuntimeError(f"Скрипт '{script}' ошибка: {result.error}")

    def _run_message(self, cfg: dict) -> str:
        """Отправить сообщение агенту."""
        from app.agent import Agent

        if not self._agent:
            self._agent = Agent()

        message = cfg.get("message", "")
        loop = asyncio.new_event_loop()
        try:
            resp = loop.run_until_complete(self._agent.process_message(message))
        finally:
            loop.close()

        return resp.text
