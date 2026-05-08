#!/bin/bash
# Listet alle verfügbaren ALSA-Audioeingabegeräte auf
echo "=== Verfügbare Audio-Eingabegeräte ==="
arecord -l || echo "arecord nicht verfügbar"
echo ""
echo "=== PulseAudio Quellen ==="
pactl list sources short 2>/dev/null || echo "PulseAudio nicht verfügbar"
