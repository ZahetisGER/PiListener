"""
Tests für Model-Selektor und dynamische Model-Auswahl.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from datetime import datetime, timedelta

from src.model_selector import (
    ModelSelector, 
    get_model_selector, 
    CACHE_FILE, 
    CACHE_DURATION_HOURS
)


class TestModelSelector:
    """Tests für ModelSelector Klasse."""

    @pytest.fixture
    def mock_api_key(self):
        """Mock API Key."""
        return "sk-or-v1-test-key"

    @pytest.fixture
    def model_selector(self, mock_api_key):
        """Erstellt einen ModelSelector mit gemockten Daten."""
        with patch('src.model_selector.requests.get'):
            selector = ModelSelector(api_key=mock_api_key)
            selector.available_models = {
                "stt": [{"id": "whisper-1", "name": "Whisper"}],
                "image": [{"id": "sdxl-turbo", "name": "SDXL Turbo"}],
                "reasoning": []
            }
            return selector

    def test_model_selector_initialization(self, mock_api_key):
        """Test ModelSelector Initialisierung."""
        selector = ModelSelector(api_key=mock_api_key)
        
        assert selector.api_key == mock_api_key
        assert "stt" in selector.available_models
        assert "image" in selector.available_models

    def test_cache_file_path(self):
        """Test das Cache-Datei-Pfad definiert ist."""
        assert CACHE_FILE == "config/.model_cache.json"
        assert CACHE_DURATION_HOURS == 24

    def test_load_cache_valid(self, mock_api_key):
        """Test Cache-Laden mit validem Cache."""
        cache_data = {
            "timestamp": datetime.now().isoformat(),
            "models": {
                "stt": [{"id": "whisper"}],
                "image": [{"id": "sdxl"}],
                "reasoning": []
            }
        }
        
        with patch('pathlib.Path.exists', return_value=True):
            with patch('builtins.open', create=True) as mock_open:
                mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(cache_data)
                
                selector = ModelSelector(api_key=mock_api_key)
                
                # Cache sollte geladen worden sein
                assert selector.cache is not None

    def test_load_cache_expired(self, mock_api_key):
        """Test Cache-Laden mit abgelaufenem Cache."""
        old_time = datetime.now() - timedelta(hours=CACHE_DURATION_HOURS + 1)
        cache_data = {
            "timestamp": old_time.isoformat(),
            "models": {"stt": [], "image": [], "reasoning": []}
        }
        
        with patch('pathlib.Path.exists', return_value=True):
            with patch('builtins.open', create=True) as mock_open:
                mock_open.return_value.__enter__.return_value.read.return_value = json.dumps(cache_data)
                
                selector = ModelSelector(api_key=mock_api_key)
                
                # Cache sollte nicht verwendet werden (abgelaufen)
                assert selector.cache is None


class TestCapabilityMatching:
    """Tests für Model Capability Matching."""

    def test_stt_capability_match(self):
        """Test STT Capability Matching."""
        selector = ModelSelector.__new__(ModelSelector)
        
        stt_models = [
            {"id": "whisper-1", "capabilities": ["speech-to-text"]},
            {"id": "gpt-4", "capabilities": ["chat"]},
            {"id": "sdxl", "capabilities": ["image-generation"]}
        ]
        
        for model in stt_models:
            matches = selector._match_capabilities(model, "stt")
            
            if "speech-to-text" in model.get("capabilities", []):
                assert matches is True
            else:
                assert matches is False

    def test_image_capability_match(self):
        """Test Image Capability Matching."""
        selector = ModelSelector.__new__(ModelSelector)
        
        image_models = [
            {"id": "sdxl-turbo", "capabilities": ["image-generation"]},
            {"id": "whisper-1", "capabilities": ["speech-to-text"]},
            {"id": "claude", "capabilities": ["chat", "image"]}
        ]
        
        # SDXL sollte für image passen
        assert selector._match_capabilities(image_models[0], "image") is True
        # Whisper nicht
        assert selector._match_capabilities(image_models[1], "image") is False

    def test_reasoning_capability_match(self):
        """Test Reasoning Capability Matching."""
        selector = ModelSelector.__new__(ModelSelector)
        
        reasoning_models = [
            {"id": "claude-3", "capabilities": ["reasoning", "chat"]},
            {"id": "gpt-4", "capabilities": ["general", "chat"]},
            {"id": "whisper", "capabilities": ["speech-to-text"]}
        ]
        
        # Claude und GPT sollten für reasoning passen
        assert selector._match_capabilities(reasoning_models[0], "reasoning") is True
        assert selector._match_capabilities(reasoning_models[1], "reasoning") is True
        # Whisper nicht
        assert selector._match_capabilities(reasoning_models[2], "reasoning") is False


class TestModelRanking:
    """Tests für Model Ranking/Bewertung."""

    def test_get_best_model_prefers_known_providers(self):
        """Test das bekannte Provider bevorzugt werden."""
        selector = ModelSelector.__new__(ModelSelector)
        
        models = [
            {"id": "unknown-model", "provider": "unknown", "likes": 100},
            {"id": "gpt-4", "provider": "OpenAI", "likes": 50},
            {"id": "claude-3", "provider": "Anthropic", "likes": 40}
        ]
        
        best = selector._get_best_model(models, "image")
        
        # OpenAI oder Anthropic sollten gewinnen wegen Provider-Bonus
        assert best["provider"] in ["OpenAI", "Anthropic"]

    def test_get_best_model_with_no_models(self):
        """Test mit leerer Model-Liste."""
        selector = ModelSelector.__new__(ModelSelector)
        
        best = selector._get_best_model([], "image")
        
        assert best is None

    def test_get_best_model_sorts_by_score(self):
        """Test das Modelle nach Score sortiert werden."""
        selector = ModelSelector.__new__(ModelSelector)
        
        models = [
            {"id": "low-score", "provider": "test", "likes": 1},
            {"id": "high-score", "provider": "test", "likes": 100}
        ]
        
        best = selector._get_best_model(models, "image")
        
        assert best["id"] == "high-score"


class TestOpenRouterIntegration:
    """Tests für OpenRouter API Integration."""

    def test_fetch_openrouter_models_success(self):
        """Test erfolgreiches Holen von OpenRouter Modellen."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "data": [
                {"id": "model-1", "name": "Model 1"},
                {"id": "model-2", "name": "Model 2"}
            ]
        }
        mock_response.raise_for_status = Mock()
        mock_response.status_code = 200

        with patch('src.model_selector.requests.get', return_value=mock_response):
            selector = ModelSelector(api_key="test-key")
            models = selector.fetch_openrouter_models(free_only=True)
            
            assert len(models) == 2
            assert models[0]["id"] == "model-1"

    def test_fetch_openrouter_models_error(self):
        """Test Fehlerbehandlung bei OpenRouter API."""
        import requests
        
        with patch('src.model_selector.requests.get', side_effect=requests.exceptions.Timeout()):
            selector = ModelSelector(api_key="test-key")
            models = selector.fetch_openrouter_models()
            
            assert models == []


