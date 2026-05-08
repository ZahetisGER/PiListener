"""
Model-Selektor für PiListener
Dynamische Auswahl von kostenlosen STT- und Image-Modellen
"""

import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

import requests
from dotenv import load_dotenv

from src.logger import get_logger

logger = get_logger()

# OpenRouter API Endpoint für kostenlose Modelle
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
NVIDIA_MODELS_URL = "https://build.nvidia.com/api/inference/v1/models"

# Cache-Datei
CACHE_FILE = "config/.model_cache.json"
CACHE_DURATION_HOURS = 24


class ModelSelector:
    """Wählt dynamisch kostenlose Modelle aus."""

    def __init__(self, api_key: str):
        """
        Initialisiert den Model-Selektor.

        Args:
            api_key: OpenRouter API Key
        """
        self.api_key = api_key
        self.cache = self._load_cache()
        self.available_models = {"stt": [], "image": [], "reasoning": []}

    def _load_cache(self) -> Optional[Dict]:
        """Lädt gecachte Modelle aus der Cache-Datei."""
        cache_path = Path(CACHE_FILE)
        if cache_path.exists():
            try:
                with open(cache_path, 'r') as f:
                    cache = json.load(f)
                # Prüfe ob Cache noch valid ist
                cache_time = datetime.fromisoformat(cache.get("timestamp", "2000-01-01"))
                if datetime.now() - cache_time < timedelta(hours=CACHE_DURATION_HOURS):
                    logger.info("Model-Cache geladen (noch valid)")
                    return cache
                else:
                    logger.info("Model-Cache abgelaufen, wird neu geladen")
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"Cache defekt, neu laden: {e}")
        return None

    def _save_cache(self, cache: Dict) -> None:
        """Speichert Modelle im Cache."""
        cache_path = Path(CACHE_FILE)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache["timestamp"] = datetime.now().isoformat()
        try:
            with open(cache_path, 'w') as f:
                json.dump(cache, f, indent=2)
            logger.debug("Model-Cache gespeichert")
        except IOError as e:
            logger.warning(f"Cache konnte nicht gespeichert werden: {e}")

    def fetch_openrouter_models(self, free_only: bool = True) -> List[Dict]:
        """
        Holt verfügbare Modelle von OpenRouter.

        Args:
            free_only: Nur kostenlose Modelle holen

        Returns:
            Liste der Modelle
        """
        try:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            params = {"free": "true"} if free_only else {}

            response = requests.get(
                OPENROUTER_MODELS_URL,
                headers=headers,
                params=params,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            models = data.get("data", [])
            logger.info(f"{len(models)} Modelle von OpenRouter geladen")
            return models

        except requests.exceptions.RequestException as e:
            logger.error(f"OpenRouter API Fehler: {e}")
            return []

    def fetch_nvidia_models(self) -> List[Dict]:
        """
        Holt verfügbare kostenlose Modelle von NVIDIA.

        Returns:
            Liste der NVIDIA Modelle
        """
        try:
            response = requests.get(NVIDIA_MODELS_URL, timeout=30)
            response.raise_for_status()
            models = response.json()
            logger.info(f"{len(models)} Modelle von NVIDIA geladen")
            return models
        except requests.exceptions.RequestException as e:
            logger.warning(f"NVIDIA API nicht verfügbar: {e}")
            return []

    def _match_capabilities(self, model: Dict, task: str) -> bool:
        """
        Prüft ob ein Model eine bestimmte Capability hat.

        Args:
            model: Model-Dict von der API
            task: Task-Typ ('stt', 'image', 'reasoning')

        Returns:
            True wenn Model passt
        """
        capabilities = model.get("capabilities", [])
        if isinstance(capabilities, list):
            capabilities = " ".join(str(c).lower() for c in capabilities)
        else:
            capabilities = str(capabilities).lower()

        task_keywords = {
            "stt": ["speech-to-text", "whisper", "transcription", "audio"],
            "image": ["image-generation", "image generation", "image", "stable diffusion", "dall-e", "flux"],
            "reasoning": ["reasoning", "general", "chat"]
        }

        keywords = task_keywords.get(task, [])
        return any(kw.lower() in capabilities for kw in keywords)

    def _get_best_model(self, models: List[Dict], task: str) -> Optional[Dict]:
        """
        Wählt das beste Model basierend auf Reviews/Stars.

        Args:
            models: Liste der Modelle
            task: Task-Typ

        Returns:
            Das beste Model oder None
        """
        if not models:
            return None

        # Sortiere nachpopularität (reviews, stars, etc.)
        def get_score(m):
            # Versuche verschiedene Scoring-Methoden
            score = 0
            # Reviews/Sterne
            if "likes" in m:
                score += m.get("likes", 0) * 10
            if "rating" in m:
                score += m.get("rating", 0) * 5
            # bevorzuge bekannte Provider
            provider = m.get("provider", "").lower()
            if "openai" in provider:
                score += 20
            elif "anthropic" in provider:
                score += 15
            elif "meta" in provider:
                score += 10
            return score

        sorted_models = sorted(models, key=get_score, reverse=True)
        return sorted_models[0] if sorted_models else None

    def update_model_list(self, force: bool = False) -> bool:
        """
        Aktualisiert die Liste der verfügbaren Modelle.

        Args:
            force: Cache ignorieren und neu laden

        Returns:
            True wenn erfolgreich
        """
        if not force and self.cache:
            self.available_models = self.cache.get("models", {
                "stt": [], "image": [], "reasoning": []
            })
            return True

        all_models = []

        # OpenRouter Modelle holen
        openrouter_models = self.fetch_openrouter_models(free_only=True)
        all_models.extend([
            {**m, "source": "openrouter"} for m in openrouter_models
        ])

        # NVIDIA Modelle holen
        nvidia_models = self.fetch_nvidia_models()
        all_models.extend([
            {**m, "source": "nvidia"} for m in nvidia_models
        ])

        # Modelle nach Task filtern
        for task in ["stt", "image", "reasoning"]:
            matching = [
                m for m in all_models
                if self._match_capabilities(m, task)
            ]
            best = self._get_best_model(matching, task)
            self.available_models[task] = matching
            if best:
                logger.info(f"Bestes {task}-Model: {best.get('name', 'unbekannt')} von {best.get('source')}")

        # Cache speichern
        self.cache = {"models": self.available_models}
        self._save_cache(self.cache)

        return True

    def get_best_stt_model(self) -> Tuple[str, str]:
        """
        Gibt das beste Speech-to-Text Model zurück.

        Returns:
            Tuple von (model_id, provider)
        """
        # Für STT bevorzugen wir lokales Whisper (faster-whisper)
        # Da es kostenlos ist und offline funktioniert
        logger.debug("STT: Bevorzuge lokales faster-whisper")
        return ("faster-whisper", "local")

    def get_best_image_model(self) -> Tuple[str, str]:
        """
        Gibt das beste Image-Generation Model zurück.

        Returns:
            Tuple von (model_id, provider)
        """
        self.update_model_list()

        image_models = self.available_models.get("image", [])

        # NVIDIA Modelle bevorzugen (oft kostenlos mit Quota)
        nvidia_models = [m for m in image_models if m.get("source") == "nvidia"]
        if nvidia_models:
            best = self._get_best_model(nvidia_models, "image")
            if best:
                return (best.get("id", best.get("name", "")), "nvidia")

        # Dann OpenRouter
        openrouter_models = [m for m in image_models if m.get("source") == "openrouter"]
        if openrouter_models:
            best = self._get_best_model(openrouter_models, "image")
            if best:
                return (best.get("id", best.get("name", "")), "openrouter")

        # Fallback zu bekanntem kostenlosem Model
        logger.warning("Kein kostenloses Image-Model gefunden, verwende Fallback")
        return ("stabilityai/sdxl-turbo", "openrouter")

    def get_model_info(self, task: str) -> Dict:
        """
        Gibt Informationen über das beste Model für einen Task.

        Args:
            task: Task-Typ ('stt', 'image', 'reasoning')

        Returns:
            Dict mit Model-Informationen
        """
        models = self.available_models.get(task, [])
        best = self._get_best_model(models, task) if models else {}

        return {
            "task": task,
            "model": best.get("id", best.get("name", "unknown")),
            "provider": best.get("source", "unknown"),
            "name": best.get("name", best.get("id", "Unknown Model")),
            "context_length": best.get("context_length", best.get("contextWindow", 0)),
            "description": best.get("description", "")
        }


def get_model_selector() -> ModelSelector:
    """
    Factory-Function für ModelSelector.

    Returns:
        Konfigurierter ModelSelector
    """
    load_dotenv("config/.env")
    api_key = os.getenv("OPENROUTER_API_KEY", "")

    if not api_key:
        raise ValueError("OPENROUTER_API_KEY nicht in config/.env gefunden")

    return ModelSelector(api_key)
