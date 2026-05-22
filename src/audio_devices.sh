#!/bin/bash
# Listet alle verfügbaren Audioeingabegeräte auf (ALSA + PulseAudio)
# Mit USB/Jabra Erkennung

echo "=== PiListener Audio Device Scanner ==="
echo ""

echo "=== ALSA Input Devices (arecord -l) ==="
arecord -l 2>/dev/null || echo "arecord nicht verfügbar"
echo ""

echo "=== ALSA alle Devices (aplay -l) ==="
aplay -l 2>/dev/null || echo "aplay nicht verfügbar"
echo ""

echo "=== PulseAudio Sources ==="
pactl list sources short 2>/dev/null || echo "PulseAudio nicht verfügbar"
echo ""

echo "=== USB Devices (lsusb) ==="
lsusb 2>/dev/null | grep -i -E "audio|sound|mic|speak|jabra|usb" || echo "lsusb nicht verfügbar oder keine USB Audio Geräte gefunden"
echo ""

echo "=== Kernel Audio Modules ==="
lsmod 2>/dev/null | grep -i -E "snd|audio|sound" || echo "Keine Audio Module geladen"
echo ""
