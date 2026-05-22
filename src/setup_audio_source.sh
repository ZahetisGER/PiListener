#!/bin/bash
# Interaktives Script zur Audio-Quellen-Auswahl für PiListener
# Mit USB/Jabra Auto-Detection und Hotplug-Unterstützung
# Verwendung: sudo ./setup_audio_source.sh [--device N | --name "Name"]
# Als Root oder mit sudo ausführbar (für ALSA Zugriff)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CONFIG_FILE="$PROJECT_DIR/config/.env"

# Standardwerte
SELECTED_DEVICE=""
DEVICE_NAME=""
AUTO_DETECT=true

# Hilfe anzeigen
show_help() {
    echo "Verwendung: $0 [OPTIONEN]"
    echo ""
    echo "Optionen:"
    echo "  --device N    Wähle Device Nummer N (von arecord -l)"
    echo "  --name NAME  Wähle Device nach Name (Teilstring)"
    echo "  --no-auto    Deaktiviert Auto-Detection für Jabra/USB"
    echo "  --help       Diese Hilfe anzeigen"
    echo ""
    echo "Ohne Optionen: Interaktiver Modus mit Auto-Detection"
    exit 0
}

# Argumente parsen
while [[ $# -gt 0 ]]; do
    case $1 in
        --device)
            SELECTED_DEVICE="$2"
            AUTO_DETECT=false
            shift 2
            ;;
        --name)
            DEVICE_NAME="$2"
            AUTO_DETECT=false
            shift 2
            ;;
        --no-auto)
            AUTO_DETECT=false
            ;;
        --help)
            show_help
            ;;
        *)
            echo "Unbekannte Option: $1"
            show_help
            ;;
    esac
done

# Farben für Ausgabe
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "=========================================="
echo "  PiListener Audio-Quellen Setup"
echo "=========================================="
echo ""

# Prüfe ob ALSA Tools verfügbar
if ! command -v arecord &> /dev/null; then
    echo -e "${RED}Fehler: arecord nicht verfügbar${NC}"
    echo "Bitte installiere alsa-utils: sudo apt-get install alsa-utils"
    exit 1
fi

# Sammle Geräte
echo "Sammle verfügbare Audio-Eingabegeräte..."
echo ""

# ALSA Geräte parsen
declare -a ALSADEVICES
declare -a ALSADEVINFO
ALSALINES=()

while IFS= read -r line; do
    ALSALINES+=("$line")
done < <(arecord -l 2>/dev/null || true)

# PulseAudio Quellen sammeln
PULSEDEVICES=()
while IFS= read -r line; do
    PULSEDEVICES+=("$line")
done < <(pactl list sources short 2>/dev/null || true)

# Keine Geräte gefunden
if [ ${#ALSALINES[@]} -eq 0 ] && [ ${#PULSEDEVICES[@]} -eq 0 ]; then
    echo -e "${YELLOW}Keine Audio-Eingabegeräte gefunden${NC}"
    echo "Bitte prüfe ob Mikrofone angeschlossen und aktiviert sind."
    echo ""
    echo "Tipps:"
    echo "  - USB Geräte erst nach dem Anstecken konfigurieren"
    echo "  - Bei Jabra: LED muss leuchten (nicht blinken)"
    echo "  - Kernel Module prüfen: lsmod | grep snd"
    exit 1
fi

# Auto-Detection für Jabra/USB
auto_detect_jabra() {
    local found=false
    while IFS= read -r line; do
        if [[ $line =~ ^card\ ([0-9]+):.*device\ ([0-9]+):.*\[([^\]]+)\] ]]; then
            CARD_NUM="${BASH_REMATCH[1]}"
            DEV_NUM="${BASH_REMATCH[2]}"
            DEV_NAME="${BASH_REMATCH[3]}"
            DEVICE_STR="hw:CARD=$CARD_NUM,DEV=$DEV_NUM"

            local name_lower=$(echo "$DEV_NAME" | tr '[:upper:]' '[:lower:]')

            # Jabra Erkennung
            if [[ "$name_lower" == *"jabra"* ]] || [[ "$name_lower" == *"speak"* ]]; then
                echo -e "${GREEN}✓ Jabra/Speak erkannt: $DEV_NAME${NC}"
                echo "  → Device: $DEVICE_STR"
                ALSADEVICES+=("$DEVICE_STR")
                ALSADEVINFO+=("Jabra/Speak: $DEV_NAME")
                found=true
            fi
        fi
    done < <(arecord -l 2>/dev/null || true)

    # USB Audio Erkennung (als Fallback)
    if [ "$found" = false ]; then
        while IFS= read -r line; do
            if [[ $line =~ ^card\ ([0-9]+):.*device\ ([0-9]+):.*\[([^\]]+)\] ]]; then
                CARD_NUM="${BASH_REMATCH[1]}"
                DEV_NUM="${BASH_REMATCH[2]}"
                DEV_NAME="${BASH_REMATCH[3]}"
                DEVICE_STR="hw:CARD=$CARD_NUM,DEV=$DEV_NUM"

                local name_lower=$(echo "$DEV_NAME" | tr '[:upper:]' '[:lower:]')

                # USB Patterns
                if [[ "$name_lower" == *"usb"* ]] || [[ "$name_lower" == *"cm108"* ]] ||
                   [[ "$name_lower" == *"cm119"* ]] || [[ "$name_lower" == *"burr-brown"* ]]; then
                    echo -e "${BLUE}○ USB Audio erkannt: $DEV_NAME${NC}"
                    echo "  → Device: $DEVICE_STR"
                    ALSADEVICES+=("$DEVICE_STR")
                    ALSADEVINFO+=("USB Audio: $DEV_NAME")
                    found=true
                fi
            fi
        done < <(arecord -l 2>/dev/null || true)
    fi

    echo "$found"
}

