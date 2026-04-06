# ============================================================
# Local AI Agent — Docker image for Railway deployment
# llama-cpp-python (CPU) + pgvector
# ============================================================
FROM python:3.11-slim

# Системные зависимости: сборка llama-cpp, Tesseract OCR, Playwright deps
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

# Скачиваем GGUF-модели при сборке
RUN mkdir -p models && \
    pip install --no-cache-dir huggingface-hub && \
    huggingface-cli download Qwen/Qwen2.5-7B-Instruct-GGUF qwen2.5-7b-instruct-q4_k_m.gguf \
        --local-dir ./models --local-dir-use-symlinks False && \
    huggingface-cli download nomic-ai/nomic-embed-text-v1.5-GGUF nomic-embed-text-v1.5.Q8_0.gguf \
        --local-dir ./models --local-dir-use-symlinks False

# Код приложения
COPY . .

# Создаём директории для данных
RUN mkdir -p data knowledge_base scripts

# Tesseract — переменная для PyMuPDF
ENV TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata

# LLM — llamacpp по дефолту в Docker
ENV LLM_BACKEND=llamacpp
ENV LLAMACPP_MODEL_PATH=./models/qwen2.5-7b-instruct-q4_k_m.gguf
ENV LLAMACPP_EMBED_MODEL_PATH=./models/nomic-embed-text-v1.5.Q8_0.gguf
ENV LLAMACPP_N_GPU_LAYERS=0
ENV LLAMACPP_N_CTX=4096
ENV LLAMACPP_CHAT_FORMAT=chatml

# Railway: PORT присваивается платформой
ENV PORT=7860
ENV GUI_HOST=0.0.0.0

EXPOSE ${PORT}

CMD ["python", "-m", "app.main"]
