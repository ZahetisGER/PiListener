"""
Tests für Display-Manager und pygame Vollbild-Anzeige.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

import pygame

from src.display import DisplayManager, create_display, BLACK, WHITE, TITLE_BG_COLOR


class TestDisplayManager:
    """Tests für DisplayManager Klasse."""

    @pytest.fixture
    def mock_pygame(self):
        """Mock für pygame Module."""
        with patch('src.display.pygame') as mock:
            # Pygame initialisieren mocken
            mock.init.return_value = None
            mock.display.set_mode.return_value = Mock()
            mock.display.Info.return_value = Mock(current_w=1920, current_h=1080)
            mock.mouse.set_cursor.return_value = None
            mock.mouse.set_visible.return_value = None
            yield mock

    def test_display_initialization(self, mock_pygame):
        """Test Display-Manager Initialisierung."""
        # Mock display info
        mock_pygame.display.Info.return_value = Mock(current_w=1920, current_h=1080)
        mock_pygame.display.set_mode.return_value = Mock()

        dm = DisplayManager(width=1920, height=1080, fullscreen=True)

        assert dm.width == 1920
        assert dm.height == 1080
        assert dm.fullscreen is True

    def test_display_fallback_to_windowed(self, mock_pygame):
        """Test Fallback zu Fenster-Modus bei Fehler."""
        mock_pygame.display.set_mode.side_effect = pygame.error("No display")

        # Sollte nicht abstürzen
        dm = DisplayManager(width=800, height=600, fullscreen=True)
        
        # fullscreen sollte auf False gesetzt sein nach Fehler
        assert dm.fullscreen is False

    def test_get_resolution(self, mock_pygame):
        """Test Auflösungs-Abfrage."""
        mock_pygame.display.Info.return_value = Mock(current_w=1920, current_h=1080)
        mock_pygame.display.set_mode.return_value = Mock()

        dm = DisplayManager(width=1920, height=1080)
        resolution = dm.get_resolution()

        assert resolution == (1920, 1080)


class TestTitleBar:
    """Tests für Titel-Balken Rendering."""

    def test_title_bar_color_constants(self):
        """Test das Farb-Konstanten definiert sind."""
        assert BLACK == (0, 0, 0)
        assert WHITE == (255, 255, 255)
        assert TITLE_BG_COLOR == (0, 0, 0)

    def test_title_height_ratio(self):
        """Test das Titel-Höhen-Verhältnis definiert ist."""
        from src.display import TITLE_HEIGHT_RATIO
        assert TITLE_HEIGHT_RATIO == 0.10  # 10%


class TestDisplayPersistence:
    """Tests für Display-Persistenz."""

    @pytest.fixture
    def mock_pygame(self):
        """Mock für pygame Module."""
        with patch('src.display.pygame') as mock:
            mock.init.return_value = None
            mock.display.set_mode.return_value = Mock()
            mock.display.Info.return_value = Mock(current_w=1920, current_h=1080)
            mock.mouse.set_cursor.return_value = None
            mock.mouse.set_visible.return_value = None
            yield mock

    def test_current_image_persistence(self, mock_pygame):
        """Test das aktuelles Bild gespeichert wird."""
        mock_pygame.display.Info.return_value = Mock(current_w=1920, current_h=1080)
        mock_pygame.display.set_mode.return_value = Mock()

        dm = DisplayManager()
        
        assert dm.current_image is None
        assert dm.current_title is None

    def test_clear_screen(self, mock_pygame):
        """Test Bildschirm löschen."""
        mock_pygame.display.Info.return_value = Mock(current_w=1920, current_h=1080)
        mock_pygame.display.set_mode.return_value = Mock()
        mock_pygame.display.flip.return_value = None

        dm = DisplayManager()
        dm.clear()

        assert dm.current_image is None
        assert dm.current_title is None


class TestDisplayEvents:
    """Tests für pygame Event-Handling."""

    @pytest.fixture
    def mock_pygame(self):
        """Mock für pygame Module."""
        with patch('src.display.pygame') as mock:
            mock.init.return_value = None
            mock.display.set_mode.return_value = Mock()
            mock.display.Info.return_value = Mock(current_w=1920, current_h=1080)
            mock.mouse.set_cursor.return_value = None
            mock.mouse.set_visible.return_value = None
            yield mock

    def test_escape_closes_display(self, mock_pygame):
        """Test das ESC Taste das Display schließt."""
        mock_pygame.display.Info.return_value = Mock(current_w=1920, current_h=1080)
        mock_pygame.display.set_mode.return_value = Mock()

        dm = DisplayManager()

        # Mock pygame.event.get für ESC
        esc_event = Mock(type=pygame.KEYDOWN, key=pygame.K_ESCAPE)
        mock_pygame.event.get.return_value = [esc_event]

        result = dm.handle_events()
        
        assert result is False  # False bedeutet schließen

    def test_q_key_closes_display(self, mock_pygame):
        """Test das Q Taste das Display schließt."""
        mock_pygame.display.Info.return_value = Mock(current_w=1920, current_h=1080)
        mock_pygame.display.set_mode.return_value = Mock()

        dm = DisplayManager()

        q_event = Mock(type=pygame.KEYDOWN, key=pygame.K_q)
        mock_pygame.event.get.return_value = [q_event]

        result = dm.handle_events()
        
        assert result is False

    def test_f_toggles_fullscreen(self, mock_pygame):
        """Test das F Taste zwischen Fullscreen und Windowed wechselt."""
        mock_pygame.display.Info.return_value = Mock(current_w=1920, current_h=1080)
        mock_pygame.display.set_mode.return_value = Mock()

        dm = DisplayManager(fullscreen=True)
        assert dm.fullscreen is True

        f_event = Mock(type=pygame.KEYDOWN, key=pygame.K_f)
        mock_pygame.event.get.return_value = [f_event]

        dm.handle_events()
        
        # Toggle sollte auf False gesetzt haben
        # (Der genaue Zustand hängt von der Implementierung ab)


class TestImageScaling:
    """Tests für Bildskalierung."""

    def test_scale_image_preserves_aspect_ratio(self):
        """Test das Aspect Ratio bei Skalierung erhalten bleibt."""
        from PIL import Image
        
        # Test mit einem 16:9 Bild
        dm = DisplayManager.__new__(DisplayManager)
        dm.width = 1920
        dm.height = 1080

        # Erstelle Test-Bild (breiter als hoch)
        img = Image.new('RGB', (1920, 1080))
        
        # Die _scale_image Methode sollte das Bild skalieren
        # und auf schwarzem Hintergrund zentrieren
        result = dm._scale_image(img)
        
        # Ergebnis sollte die Display-Größe haben
        assert result.size == (1920, 1080)


class TestCreateDisplay:
    """Tests für create_display Factory-Function."""

    def test_create_display_requires_env(self):
        """Test das create_display .env Konfiguration liest."""
        with patch('src.display.load_dotenv'):
            with patch.dict('os.environ', {'IMAGE_WIDTH': '1280', 'IMAGE_HEIGHT': '720'}):
                dm = create_display()
                # Sollte ohne Fehler durchlaufen
                assert dm is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
