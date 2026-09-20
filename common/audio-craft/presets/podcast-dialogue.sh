#!/usr/bin/env bash
# Preset: Generate a 2-speaker podcast dialogue using Gemini TTS
# Usage: ./presets/podcast-dialogue.sh [Topic]

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOPIC="${1:-"The fascinating discovery of water vapor in deep space exoplanet atmospheres"}"

echo "================================================================================"
echo "[Preset] Generating 2-Host Podcast Dialogue with Gemini 3.8 & Gemini TTS"
echo "Topic: $TOPIC"
echo "================================================================================"

"$DIR/gemini-audio" "$TOPIC" \
  --generate-script \
  --speakers "Dr. Maya:Zephyr,Leo:Puck" \
  -o "$DIR/outputs/podcast_dialogue.wav" \
  -y
