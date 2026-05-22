#!/bin/bash
# PiListener Installations-Script
# One-Line Installer: curl -sSL https://raw.githubusercontent.com/ZahetisGER/PiListener/main/install.sh | bash

set -e

REPO_URL="https://github.com/ZahetisGER/PiListener.git"
INSTALL_DIR="$HOME/PiListener"
VENV_DIR="$INSTALL_DIR/.venv"

echo "=========================================="
echo "  PiListener Installation"
echo "=========================================="

#Farben
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 1. System-Pakete installieren
echo "[1/9] Installiere System-Pakete..."
sudo apt-get update

# Basis-Pakete (immer erforderlich)
BASE_PKGS="python3 python3-pip python3-venv python3-dev git ffmpeg libasound2-dev"

# Audio-Pakete (flexibel - versuche verschiedene Paketnamen)
AUDIO_PKGS=""
for pkg in "portaudio19-dev" "libportaudio2 portaudio19-dev" "libportaudiocpp0"; do
    if apt-cache show "$pkg" &>/dev/null 2>&1; then
        AUDIO_PKGS="$pkg"
        break
    fi
done
if [ -z "$AUDIO_PKGS" ]; then
    echo -e "${YELLOW}PortAudio Paket nicht gefunden, versuche Alternative...${NC}"
    apt-get install -y portaudio19-dev libportaudio2 2>/dev/null || true
fi

# X11/Unclutter
X11_PKGS="x11-xserver-utils unclutter"
if ! dpkg -l | grep -q unclutter; then
    apt-get install -y $X11_PKGS 2>/dev/null || sudo apt-get install -y $X11_PKGS
fi

# Alle Pakete installieren
sudo apt-get install -y $BASE_PKGS $AUDIO_PKGS $X11_PKGS 2>/dev/null || \
sudo apt-get install -y python3 python3-pip python3-venv python3-dev git ffmpeg libasound2-dev portaudio19-dev

echo -e "${GREEN}System-Pakete installiert${NC}"

# 2. Verzeichnis erstellen und Repo klonen
echo "[2/9] Klone Repository..."
mkdir -p "$INSTALL_DIR"
if [ -d "$INSTALL_DIR/.git" ]; then
    echo "Repository bereits vorhanden, Update..."
    cd "$INSTALL_DIR" && git pull
else
    git clone "$REPO_URL" "$INSTALL_DIR"
fi
cd "$INSTALL_DIR"

# 3. venv erstellen und Requirements installieren
echo "[3/9] Erstelle Python Virtual Environment..."
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

echo "[4/9] Installiere Python-Pakete..."
pip install --upgrade pip setuptools wheel

# Installiere Pakete mit Fehlerbehandlung
if pip install -r requirements.txt; then
    echo -e "${GREEN}Python-Pakete installiert${NC}"
else
    echo -e "${YELLOW}Einige Pakete konnten nicht installiert werden, versuche alternatif...${NC}"
    # Versuche Pakete einzeln zu installieren für bessere Fehlerdiagnose
    pip install faster-whisper openai Pillow pygame loguru python-dotenv requests sounddevice numpy schedule pytest pytest-mock 2>/dev/null || \
    pip install faster-whisper openai Pillow pygame loguru python-dotenv requests sounddevice numpy pytest pytest-mock 2>/dev/null || \
    echo -e "${YELLOW}Manuelle Paketinstallation erforderlich${NC}"
fi

# 5. Konfigurationsdateien erstellen
echo "[5/9] Erstelle Konfigurationsdateien..."
mkdir -p "$INSTALL_DIR/config"
mkdir -p "$INSTALL_DIR/logs"
mkdir -p "$INSTALL_DIR/output"
mkdir -p "$INSTALL_DIR/models"

if [ ! -f "$INSTALL_DIR/config/.env" ]; then
    cp "$INSTALL_DIR/.env.template" "$INSTALL_DIR/config/.env"
    echo "config/.env erstellt - bitte API-Key eintragen!"
fi

# 6. Whisper-Modell herunterladen (bei Installation, NICHT lazy)
echo "[6/9] Lade Whisper-Modell (base) herunter..."
export PYTHONPATH="$INSTALL_DIR/src:$PYTHONPATH"

