#!/bin/bash
# PiListener Easy Setup Wizard
# Interactive step-by-step setup with user-friendly prompts

set -euo pipefail

# Farben
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# Konfiguration
INSTALL_DIR="${PILISTENER_DIR:-$HOME/PiListener}"
VENV_DIR="$INSTALL_DIR/.venv"
CONFIG_FILE="$INSTALL_DIR/config/.env"
PYTHON="$VENV_DIR/bin/python3"
PIP="$VENV_DIR/bin/pip"

# Status
STEPS_DONE=0
TOTAL_STEPS=10

# Utils
step() {
    STEPS_DONE=$((STEPS_DONE + 1))
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════${NC}"
    echo -e "${CYAN}  [$STEPS_DONE/$TOTAL_STEPS] $1${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════${NC}"
}

info()    { echo -e "${BLUE}ℹ${NC} $1"; }
success(){ echo -e "${GREEN}✓${NC} $1"; }
warn()    { echo -e "${YELLOW}⚠${NC} $1"; }
error()   { echo -e "${RED}✗${NC} $1"; }

prompt() {
    local msg="$1"
    local var="$2"
    local default="${3:-}"
    echo ""
    if [ -n "$default" ]; then
        read -r -p "$msg [$default]: " "$var"
        [ -z "${!var}" ] && eval "$var=$default"
    else
        read -r -p "$msg: " "$var"
    fi
}

yes_no() {
    local msg="$1"
    local var="$2"
    local default="${3:-N}"
    local choices="[J/n]"
    [ "$default" = "N" ] && choices="[j/N]" || choices="[J/n]"
    read -r -p "$msg $choices: " "$var"
    eval "$var=\${${var}:-$default}"
    [[ "${!var}" =~ ^[Jj]$ ]]
}

pause() {
    echo ""
    read -r -p "Drücke Enter um fortzufahren..." dummy
}

is_venv_active() {
    $PYTHON -c "import sys; sys.exit(0 if hasattr(sys, 'real_prefix') or sys.prefix != sys.base_prefix else 1)" 2>/dev/null
}

activate_venv() {
    if ! is_venv_active; then
        source "$VENV_DIR/bin/activate" 2>/dev/null || true
    fi
}

cleanup() {
    tput cnorm 2>/dev/null || true
    # Resume cursor on exit
}
trap cleanup EXIT

#==========================================
# Willkommens-Bildschirm
#==========================================
show_welcome() {
    clear
    echo ""
    echo -e "${CYAN}    ╔═══════════════════════════════════╗${NC}"
    echo -e "${CYAN}    ║${NC}       ${BOLD}PiListener Setup Wizard${NC}       ${CYAN}║${NC}"
    echo -e "${CYAN}    ╚═══════════════════════════════════╝${NC}"
    echo ""
    echo -e "  ${BOLD}Willkommen!${NC}"
    echo "  Dieses Script führt dich durch die Einrichtung von PiListener."
    echo ""
    echo "  Was du brauchst:"
    echo "    • Raspberry Pi 4 (oder ähnlich mit mind. 4GB RAM)"
    echo "    • USB-Mikrofon (z.B. Jabra Speak 410/510)"
    echo "    • OpenRouter API Key (kostenlos bei openrouter.ai)"
    echo ""
    echo -e "  ${YELLOW}Hinweis: Admin-Rechte (sudo) werden benötigt.${NC}"
    echo ""
    info "Du kannst den Wizard jederzeit mit Strg+C abbrechen."
    pause
}

