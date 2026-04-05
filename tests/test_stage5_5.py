"""
Тесты Stage 5.5 — Планировщик задач (scheduler).
Тестирует: CRUD задач, парсинг расписаний, выполнение по таймеру, enable/disable, историю.
"""
import asyncio
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Тестовая БД (не трогаем основную)
TEST_DB = "./data/test_scheduler.db"


def cleanup_db():
    """Удалить тестовую БД (если не заблокирована)."""
    from pathlib import Path
    try:
        Path(TEST_DB).unlink(missing_ok=True)
    except PermissionError:
        pass


def test_crud():
    """CRUD: создание, чтение, обновление, удаление задач."""
    print("\n=== ТЕСТ: CRUD задач ===")
    cleanup_db()
    from app.scheduler.manager import TaskManager

    tm = TaskManager(db_path=TEST_DB)

    # Пресеты создаются автоматически
    tasks = tm.list_tasks()
    assert len(tasks) >= 2, f"Должно быть >=2 пресетов, есть {len(tasks)}"
    names = [t.name for t in tasks]
    assert "daily_report" in names
    assert "check_site" in names
    print(f"  ✓ пресеты: {names}")

    # Создание
    t = tm.create_task(
        name="test_task",
        schedule_type="interval",
        schedule_value="10m",
        action_type="script",
        action_config={"script": "example_script.py", "args": {"action": "hello"}},
        description="Тестовая задача",
    )
    assert t.name == "test_task"
    assert t.run_count == 0
    print(f"  ✓ create: {t}")

    # Чтение
    fetched = tm.get_task("test_task")
    assert fetched is not None
    assert fetched.schedule_value == "10m"
    cfg = fetched.get_action_config()
    assert cfg["script"] == "example_script.py"
    print(f"  ✓ get: config={cfg}")

    # Обновление
    tm.update_task("test_task", description="Обновлённая", schedule_value="30m")
    updated = tm.get_task("test_task")
    assert updated.description == "Обновлённая"
    assert updated.schedule_value == "30m"
    print(f"  ✓ update: desc='{updated.description}', schedule='{updated.schedule_value}'")

    # Enable/Disable
    tm.disable_task("test_task")
    disabled = tm.get_task("test_task")
    assert not disabled.is_active
    print(f"  ✓ disable: is_active={disabled.is_active}")

    tm.enable_task("test_task")
    enabled = tm.get_task("test_task")
    assert enabled.is_active
    print(f"  ✓ enable: is_active={enabled.is_active}")

    # Удаление
    ok = tm.delete_task("test_task")
    assert ok
    assert tm.get_task("test_task") is None
    print(f"  ✓ delete: OK")

    # Дубликат
    try:
        tm.create_task(
            name="daily_report",
            schedule_type="interval",
            schedule_value="1h",
            action_type="message",
            action_config={"message": "test"},
        )
        assert False, "Должна быть ошибка дубликата"
    except ValueError as e:
        print(f"  ✓ дубликат отклонён: {e}")

    tm.dispose()


def test_parse_schedule():
    """Парсинг расписаний: interval, cron, once."""
    print("\n=== ТЕСТ: Парсинг расписаний ===")
    from app.scheduler.runner import parse_interval, parse_schedule
    from app.scheduler.models import ScheduledTask
    from apscheduler.triggers.interval import IntervalTrigger
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.date import DateTrigger

    # Интервалы
    assert parse_interval("30s") == {"seconds": 30}
    assert parse_interval("5m") == {"minutes": 5}
    assert parse_interval("2h") == {"hours": 2}
    assert parse_interval("1d") == {"days": 1}
    print("  ✓ interval: 30s, 5m, 2h, 1d")

    # Невалидный интервал
    try:
        parse_interval("abc")
        assert False, "Должна быть ошибка"
    except ValueError:
        print("  ✓ невалидный интервал отклонён")

    # Cron через mock-задачу
    task = ScheduledTask(
        name="t", schedule_type="cron", schedule_value="0 9 * * MON-FRI",
        action_type="skill", action_config="{}",
    )
    trigger = parse_schedule(task)
    assert isinstance(trigger, CronTrigger)
    print("  ✓ cron: 0 9 * * MON-FRI → CronTrigger")

    # Once
    task2 = ScheduledTask(
        name="t2", schedule_type="once", schedule_value="2026-12-31 23:59",
        action_type="message", action_config="{}",
    )
    trigger2 = parse_schedule(task2)
    assert isinstance(trigger2, DateTrigger)
    print("  ✓ once: 2026-12-31 23:59 → DateTrigger")

    # Interval через parse_schedule
    task3 = ScheduledTask(
        name="t3", schedule_type="interval", schedule_value="5s",
        action_type="script", action_config="{}",
    )
    trigger3 = parse_schedule(task3)
    assert isinstance(trigger3, IntervalTrigger)
    print("  ✓ interval: 5s → IntervalTrigger")


