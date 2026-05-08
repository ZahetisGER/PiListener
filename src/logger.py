"""
Logger-Modul für PiListener
Logging-Setup mit loguru, schreibt in logs/listener.log
"""

import sys
import os
from pathlib import Path
from loguru import logger


def setup_logger(log_file: str = "logs/listener.log", level: str = "INFO") -> None:
    """
    Konfiguriert den Logger für PiListener.

    Args:
        log_file: Pfad zur Log-Datei
        level: Log-Level (DEBUG, INFO, WARNING, ERROR)
    """
    # Entferne default stderr handler
    logger.remove()

    # Formatter für strukturierte Logs
    format_string = (
        "<green>[{time:YYYY-MM-DD HH:mm:ss}]</green> | "
        "<level>{level: <8}</level> | "
        "<level>{message}</level>"
    )

    # Console Output
    logger.add(
        sys.stderr,
        format=format_string,
        level=level,
        colorize=True
    )

    # File Output - rotates daily, keeps 7 days
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger.add(
        log_file,
        format=format_string,
        level=level,
        rotation="00:00",  # Midnight rotation
        retention="7 days",
        compression="zip",
        encoding="utf-8"
    )

    logger.info(f"Logger initialisiert. Level: {level}, Log-Datei: {log_file}")


def get_logger():
    """Gibt den konfigurierten Logger zurück."""
    return logger