#==========================================
# Schritt 1: System-Prüfung
#==========================================
check_system() {
    step "System-Prüfung"
    echo ""

    # OS prüfen
    info "Prüfe Betriebssystem..."
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        case "$ID" in
            raspbian|debian|ubuntu)
                success "Betriebssystem: $PRETTY_NAME"
                ;;
            *)
                warn "Betriebssystem: $PRETTY_NAME (nicht offiziell unterstützt)"
                ;;
        esac
    else
        warn "Betriebssystem nicht erkannt"
    fi

    # Python prüfen
    info "Prüfe Python 3..."
    if command -v python3 &>/dev/null; then
        PYVER=$(python3 --version 2>&1 | cut -d' ' -f2)
        success "Python $PYVER gefunden"
    else
        error "Python 3 nicht gefunden!"
        echo "  Installiere mit:"
        echo "    sudo apt install python3 python3-pip python3-venv"
        exit 1
    fi

    # Python Version prüfen (min 3.8)
    PYVER_NUM=$(python3 -c 'import sys; print(sys.version_info.minor)')
    if [ "$PYVER_NUM" -lt 8 ]; then
        warn "Python 3.${PYVER_NUM} - empfohlen ist 3.8+"
    fi

    # Internet prüfen
    info "Prüfe Internet-Verbindung..."
    if curl -s --connect-timeout 3 openrouter.ai &>/dev/null; then
        success "Internet-Verbindung OK"
    else
        warn "Keine Internet-Verbindung"
        info "Wird für API-Key und Downloads benötigt"
    fi

    # Disk Space prüfen (min 2GB = 2048MB)
    info "Prüfe Festplatten-Platz..."
    FREE_MB=$(df -BM "$HOME" 2>/dev/null | tail -1 | awk '{print $4}' | sed 's/M//')
    if [ "${FREE_MB:-0}" -gt 2048 ]; then
        success "Freier Speicher: ${FREE_MB}MB"
    elif [ "${FREE_MB:-0}" -gt 1024 ]; then
        warn "Speicherplatz niedrig: ${FREE_MB}MB (empfohlen: >2048MB)"
    else
        error "Zu wenig Speicherplatz: ${FREE_MB}MB"
        exit 1
    fi

    # RAM prüfen
    info "Prüfe verfügbaren RAM..."
    AVAILABLE_MB=$(free -M 2>/dev/null | awk '/Mem:/ {print $7}' | sed 's/M//')
    if [ "${AVAILABLE_MB:-0}" -gt 1500 ]; then
        success "Verfügbarer RAM: ${AVAILABLE_MB}MB"
    elif [ "${AVAILABLE_MB:-0}" -gt 800 ]; then
        warn "RAM niedrig: ${AVAILABLE_MB}MB (empfohlen: >1500MB)"
    else
        warn "RAM sehr niedrig: ${AVAILABLE_MB}MB"
    fi
}

#==========================================
# Schritt 2: Verzeichnis erstellen
#==========================================
setup_directories() {
    step "Verzeichnis-Struktur erstellen"
    echo ""

    INSTALLED=false
    if [ -d "$INSTALL_DIR" ] && [ -f "$INSTALL_DIR/src/main.py" ]; then
        info "PiListener bereits installiert: $INSTALL_DIR"
        if yes_no "Neu installieren?" confirm "N"; then
            rm -rf "$INSTALL_DIR"
            info "Alte Installation entfernt"
        else
            INSTALLED=true
        fi
    fi

    if [ "$INSTALLED" = false ]; then
        info "Erstelle Verzeichnis-Struktur..."
        mkdir -p "$INSTALL_DIR/config"
        mkdir -p "$INSTALL_DIR/logs"
        mkdir -p "$INSTALL_DIR/output"
        mkdir -p "$INSTALL_DIR/models"
        success "Verzeichnisse erstellt"

        if [ -f "$INSTALL_DIR/.env.template" ] && [ ! -f "$CONFIG_FILE" ]; then
            cp "$INSTALL_DIR/.env.template" "$CONFIG_FILE"
            success "config/.env aus Template erstellt"
        fi
    fi
}