def test_runner_execution():
    """Runner: запуск задачи по интервалу, проверка run_count."""
    print("\n=== ТЕСТ: Выполнение задач по расписанию ===")
    cleanup_db()
    from app.scheduler.manager import TaskManager
    from app.scheduler.runner import SchedulerRunner

    tm = TaskManager(db_path=TEST_DB)

    # Отключаем пресеты (чтобы не запускались)
    tm.disable_task("daily_report")
    tm.disable_task("check_site")

    # Создаём быструю тестовую задачу: запуск скрипта каждые 5 секунд
    tm.create_task(
        name="fast_test",
        schedule_type="interval",
        schedule_value="5s",
        action_type="script",
        action_config={
            "script": "example_script.py",
            "args": {"action": "hello", "name": "Scheduler"},
        },
        description="Тест быстрого запуска",
    )

    runner = SchedulerRunner(task_manager=tm)
    runner.start()
    assert runner.is_running
    print("  ✓ scheduler запущен")

    # Ждём 12 секунд — должно сработать минимум 2 раза
    print("  ⏳ ждём 12 секунд...")
    time.sleep(12)

    runner.stop()
    assert not runner.is_running
    print("  ✓ scheduler остановлен")

    # Проверяем результаты
    task = tm.get_task("fast_test")
    print(f"  run_count: {task.run_count}")
    print(f"  last_result: {task.last_result[:100] if task.last_result else '(пусто)'}")
    print(f"  last_run: {task.last_run}")

    assert task.run_count >= 2, f"Ожидали >= 2 запусков, получили {task.run_count}"
    print(f"  ✓ run_count = {task.run_count} (>= 2)")

    assert task.last_result, "last_result не должен быть пустым"
    assert "Привет" in task.last_result or "stdout" in task.last_result
    print(f"  ✓ last_result: содержит результат")

    # Проверяем историю
    history = tm.get_history("fast_test")
    assert len(history) >= 2, f"Ожидали >= 2 записей в истории, есть {len(history)}"
    print(f"  ✓ история: {len(history)} записей")

    tm.dispose()


def test_enable_disable_stops_execution():
    """Disable останавливает запуск задачи."""
    print("\n=== ТЕСТ: Enable/Disable в runner ===")
    cleanup_db()
    from app.scheduler.manager import TaskManager
    from app.scheduler.runner import SchedulerRunner

    tm = TaskManager(db_path=TEST_DB)
    tm.disable_task("daily_report")
    tm.disable_task("check_site")

    # Создаём задачу, сразу неактивную
    tm.create_task(
        name="disabled_test",
        schedule_type="interval",
        schedule_value="2s",
        action_type="script",
        action_config={"script": "example_script.py", "args": {"action": "info"}},
        is_active=False,
    )

    runner = SchedulerRunner(task_manager=tm)
    runner.start()

    time.sleep(5)
    runner.stop()

    task = tm.get_task("disabled_test")
    assert task.run_count == 0, f"Неактивная задача не должна запускаться, но run_count={task.run_count}"
    print(f"  ✓ неактивная задача НЕ выполнялась (run_count=0)")

    tm.dispose()


def test_record_run_and_history():
    """record_run корректно обновляет задачу и пишет историю."""
    print("\n=== ТЕСТ: record_run + history ===")
    cleanup_db()
    from app.scheduler.manager import TaskManager

    tm = TaskManager(db_path=TEST_DB)

    tm.create_task(
        name="hist_test",
        schedule_type="interval",
        schedule_value="1h",
        action_type="message",
        action_config={"message": "test"},
    )

    # Имитируем 3 запуска
    tm.record_run("hist_test", success=True, result="Результат 1")
    tm.record_run("hist_test", success=True, result="Результат 2")
    tm.record_run("hist_test", success=False, error="Ошибка тест")

    task = tm.get_task("hist_test")
    assert task.run_count == 3
    print(f"  ✓ run_count = {task.run_count}")

    history = tm.get_history("hist_test", limit=10)
    assert len(history) == 3
    assert history[0].success is False  # Последний — ошибка (отсортирован DESC)
    assert "Ошибка тест" in history[0].error
    print(f"  ✓ история: 3 записи, последняя — ошибка")

    tm.dispose()


def test_on_error_disable():
    """on_error=disable отключает задачу при ошибке."""
    print("\n=== ТЕСТ: on_error=disable ===")
    cleanup_db()
    from app.scheduler.manager import TaskManager

    tm = TaskManager(db_path=TEST_DB)

    tm.create_task(
        name="fragile_task",
        schedule_type="interval",
        schedule_value="1h",
        action_type="tool",
        action_config={"tool": "nonexistent"},
        on_error="disable",
    )

    # Имитируем ошибку
    tm.record_run("fragile_task", success=False, error="Tool not found")

    task = tm.get_task("fragile_task")
    assert not task.is_active, "Задача должна быть отключена после ошибки"
    print(f"  ✓ задача отключена после ошибки (is_active={task.is_active})")

    tm.dispose()


if __name__ == "__main__":
    print("=" * 60)
    print("  ТЕСТЫ STAGE 5.5 — ПЛАНИРОВЩИК (Scheduler)")
    print("=" * 60)

    tests = [
        test_crud,
        test_parse_schedule,
        test_runner_execution,
        test_enable_disable_stops_execution,
        test_record_run_and_history,
        test_on_error_disable,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"  ✗ ПРОВАЛ: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print(f"  РЕЗУЛЬТАТ: {passed}/{len(tests)} тестов прошло")
    if failed:
        print(f"  ✗ {failed} тестов провалилось")
    else:
        print("  ✓ ВСЕ ТЕСТЫ ПРОЙДЕНЫ")
    print("=" * 60)

    # Финальная очистка
    cleanup_db()
