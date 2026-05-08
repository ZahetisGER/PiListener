"""
Audio-Listener und Speech-to-Text Modul für PiListener
Nimmt Audio auf, erkennt Stille und transkribiert mit faster-whisper
"""

import os
import io
import wave
import time
import tempfile
from pathlib import Path
from typing import Optional, Tuple, List
from dataclasses import dataclass
import struct

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel
from dotenv import load_dotenv

from src.logger import get_logger

logger = get_logger()

# Default Werte
DEFAULT_SAMPLE_RATE = 16000
DEFAULT_CHANNELS = 1
DEFAULT_SILENCE_THRESHOLD_DB = 30
DEFAULT_LISTEN_DURATION = 20  # Sekunden

# Fix-Liste für akustische Beschreibungen (Fallback)
ACOUSTIC_SOUNDS = [
    "Regen", "Wind", "Vogelgesang", "Verkehr", "Stimme",
    "Musik", "Stille", "Ticken", "Tür", "Hund", "Kinder",
    "Gewitter", "Meereswellen", "Feuer", "Kirchenglocken",
    "Autohupe", "Treppen", "Flüstern"
]


@dataclass
class AudioData:
    """Datenklasse für Audio-Aufnahme."""
    samples: np.ndarray
    sample_rate: int
    duration: float
    rms_db: float


@dataclass
class TranscriptionResult:
    """Datenklasse für Transkriptions-Ergebnis."""
    text: str
    language: str
    model_used: str
    is_fallback: bool = False


