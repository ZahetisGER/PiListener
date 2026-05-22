"""
Hauptschleife für PiListener
Koordiniert Audio-Aufnahme, STT, Bildgenerierung und Anzeige
"""

import os
import sys
import time
import signal
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta

from dotenv import load_dotenv

from src.logger import setup_logger, get_logger
from src.listener import AudioListener, STTEngine, AudioData
from src.image_generator import ImageGenerator
from src.display import DisplayManager
from src.model_selector import get_model_selector
from src.webserver import PiListenerWebServer

logger = None


class PiListener:
    """Hauptklasse für das PiListener-System."""

    def __init__(self):
        """Initialisiert das PiListener-System."""
        global logger

        # Logger initialisieren
        load_dotenv("config/.env")
        log_level = os.getenv("LOG_LEVEL", "INFO")
        setup_logger("logs/listener.log", log_level)
        logger = get_logger()

        # Konfiguration laden
        self.interval_minutes = int(os.getenv("LISTEN_INTERVAL_MINUTES", "15"))
        self.listen_duration = int(os.getenv("LISTEN_DURATION_SECONDS", "20"))
        self.silence_threshold = float(os.getenv("SILENCE_THRESHOLD_DB", "30"))

        # Komponenten
        self.listener: Optional[AudioListener] = None
        self.stt_engine: Optional[STTEngine] = None
        self.image_generator: Optional[ImageGenerator] = None
        self.display: Optional[DisplayManager] = None
        self.model_selector = None
        self.webserver: Optional[PiListenerWebServer] = None

        # Letztes Bild merken (für Persistenz)
        self.last_image_path: Optional[str] = None
        self.last_title: Optional[str] = None

        # Status
        self.running = True
        self.initialized = False
        self.trigger_cycle_now = False

        logger.info("=" * 50)
        logger.info("PiListener startet...")
        logger.info(f"Intervall: {self.interval_minutes} Min, Dauer: {self.listen_duration}s")
        logger.info("=" * 50)

    def _initialize_components(self) -> bool:
        """
        Initialisiert alle System-Komponenten.

        Returns:
            True wenn alle Komponenten erfolgreich initialisiert
        """
        try:
            # Audio Listener
            logger.info("Initialisiere Audio-Listener...")
            from src.listener import create_listener
            self.listener, self.stt_engine = create_listener()

            # Prüfe ob Jabra verbunden ist
            if not self.listener.is_device_connected():
                logger.warning("Audio-Device nicht verbunden, versuche weiter...")

            # Image Generator
            logger.info("Initialisiere Image-Generator...")
            self.image_generator = ImageGenerator.create_image_generator()

            # Display
            logger.info("Initialisiere Display...")
            self.display = DisplayManager.create_display()

            # Model Selector
            logger.info("Initialisiere Model-Selektor...")
            try:
                self.model_selector = get_model_selector()
                self.model_selector.update_model_list()
            except ValueError as e:
                logger.warning(f"Model-Selektor nicht verfügbar: {e}")

            # Webserver
            logger.info("Initialisiere Webserver...")
            try:
                self.webserver = PiListenerWebServer(pilistener_instance=self)
                self.webserver.start()
            except Exception as e:
                logger.warning(f"Webserver nicht verfügbar: {e}")

            self.initialized = True
            logger.info("Alle Komponenten initialisiert")
            return True

        except Exception as e:
            logger.error(f"Initialisierung fehlgeschlagen: {e}")
            return False

    def _wait_until_next_cycle(self) -> None:
        """
        Wartet bis zur nächsten vollen 15-Minuten-Markierung.
        """
        now = datetime.now()

        # Berechne nächste volle Intervall-Markierung
        minutes = (now.minute // self.interval_minutes + 1) * self.interval_minutes
        next_hour = now.hour

        if minutes >= 60:
            minutes = minutes % 60
            next_hour = (now.hour + 1) % 24

        next_cycle = now.replace(
            hour=next_hour,
            minute=minutes,
            second=0,
            microsecond=0
        )

        wait_seconds = (next_cycle - now).total_seconds()
        wait_seconds = max(0, wait_seconds)

        logger.debug(f"Warte bis {next_cycle.strftime('%H:%M:%S')} ({wait_seconds:.0f}s)")

        # Warte in kleinen Intervallen (für schnelles Shutdown)
        while wait_seconds > 0 and self.running:
            time.sleep(min(wait_seconds, 30))
            wait_seconds = (next_cycle - datetime.now()).total_seconds()

    def _run_cycle(self) -> bool:
        """
        Führt einen vollständigen Zyklus aus:
        Aufnahme -> STT -> Bildgenerierung -> Anzeige

        Returns:
            True wenn Zyklus erfolgreich
        """
        cycle_start = datetime.now()
        logger.info(f"Zyklus gestartet um {cycle_start.strftime('%H:%M:%S')}")

        try:
            # 1. Audio aufnehmen
            logger.info(f"Nehme {self.listen_duration}s Audio auf...")
            audio_data = self.listener.record(
                duration=self.listen_duration,
                threshold_db=self.silence_threshold
            )

            if audio_data is None:
                logger.warning("Stille erkannt oder Aufnahme fehlgeschlagen, überspringe...")
                return False

            logger.info(f"Audio aufgenommen: RMS={audio_data.rms_db:.1f}dB")

            # 2. STT Transkription
            logger.info("Starte STT-Transkription...")
            api_key = os.getenv("OPENROUTER_API_KEY")

            result = self.stt_engine.transcribe(audio_data, api_key)

            if not result.text or not result.text.strip():
                logger.warning("Kein Text transkribiert")
                return False

            prompt = result.text
            logger.info(f"Transkribiert: \"{prompt[:80]}...\"" if len(prompt) > 80 else f"Transkribiert: \"{prompt}\"")
            logger.info(f"STT Model: {result.model_used}")

            # 3. Bild generieren
            logger.info("Generiere Bild...")

            # Model-Auswahl
            if self.model_selector:
                model_id, provider = self.model_selector.get_best_image_model()
                logger.info(f"Verwende Image-Model: {model_id} ({provider})")
            else:
                model_id = "stabilityai/sdxl-turbo"
                provider = "openrouter"

            image_bytes = self.image_generator.generate(prompt, model_id)

            if image_bytes is None:
                logger.error("Bildgenerierung fehlgeschlagen")
                return False

            # 4. Bild speichern
            output_path = self.image_generator.save_image(
                image_bytes,
                prompt,
                output_dir="output"
            )

            if output_path is None:
                logger.error("Bild speichern fehlgeschlagen")
                return False

            # 5. Bild anzeigen
            logger.info("Zeige Bild auf Display...")

            # Erstelle Titel aus Prompt
            title = prompt[:100] if len(prompt) > 100 else prompt

            if self.display:
                self.display.show_image(output_path, title)
                self.last_image_path = output_path
                self.last_title = title

            # Log Erfolg
            cycle_duration = (datetime.now() - cycle_start).total_seconds()
            logger.info(f"Zyklus erfolgreich beendet in {cycle_duration:.1f}s")
            logger.info(f"Bild gespeichert: {output_path}")
            logger.info(f"Angezeigt auf Display")

            return True

        except Exception as e:
            logger.error(f"Fehler im Zyklus: {e}")
            return False

    def reload_config(self) -> None:
        """Lädt Konfiguration neu aus .env Datei."""
        load_dotenv("config/.env")
        self.interval_minutes = int(os.getenv("LISTEN_INTERVAL_MINUTES", "15"))
        self.listen_duration = int(os.getenv("LISTEN_DURATION_SECONDS", "20"))
        self.silence_threshold = float(os.getenv("SILENCE_THRESHOLD_DB", "30"))
        logger.info("Konfiguration neu geladen")

    def _show_welcome(self) -> None:
        """Zeigt ein Willkommens-Bild beim Start."""
        welcome_path = Path("output/welcome.jpg")
        if welcome_path.exists() and self.display:
            self.display.show_image(str(welcome_path), "PiListener bereit")
        elif self.display:
            # Zeige schwarzen Bildschirm mit Status
            self.display.clear()
            logger.info("Warte auf ersten Zyklus...")

    def run(self) -> None:
        """Hauptschleife - läuft bis SIGTERM/SIGINT."""
        # Komponenten initialisieren
        if not self._initialize_components():
            logger.error("Kritischer Fehler bei Initialisierung, beende...")
            sys.exit(1)

        # Signal-Handler für sauberes Shutdown
        def signal_handler(signum, frame):
            logger.info(f"Signal {signum} empfangen, fahre runter...")
            self.running = False

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

        # Zeige Willkommens-Bild
        self._show_welcome()

        logger.info("PiListener läuft im Hintergrund...")
        logger.info(f"Drücke Ctrl+C zum Beenden oder 'q' im Display-Modus")

        # Hauptschleife
        while self.running:
            # Prüfe ob sofortiger Zyklus gewünscht
            if self.trigger_cycle_now:
                logger.info("Sofortiger Zyklus über Webserver angefordert")
                self.trigger_cycle_now = False
                self._run_cycle()
            else:
                # Warte bis zum nächsten Zyklus
                self._wait_until_next_cycle()

            if not self.running:
                break

            # Führe Zyklus aus
            if not self.trigger_cycle_now:
                self._run_cycle()

        # Cleanup
        self._shutdown()

    def _shutdown(self) -> None:
        """Fährt das System sauber herunter."""
        logger.info("Fahre PiListener herunter...")

        if self.webserver:
            self.webserver.stop()

        if self.display:
            self.display.close()

        logger.info("PiListener beendet")


def main():
    """Entry-Point."""
    try:
        listener = PiListener()
        listener.run()
    except KeyboardInterrupt:
        print("\nPiListener interrupted by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
