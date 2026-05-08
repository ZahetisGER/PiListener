"""
Webserver-Modul für PiListener
	Einfacher HTTP-Server für Status-Anzeige und Fernsteuerung
"""

import os
import json
import threading
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from dotenv import load_dotenv

from src.logger import get_logger

logger = get_logger()

# Server Konfiguration
DEFAULT_PORT = 8000
DEFAULT_HOST = "0.0.0.0"

# HTML Template für die Status-Seite
STATUS_TEMPLATE = """
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PiListener Status</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1a1a2e;
            color: #eee;
            margin: 0;
            padding: 20px;
            min-height: 100vh;
        }}
        .container {{
            max-width: 800px;
            margin: 0 auto;
        }}
        h1 {{
            color: #00d4ff;
            border-bottom: 2px solid #00d4ff;
            padding-bottom: 10px;
        }}
        .card {{
            background: #16213e;
            border-radius: 10px;
            padding: 20px;
            margin: 20px 0;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }}
        .status-ok {{ color: #00ff88; }}
        .status-warning {{ color: #ffaa00; }}
        .status-error {{ color: #ff4444; }}
        .info-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
        }}
        .info-item {{
            background: #0f3460;
            padding: 15px;
            border-radius: 8px;
        }}
        .info-label {{
            color: #888;
            font-size: 0.85em;
            margin-bottom: 5px;
        }}
        .info-value {{
            font-size: 1.2em;
            font-weight: bold;
        }}
        .btn {{
            display: inline-block;
            padding: 10px 20px;
            background: #00d4ff;
            color: #1a1a2e;
            text-decoration: none;
            border-radius: 5px;
            font-weight: bold;
            margin: 5px;
            cursor: pointer;
            border: none;
        }}
        .btn:hover {{ background: #00a8cc; }}
        .btn-danger {{ background: #ff4444; }}
        .btn-danger:hover {{ background: #cc0000; }}
        .latest-image {{
            max-width: 100%;
            border-radius: 10px;
            margin-top: 10px;
        }}
        .log-output {{
            background: #0d1117;
            padding: 15px;
            border-radius: 5px;
            font-family: monospace;
            font-size: 0.9em;
            max-height: 300px;
            overflow-y: auto;
            white-space: pre-wrap;
            word-wrap: break-word;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🎧 PiListener Status</h1>

        <div class="card">
            <h2>System Status</h2>
            <div class="info-grid">
                <div class="info-item">
                    <div class="info-label">Status</div>
                    <div class="info-value status-ok">● Aktiv</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Letzter Zyklus</div>
                    <div class="info-value">{last_cycle}</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Letztes Bild</div>
                    <div class="info-value">{image_count} Bilder</div>
                </div>
                <div class="info-item">
                    <div class="info-label">Intervall</div>
                    <div class="info-value">{interval} Min</div>
                </div>
            </div>
        </div>

        <div class="card">
            <h2>Letztes Bild</h2>
            {last_image_html}
            <p><small>Prompt: {last_prompt}</small></p>
        </div>

        <div class="card">
            <h2>Steuerung</h2>
            <a href="/trigger" class="btn">🔄 Zyklus jetzt starten</a>
            <a href="/reload" class="btn">🔃 Konfiguration neu laden</a>
            <a href="/shutdown" class="btn btn-danger" onclick="return confirm('Wirklich beenden?')">⏹️ System beenden</a>
        </div>

        <div class="card">
            <h2>Letzte Logs</h2>
            <div class="log-output">{logs}</div>
        </div>
    </div>
</body>
</html>
"""


