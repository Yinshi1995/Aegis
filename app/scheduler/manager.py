"""
CRUD-менеджер запланированных задач.
"""
import json
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import config
from app.scheduler.models import Base, ScheduledTask, TaskHistory

logger = logging.getLogger(__name__)

# Предустановленные задачи
PRESET_TASKS = [
    {
        "name": "daily_report",
        "description": "Щоденний аналіз бази знань о 9:00",
        "schedule_type": "cron",
        "schedule_value": "0 9 * * *",
        "action_type": "skill",
        "action_config": {
            "skill": "analyze_document",
            "params": {"topic": "загальний стан бази знань"},
        },
        "on_error": "ignore",
    },
    {
        "name": "check_site",
        "description": "Перевірка сайту кожні 2 години",
        "schedule_type": "interval",
        "schedule_value": "2h",
        "action_type": "tool",
        "action_config": {
            "tool": "web_scraper",
            "params": {"action": "extract_text", "url": "https://example.com"},
        },
        "on_error": "retry",
    },
]


class TaskManager:
    """CRUD для запланированных задач."""

    def __init__(self, db_path: str | None = None):
        db_path = db_path or config.skills.db_path
        if config.database.db_type == "postgres" and config.database.database_url:
            self.engine = create_engine(
                config.database.database_url, echo=False,
                pool_pre_ping=True, pool_size=5, max_overflow=10,
            )
        else:
            self.engine = create_engine(f"sqlite:///{db_path}", echo=False)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        self._ensure_presets()

    def dispose(self):
        """Освободить соединения с БД."""
        self.engine.dispose()

    def _ensure_presets(self):
        """Создать предустановленные задачи, если их нет."""
        for preset in PRESET_TASKS:
            existing = self.get_task(preset["name"])
            if not existing:
                try:
                    self.create_task(**preset)
                    logger.info("Предустановленная задача создана: %s", preset["name"])
                except Exception as e:
                    logger.warning("Не удалось создать пресет %s: %s", preset["name"], e)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_task(
        self,
        name: str,
        schedule_type: str,
        schedule_value: str,
        action_type: str,
        action_config: dict,
        description: str = "",
        on_error: str = "ignore",
        is_active: bool = True,
    ) -> ScheduledTask:
        """Создать новую задачу."""
        name = name.strip()
        if not name:
            raise ValueError("Имя задачи не может быть пустым")
        if schedule_type not in ("interval", "cron", "once"):
            raise ValueError(f"Невалидный schedule_type: {schedule_type}")
        if action_type not in ("skill", "tool", "script", "message"):
            raise ValueError(f"Невалидный action_type: {action_type}")
        if on_error not in ("ignore", "retry", "disable"):
            raise ValueError(f"Невалидный on_error: {on_error}")

        with self.Session() as session:
            existing = session.query(ScheduledTask).filter_by(name=name).first()
            if existing:
                raise ValueError(f"Задача '{name}' уже существует")

            task = ScheduledTask(
                name=name,
                description=description,
                schedule_type=schedule_type,
                schedule_value=schedule_value,
                action_type=action_type,
                action_config=json.dumps(action_config, ensure_ascii=False),
                is_active=is_active,
                on_error=on_error,
            )
            session.add(task)
            session.commit()
            session.refresh(task)
            logger.info("Задача создана: %s (%s: %s)", name, schedule_type, schedule_value)
            return task

    def get_task(self, name: str) -> Optional[ScheduledTask]:
        """Получить задачу по имени."""
        with self.Session() as session:
            return session.query(ScheduledTask).filter_by(name=name).first()

    def list_tasks(self, active_only: bool = False) -> list[ScheduledTask]:
        """Список задач."""
        with self.Session() as session:
            q = session.query(ScheduledTask)
            if active_only:
                q = q.filter_by(is_active=True)
            return q.order_by(ScheduledTask.name).all()

    def update_task(self, name: str, **kwargs) -> Optional[ScheduledTask]:
        """Обновить задачу."""
        forbidden = {"id", "created_at"}
        bad = set(kwargs.keys()) & forbidden
        if bad:
            raise ValueError(f"Нельзя менять поля: {bad}")

        with self.Session() as session:
            task = session.query(ScheduledTask).filter_by(name=name).first()
            if not task:
                return None
            for key, value in kwargs.items():
                if key == "action_config" and isinstance(value, dict):
                    value = json.dumps(value, ensure_ascii=False)
                if hasattr(task, key):
                    setattr(task, key, value)
            session.commit()
            session.refresh(task)
            return task

    def delete_task(self, name: str) -> bool:
        """Удалить задачу (жёсткое удаление)."""
        with self.Session() as session:
            task = session.query(ScheduledTask).filter_by(name=name).first()
            if not task:
                return False
            session.delete(task)
            session.commit()
            return True

    def enable_task(self, name: str) -> Optional[ScheduledTask]:
        """Включить задачу."""
        return self.update_task(name, is_active=True)

    def disable_task(self, name: str) -> Optional[ScheduledTask]:
        """Выключить задачу."""
        return self.update_task(name, is_active=False)

    # ------------------------------------------------------------------
    # Обновление после запуска
    # ------------------------------------------------------------------

    def record_run(
        self,
        name: str,
        success: bool,
        result: str = "",
        error: str = "",
    ):
        """Записать результат выполнения задачи."""
        now = datetime.utcnow()
        with self.Session() as session:
            task = session.query(ScheduledTask).filter_by(name=name).first()
            if task:
                task.last_run = now
                task.run_count = (task.run_count or 0) + 1
                task.last_result = result[:5000] if result else ""
                # on_error=disable → отключаем при ошибке
                if not success and task.on_error == "disable":
                    task.is_active = False
                    logger.warning("Задача '%s' отключена после ошибки", name)
                session.commit()

            # Запись в историю
            entry = TaskHistory(
                task_name=name,
                started_at=now,
                finished_at=datetime.utcnow(),
                success=success,
                result=result[:5000] if result else "",
                error=error[:2000] if error else "",
            )
            session.add(entry)
            session.commit()

    def get_history(self, task_name: str, limit: int = 20) -> list[TaskHistory]:
        """Получить историю запусков задачи."""
        with self.Session() as session:
            return (
                session.query(TaskHistory)
                .filter_by(task_name=task_name)
                .order_by(TaskHistory.id.desc())
                .limit(limit)
                .all()
            )
