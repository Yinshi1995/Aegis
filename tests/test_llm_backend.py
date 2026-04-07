"""
Тесты LLM-бэкенда: фабрика, интерфейс, обработка ошибок.
"""
import os
import sys
import inspect
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

# Корень проекта
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestLLMFactory:
    """Тесты фабрики get_llm_client()."""

    def setup_method(self):
        """Сбрасываем синглтон перед каждым тестом."""
        from app.llm import reset_llm_client
        reset_llm_client()

    def test_default_backend_is_ollama(self):
        """По умолчанию (LLM_BACKEND=ollama) — OllamaClient."""
        with patch.dict(os.environ, {"LLM_BACKEND": "ollama"}, clear=False):
            from app.llm import reset_llm_client, get_llm_client
            reset_llm_client()
            # Перезагружаем конфиг
            from app.config import AppConfig
            with patch("app.llm.config", AppConfig()):
                from app.llm import reset_llm_client as r2
                r2()
                client = get_llm_client()
                from app.llm.ollama_client import OllamaClient
                assert isinstance(client, OllamaClient)

class TestBaseLLMInterface:
    """Проверяем что OllamaClient реализует все методы BaseLLMClient."""

    def test_ollama_implements_interface(self):
        """OllamaClient реализует все абстрактные методы."""
        from app.llm.ollama_client import OllamaClient
        from app.llm.base_client import BaseLLMClient

        assert issubclass(OllamaClient, BaseLLMClient)

        required_methods = ["is_available", "list_models", "chat", "generate", "embed", "embed_batch"]
        for method_name in required_methods:
            assert hasattr(OllamaClient, method_name), f"OllamaClient не имеет метода {method_name}"
            method = getattr(OllamaClient, method_name)
            assert callable(method), f"OllamaClient.{method_name} не callable"
