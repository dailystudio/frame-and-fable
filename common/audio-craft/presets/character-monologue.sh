#!/usr/bin/env bash
# Preset: Generate a dramatic character monologue with expressive audio tags
# Usage: ./presets/character-monologue.sh [Prompt or Topic]

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROMPT="${1:-"An ancient wizard warning young adventurers about the sleeping dragon in the volcano"}"

echo "================================================================================"
echo "[Preset] Generating Character Performance Monologue"
echo "Concept: $PROMPT"
echo "================================================================================"

"$DIR/gemini-audio" "$PROMPT" \
  --generate-script \
  -v Algenib \
  -o "$DIR/outputs/character_monologue.wav" \
  -y
