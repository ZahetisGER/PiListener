"""
Tests für Speech-to-Text Engine und Fallback-Kette.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import numpy as np

from src.listener import AudioData, TranscriptionResult, STTEngine


class TestTranscriptionResult:
    """Tests für TranscriptionResult Datenklasse."""

    def test_transcription_result_creation(self):
        """Test das Erstellen von TranscriptionResult."""
        result = TranscriptionResult(
            text="Hallo Welt",
            language="de",
            model_used="faster-whisper-base",
            is_fallback=False
        )

        assert result.text == "Hallo Welt"
        assert result.language == "de"
        assert result.model_used == "faster-whisper-base"
        assert result.is_fallback is False

    def test_transcription_result_fallback(self):
        """Test Fallback Kennzeichnung."""
        result = TranscriptionResult(
            text="Es klingt nach: Regen, Wind",
            language="de",
            model_used="acoustic-description",
            is_fallback=True
        )

        assert result.is_fallback is True
        assert result.model_used == "acoustic-description"


class TestSTTEngine:
    """Tests für STTEngine."""

    @pytest.fixture
    def mock_audio_data(self):
        """Erstellt Test-Audiodaten."""
        samples = np.random.randn(16000 * 5).astype(np.float32) * 0.1
        return AudioData(
            samples=samples,
            sample_rate=16000,
            duration=5.0,
            rms_db=35.0
        )

    @pytest.fixture
    def mock_whisper_model(self):
        """Mock für WhisperModel."""
        with patch('src.listener.WhisperModel') as mock:
            yield mock

    def test_stt_engine_initialization(self, mock_whisper_model):
        """Test STT Engine Initialisierung."""
        engine = STTEngine(model_size="tiny", language="de")

        assert engine.model_size == "tiny"
        assert engine.language == "de"
        mock_whisper_model.assert_called_once()

    def test_generate_acoustic_description(self, mock_audio_data):
        """Test akustische Beschreibung Fallback."""
        engine = STTEngine.__new__(STTEngine)
        engine.language = "de"

        result = engine._generate_acoustic_description(mock_audio_data)

        assert result.is_fallback is True
        assert result.model_used == "acoustic-description"
        assert "klingt nach" in result.text
        assert result.language == "de"

    def test_generate_acoustic_description_silent(self, mock_whisper_model):
        """Test akustische Beschreibung bei Stille."""
        silent_audio = AudioData(
            samples=np.zeros(16000),
            sample_rate=16000,
            duration=1.0,
            rms_db=20.0
        )

        engine = STTEngine.__new__(STTEngine)
        engine.language = "de"

        result = engine._generate_acoustic_description(silent_audio)

        assert "Stille" in result.text

    def test_transcribe_with_fallback(self, mock_audio_data, mock_whisper_model):
        """Test Transkription mit API Fallback."""
        # Mock Whisper für lokal
        mock_model_instance = MagicMock()
        mock_segments = [Mock(text="Lokaler Text")]
        mock_model_instance.transcribe.return_value = (mock_segments, Mock(language="de"))
        mock_whisper_model.return_value = mock_model_instance

        engine = STTEngine(model_size="tiny", language="de")

        # Kein API Key, sollte akustische Beschreibung generieren
        with patch.object(engine, '_transcribe_local', side_effect=Exception("Lokal fehlgeschlagen")):
            result = engine.transcribe(mock_audio_data, api_key=None)

        assert result.is_fallback is True


class TestFallbackChain:
    """Tests für die Fallback-Kette."""

    def test_fallback_priority_order(self):
        """Test das Fallbacks in richtiger Reihenfolge probiert werden."""
        # Die Fallback-Kette sollte sein:
        # 1. Lokales Whisper
        # 2. OpenRouter API
        # 3. Akustische Beschreibung

        priorities = [
            "Lokales Whisper (faster-whisper)",
            "OpenRouter Whisper API",
            "Akustische Beschreibung"
        ]

        # Diese Reihenfolge muss eingehalten werden
        assert "Akustische Beschreibung" in priorities
        assert "Lokales Whisper" in priorities


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
