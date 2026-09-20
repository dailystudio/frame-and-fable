#!/usr/bin/env bash
# Preset: Generate an epic cinematic orchestral score using Lyria 3.5
# Usage: ./presets/cinematic-soundtrack.sh [Theme or Description]

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
THEME="${1:-"An epic fantasy orchestral battle theme, building from brooding low strings and horns into thundering percussion and soaring heroic brass climax"}"

echo "================================================================================"
echo "[Preset] Composing Cinematic Soundtrack with Lyria 3.5"
echo "Theme: $THEME"
echo "================================================================================"

"$DIR/gemini-audio" "$THEME" \
  --music \
  -m lyria-3.5 \
  -o "$DIR/outputs/cinematic_soundtrack.mp3"