# Prüfe ob faster-whisper installiert ist
if python3 -c "from faster_whisper import WhisperModel" 2>/dev/null; then
    python3 -c "
from faster_whisper import WhisperModel
print('Lade Whisper base Modell...')
model = WhisperModel('base', device='cpu', compute_type='int8')
print('Whisper Modell bereit!')
"
    echo -e "${GREEN}Whisper Modell heruntergeladen${NC}"
else
    echo -e "${YELLOW}Whisper nicht verfügbar - wird beim ersten Start heruntergeladen${NC}"
fi

# 7. Audio-Quellen auflisten und Auswahl
echo "[7/9] Konfiguriere Audio-Quelle..."

# Prüfe auf --audio-source Parameter (ohne Installation nur Audio-Setup)
if [ "$1" = "--audio-source" ]; then
    echo "Starte Audio-Quellen Setup (ohne Installation)..."
    sudo "$INSTALL_DIR/src/setup_audio_source.sh"
    exit 0
fi

# Listet Geräte auf (ignoriere Fehler wenn nicht als Root)
"$INSTALL_DIR/src/audio_devices.sh" 2>/dev/null || true

# Interaktive Auswahl (nur wenn Audio-Geräte erkannt wurden)
if command -v arecord &> /dev/null && arecord -l &>/dev/null; then
    sudo "$INSTALL_DIR/src/setup_audio_source.sh" 2>/dev/null || true
else
    echo -e "${YELLOW}Keine Audio-Geräte erkannt - USB-Jabra nach Anschluss konfigurieren${NC}"
fi

# 8. OpenRouter API Key interaktiv abfragen
echo "[8/9] OpenRouter API Key..."
echo "Bitte gib deinen OpenRouter API Key ein:"
echo "Hole ihn von: https://openrouter.ai/keys"
read -r -p "API Key: " api_key

if [ -n "$api_key" ]; then
    if grep -q "OPENROUTER_API_KEY=" "$INSTALL_DIR/config/.env"; then
        sed -i "s|OPENROUTER_API_KEY=.*|OPENROUTER_API_KEY=$api_key|" "$INSTALL_DIR/config/.env"
    else
        echo "OPENROUTER_API_KEY=$api_key" >> "$INSTALL_DIR/config/.env"
    fi
    echo "API Key gespeichert"
else
    echo "Kein API Key eingegeben - bitte später in config/.env eintragen"
fi

# 9. Crontab einrichten
echo "[9/9] Richte Crontab ein..."
# Entferne alte crontab Einträge für PiListener
crontab_lines=$(crontab -l 2>/dev/null | grep -v "PiListener" || true)

# Füge neuen Eintrag hinzu (alle 5 Minuten für Test, kann in config auf 15 geändert werden)
new_cron="*/5 * * * * cd $INSTALL_DIR && .venv/bin/python src/main.py >> logs/listener.log 2>&1"

echo "$crontab_lines" | grep -v "^#" | grep -v "^$" > /tmp/current_cron 2>/dev/null || true
echo "$new_cron" >> /tmp/current_cron 2>/dev/null || true
echo "$new_cron" | crontab - 2>/dev/null || true

echo "Crontab aktualisiert (alle 5 Minuten)"

# Unclutter für Cursor verstecken starten
echo "Starte unclutter für Cursor-Verbergung..."
(sleep 2 && unclutter -idle 2 -root) &

# PulseAudio starten falls nicht aktiv
if ! pulseaudio --check 2>/dev/null; then
    echo "Starte PulseAudio..."
    pulseaudio --start 2>/dev/null || true
fi

echo ""
echo "=========================================="
echo "  Installation abgeschlossen!"
echo "=========================================="
echo ""
echo "Nächste Schritte:"
echo "1. Bearbeite $INSTALL_DIR/config/.env und trage OPENROUTER_API_KEY ein"
echo "2. Starte manuell mit: cd $INSTALL_DIR && .venv/bin/python src/main.py"
echo "3. Oder warte auf Crontab (alle 5 Minuten)"
echo ""
echo "Für manuellen Start ohne Crontab:"
echo "  cd $INSTALL_DIR && .venv/bin/python src/main.py"
echo ""