# Device nach Nummer auswählen
if [ -n "$SELECTED_DEVICE" ]; then
    CARD_NUM=""
    DEV_NUM="$SELECTED_DEVICE"

    IDX=0
    while IFS= read -r line; do
        if [[ $line =~ ^card\ ([0-9]+):.*device\ ([0-9]+): ]]; then
            if [ "$IDX" -eq "$SELECTED_DEVICE" ]; then
                CARD_NUM="${BASH_REMATCH[1]}"
                DEV_NUM="${BASH_REMATCH[2]}"
                break
            fi
            ((IDX++))
        fi
    done < <(arecord -l 2>/dev/null || true)

    if [ -z "$CARD_NUM" ]; then
        echo -e "${RED}Device $SELECTED_DEVICE nicht gefunden${NC}"
        exit 1
    fi

    AUDIO_SOURCE="hw:CARD=$CARD_NUM,DEV=$DEV_NUM"
    echo -e "${GREEN}Ausgewählt: $AUDIO_SOURCE${NC}"

# Device nach Name auswählen
elif [ -n "$DEVICE_NAME" ]; then
    FOUND=false
    while IFS= read -r line; do
        if [[ $line =~ ^card\ ([0-9]+):.*device\ ([0-9]+):.*\[([^\]]+)\] ]]; then
            CARD_NUM="${BASH_REMATCH[1]}"
            DEV_NUM="${BASH_REMATCH[2]}"
            DEV_NAME="${BASH_REMATCH[3]}"

            if [[ "$DEV_NAME" == *"$DEVICE_NAME"* ]]; then
                AUDIO_SOURCE="hw:CARD=$CARD_NUM,DEV=$DEV_NUM"
                echo -e "${GREEN}Gefunden: $AUDIO_SOURCE ($DEV_NAME)${NC}"
                FOUND=true
                break
            fi
        fi
    done < <(arecord -l 2>/dev/null || true)

    if [ "$FOUND" = false ]; then
        echo -e "${RED}Kein Device mit Name '$DEVICE_NAME' gefunden${NC}"
        exit 1
    fi

# Interaktiver/Auto-Detection Modus
else
    echo "=== Verfügbare Audio-Eingabegeräte ==="
    echo ""

    IDX=0
    while IFS= read -r line; do
        if [[ $line =~ ^card\ ([0-9]+):.*device\ ([0-9]+):.*\[([^\]]+)\] ]]; then
            CARD_NUM="${BASH_REMATCH[1]}"
            DEV_NUM="${BASH_REMATCH[2]}"
            DEV_NAME="${BASH_REMATCH[3]}"

            DEVICE_STR="hw:CARD=$CARD_NUM,DEV=$DEV_NUM"
            echo -e "  [$IDX] $DEVICE_STR"
            echo "      $DEV_NAME"

            ALSADEVICES+=("$DEVICE_STR")
            ((IDX++))
        fi
    done < <(arecord -l 2>/dev/null || true)

    echo ""
    echo "=== PulseAudio Quellen ==="
    while IFS= read -r line; do
        echo "  $line"
    done < <(pactl list sources short 2>/dev/null || true)
    echo ""

    # Auto-Detection
    if [ "$AUTO_DETECT" = true ]; then
        echo -e "${YELLOW}Prüfe auf Jabra/USB Geräte...${NC}"
        auto_detect_jabra
        echo ""
    fi

    echo -e "${YELLOW}Bitte wähle dein Audio Device:${NC}"
    echo -e "Drücke Enter für${GREEN} Standard (Jabra hw:CARD=Speak,DEV=0)${NC}"

    if [ ${#ALSADEVICES[@]} -gt 0 ]; then
        echo -e "(${GREEN}0-${#ALSADEVICES[@]}${NC} für ALSA Device)"
    fi
    read -r -p "> " choice

    if [ -z "$choice" ]; then
        AUDIO_SOURCE="hw:CARD=Speak,DEV=0"
        echo -e "${GREEN}Standard verwendet: $AUDIO_SOURCE${NC}"
    else
        if [ "$choice" -ge 0 ] && [ "$choice" -lt ${#ALSADEVICES[@]} ]; then
            AUDIO_SOURCE="${ALSADEVICES[$choice]}"
            echo -e "${GREEN}Ausgewählt: $AUDIO_SOURCE${NC}"
        else
            echo -e "${RED}Ungültige Auswahl${NC}"
            exit 1
        fi
    fi
fi

# In .env speichern
echo ""
echo "Speichere Auswahl in $CONFIG_FILE..."

# Erstelle config Verzeichnis falls nötig
mkdir -p "$(dirname "$CONFIG_FILE")"

# Aktualisiere oder füge AUDIO_SOURCE hinzu
if [ -f "$CONFIG_FILE" ]; then
    if grep -q "^AUDIO_SOURCE=" "$CONFIG_FILE"; then
        sed -i "s|^AUDIO_SOURCE=.*|AUDIO_SOURCE=$AUDIO_SOURCE|" "$CONFIG_FILE"
    else
        echo "AUDIO_SOURCE=$AUDIO_SOURCE" >> "$CONFIG_FILE"
    fi
else
    echo "AUDIO_SOURCE=$AUDIO_SOURCE" > "$CONFIG_FILE"
fi

echo -e "${GREEN}Audio-Quelle konfiguriert: $AUDIO_SOURCE${NC}"
echo ""