#==========================================
# Schritt 3: System-Pakete
#==========================================
install_system_packages() {
    step "System-Pakete installieren"
    echo ""

    info "Aktualisiere Paketquellen (kann eine Minute dauern)..."
    sudo apt-get update -qq 2>&1 | grep -v "^Get:" | grep -v "^Hit:" || true

    info "Installiere System-Pakete..."
    PKGS="python3 python3-pip python3-venv python3-dev git ffmpeg libasound2-dev"

    # Flexible PortAudio Pakete
    for pkg_combo in \
        "portaudio19-dev" \
        "portaudio19-dev libportaudio2" \
        "portaudio19-dev libportaudiocpp0" \
        "portaudio-all-dev"; do
        if apt-cache show $pkg_combo &>/dev/null 2>&1; then
            PKGS="$PKGS $pkg_combo"
            break
        fi
    done

    # Unclutter + X11
    PKGS="$PKGS unclutter x11-xserver-utils"

    sudo apt-get install -y $PKGS 2>&1 | tail -5
    success "System-Pakete installiert"

    # PulseAudio starten falls nicht aktiv
    if ! pulseaudio --check 2>/dev/null; then
        info "Starte PulseAudio..."
        pulseaudio --start 2>/dev/null || true
    fi
}

#==========================================
# Schritt 4: Python Virtual Environment
#==========================================
setup_venv() {
    step "Python Virtual Environment"
    echo ""

    if [ -d "$VENV_DIR" ]; then
        info "Virtual Environment existiert bereits"
        if yes_no "Neu erstellen?" confirm "N"; then
            rm -rf "$VENV_DIR"
            info "Altes venv entfernt"
        fi
    fi

    if [ ! -d "$VENV_DIR" ]; then
        info "Erstelle Virtual Environment..."
        python3 -m venv "$VENV_DIR"
        success "Virtual Environment erstellt"
    fi

    info "Aktualisiere pip und setuptools..."
    $PIP install --upgrade pip setuptools wheel -q 2>/dev/null
    success "pip und setuptools aktualisiert"
}

#==========================================
# Schritt 5: Python-Pakete
#==========================================
install_python_packages() {
    step "Python-Pakete installieren"
    echo ""

    activate_venv

    info "Installiere Python-Pakete..."
    info "Dies kann 5-10 Minuten dauern (erste Installation)..."
    echo ""

    # Pakete in Blöcken installieren für besseres Feedback
    CORE_PKGS=(
        "loguru>=0.7.0"
        "python-dotenv>=1.0.0"
        "requests>=2.31.0"
        "numpy>=1.26.0"
    )

    AUDIO_PKGS=(
        "sounddevice>=0.4.0"
    )

    ML_PKGS=(
        "faster-whisper>=1.0.0"
    )

    IMG_PKGS=(
        "Pillow>=10.0.0"
        "openai>=1.0.0"
    )

    UI_PKGS=(
        "pygame>=2.5.0"
    )

    TEST_PKGS=(
        "pytest>=8.0.0"
        "pytest-mock>=3.12.0"
    )

    install_pkg_group() {
        local group_name="$1"
        shift
        local pkgs=("$@")
        echo -e "${CYAN}  → $group_name${NC}"

        for pkg in "${pkgs[@]}"; do
            pkg_name="${pkg%%[=><]*}"
            printf "    %-25s" "$pkg_name..."
            if $PIP install "$pkg" -q 2>/dev/null; then
                echo -e "\r    ${GREEN}✓${NC} $pkg_name"
            else
                echo -e "\r    ${YELLOW}⚠${NC} $pkg_name"
            fi
        done
    }

    install_pkg_group "Core" "${CORE_PKGS[@]}"
    install_pkg_group "Audio" "${AUDIO_PKGS[@]}"
    install_pkg_group "ML/AI" "${ML_PKGS[@]}"
    install_pkg_group "Image" "${IMG_PKGS[@]}"
    install_pkg_group "UI" "${UI_PKGS[@]}"
    install_pkg_group "Testing" "${TEST_PKGS[@]}"

    success "Python-Pakete installiert"
}

