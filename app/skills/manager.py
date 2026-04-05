"""
Высокоуровневый менеджер скиллов.
Обёртка над SkillManager из models.py с валидацией, логированием и предустановками.
"""
import logging
from typing import Optional

from app.skills.models import Skill, SkillManager
from app.config import config

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Предустановленные скиллы
# ------------------------------------------------------------------

PRESET_SKILLS = [
    {
        "name": "analyze_document",
        "description": "Аналіз та підсумок документа з бази знань",
        "category": "rag",
        "system_prompt": (
            "Ти — аналітик документів. Твоє завдання — проаналізувати наданий контекст "
            "з бази знань та зробити структурований підсумок.\n\n"
            "Правила:\n"
            "1. Використовуй ТІЛЬКИ інформацію з контексту.\n"
            "2. Структуруй відповідь: основні тези, ключові факти, числа.\n"
            "3. Вказуй джерело для кожного факту: [Джерело: файл, стор. N].\n"
            "4. Якщо контекст порожній — скажи прямо.\n"
        ),
        "user_template": "Проаналізуй та підсумуй інформацію про: {topic}",
        "requires_rag": True,
        "temperature": None,
    },
    {
        "name": "knowledge_qa",
        "description": "Відповідь на питання по базі знань з перевіркою галюцинацій",
        "category": "rag",
        "system_prompt": (
            "Ти — експерт з бази знань. Відповідай ТІЛЬКИ на основі наданого контексту.\n\n"
            "Правила:\n"
            "1. Якщо відповіді немає в контексті — скажи: 'В базі знань немає інформації з цього питання.'\n"
            "2. НЕ вигадуй і НЕ додавай від себе.\n"
            "3. Для кожного твердження вказуй джерело: [Джерело: файл, стор. N].\n"
            "4. Відповідай мовою питання.\n"
        ),
        "user_template": "{question}",
        "requires_rag": True,
        "temperature": None,
    },
    {
        "name": "translate",
        "description": "Переклад тексту на вказану мову",
        "category": "generation",
        "system_prompt": (
            "Ти — професійний перекладач. Перекладай точно, зберігаючи стиль і смисл оригіналу.\n"
            "Якщо в тексті є терміни — надай переклад і оригінал у дужках.\n"
            "Не додавай пояснення, тільки переклад.\n"
        ),
        "user_template": "Переведи на {target_language}: {text}",
        "requires_rag": False,
        "temperature": None,
    },
    {
        "name": "code_gen",
        "description": "Генерація коду за описом",
        "category": "generation",
        "system_prompt": (
            "Ти — досвідчений програміст. Пиши чистий, робочий код.\n\n"
            "Правила:\n"
            "1. Код повинен бути готовий до запуску.\n"
            "2. Додай короткі коментарі до ключових частин.\n"
            "3. Використовуй сучасні практики та ідіоми мови.\n"
            "4. Якщо потрібні залежності — вкажи їх.\n"
        ),
        "user_template": "Напиши код на {language}: {description}",
        "requires_rag": False,
        "temperature": None,
    },
]


# ------------------------------------------------------------------
# Manager
# ------------------------------------------------------------------

class Manager:
    """Высокоуровневый менеджер скиллов — валидация, пресеты, единая точка входа."""

    def __init__(self, db_path: str | None = None):
        db_path = db_path or config.skills.db_path
        self._store = SkillManager(db_path)
        self._ensure_presets()

    # ------------------------------------------------------------------
    # Пресеты
    # ------------------------------------------------------------------

    def _ensure_presets(self):
        """Создаёт предустановленные скиллы, если их ещё нет."""
        for preset in PRESET_SKILLS:
            existing = self._store.get(preset["name"])
            if not existing:
                try:
                    self._store.create(**preset)
                    logger.info(f"Предустановленный скилл создан: {preset['name']}")
                except Exception as e:
                    logger.warning(f"Не удалось создать пресет {preset['name']}: {e}")

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_skill(
        self,
        name: str,
        system_prompt: str,
        description: str = "",
        category: str = "general",
        user_template: str = "",
        requires_rag: bool = False,
        script_path: str | None = None,
        temperature: int | None = None,
    ) -> Skill:
        """Создать новый скилл с валидацией.

        Raises:
            ValueError: Если имя пустое или скилл с таким именем уже существует.
        """
        name = name.strip()
        if not name:
            raise ValueError("Имя скилла не может быть пустым")
        if not system_prompt.strip():
            raise ValueError("system_prompt не может быть пустым")

        existing = self._store.get(name)
        if existing:
            raise ValueError(f"Скилл с именем '{name}' уже существует")

        skill = self._store.create(
            name=name,
            system_prompt=system_prompt,
            description=description,
            category=category,
            user_template=user_template,
            requires_rag=requires_rag,
            script_path=script_path,
            temperature=temperature,
        )
        logger.info(f"Скилл создан: {name} (категория: {category})")
        return skill

    def get_skill(self, name: str) -> Optional[Skill]:
        """Получить скилл по имени."""
        skill = self._store.get(name)
        if not skill:
            logger.warning(f"Скилл не найден: {name}")
        return skill

    def list_skills(self, category: str | None = None) -> list[Skill]:
        """Список всех активных скиллов."""
        skills = self._store.list_all(category=category)
        logger.debug(f"Скиллы: {len(skills)} (категория: {category or 'все'})")
        return skills

    def update_skill(self, name: str, **kwargs) -> Optional[Skill]:
        """Обновить скилл. Только переданные поля.

        Raises:
            ValueError: Если скилл не найден.
        """
        # Запрещаем менять служебные поля
        forbidden = {"id", "created_at", "is_active"}
        bad_keys = set(kwargs.keys()) & forbidden
        if bad_keys:
            raise ValueError(f"Нельзя менять поля: {bad_keys}")

        skill = self._store.update(name, **kwargs)
        if not skill:
            raise ValueError(f"Скилл не найден: {name}")

        logger.info(f"Скилл обновлён: {name}, поля: {list(kwargs.keys())}")
        return skill

    def delete_skill(self, name: str) -> bool:
        """Мягкое удаление скилла.

        Raises:
            ValueError: Если скилл не найден.
        """
        ok = self._store.delete(name)
        if not ok:
            raise ValueError(f"Скилл не найден: {name}")
        logger.info(f"Скилл удалён: {name}")
        return True

    def export_skill(self, name: str) -> Optional[dict]:
        """Экспорт скилла в словарь."""
        return self._store.export_skill(name)

    def get_skill_names(self) -> list[str]:
        """Список имён всех активных скиллов."""
        return [s.name for s in self.list_skills()]
