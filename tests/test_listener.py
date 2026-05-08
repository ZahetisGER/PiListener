"""
Tests für Audio-Listener und Stille-Erkennung.
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock

from src.listener import AudioListener, AudioData, STTEngine, ACOUSTIC_SOUNDS


class TestAudioData:
    """Tests für AudioData Datenklasse."""

    def test_audio_data_creation(self):
        """Test das Erstellen von AudioData."""
        samples = np.random.randn(16000).astype(np.float32)
        audio = AudioData(
            samples=samples,
            sample_rate=16000,
            duration=1.0,
            rms_db=45.0
        )

        assert audio.sample_rate == 16000
        assert audio.duration == 1.0
        assert audio.rms_db == 45.0
        assert len(audio.samples) == 16000

    def test_audio_data_empty(self):
        """Test mit leeren Samples."""
        audio = AudioData(
            samples=np.array([]),
            sample_rate=16000,
            duration=0.0,
            rms_db=-np.inf
        )

        assert len(audio.samples) == 0


class TestAudioListener:
    """Tests für AudioListener Klasse."""

    @pytest.fixture
    def mock_listener(self):
        """Erstellt einen gemockten AudioListener."""
        with patch('src.listener.sd') as mock_sd:
            yield mock_sd

    def test_calculate_rms_db(self, mock_listener):
        """Test RMS dB Berechnung."""
        listener = AudioListener(sample_rate=16000, channels=1)

        # Test mit leisen Samples
        quiet_samples = np.random.randn(16000).astype(np.float32) * 0.001
        rms_db = listener.calculate_rms_db(quiet_samples)
        assert rms_db < -40  # Sehr leise

        # Test mit lauten Samples
        loud_samples = np.random.randn(16000).astype(np.float32) * 0.5
        rms_db = listener.calculate_rms_db(loud_samples)
        assert rms_db > -6  # Laut

    def test_record_no_silence(self, mock_listener):
        """Test Aufnahme mit ausreichend Lautstärke."""
        # Mock sounddevice
        mock_sd = MagicMock()
        mock_sd.rec.return_value = np.random.randn(16000 * 5, 1).astype(np.int16)
        mock_sd.wait.return_value = None

        listener = AudioListener(sample_rate=16000, channels=1)

        with patch('src.listener.sd', mock_sd):
            result = listener.record(duration=5.0, threshold_db=20.0)

        assert result is not None
        assert result.rms_db >= 20.0

    def test_record_silence_detected(self, mock_listener):
        """Test das Stille erkannt wird."""
        # Mock mit sehr leisen Samples
        mock_sd = MagicMock()
        quiet_samples = np.zeros((16000 * 5, 1), dtype=np.int16)
        mock_sd.rec.return_value = quiet_samples
        mock_sd.wait.return_value = None

        listener = AudioListener(sample_rate=16000, channels=1)

        with patch('src.listener.sd', mock_sd):
            result = listener.record(duration=5.0, threshold_db=30.0)

        assert result is None  # Stille erkannt

    def test_device_resolution(self, mock_listener):
        """Test Device-Auflösung."""
        listener = AudioListener(device="hw:CARD=Speak,DEV=0")
        # Sollte ohne Fehler durchlaufen

    def test_is_device_connected(self, mock_listener):
        """Test Device-Connection Check."""
        listener = AudioListener()
        # Sollte True oder False zurückgeben ohne Fehler
        result = listener.is_device_connected()
        assert isinstance(result, bool)


class TestAcousticSounds:
    """Tests für akustische Sound-Erkennung."""

    def test_acoustic_sounds_list_not_empty(self):
        """Test das ACOUSTIC_SOUNDS nicht leer ist."""
        assert len(ACOUSTIC_SOUNDS) > 0
        assert "Regen" in ACOUSTIC_SOUNDS
        assert "Stille" in ACOUSTIC_SOUNDS
        assert "Stimme" in ACOUSTIC_SOUNDS

    def test_acoustic_sounds_fallback_description(self):
        """Test das akustische Beschreibungen generiert werden können."""
        # Dies testet nur das die Liste verfügbar ist
        assert isinstance(ACOUSTIC_SOUNDS, list)
        assert all(isinstance(s, str) for s in ACOUSTIC_SOUNDS)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
