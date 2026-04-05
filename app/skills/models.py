"""
Модели и менеджер скиллов (сохранённых промптов).
Скилл = промпт + метаданные + опциональный скрипт.
"""
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker
from typing import Optional
import json
import logging

logger = logging.getLogger(__name__)
Base = declarative_base()


class Skill(Base):
    """Модель скилла в БД."""
    __tablename__ = "skills"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), unique=True, nullable=False, index=True)
    description = Column(Text, default="")
    category = Column(String(100), default="general")  # напр. "rag", "automation", "analysis"

    # Промпт
    system_prompt = Column(Text, nullable=False)  # системный промпт скилла
    user_template = Column(Text, default="")       # шаблон для пользовательского ввода, с {placeholders}

    # Опциональный скрипт
    script_path = Column(String(500), default=None)   # путь к Python-скрипту
    script_params_schema = Column(Text, default="{}")  # JSON-схема параметров скрипта

    # Настройки
    requires_rag = Column(Boolean, default=False)      # нужен ли контекст из базы знаний
    temperature = Column(Integer, default=None)         # переопределение температуры (null = default)

    # Мета
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)


class SkillManager:
    """CRUD операции над скиллами."""

    def __init__(self, db_path: str = "./data/agent.db"):
        self.engine = create_engine(f"sqlite:///{db_path}", echo=False)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def create(self, name: str, system_prompt: str, **kwargs) -> Skill:
        """Создать новый скилл."""
        with self.Session() as session:
            skill = Skill(name=name, system_prompt=system_prompt, **kwargs)
            session.add(skill)
            session.commit()
            session.refresh(skill)
            logger.info(f"Скилл создан: {name}")
            return skill

    def get(self, name: str) -> Optional[Skill]:
        """Получить скилл по имени."""
        with self.Session() as session:
            return session.query(Skill).filter_by(name=name, is_active=True).first()

    def list_all(self, category: str = None) -> list[Skill]:
        """Список всех активных скиллов."""
        with self.Session() as session:
            q = session.query(Skill).filter_by(is_active=True)
            if category:
                q = q.filter_by(category=category)
            return q.order_by(Skill.name).all()

    def update(self, name: str, **kwargs) -> Optional[Skill]:
        """Обновить скилл."""
        with self.Session() as session:
            skill = session.query(Skill).filter_by(name=name).first()
            if not skill:
                return None
            for key, value in kwargs.items():
                if hasattr(skill, key):
                    setattr(skill, key, value)
            session.commit()
            session.refresh(skill)
            return skill

    def delete(self, name: str) -> bool:
        """Мягкое удаление скилла."""
        with self.Session() as session:
            skill = session.query(Skill).filter_by(name=name).first()
            if not skill:
                return False
            skill.is_active = False
            session.commit()
            return True

    def export_skill(self, name: str) -> Optional[dict]:
        """Экспорт скилла в JSON (для бекапа/обмена)."""
        skill = self.get(name)
        if not skill:
            return None
        return {
            "name": skill.name,
            "description": skill.description,
            "category": skill.category,
            "system_prompt": skill.system_prompt,
            "user_template": skill.user_template,
            "script_path": skill.script_path,
            "script_params_schema": skill.script_params_schema,
            "requires_rag": skill.requires_rag,
        }

    def import_skill(self, data: dict) -> Skill:
        """Импорт скилла из JSON."""
        return self.create(**data)
