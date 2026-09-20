#!/usr/bin/env bash
# Preset: Generate Foley & Sound Effects (hits, kicks, roars, bird chirps, nature audio)
# Usage: ./presets/sound-effect.sh [Effect Description]

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EFFECT="${1:-"Cinematic action punch and kick impact, fast whooshing air slice followed by heavy sub-bass thud"}"

echo "================================================================================"
echo "[Preset] Synthesizing Sound Effect / Foley with Gemini 3.8 & Lyria"
echo "Effect: $EFFECT"
echo "================================================================================"

"$DIR/gemini-audio" "$EFFECT" \
  --sfx \
  --generate-prompt \
  -o "$DIR/outputs/sound_effect.mp3" \
  -y
