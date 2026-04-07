# ============================================================
# Local AI Agent — Docker image for Railway deployment
# Ollama + pgvector
# ============================================================
FROM python:3.11-slim

# Системные зависимости: Tesseract OCR, Playwright deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake \
    tesseract-ocr \
    tesseract-ocr-ukr \
    tesseract-ocr-rus \
    tesseract-ocr-eng \
    # Playwright chromium deps
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 \
    libxdamage1 libxrandr2 libgbm1 libpango-1.0-0 \
    libcairo2 libasound2 libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Зависимости Python (кеш Docker layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Установка Playwright Chromium
RUN playwright install chromium

# Код приложения
COPY . .

# Создаём директории для данных
RUN mkdir -p data knowledge_base scripts

# Tesseract — переменная для PyMuPDF
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata

# LLM — Ollama
ENV OLLAMA_BASE_URL=http://ollama:11434
ENV OLLAMA_MODEL=qwen2.5:7b
ENV OLLAMA_EMBEDDING_MODEL=nomic-embed-text

# Railway: PORT присваивается платформой
ENV PORT=7860
ENV GUI_HOST=0.0.0.0

EXPOSE ${PORT}

CMD ["python", "-m", "app.main"]
