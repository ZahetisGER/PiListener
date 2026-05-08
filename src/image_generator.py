"""
Bildgenerierungs-Modul für PiListener
Generiert KI-Bilder basierend auf STT-Text via OpenRouter API
"""

import os
import json
import time
import tempfile
from pathlib import Path
from typing import Optional, Dict, Tuple
from datetime import datetime
from io import BytesIO

from PIL import Image, PngImagePlugin
import requests
from openai import OpenAI
from dotenv import load_dotenv

from src.logger import get_logger

logger = get_logger()

# OpenRouter API Endpoints
OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"


class ImageGenerator:
    """Generiert KI-Bilder basierend auf Text-Prompts."""

    def __init__(
        self,
        api_key: str,
        width: int = 1024,
        height: int = 1024,
        quality: int = 85
    ):
        """
        Initialisiert den Image Generator.

        Args:
            api_key: OpenRouter API Key
            width: Bildbreite in Pixel
            height: Bildhöhe in Pixel
            quality: JPEG-Qualität (1-100)
        """
        self.api_key = api_key
        self.width = width
        self.height = height
        self.quality = quality
        self.client = OpenAI(api_key=api_key, base_url=OPENROUTER_API_BASE)

        logger.info(f"ImageGenerator initialisiert: {width}x{height}, Qualität: {quality}")

    def generate(
        self,
        prompt: str,
        model: str = "stabilityai/sdxl-turbo"
    ) -> Optional[bytes]:
        """
        Generiert ein Bild basierend auf dem Prompt.

        Args:
            prompt: Text-Beschreibung für das Bild
            model: Zu verwendendes Model

        Returns:
            Bilddaten als Bytes oder None bei Fehler
        """
        if not prompt or not prompt.strip():
            logger.warning("Leerer Prompt, kein Bild generiert")
            return None

        # Prompt bereinigen und vorbereiten
        clean_prompt = prompt.strip()
        logger.info(f"Generiere Bild für: \"{clean_prompt[:50]}...\"" if len(clean_prompt) > 50 else f"Generiere Bild für: \"{clean_prompt}\"")

        try:
            # OpenRouter API Aufruf für Bildgenerierung
            response = self.client.images.generate(
                model=model,
                prompt=clean_prompt,
                size=f"{self.width}x{self.height}",
                quality="standard",
                response_format="b64_json"
            )

            # Base64 dekodieren
            if response.data and len(response.data) > 0:
                image_data = response.data[0].b64_json
                image_bytes = bytes.fromhex(image_data)

                logger.info(f"Bild generiert: {len(image_bytes)} bytes")
                return image_bytes

        except Exception as e:
            logger.error(f"Bildgenerierung fehlgeschlagen: {e}")

            # Versuche alternatives Model
            try:
                logger.info("Versuche alternatives Model...")
                alt_model = "anthropic/claude-3.5-sonnet"
                response = self.client.images.generate(
                    model=alt_model,
                    prompt=clean_prompt,
                    size=f"{self.width}x{self.height}"
                )

                if response.data and len(response.data) > 0:
                    url = response.data[0].url
                    image_bytes = self._download_image(url)
                    if image_bytes:
                        return image_bytes

            except Exception as e2:
                logger.error(f"Alternatives Model auch fehlgeschlagen: {e2}")

        return None

    def _download_image(self, url: str) -> Optional[bytes]:
        """
        Lädt ein Bild von einer URL herunter.

        Args:
            url: Bild-URL

        Returns:
            Bilddaten als Bytes oder None
        """
        try:
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            return response.content
        except requests.RequestException as e:
            logger.error(f"Bild-Download fehlgeschlagen: {e}")
            return None

    def save_with_metadata(
        self,
        image_bytes: bytes,
        prompt: str,
        output_path: str,
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        Speichert ein Bild mit Metadaten (EXIF/Prompt).

        Args:
            image_bytes: Bilddaten
            prompt: Original-Prompt
            output_path: Ziel-Pfad
            metadata: Zusätzliche Metadaten

        Returns:
            True wenn erfolgreich
        """
        try:
            # Öffne Bild mit PIL
            image = Image.open(BytesIO(image_bytes))

            # Konvertiere zu RGB falls nötig (für JPEG)
            if image.mode not in ('RGB', 'L'):
                image = image.convert('RGB')

            # Erstelle Metadaten
            pnginfo = PngImagePlugin.PngInfo()
            pnginfo.add_text("Prompt", prompt)
            pnginfo.add_text("Generated-By", "PiListener")
            pnginfo.add_text("Generated-At", datetime.now().isoformat())

            # Füge zusätzliche Metadaten hinzu
            if metadata:
                for key, value in metadata.items():
                    pnginfo.add_text(str(key), str(value))

            # Erstelle Output-Verzeichnis falls nötig
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

            # Speichere als PNG mit Metadaten
            if output_path.lower().endswith('.jpg') or output_path.lower().endswith('.jpeg'):
                # Für JPEG: Speichere erst als PNG temporär, dann konvertiere
                # (JPEG unterstützt keine Text-Metadaten nativ)
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                    temp_png = tmp.name

                image.save(temp_png, "PNG", pnginfo=pnginfo)

                # Konvertiere zu JPEG mit optimierter Größe
                image_jpg = Image.open(temp_png)
                if image_jpg.mode != 'RGB':
                    image_jpg = image_jpg.convert('RGB')
                image_jpg.save(output_path, "JPEG", quality=self.quality, optimize=True)

                # Füge JPEGComment für Prompt (EXIF Alternative)
                try:
                    # Speichere Prompt als Kommentar
                    from PIL import ImageDraw, ImageFont

                    # Zeichne kleinen Text unten links als "Watermark"
                    draw = ImageDraw.Draw(image_jpg)
                    width, height = image_jpg.size

                    # Schriftgröße dynamisch
                    font_size = max(12, min(width, height) // 40)

                    # Speichere Metadaten in APP14 Markern (bei JPEG)
                    # Dies ist eine einfache Methode - echte EXIF wäre complexer
                    # Hier speichern wir den Prompt in den Kommentar
                    image_jpg.info["prompt"] = prompt
                    image_jpg.save(output_path, "JPEG", quality=self.quality,
                                   optimize=True, comment=prompt.encode('utf-8'))

                except Exception as e:
                    logger.warning(f"Konnte Kommentar nicht speichern: {e}")
                    # Speichere trotzdem ohne Kommentar
                    image_jpg.save(output_path, "JPEG", quality=self.quality, optimize=True)

                # Lösche Temp-Datei
                try:
                    os.unlink(temp_png)
                except:
                    pass

            else:
                # Speichere als PNG mit vollständigen Metadaten
                image.save(output_path, "PNG", pnginfo=pnginfo)

            logger.info(f"Bild gespeichert: {output_path}")
            return True

        except Exception as e:
            logger.error(f"Fehler beim Speichern des Bildes: {e}")
            return False

    def save_image(
        self,
        image_bytes: bytes,
        prompt: str,
        output_dir: str = "output"
    ) -> Optional[str]:
        """
        Speichert ein Bild mit generiertem Dateinamen.

        Args:
            image_bytes: Bilddaten
            prompt: Original-Prompt
            output_dir: Output-Verzeichnis

        Returns:
            Pfad zur gespeicherten Datei oder None
        """
        # Generiere Dateinamen aus Prompt und Timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d-%H%M")
        slug = self._slugify(prompt)[:50]

        # Erstelle Monats-Unterordner
        month_folder = datetime.now().strftime("%Y-%m")
        output_path = Path(output_dir) / month_folder
        output_path.mkdir(parents=True, exist_ok=True)

        # Voller Pfad mit Extension
        filename = f"{timestamp}-{slug}.jpg"
        full_path = output_path / filename

        # Speichere mit Metadaten
        metadata = {
            "prompt": prompt,
            "timestamp": timestamp,
            "model": "stabilityai/sdxl-turbo"
        }

        if self.save_with_metadata(image_bytes, prompt, str(full_path), metadata):
            return str(full_path)

        return None

    def _slugify(self, text: str) -> str:
        """
        Erstellt einen URL-sicheren Slug aus einem Text.

        Args:
            text: Eingabe-Text

        Returns:
            Slug-String
        """
        import re

        # Ersetze Umlaute
        replacements = {
            'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'ß': 'ss',
            'Ä': 'Ae', 'Ö': 'Oe', 'Ü': 'Ue'
        }
        for char, replacement in replacements.items():
            text = text.replace(char, replacement)

        # Nur alphanumerisch, Bindestriche, Unterstriche
        slug = re.sub(r'[^a-zA-Z0-9\s-]', '', text)
        slug = re.sub(r'[\s]+', '-', slug)
        slug = slug.lower().strip('-')

        return slug


def create_image_generator() -> ImageGenerator:
    """
    Factory-Function für ImageGenerator.

    Returns:
        Konfigurierter ImageGenerator
    """
    load_dotenv("config/.env")

    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY nicht in config/.env gefunden")

    width = int(os.getenv("IMAGE_WIDTH", "1024"))
    height = int(os.getenv("IMAGE_HEIGHT", "1024"))
    quality = int(os.getenv("IMAGE_QUALITY", "85"))

    return ImageGenerator(
        api_key=api_key,
        width=width,
        height=height,
        quality=quality
    )
