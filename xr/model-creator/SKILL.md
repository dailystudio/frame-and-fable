---
name: model-creator
description: Generates high-fidelity 3D assets (GLB, USDZ, FBX, OBJ, STL) from text descriptions or reference images using generative 3D AI providers (Hyper3D / Rodin Gen-2.5 v2 API) via the model-creator CLI. Use when asked to create 3D meshes, generate 3D models from text prompts or turnaround concept art, control polygon counts/topology (Raw vs Quad), export PBR textured 3D assets, or generate T/A-pose humanoid models for rigging.
metadata:
  author: Frame & Fable
  keywords:
    - model-creator
    - text-to-3d
    - image-to-3d
    - hyper3d
    - rodin
    - 3d-asset-generation
    - glb
    - usdz
    - fbx
    - 3d-printing
    - pbr-textures
---

# 3D Model Creator (`model-creator`)

`model-creator` is a modular generative 3D asset pipeline that creates production-ready 3D meshes (`.glb`, `.usdz`, `.fbx`, `.obj`, `.stl`) from text descriptions or multi-view reference images. Currently powered by Hyper3D (Rodin Gen-2.5 API v2) with topology control (Raw triangles or clean Quads), target triangle budgets, PBR textures, and T/A-pose humanoid generation.

---

## 1. Quick Command Overview

When installed system-wide, the CLI is accessible anywhere via `model-creator`:

```bash
# Global CLI command (in PATH):
model-creator [OPTIONS]

# System-wide venv fallback:
~/.local/share/frame-and-fable/venvs/model-creator/bin/python \
  /Volumes/Workspace/gitrepos/dailystudio/frame-and-fable/xr/model-creator/model_creator.py [OPTIONS]
```

### Environment Setup
```bash
export HYPER3D_API_KEY="your-hyper3d-api-key"
# or
export RODIN_API_KEY="your-hyper3d-api-key"
```

---

## 2. Key Capabilities & Usage Workflows

### A. Text-to-3D Generation

Generate props, environment items, or characters with specific polygon limits and PBR materials:
```bash
# Generate low-poly game asset (e.g. 5,000 triangles) in GLB:
model-creator \
  --prompt "A medieval fantasy wooden treasure chest with engraved brass fittings" \
  --format glb \
  --triangles 5000 \
  --material PBR \
  -o ./outputs

# High-detail USDZ asset for AR / Apple Quick Look:
model-creator \
  --prompt "An antique brass sextant on a polished mahogany stand, scientific instrument" \
  --format usdz \
  --tier Gen-2.5-High \
  --quality high \
  -o ./outputs
```

---

### B. Image-to-3D Generation (Single or Multi-View)

Generate 3D meshes faithful to reference artwork or concept sketches:
```bash
# Single concept image:
model-creator \
  --images concept_art.png \
  --format glb \
  -o ./outputs

# Multi-view turnaround images with viewing direction labels (F=Front, B=Back, L=Left, R=Right):
model-creator \
  --images front.png back.png left.png \
  --image-labels F B L \
  --format usdz \
  -o ./outputs
```

---

### C. Humanoid T-Pose / A-Pose for Rigging (`--ta-pose`)

Prepares characters in a standard neutral pose for immediate skeletal rigging in `rig-binder`, `pose-binder`, or `human-composer`:
```bash
model-creator \
  --prompt "Stylized cyberpunk detective in a long trench coat, full body humanoid" \
  --ta-pose \
  --mesh-mode Quad \
  --quality high \
  --format fbx \
  -o ./outputs
```

---

### D. Asynchronous Execution & Task Management

For long-running generations, submit tasks asynchronously and poll/download later:
```bash
# 1. Submit task asynchronously:
model-creator --prompt "Detailed Gothic cathedral archway" --no-wait
# Output displays:
#   subscription_key: sub_12345abcde
#   task_uuid: 98765-fedcba

# 2. Check task status:
model-creator --status sub_12345abcde

# 3. Download results once completed:
model-creator --download 98765-fedcba --format glb -o ./outputs
```

---

### E. Check API Credit Balance

```bash
model-creator --balance
```

---

## 3. CLI Arguments Reference

| Argument | Options | Description | Default |
|---|---|---|---|
| `-p, --prompt` | Text string | Prompt description for 3D generation | None |
| `-i, --images` | File paths | 1–5 reference image paths for Image-to-3D | None |
| `--image-labels` | `F B L R` | Camera angle labels corresponding to `--images` | Auto |
| `-f, --format` | `glb`, `usdz`, `fbx`, `obj`, `stl` | Target 3D file format | `glb` |
| `--triangles` | `500` to `2000000` | Exact target triangle count budget | None |
| `--tier` | `Gen-2.5-Medium`, `Gen-2.5-High`, etc. | Generation quality tier | `Gen-2.5-Medium` |
| `--mesh-mode` | `Raw`, `Quad` | Mesh topology (triangles vs quads) | `Raw` |
| `--material` | `PBR`, `Shaded`, `All`, `Hybrid`, `None` | Material and texture type | `PBR` |
| `--ta-pose` | Flag | Force neutral T-pose/A-pose for humanoid rigging | Off |
| `--preview-render` | Flag | Download high-quality turntable preview image | Off |
| `--no-wait` | Flag | Submit task without blocking for completion | Off |
| `--status` | Key string | Check status of an ongoing task | None |
| `--download` | UUID string | Download generated asset for completed task | None |
| `--balance` | Flag | Query remaining API credits | Off |
| `--list`, `--history` | Flag | List created models and generation tasks from account history | Off |
| `--addons` | `HighPack`, etc. | Add-on packs (e.g. `HighPack` for 4K packed textures) | None |
| `-o, --output-dir` | Directory | Destination folder for 3D models | `./outputs` |

---

## 4. Agent Best Practices

1. **Topology & Face Count**: For real-time mobile/XR engines, set `--triangles 10000` or `--quality medium`. For high-poly hero assets, set `--tier Gen-2.5-High` and `--quality high`.
2. **Animation Preparation**: Always include `--ta-pose` when generating characters intended to be rigged with `pose-binder` or `rig-binder`.
3. **Multi-Format Export**: If you need multiple formats, specify `--format glb` first, and if USDZ is also needed for Apple devices, generate both or convert via Blender.
