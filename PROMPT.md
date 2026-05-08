# PiListener - Claude Code Prompt

## Übersicht (Was ist das?)

PiListener ist ein kreatives KI-System für Raspberry Pi 4, das alle 15 Minuten für 20 Sekunden lauscht, Gehörtes per Speech-to-Text (Whisper) in Text verwandelt, und daraus mit Stable Diffusion ein KI-Bild generiert, das auf einem HDMI-Display in Vollbild angezeigt wird.

Das letzte Bild bleibt stehen, bis ein neues generiert wird – wie ein digitaler Bildschirm für akustische Erinnerungen.

**Kernfunktionen:**
- Automatisches Audio-Monitoring im 15-Minuten-Intervall
- Lokale STT mit faster-whisper (CPU, keine Cloud-Kosten)
- Fallback-Kette: Lokal → OpenRouter Whisper API → Akustische Beschreibung
- KI-Bildgenerierung via OpenRouter (SDXL Turbo, kostenloses Kontingent)
- Dynamische Model-Auswahl (bevorzugt kostenlose Modelle)
- Vollbild-Anzeige mit Titel-Balken
- Metadaten/Prompt im Bild gespeichert
- Resilient gegen Jabra-Disconnect und Netzwerkfehler

## Architektur (Wie funktioniert es?)

```
┌─────────────────────────────────────────────────────────────────┐
│                        PiListener                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    │
│   │   Jabra      │───▶│   Audio      │───▶│    STT       │    │
│   │   Speak      │    │   Listener   │    │   (Whisper)  │    │
│   │   (USB)      │    │              │    │              │    │
│   └──────────────┘    └──────────────┘    └──────┬───────┘    │
│                                                   │            │
│                                                   ▼            │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    │
│   │   Display    │◀───│    Image     │◀───│    OpenRouter│    │
│   │   (HDMI)     │    │   Generator  │    │    API        │    │
│   │   Vollbild   │    │              │    │    (SDXL)     │    │
│   └──────────────┘    └──────────────┘    └──────────────┘    │
│                                                                 │
│   ┌──────────────┐    ┌──────────────┐                         │
│   │    Model     │───▶│    Config    │                         │
│   │   Selector   │    │   (.env)     │                         │
│   └──────────────┘    └──────────────┘                         │
│                                                                 │
│   ┌──────────────┐                                              │
│   │   WebServer  │  (Optional, Port 8000)                       │
│   │   Status     │                                              │
│   └──────────────┘                                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

Zyklus (alle 15 Minuten):
1. WARTEN bis zur vollen 15-Min-Markierung
         │
         ▼
2. AUDIO AUFNAHME (20 Sekunden)
         │
         ▼
3. STILLE-PRÜFUNG (RMS > 30dB?)
         │
    Nein │
         ▼
4. STT TRANSKRIPTION (Whisper)
         │
         ▼
5. BILDGENERIERUNG (OpenRouter/SDXL)
         │
         ▼
6. BILD SPEICHERN (mit Metadaten)
         │
         ▼
7. VOLLBILD-ANZEIGE (letztes Bild bleibt)
```

## Ordnerstruktur (Was ist wo?)

```
PiListener/
├── config/                    # Konfiguration
│   └── .env                  # API-Keys + Einstellungen (nicht in Git)
├── logs/                      # Log-Dateien
│   └── listener.log          # Haupt-Log (rotiert täglich, 7 Tage)
├── models/                    # Lokale Whisper-Modelle
├── output/                    # Generierte Bilder
│   └── YYYY-MM/             # Nach Monat organisiert
├── src/                       # Hauptquellcode
│   ├── __init__.py
│   ├── main.py              # Hauptschleife, PiListener-Klasse
│   ├── listener.py           # Audio-Capture + STT (AudioListener, STTEngine)
│   ├── image_generator.py    # Bildgenerierung (ImageGenerator)
│   ├── display.py            # Vollbild-Anzeige (DisplayManager)
│   ├── model_selector.py     # Model-Auswahl (ModelSelector)
│   ├── logger.py             # Logging-Setup
│   ├── webserver.py          # HTTP-Status-Server (optional)
│   ├── audio_devices.sh       # Listet Audio-Geräte auf
│   └── setup_audio_source.sh  # Interaktives Audio-Setup
├── tests/                     # Unit-Tests (pytest)
│   ├── test_listener.py
│   ├── test_stt.py
│   ├── test_image_generator.py
│   ├── test_display.py
│   └── test_model_selector.py
├── install.sh                 # One-Line Installer
├── requirements.txt           # Python Dependencies
├── .env.template             # Vorlage für config/.env
├── README.md                 # Haupt-Dokumentation
├── LICENSE                   # MIT License
└── .gitignore
```

## Installation (Schnellstart + Details)

### One-Line Installer

```bash
curl -sSL https://raw.githubusercontent.com/ZahetisGER/PiListener/main/install.sh | bash
```

### Manuelle Installation

