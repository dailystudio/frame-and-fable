---
name: asset-generator
description: End-to-end generative 3D asset creation pipeline for characters and common objects (furniture, props, items, environment assets). Generates from reference images or text prompts, style references, through multi-views (T-pose views for characters, product views for objects), 4K textured 3D models (USDZ/GLB) via Hyper3D with ground-plane root placement, and skeletal rigging/animation (Mixamo / Rig-Binder). Use when asked to generate 3D characters, props, tables, chairs, cups, items, multi-views, 4K textures, or automated character rigging.
metadata:
  author: Frame & Fable
  keywords:
    - asset-generator
    - generate-asset
    - asset-craft
    - 3d-character
    - 3d-object
    - props
    - furniture
    - multiviews
    - t-pose
    - hyper3d
    - 4k-textures
    - mixamo
    - rigging
    - usdz
    - glb
---

# Generative 3D Asset Generator (`asset-generator`)

`asset-generator` (aliases: `generate-asset`, `asset-craft`) is a unified, end-to-end generative 3D pipeline that automates the transition from concept to complete, production-ready 3D assets for both **characters** and **common objects** (props, furniture, tableware, vehicles, environment items).

---

## 1. Quick Command Overview

Accessible globally via:
```bash
asset-generator [INPUT] [OPTIONS]
# or
generate-asset [INPUT] [OPTIONS]
```

### Supported Asset Categories
1. **Characters (`--type character`)**:
   - Generates canonical T-pose multi-views (Front, Back, Left, Right)
   - Visual inspection and confirmation (`-y` to auto-confirm)
   - 4K textured 3D model with `--root foot` grounding (feet at ground plane Z=0)
   - Skeletal rigging & animation via `pose-binder` (Adobe Mixamo) or `rig-binder` (Blender)

2. **Common Objects & Props (`--type object`)**:
   - Generates product views (Front, Left, Right, Back, optional Top) or direct single-view 3D
   - 4K textured 3D model with `--root bottom` / `foot` grounding (sits flat on floor or table)
   - Skeletal rigging is automatically skipped for objects

---

## 2. Common Workflows & Examples

### A. Generate Character from Text Prompt (End-to-End)
```bash
asset-generator "cyberpunk ninja warrior with glowing katana" \
  --type character \
  --style-prompt "stylized anime, cel shaded" \
  -o outputs/ninja \
  --4k
```

### B. Generate Character from Reference & Style Images
```bash
asset-generator -i hero_concept.png \
  -S anime_style_ref.png \
  --type character \
  -o outputs/hero \
  --4k
```

### C. Generate Common Objects (Table, Chair, Cup, Props)
```bash
# Generate a modern wooden dining table:
asset-generator "modern wooden dining table with black steel legs" \
  --type object \
  -o outputs/dining_table \
  --4k

# Generate an office chair:
asset-generator "ergonomic mesh office chair with armrests" \
  --type object \
  -o outputs/office_chair

# Generate a ceramic coffee cup:
asset-generator "ceramic coffee cup" \
  --type object \
  --style-prompt "Nordic minimalist, matte glazed finish" \
  -o outputs/coffee_cup

# Generate an object using single-view / direct 3D (bypasses multi-view expansion):
asset-generator "antique brass pocket watch" \
  --type object \
  --single-view \
  -o outputs/pocket_watch
```

### D. Step-by-Step Execution
```bash
# Step 1: Generate only multi-views for review:
asset-generator "steampunk airship" --type object --step views -o outputs/airship

# Step 2: Generate 3D model from existing views:
asset-generator outputs/airship --step model --4k

# Step 3: Rig and animate an existing character model:
asset-generator outputs/hero/model/hero.usdz --step pose --rig-engine mixamo
```

### E. Account History & Utility Actions
```bash
# List previously created 3D models and tasks from Hyper3D account:
asset-generator --list

# Check remaining Hyper3D credit balance:
asset-generator --balance

# Download any past model by task UUID:
asset-generator --download <TASK_UUID> -f usdz -o outputs/downloaded_model
```

---

## 3. CLI Arguments Reference

| Option | Description | Default |
| :--- | :--- | :--- |
| `input` | Path to reference image, character folder, or descriptive text prompt | Positional |
| `-t, --type` | Asset category: `character` or `object` | Auto-inferred |
| `--character` | Shortcut to force category as `character` | Auto |
| `--object, --prop` | Shortcut to force category as `object` | Auto |
| `-i, --image, --ref` | Path to reference image file | `None` |
| `-p, --prompt` | Descriptive prompt for asset synthesis or guidance | `None` |
| `-S, --style` | Path to style reference image | `None` |
| `--style-prompt` | Textual style description | `None` |
| `-o, --output-dir` | Output target directory | `outputs/<name>` |
| `--step` | Execution step: `all`, `views`, `model`, `pose` | `all` |
| `--single-view` | For objects: bypass multi-view synthesis and generate 3D directly | `False` |
| `-y, --yes` | Auto-confirm multi-views without interactive terminal prompt | `False` |
| `--4k, --no-4k` | Enable / disable 4K (4096×4096) packed textures | Enabled (`--4k`) |
| `-f, --format` | Output geometry format: `usdz`, `glb`, `fbx`, `obj`, `stl` | `usdz` |
| `--triangles` | Target triangle polygon count | `50000` |
| `--root` | Root placement: `foot` (ground min Z=0) or `center` | `foot` |
| `--rig-engine` | Rigging system for characters: `mixamo` or `humanoid-65` | `mixamo` |
| `--dry-run` | Preview all commands and parameters without spending credits | `False` |
| `--list` | List created 3D models & tasks in Hyper3D account | — |
| `--download` | Download model by task UUID | — |
