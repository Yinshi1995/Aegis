"""Скачивание GGUF-моделей для llama-cpp-python.

Запуск:
    python scripts/download_models.py

Скачивает в ./models/:
  - qwen2.5-7b-instruct-q4_k_m.gguf  (чат)
  - nomic-embed-text-v1.5.Q8_0.gguf   (эмбеддинги)
"""

import os
import sys
from pathlib import Path

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"

MODELS = [
    {
        "repo": "Qwen/Qwen2.5-7B-Instruct-GGUF",
        "filename": "qwen2.5-7b-instruct-q4_k_m.gguf",
    },
    {
        "repo": "nomic-ai/nomic-embed-text-v1.5-GGUF",
        "filename": "nomic-embed-text-v1.5.Q8_0.gguf",
    },
]


def main() -> None:
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        print("huggingface-hub не установлен. Устанавливаю...")
        os.system(f"{sys.executable} -m pip install huggingface-hub")
        from huggingface_hub import hf_hub_download

    MODELS_DIR.mkdir(exist_ok=True)

    for model in MODELS:
        dest = MODELS_DIR / model["filename"]
        if dest.exists():
            print(f"✓ {model['filename']} уже скачана, пропускаю")
            continue
        print(f"⬇ Скачиваю {model['filename']} из {model['repo']}...")
        hf_hub_download(
            repo_id=model["repo"],
            filename=model["filename"],
            local_dir=str(MODELS_DIR),
            local_dir_use_symlinks=False,
        )
        print(f"✓ {model['filename']} готова")

    print(f"\nМодели в {MODELS_DIR}:")
    for f in MODELS_DIR.glob("*.gguf"):
        size_gb = f.stat().st_size / (1024**3)
        print(f"  {f.name}  ({size_gb:.1f} GB)")


if __name__ == "__main__":
    main()