#==========================================
# Schritt 6: Audio-Geräte
#==========================================
setup_audio() {
    step "Audio-Gerät konfigurieren"
    echo ""

    # Zeige verfügbare Geräte
    echo -e "${CYAN}=== Verfügbare Audio-Geräte ===${NC}"
    echo ""

    if command -v arecord &>/dev/null; then
        echo -e "${BOLD}ALSA Input Devices:${NC}"
        arecord -l 2>/dev/null || echo "  (keine ALSA-Geräte)"
    fi

    if command -v pactl &>/dev/null; then
        echo ""
        echo -e "${BOLD}PulseAudio Sources:${NC}"
        pactl list sources short 2>/dev/null || echo "  (keine PulseAudio-Quellen)"
    fi

    echo ""
    echo -e "${BOLD}USB Audio Devices:${NC}"
    lsusb 2>/dev/null | grep -i -E "audio|sound|mic|speak|jabra|usb|cmedia" || echo "  (keine USB-Audiogeräte via lsusb)"

    echo ""

    # Auto-Detection
    info "Suche Jabra/USB Mikrofone..."

    activate_venv
    export PYTHONPATH="$INSTALL_DIR/src"

    DETECTED=""
    if $PYTHON -c "
import sys, os
sys.path.insert(0, '$INSTALL_DIR/src')
os.environ['PYTHONPATH'] = '$INSTALL_DIR/src'
try:
    from listener import AudioListener
    listener = AudioListener()
    dev = listener.device
    if dev is not None:
        print(dev)
except Exception as e:
    print('ERROR:', e, file=sys.stderr)
" 2>/dev/null | grep -v ERROR | grep -v Error >/dev/null; then
        DETECTED=$($PYTHON -c "
import sys, os
sys.path.insert(0, '$INSTALL_DIR/src')
os.environ['PYTHONPATH'] = '$INSTALL_DIR/src'
from listener import AudioListener
listener = AudioListener()
print(listener.device if listener.device is not None else 'default')
" 2>/dev/null)
    fi

    if [ -n "$DETECTED" ] && [ "$DETECTED" != "default" ]; then
        success "Auto-detected: $DETECTED"
        DEFAULT_CHOICE=1
    else
        warn "Kein Gerät automatisch erkannt"
        DEFAULT_CHOICE=1
    fi

    # Auswahl
    echo ""
    echo -e "${BOLD}Wähle dein Audio-Gerät:${NC}"
    echo "  1) Jabra Speak (Standard: hw:CARD=Speak,DEV=0)"
    echo "  2) anderes USB-Mikrofon (Index eingeben)"
    echo "  3) ALSA Device String manuell (z.B. hw:CARD=0,DEV=0)"
    echo "  4) Überspringen (später in config/.env konfigurieren)"
    read -r -p "> Auswahl [1]: " choice
    choice="${choice:-1}"

    case "$choice" in
        1|"")
            AUDIO_SOURCE="hw:CARD=Speak,DEV=0"
            ;;
        2)
            echo "Gib den Device-Index oder Namen ein:"
            read -r -p "> " AUDIO_SOURCE
            ;;
        3)
            echo "Gib den ALSA Device-String ein:"
            read -r -p "> " AUDIO_SOURCE
            ;;
        4)
            info "Übersprungen - bitte später konfigurieren"
            AUDIO_SOURCE="hw:CARD=Speak,DEV=0"
            ;;
        *)
            AUDIO_SOURCE="hw:CARD=Speak,DEV=0"
            ;;
    esac

    # Speichere
    if grep -q "^AUDIO_SOURCE=" "$CONFIG_FILE" 2>/dev/null; then
        sed -i "s|^AUDIO_SOURCE=.*|AUDIO_SOURCE=$AUDIO_SOURCE|" "$CONFIG_FILE"
    else
        echo "AUDIO_SOURCE=$AUDIO_SOURCE" >> "$CONFIG_FILE"
    fi

    success "Audio konfiguriert: $AUDIO_SOURCE"
}

