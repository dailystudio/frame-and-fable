# Asset Generator (`asset-generator`)

An end-to-end, production-grade generative 3D asset creation pipeline for characters and common objects (furniture, props, items, environment assets).

Orchestrates multi-modal generative AI across:
1. **Gemini Image (Nano Banana 2 / Pro)**: Text-to-concept synthesis and style-guided reference art.
2. **Multi-View Synthesis (`t-pose-multiviews` / `model-multiviews`)**: Consistent turnaround views for 3D reconstruction.
3. **Hyper3D (Rodin Gen-2.5)**: 4K textured 3D mesh creation (`base_high_pbr.usdz`) with ground plane grounding.
4. **Mixamo / Blender Rigging (`pose-binder` / `rig-binder`)**: Automated character skeletal animation.

---

## Installation

To install `asset-generator` as a global command on your system:

```bash
cd /Volumes/Workspace/gitrepos/dailystudio/frame-and-fable
./install-skills.sh asset-generator
```

This installs the CLI executable into `~/.local/bin/asset-generator` (with aliases `generate-asset`, `asset-craft`, `character-pipeline`) and links its agent skill to `~/.gemini/config/skills/asset-generator/`.

---

## Quick Usage

### 1. Characters

```bash
# From text prompt:
asset-generator "cyberpunk samurai" --type character -o outputs/samurai

# From reference image + style reference:
asset-generator -i hero.png -S anime_style.png --type character -o outputs/hero
```

### 2. Common Objects & Props (Table, Chair, Cup, etc.)

```bash
# Generate a modern table:
asset-generator "modern wooden dining table with black steel legs" -o outputs/table

# Generate an office chair:
asset-generator "ergonomic mesh office chair" -o outputs/chair

# Generate a ceramic cup with Nordic style:
asset-generator "ceramic coffee cup" --style-prompt "Nordic minimalist" -o outputs/cup

# Fast direct 3D (skip multi-views for simple props):
asset-generator "crystal magic orb" --single-view -o outputs/orb
```

### 3. Step Control & Inspection

```bash
# Views only:
asset-generator "steampunk airship" --step views -o outputs/airship

# 3D model only from existing views:
asset-generator outputs/airship --step model --4k

# Rigging only:
asset-generator outputs/samurai/model/samurai.usdz --step pose
```

### 4. Account Management

```bash
# List past generation tasks:
asset-generator --list

# Check credit balance:
asset-generator --balance

# Download past model by UUID:
asset-generator --download <TASK_UUID> -o outputs/downloaded
```