class TestModelSelectorFactory:
    """Tests für get_model_selector Factory."""

    def test_get_model_selector_requires_api_key(self):
        """Test das API Key erforderlich ist."""
        with patch('src.model_selector.load_dotenv'):
            with patch.dict('os.environ', {}, clear=True):
                with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
                    get_model_selector()


class TestUpdateModelList:
    """Tests für update_model_list Methode."""

    def test_update_model_list_stores_models(self):
        """Test das Modelle nach Update gespeichert werden."""
        mock_response = Mock()
        mock_response.json.return_value = {"data": []}
        mock_response.raise_for_status = Mock()
        mock_response.status_code = 200

        with patch('src.model_selector.requests.get', return_value=mock_response):
            selector = ModelSelector(api_key="test-key")
            selector.update_model_list(force=True)
            
            # Sollte_available_models aktualisiert haben
            assert "stt" in selector.available_models
            assert "image" in selector.available_models


class TestGetBestModels:
    """Tests für get_best_* Methoden."""

    def test_get_best_stt_model_returns_local(self):
        """Test das STT lokales Whisper bevorzugt."""
        selector = ModelSelector(api_key="test-key")
        model_id, provider = selector.get_best_stt_model()
        
        assert model_id == "faster-whisper"
        assert provider == "local"

    def test_get_best_image_model_with_cache(self):
        """Test Image Model Auswahl mit gecachten Modellen."""
        selector = ModelSelector(api_key="test-key")
        selector.available_models = {
            "stt": [],
            "image": [
                {"id": "sdxl-turbo", "source": "openrouter", "likes": 50}
            ],
            "reasoning": []
        }
        
        model_id, provider = selector.get_best_image_model()
        
        assert model_id == "sdxl-turbo"
        assert provider == "openrouter"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