#==========================================
# Schritt 7: OpenRouter API Key
#==========================================
setup_api_key() {
    step "OpenRouter API Key"
    echo ""

    # Prüfe vorhandenen Key
    EXISTING_KEY=""
    if grep -q "^OPENROUTER_API_KEY=sk-" "$CONFIG_FILE" 2>/dev/null; then
        EXISTING_KEY=$(grep "^OPENROUTER_API_KEY=" "$CONFIG_FILE" | cut -d'=' -f2 | cut -c1-15)
        info "Vorhandener Key gefunden: ${EXISTING_KEY}..."
        EXISTING_KEY="${EXISTING_KEY:0:15}..."
    fi

    if [ -n "$EXISTING_KEY" ]; then
        if yes_no "API-Key neu eingeben?" confirm "N"; then
            prompt "OpenRouter API Key (sk-...)" API_KEY
        else
            info "Behalte vorhandenen Key"
            return 0
        fi
    else
        echo -e "${BOLD}Du brauchst einen OpenRouter API Key:${NC}"
        echo "  1. Gehe zu https://openrouter.ai/keys"
        echo "  2. Registriere dich (kostenlos)"
        echo "  3. Erstelle einen neuen API Key"
        echo "  4. Kopiere ihn hierher"
        echo ""
        prompt "OpenRouter API Key" API_KEY
    fi

    if [ -n "$API_KEY" ] && [[ "$API_KEY" == sk-* ]]; then
        if grep -q "^OPENROUTER_API_KEY=" "$CONFIG_FILE" 2>/dev/null; then
            sed -i "s|^OPENROUTER_API_KEY=.*|OPENROUTER_API_KEY=$API_KEY|" "$CONFIG_FILE"
        else
            echo "OPENROUTER_API_KEY=$API_KEY" >> "$CONFIG_FILE"
        fi
        success "API-Key gespeichert"
    else
        warn "Ungültiger oder leerer API-Key"
        info "Du kannst ihn später in $CONFIG_FILE eintragen"
    fi
}

#==========================================
# Schritt 8: Whisper Modell
#==========================================
download_whisper_model() {
    step "Whisper Modell herunterladen"
    echo ""

    activate_venv
    export PYTHONPATH="$INSTALL_DIR/src"

    info "Lade Whisper base Modell herunter (ca. 140MB)..."
    info "Dies dauert einige Minuten (einmalig)..."
    echo ""

    WHISPER_LOG="/tmp/whisper_download_$$.log"

    if $PYTHON -c "
import sys, os
sys.path.insert(0, '$INSTALL_DIR/src')
os.environ['PYTHONPATH'] = '$INSTALL_DIR/src'
print('Download gestartet...')
sys.stdout.flush()
from faster_whisper import WhisperModel
model = WhisperModel('base', device='cpu', compute_type='int8', download_root='$INSTALL_DIR/models')
print('MODELL_OK')
" 2>&1 | tee "$WHISPER_LOG"; then
        if grep -q "MODELL_OK" "$WHISPER_LOG"; then
            success "Whisper Modell heruntergeladen und bereit"
        else
            warn "Modell konnte nicht verifiziert werden"
            info "Es wird beim ersten Start automatisch geladen"
        fi
    else
        warn "Whisper Modell Installation fehlgeschlagen"
        info "Das Modell wird beim ersten Start heruntergeladen"
    fi
    rm -f "$WHISPER_LOG"
}

#==========================================
# Schritt 9: Test-Aufnahme
#==========================================
test_recording() {
    step "Test-Aufnahme"
    echo ""

    activate_venv
    export PYTHONPATH="$INSTALL_DIR/src"

    info "Wir nehmen jetzt 3 Sekunden Audio auf..."
    info "Sprich bitte deutlich in dein Mikrofon!"
    echo ""
    read -r -p "Drücke Enter um die Aufnahme zu starten..." dummy

    info "Rekorde..."

    AUDIO_LOG="/tmp/audio_test_$$.log"

    $PYTHON -c "
import sys, os, numpy as np
sys.path.insert(0, '$INSTALL_DIR/src')
os.environ['PYTHONPATH'] = '$INSTALL_DIR/src'
os.environ['SDL_AUDIODRIVER'] = 'dummy'

import sounddevice as sd

try:
    recording = sd.rec(int(3 * 16000), samplerate=16000, channels=1, dtype='int16')
    sd.wait()
    samples = recording.flatten().astype(np.float32) / 32768.0
    rms = np.sqrt(np.mean(samples ** 2))
    db = 20 * np.log10(rms) if rms > 0 else -np.inf
    print(f'RMS-Pegel: {db:.1f} dB')
    if db > -40:
        print('TEST_OK')
    else:
        print('TEST_LOW')
except Exception as e:
    print(f'FEHLER: {e}', file=sys.stderr)
    sys.exit(1)
" 2>&1 | tee "$AUDIO_LOG"

    if grep -q "TEST_OK" "$AUDIO_LOG"; then
        success "Audio-Test erfolgreich!"
    elif grep -q "TEST_LOW" "$AUDIO_LOG"; then
        warn "Mikrofon funktioniert, aber Signal ist leise"
        info "Prüfe ob das Mikrofon richtig erkannt ist und die Lautstärke reicht"
    else
        warn "Audio-Test fehlgeschlagen"
        info "Prüfe die Kabelverbindung und ob das Mikrofon als Standard-Aufnahmegerät eingestellt ist"
    fi
    rm -f "$AUDIO_LOG"
}

