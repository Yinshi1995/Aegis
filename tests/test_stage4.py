"""
Тесты Stage 4 — Инструменты (tools).
Тестирует: file_manager, script_runner, plugin_loader, whatsapp, web_scraper (частично).
Браузер (Playwright) — опциональный тест, пропускается если не установлен.
"""
import asyncio
import sys
import os

# Убедимся что корень проекта в PATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_registration():
    """Все инструменты регистрируются корректно."""
    print("\n=== ТЕСТ: Регистрация инструментов ===")
    from app.tools import register_all_tools, registry
    register_all_tools()

    expected = {"browser", "web_scraper", "file_manager", "whatsapp", "script_runner", "example"}
    actual = set(registry.names)

    print(f"  Ожидаемые : {sorted(expected)}")
    print(f"  Реальные  : {sorted(actual)}")

    assert expected.issubset(actual), f"Отсутствуют: {expected - actual}"
    print(f"  ✓ Все {len(expected)} инструментов зарегистрированы")

    # Проверяем что описания не пустые
    desc = registry.list_descriptions()
    assert len(desc) > 100, "Описания слишком короткие"
    print(f"  ✓ Описания сгенерированы ({len(desc)} символов)")


def test_file_manager():
    """FileManagerTool: list, write, read, info + запрет выхода за границы."""
    print("\n=== ТЕСТ: FileManagerTool ===")
    from app.tools.file_manager import FileManagerTool
    fm = FileManagerTool()

    async def run():
        # list scripts/
        r = await fm.execute(action="list", path="scripts")
        assert r.success, f"list failed: {r.error}"
        print(f"  ✓ list scripts/: {len(r.data)} файлов")

        # write
        r = await fm.execute(action="write", path="data/test_write.txt", content="Тестовая запись 🚀")
        assert r.success, f"write failed: {r.error}"
        print(f"  ✓ write data/test_write.txt: {r.data['size']} байт")

        # read
        r = await fm.execute(action="read", path="data/test_write.txt")
        assert r.success, f"read failed: {r.error}"
        assert "Тестовая запись" in r.data
        print(f"  ✓ read: '{r.data}'")

        # info
        r = await fm.execute(action="info", path="data/test_write.txt")
        assert r.success, f"info failed: {r.error}"
        assert r.data["type"] == "file"
        print(f"  ✓ info: size={r.data['size']}")

        # Безопасность: path traversal
        r = await fm.execute(action="read", path="../../../etc/passwd")
        assert not r.success, "Должен был отклонить path traversal!"
        assert "Доступ запрещён" in r.error
        print(f"  ✓ path traversal заблокирован: {r.error}")

        # Безопасность: выход за разрешённые корни
        r = await fm.execute(action="read", path="app/config.py")
        assert not r.success, "Должен был отклонить доступ к app/"
        print(f"  ✓ доступ к app/ заблокирован: {r.error}")

        # Очистка
        from pathlib import Path
        Path("data/test_write.txt").unlink(missing_ok=True)
        print("  ✓ Очистка завершена")

    asyncio.run(run())


def test_script_runner():
    """ScriptRunnerTool: list, run с аргументами, таймаут-защита."""
    print("\n=== ТЕСТ: ScriptRunnerTool ===")
    from app.tools.script_runner import ScriptRunnerTool
    sr = ScriptRunnerTool()

    async def run():
        # list
        r = await sr.execute(action="list")
        assert r.success, f"list failed: {r.error}"
        names = [s["name"] for s in r.data]
        assert "example_script.py" in names
        print(f"  ✓ list: {names}")

        # run hello
        r = await sr.execute(action="run", script="example_script.py", args={"action": "hello", "name": "Агент"})
        assert r.success, f"run hello failed: {r.error}"
        assert "Привет, Агент!" in r.data["stdout"]
        print(f"  ✓ run hello: {r.data['stdout']}")

        # run sum
        r = await sr.execute(action="run", script="example_script.py", args={"action": "sum", "numbers": [1, 2, 3, 4, 5]})
        assert r.success, f"run sum failed: {r.error}"
        assert '"result": 15' in r.data["stdout"]
        print(f"  ✓ run sum: {r.data['stdout']}")

        # run info
        r = await sr.execute(action="run", script="example_script.py", args={"action": "info"})
        assert r.success, f"run info failed: {r.error}"
        assert "python" in r.data["stdout"].lower()
        print(f"  ✓ run info: OK")

        # Безопасность: path traversal
        r = await sr.execute(action="run", script="../app/config.py")
        assert not r.success, "Должен был отклонить path traversal!"
        print(f"  ✓ path traversal заблокирован: {r.error}")

        # Ошибка скрипта (неизвестное действие)
        r = await sr.execute(action="run", script="example_script.py", args={"action": "bad"})
        assert not r.success, "Скрипт должен был завершиться с ошибкой"
        assert r.data["returncode"] != 0
        print(f"  ✓ ошибка скрипта: returncode={r.data['returncode']}")

    asyncio.run(run())