class AudioListener:
    """ Nimmt Audio auf und erkennt Lautstärke-Pegel. """

    def __init__(
        self,
        device: Optional[str] = None,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        channels: int = DEFAULT_CHANNELS
    ):
        """
        Initialisiert den Audio-Listener.

        Args:
            device: ALSA Device String (z.B. 'hw:CARD=Speak,DEV=0')
            sample_rate: Sample Rate (16kHz optimal für Whisper)
            channels: Anzahl Kanäle (1 = Mono)
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.device = self._resolve_device(device)
        self._stream = None

        logger.info(f"Audio-Listener initialisiert. Device: {self.device}, Rate: {sample_rate}")

    def _resolve_device(self, device: Optional[str]) -> Optional[str]:
        """
        Löst ALSA Device String auf.

        Args:
            device: ALSA Device oder None für Default

        Returns:
            Aufgelöstes Device
        """
        if device is None:
            return None

        # Prüfe ob Device verfügbar ist
        try:
            devices = sd.query_devices()
            logger.debug(f"Verfügbare Audio-Geräte: {len(devices)}")

            # Versuche Device als Index oder Name zu finden
            if isinstance(device, str):
                # ALSA Format wie 'hw:CARD=Speak,DEV=0'
                if device.startswith('hw:'):
                    # Finde对应的 Index
                    for i, dev in enumerate(devices):
                        dev_name = dev.get('name', '')
                        if device.split(',')[0].replace('hw:', '') in dev_name:
                            logger.info(f"Device '{device}' gefunden als Index {i}")
                            return i
                elif device.isdigit():
                    idx = int(device)
                    if idx < len(devices):
                        return idx
        except sd.PortAudioError as e:
            logger.warning(f"Device-Abfrage fehlgeschlagen: {e}")

        return None

    def get_audio_devices(self) -> List[dict]:
        """
        Gibt alle verfügbaren Audio-Geräte zurück.

        Returns:
            Liste von Device-Dicts
        """
        try:
            devices = sd.query_devices()
            result = []
            for i, dev in enumerate(devices):
                result.append({
                    "index": i,
                    "name": dev.get('name', 'Unknown'),
                    "channels": dev.get('max_input_channels', 0),
                    "sample_rate": dev.get('default_samplerate', 0)
                })
            return result
        except sd.PortAudioError as e:
            logger.error(f"Device-Abfrage fehlgeschlagen: {e}")
            return []

    def calculate_rms_db(self, samples: np.ndarray) -> float:
        """
        Berechnet den RMS-Pegel in dB.

        Args:
            samples: Audio-Samples

        Returns:
            Pegel in dB
        """
        if len(samples) == 0:
            return -np.inf

        # RMS berechnen
        rms = np.sqrt(np.mean(samples.astype(np.float32) ** 2))

        # In dB umrechnen (mit kleinem Offset um -inf zu vermeiden)
        if rms > 0:
            db = 20 * np.log10(rms)
        else:
            db = -np.inf

        return db

    def record(
        self,
        duration: float = DEFAULT_LISTEN_DURATION,
        threshold_db: float = DEFAULT_SILENCE_THRESHOLD_DB
    ) -> Optional[AudioData]:
        """
        Nimmt Audio für angegebene Dauer auf.

        Args:
            duration: Aufnahme-Dauer in Sekunden
            threshold_db: Schwellwert für Stille-Erkennung

        Returns:
            AudioData oder None wenn zu leise
        """
        try:
            logger.debug(f"Starte Aufnahme: {duration}s, Device: {self.device}")

            # Audio aufnehmen
            audio_data = sd.rec(
                int(duration * self.sample_rate),
                samplerate=self.sample_rate,
                channels=self.channels,
                device=self.device,
                dtype='int16'
            )

            # Warten bis Aufnahme fertig
            sd.wait()

            # Zu float32 konvertieren für RMS-Berechnung
            samples = audio_data.flatten().astype(np.float32) / 32768.0

            # RMS berechnen
            rms_db = self.calculate_rms_db(samples)

            logger.debug(f"Aufnahme beendet: RMS={rms_db:.1f}dB")

            # Stille-Prüfung
            if rms_db < threshold_db:
                logger.warning(f"Stille erkannt (RMS={rms_db:.1f}dB < {threshold_db}dB)")
                return None

            return AudioData(
                samples=samples,
                sample_rate=self.sample_rate,
                duration=duration,
                rms_db=rms_db
            )

        except sd.PortAudioError as e:
            logger.error(f"PortAudio Fehler bei Aufnahme: {e}")
            return None
        except Exception as e:
            logger.error(f"Unerwarteter Fehler bei Aufnahme: {e}")
            return None

    def is_device_connected(self) -> bool:
        """
        Prüft ob das konfigurierte Device noch verbunden ist.

        Returns:
            True wenn Device verfügbar
        """
        try:
            if self.device is None:
                return True  # Default Device

            devices = sd.query_devices()
            if isinstance(self.device, int):
                return 0 <= self.device < len(devices)
            return True
        except:
            return False


class STTEngine:
    """Speech-to-Text Engine mit faster-whisper und Fallbacks."""

    def __init__(
        self,
        model_size: str = "base",
        language: str = "de",
        models_dir: str = "models"
    ):
        """
        Initialisiert die STT Engine.

        Args:
            model_size: Whisper Modell-Größe (tiny, base, small, medium, large)
            language: Sprache-Code (de, en, etc.)
            models_dir: Verzeichnis für lokale Modelle
        """
        self.model_size = model_size
        self.language = language
        self.models_dir = Path(models_dir)
        self.model = None

        # Model herunterladen/wenn nötig
        self._load_model()

    def _load_model(self) -> None:
        """Lädt das Whisper-Modell (bei Installation, nicht lazy)."""
        try:
            logger.info(f"Lade Whisper-Modell '{self.model_size}'...")

            # Stelle sicher dass Model-Verzeichnis existiert
            self.models_dir.mkdir(parents=True, exist_ok=True)

            # Lade Modell (CPU, int8 für Pi 4)
            self.model = WhisperModel(
                self.model_size,
                device="cpu",
                compute_type="int8",
                download_root=str(self.models_dir)
            )

            logger.info(f"Whisper-Modell '{self.model_size}' geladen")

        except Exception as e:
            logger.error(f"Fehler beim Laden des Whisper-Modells: {e}")
            raise

    def transcribe(
        self,
        audio_data: AudioData,
        api_key: Optional[str] = None
    ) -> TranscriptionResult:
        """
        Transkribiert Audio zu Text.

        Args:
            audio_data: Audio-Daten
            api_key: Optionaler API Key für OpenRouter Fallback

        Returns:
            TranscriptionResult
        """
        # Versuche lokales Whisper
        try:
            result = self._transcribe_local(audio_data)
            if result.text.strip():
                return result
        except Exception as e:
            logger.error(f"Lokales Whisper fehlgeschlagen: {e}")

        # Fallback 1: OpenRouter API
        if api_key:
            try:
                result = self._transcribe_openrouter(audio_data, api_key)
                if result.text.strip():
                    return result
            except Exception as e:
                logger.error(f"OpenRouter STT Fallback fehlgeschlagen: {e}")

        # Fallback 2: Akustische Beschreibung
        return self._generate_acoustic_description(audio_data)

    def _transcribe_local(self, audio_data: AudioData) -> TranscriptionResult:
        """
        Transkribiert mit lokaler Whisper-Modell.

        Args:
            audio_data: Audio-Daten

        Returns:
            TranscriptionResult
        """
        # Konvertiere zu Float32 Array
        samples = audio_data.samples

        # Transkribiere
        segments, info = self.model.transcribe(
            samples,
            language=self.language,
            beam_size=5,
            vad_filter=True  # Voice Activity Detection
        )

        # Sammle Text
        text_parts = []
        for segment in segments:
            text_parts.append(segment.text.strip())

        text = " ".join(text_parts)

        logger.info(f"STT (lokal): \"{text[:100]}...\"" if len(text) > 100 else f"STT (lokal): \"{text}\"")

        return TranscriptionResult(
            text=text,
            language=info.language or self.language,
            model_used=f"faster-whisper-{self.model_size}",
            is_fallback=False
        )

    def _transcribe_openrouter(
        self,
        audio_data: AudioData,
        api_key: str
    ) -> TranscriptionResult:
        """
        Transkribiert via OpenRouter API (Fallback).

        Args:
            audio_data: Audio-Daten
            api_key: OpenRouter API Key

        Returns:
            TranscriptionResult
        """
        from openai import OpenAI

        # Speichere Audio temporär als WAV
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            temp_wav = f.name
            self._save_wav(audio_data, temp_wav)

        try:
            client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")

            with open(temp_wav, 'rb') as audio_file:
                transcript = client.audio.transcriptions.create(
                    model="openai/whisper-large-v3",
                    file=audio_file,
                    language="de"
                )

            text = transcript.text if hasattr(transcript, 'text') else str(transcript)

            logger.info(f"STT (OpenRouter): \"{text}\"")

            return TranscriptionResult(
                text=text,
                language=self.language,
                model_used="openrouter/whisper",
                is_fallback=True
            )

        finally:
            # Temp-Datei löschen
            try:
                os.unlink(temp_wav)
            except:
                pass

    def _generate_acoustic_description(self, audio_data: AudioData) -> TranscriptionResult:
        """
        Generiert eine akustische Beschreibung als letzten Fallback.

        Args:
            audio_data: Audio-Daten

        Returns:
            TranscriptionResult mit akustischer Beschreibung
        """
        # Analysiere Audio-Eigenschaften
        rms_db = audio_data.rms_db
        duration = audio_data.duration

        # Wähle passende Sounds aus der Fix-Liste basierend auf
        #heuristik (hier vereinfacht - in echtem System würde hier
        #eine echte Audio-Analyse mit Frequenzbins stattfinden)

        # Da wir keine echte Frequenzanalyse haben,
        # generiere eine reasonable description basierend auf RMS
        if rms_db < 25:
            detected = ["Stille"]
        elif rms_db < 40:
            detected = ["ferne Stimme", "leiser Wind"]
        else:
            detected = ["Stimme", "Gewitter"]

        description = f"Es klingt nach: {', '.join(detected)}"

        logger.info(f"STT (Fallback/Beschreibung): \"{description}\"")

        return TranscriptionResult(
            text=description,
            language=self.language,
            model_used="acoustic-description",
            is_fallback=True
        )

    def _save_wav(self, audio_data: AudioData, filename: str) -> None:
        """
        Speichert AudioData als WAV-Datei.

        Args:
            audio_data: Audio-Daten
            filename: Ziel-Dateiname
        """
        with wave.open(filename, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(audio_data.sample_rate)

            # Konvertiere float zu int16
            samples_int = (audio_data.samples * 32767).astype(np.int16)
            wav_file.writeframes(samples_int.tobytes())


def create_listener() -> Tuple[AudioListener, STTEngine]:
    """
    Factory-Function für AudioListener und STTEngine.

    Returns:
        Tuple von (AudioListener, STTEngine)
    """
    load_dotenv("config/.env")

    # Konfiguration aus .env
    audio_source = os.getenv("AUDIO_SOURCE")
    sample_rate = int(os.getenv("SAMPLE_RATE", str(DEFAULT_SAMPLE_RATE)))
    language = os.getenv("LANGUAGE", "de")
    whisper_model = os.getenv("WHISPER_MODEL", "base")
    models_dir = os.getenv("MODELS_DIR", "models")
    silence_threshold = float(os.getenv("SILENCE_THRESHOLD_DB", str(DEFAULT_SILENCE_THRESHOLD_DB)))

    listener = AudioListener(
        device=audio_source,
        sample_rate=sample_rate
    )

    stt_engine = STTEngine(
        model_size=whisper_model,
        language=language,
        models_dir=models_dir
    )

    return listener, stt_engine
