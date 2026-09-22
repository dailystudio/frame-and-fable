---
name: model-composer
description: Combines, fits, scales, rigs, skins, and verifies modular 3D character assets (body, animation track, hair, garments) using Blender and computer vision geometry algorithms via auto_combine_models. Use when asked to fit modular 3D clothing or hair to a character body, compose skeletal animations into native Pixar UsdSkel USDZ/GLB/FBX assets, eliminate flared skirt polygon tearing via stratified skinning, or generate 4-view QC comparison sheets against 2D concept art.
metadata:
  author: Frame & Fable
  keywords:
    - model-composer
    - auto-combine-models
    - 3d-fitting
    - usdskel
    - usdz
    - character-pipeline
    - skirt-skinning
    - landmark-detection
    - qc-turnaround
---

# 3D Model Composer (`model-composer` / `auto_combine_models`)

`model-composer` is an automated Python and Blender pipeline to fit, scale, rig, skin, animate, and verify modular 3D character assets (body, skeletal motion, hair, and garments). It outputs production-ready animated USDZ (`UsdSkel`), Blender (`.blend`), glTF (`.glb`), and FBX (`.fbx`) assets, complete with 4-view turnaround QC comparison sheets against 2D reference concept art.

---

## 1. Quick Command Overview

When installed system-wide, the CLI is accessible anywhere via `model-composer` or `auto_combine_models`:

```bash
# Global CLI command (in PATH):
model-composer [OPTIONS]
# or
auto_combine_models [OPTIONS]

# System-wide venv fallback:
~/.local/share/frame-and-fable/venvs/model-composer/bin/python \
  /Volumes/Workspace/gitrepos/dailystudio/frame-and-fable/xr/model-composer/auto_combine_models.py [OPTIONS]
```

### Prerequisites
- **Blender 4.x** (found in PATH or `/Applications/Blender.app`, or configured via `--blender-path`).

---

## 2. Key Capabilities

- **Automated Anatomical Landmark Detection**: Detects cranium dimensions, cleavage mid-line, ribcage volume, waist indentation, and hip width using geometry algorithms.
- **Intelligent Scaling & Alignment**: Normalizes standalone garment/hair bounding boxes to fit the character torso and scalp precisely.
- **Stratified Parametric Skinning**: Employs continuous height-gradient joint weighting to eliminate the polygon spiking and tearing caused by proximity weight transfer on flared skirts and wide dresses.
- **Native Pixar `UsdSkel` Animation Composition**: Embeds `UsdSkel.Animation`, `UsdSkel.Skeleton`, and `UsdSkel.BindingAPI` into `.usdz` archives compatible with Apple Quick Look, iOS, and visionOS.
- **4-View Turnaround QC & Reference Comparison**: Renders Front, Left-Side, Right-Side, and Back views, building side-by-side composite sheets with concept art.

---

## 3. Production Workflows

### A. Stage 1: T-Pose Decoration Alignment & QC Verification

Fits hair and garments onto the base body and verifies alignment against concept art without applying skeletal weights:
```bash
model-composer --stage 1 \
  --body tests/man_anim_base.usdz \
  --hair tests/man_hair.usdz \
  --cloth tests/man_suit.usdz \
  --bottom tests/man_pants.usdz \
  --ref-front tests/man_ref_front.png \
  --ref-right tests/man_ref_right.png \
  --output-dir outputs
```

---

### B. Stage 2: Skeletal Binding & Animation Composition

Applies stratified skinning, binds external skeletal animation tracks, and exports animated USDZ/GLB/FBX files:
```bash
model-composer --stage 2 \
  --body tests/man_anim_base.usdz \
  --anim tests/motion_walk.fbx \
  --hair tests/man_hair.usdz \
  --cloth tests/dress.usdz \
  --cloth-type full_dress \
  --output-dir outputs
```

---

### C. Full End-to-End Execution (Both Stages)

Executes full alignment, skinning, animation composition, and verification:
```bash
model-composer \
  --body character_body.usdz \
  --anim walking_routine.usdc \
  --hair hair_mesh.usdz \
  --top upper_jacket.usdz \
  --bottom trousers.usdz \
  --cloth-type auto \
  --output-dir outputs
```

---

## 4. CLI Arguments Reference

| Argument | Type | Description | Default |
|---|:---:|---|---|
| `--body` | File Path | Base textured character body model (`.usdz`, `.glb`, `.blend`) | Required |
| `--anim` | File Path | Skeletal animation track (`.usdc`, `.fbx`, `.glb`) | Body's skeleton |
| `--hair` | File Path | Hair model (`.usdz`, `.glb`, `.obj`) | Optional |
| `--cloth` | File Path | Single garment model (dress, gown, suit) | Optional |
| `--cloth-type` | Enum | `auto`, `full_dress`, `tube`, `top`, `shirt`, `skirt`, `bottom`, `pants` | `auto` |
| `--top` | File Path | Upper garment model for two-piece outfits | Optional |
| `--bottom` / `--skirt` | File Path | Lower garment model for two-piece outfits | Optional |
| `--stage` | Integer | Pipeline stage: `1` (Align & Verify) or `2` (Bind & Animate) | Both |
| `--ref-front` | Image Path | Front concept art reference image for turnaround comparison | Optional |
| `--ref-right` | Image Path | Right-view reference image | Optional |
| `--output-dir` | Directory | Destination directory for composite files and renders | `./outputs` |
| `--blender-path` | File Path | Explicit path to Blender binary | Auto-detected |

---

## 5. Agent Best Practices

1. **Flared Skirt / Tube Dress Tip**: When composing wide dresses or flared skirts, explicitly set `--cloth-type full_dress` or `skirt` to activate the stratified height-gradient skinning algorithm.
2. **Two-Piece Outfits**: Use `--top` and `--bottom` rather than combining them into a single file to allow independent weight sanitization and limb isolation.
