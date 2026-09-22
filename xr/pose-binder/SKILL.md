---
name: pose-binder
description: Automates Adobe Mixamo character rigging and animation workflows for USDZ models via Playwright browser automation, exports clean T-pose base models and animation tracks in USD format (.usdz and .usdc), and auto-imports them into PICO Spatial Editor projects. Use when asked to rig a USDZ character with Mixamo, convert USDZ to FBX for rigging, capture Mixamo animations, export clean rest-pose USDZ and skeletal animation USDC, or import animated assets into Spatial Editor scenes.
metadata:
  author: Frame & Fable
  keywords:
    - pose-binder
    - mixamo
    - usdz
    - usdc
    - character-rigging
    - animation-pipeline
    - playwright
    - pico-spatial-editor
    - spatial-computing
---

# Pose Binder (`pose-binder`)

`pose-binder` bridges Apple USDZ 3D character models with Adobe Mixamo auto-rigging and PICO Spatial Editor projects. It automates USDZ-to-FBX conversion, runs Playwright browser automation to handle Mixamo rigging and animation selection, exports clean T-pose rest meshes and animation USDC files via Blender, and automatically imports assets into Spatial Editor scenes.

---

## 1. Quick Command Overview

When installed system-wide, the CLI is accessible anywhere via `pose-binder`:

```bash
# Global CLI command (in PATH):
pose-binder [OPTIONS]

# System-wide venv fallback:
~/.local/share/frame-and-fable/venvs/pose-binder/bin/python \
  /Volumes/Workspace/gitrepos/dailystudio/frame-and-fable/xr/pose-binder/pose_binder.py [OPTIONS]
```

### Prerequisites
- **Python 3.10+**
- **Blender 4.x** (found at `/Applications/Blender.app` or in PATH)
- **Playwright Chromium**: `playwright install chromium`
- Active Adobe Mixamo account for browser login

---

## 2. Modes & Production Workflows

### Mode 1: Full Pipeline from USDZ Model (`--input`)

Converts character USDZ, launches browser for Mixamo auto-rigging & motion selection, extracts T-pose USDZ & animation USDC, and deploys to Spatial Editor:
```bash
pose-binder \
  --input verify/character.usdz \
  --output outputs/ \
  --import-to-se ~/Editor/MyProject \
  --scene MainScene
```

#### Pipeline Steps:
1. **Unpack & Convert**: Converts input `.usdz` to `.fbx` with unpacked textures and builds a zip package.
2. **Mixamo Automation**: Launches stealth Playwright Chromium and auto-uploads the zip package.
3. **Rigging & Action Selection**: Prompts user/developer to place chin/wrist/elbow/knee/groin markers, pick an animation (e.g. `Walk`, `Defeated`, `Jab Cross`), and download the result.
4. **Download Interception**: Detects blob download stream and verifies file integrity.
5. **Rest-Pose T-Pose USDZ Export**: Resets pose bone transforms in Blender to rest T-pose, fixes Principled BSDF shader links, and exports `<name>_anim_base.usdz`.
6. **Animation Track USDC Export**: Exports pure skeletal motion track `<name>_anim_<action>.usdc` preserving Mixamo action name in the USD `SkelAnimation` prim.
7. **Spatial Editor Import**: Deploys base mesh to `Sources/Assets/`, motion tracks to `Sources/Assets/anims/`, and composes/updates `Sources/Scenes/<Scene>.usda`.

---

### Mode 2: Process Existing Mixamo Animated FBX (`--input-anim`)

Skips browser automation when you already have an exported Mixamo FBX file:
```bash
pose-binder \
  --input-anim character_dance.fbx \
  --output outputs/ \
  --import-to-se ~/Editor/MyProject
```

---

### Mode 3: Interactive Mixamo Session (`--input-mixamo`)

Keeps the Mixamo browser session alive to download multiple different animation clips for the same rigged avatar:
```bash
pose-binder --input-mixamo --output outputs/
```

---

### Mesh Weight Correction Helper (`fix_chin_jaw_weights.py`)

If automatic skinning bleeds jaw/chin vertices into the upper chest:
```bash
/Volumes/Workspace/gitrepos/dailystudio/frame-and-fable/xr/pose-binder/.venv/bin/python \
  /Volumes/Workspace/gitrepos/dailystudio/frame-and-fable/xr/pose-binder/fix_chin_jaw_weights.py \
  --input character_anim.fbx \
  --output character_fixed.fbx
```

---

## 3. CLI Arguments Reference

| Argument | Description | Default |
|---|---|---|
| `--input` | Input raw character `.usdz` file | None |
| `--input-anim` | Input pre-downloaded animated `.fbx` from Mixamo | None |
| `--input-mixamo` | Launch interactive Mixamo browser session | Off |
| `--output` | Destination directory for exported USD files | `./outputs` |
| `--import-to-se` | Path to PICO Spatial Editor project root | None |
| `--scene` | Target scene name inside Spatial Editor project | `MainScene` |
| `--blender-path` | Explicit path to Blender binary | Auto-detected |

---

## 4. Agent Best Practices

1. **Headful Browser Requirement**: When using Mode 1, Playwright runs headful so markers can be visually confirmed. Ensure the user is in a desktop environment.
2. **Batch Animation Workflow**: For multiple animations, first rig the avatar once to produce the T-pose base USDZ, then use Mode 2 with different animated FBX clips to quickly generate additional `.usdc` tracks.