class PiListenerWebServer:
    """Einfacher Webserver für PiListener Status und Steuerung."""

    def __init__(
        self,
        port: int = DEFAULT_PORT,
        host: str = DEFAULT_HOST,
        pilistener_instance=None
    ):
        """
        Initialisiert den Webserver.

        Args:
            port: Port für den Server (Standard: 8000)
            host: Host für den Server (Standard: 0.0.0.0)
            pilistener_instance: Referenz auf PiListener-Instanz für Steuerung
        """
        self.port = port
        self.host = host
        self.pilistener = pilistener_instance
        self.server: Optional[HTTPServer] = None
        self.thread: Optional[threading.Thread] = None
        self.running = False

        logger.info(f"WebServer initialisiert: {host}:{port}")

    def start(self) -> bool:
        """
        Startet den Webserver in einem separaten Thread.

        Returns:
            True wenn erfolgreich gestartet
        """
        if self.running:
            logger.warning("WebServer läuft bereits")
            return False

        try:
            handler = self._create_handler()
            self.server = HTTPServer((self.host, self.port), handler)

            # Thread erstellen und starten
            self.thread = threading.Thread(target=self._run_server, daemon=True)
            self.thread.start()

            self.running = True
            logger.info(f"WebServer gestartet auf http://{self.host}:{self.port}")
            return True

        except Exception as e:
            logger.error(f"WebServer Start fehlgeschlagen: {e}")
            return False

    def _run_server(self) -> None:
        """Läuft den Server (in separatem Thread)."""
        try:
            self.server.serve_forever()
        except Exception as e:
            logger.error(f"WebServer Fehler: {e}")

    def stop(self) -> None:
        """Stoppt den Webserver."""
        if self.server and self.running:
            logger.info("WebServer wird gestoppt...")
            self.server.shutdown()
            self.running = False

    def _create_handler(self):
        """Erstellt einen Request-Handler mit Referenz auf dieses Server-Instanz."""

        class RequestHandler(BaseHTTPRequestHandler):
            """HTTP Request Handler für PiListener."""

            def log_message(self, format, *args):
                """Überschreibt default logging."""
                pass  # Kein Logging zu stderr

            def do_GET(self):
                """Behandelt GET-Requests."""
                parsed = urlparse(self.path)
                path = parsed.path

                if path == "/" or path == "/status":
                    self._send_status()
                elif path == "/trigger":
                    self._send_trigger()
                elif path == "/reload":
                    self._send_reload()
                elif path == "/shutdown":
                    self._send_shutdown()
                elif path == "/logs":
                    self._send_logs()
                elif path == "/images":
                    self._send_images_list()
                else:
                    self._send_error(404, "Nicht gefunden")

            def _send_status(self):
                """Sendet Status-Seite."""
                status = self._get_status_data()
                html = self._render_status_template(status)

                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(html.encode("utf-8"))

            def _send_trigger(self):
                """Triggert einen sofortigen Zyklus."""
                logger.info("WebServer: Trigger-Zyklus angefordert")

                if server.pilistener:
                    # Signalisiere sofortigen Zyklus
                    server.pilistener.trigger_cycle_now = True

                self.send_response(302)
                self.send_header("Location", "/status")
                self.end_headers()

            def _send_reload(self):
                """Lädt Konfiguration neu."""
                logger.info("WebServer: Konfiguration neu laden")

                if server.pilistener:
                    server.pilistener.reload_config()

                self.send_response(302)
                self.send_header("Location", "/status")
                self.end_headers()

            def _send_shutdown(self):
                """Fährt das System herunter."""
                logger.info("WebServer: Shutdown angefordert")

                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(b"<html><body>System wird beendet...</body></html>")

                # Trigger shutdown
                if server.pilistener:
                    server.pilistener.running = False

            def _send_logs(self):
                """Sendet Log-Informationen als JSON."""
                logs = self._get_recent_logs()

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(json.dumps(logs, ensure_ascii=False).encode("utf-8"))

            def _send_images_list(self):
                """Sendet Liste der letzten Bilder als JSON."""
                images = self._get_images_list()

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(json.dumps(images, ensure_ascii=False).encode("utf-8"))

            def _send_error(self, code: int, message: str):
                """Sendet Fehlerseite."""
                self.send_response(code)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(f"<html><body><h1>{code} - {message}</h1></body></html>".encode())

            def _get_status_data(self) -> Dict[str, Any]:
                """Sammelt Status-Daten."""
                data = {
                    "running": True,
                    "last_cycle": "Unbekannt",
                    "image_count": 0,
                    "interval": 15,
                    "last_image": None,
                    "last_prompt": ""
                }

                # Versuche Daten vom PiListener zu bekommen
                if server.pilistener:
                    data["running"] = server.pilistener.running

                    if hasattr(server.pilistener, 'last_image_path') and server.pilistener.last_image_path:
                        data["last_image"] = server.pilistener.last_image_path
                        data["last_prompt"] = server.pilistener.last_title or ""

                    if hasattr(server.pilistener, 'interval_minutes'):
                        data["interval"] = server.pilistener.interval_minutes

                # Zähle Bilder im Output-Verzeichnis
                output_dir = Path("output")
                if output_dir.exists():
                    jpg_files = list(output_dir.rglob("*.jpg")) + list(output_dir.rglob("*.png"))
                    data["image_count"] = len(jpg_files)

                # Letzte Log-Zeit als Proxy für letzten Zyklus
                log_file = Path("logs/listener.log")
                if log_file.exists():
                    try:
                        with open(log_file, 'r') as f:
                            lines = f.readlines()
                            if lines:
                                # Versuche Zeit aus letzter Zeile zu extrahieren
                                for line in reversed(lines):
                                    if "Zyklus" in line or "beendet" in line:
                                        parts = line.split("]")
                                        if len(parts) > 1:
                                            data["last_cycle"] = parts[1].split("|")[0].strip()
                                            break
                    except Exception:
                        pass

                return data

            def _render_status_template(self, data: Dict) -> str:
                """Rendert das Status-HTML-Template."""

                # Letztes Bild HTML
                if data.get("last_image"):
                    image_url = f"/output/{Path(data['last_image']).name}"
                    last_image_html = f'<img src="{image_url}" class="latest-image" alt="Letztes Bild">'
                else:
                    last_image_html = "<p>Noch kein Bild generiert.</p>"

                # Logs abrufen
                logs = self._get_recent_logs_text()

                return STATUS_TEMPLATE.format(
                    last_cycle=data.get("last_cycle", "Unbekannt"),
                    image_count=data.get("image_count", 0),
                    interval=data.get("interval", 15),
                    last_image_html=last_image_html,
                    last_prompt=data.get("last_prompt", "")[:200],
                    logs=logs
                )

            def _get_recent_logs(self, lines: int = 50) -> list:
                """Liest letzte Log-Einträge."""
                log_file = Path("logs/listener.log")
                result = []

                if log_file.exists():
                    try:
                        with open(log_file, 'r') as f:
                            all_lines = f.readlines()
                            result = [line.strip() for line in all_lines[-lines:]]
                    except Exception as e:
                        result = [f"Fehler beim Lesen der Logs: {e}"]

                return result

            def _get_recent_logs_text(self, lines: int = 20) -> str:
                """Liest letzte Logs als Text."""
                logs = self._get_recent_logs(lines)
                return "\n".join(logs[-20:]) if logs else "Keine Logs verfügbar."

            def _get_images_list(self) -> list:
                """Gibt Liste der letzten Bilder zurück."""
                output_dir = Path("output")
                images = []

                if output_dir.exists():
                    for f in sorted(output_dir.rglob("*.jpg")) + sorted(output_dir.rglob("*.png")):
                        if f.is_file():
                            images.append({
                                "name": f.name,
                                "path": str(f),
                                "size": f.stat().st_size,
                                "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat()
                            })

                return images[-10:]  # Nur letzte 10

        # Closure: Referenz auf server-Instanz
        server = self
        return RequestHandler


def create_webserver(pilistener_instance=None, port: int = None) -> PiListenerWebServer:
    """
    Factory-Function für WebServer.

    Args:
        pilistener_instance: PiListener-Instanz für Steuerung
        port: Optionaler Port (aus .env wenn nicht angegeben)

    Returns:
        Konfigurierter PiListenerWebServer
    """
    load_dotenv("config/.env")

    if port is None:
        port = int(os.getenv("WEB_PORT", str(DEFAULT_PORT)))

    host = os.getenv("WEB_HOST", DEFAULT_HOST)

    return PiListenerWebServer(
        port=port,
        host=host,
        pilistener_instance=pilistener_instance
    )
