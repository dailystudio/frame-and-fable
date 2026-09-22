---
name: image-craft
description: Generates and edits high-quality 2D images, transparent character sprites, concept art, storyboards, and textures using Google Gemini Image models (Nano Banana 2 / gemini-3.1-flash-image, Nano Banana Pro / gemini-3-pro-image, and Imagen 3) via the gemini-image CLI. Use when asked to generate images, create transparent PNG sprites with chroma-keying, edit images from reference pictures, transform video frames into images, or create visual assets.
metadata:
  author: Frame & Fable
  keywords:
    - image-craft
    - gemini-image
    - nano-banana
    - imagen-3
    - text-to-image
    - image-editing
    - transparent-png
    - chroma-key
    - sprites
    - concept-art
---

# Image Craft (`image-craft` / `gemini-image`)

`image-craft` provides image generation and multi-turn image editing powered by Google Gemini Image models (Nano Banana 2, Nano Banana Pro, and Imagen 3). It features native green chroma key background removal for transparent PNG sprites, up to 4K resolution, 14-reference multimodal conditioning, and multi-turn iterative editing.

---

## 1. Quick Command Overview

When installed system-wide, the CLI is accessible anywhere via `gemini-image` or `image-craft`:

```bash
# Global CLI command (in PATH):
gemini-image [OPTIONS] [PROMPT]
# or
image-craft [OPTIONS] [PROMPT]

# Multi-View Modeling Presets (Turnaround generators):
model-multiviews <REF_IMAGE> [EXTRA_PROMPT] [OPTIONS]
t-pose-multiviews <REF_IMAGE> [EXTRA_PROMPT] [OPTIONS]
garment-multiviews <REF_IMAGE> [EXTRA_PROMPT] [OPTIONS]
```

### Environment Setup
```bash
export GEMINI_API_KEY="your-gemini-api-key"
```

---

## 2. Key Capabilities & Usage Workflows

### A. Text-to-Image Generation

Generate high-resolution scenes, concept art, or illustrations:
```bash
# Standard high-resolution generation (default model: gemini-3.1-flash-image / Nano Banana 2):
gemini-image "A majestic oriental dragon coiling around a mountain pagoda at sunset" \
  -r 16:9 \
  -s 4K \
  -o dragon_pagoda.png

# Professional photorealistic asset with Nano Banana Pro (gemini-3-pro-image):
gemini-image "Macro photography of an intricate brass mechanical watch movement with polished gears and ruby jewels" \
  -m 3-pro \
  -r 1:1 \
  -s 2K \
  -o watch_macro.png
```

---

### B. Transparent PNG Character Sprites & Props (`--transparent`)

Automatically appends `use 0x00FF00 chroma key background` and executes OpenCV/Pillow post-processing to isolate the subject on a transparent background:
```bash
# Generate transparent 2D character sprite:
gemini-image "Full-body 2D concept character sprite of a female cyberpunk detective holding a glowing datapad" \
  --transparent \
  -s 2K \
  -o detective_sprite.png

# Generate transparent game item / prop:
gemini-image "An ancient glowing crystalline dagger with golden runic engravings" \
  --transparent \
  -s 1K \
  -o crystal_dagger.png
```

---

### C. Reference Image-to-Image Conditioning (`-i` / `--image`)

Guide art style, character appearance, or layout using up to 14 reference images:
```bash
# Transform portrait into another art style while preserving likeness:
gemini-image "Convert this person into a Studio Ghibli style watercolor illustration with soft pastel lighting" \
  -i character_photo.png \
  -o ghibli_character.png

# Multi-reference conditioning (character + costume + environment):
gemini-image "Place the character from image 1 in the outfit from image 2 inside the neon alley of image 3" \
  -i character.png costume.png background.png \
  -r 16:9 \
  -s 4K \
  -o composite_scene.png
```

---

### D. Multi-Turn Iterative Editing (`--previous-id`)

Continue an existing image generation session without restarting:
```bash
# Step 1: Generate base image
gemini-image "A cozy medieval tavern interior with a stone fireplace" -o tavern.png
# Output logs: Interaction ID: x9k2m1b8laq0

# Step 2: Iteratively edit that exact image:
gemini-image "Add a sleeping fluffy white cat on a rug near the fireplace hearth" \
  --previous-id x9k2m1b8laq0 \
  -o tavern_with_cat.png
```

---

### E. Video-to-Image Generation (`--video`)

Feed a video file or YouTube URL for visual scene extraction and re-imagination:
```bash
gemini-image "Generate a dynamic anime fight poster based on the climax scene of this video" \
  --video combat_clip.mp4 \
  -s 2K \
  -o anime_poster.png
```

