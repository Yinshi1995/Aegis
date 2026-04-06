"""
Gradio GUI — 5 вкладок: Чат, База знань, Скіли, Інструменти, Планувальник.
Мова інтерфейсу: українська.

ВАЖЛИВО: жодних callable value=, every=, .load(), .change() на компоненти що
оновлюють самі себе. Усі дані — лише по кнопці від користувача.
"""
import asyncio
import json
import logging
from pathlib import Path

import gradio as gr

from app.config import config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Глобальні посилання (встановлюються з main.py)
# ---------------------------------------------------------------------------

_agent = None
_scheduler_runner = None
_task_manager = None


def set_agent(agent):
    global _agent
    _agent = agent


def set_scheduler(runner, task_manager):
    global _scheduler_runner, _task_manager
    _scheduler_runner = runner
    _task_manager = task_manager


def _run_async(coro):
    """Запустити async-корутину в синхронному контексті Gradio."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result(timeout=120)
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

APP_CSS = """
.gradio-container { max-width: 1400px !important; }
footer { display: none !important; }

/* Метадані чату — компактний рядок */
.meta-line { font-size: 0.82em; color: #888; margin-top: 2px; }
.meta-line p { margin: 0; }

/* Таблиці — zebra */
table tbody tr:nth-child(even) { background: rgba(0,0,0,.03); }
.dark table tbody tr:nth-child(even) { background: rgba(255,255,255,.04); }

/* Картки-акордеони */
.gr-accordion { border-radius: 10px !important; }

/* Кнопки «Оновити» — компактні */
.refresh-btn { max-width: 160px; }
"""


# =========================================================================
# ДОПОМІЖНІ ФУНКЦІЇ (викликаються лише по кнопці)
# =========================================================================

def _check_ollama_status() -> str:
    try:
        from app.llm import get_llm_client
        client = get_llm_client()
        if client.is_available():
            models = client.list_models()
            backend = config.llm_backend
            return f"🟢 {backend} онлайн — {len(models)} моделей"
        return f"🔴 {config.llm_backend} недоступна"
    except Exception:
        return f"🔴 {config.llm_backend} недоступна"


def _refresh_models():
    """Повертає оновлений Dropdown з моделями."""
    try:
        from app.llm import get_llm_client
        client = get_llm_client()
        models = client.list_models()
        if not models:
            models = [client.model]
    except Exception:
        models = [config.ollama.model]
    current = models[0] if models else config.ollama.model
    if _agent and _agent.llm.model in models:
        current = _agent.llm.model
    status = _check_ollama_status()
    return gr.update(choices=models, value=current), status


def _get_indexed_docs() -> list[list]:
    try:
        from app.rag.vector_store import VectorStore
        store = VectorStore()
        all_data = store._collection.get(include=["metadatas"])
        metadatas = all_data.get("metadatas", [])
        docs = {}
        for m in metadatas:
            source = m.get("source", "невідомо")
            if source not in docs:
                docs[source] = {"name": source, "pages": set(), "chunks": 0, "ocr": False}
            docs[source]["chunks"] += 1
            page = m.get("page")
            if page is not None:
                docs[source]["pages"].add(page)
            if m.get("ocr"):
                docs[source]["ocr"] = True
        rows = []
        for d in docs.values():
            rows.append([d["name"], len(d["pages"]), d["chunks"], "OCR" if d["ocr"] else "Текст"])
        return rows if rows else [["(порожньо)", 0, 0, "-"]]
    except Exception as e:
        logger.error("Помилка отримання документів: %s", e)
        return [["(помилка)", 0, 0, str(e)[:50]]]


def _get_skills_table() -> list[list]:
    try:
        from app.skills.manager import Manager
        mgr = Manager()
        skills = mgr.list_skills()
        if not skills:
            return [["(немає)", "", "", ""]]
        return [[s.name, s.category, "✅" if s.requires_rag else "—", s.description[:60]] for s in skills]
    except Exception as e:
        return [["(помилка)", "", "", str(e)[:50]]]


def _get_tools_info() -> str:
    try:
        from app.tools import register_all_tools
        from app.tools.base import registry
        register_all_tools()
        if not registry.names:
            return "Немає зареєстрованих інструментів"
        lines = []
        for name in sorted(registry.names):
            tool = registry.get(name)
            desc = tool.description if tool else "—"
            lines.append(f"- **{name}** — {desc}")
        # Плагіни
        plugins_dir = Path("app/tools/plugins")
        if plugins_dir.exists():
            pfiles = [f for f in plugins_dir.glob("*.py") if f.name != "__init__.py"]
            if pfiles:
                lines.append("\n**Плагіни:** " + ", ".join(f.stem for f in pfiles))
        # Скрипти
        scripts_dir = Path("scripts")
        if scripts_dir.exists():
            sfiles = list(scripts_dir.glob("*.py"))
            if sfiles:
                lines.append("**Скрипти:** " + ", ".join(f.name for f in sfiles))
        return "\n".join(lines)
    except Exception as e:
        return f"Помилка: {e}"


def _get_tasks_table() -> list[list]:
    try:
        tm = _task_manager
        if not tm:
            from app.scheduler.manager import TaskManager
            tm = TaskManager()
        tasks = tm.list_tasks()
        if not tasks:
            return [["(немає)", "", "", "", "", ""]]
        rows = []
        for t in tasks:
            rows.append([
                t.name,
                f"{t.schedule_type}: {t.schedule_value}",
                t.action_type,
                "✅" if t.is_active else "❌",
                str(t.last_run)[:19] if t.last_run else "—",
                t.run_count or 0,
            ])
        return rows
    except Exception as e:
        return [["(помилка)", "", "", "", "", str(e)[:40]]]


# =========================================================================
# ВКЛАДКА 1 — ЧАТ
# =========================================================================

def _chat_respond(message: str, history: list[dict], model: str):
    if not message or not message.strip():
        yield history, "", ""
        return

    if not _agent:
        history.append(gr.ChatMessage(role="assistant", content="⚠️ Агент не ініціалізовано"))
        yield history, "", ""
        return

    # Змінити модель якщо обрана інша
    if model and model != _agent.llm.model:
        _agent.llm.model = model

    history.append(gr.ChatMessage(role="user", content=message))
    history.append(gr.ChatMessage(role="assistant", content="⏳ Думаю..."))
    yield history, "", ""

    try:
        response = _run_async(_agent.process_message(message))
        history.pop()
        history.append(gr.ChatMessage(role="assistant", content=response.text))

        parts = [response.intent]
        if response.sources:
            srcs = [f"{s.get('source','?')} стр.{s.get('page','?')}" for s in response.sources[:3]]
            parts.append("джерела: " + ", ".join(srcs))
        if response.skill_used:
            parts.append(f"скіл: {response.skill_used}")
        if response.tool_used:
            parts.append(f"інструмент: {response.tool_used}")
        parts.append(f"{response.execution_time}с")
        meta = " · ".join(parts)
        yield history, "", meta

    except Exception as e:
        history.pop()
        history.append(gr.ChatMessage(role="assistant", content=f"❌ Помилка: {e}"))
        yield history, "", str(e)


def _clear_chat():
    if _agent:
        _agent._history.clear()
    return [], "", ""


def _build_chat_tab():
    with gr.Row():
        with gr.Column(scale=5):
            chatbot = gr.Chatbot(
                height=600,
                placeholder="Напишіть повідомлення, щоб почати діалог…",
                layout="bubble",
            )
            # Метадані — компактний рядок
            meta_display = gr.Markdown(value="", elem_classes=["meta-line"])

            with gr.Row():
                msg_input = gr.Textbox(
                    placeholder="Введіть повідомлення…",
                    show_label=False,
                    scale=5,
                    lines=2,
                    max_lines=5,
                )
                send_btn = gr.Button("Надіслати", variant="primary", scale=1, min_width=120)

            with gr.Row():
                clear_btn = gr.Button("🗑️ Очистити", variant="secondary", size="sm")

        # Бічна панель — модель і статус
        with gr.Column(scale=1, min_width=200):
            ollama_status = gr.Textbox(value="натисніть 🔄", label="Ollama", interactive=False)
            model_dropdown = gr.Dropdown(
                choices=[config.ollama.model],
                value=config.ollama.model,
                label="Модель",
                interactive=True,
            )
            refresh_btn = gr.Button("🔄 Оновити", size="sm", elem_classes=["refresh-btn"])

    # Обробники — лише по кнопці / Enter
    send_btn.click(
        fn=_chat_respond,
        inputs=[msg_input, chatbot, model_dropdown],
        outputs=[chatbot, msg_input, meta_display],
    )
    msg_input.submit(
        fn=_chat_respond,
        inputs=[msg_input, chatbot, model_dropdown],
        outputs=[chatbot, msg_input, meta_display],
    )
    clear_btn.click(fn=_clear_chat, outputs=[chatbot, msg_input, meta_display])
    refresh_btn.click(fn=_refresh_models, outputs=[model_dropdown, ollama_status])


# =========================================================================
# ВКЛАДКА 2 — БАЗА ЗНАНЬ
# =========================================================================

def _index_pdf(file, progress=gr.Progress()):
    if file is None:
        return "⚠️ Оберіть PDF файл", _get_indexed_docs()
    try:
        from app.rag.retriever import Retriever
        retriever = Retriever()
        progress(0.1, desc="Завантаження PDF…")
        pdf_path = Path(file.name if hasattr(file, "name") else file)
        progress(0.3, desc="Парсинг та розбивка…")
        count = retriever.index_pdf(pdf_path)
        progress(1.0, desc="Готово!")
        return f"✅ Проіндексовано: {count} чанків з {pdf_path.name}", _get_indexed_docs()
    except Exception as e:
        return f"❌ {e}", _get_indexed_docs()


def _reindex_all(progress=gr.Progress()):
    try:
        from app.rag.retriever import Retriever
        retriever = Retriever()
        progress(0.2, desc="Очищення…")
        progress(0.5, desc="Індексація…")
        count = retriever.reindex()
        progress(1.0, desc="Готово!")
        return f"✅ Переіндексовано: {count} чанків", _get_indexed_docs()
    except Exception as e:
        return f"❌ {e}", _get_indexed_docs()


def _delete_doc(doc_name: str):
    if not doc_name or not doc_name.strip():
        return "⚠️ Введіть ім'я документа", _get_indexed_docs()
    try:
        from app.rag.vector_store import VectorStore
        store = VectorStore()
        all_data = store._collection.get(include=["metadatas"])
        ids_to_delete = [
            all_data["ids"][i]
            for i, m in enumerate(all_data.get("metadatas", []))
            if m.get("source") == doc_name.strip()
        ]
        if ids_to_delete:
            store._collection.delete(ids=ids_to_delete)
            return f"✅ Видалено {len(ids_to_delete)} чанків «{doc_name}»", _get_indexed_docs()
        return f"⚠️ Документ «{doc_name}» не знайдено", _get_indexed_docs()
    except Exception as e:
        return f"❌ {e}", _get_indexed_docs()


def _build_knowledge_tab():
    refresh_kb_btn = gr.Button("🔄 Оновити таблицю", size="sm", elem_classes=["refresh-btn"])
    docs_table = gr.Dataframe(
        value=[["натисніть 🔄 Оновити", "", "", ""]],
        headers=["Документ", "Сторінок", "Чанків", "Метод"],
        interactive=False,
    )
    status_msg = gr.Textbox(label="Статус", interactive=False)

    with gr.Row():
        with gr.Column(scale=1):
            with gr.Accordion("📤 Завантажити PDF", open=True):
                pdf_upload = gr.File(label="PDF файл", file_types=[".pdf"], type="filepath")
                index_btn = gr.Button("📥 Індексувати", variant="primary")

        with gr.Column(scale=1):
            with gr.Accordion("⚙️ Керування", open=False):
                reindex_btn = gr.Button("🔄 Переіндексувати все", variant="secondary")
                del_name = gr.Textbox(label="Документ для видалення", placeholder="example.pdf")
                del_btn = gr.Button("🗑️ Видалити", variant="stop")

    # Обробники
    refresh_kb_btn.click(fn=_get_indexed_docs, outputs=[docs_table])
    index_btn.click(fn=_index_pdf, inputs=[pdf_upload], outputs=[status_msg, docs_table])
    reindex_btn.click(fn=_reindex_all, outputs=[status_msg, docs_table])
    del_btn.click(fn=_delete_doc, inputs=[del_name], outputs=[status_msg, docs_table])


# =========================================================================
# ВКЛАДКА 3 — СКІЛИ
# =========================================================================

def _create_skill(name, description, category, system_prompt, user_template, requires_rag):
    try:
        from app.skills.manager import Manager
        mgr = Manager()
        mgr.create_skill(
            name=name, description=description, category=category,
            system_prompt=system_prompt, user_template=user_template,
            requires_rag=requires_rag,
        )
        return f"✅ Скіл «{name}» створено", _get_skills_table()
    except Exception as e:
        return f"❌ {e}", _get_skills_table()


def _load_skill(name: str):
    if not name or not name.strip():
        return "", "", "", "", False
    try:
        from app.skills.manager import Manager
        mgr = Manager()
        s = mgr.get_skill(name.strip())
        if s:
            return s.description, s.category, s.system_prompt, s.user_template or "", s.requires_rag
    except Exception:
        pass
    return "", "", "", "", False


def _save_skill(name, description, category, system_prompt, user_template, requires_rag):
    try:
        from app.skills.manager import Manager
        mgr = Manager()
        mgr.update_skill(
            name=name.strip(), description=description, category=category,
            system_prompt=system_prompt, user_template=user_template,
            requires_rag=requires_rag,
        )
        return f"✅ Скіл «{name}» оновлено", _get_skills_table()
    except Exception as e:
        return f"❌ {e}", _get_skills_table()


def _delete_skill(name: str):
    try:
        from app.skills.manager import Manager
        mgr = Manager()
        mgr.delete_skill(name.strip())
        return f"✅ Скіл «{name}» видалено", _get_skills_table()
    except Exception as e:
        return f"❌ {e}", _get_skills_table()


def _execute_skill(name: str, params_text: str):
    try:
        from app.skills.manager import Manager
        from app.skills.executor import SkillExecutor
        mgr = Manager()
        skill = mgr.get_skill(name.strip())
        if not skill:
            return f"❌ Скіл «{name}» не знайдено"
        params = {}
        if params_text.strip():
            try:
                params = json.loads(params_text)
            except json.JSONDecodeError:
                params = {"text": params_text, "question": params_text, "topic": params_text}
        executor = SkillExecutor()
        result = executor.execute(skill, **params)
        if result.success:
            out = f"✅ **{result.skill_name}** ({result.elapsed_seconds}с)\n\n{result.answer}"
            if result.sources:
                src = ", ".join(f"{s.get('source','?')} стр.{s.get('page','?')}" for s in result.sources[:3])
                out += f"\n\n*Джерела: {src}*"
            return out
        return f"❌ {result.error}"
    except Exception as e:
        return f"❌ {e}"


def _build_skills_tab():
    with gr.Row():
        refresh_sk_btn = gr.Button("🔄 Оновити", size="sm", elem_classes=["refresh-btn"])

    skills_table = gr.Dataframe(
        value=[["натисніть 🔄", "", "", ""]],
        headers=["Ім'я", "Категорія", "RAG", "Опис"],
        interactive=False,
    )
    sk_status = gr.Textbox(label="Статус", interactive=False)

    with gr.Row():
        with gr.Column(scale=1):
            with gr.Accordion("➕ Створити / Редагувати", open=False):
                sk_name = gr.Textbox(label="Ім'я", placeholder="my_skill")
                sk_desc = gr.Textbox(label="Опис")
                sk_cat = gr.Dropdown(
                    choices=["rag", "generation", "automation", "analysis"],
                    value="generation", label="Категорія",
                )
                sk_sys = gr.TextArea(label="System Prompt", lines=4, placeholder="Ти — …")
                sk_tpl = gr.TextArea(label="User Template", lines=2, placeholder="{text}, {question}…")
                sk_rag = gr.Checkbox(label="Потрібен RAG", value=False)
                with gr.Row():
                    sk_load_btn = gr.Button("📂 Завантажити")
                    sk_create_btn = gr.Button("➕ Створити", variant="primary")
                    sk_save_btn = gr.Button("💾 Зберегти", variant="secondary")
                    sk_del_btn = gr.Button("🗑️ Видалити", variant="stop")

        with gr.Column(scale=1):
            with gr.Accordion("▶️ Запуск скіла", open=False):
                sk_exec_name = gr.Textbox(label="Ім'я скіла", placeholder="translate")
                sk_exec_params = gr.TextArea(label="Параметри (JSON / текст)", lines=3)
                sk_exec_btn = gr.Button("▶️ Виконати", variant="primary")
                sk_exec_result = gr.Markdown()

    # Обробники
    refresh_sk_btn.click(fn=_get_skills_table, outputs=[skills_table])
    sk_load_btn.click(fn=_load_skill, inputs=[sk_name], outputs=[sk_desc, sk_cat, sk_sys, sk_tpl, sk_rag])
    sk_create_btn.click(
        fn=_create_skill, inputs=[sk_name, sk_desc, sk_cat, sk_sys, sk_tpl, sk_rag],
        outputs=[sk_status, skills_table],
    )
    sk_save_btn.click(
        fn=_save_skill, inputs=[sk_name, sk_desc, sk_cat, sk_sys, sk_tpl, sk_rag],
        outputs=[sk_status, skills_table],
    )
    sk_del_btn.click(fn=_delete_skill, inputs=[sk_name], outputs=[sk_status, skills_table])
    sk_exec_btn.click(fn=_execute_skill, inputs=[sk_exec_name, sk_exec_params], outputs=[sk_exec_result])


# =========================================================================
# ВКЛАДКА 4 — ІНСТРУМЕНТИ
# =========================================================================

def _execute_tool(tool_name: str, params_json: str):
    if not tool_name or not tool_name.strip():
        return "⚠️ Введіть ім'я інструмента"
    try:
        from app.tools.base import registry
        tool = registry.get(tool_name.strip())
        if not tool:
            return f"❌ Інструмент «{tool_name}» не знайдено"
        params = json.loads(params_json) if params_json.strip() else {}
        result = _run_async(tool.safe_execute(**params))
        if result.success:
            data_str = json.dumps(result.data, ensure_ascii=False, indent=2) if isinstance(result.data, (dict, list)) else str(result.data)
            return f"✅ **{tool_name}**\n```\n{data_str[:3000]}\n```"
        return f"❌ {result.error}"
    except json.JSONDecodeError:
        return "❌ Невалідний JSON"
    except Exception as e:
        return f"❌ {e}"


def _build_tools_tab():
    refresh_tools_btn = gr.Button("🔄 Оновити", size="sm", elem_classes=["refresh-btn"])
    tools_md = gr.Markdown(value="*Натисніть 🔄 щоб завантажити список*")

    with gr.Accordion("▶️ Ручний тест", open=False):
        tool_name_input = gr.Textbox(label="Інструмент", placeholder="web_scraper")
        tool_params_input = gr.TextArea(
            label="Параметри (JSON)", lines=4,
            placeholder='{"action": "extract_text", "url": "https://example.com"}',
        )
        tool_exec_btn = gr.Button("▶️ Виконати", variant="primary")
        tool_result = gr.Markdown()

    refresh_tools_btn.click(fn=_get_tools_info, outputs=[tools_md])
    tool_exec_btn.click(fn=_execute_tool, inputs=[tool_name_input, tool_params_input], outputs=[tool_result])


# =========================================================================
# ВКЛАДКА 5 — ПЛАНУВАЛЬНИК
# =========================================================================

def _create_task(name, description, schedule_type, schedule_value, action_type, action_config_json, on_error):
    try:
        tm = _task_manager
        if not tm:
            from app.scheduler.manager import TaskManager
            tm = TaskManager()
        action_config = json.loads(action_config_json) if action_config_json.strip() else {}
        tm.create_task(
            name=name.strip(), description=description,
            schedule_type=schedule_type, schedule_value=schedule_value.strip(),
            action_type=action_type, action_config=action_config, on_error=on_error,
        )
        if _scheduler_runner and _scheduler_runner.is_running:
            _scheduler_runner.reload()
        return f"✅ Задачу «{name}» створено", _get_tasks_table()
    except Exception as e:
        return f"❌ {e}", _get_tasks_table()


def _toggle_task(name: str):
    try:
        tm = _task_manager
        if not tm:
            from app.scheduler.manager import TaskManager
            tm = TaskManager()
        task = tm.get_task(name.strip())
        if not task:
            return f"❌ Задачу «{name}» не знайдено", _get_tasks_table()
        if task.is_active:
            tm.disable_task(name.strip())
            msg = f"⏸️ «{name}» вимкнено"
        else:
            tm.enable_task(name.strip())
            msg = f"▶️ «{name}» увімкнено"
        if _scheduler_runner and _scheduler_runner.is_running:
            _scheduler_runner.reload()
        return msg, _get_tasks_table()
    except Exception as e:
        return f"❌ {e}", _get_tasks_table()


def _delete_task(name: str):
    try:
        tm = _task_manager
        if not tm:
            from app.scheduler.manager import TaskManager
            tm = TaskManager()
        tm.delete_task(name.strip())
        if _scheduler_runner and _scheduler_runner.is_running:
            _scheduler_runner.reload()
        return f"✅ Задачу «{name}» видалено", _get_tasks_table()
    except Exception as e:
        return f"❌ {e}", _get_tasks_table()


def _get_task_history(name: str) -> str:
    try:
        tm = _task_manager
        if not tm:
            from app.scheduler.manager import TaskManager
            tm = TaskManager()
        history = tm.get_history(name.strip(), limit=10)
        if not history:
            return "Немає записів"
        lines = []
        for h in history:
            icon = "✅" if h.success else "❌"
            when = str(h.started_at)[:19] if h.started_at else "?"
            txt = h.result[:80] if h.result else (h.error[:80] if h.error else "—")
            lines.append(f"{icon} {when} — {txt}")
        return "\n\n".join(lines)
    except Exception as e:
        return f"Помилка: {e}"


def _start_scheduler():
    if not _scheduler_runner:
        return "⚠️ Планувальник не ініціалізовано"
    try:
        if _scheduler_runner.is_running:
            return "ℹ️ Вже працює"
        _scheduler_runner.start()
        return "✅ Планувальник запущено"
    except Exception as e:
        return f"❌ {e}"


def _stop_scheduler():
    if not _scheduler_runner:
        return "⚠️ Планувальник не ініціалізовано"
    try:
        _scheduler_runner.stop()
        return "⏹️ Зупинено"
    except Exception as e:
        return f"❌ {e}"


def _build_scheduler_tab():
    with gr.Row():
        refresh_t_btn = gr.Button("🔄 Оновити", size="sm", elem_classes=["refresh-btn"])
        t_start_btn = gr.Button("▶️ Запустити планувальник", variant="primary", size="sm")
        t_stop_btn = gr.Button("⏹️ Зупинити", variant="stop", size="sm")

    tasks_table = gr.Dataframe(
        value=[["натисніть 🔄", "", "", "", "", ""]],
        headers=["Ім'я", "Розклад", "Дія", "Активна", "Останній запуск", "Запусків"],
        interactive=False,
    )
    t_status = gr.Textbox(label="Статус", interactive=False)

    with gr.Row():
        with gr.Column(scale=1):
            with gr.Accordion("➕ Нова задача", open=False):
                t_name = gr.Textbox(label="Ім'я", placeholder="my_task")
                t_desc = gr.Textbox(label="Опис")
                t_stype = gr.Dropdown(choices=["interval", "cron", "once"], value="interval", label="Тип розкладу")
                t_svalue = gr.Textbox(label="Значення", placeholder="30m / 0 9 * * * / 2026-12-31 14:00")
                t_atype = gr.Dropdown(choices=["skill", "tool", "script", "message"], value="skill", label="Тип дії")
                t_aconfig = gr.TextArea(label="Конфігурація (JSON)", lines=3,
                                         placeholder='{"skill": "analyze_document", "params": {"topic": "..."}}')
                t_onerror = gr.Dropdown(choices=["ignore", "retry", "disable"], value="ignore", label="При помилці")
                t_create_btn = gr.Button("➕ Створити", variant="primary")

        with gr.Column(scale=1):
            with gr.Accordion("⚙️ Керування задачею", open=False):
                t_task_name = gr.Textbox(label="Ім'я задачі", placeholder="daily_report")
                with gr.Row():
                    t_toggle_btn = gr.Button("⏯️ Увімк/Вимк", variant="secondary")
                    t_del_btn_sch = gr.Button("🗑️ Видалити", variant="stop")

            with gr.Accordion("📋 Лог запусків", open=False):
                t_hist_name = gr.Textbox(label="Ім'я задачі", placeholder="daily_report")
                t_hist_btn = gr.Button("📋 Показати лог", variant="secondary")
                t_hist_output = gr.Markdown()

    # Обробники
    refresh_t_btn.click(fn=_get_tasks_table, outputs=[tasks_table])
    t_create_btn.click(
        fn=_create_task,
        inputs=[t_name, t_desc, t_stype, t_svalue, t_atype, t_aconfig, t_onerror],
        outputs=[t_status, tasks_table],
    )
    t_toggle_btn.click(fn=_toggle_task, inputs=[t_task_name], outputs=[t_status, tasks_table])
    t_del_btn_sch.click(fn=_delete_task, inputs=[t_task_name], outputs=[t_status, tasks_table])
    t_start_btn.click(fn=_start_scheduler, outputs=[t_status])
    t_stop_btn.click(fn=_stop_scheduler, outputs=[t_status])
    t_hist_btn.click(fn=_get_task_history, inputs=[t_hist_name], outputs=[t_hist_output])


# =========================================================================
# ГОЛОВНА ФУНКЦІЯ
# =========================================================================

def create_interface() -> gr.Blocks:
    """Створити Gradio інтерфейс — 5 вкладок, без auto-load."""
    # Визначаємо бекенд та модель для заголовка
    backend = config.llm_backend
    if backend == "llamacpp":
        model_label = Path(config.llamacpp.model_path).stem
    else:
        model_label = config.ollama.model

    with gr.Blocks(title="🤖 AI Агент") as demo:
        gr.Markdown(
            f"# ⬡ Aegis · LLM: {backend} ({model_label})\n"
            f"RAG · Скіли · Інструменти · Планувальник"
        )

        with gr.Tabs():
            with gr.Tab("💬 Чат"):
                _build_chat_tab()
            with gr.Tab("📚 База знань"):
                _build_knowledge_tab()
            with gr.Tab("🧠 Скіли"):
                _build_skills_tab()
            with gr.Tab("🔧 Інструменти"):
                _build_tools_tab()
            with gr.Tab("⏰ Планувальник"):
                _build_scheduler_tab()

    return demo
