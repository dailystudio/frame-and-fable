---
name: human-composer
description: Composes, binds, skins, and verifies 3D modular human character models (body, hair, upper garment, lower garment) in USDZ format using headless Blender. Use when asked to combine 3D character accessories and garments onto an animated base body, transfer and sanitize vertex weights, align bone axes, prevent mesh poke-through/skin clipping, or generate 5-angle turnaround inspection renders and turntable videos.
metadata:
  author: Frame & Fable
  keywords:
    - human-composer
    - 3d-character
    - usdz
    - blender
    - garment-binding
    - hair-binding
    - weight-transfer
    - character-rigging
    - skinning
    - turnaround-render
---

# Human Composer (`human-composer`)

`human-composer` is an automated 3D character composition and garment/hair binding pipeline in USDZ format powered by headless Blender. It solves skinning artifacts, cross-limb vertex weight bleeding, and garment poke-through using clean algorithmic alignment and vertex sanitization.

---

## 1. Quick Command Overview

When installed system-wide, the CLI is accessible anywhere via `human-composer`:

```bash
# Global CLI command (in PATH):
human-composer <COMMAND> [OPTIONS]

# System-wide venv fallback:
~/.local/share/frame-and-fable/venvs/human-composer/bin/python \
  /Volumes/Workspace/gitrepos/dailystudio/frame-and-fable/xr/human-composer/human-composer.py <COMMAND> [OPTIONS]
```

### Prerequisites
- **Blender 4.x** installed on the system (automatically found at `/Applications/Blender.app`, in `PATH`, or via `--blender /path/to/blender`).
- Input models in `.usdz` format.

---

## 2. Architectural Core Rules

```text
               +----------------------------------+
               | Clean Body Mesh & Clean Armature |
               +----------------------------------+
                 /              |               \
   (In isolation)        (In isolation)    (In isolation)
               v                v                v
      +----------------+ +----------------+ +----------------+
      |   Hair Model   | | Upper Garment  | | Lower Garment  |
      | (Scalp Align)  | |(WeightTransfer)| |(WeightTransfer)|
      +----------------+ +----------------+ +----------------+
               \                |               /
                \               |              /
                 v              v             v
               +----------------------------------+
               | Unified Scene Composite & Export |
               |     (Zero Weight Pollution)      |
               +----------------------------------+
```

1. **Isolated Binding on Clean Body**: Every accessory or garment (`--hair`, `--upper`, `--lower`) is bound in isolation against the clean base body and armature. Bindings are never chained sequentially.
2. **Skinning via Data Transfer**: Vertex weights are transferred from the clean body using Blender's `DATA_TRANSFER` modifier (`POLYINTERP_NEAREST`), avoiding heat-diffusion cross-limb bridging.
3. **Weight Sanitization**: Upper garments strip head weights to neck bones. Lower garments prune upper-body weights, reassign crotch-apex cross-limb weights to hips, and enforce strict leg-bone assignment below the crotch to prevent sticky webbing ("粘在一起").
4. **Bone-Axis Centerline Alignment & Clearance**: Sleeves and pant legs are aligned to bone axes. Pant cuffs taper down proportionally to ankle width ($R_{\text{ankle}} \times 1.08$) with strict sagittal medial clearance and gastrocnemius muscle volume clearance.

---

## 3. Production Workflows

### A. Full Character Binding (`human-composer bind`)

Combines body, hair, upper outfit, and lower pants/skirt into a single rigged `.usdz` character with previews:
```bash
human-composer bind \
  --body tests/man_anim_base.usdz \
  --hair tests/man_hair.usdz \
  --upper tests/man_suit.usdz \
  --lower tests/man_pants.usdz \
  --output-dir outputs \
  --render-views \
  --render-anim
```

#### Outputs Generated:
- `outputs/<model>/<model>_composed.usdz` (Final animated rigged character)
- `outputs/<model>/preview_composed.png` (Composite overview)
- `outputs/<model>/turntable.mp4` (Full 360° motion animation render)
- `outputs/<model>/intermediates/` (5-angle turnaround PNG renders: Front, 45° Left, Left, Right, Back)

---

### B. Inspect 3D Model Structure (`human-composer info`)

Extracts mesh hierarchy, materials, vertex counts, and skeleton details from any USDZ asset:
```bash
human-composer info --model path/to/character.usdz
```

---

### C. 5-Angle Turnaround Rendering (`human-composer render`)

Renders clean turnaround verification images for visual quality control:
```bash
human-composer render \
  --model outputs/character_composed.usdz \
  --output-dir outputs/qc_renders
```

---

## 4. CLI Arguments Reference (`bind`)

| Argument | Type | Required | Description |
|---|:---:|:---:|---|
| `--body` | File Path | **Yes** | Base character body model (`.usdz`) containing skeleton |
| `--hair` | File Path | Optional | Scalp/hair asset (`.usdz`) |
| `--upper` | File Path | Optional | Shirt, jacket, suit, or top garment (`.usdz`) |
| `--lower` | File Path | Optional | Pants, trousers, or skirt garment (`.usdz`) |
| `--output-dir` | Directory | No | Destination folder (default: `./outputs`) |
| `--render-views` | Flag | No | Generate 5-angle inspection PNG renders |
| `--render-anim` | Flag | No | Generate MP4 turntable animation video |
| `--blender` | File Path | No | Custom path to Blender executable |

---

## 5. Agent Best Practices

1. **Verify Base Model First**: Run `human-composer info --model <body.usdz>` to verify that the base model has valid meshes and a humanoid skeleton (`mixamorig_*` or standard bone naming).
2. **Always Enable Previews for Quality Control**: Pass `--render-views` so visual artifacts or clipping can be quickly inspected via generated turnaround images.
