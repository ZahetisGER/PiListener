#!/bin/bash
# PiListener Installations-Script
# One-Line Installer: curl -sSL https://raw.githubusercontent.com/GITHUB_USER/PiListener/main/install.sh | bash

set -e

REPO_URL="https://github.com/GITHUB_USER/PiListener.git"
INSTALL_DIR="$HOME/PiListener"
VENV_DIR="$INSTALL_DIR/.venv"

echo "=========================================="
echo "  PiListener Installation"
echo "=========================================="

# 1. System-Pakete installieren
echo "[1/9] Installiere System-Pakete..."
sudo apt-get update
sudo apt-get install -y \
    python3 python3-pip python3-venv python3-dev git ffmpeg \
    libasound2-dev libportaudio2 libportaudiocpp0 portaudio19-dev \
    x11-xserver-utils unclutter pulseaudio

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
pip install --upgrade pip
pip install -r requirements.txt

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
python3 -c "
from faster_whisper import WhisperModel
print('Lade Whisper base Modell...')
model = WhisperModel('base', device='cpu', compute_type='int8')
print('Whisper Modell bereit!')
"

# 7. Audio-Quellen auflisten und Auswahl
echo "[7/9] Konfiguriere Audio-Quelle..."

# Prüfe auf --audio-source Parameter (ohne Installation nur Audio-Setup)
if [ "$1" = "--audio-source" ]; then
    echo "Starte Audio-Quellen Setup (ohne Installation)..."
    sudo "$INSTALL_DIR/src/setup_audio_source.sh"
    exit 0
fi

# Listet Geräte auf
"$INSTALL_DIR/src/audio_devices.sh"

# Interaktive Auswahl
sudo "$INSTALL_DIR/src/setup_audio_source.sh"

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
