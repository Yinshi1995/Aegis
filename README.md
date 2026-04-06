<div align="center">

<br>

<img src="https://img.shields.io/badge/⬡-AEGIS-0F172A?style=for-the-badge&labelColor=0F172A&color=1E3A5F" alt="Aegis" height="40"/>

# A E G I S

**Autonomous Expert & Ground Intelligence System**

*Локальний AI-агент з RAG · Система скілів · Автоматизація середовища*

<br>

[![Python](https://img.shields.io/badge/Python-3.11+-0D1117?style=flat-square&logo=python&logoColor=3776AB)](https://python.org)
[![Ollama](https://img.shields.io/badge/Ollama-Local_LLM-0D1117?style=flat-square&logo=ollama&logoColor=white)](https://ollama.com)
[![Gradio](https://img.shields.io/badge/Gradio-GUI-0D1117?style=flat-square&logo=gradio&logoColor=F97316)](https://gradio.app)
[![ChromaDB](https://img.shields.io/badge/Chroma-Vector_DB-0D1117?style=flat-square&logoColor=4A154B)](https://trychroma.com)
![Offline](https://img.shields.io/badge/100%25_OFFLINE-22C55E?style=flat-square)

<br>

```
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   📡 RAG + OCR   🧠 Skills   🔧 Tools   🔌 Plugins   ⏰ Cron  ║
║  ──────────────────────────────────────────────────────────  ║
║                   ⬡ AEGIS ORCHESTRATOR                       ║
║  ──────────────────────────────────────────────────────────  ║
║        Ollama  ·  ChromaDB  ·  SQLite  ·  Playwright         ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
```

<br>

[Можливості](#-можливості) · [Швидкий старт](#-швидкий-старт) · [Архітектура](#-архітектура) · [Модулі](#-модулі) · [FAQ](#-faq)

</div>

<br>

---

<br>

## Що це?

**Aegis** — повністю локальний AI-агент, який працює без хмарних API, без інтернету, без витоку даних.

Він аналізує ваші PDF-документи через RAG з OCR, виконує задачі за розкладом, керує браузером,
запускає скрипти і розширюється плагінами — все на вашому залізі.

**Ключова відмінність** — антигалюцинаційний RAG: подвійна перевірка кожної відповіді,
обов'язкове цитування джерел, чесне «в базі знань немає інформації» замість вигадок.

```
Питання:  Яка потужність двигуна БМП К-17?
Відповідь: Потужність двигуна БМП К-17 становить 510 к.с.
           [Джерело: ozbroennia.pdf, стр. 50]

Питання:  Який рецепт борщу?
Відповідь: В базі знань немає інформації про рецепт борщу.
```

<br>

---

<br>

## ✦ Можливості

<table>
<tr>
<td width="50%" valign="top">

### 📚 RAG з OCR
PDF → чанки → ембедінги → ChromaDB.
Зашифровані PDF з битим текстом — через Tesseract OCR.
Подвійна перевірка галюцинацій.

### 🧠 Скіли
Збережені промпти з `{параметрами}`.
4 вбудованих + необмежено кастомних.
Кожен скіл може використовувати RAG-контекст.

### ⏰ Планувальник
Автономне виконання задач: interval / cron / once.
Моніторинг сайтів, генерація звітів, будь-яка автоматизація.

</td>
<td width="50%" valign="top">

### 🔧 Інструменти
Браузер (Playwright), скрапер, файловий менеджер,
запуск скриптів, WhatsApp (заглушка).

### 🔌 Плагіни
Кинув `.py` у `plugins/` — інструмент з'явився.
Без зміни ядра, без перекомпіляції.

### 🖥️ GUI
Gradio-інтерфейс з 5 вкладками.
Чат, база знань, скіли, інструменти, планувальник.

</td>
</tr>
</table>

<br>

---

<br>

## 🚀 Швидкий старт

### Вимоги

| Компонент | Мінімум | Рекомендовано |
|-----------|---------|---------------|
| Python | 3.11+ | 3.12 |
| RAM | 6 GB | 16 GB |
| Ollama | встановлена | остання версія |
| Tesseract | — | для OCR сканованих PDF |

### Встановлення

```bash
# 1 — Клонування
git clone https://github.com/yourname/aegis.git
cd aegis

# 2 — Оточення
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # Windows
# source .venv/bin/activate            # Linux / Mac

# 3 — Залежності
pip install -r requirements.txt

# 4 — Моделі Ollama
ollama serve                           # в окремому терміналі
ollama pull qwen2.5:7b                 # чат (~4.7 GB)
ollama pull nomic-embed-text           # ембедінги (~274 MB)

# 5 — Конфігурація
cp .env.example .env                   # за потреби відредагуйте

# 6 — Запуск
python -m app.main
```

Відкрийте **http://localhost:7860**

<br>

---

<br>

## 🏗 Архітектура

```
                    ┌─────────────────────────────────┐
                    │          Gradio GUI              │
                    │  💬  📚  🧠  🔧  ⏰               │
                    └────────────┬────────────────────┘
                                 │
                    ┌────────────▼────────────────────┐
                    │     ⬡ Agent (Orchestrator)       │
                    │                                  │
                    │  user msg → intent classification │
                    │  RAG │ SKILL │ TOOL │ CHAT       │
                    └──┬───────┬───────┬───────┬──────┘
                       │       │       │       │
              ┌────────┘   ┌───┘   ┌───┘   ┌───┘
              ▼            ▼       ▼       ▼
         ┌─────────┐ ┌────────┐ ┌──────┐ ┌──────────┐
         │   RAG   │ │ Skills │ │ Tools│ │ Scheduler│
         │         │ │        │ │      │ │          │
         │ PDF/OCR │ │ SQLite │ │Playw.│ │APSched.  │
         │ Chroma  │ │ Prompts│ │Scrapr│ │ cron     │
         │ Embed   │ │ Script │ │Files │ │ interval │
         └─────────┘ └────────┘ └──────┘ └──────────┘
              │
         ┌────┴────┐
         │ Ollama  │
         │  LLM    │
         │ Embed   │
         └─────────┘
```

**Потік обробки запиту:**

```
User Message
  │
  ├─→ Intent Classification (LLM, одне слово: RAG / SKILL / TOOL / CHAT)
  │
  ├─→ RAG:   embed query → ChromaDB top-k → LLM + context → hallucination check → ✅
  ├─→ SKILL: find skill → format template → (optional RAG) → LLM → ✅
  ├─→ TOOL:  parse params → safe_execute(timeout=30s) → format result → ✅
  └─→ CHAT:  history + system prompt → LLM → ✅
  │
  └─→ AgentResponse { text, intent, sources, skill_used, tool_used, time }
```

<br>

---

<br>

## 📁 Структура проєкту

```
aegis/
│
├── app/
│   ├── main.py                    # Точка входу
│   ├── agent.py                   # Оркестратор
│   ├── config.py                  # Конфігурація (.env)
│   │
│   ├── llm/
│   │   ├── ollama_client.py       # Клієнт Ollama API
│   │   └── prompts.py             # Системні промпти + антигалюцинація
│   │
│   ├── rag/
│   │   ├── pdf_loader.py          # PDF → чанки (text + OCR fallback)
│   │   ├── embeddings.py          # Ollama / sentence-transformers
│   │   ├── vector_store.py        # ChromaDB
│   │   └── retriever.py           # Повний RAG-пайплайн
│   │
│   ├── skills/
│   │   ├── models.py              # SQLAlchemy моделі
│   │   ├── manager.py             # CRUD
│   │   └── executor.py            # Виконання скілів
│   │
│   ├── tools/
│   │   ├── base.py                # BaseTool + ToolRegistry
│   │   ├── browser.py             # Playwright
│   │   ├── web_scraper.py         # BeautifulSoup
│   │   ├── file_manager.py        # Файлова система (sandboxed)
│   │   ├── whatsapp.py            # Заглушка
│   │   ├── script_runner.py       # Запуск скриптів
│   │   ├── plugin_loader.py       # Автозавантаження
│   │   └── plugins/               # ← кидати плагіни сюди
│   │
│   ├── scheduler/
│   │   ├── models.py              # Модель задачі
│   │   ├── manager.py             # CRUD + історія
│   │   ├── runner.py              # APScheduler
│   │   └── notifications.py       # Callbacks
│   │
│   ├── gui/
│   │   └── interface.py           # Gradio (5 вкладок)
│   │
│   └── db/
│       └── database.py            # SQLite
│
├── knowledge_base/                # ← PDF сюди
├── scripts/                       # ← скрипти сюди
├── data/                          # БД, ChromaDB, скріншоти
├── tests/                         # Тести по етапах
│
├── .env                           # Конфігурація
├── requirements.txt
└── README.md
```

<br>

---

<br>

## 📦 Модулі

<details>
<summary><b>💬 Chat & LLM</b></summary>

<br>

```python
from app.llm.ollama_client import OllamaClient

client = OllamaClient()
client.is_available()            # True
client.list_models()             # ['qwen2.5:7b', ...]
client.chat("Привіт!")          # "Привіт! Чим можу допомогти?"
client.embed("текст")           # [0.012, -0.045, ...] (768-dim)
```

Оркестратор класифікує інтент одним словом і маршрутизує запит:

```python
from app.agent import Agent

agent = Agent()
r = await agent.process_message("Яка потужність двигуна БМП К-17?")

r.text            # "510 к.с. [Джерело: ozbroennia.pdf, стр. 50]"
r.intent          # "RAG"
r.sources         # [{"source": "ozbroennia.pdf", "page": 50, "score": 0.84}]
r.execution_time  # 5.2
```

</details>

<details>
<summary><b>📚 RAG Pipeline</b></summary>

<br>

```python
from app.rag.retriever import Retriever

r = Retriever()
r.index_pdf("knowledge_base/document.pdf")  # → 42 чанки
r.reindex()                                  # переіндексувати все

chunks = r.search("питання", top_k=5)       # тільки пошук
answer = r.ask("Що таке RAG?")              # пошук + генерація
```

**Антигалюцинаційний захист:**
- Температура 0.1 (мінімум креативності)
- Контекст ЗАВЖДИ передається явно в промпті
- Відповідь без контексту = «немає інформації»
- Подвійна перевірка через `HALLUCINATION_CHECK_PROMPT`
- Кожне твердження — з посиланням на джерело та сторінку

**OCR fallback**: автовизначення битого тексту (< 30% кирилиці) → Tesseract `ukr+rus+eng`

**Налаштування** через `.env`:

| Параметр | Default | Ефект |
|----------|---------|-------|
| `RAG_CHUNK_SIZE` | 600 | Більше → більше контексту, менше точності |
| `RAG_CHUNK_OVERLAP` | 100 | Більше → менше втрат на границях чанків |
| `RAG_TOP_K` | 5 | Більше → більше контексту для LLM |
| `RAG_RELEVANCE_THRESHOLD` | 0.3 | Менше → більше результатів |

</details>

<details>
<summary><b>🧠 Skills System</b></summary>

<br>

Скіл = збережений промпт + шаблон з `{параметрами}` + опціональний скрипт.

**Вбудовані скіли:**

| Скіл | Категорія | RAG | Що робить |
|------|-----------|-----|-----------|
| `knowledge_qa` | rag | ✅ | Питання-відповідь по базі |
| `analyze_document` | rag | ✅ | Аналіз документа |
| `translate` | generation | — | Переклад тексту |
| `code_gen` | generation | — | Генерація коду |

```python
from app.skills.manager import Manager

mgr = Manager()

# Створити кастомний скіл
mgr.create_skill(
    name="email_writer",
    category="generation",
    system_prompt="Ти — експерт з ділового листування.",
    user_template="Лист на тему: {topic}\nДеталі: {details}",
)
```

</details>

<details>
<summary><b>🔧 Tools & Plugins</b></summary>

<br>

| Інструмент | Дії |
|------------|-----|
| `browser` | get_text, screenshot, click |
| `web_scraper` | headings, tables, links, all |
| `file_manager` | read, write, list (sandboxed) |
| `script_runner` | запуск .py з `scripts/` (timeout 60s) |
| `whatsapp` | заглушка (WIP) |

**Створення плагіна** — один файл у `app/tools/plugins/`:

```python
# app/tools/plugins/telegram_bot.py
from app.tools.base import BaseTool, ToolResult

class TelegramTool(BaseTool):
    name = "telegram"
    description = "Відправляє повідомлення в Telegram"

    async def execute(self, **params) -> ToolResult:
        chat_id = params.get("chat_id")
        message = params.get("message")
        # ... ваша логіка ...
        return ToolResult(success=True, data={"sent": True})
```

Перезапуск — і агент вже знає про `telegram`.

**Скрипти** — кинути `.py` у `scripts/`, агент запустить через `script_runner`:
```bash
scripts/
├── check_prices.py
├── generate_report.py
└── sync_data.py
```

</details>

<details>
<summary><b>⏰ Scheduler</b></summary>

<br>

```python
from app.scheduler.manager import TaskManager

tm = TaskManager()

# Щодня о 9:00 — звіт
tm.create_task(
    name="morning_report",
    schedule_type="cron",
    schedule_value="0 9 * * *",
    action_type="skill",
    action_config={"skill": "analyze_document", "topic": "стан бази"},
)

# Кожні 2 години — моніторинг
tm.create_task(
    name="check_site",
    schedule_type="interval",
    schedule_value="2h",
    action_type="tool",
    action_config={"tool": "browser", "action": "get_text", "url": "https://..."},
    on_error="disable",  # вимкнути при помилці
)
```

| Тип | Формат | Приклад |
|-----|--------|---------|
| interval | `Ns`, `Nm`, `Nh`, `Nd` | `30m`, `2h`, `1d` |
| cron | стандартний cron | `0 9 * * MON-FRI` |
| once | datetime | `2026-12-31 14:00` |

</details>

<br>

---

<br>

## ⚙️ Конфігурація

Усі параметри — у файлі `.env` в корені проєкту.

```env
# ── LLM ─────────────────────────────────────────
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
OLLAMA_TEMPERATURE=0.1
OLLAMA_NUM_CTX=8192
OLLAMA_TIMEOUT=120

# ── RAG ─────────────────────────────────────────
RAG_CHUNK_SIZE=600
RAG_CHUNK_OVERLAP=100
RAG_TOP_K=5
RAG_RELEVANCE_THRESHOLD=0.3

# ── GUI ─────────────────────────────────────────
GUI_HOST=0.0.0.0
GUI_PORT=7860
```

**Віддалений Ollama:** `OLLAMA_BASE_URL=http://192.168.1.100:11434`
**Більший контекст:** `OLLAMA_NUM_CTX=16384`
**Точніший RAG:** `RAG_TOP_K=8` + `RAG_CHUNK_OVERLAP=150`

<br>

---

<br>

## 🧪 Тести

Кожен етап розробки має окремий тест-файл:

```bash
python -m tests.test_stage1      # Config, DB, Ollama
python -m tests.test_stage2      # RAG pipeline
python -m tests.test_ocr_rag     # RAG + OCR (зашифровані PDF)
python -m tests.test_stage3      # Skills CRUD + execution
python -m tests.test_stage4      # Tools + plugins + security
python -m tests.test_stage5      # Orchestrator (intent routing)
python -m tests.test_stage5_5    # Scheduler
```

| Модуль | Тести | Статус |
|--------|-------|--------|
| Config + DB + Ollama | 6/6 | ✅ |
| RAG Pipeline | 6/6 | ✅ |
| OCR Fallback | 3/3 | ✅ |
| Skills System | 6/6 | ✅ |
| Tools + Plugins | 6/6 | ✅ |
| Orchestrator | 6/6 | ✅ |
| Scheduler | 6/6 | ✅ |
| GUI | manual | ✅ |

<br>

---

<br>

## 🤖 Яку модель обрати?

| Модель | RAM | Швидкість | Якість (uk/ru) | Рекомендація |
|--------|-----|-----------|----------------|--------------|
| `qwen2.5:7b` | ~5 GB | ⚡⚡⚡ | ⭐⭐⭐⭐ | **За замовчуванням.** Найкращий баланс для кирилиці |
| `llama3.1:8b` | ~5 GB | ⚡⚡⚡ | ⭐⭐⭐ | Добрий для англомовних документів |
| `mistral:7b` | ~4.5 GB | ⚡⚡⚡⚡ | ⭐⭐⭐ | Найшвидший |
| `deepseek-r1` | ~8 GB | ⚡⚡ | ⭐⭐⭐⭐⭐ | Найрозумніший, але повільний |

<br>

---

<br>

## ❓ FAQ

<details>
<summary><b>Як підключити Ollama на іншому комп'ютері?</b></summary>
<br>

На сервері: `OLLAMA_HOST=0.0.0.0 ollama serve`
В `.env` агента: `OLLAMA_BASE_URL=http://192.168.1.100:11434`
</details>

<details>
<summary><b>PDF не індексується — OCR не працює</b></summary>
<br>

Встановіть Tesseract:
- Windows: `choco install tesseract` або [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki)
- Linux: `apt install tesseract-ocr tesseract-ocr-ukr tesseract-ocr-rus`
- Переконайтесь що `tesseract` доступний у PATH
</details>

<details>
<summary><b>Агент галюцинує</b></summary>
<br>

- Зменшіть `OLLAMA_TEMPERATURE` до `0.0`
- Збільшіть `RAG_TOP_K` до `8`
- Перевірте якість OCR: `python -m tests.test_ocr_rag`
- Спробуйте іншу модель (`deepseek-r1` — найточніша)
</details>

<details>
<summary><b>Як додати свій інструмент?</b></summary>
<br>

Три шляхи:

1. **Плагін** — `.py` файл у `app/tools/plugins/`
2. **Скрипт** — `.py` файл у `scripts/` (запускається через `script_runner`)
3. **Скіл** — збережений промпт через GUI (вкладка «Скіли»)
</details>

<details>
<summary><b>Вкладки в GUI зависають</b></summary>
<br>

Дані на вкладках завантажуються тільки по кнопці «🔄 Оновити». Якщо все одно зависає — перевірте консоль браузера на `effect_update_depth_exceeded` і перезапустіть агента.
</details>

<br>

---

<br>

<div align="center">

```
⬡ AEGIS — your knowledge, your hardware, your control.
```

<sub>Built with Ollama, ChromaDB, Gradio & ☕</sub>

</div>