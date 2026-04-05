"""
Тесты Stage 5 — Оркестратор (Agent).
Тестирует: классификацию намерений, маршрутизацию RAG/SKILL/TOOL/CHAT,
антигаллюцинации, историю чата.
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def setup_test_file():
    """Создаём файл для теста file_manager tool."""
    from pathlib import Path
    Path("data").mkdir(exist_ok=True)
    Path("data/test_write.txt").write_text("Привіт з тестового файлу!", encoding="utf-8")


def test_rag():
    """RAG: вопрос по базе знаний → intent=RAG, есть источники, 510 к.с."""
    print("\n=== ТЕСТ: RAG — питання по базі знань ===")
    from app.agent import Agent
    agent = Agent()

    async def run():
        resp = await agent.process_message("Яка потужність двигуна БМП К-17?")
        print(f"  intent: {resp.intent}")
        print(f"  answer: {resp.text[:200]}")
        print(f"  sources: {resp.sources[:2]}")
        print(f"  time: {resp.execution_time}с")

        assert resp.intent == "RAG", f"Ожидали RAG, получили {resp.intent}"
        print("  ✓ intent = RAG")

        assert resp.sources, "Должны быть источники"
        print(f"  ✓ sources: {len(resp.sources)} шт")

        assert "510" in resp.text, f"Ответ должен содержать '510': {resp.text[:200]}"
        print("  ✓ содержит '510'")

        agent.clear_history()

    asyncio.run(run())


def test_chat():
    """CHAT: приветствие → intent=CHAT, адекватный ответ."""
    print("\n=== ТЕСТ: CHAT — привітання ===")
    from app.agent import Agent
    agent = Agent()

    async def run():
        resp = await agent.process_message("Привіт, як справи?")
        print(f"  intent: {resp.intent}")
        print(f"  answer: {resp.text[:200]}")
        print(f"  time: {resp.execution_time}с")

        assert resp.intent == "CHAT", f"Ожидали CHAT, получили {resp.intent}"
        print("  ✓ intent = CHAT")

        assert len(resp.text) > 5, "Ответ слишком короткий"
        assert "[Ошибка" not in resp.text, f"Ошибка в ответе: {resp.text}"
        print("  ✓ адекватный ответ")

        agent.clear_history()

    asyncio.run(run())


def test_skill():
    """SKILL: перевод → intent=SKILL, skill_used=translate."""
    print("\n=== ТЕСТ: SKILL — переклад ===")
    from app.agent import Agent
    agent = Agent()

    async def run():
        resp = await agent.process_message("Переведи на английский: Бойова машина піхоти")
        print(f"  intent: {resp.intent}")
        print(f"  skill_used: {resp.skill_used}")
        print(f"  answer: {resp.text[:200]}")
        print(f"  time: {resp.execution_time}с")

        assert resp.intent == "SKILL", f"Ожидали SKILL, получили {resp.intent}"
        print("  ✓ intent = SKILL")

        assert resp.skill_used == "translate", f"Ожидали translate, получили {resp.skill_used}"
        print("  ✓ skill_used = translate")

        # Проверяем наличие английского перевода
        text_lower = resp.text.lower()
        has_translation = any(w in text_lower for w in ["infantry", "fighting", "combat", "vehicle", "armored"])
        assert has_translation, f"Нет перевода в ответе: {resp.text[:200]}"
        print("  ✓ содержит перевод")

        agent.clear_history()

    asyncio.run(run())


def test_tool():
    """TOOL: прочитать файл → intent=TOOL, tool_used=file_manager."""
    print("\n=== ТЕСТ: TOOL — читання файлу ===")
    setup_test_file()

    from app.agent import Agent
    agent = Agent()

    async def run():
        resp = await agent.process_message("Прочитай файл data/test_write.txt")
        print(f"  intent: {resp.intent}")
        print(f"  tool_used: {resp.tool_used}")
        print(f"  answer: {resp.text[:200]}")
        print(f"  time: {resp.execution_time}с")

        assert resp.intent == "TOOL", f"Ожидали TOOL, получили {resp.intent}"
        print("  ✓ intent = TOOL")

        assert resp.tool_used == "file_manager", f"Ожидали file_manager, получили {resp.tool_used}"
        print("  ✓ tool_used = file_manager")

        assert "Привіт" in resp.text, f"Нет содержимого файла в ответе: {resp.text[:200]}"
        print("  ✓ содержит данные из файла")

        agent.clear_history()

    asyncio.run(run())


def test_anti_hallucination():
    """Антигаллюцинация: вопрос не из базы → НЕ выдумывает факты."""
    print("\n=== ТЕСТ: Антигаллюцинація ===")
    from app.agent import Agent
    agent = Agent()

    async def run():
        resp = await agent.process_message("Який рецепт борщу є в базі знань?")
        print(f"  intent: {resp.intent}")
        print(f"  answer: {resp.text[:300]}")
        print(f"  time: {resp.execution_time}с")

        # Должен либо сказать что нет информации, либо не выдавать рецепт
        text_lower = resp.text.lower()
        # Ожидаем: "нет информации" / "не знайдено" / "немає" / не должно быть рецепта с ингредиентами
        has_disclaimer = any(w in text_lower for w in [
            "нет информации", "немає інформації", "не знайдено",
            "нет в базе", "не містить", "відсутня",
            "не найден", "не є в базі", "не знаходиться",
        ])
        has_recipe = all(w in text_lower for w in ["свёкла", "картофель", "капуста"])

        if has_recipe and not has_disclaimer:
            print("  ✗ ГАЛЛЮЦИНАЦИЯ: выдал рецепт борща как из базы знаний!")
            assert False, "Галлюцинация — агент выдумал рецепт борща из базы знаний"
        else:
            print("  ✓ не галлюцинирует (нет рецепта из базы или есть disclaimer)")

        agent.clear_history()

    asyncio.run(run())


def test_history():
    """История: два последовательных сообщения, агент помнит контекст."""
    print("\n=== ТЕСТ: Історія чату ===")
    from app.agent import Agent
    agent = Agent()

    async def run():
        # Первое сообщение — представляемся
        resp1 = await agent.process_message("Мене звати Олександр")
        print(f"  msg1 answer: {resp1.text[:150]}")

        # Второе — спрашиваем имя
        resp2 = await agent.process_message("Як мене звати?")
        print(f"  msg2 answer: {resp2.text[:150]}")

        # Проверяем историю
        history = agent.get_history()
        assert len(history) >= 4, f"В истории должно быть >= 4 записей, есть {len(history)}"
        print(f"  ✓ история: {len(history)} записей")

        # Агент должен помнить имя
        assert "Олександр" in resp2.text or "олександр" in resp2.text.lower(), \
            f"Агент не помнит имя: {resp2.text[:200]}"
        print("  ✓ агент помнит имя 'Олександр'")

        # Проверяем clear
        agent.clear_history()
        assert len(agent.get_history()) == 0
        print("  ✓ clear_history() работает")

    asyncio.run(run())


if __name__ == "__main__":
    print("=" * 60)
    print("  ТЕСТЫ STAGE 5 — ОРКЕСТРАТОР (Agent)")
    print("=" * 60)

    tests = [
        test_rag,
        test_chat,
        test_skill,
        test_tool,
        test_anti_hallucination,
        test_history,
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
