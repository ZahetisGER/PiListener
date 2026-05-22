# 🎧 PiListener

*Ein Raspberry Pi 4 Projekt, das alle 15 Minuten für 20 Sekunden lauscht, Gehörtes in Text verwandelt, und daraus KI-Bilder generiert.*

## Was ist PiListener?

PiListener ist ein kreatives KI-System, das auf einem Raspberry Pi 4 mit einem Jabra Speak USB-Mikrofon läuft. In regelmäßigen Intervallen nimmt das System Audio auf, transkribiert es mit Whisper zu Text, und generiert mit Stable Diffusion oder anderen kostenlosen KI-Modellen ein Bild, das auf einem HDMI-Display in Vollbild angezeigt wird.

Das letzte Bild bleibt stehen, bis ein neues generiert wird – wie ein digitaler Bildschirm für akustische Erinnerungen.

## ✨ Features

- **Automatisches Audio-Monitoring** – Alle 15 Minuten 20 Sekunden Aufnahme
- **USB/Jabra Auto-Detection** – Automatische Erkennung von USB-Mikrofonen
- **Lokale STT** – faster-whisper auf CPU (keine Cloud-Kosten)
- **Fallback-Kette** – OpenRouter Whisper API → Akustische Beschreibung
- **Dynamische Model-Auswahl** – Wählt beste kostenlose Modelle
- **KI-Bildgenerierung** – Stable Diffusion XL via OpenRouter
- **Vollbild-Anzeige** – HDMI-Display mit Titel-Balken
- **Metadaten** – Original-Prompt im Bild gespeichert
- **Webserver** – Status und Steuerung via Browser (http://localhost:8000)
- **Setup Wizard** – Einfache 10-Schritt Installation

## 🖥️ Hardware

| Komponente | Spezifikation |
|------------|---------------|
| **Raspberry Pi** | Pi 4 4GB RAM |
| **Mikrofon** | Jabra Speak 410/510/750 (USB) oder anderes USB-Mikrofon |
| **Display** | HDMI (Full HD 1920x1080) |
| **Betriebssystem** | Raspberry Pi OS (Bookworm) |

## 🚀 Installation

### One-Line Installer (Schnellstart)

```bash
curl -sSL https://raw.githubusercontent.com/ZahetisGER/PiListener/main/wizard.sh | bash
```

Das führt dich durch 10 Schritte: System-Prüfung → Verzeichnisse → Pakete → Python → Audio → API-Key → Whisper → Test → Fertig!

### Manuelle Installation

1. **System-Pakete installieren:**
```bash
sudo apt-get update && sudo apt-get install -y \
    python3 python3-pip python3-venv python3-dev git ffmpeg \
    libasound2-dev portaudio19-dev x11-xserver-utils unclutter
```

2. **Repository klonen:**
```bash
git clone https://github.com/ZahetisGER/PiListener.git ~/PiListener
cd ~/PiListener
```

3. **Virtual Environment und Pakete:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

4. **Konfiguration:**
```bash
cp .env.template config/.env
# Bearbeite config/.env und trage OPENROUTER_API_KEY ein
```

5. **Whisper-Modell herunterladen:**
```bash
python3 -c "from faster_whisper import WhisperModel; WhisperModel('base', device='cpu')"
```

6. **Manueller Start:**
```bash
python src/main.py
```

### Audio-Gerät einrichten

```bash
# Verfügbare Geräte anzeigen
./src/audio_devices.sh

# Interaktives Setup
sudo ./src/setup_audio_source.sh

# Oder direkt konfigurieren:
# In config/.env: AUDIO_SOURCE=hw:CARD=Speak,DEV=0
```

## 📱 Bedienung

### Manueller Start

```bash
cd ~/PiListener
source .venv/bin/activate
python src/main.py
```

### Web-Interface

Nach dem Start ist das System unter http://localhost:8000 erreichbar:

- **Status anzeigen** – Aktueller Zustand und letzte Bilder
- **Zyklus triggern** – Sofortige Audio-Aufnahme starten
- **Konfiguration neu laden** – .env Änderungen übernehmen
- **System beenden** – Sauberes Herunterfahren

### Crontab (automatisches Starten)

```bash
# Alle 15 Minuten ausführen
*/15 * * * * cd ~/PiListener && .venv/bin/python src/main.py >> logs/listener.log 2>&1
```

## 💰 Kostenlose Modelle

| Model | Provider | Task | Kosten |
|-------|----------|------|--------|
| Whisper Base | faster-whisper (lokal) | STT | ✓ |
| SDXL Turbo | OpenRouter | Image | ✓ |
| Stable Diffusion XL | NVIDIA | Image | ✓ |
| Claude 3.5 Sonnet | OpenRouter | Image | ✓ |

Mehr kostenlose Modelle:
- [OpenRouter Free Models](https://openrouter.ai/models?free=true)
- [NVIDIA Build](https://build.nvidia.com)

## 📁 Projektstruktur

```
PiListener/
├── config/
│   └── .env                  # API-Keys + Konfiguration
├── logs/
│   └── listener.log          # Log-Datei
├── models/                   # Lokale Whisper-Modelle
├── output/
│   └── YYYY-MM/             # Generierte Bilder
├── src/
│   ├── __init__.py
│   ├── listener.py           # Audio-Capture + STT + USB-Erkennung
│   ├── image_generator.py   # Bildgenerierung
│   ├── display.py           # Vollbild-Anzeige
│   ├── model_selector.py    # Model-Auswahl
│   ├── webserver.py         # HTTP Status/Steuerung
│   ├── logger.py            # Logging
│   ├── audio_devices.sh      # Audio-Geräte auflisten
│   ├── setup_audio_source.sh # Audio-Setup Wizard
│   └── main.py              # Hauptschleife
├── tests/                    # pytest Tests
├── wizard.sh                # Interaktiver Setup Wizard
├── install.sh               # One-Line Installer
├── requirements.txt
├── README.md
└── .gitignore
```

## 🏗️ Architektur

```
┌─────────────────────────────────────────────────────────────────┐
│                        PiListener                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    │
│   │   Jabra/USB  │───▶│   Audio      │───▶│    STT       │    │
│   │   Speak      │    │   Listener   │    │   (Whisper)  │    │
│   │   Mikrofon   │    │  + Auto-Detect│   │              │    │
│   └──────────────┘    └──────────────┘    └──────┬───────┘    │
│                                                   │            │
│                                                   ▼            │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    │
│   │   Display    │◀───│    Image     │◀───│    OpenRouter│    │
│   │   (HDMI)     │    │   Generator  │    │    API        │    │
│   │   Vollbild   │    │              │    │    (SDXL)     │    │
│   └──────────────┘    └──────────────┘    └──────────────┘    │
│                                                                 │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    │
│   │    Model     │───▶│    Config    │    │   Webserver  │    │
│   │   Selector   │    │   (.env)     │    │   :8000      │    │
│   └──────────────┘    └──────────────┘    └──────────────┘    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

    Zyklus (alle 15 Minuten):

    ┌────────────────────────────────────────────────────────────┐
    │  1. WARTEN bis zur vollen 15-Min-Markierung               │
    │              │                                              │
    │              ▼                                              │
    │  2. USB/JABRA ERKENNUNG (auto-detect)                       │
    │              │                                              │
    │              ▼                                              │
    │  3. AUDIO AUFNAHME (20 Sekunden)                          │
    │              │                                              │
    │              ▼                                              │
    │  4. STILLE-PRÜFUNG (RMS > 30dB?)                          │
    │              │                                              │
    │         Nein │                                              │
    │              ▼                                              │
    │  5. STT TRANSKRIPTION (Whisper lokal)                     │
    │              │                                              │
    │              ▼                                              │
    │  6. BILDGENERIERUNG (OpenRouter/SDXL)                      │
    │              │                                              │
    │              ▼                                              │
    │  7. BILD SPEICHERN (mit Prompt-Metadaten)                 │
    │              │                                              │
    │              ▼                                              │
    │  8. VOLLBILD-ANZEIGE (auf HDMI)                           │
    │              │                                              │
    │              ▼                                              │
    │  9. STATUS PER WEBSEERVER (http://localhost:8000)        │
    └────────────────────────────────────────────────────────────┘
```

## 📝 Log-Beispiele

```
[2026-05-22 08:15:00] INFO: PiListener startet...
[2026-05-22 08:15:01] INFO: Audio-Listener initialisiert. Device: 2, Rate: 16000
[2026-05-22 08:15:01] INFO: USB Audio Device erkannt: 'Jabra Speak 410' an Index 2
[2026-05-22 08:15:02] INFO: ImageGenerator initialisiert: 1920x1080, Qualität: 85
[2026-05-22 08:15:03] INFO: Display initialisiert: 1920x1080, Fullscreen: True
[2026-05-22 08:15:04] INFO: WebServer gestartet auf http://0.0.0.0:8000
[2026-05-22 08:15:05] INFO: Alle Komponenten initialisiert
[2026-05-22 08:15:05] INFO: PiListener läuft im Hintergrund...

[2026-05-22 08:30:00] INFO: Zyklus gestartet um 08:30:00
[2026-05-22 08:30:00] INFO: Nehme 20s Audio auf...
[2026-05-22 08:30:00] INFO: Audio aufgenommen: RMS=45.2dB
[2026-05-22 08:30:08] INFO: STT: "Regen trommelt auf das dach"
[2026-05-22 08:30:08] INFO: STT Model: faster-whisper-base
[2026-05-22 08:30:22] INFO: Bild generiert: 1920x1080, 245KB
[2026-05-22 08:30:23] INFO: Bild gespeichert: output/2026-05/2026-05-22-0830-regen-trommelt.jpg
[2026-05-22 08:30:23] INFO: Angezeigt auf Display
[2026-05-22 08:30:23] INFO: Zyklus erfolgreich beendet in 23.5s
```

### Fehler-Logs (mit Fallback)

```
[2026-05-22 09:00:00] WARNING: Stille erkannt (RMS=22dB < 30dB), kein Bild
[2026-05-22 09:15:00] ERROR: OpenRouter API Fehler: quota exceeded
[2026-05-22 09:15:00] INFO: Fallback: akustische Beschreibung generiert
[2026-05-22 09:15:00] INFO: STT (Fallback/Beschreibung): "Es klingt nach: ferne Stimme"
```

## 🧪 Tests

```bash
# Alle Tests ausführen
source .venv/bin/activate
pytest tests/ -v

# Einzelne Tests
pytest tests/test_listener.py -v
pytest tests/test_stt.py -v
pytest tests/test_image_generator.py -v
```

## 🔧 Konfiguration

Bearbeite `config/.env`:

```env
# API
OPENROUTER_API_KEY=sk-or-v1-dein-key

# Audio (wird auto-detected wenn leer)
AUDIO_SOURCE=hw:CARD=Speak,DEV=0
LISTEN_INTERVAL_MINUTES=15
LISTEN_DURATION_SECONDS=20
SILENCE_THRESHOLD_DB=30

# Bild
IMAGE_WIDTH=1920
IMAGE_HEIGHT=1080
IMAGE_QUALITY=85

# Display
FULLSCREEN=true
SHOW_TITLE_BAR=true

# Webserver
WEB_PORT=8000
WEB_HOST=0.0.0.0

# Logging
LOG_LEVEL=INFO

# Whisper
WHISPER_MODEL=base
LANGUAGE=de
```

## 🐛 Troubleshooting

**Problem:** Jabra/USB-Mikrofon wird nicht erkannt

```bash
# Verfügbare Geräte anzeigen
./src/audio_devices.sh

# Manuell konfigurieren
sudo ./src/setup_audio_source.sh
```

**Problem:** Schwarzer Bildschirm beim Start

```bash
# X11 prüfen
echo $DISPLAY
# Sollte :0 sein

# Als nicht-root starten (X11 Berechtigung)
xhost +local:nonroot
```

**Problem:** Bildgenerierung schlägt fehl

```bash
# API Key prüfen
grep OPENROUTER config/.env

# Quota prüfen auf openrouter.ai/credits
```

**Problem:** Webserver nicht erreichbar

```bash
# Port prüfen
ss -tlnp | grep 8000

# Firewall prüfen
sudo ufw allow 8000
```

## 📄 Lizenz

MIT License - siehe [LICENSE](LICENSE) Datei.

## 🙏 Danke an

- [faster-whisper](https://github.com/guillaumekln/faster-whisper) – Schnelle STT
- [OpenRouter](https://openrouter.ai) – Kostenlose Modelle
- [PyGame](https://www.pygame.org) – Display-Anzeige
- [Pillow](https://python-pillow.org) – Bildverarbeitung