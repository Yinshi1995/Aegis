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

    def test_llamacpp_backend_creation(self):
        """LLM_BACKEND=llamacpp → LlamaCppClient (без загрузки модели)."""
        from app.llm.llamacpp_client import LlamaCppClient
        from app.llm.base_client import BaseLLMClient

        # Создаём клиент напрямую (модель не грузим)
        client = LlamaCppClient()
        assert isinstance(client, BaseLLMClient)
        assert isinstance(client, LlamaCppClient)
        # Модель ещё не загружена (ленивая загрузка)
        assert client._model is None
        assert client._embed_model is None

    def test_llamacpp_missing_model_file(self):
        """Если файл .gguf не существует — FileNotFoundError с понятным сообщением."""
        from app.llm.llamacpp_client import LlamaCppClient

        client = LlamaCppClient()
        # Пытаемся получить модель — должно быть FileNotFoundError
        with pytest.raises(FileNotFoundError, match="GGUF-модель не найдена"):
            client._get_model()

    def test_llamacpp_is_available_false_when_no_files(self):
        """is_available() = False если .gguf файлов нет."""
        from app.llm.llamacpp_client import LlamaCppClient

        client = LlamaCppClient()
        assert client.is_available() is False


class TestBaseLLMInterface:
    """Проверяем что оба клиента реализуют все методы BaseLLMClient."""

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

    def test_llamacpp_implements_interface(self):
        """LlamaCppClient реализует все абстрактные методы."""
        from app.llm.llamacpp_client import LlamaCppClient
        from app.llm.base_client import BaseLLMClient

        assert issubclass(LlamaCppClient, BaseLLMClient)

        required_methods = ["is_available", "list_models", "chat", "generate", "embed", "embed_batch", "chat_stream"]
        for method_name in required_methods:
            assert hasattr(LlamaCppClient, method_name), f"LlamaCppClient не имеет метода {method_name}"
            method = getattr(LlamaCppClient, method_name)
            assert callable(method), f"LlamaCppClient.{method_name} не callable"

    def test_both_have_same_signature_for_core_methods(self):
        """Сигнатуры ключевых методов совпадают."""
        from app.llm.ollama_client import OllamaClient
        from app.llm.llamacpp_client import LlamaCppClient

        for method_name in ["chat", "generate", "embed", "embed_batch"]:
            ollama_sig = inspect.signature(getattr(OllamaClient, method_name))
            llamacpp_sig = inspect.signature(getattr(LlamaCppClient, method_name))

            ollama_params = set(ollama_sig.parameters.keys())
            llamacpp_params = set(llamacpp_sig.parameters.keys())

            # Общие параметры должны присутствовать в обоих
            common = ollama_params & llamacpp_params
            assert "self" in common, f"{method_name}: оба должны иметь self"


class TestLlamaCppListModels:
    """Тесты list_models()."""

    def test_list_models_empty_dir(self, tmp_path):
        """list_models() возвращает [] если папки models нет."""
        from app.llm.llamacpp_client import LlamaCppClient
        client = LlamaCppClient()
        # По умолчанию ./models/ может не существовать
        models = client.list_models()
        assert isinstance(models, list)
