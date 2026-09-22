---
name: video-craft
description: Generates high-fidelity cinematic videos with synchronized audio using Google Veo (Veo 3.1 & Veo 3) via the gemini-video CLI. Use when asked to create videos from text prompts, animate still images into videos, interpolate between first and last keyframes, generate cinematic transitions, or use reference images for character and style consistency.
metadata:
  author: Frame & Fable
  keywords:
    - video-craft
    - gemini-video
    - veo
    - text-to-video
    - image-to-video
    - video-generation
    - keyframe-interpolation
    - cinematic
    - synchronized-audio
---

# Video Craft (`video-craft` / `gemini-video`)

`video-craft` provides cinematic AI video generation powered by Google Veo (Veo 3.1 & Veo 3 models). It supports native synchronized audio (speech, sound effects, ambience), reference image conditioning (subject assets and visual styles), image-to-video animation, first-to-last keyframe interpolation, and Gemini 3.8 Flash multimodal vision prompt optimization.

---

## 1. Quick Command Overview

When installed system-wide, the CLI is accessible anywhere via `gemini-video` or `video-craft`:

```bash
# Global CLI command (in PATH):
gemini-video [OPTIONS]
# or
video-craft [OPTIONS]

# System-wide venv fallback:
~/.local/share/frame-and-fable/venvs/video-craft/bin/python \
  /Volumes/Workspace/gitrepos/dailystudio/frame-and-fable/common/video-craft/gemini-video.py [OPTIONS]
```

### Environment Setup
```bash
export GEMINI_API_KEY="your-gemini-api-key"
```

---

## 2. Key Capabilities & Usage Workflows

### A. Text-to-Video Generation

Generate videos with cinematic camera motion, realistic lighting, and native audio:
```bash
# Standard widescreen 1080p generation with native audio:
gemini-video \
  --prompt "Cinematic wide drone shot of a misty emerald fjord at sunrise, gentle water ripples, high realism" \
  -r 16:9 \
  -s 1080p \
  -d 8s \
  -o fjord_sunrise.mp4

# Vertical 9:16 video for mobile / social shorts:
gemini-video \
  --prompt "A cyberpunk courier racing on a neon lightcycle through heavy rain in Neo-Tokyo" \
  -r 9:16 \
  -s 720p \
  -d 6s \
  -o lightcycle.mp4
```

---

### B. Reference Images for Asset & Style Consistency

Condition character design and artistic style using up to 3 reference images:
```bash
# Guide subject character and artistic style:
gemini-video \
  --prompt "The warrior unsheathes his katana as lightning flashes across the temple courtyard" \
  --ref-asset warrior_character.png \
  --ref-style anime_aesthetic.png \
  -o warrior_lightning.mp4
```

---

### C. Image-to-Video Animation (`--start-frame`)

Animate a static image into a living scene:
```bash
gemini-video \
  --prompt "The cherry blossom petals begin dancing in the gentle mountain breeze" \
  --start-frame serene_temple.png \
  -o temple_animated.mp4
```

---

### D. Keyframe Interpolation (`--start-frame` & `--last-frame`)

Generate a seamless transitional video bridging two separate keyframes:
```bash
gemini-video \
  --start-frame scene_before.png \
  --last-frame scene_after.png \
  --generate-prompt \
  -y \
  -o smooth_transition.mp4
```

---

### E. AI Prompt Optimization & Vision Reasoning (`--generate-prompt`)

Uses **Gemini 3.8 Flash** to analyze input images/keyframes, enforcing style consistency, character identity preservation (strictly avoiding inventing rogue characters), and natural camera choreography:
```bash
# Automatic non-interactive prompt generation (-y):
gemini-video \
  --start-frame portrait.png \
  --generate-prompt \
  -y \
  -o portrait_motion.mp4

# Preview prompt only without generating video:
gemini-video \
  --start-frame frame_a.png \
  --last-frame frame_b.png \
  --generate-prompt \
  --prompt-only
```

---

## 3. Command Reference & Arguments

| Option | Flag | Description | Default |
|---|---|---|---|
| **Prompt** | `-p, --prompt` | Text description directing scene and motion | Required (or `--generate-prompt`) |
| **Model** | `-m, --model` | `veo-3.1-generate-preview` (default), `veo-3.1-fast`, `veo-3.1-lite`, `veo-3.0` | `veo-3.1-generate-preview` |
| **Aspect Ratio** | `-r, --ratio` | `16:9` (landscape), `9:16` (portrait) | `16:9` |
| **Resolution** | `-s, --size` | `720p` (1280x720), `1080p` (1920x1080), `4k` (3840x2160) | `720p` |
| **Duration** | `-d, --duration` | `4s`, `6s`, `8s` (reference images and 1080p/4k require `8s`) | `8s` |
| **Audio** | `--audio` / `--no-audio`| Native synchronized dialogue, SFX, and ambient sound | `--audio` (Enabled) |
| **Reference Images**| `-i, --image` | Path(s) to reference images (up to 3) | None |
| **Reference Types** | `--ref-asset`, `--ref-style` | Explicitly assign subject or style reference | Inferred |
| **Keyframes** | `--start-frame`, `--last-frame` | Beginning / ending frames for animation/interpolation | None |
| **Prompt Gen** | `--generate-prompt` | Multimodal Gemini 3.8 Flash prompt synthesizer | Off |
| **Auto Confirm** | `-y, --yes` | Proceed immediately without interactive confirmation | Off |
| **Output** | `-o, --output` | Target video file (`.mp4`) or directory | `./outputs/<id>.mp4` |

---

## 4. Agent Best Practices

1. **Always Use `-y` with `--generate-prompt`**: In automated agent tasks, omit interactive prompts by including `-y` or `--yes`.
2. **Duration Constraints**: When using reference images, 1080p, or 4K resolution, Veo enforces an 8-second duration. Always pass `-d 8s`.
3. **Audio Control**: Synchronized audio is enabled by default. If pure video without audio is desired, pass `--no-audio`.
