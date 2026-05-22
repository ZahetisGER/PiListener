"""
Display-Modul für PiListener
Vollbild-Anzeige von generierten Bildern mit pygame
"""

import os
import sys
from pathlib import Path
from typing import Optional, Tuple

import pygame
from PIL import Image
from dotenv import load_dotenv

from src.logger import get_logger

logger = get_logger()

# Farben
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
TITLE_BG_COLOR = (0, 0, 0)  # Schwarz
TITLE_TEXT_COLOR = (255, 255, 255)  # Weiß
TITLE_HEIGHT_RATIO = 0.10  # 10% der Bildschirmhöhe
TITLE_PADDING = 20  # Pixel Abstand


class DisplayManager:
    """Verwaltet die Vollbild-Anzeige mit pygame."""

    def __init__(
        self,
        width: Optional[int] = None,
        height: Optional[int] = None,
        fullscreen: bool = True
    ):
        """
        Initialisiert den Display-Manager.

        Args:
            width: Breite in Pixel (None = native Auflösung)
            height: Höhe in Pixel (None = native Auflösung)
            fullscreen: Im Vollbild-Modus starten
        """
        # Pygame initialisieren
        pygame.init()
        pygame.mouse.set_cursor(False)  # Cursor verstecken

        # Lade Konfiguration falls nicht übergeben
        if width is None or height is None:
            load_dotenv("config/.env")
            width = int(os.getenv("IMAGE_WIDTH", "0"))
            height = int(os.getenv("IMAGE_HEIGHT", "0"))

        # Display Info holen
        info = pygame.display.Info()
        self.native_width = info.current_w
        self.native_height = info.current_h

        # Verwende native Auflösung wenn nicht explizit angegeben
        if width == 0:
            width = self.native_width
        if height == 0:
            height = self.native_height

        self.width = width
        self.height = height
        self.fullscreen = fullscreen

        # Display Modus setzen
        self._setup_display()

        # Aktuelles Bild und Titel
        self.current_image: Optional[pygame.Surface] = None
        self.current_title: Optional[str] = None

        logger.info(f"Display initialisiert: {width}x{height}, Fullscreen: {fullscreen}")

    def _setup_display(self) -> None:
        """Konfiguriert den Pygame-Display-Modus."""
        try:
            if self.fullscreen:
                self.screen = pygame.display.set_mode(
                    (self.width, self.height),
                    pygame.FULLSCREEN | pygame.HWACCEL
                )
            else:
                self.screen = pygame.display.set_mode(
                    (self.width, self.height),
                    pygame.HWACCEL
                )

            # Verstecke Cursor
            pygame.mouse.set_visible(False)

        except pygame.error as e:
            logger.error(f"Display-Setup fehlgeschlagen: {e}")
            # Fallback zu Fenster-Modus
            logger.warning("Fall back to windowed mode - fullscreen not available")
            self.fullscreen = False
            self.screen = pygame.display.set_mode((self.width, self.height))

    def _load_image(self, image_path: str) -> Optional[pygame.Surface]:
        """
        Lädt ein Bild und skaliert es für das Display.

        Args:
            image_path: Pfad zum Bild

        Returns:
            Skalierte pygame.Surface oder None
        """
        try:
            # Lade Bild mit PIL
            pil_image = Image.open(image_path)

            # Konvertiere zu RGB falls nötig
            if pil_image.mode != 'RGB':
                pil_image = pil_image.convert('RGB')

            # Skaliere auf Display-Größe (aspect-ratio erhalten)
            scaled = self._scale_image(pil_image)

            # Konvertiere zu pygame Surface
            pygame_image = pygame.image.fromstring(
                scaled.tobytes(),
                scaled.size,
                'RGB'
            )

            return pygame_image

        except Exception as e:
            logger.error(f"Bild laden fehlgeschlagen: {e}")
            return None

    def _scale_image(self, image: Image.Image) -> Image.Image:
        """
        Skaliert ein Bild auf die Display-Größe.

        Behält Aspect Ratio bei, zentriert auf schwarzem Hintergrund.

        Args:
            image: PIL Image

        Returns:
            Skaliertes PIL Image
        """
        img_width, img_height = image.size
        display_width, display_height = self.width, self.height

        # Berechne Skalierungsfaktor
        scale_w = display_width / img_width
        scale_h = display_height / img_height
        scale = min(scale_w, scale_h)  # Min um整个 Bild zu zeigen

        # Neue Größe
        new_width = int(img_width * scale)
        new_height = int(img_height * scale)

        # Skaliere
        scaled = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # Erstelle schwarzes Hintergrund-Bild
        result = Image.new('RGB', (display_width, display_height), BLACK)

        # Zentriere das skalierte Bild
        x_offset = (display_width - new_width) // 2
        y_offset = (display_height - new_height) // 2

        result.paste(scaled, (x_offset, y_offset))

        return result

    def _draw_title_bar(self, title: str) -> None:
        """
        Zeichnet den Titel-Balken am unteren Rand des Bildschirms.

        Args:
            title: Titel-Text
        """
        if not title:
            return

        # Berechne Höhe des Titelbalkens
        title_height = int(self.height * TITLE_HEIGHT_RATIO)
        title_y = self.height - title_height

        # Hintergrund-Rechteck zeichnen
        pygame.draw.rect(
            self.screen,
            TITLE_BG_COLOR,
            (0, title_y, self.width, title_height)
        )

        # Linie oben (leichte Abgrenzung)
        pygame.draw.line(
            self.screen,
            (50, 50, 50),  # Dunkelgrau
            (0, title_y),
            (self.width, title_y),
            2
        )

        # Font auswählen (dynamische Größe)
        # Versuche erst System-Font, dann Default
        try:
            # Berechne Font-Größe basierend auf Textlänge
            max_width = self.width - (2 * TITLE_PADDING)
            font_size = title_height // 2

            # Probiere verschiedene Fonts
            font = None
            for font_name in ['DejaVu Sans', 'Liberation Sans', 'Arial', 'sans-serif']:
                try:
                    font = pygame.font.SysFont(font_name, font_size)
                    break
                except:
                    continue

            if font is None:
                font = pygame.font.Font(None, font_size)

        except:
            font = pygame.font.Font(None, int(title_height * 0.4))

        # Text rendern (mehrzeilig falls nötig)
        words = title.split()
        lines = []
        current_line = []

        for word in words:
            test_line = ' '.join(current_line + [word])
            if font.size(test_line)[0] <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
        if current_line:
            lines.append(' '.join(current_line))

        # Zeichne Text-Zeilen (von unten nach oben)
        line_height = font.get_height()
        y_offset = title_y + title_height - TITLE_PADDING - line_height

        for line in lines[:2]:  # Max 2 Zeilen
            text_surface = font.render(line, True, TITLE_TEXT_COLOR)
            self.screen.blit(text_surface, (TITLE_PADDING, y_offset))
            y_offset -= line_height + 5

    def show_image(self, image_path: str, title: Optional[str] = None) -> bool:
        """
        Zeigt ein Bild im Vollbild-Modus an.

        Args:
            image_path: Pfad zum Bild
            title: Optionaler Titel für den unteren Balken

        Returns:
            True wenn erfolgreich
        """
        try:
            pygame_image = None

            # Wenn kein neuer Pfad angegeben, aber ein Bild gespeichert ist
            if not image_path and self.current_image is not None:
                pygame_image = self.current_image
            else:
                # Lade und skaliere Bild
                pygame_image = self._load_image(image_path)
                if pygame_image is None:
                    return False

            # Lösche Screen
            self.screen.fill(BLACK)

            # Zeichne Bild (zentriert)
            img_rect = pygame_image.get_rect(center=self.screen.get_rect().center)
            self.screen.blit(pygame_image, img_rect)

            # Zeichne Titel-Balken falls vorhanden
            if title is None and self.current_title:
                title = self.current_title
            if title:
                self._draw_title_bar(title)

            # Update Display
            pygame.display.flip()

            # Aktuelles merken
            self.current_image = pygame_image
            if title:
                self.current_title = title

            logger.debug(f"Bild angezeigt: {image_path}")
            return True

        except Exception as e:
            logger.error(f"Bild anzeigen fehlgeschlagen: {e}")
            return False

    def clear(self) -> None:
        """Löscht den Bildschirm (schwarz)."""
        self.screen.fill(BLACK)
        pygame.display.flip()
        self.current_image = None
        self.current_title = None

    def is_fullscreen(self) -> bool:
        """Prüft ob Display im Vollbild-Modus ist."""
        return self.fullscreen

    def get_resolution(self) -> Tuple[int, int]:
        """Gibt die aktuelle Auflösung zurück."""
        return (self.width, self.height)

    def toggle_fullscreen(self) -> None:
        """Wechselt zwischen Vollbild und Fenster-Modus."""
        self.fullscreen = not self.fullscreen
        self._setup_display()

        # Zeige aktuelles Bild erneut falls vorhanden
        if self.current_image:
            self.show_image("", self.current_title)  # Aktuelles Bild neu zeichnen

    def handle_events(self) -> bool:
        """
        Verarbeitet pygame-Events.

        Returns:
            False wenn quit/ESC gedrückt, True sonst
        """
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False
                elif event.key == pygame.K_f:
                    self.toggle_fullscreen()
                elif event.key == pygame.K_q:
                    return False

        return True

    def wait_for_key(self, timeout: Optional[int] = None) -> bool:
        """
        Wartet auf Taste oder Timeout.

        Args:
            timeout: Timeout in Sekunden (None = endlos)

        Returns:
            False bei ESC oder timeout, True sonst
        """
        try:
            if timeout:
                pygame.time.wait(timeout * 1000)
            else:
                # Warte auf Event
                while True:
                    event = pygame.event.wait()
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_ESCAPE:
                            return False
                    elif event.type == pygame.QUIT:
                        return False

        except KeyboardInterrupt:
            return False

        return True

    def close(self) -> None:
        """Schließt das Display und räumt auf."""
        pygame.quit()
        logger.info("Display geschlossen")


def create_display() -> DisplayManager:
    """
    Factory-Function für DisplayManager.

    Returns:
        Konfigurierter DisplayManager
    """
    load_dotenv("config/.env")

    width = int(os.getenv("IMAGE_WIDTH", "0"))
    height = int(os.getenv("IMAGE_HEIGHT", "0"))
    fullscreen = os.getenv("FULLSCREEN", "true").lower() == "true"

    return DisplayManager(width=width, height=height, fullscreen=fullscreen)
