"""
Gallery Server für PiListener
Statisches HTTP Serve der generierten Bilder mit Metadaten
Läuft auf Port 8888 im LAN
"""

import os
import json
import mimetypes
from pathlib import Path
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Optional, List, Dict, Any
from threading import Thread

from src.logger import get_logger

logger = get_logger()

DEFAULT_PORT = 8888
DEFAULT_HOST = "0.0.0.0"
OUTPUT_DIR = "output"

# HTML Template für die Gallery
GALLERY_HTML = """
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PiListener Gallery</title>
    <style>
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0a0a0f;
            color: #eee;
            min-height: 100vh;
        }}
        header {{
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            padding: 20px 30px;
            border-bottom: 2px solid #00d4ff;
        }}
        h1 {{
            color: #00d4ff;
            font-size: 1.8em;
            margin-bottom: 5px;
        }}
        .subtitle {{
            color: #888;
            font-size: 0.9em;
        }}
        .stats {{
            display: flex;
            gap: 30px;
            margin-top: 15px;
            flex-wrap: wrap;
        }}
        .stat {{
            background: rgba(0,212,255,0.1);
            padding: 10px 20px;
            border-radius: 8px;
        }}
        .stat-value {{
            font-size: 1.5em;
            font-weight: bold;
            color: #00d4ff;
        }}
        .stat-label {{
            font-size: 0.75em;
            color: #888;
            text-transform: uppercase;
        }}
        .filters {{
            padding: 20px 30px;
            background: #12121a;
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
            align-items: center;
        }}
        .filter-label {{
            color: #888;
            font-size: 0.85em;
        }}
        select, input {{
            background: #1a1a2e;
            color: #eee;
            border: 1px solid #333;
            padding: 8px 15px;
            border-radius: 5px;
            font-size: 0.9em;
        }}
        select:focus, input:focus {{
            outline: none;
            border-color: #00d4ff;
        }}
        .gallery {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 20px;
            padding: 30px;
        }}
        .card {{
            background: #1a1a2e;
            border-radius: 12px;
            overflow: hidden;
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        .card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 10px 30px rgba(0,212,255,0.2);
        }}
        .card-image {{
            width: 100%;
            aspect-ratio: 16/9;
            object-fit: cover;
            cursor: pointer;
        }}
        .card-content {{
            padding: 15px;
        }}
        .card-title {{
            font-size: 0.95em;
            color: #ccc;
            margin-bottom: 10px;
            line-height: 1.4;
            max-height: 2.8em;
            overflow: hidden;
        }}
        .card-meta {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
            font-size: 0.8em;
            color: #666;
        }}
        .card-meta span {{
            background: #12121a;
            padding: 5px 10px;
            border-radius: 4px;
        }}
        .card-prompt {{
            margin-top: 10px;
            font-size: 0.8em;
            color: #555;
            max-height: 3em;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        .lightbox {{
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.95);
            z-index: 1000;
            justify-content: center;
            align-items: center;
            flex-direction: column;
        }}
        .lightbox.active {{
            display: flex;
        }}
        .lightbox img {{
            max-width: 90%;
            max-height: 80vh;
            border-radius: 8px;
            box-shadow: 0 0 50px rgba(0,212,255,0.3);
        }}
        .lightbox-info {{
            margin-top: 20px;
            text-align: center;
            max-width: 800px;
        }}
        .lightbox-title {{
            font-size: 1.3em;
            color: #00d4ff;
            margin-bottom: 10px;
        }}
        .lightbox-prompt {{
            color: #888;
            font-size: 0.95em;
            margin-bottom: 15px;
        }}
        .lightbox-meta {{
            display: flex;
            gap: 20px;
            justify-content: center;
            flex-wrap: wrap;
        }}
        .lightbox-meta span {{
            background: #1a1a2e;
            padding: 8px 15px;
            border-radius: 20px;
            font-size: 0.85em;
        }}
        .lightbox-close {{
            position: absolute;
            top: 20px;
            right: 30px;
            font-size: 2em;
            color: #666;
            cursor: pointer;
            transition: color 0.2s;
        }}
        .lightbox-close:hover {{
            color: #00d4ff;
        }}
        .lightbox-nav {{
            position: absolute;
            top: 50%;
            transform: translateY(-50%);
            font-size: 3em;
            color: #666;
            cursor: pointer;
            padding: 20px;
            transition: color 0.2s;
        }}
        .lightbox-nav:hover {{
            color: #00d4ff;
        }}
        .lightbox-prev {{
            left: 10px;
        }}
        .lightbox-next {{
            right: 10px;
        }}
        .loading {{
            text-align: center;
            padding: 50px;
            color: #666;
        }}
        .no-images {{
            text-align: center;
            padding: 100px;
            color: #444;
            font-size: 1.2em;
        }}
        .no-images span {{
            display: block;
            font-size: 3em;
            margin-bottom: 20px;
        }}
        @media (max-width: 768px) {{
            .gallery {{
                grid-template-columns: 1fr;
                padding: 15px;
            }}
            .stats {{
                gap: 15px;
            }}
            .filters {{
                padding: 15px;
            }}
        }}
    </style>
</head>
<body>
    <header>
        <h1>🎨 PiListener Gallery</h1>
        <div class="subtitle">KI-generierte Bilder aus Audio-Aufnahmen</div>
        <div class="stats">
            <div class="stat">
                <div class="stat-value" id="total-count">{total_count}</div>
                <div class="stat-label">Bilder</div>
            </div>
            <div class="stat">
                <div class="stat-value" id="date-range">{date_range}</div>
                <div class="stat-label">Zeitraum</div>
            </div>
            <div class="stat">
                <div class="stat-value">{latest_count}</div>
                <div class="stat-label">Diesen Monat</div>
            </div>
        </div>
    </header>

    <div class="filters">
        <span class="filter-label">Monat:</span>
        <select id="filter-month">
            <option value="">Alle</option>
            {month_options}
        </select>

        <span class="filter-label">Jahr:</span>
        <select id="filter-year">
            <option value="">Alle</option>
            {year_options}
        </select>

        <span class="filter-label">Suche:</span>
        <input type="text" id="filter-search" placeholder="Prompt durchsuchen...">

        <button onclick="clearFilters()" style="background:#333;border:none;color:#888;padding:8px 15px;border-radius:5px;cursor:pointer;">Reset</button>
    </div>

    <div class="gallery" id="gallery">
        {gallery_cards}
    </div>

    <div class="lightbox" id="lightbox">
        <span class="lightbox-close" onclick="closeLightbox()">×</span>
        <span class="lightbox-nav lightbox-prev" onclick="navigate(-1)">‹</span>
        <span class="lightbox-nav lightbox-next" onclick="navigate(1)">›</span>
        <img id="lightbox-img" src="" alt="">
        <div class="lightbox-info">
            <div class="lightbox-title" id="lightbox-title"></div>
            <div class="lightbox-prompt" id="lightbox-prompt"></div>
            <div class="lightbox-meta" id="lightbox-meta"></div>
        </div>
    </div>

    <script>
        let images = {images_json};
        let currentIndex = 0;

        function openLightbox(index) {{
            currentIndex = index;
            showImage(index);
            document.getElementById('lightbox').classList.add('active');
        }}

        function closeLightbox() {{
            document.getElementById('lightbox').classList.remove('active');
        }}

        function showImage(index) {{
            let img = images[index];
            document.getElementById('lightbox-img').src = img.path;
            document.getElementById('lightbox-title').textContent = img.title;
            document.getElementById('lightbox-prompt').textContent = img.prompt;
            document.getElementById('lightbox-meta').innerHTML =
                `<span>📅 {img.date_formatted}</span>` +
                `<span>⏰ {img.time_formatted}</span>` +
                `<span>🔊 {img.rms_db} dB</span>` +
                `<span>🤖 {img.model}</span>`;
        }}

        function navigate(direction) {{
            currentIndex = (currentIndex + direction + images.length) % images.length;
            showImage(currentIndex);
        }}

        function clearFilters() {{
            document.getElementById('filter-month').value = '';
            document.getElementById('filter-year').value = '';
            document.getElementById('filter-search').value = '';
            filterImages();
        }}

        function filterImages() {{
            let month = document.getElementById('filter-month').value;
            let year = document.getElementById('filter-year').value;
            let search = document.getElementById('filter-search').value.toLowerCase();

            let filtered = images.filter(img => {{
                if (month && img.month !== month) return false;
                if (year && img.year !== year) return false;
                if (search && !img.prompt.toLowerCase().includes(search)) return false;
                return true;
            }});

            renderGallery(filtered);
        }}

        function renderGallery(imgs) {{
            let gallery = document.getElementById('gallery');
            if (imgs.length === 0) {{
                gallery.innerHTML = '<div class="no-images"><span>🖼️</span>Keine Bilder gefunden</div>';
                return;
            }}

            gallery.innerHTML = imgs.map((img, i) => `
                <div class="card" onclick="openLightbox(images.indexOf(img))">
                    <img class="card-image" src="${{img.path}}" alt="${{img.title}}" loading="lazy">
                    <div class="card-content">
                        <div class="card-title">${{img.title}}</div>
                        <div class="card-meta">
                            <span>📅 ${{img.date_formatted}}</span>
                            <span>⏰ ${{img.time_formatted}}</span>
                        </div>
                        <div class="card-prompt">${{img.prompt.substring(0, 80)}}...</div>
                    </div>
                </div>
            `).join('');
        }}

        document.getElementById('filter-month').addEventListener('change', filterImages);
        document.getElementById('filter-year').addEventListener('change', filterImages);
        document.getElementById('filter-search').addEventListener('input', filterImages);

        document.addEventListener('keydown', (e) => {{
            if (!document.getElementById('lightbox').classList.contains('active')) return;
            if (e.key === 'Escape') closeLightbox();
            if (e.key === 'ArrowLeft') navigate(-1);
            if (e.key === 'ArrowRight') navigate(1);
        }});

        document.getElementById('lightbox').addEventListener('click', (e) => {{
            if (e.target.id === 'lightbox') closeLightbox();
        }});
    </script>
</body>
</html>
"""