def test_plugin_loader():
    """Plugin loader: обнаружение и загрузка плагинов."""
    print("\n=== ТЕСТ: Plugin Loader ===")
    from app.tools.plugin_loader import discover_plugins, load_plugins
    from app.tools.base import BaseTool, ToolRegistry

    # discover
    plugins = discover_plugins()
    plugin_names = [p.name for p in plugins]
    assert "example" in plugin_names, f"example не найден в {plugin_names}"
    print(f"  ✓ discover: найдено {len(plugins)} плагинов — {plugin_names}")

    # load в чистый реестр
    test_registry = ToolRegistry()
    count = load_plugins(test_registry)
    assert count >= 1, f"Загружено {count} плагинов, ожидалось >=1"
    assert "example" in test_registry.names
    print(f"  ✓ load: {count} плагинов в реестре — {test_registry.names}")

    # Проверяем что example работает
    example = test_registry.get("example")
    assert example is not None

    async def test_example():
        r = await example.execute(action="echo", text="привет")
        assert r.success and r.data == "привет"

        r = await example.execute(action="reverse", text="hello")
        assert r.success and r.data == "olleh"
        print(f"  ✓ example plugin: echo + reverse работают")

    asyncio.run(test_example())


def test_whatsapp_stub():
    """WhatsApp заглушка: status возвращает stub."""
    print("\n=== ТЕСТ: WhatsApp (заглушка) ===")
    from app.tools.whatsapp import WhatsAppTool
    wa = WhatsAppTool()

    async def run():
        r = await wa.execute(action="status")
        assert r.success
        assert r.data["status"] == "stub"
        print(f"  ✓ status: {r.data}")

        r = await wa.execute(action="send", phone="+1234567890", message="test")
        assert not r.success
        assert "не реализована" in r.error
        print(f"  ✓ send заблокирован: {r.error}")

    asyncio.run(run())


def test_safe_execute_timeout():
    """BaseTool.safe_execute: таймаут работает."""
    print("\n=== ТЕСТ: safe_execute таймаут ===")
    from app.tools.base import BaseTool, ToolResult

    class SlowTool(BaseTool):
        name = "slow"
        description = "Медленный инструмент для теста"

        async def execute(self, **params) -> ToolResult:
            await asyncio.sleep(10)
            return ToolResult(success=True, data="done")

    slow = SlowTool()

    async def run():
        r = await slow.safe_execute(timeout=1)
        assert not r.success
        assert "Таймаут" in r.error
        print(f"  ✓ Таймаут сработал: {r.error}")

    asyncio.run(run())


if __name__ == "__main__":
    print("=" * 60)
    print("  ТЕСТЫ STAGE 4 — ИНСТРУМЕНТЫ")
    print("=" * 60)

    tests = [
        test_registration,
        test_file_manager,
        test_script_runner,
        test_plugin_loader,
        test_whatsapp_stub,
        test_safe_execute_timeout,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"  ✗ ОШИБКА: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print(f"  РЕЗУЛЬТАТ: {passed}/{len(tests)} тестов прошло")
    if failed:
        print(f"  ✗ {failed} тестов провалилось")
    else:
        print("  ✓ ВСЕ ТЕСТЫ ПРОЙДЕНЫ")
    print("=" * 60)