**1. System-Pakete installieren:**
```bash
sudo apt-get update && sudo apt-get install -y \
    python3 python3-pip python3-venv python3-dev git ffmpeg \
    libasound2-dev libportaudio2 libportaudiocpp0 portaudio19-dev \
    x11-xserver-utils unclutter pulseaudio
```

**2. Repository klonen:**
```bash
git clone https://github.com/ZahetisGER/PiListener.git ~/PiListener
cd ~/PiListener
```

**3. Virtual Environment und Pakete:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**4. Konfiguration erstellen:**
```bash
cp .env.template config/.env
# Bearbeite config/.env und trage OPENROUTER_API_KEY ein
```

**5. Whisper-Modell herunterladen:**
```bash
python3 -c "from faster_whisper import WhisperModel; WhisperModel('base', device='cpu')"
```

**6. Audio-Quelle konfigurieren:**
```bash
# Interaktives Setup
sudo ./src/setup_audio_source.sh

# Oder automatisch nach Name (z.B. Jabra Speak)
sudo ./src/setup_audio_source.sh --name "Speak"
```

**7. Manueller Start:**
```bash
python src/main.py
```

### Crontab (optional)

```bash
# Alle 15 Minuten ausführen
*/15 * * * * cd ~/PiListener && .venv/bin/python src/main.py >> logs/listener.log 2>&1
```

## Konfiguration (.env Variablen erklärt)

Kopiere `.env.template` nach `config/.env` und bearbeite die Werte:

```env
# ============================================
# API KONFIGURATION
# ============================================

# OpenRouter API Key (erforderlich)
# Hole deinen Key von: https://openrouter.ai/keys
OPENROUTER_API_KEY=sk-or-v1-dein-api-key-hier

# ============================================
# AUDIO KONFIGURATION
# ============================================

# Audio-Quelle (ALSA Device)
# Beispiel: hw:CARD=Speak,DEV=0 für Jabra Speak
# Liste verfügbare Geräte mit: arecord -l
AUDIO_SOURCE=hw:CARD=Speak,DEV=0

# Alternativ: PulseAudio Quelle (z.B. für some Jabra Speak Modelle)
# PULSE_SOURCE=0

# ============================================
# LISTEN INTERVALL
# ============================================

# Alle wieviel Minuten wird gelauscht (Standard: 15)
LISTEN_INTERVAL_MINUTES=15

# Wie lange wird gelauscht in Sekunden (Standard: 20)
LISTEN_DURATION_SECONDS=20

# Mindest-Lautstärke in dB RMS für "Stille-Erkennung"
# Unter diesem Wert wird kein Bild generiert (Standard: 30)
SILENCE_THRESHOLD_DB=30

# ============================================
# BILD GENERIERUNG
# ============================================

# Bildauflösung (Standard: 1920x1080 für Full HD)
IMAGE_WIDTH=1920
IMAGE_HEIGHT=1080

# Bildqualität (1-100, Standard: 85)
IMAGE_QUALITY=85

# ============================================
# DISPLAY KONFIGURATION
# ============================================

# Vollbild-Modus (Standard: true)
FULLSCREEN=true

# Titelbalken anzeigen (Standard: true)
SHOW_TITLE_BAR=true

# ============================================
# LOGGING
# ============================================

# Log-Level: DEBUG, INFO, WARNING, ERROR (Standard: INFO)
LOG_LEVEL=INFO

# ============================================
# WHISPER MODELL
# ============================================

# Welches Whisper-Modell verwenden (tiny, base, small, medium, large)
# Standard: base (gut für Pi 4 4GB)
WHISPER_MODEL=base

# ============================================
# SYSTEM
# ============================================

# Sprachcode für STT (Standard: de für Deutsch)
LANGUAGE=de
```

## Betrieb (Wie startet man? Wie debuggt man?)

### Starten

```bash
# Ins Projektverzeichnis wechseln
cd ~/PiListener

# Virtual Environment aktivieren
source .venv/bin/activate

# Manuell starten
python src/main.py

# Oder direkt mit venv
.venv/bin/python src/main.py
```

### Debugging

**Log-Datei anzeigen:**
```bash
tail -f logs/listener.log
```

**Log-Level ändern** (in config/.env):
```env
LOG_LEVEL=DEBUG
```

**Audio-Geräte prüfen:**
```bash
./src/audio_devices.sh
```

**Manueller Audio-Test:**
```python
from src.listener import create_listener
listener, stt = create_listener()
audio = listener.record(duration=5)
print(f"RMS: {audio.rms_db}dB")
```

**Manuelle Bildgenerierung:**
```python
from src.image_generator import create_image_generator
gen = create_image_generator()
img = gen.generate("Ein sonniger Tag im Wald")
if img:
    path = gen.save_image(img, "Test-Prompt")
    print(f"Gespeichert: {path}")
```

### Web Interface (optional)

Der Webserver läuft standardmäßig auf Port 8000 und bietet:
- `/` - Status-Seite mit letztem Bild
- `/trigger` - Zyklus sofort starten
- `/reload` - Konfiguration neu laden
- `/shutdown` - System beenden
- `/logs` - Logs als JSON