class GalleryServer:
    """HTTP Gallery Server für PiListener Bilder."""

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, output_dir: str = OUTPUT_DIR):
        """
        Initialisiert den Gallery Server.

        Args:
            host: Host für den Server (Standard: 0.0.0.0 für LAN Zugriff)
            port: Port für den Server (Standard: 8888)
            output_dir: Verzeichnis mit generierten Bildern
        """
        self.host = host
        self.port = port
        self.output_dir = Path(output_dir)
        self.server: Optional[HTTPServer] = None
        self.thread: Optional[Thread] = None
        self.running = False

        logger.info(f"Gallery Server initialisiert: {host}:{port}, Output: {output_dir}")

    def start(self) -> bool:
        """
        Startet den Gallery Server in einem separaten Thread.

        Returns:
            True wenn erfolgreich gestartet
        """
        if self.running:
            logger.warning("Gallery Server läuft bereits")
            return False

        try:
            handler = self._create_handler()
            self.server = HTTPServer((self.host, self.port), handler)
            self.thread = Thread(target=self._run_server, daemon=True)
            self.thread.start()
            self.running = True

            logger.info(f"Gallery Server gestartet auf http://{self.host}:{self.port}")
            logger.info(f"Öffne http://localhost:{self.port} oder http://<IP>:{self.port}")
            return True

        except Exception as e:
            logger.error(f"Gallery Server Start fehlgeschlagen: {e}")
            return False

    def _run_server(self) -> None:
        """Läuft den Server (in separatem Thread)."""
        try:
            self.server.serve_forever()
        except Exception as e:
            logger.error(f"Gallery Server Fehler: {e}")

    def stop(self) -> None:
        """Stoppt den Gallery Server."""
        if self.server and self.running:
            logger.info("Gallery Server wird gestoppt...")
            self.server.shutdown()
            self.running = False

    def _create_handler(self):
        """Erstellt einen Request-Handler mit Referenz auf diese Server-Instanz."""

        class RequestHandler(SimpleHTTPRequestHandler):
            """HTTP Request Handler für Gallery."""

            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(server.output_dir.absolute()), **kwargs)

            def log_message(self, format, *args):
                """Überschreibt default logging."""
                pass

            def do_GET(self):
                """Behandelt GET-Requests."""
                parsed = urlparse(self.path)
                path = parsed.path

                if path == "/" or path == "/gallery" or path == "/index.html":
                    self._send_gallery()
                elif path == "/api/images":
                    self._send_images_json()
                elif path == "/api/stats":
                    self._send_stats()
                elif path.startswith("/thumb/"):
                    # Thumbnail request - serve original
                    path = path.replace("/thumb/", "/")
                    super().do_GET()
                else:
                    # Static file serving from output directory
                    super().do_GET()

            def _send_gallery(self):
                """Sendet die Gallery HTML Seite."""
                html = self._generate_gallery_html()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(html.encode("utf-8"))

            def _send_images_json(self):
                """Sendet Bilder-Liste als JSON."""
                images = self._get_images_list()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(json.dumps(images, ensure_ascii=False).encode("utf-8"))

            def _send_stats(self):
                """Sendet Statistiken als JSON."""
                stats = self._get_stats()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(stats, ensure_ascii=False).encode("utf-8"))

            def _get_images_list(self) -> List[Dict[str, Any]]:
                """Sammelt alle Bilder mit Metadaten."""
                images = []
                output_dir = Path(server.output_dir)

                if not output_dir.exists():
                    return images

                for month_dir in sorted(output_dir.iterdir(), reverse=True):
                    if not month_dir.is_dir():
                        continue

                    for img_file in sorted(month_dir.glob("*.jpg")) + sorted(month_dir.glob("*.png")):
                        try:
                            stat = img_file.stat()
                            parts = img_file.stem.split("-", 4)

                            if len(parts) >= 4:
                                date_str = parts[0]  # YYYY-MM-DD
                                time_str = parts[1]  # HHMM
                                prompt_slug = parts[2] if len(parts) > 2 else ""

                                try:
                                    date_formatted = datetime.strptime(date_str, "%Y-%m-%d").strftime("%d.%m.%Y")
                                    time_formatted = f"{time_str[:2]}:{time_str[2:4]}"
                                except ValueError:
                                    date_formatted = date_str
                                    time_formatted = time_str

                                images.append({
                                    "path": f"/{img_file.name}",
                                    "filename": img_file.name,
                                    "title": prompt_slug.replace("-", " ").title(),
                                    "prompt": prompt_slug.replace("-", " "),
                                    "date": date_str,
                                    "time": time_str,
                                    "date_formatted": date_formatted,
                                    "time_formatted": time_formatted,
                                    "month": date_str[:7],  # YYYY-MM
                                    "year": date_str[:4],
                                    "size": stat.st_size,
                                    "size_formatted": self._format_size(stat.st_size),
                                    "model": "stable-diffusion-xl",
                                    "rms_db": 40  # placeholder
                                })
                        except Exception as e:
                            continue

                return list(reversed(images))  # Neueste zuerst

            def _get_stats(self) -> Dict[str, Any]:
                """Sammelt Statistiken."""
                images = self._get_images_list()
                months = set(img["month"] for img in images)
                years = set(img["year"] for img in images)

                current_month = datetime.now().strftime("%Y-%m")
                this_month_count = sum(1 for img in images if img["month"] == current_month)

                return {
                    "total": len(images),
                    "months": len(months),
                    "years": list(years),
                    "this_month": this_month_count
                }

            def _generate_gallery_html(self) -> str:
                """Generiert die Gallery HTML Seite."""
                images = self._get_images_list()
                stats = self._get_stats()

                # Verfügbare Monate/Jahre
                months = sorted(set(img["month"] for img in images), reverse=True)
                years = sorted(set(img["year"] for img in images), reverse=True)

                month_options = "".join(
                    f'<option value="{m}">{datetime.strptime(m, "%Y-%m").strftime("%B %Y")}</option>'
                    for m in months
                )
                year_options = "".join(f'<option value="{y}">{y}</option>' for y in years)

                # Date range
                if images:
                    date_range = f"{images[-1]['date_formatted']} - {images[0]['date_formatted']}"
                else:
                    date_range = "-"

                # Gallery cards
                if images:
                    gallery_cards = []
                    for img in images:
                        gallery_cards.append(f'''
                        <div class="card" onclick="openLightbox({images.index(img)})">
                            <img class="card-image" src="/{img['filename']}" alt="{img['title']}" loading="lazy">
                            <div class="card-content">
                                <div class="card-title">{img['title']}</div>
                                <div class="card-meta">
                                    <span>📅 {img['date_formatted']}</span>
                                    <span>⏰ {img['time_formatted']}</span>
                                </div>
                                <div class="card-prompt">{img['prompt'][:60]}...</div>
                            </div>
                        </div>
                        ''')
                    gallery_cards_str = "\n".join(gallery_cards)
                else:
                    gallery_cards_str = '<div class="no-images"><span>🖼️</span>Noch keine Bilder generiert</div>'

                # Images JSON für JavaScript
                images_json = json.dumps(images, ensure_ascii=False)

                return GALLERY_HTML.format(
                    total_count=stats["total"],
                    date_range=date_range,
                    latest_count=stats["this_month"],
                    month_options=month_options,
                    year_options=year_options,
                    gallery_cards=gallery_cards_str,
                    images_json=images_json
                )

            def _format_size(self, size: int) -> str:
                """Formatiert Dateigröße."""
                for unit in ["B", "KB", "MB", "GB"]:
                    if size < 1024:
                        return f"{size:.1f} {unit}"
                    size /= 1024
                return f"{size:.1f} TB"

        server = self
        return RequestHandler


def create_gallery_server(port: int = None) -> GalleryServer:
    """
    Factory-Function für GalleryServer.

    Args:
        port: Optionaler Port (aus .env wenn nicht angegeben)

    Returns:
        Konfigurierter GalleryServer
    """
    from dotenv import load_dotenv
    load_dotenv("config/.env")

    if port is None:
        port = int(os.getenv("GALLERY_PORT", str(DEFAULT_PORT)))

    host = os.getenv("GALLERY_HOST", DEFAULT_HOST)
    output_dir = os.getenv("OUTPUT_DIR", OUTPUT_DIR)

    return GalleryServer(
        host=host,
        port=port,
        output_dir=output_dir
    )