---

### F. 3D Modeling Turnaround Multi-View Presets

`image-craft` includes companion CLI tools for generating multi-angle views (front, left, right, back, top, bottom) from 2D character or garment artwork. All presets support an optional **style reference image** (`-S`, `--style-image`, or 2nd positional argument) to transfer visual style (e.g. cel-shaded, clay render, anime lineart) onto the model:

```
# General syntax:
<command> <REF_IMAGE> [STYLE_IMAGE] [EXTRA_PROMPT] [OPTIONS...]
<command> -i <REF_IMAGE> [-S <STYLE_IMAGE>] [-p EXTRA_PROMPT] [OPTIONS...]
```

When a style image is provided, the prompt formula `"Use <style.png> style to draw the content of <ref.png>. <view_prompt>[, <extra_prompt>]"` is automatically constructed and both images are passed to `gemini-image`.

#### 1. Standard Character Multi-Views (`model-multiviews`)
Generates Left, Right, and Back views by default from a single front reference image:
```bash
# Standard 4K turnaround views (Left, Right, Back):
model-multiviews character_front.png -o outputs/

# With style reference image (positional or -S):
model-multiviews character_front.png style_art.png "cel shaded, clean lineart"
model-multiviews -i character_front.png -S style_art.png -p "clay style" --transparent

# Custom views and hollow parts:
model-multiviews character_front.png -S style_art.png -v "left; top; bottom"
```

#### 2. Canonical T-Pose Multi-Views (`t-pose-multiviews`)
Accepts **any** reference image (even in non-front or dynamic action poses) and executes a 2-phase pipeline:
- **Phase 1**: Generates a canonical front T-pose maintaining character identity (and applying style reference if provided).
- **Phase 2**: Uses that front T-pose to generate Left, Right, and Back turnaround views with the same style.
```bash
# Dynamic pose to canonical T-pose turnaround:
t-pose-multiviews action_character.png -o outputs/character.png

# With style reference transfer:
t-pose-multiviews action_character.png style_art.png "3D render, clay style" -o outputs/character.png
t-pose-multiviews -i action_character.png -S style_art.png -p "anime style" --transparent
```

#### 3. Garment & Clothing Multi-Views (`garment-multiviews`)
Specifically tuned for 3D apparel and costume design. Prompts Gemini to preserve hollow openings (sleeves, neck, waist):
```bash
# Standard garment turnaround (Left, Top, Bottom):
garment-multiviews jacket_front.png "denim fabric, detailed folds" -o outputs/jacket.png

# With style reference image:
garment-multiviews jacket_front.png style_art.png "denim fabric, realistic folds"
garment-multiviews -i dress_front.png -S fabric_style.png -p "3D render" --transparent
```

---

## 3. Command Reference & Arguments

| Flag | Options / Examples | Description | Default |
|---|---|---|---|
| `-p, --prompt` | `"A neon cityscape..."` | Prompt description (or positional arg) | (Required) |
| `-m, --model` | `3.1-flash`, `3-pro`, `3.1-lite`, `2.5-flash`, `imagen3` | Model selection | `gemini-3.1-flash-image` |
| `-r, --ratio` | `1:1`, `16:9`, `9:16`, `4:3`, `3:4`, `2:3`, `3:2`, `21:9` | Aspect ratio | Inferred / `1:1` |
| `-s, --size` | `0.5K` (512), `1K`, `2K`, `4K` | Resolution limit | `1K` |
| `--transparent` | Flag | Generate with green chroma key and isolate transparency | Off |
| `-i, --image` | Path(s) | Input reference image(s) (1–14) | None |
| `--video` | Path or URL | Video reference for image generation | None |
| `--previous-id` | `<interaction_id>` | Iterative editing session ID | None |
| `--search` | Flag | Real-time Google Search grounding | Off |
| `--image-search` | Flag | Real-time Google Image Search grounding | Off |
| `-o, --output` | File path or directory | Output image destination | `./outputs/<id>.png` |

---

## 4. Agent Best Practices

1. **Always Specify `-o <filepath.png>`**: By default, files are written to `./outputs/<id>.png`. Specifying a direct output path makes referencing the generated asset immediate and deterministic.
2. **Sprites & Assets**: For UI elements, game props, and avatars intended for composition, always pass `--transparent` to automatically receive a cleanly cut-out transparent PNG.
3. **Aspect Ratio Alignment**: Match the aspect ratio to the target medium (e.g. `16:9` for landscape wallpapers/headers, `9:16` for mobile vertical stories, `1:1` for profile avatars/icons).
