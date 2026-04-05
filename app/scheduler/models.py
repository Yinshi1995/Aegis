"""
Модель запланированной задачи в SQLite.
Хранит расписание, тип действия, конфигурацию и историю запусков.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from sqlalchemy.orm import declarative_base
import json
import logging

logger = logging.getLogger(__name__)

Base = declarative_base()


class ScheduledTask(Base):
    """Запланированная задача."""
    __tablename__ = "scheduled_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), unique=True, nullable=False, index=True)
    description = Column(Text, default="")

    # Расписание
    schedule_type = Column(String(20), nullable=False)   # "interval" | "cron" | "once"
    schedule_value = Column(String(200), nullable=False)  # "30m" / "0 9 * * *" / "2026-04-10 14:00"

    # Действие
    action_type = Column(String(20), nullable=False)     # "skill" | "tool" | "script" | "message"
    action_config = Column(Text, nullable=False)         # JSON: {"skill": "...", "params": {...}}

    # Статус
    is_active = Column(Boolean, default=True)
    on_error = Column(String(20), default="ignore")      # "ignore" | "retry" | "disable"

    # История запусков
    last_run = Column(DateTime, default=None)
    next_run = Column(DateTime, default=None)
    run_count = Column(Integer, default=0)
    last_result = Column(Text, default="")

    # Мета
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_action_config(self) -> dict:
        """Десериализация action_config из JSON."""
        try:
            return json.loads(self.action_config) if self.action_config else {}
        except json.JSONDecodeError:
            logger.warning("Невалидный action_config у задачи %s", self.name)
            return {}

    def set_action_config(self, cfg: dict):
        """Сериализация action_config в JSON."""
        self.action_config = json.dumps(cfg, ensure_ascii=False)

    def __repr__(self):
        return (
            f"<ScheduledTask(name='{self.name}', "
            f"schedule={self.schedule_type}:{self.schedule_value}, "
            f"action={self.action_type}, active={self.is_active}, "
            f"runs={self.run_count})>"
        )


class TaskHistory(Base):
    """Запись истории выполнения задачи."""
    __tablename__ = "task_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_name = Column(String(200), nullable=False, index=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, default=None)
    success = Column(Boolean, default=True)
    result = Column(Text, default="")
    error = Column(Text, default="")
