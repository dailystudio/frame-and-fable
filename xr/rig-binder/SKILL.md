---
name: rig-binder
description: Dynamically generates skeletons, computes proportional anatomical landmarks, assigns automatic bone skinning weights, and binds animations for 3D and 2D character meshes across multiple specifications (Chinese Shadow Play 19-joint 2D planar rig, humanoid 65-joint mocap rig, biped-24 rig, or custom JSON rigs) via Blender. Use when asked to rig static 3D/2D models, create Chinese shadow puppet rigs and animations, rig 65-joint humanoid models with 5-finger hand chains, or export rigged assets to USDZ, GLB, Blend, and FBX.
metadata:
  author: Frame & Fable
  keywords:
    - rig-binder
    - skeleton-rigging
    - skinning
    - shadow-puppet
    - shadow-play
    - 2d-planar-rig
    - humanoid-65
    - biped-24
    - blender-rigging
    - usdz
    - glb
---

# Rig Binder (`rig-binder`)

`rig-binder` is an automated, generalized rigging and skinning pipeline in Blender. It dynamically computes anatomical landmarks from 3D/2D meshes, generates bone hierarchies, computes bone envelopes and skinning vertex weights, and exports clean, multi-format assets (`.usdz`, `.glb`, `.blend`, `.fbx`) alongside automated visual previews and performance animations.

---

## 1. Quick Command Overview

When installed system-wide, the CLI is accessible anywhere via `rig-binder`:

```bash
# Global CLI command (in PATH):
rig-binder [OPTIONS]

# System-wide venv fallback:
~/.local/share/frame-and-fable/venvs/rig-binder/bin/python \
  /Volumes/Workspace/gitrepos/dailystudio/frame-and-fable/xr/rig-binder/rig_binder.py [OPTIONS]
```

### Prerequisites
- **Blender 4.x** (found at `/Applications/Blender.app` or in PATH).

---

## 2. Supported Rig Specifications & Workflows

### A. Preset 1: Chinese Shadow Play 19-Joint 2D Rig (`shadow-puppet`)

Designed for traditional Chinese shadow puppetry (皮影戏). Generates a 19-joint skeleton with strict planar hinge constraints (depth/Y locked, bone rolls aligned to screen normal) and binds a classic 100-frame performance routine (走场步, 起霸亮相, 抱拳作揖, 回身归位):
```bash
rig-binder \
  --model samples/puppet.usdz \
  --rig-type shadow-puppet \
  --output-dir outputs
```

#### Bone Hierarchy (19 Joints):
- `root` $\rightarrow$ `waist` (腰) $\rightarrow$ `thigh.L/R` $\rightarrow$ `knee.L/R` $\rightarrow$ `ankle.L/R`
- `waist` $\rightarrow$ `spine` (胸) $\rightarrow$ `neck` (领) $\rightarrow$ `head` (头茬)
- `spine` $\rightarrow$ `shoulder.L/R` $\rightarrow$ `upper_arm.L/R` $\rightarrow$ `elbow.L/R` $\rightarrow$ `wrist.L/R`

---

### B. Preset 2: Standard Humanoid 65-Joint Mocap Rig (`humanoid-65`)

Standard production skeleton compatible with Mixamo, SMPL, and major game engines:
- Full 5-finger articulated hand chains (30 hand bones)
- Articulated feet and toes
- Multi-segment spine (`spine`, `spine1`, `spine2`, `chest`), neck, head, jaw, eyes
- Binds a 100-frame Walk-to-Run progression routine (Stance $\rightarrow$ Walk $\rightarrow$ Jog $\rightarrow$ Sprint $\rightarrow$ Ease):

```bash
# Rig humanoid model (humanoid-65 is the default rig):
rig-binder \
  --model samples/base_basic_shaded.usdz \
  --rig-type humanoid-65 \
  --output-dir outputs
```

---

### C. Preset 3: Streamlined Game Biped 24-Joint Rig (`biped-24`)

Optimized 24-joint game skeleton without individual finger bones (single hand and foot pivots):
```bash
rig-binder \
  --model character.glb \
  --rig-type biped-24 \
  --output-dir outputs
```

---

### D. Custom Rig Specification (`--custom-rig`)

Pass any user-defined JSON skeleton configuration defining bone hierarchy, proportional offsets, and skinning rules:
```bash
rig-binder \
  --model creature.obj \
  --custom-rig presets/custom_creature.json \
  --output-dir outputs
```

---

## 3. Output Artifacts

For any rigged model, `rig-binder` generates a complete asset bundle in `--output-dir`:
1. **Rest-Pose Models**: `<name>_rigged.usdz`, `.glb`, `.blend`, `.fbx`
2. **Animated Performance Models**: `<name>_animated.usdz`, `.glb`, `.blend`, `.fbx`
3. **Turnaround & Previews**:
   - `<name>_contact_sheet.png` (Multi-angle static QC grid)
   - `<name>_preview.mp4` (Full performance motion video render)

---

## 4. CLI Arguments Reference

| Argument | Options | Description | Default |
|---|---|---|---|
| `--model` | File Path | Input 3D/2D model (`.usdz`, `.glb`, `.blend`, `.obj`) | Required |
| `--rig-type` | `humanoid-65`, `shadow-puppet`, `biped-24`, `custom` | Skeleton specification | `humanoid-65` |
| `--custom-rig` | JSON File Path | Custom rig configuration file | None |
| `--output-dir` | Directory | Target output folder | `./outputs` |
| `--no-animation` | Flag | Export rest-pose rigged assets only without motion routine | Off |
| `--no-preview` | Flag | Skip rendering contact sheet and MP4 preview video | Off |
| `--blender-bin` | File Path | Custom path to Blender executable | Auto-detected |

---

## 5. Agent Best Practices

1. **2D vs 3D Selection**: If the asset is a flat 2D puppet cutout or traditional puppet illustration, always specify `--rig-type shadow-puppet` so the planar constraints prevent unwanted out-of-plane distortion.
2. **Reviewing Animation**: The generated `<name>_preview.mp4` provides immediate visual validation of joint deformation and skinning weights.
