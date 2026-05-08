# 🎧 PiListener

*Ein Raspberry Pi 4 Projekt, das alle 15 Minuten für 20 Sekunden lauscht, Gehörtes in Text verwandelt, und daraus KI-Bilder generiert.*

![PiListener Architektur](docs/architecture.png)

## Was ist PiListener?

PiListener ist ein kreatives KI-System, das auf einem Raspberry Pi 4 mit einem Jabra Speak USB-Mikrofon läuft. In regelmäßigen Intervallen nimmt das System Audio auf, transkribiert es mit Whisper zu Text, und generiert mit Stable Diffusion oder anderen kostenlosen KI-Modellen ein Bild, das auf einem HDMI-Display in Vollbild angezeigt wird.

Das letzte Bild bleibt stehen, bis ein neues generiert wird – wie ein digitaler Bildschirm für akustche Erinnerungen.

## ✨ Features

- **Automatisches Audio-Monitoring** – Alle 15 Minuten 20 Sekunden Aufnahme
- **Stille-Erkennung** – Kein Bild bei zu leiser Umgebung
- **Lokale STT** – faster-whisper auf CPU (keine Cloud-Kosten)
- **Fallback-Kette** – OpenRouter Whisper API → Akustische Beschreibung
- **Dynamische Model-Auswahl** – Wählt beste kostenlose Modelle
- **KI-Bildgenerierung** – Stable Diffusion XL via OpenRouter
- **Vollbild-Anzeige** – HDMI-Display mit Titel-Balken
- **Metadaten** – Original-Prompt im Bild gespeichert
- **Resilient** – Kein Crash bei Jabra-Disconnect oder Netzwerkfehlern

## 🖥️ Hardware

| Komponente | Spezifikation |
|------------|---------------|
| **Raspberry Pi** | Pi 4 4GB RAM |
| **Mikrofon** | Jabra Speak 410/510/750 (USB) |
| **Display** | HDMI (Full HD 1920x1080) |
| **Betriebssystem** | Raspberry Pi OS (Bookworm) |

## 🚀 Installation

### One-Line Installer

```bash
curl -sSL https://raw.githubusercontent.com/GITHUB_USER/PiListener/main/install.sh | bash
```

### Manuelle Installation

1. **System-Pakete installieren:**
```bash
sudo apt-get update && sudo apt-get install -y \
    python3 python3-pip python3-venv python3-dev git ffmpeg \
    libasound2-dev libportaudio2 libportaudiocpp0 portaudio19-dev \
    x11-xserver-utils unclutter pulseaudio
```

2. **Repository klonen:**
```bash
git clone https://github.com/GITHUB_USER/PiListener.git ~/PiListener
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

### Crontab (optional)

```bash
# Alle 15 Minuten ausführen
*/15 * * * * cd ~/PiListener && .venv/bin/python src/main.py >> logs/listener.log 2>&1
```

## 💰 Kostenlose Modelle

| Model | Provider | Task | API |
|-------|----------|------|-----|
| Whisper Base | faster-whisper (lokal) | STT | Kostenlos |
| SDXL Turbo | OpenRouter | Image | kostenloses Kontingent |
| Stable Diffusion XL | NVIDIA | Image | kostenlos |
| Claude 3.5 Sonnet | OpenRouter | Image | kostenloses Kontingent |

Mehr Modelle auf:
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
│   ├── listener.py           # Audio-Capture + STT
│   ├── image_generator.py   # Bildgenerierung
│   ├── display.py           # Vollbild-Anzeige
│   ├── model_selector.py    # Model-Auswahl
│   ├── logger.py            # Logging
│   └── main.py              # Hauptschleife
├── tests/
│   ├── test_listener.py
│   ├── test_stt.py
│   ├── test_image_generator.py
│   ├── test_display.py
│   └── test_model_selector.py
├── install.sh                # One-Line Installer
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
└─────────────────────────────────────────────────────────────────┘

    Zyklus (alle 15 Minuten):
    
    ┌────────────────────────────────────────────────────────────┐
    │                                                            │
    │    1. WARTEN bis zur vollen 15-Min-Markierung             │
    │              │                                              │
    │              ▼                                              │
    │    2. AUDIO AUFNAHME (20 Sekunden)                         │
    │              │                                              │
    │              ▼                                              │
    │    3. STILLE-PRÜFUNG (RMS > 30dB?)                         │
    │              │                                              │
    │         Nein │                                              │
    │              ▼                                              │
    │    4. STT TRANSKRIPTION (Whisper)                          │
    │              │                                              │
    │              ▼                                              │
    │    5. BILDGENERIERUNG (OpenRouter/SDXL)                     │
    │              │                                              │
    │              ▼                                              │
    │    6. BILD SPEICHERN (mit Metadaten)                       │
    │              │                                              │
    │              ▼                                              │
    │    7. VOLLBILD-ANZEIGE (letztes Bild bleibt)              │
    │                                                            │
    └────────────────────────────────────────────────────────────┘
```