#==========================================
# Schritt 10: Finale
#==========================================
finalize() {
    step "Finalisierung"
    echo ""

    # Crontab
    info "Richte Crontab ein (alle 15 Minuten)..."
    CRON_LINE="*/15 * * * * cd $INSTALL_DIR && .venv/bin/python src/main.py >> logs/listener.log 2>&1"

    # Entferne alte PiListener Einträge und füge neuen hinzu
    (crontab -l 2>/dev/null | grep -v "PiListener" || true) > /tmp/current_cron
    echo "$CRON_LINE" >> /tmp/current_cron
    crontab /tmp/current_cron 2>/dev/null || true
    rm -f /tmp/current_cron
    success "Crontab eingerichtet"

    # Unclutter starten
    if ! pgrep -x unclutter > /dev/null; then
        (unclutter -idle 2 -root &) 2>/dev/null || true
        info "Unclutter gestartet (Cursor wird versteckt)"
    fi

    # Zeige Config
    echo ""
    info "Aktuelle Konfiguration:"
    echo ""
    if [ -f "$CONFIG_FILE" ]; then
        while IFS= read -r line; do
            if [[ "$line" =~ ^OPENROUTER_API_KEY= ]]; then
                masked="${line:0:20}..."
                echo "  $masked"
            else
                echo "  $line"
            fi
        done < "$CONFIG_FILE"
    else
        echo "  (keine Config gefunden)"
    fi
    echo ""

    # Summary
    echo -e "${CYAN}═══════════════════════════════════════════${NC}"
    echo -e "${CYAN}  ${BOLD}Setup abgeschlossen!${NC}${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════${NC}"
    echo ""
    echo -e "${GREEN}Nächste Schritte:${NC}"
    echo ""
    echo "  1. PiListener manuell starten:"
    echo -e "     ${CYAN}cd $INSTALL_DIR && .venv/bin/python src/main.py${NC}"
    echo ""
    echo "  2. Web-Interface (nach Start):"
    echo -e "     ${CYAN}http://localhost:8000${NC}"
    echo ""
    echo "  3. Logs anzeigen:"
    echo -e "     ${CYAN}tail -f $INSTALL_DIR/logs/listener.log${NC}"
    echo ""
    echo "  4. Konfiguration bearbeiten:"
    echo -e "     ${CYAN}nano $CONFIG_FILE${NC}"
    echo ""

    if yes_no "PiListener jetzt starten?" confirm "J"; then
        info "Starte PiListener (Strg+C zum Beenden)..."
        cd "$INSTALL_DIR"
        activate_venv
        export PYTHONPATH="$INSTALL_DIR/src"
        $PYTHON src/main.py
    else
        info "Bis zum nächsten Mal!"
    fi
}

#==========================================
# MAIN
#==========================================
main() {
    tput civis 2>/dev/null || true

    show_welcome
    check_system
    setup_directories
    install_system_packages
    setup_venv
    install_python_packages
    setup_audio
    setup_api_key
    download_whisper_model
    test_recording
    finalize

    tput cnorm 2>/dev/null || true
}

main "$@"