## Entwicklung (Wie testet man? Commit-Regeln?)

### Tests ausführen

```bash
# Alle Tests
pytest tests/ -v

# Einzelne Tests
pytest tests/test_listener.py -v
pytest tests/test_stt.py -v
pytest tests/test_image_generator.py -v
pytest tests/test_display.py -v
pytest tests/test_model_selector.py -v

# Mit Coverage
pytest tests/ --cov=src --cov-report=term-missing
```

### Commit-Konventionen

Bitte nutze folgende Prefixes:

- `feat:` – Neue Features
- `fix:` – Bugfixes
- `docs:` – Dokumentation
- `chore:` – Wartung, Refactoring
- `test:` – Tests hinzugefügt/geändert

**Beispiele:**
```bash
git commit -m "feat: WebServer für Status-Anzeige hinzugefügt"
git commit -m "fix: Stille-Erkennung funktioniert nicht bei niedrigen RMS-Werten"
git commit -m "docs: README mit Beispiel-Prompts erweitert"
```

### Workflow

1. Fork erstellen (oder direkt auf main bei privatem Repo)
2. Feature-Branch: `git checkout -b feat/neues-feature`
3. Änderungen machen + testen
4. Commit: `git commit -m "feat: ..."`
5. Push: `git push origin feat/neues-feature`
6. Pull Request öffnen (falls Fork)

### Code-Struktur

**Wichtige Klassen:**

- `PiListener` (main.py) - Hauptschleife, koordiniert alle Komponenten
- `AudioListener` (listener.py) - Audio-Capture mit Stille-Erkennung
- `STTEngine` (listener.py) - Whisper-Transkription mit Fallbacks
- `ImageGenerator` (image_generator.py) - OpenRouter API für Bildgenerierung
- `DisplayManager` (display.py) - Pygame-basierte Vollbild-Anzeige
- `ModelSelector` (model_selector.py) - Dynamische Auswahl kostenloser Modelle
- `PiListenerWebServer` (webserver.py) - HTTP-Status-Server

**Factory-Functions:**
- `create_listener()` - Erstellt AudioListener + STTEngine
- `create_image_generator()` - Erstellt konfigurierten ImageGenerator
- `create_display()` - Erstellt konfigurierten DisplayManager
- `get_model_selector()` - Singleton ModelSelector
- `create_webserver()` - Erstellt WebServer

## Troubleshooting (Häufige Probleme)

### Problem: Jabra wird nicht erkannt

```bash
# ALSA Devices prüfen
arecord -l

# Device-Index finden und in config/.env anpassen
# Beispiel: hw:CARD=Speak,DEV=0
```

### Problem: Schwarzer Bildschirm

```bash
# X11 prüfen
echo $DISPLAY
# Sollte :0 sein

# Falls nicht:
export DISPLAY=:0
```

### Problem: "OPENROUTER_API_KEY nicht gefunden"

```bash
# API Key in config/.env eintragen
cat config/.env | grep OPENROUTER
```

### Problem: Bildgenerierung schlägt fehl

```bash
# API Key prüfen
cat config/.env | grep OPENROUTER

# Quota prüfen auf https://openrouter.ai/credits

# Logs prüfen
tail -50 logs/listener.log
```

### Problem: Stille wird immer erkannt obwohl Audio vorhanden

```bash
# SILENCE_THRESHOLD_DB in config/.env senken
# Standard: 30, probiere: 20 oder 25

# Manuell RMS prüfen
python3 -c "
from src.listener import create_listener
l, _ = create_listener()
a = l.record(duration=5)
print(f'RMS: {a.rms_db}dB')
"
```

### Problem: whisper Model lädt nicht

```bash
# Model manuell herunterladen
python3 -c "
from faster_whisper import WhisperModel
model = WhisperModel('base', device='cpu', download_root='models')
"
```

### Problem: WebServer startet nicht

```bash
# Port prüfen (Standard: 8000)
lsof -i :8000

# Firewall prüfen
sudo ufw allow 8000
```

## Kostenlose Modelle

| Model | Provider | Task | API |
|-------|----------|------|-----|
| Whisper Base | faster-whisper (lokal) | STT | Kostenlos |
| SDXL Turbo | OpenRouter | Image | kostenloses Kontingent |
| Stable Diffusion XL | NVIDIA | Image | kostenlos |
| Claude 3.5 Sonnet | OpenRouter | Image | kostenloses Kontingent |

**Mehr Modelle:**
- [OpenRouter Free Models](https://openrouter.ai/models?free=true)
- [NVIDIA Build](https://build.nvidia.com)

## Hardware

| Komponente | Spezifikation |
|------------|---------------|
| **Raspberry Pi** | Pi 4 4GB RAM |
| **Mikrofon** | Jabra Speak 410/510/750 (USB) |
| **Display** | HDMI (Full HD 1920x1080) |
| **Betriebssystem** | Raspberry Pi OS (Bookworm) |