## 🖼️ Beispiel-Bilder

### Beispiel 1: "Regen trommelt auf das Dach"
![Beispiel 1](docs/examples/regen-dach.jpg)
*Prompt: "Regen trommelt auf das Dach" – Generiert um 08:15

### Beispiel 2: "Sonnenuntergang über der Stadt"
![Beispiel 2](docs/examples/sonnenuntergang-stadt.jpg)
*Prompt: "Sonnenuntergang über der Stadt" – Generiert um 12:30

### Beispiel 3: "Wald im Nebel"
![Beispiel 3](docs/examples/wald-nebel.jpg)
*Prompt: "Wald im Nebel" – Generiert um 18:45

## 📝 Log-Beispiele

```
[2026-05-08 02:15:00] INFO: Zyklus gestartet
[2026-05-08 02:15:00] INFO: Audio: 20s aufgenommen, RMS=45dB
[2026-05-08 02:15:08] INFO: STT: "Regen trommelt auf das dach"
[2026-05-08 02:15:08] INFO: Model STT: faster-whisper (lokal)
[2026-05-08 02:15:22] INFO: Image generiert: 1024x576
[2026-05-08 02:15:22] INFO: Model Image: stable-diffusion-xl
[2026-05-08 02:15:22] INFO: Gespeichert: output/2026-05/2026-05-08-0215-regen-trommelt.jpg
[2026-05-08 02:15:22] INFO: Angezeigt auf Display
[2026-05-08 02:15:22] INFO: Zyklus beendet
```

### Fehler-Logs

```
[2026-05-08 03:00:00] WARNING: Stille erkannt (RMS=22dB), kein Bild
[2026-05-08 04:15:00] ERROR: STT fehlgeschlagen: connection timeout
[2026-05-08 04:15:00] INFO: Fallback: akustische Beschreibung
```

## 🧪 Tests

```bash
# Alle Tests ausführen
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

# Audio
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

# Logging
LOG_LEVEL=INFO

# Whisper
WHISPER_MODEL=base
LANGUAGE=de
```

## 🐛 Troubleshooting

**Problem:** Jabra wird nicht erkannt
```bash
# ALSA Devices prüfen
arecord -l
# Device in config/.env anpassen
```

**Problem:** Schwarzer Bildschirm
```bash
# X11 prüfen
echo $DISPLAY
# Sollte :0 sein
```

**Problem:** Bildgenerierung schlägt fehl
```bash
# API Key prüfen
cat config/.env | grep OPENROUTER
# Quota prüfen auf openrouter.ai
```

## 📄 Lizenz

MIT License - siehe [LICENSE](LICENSE) Datei.

## 🤝 Contributing

### Commit-Konventionen

Bitte nutze folgende Prefixes:

- `feat:` – Neue Features
- `fix:` – Bugfixes
- `docs:` – Dokumentation
- `chore:` – Wartung, Refactoring

### Workflow

1. Fork erstellen
2. Feature-Branch: `git checkout -b feat/neues-feature`
3. Commit: `git commit -m "feat: neues Feature hinzugefügt"`
4. Push: `git push origin feat/neues-feature`
5. Pull Request öffnen

---

**Hinweis:** Dies ist ein privates Repository. Bitte fork erstellen für eigene Änderungen.

## 🙏 Danke an

- [faster-whisper](https://github.com/guillaumekln/faster-whisper) – Schnelle STT
- [OpenRouter](https://openrouter.ai) – Kostenlose Modelle
- [PyGame](https://www.pygame.org) – Display-Anzeige
- [Pillow](https://python-pillow.org) – Bildverarbeitung
