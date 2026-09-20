#!/usr/bin/env bash
# Preset: Compose a soundtrack inspired by a reference artwork/image
# Usage: ./presets/music-from-image.sh <image_path> [style_description]

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="$1"
STYLE="${2:-"An evocative, atmospheric ambient soundtrack capturing the emotional tone and colors of this visual artwork"}"

if [ -z "$IMAGE" ] || [ ! -f "$IMAGE" ]; then
  echo "Usage: ./presets/music-from-image.sh <image_path> [style_description]"
  echo "Error: Reference image file '$IMAGE' not found."
  exit 1
fi

echo "================================================================================"
echo "[Preset] Composing Music from Reference Image with Lyria 3.5"
echo "Image: $IMAGE"
echo "Style: $STYLE"
echo "================================================================================"

"$DIR/gemini-audio" "$STYLE" \
  --music \
  -i "$IMAGE" \
  -o "$DIR/outputs/image_inspired_track.mp3"
