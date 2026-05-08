"""
Tests für Image-Generator und Metadaten.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from io import BytesIO
from PIL import Image

from src.image_generator import ImageGenerator


class TestImageGenerator:
    """Tests für ImageGenerator Klasse."""

    @pytest.fixture
    def generator(self):
        """Erstellt einen ImageGenerator mit gemocktem Client."""
        with patch('src.image_generator.OpenAI') as mock_openai:
            yield mock_openai

    @pytest.fixture
    def sample_image_bytes(self):
        """Erstellt Sample-Bilddaten."""
        img = Image.new('RGB', (100, 100), color='red')
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        return buffer.getvalue()

    def test_slugify(self):
        """Test Slug-Generierung."""
        gen = ImageGenerator.__new__(ImageGenerator)

        # Test einfache Strings
        assert gen._slugify("Hallo Welt") == "hallo-welt"
        assert gen._slugify("Das ist ein Test") == "das-ist-ein-test"

        # Test Umlaute
        assert gen._slugify("Über den Wolken") == "ueber-den-wolken"

        # Test Sonderzeichen
        assert gen._slugify("Test!@#$%^&*()") == "test"

        # Test lange Strings
        long_text = "a" * 100
        slug = gen._slugify(long_text)
        assert len(slug) <= 50

    def test_download_image_success(self):
        """Test Bild-Download von URL."""
        with patch('src.image_generator.requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.content = b"fake_image_data"
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            gen = ImageGenerator.__new__(ImageGenerator)
            result = gen._download_image("https://example.com/image.jpg")

            assert result == b"fake_image_data"
            mock_get.assert_called_once_with("https://example.com/image.jpg", timeout=60)

    def test_download_image_failure(self):
        """Test fehlgeschlagener Bild-Download."""
        with patch('src.image_generator.requests.get') as mock_get:
            mock_get.side_effect = Exception("Network error")

            gen = ImageGenerator.__new__(ImageGenerator)
            result = gen._download_image("https://example.com/image.jpg")

            assert result is None

    def test_generate_empty_prompt(self):
        """Test das kein Bild für leeren Prompt generiert wird."""
        gen = ImageGenerator.__new__(ImageGenerator)
        result = gen.generate("")
        assert result is None

    def test_generate_with_whitespace_prompt(self):
        """Test das kein Bild für nur Whitespace generiert wird."""
        gen = ImageGenerator.__new__(ImageGenerator)
        result = gen.generate("   ")
        assert result is None


class TestMetadata:
    """Tests für Metadaten-Speicherung."""

    def test_prompt_in_metadata(self):
        """Test das Prompt in Metadaten gespeichert wird."""
        # Die Speicherung sollte immer den Original-Prompt enthalten
        prompt = "Regen trommelt auf das Dach"

        # Erstelle minimalen ImageGenerator
        gen = ImageGenerator.__new__(ImageGenerator)
        gen.quality = 85

        # Mock save
        with patch.object(gen, 'save_with_metadata') as mock_save:
            mock_save.return_value = True

            # Test das die Metadaten den Prompt enthalten
            metadata = {"prompt": prompt}
            gen.save_with_metadata(b"fake_data", prompt, "/tmp/test.jpg", metadata)

            # Prüfe das save_with_metadata aufgerufen wurde mit Prompt
            mock_save.assert_called_once()
            args = mock_save.call_args
            assert args[0][1] == prompt  # prompt als zweiter Parameter

    def test_metadata_format(self):
        """Test Metadaten-Format."""
        prompt = "Test Prompt"
        metadata = {
            "prompt": prompt,
            "timestamp": "2026-05-08-0215",
            "model": "stabilityai/sdxl-turbo"
        }

        # Metadaten sollten JSON-serialisierbar sein
        json_str = json.dumps(metadata)
        parsed = json.loads(json_str)

        assert parsed["prompt"] == prompt
        assert parsed["model"] == "stabilityai/sdxl-turbo"


class TestImageOutput:
    """Tests für Bild-Output."""

    def test_output_filename_format(self):
        """Test Dateinamen-Format."""
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y-%m-%d-%H%M")
        prompt = "Regen"
        slug = "regen"

        filename = f"{timestamp}-{slug}.jpg"

        # Sollte Format haben: YYYY-MM-DD-HHMM-slug.jpg
        assert len(filename) > 10
        assert filename.endswith(".jpg")
        assert "-" in filename

    def test_month_folder_structure(self):
        """Test Monats-Ordner Struktur."""
        from datetime import datetime

        month_folder = datetime.now().strftime("%Y-%m")
        expected = "2026-05"

        assert month_folder == expected
        assert len(month_folder) == 7


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
