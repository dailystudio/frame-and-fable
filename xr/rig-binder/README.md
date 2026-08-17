# Rig Binder (`rig-binder`): Universal 3D/2D Mesh Rigging, Skinning & Animation Pipeline

**Rig Binder** (`rig-binder`) is an automated, generalized rigging system designed to dynamically bind skeletons, compute proportional anatomical landmarks, assign automatic bone weights (skinning), and export clean, multi-format 3D assets (`.usdz`, `.glb`, `.blend`, `.fbx`).

It supports both **strict 2D planar rigs** (such as Chinese Shadow Play puppets with 19 joints) and **full 3D humanoid mocap rigs** (such as industry-standard 65-joint skeletons with 5-finger hand chains and toes), as well as **custom user-defined rig definitions via JSON**.

---

## 🌟 Key Capabilities

- **Preset 1: Chinese Shadow Play 19-Joint 2D Planar Rig (`shadow-puppet`)**:
  - Pure 19-joint skeleton representing traditional shadow puppetry hinge joints (骨节铰链).
  - Strict 2D planar constraints: bone rolls aligned to screen normal `(0, 1, 0)`, out-of-plane rotation (X & Y) locked, depth translation (Y) locked.
  - Included 100-frame classic performance routine (走场步, 起霸亮相, 抱拳作揖, 回身归位).
- **Preset 2: Standard Humanoid 65-Joint 3D Mocap Rig (`humanoid-65`)**:
  - Full 65-joint humanoid hierarchy compatible with Mixamo, SMPL, and standard game engines.
  - Complete 5-finger articulated hand chains (Thumb, Index, Middle, Ring, Pinky with 3 phalanges each = 30 hand bones).
  - Facial anchors (Eyes, Jaw), multi-segment spine (Spine, Spine1, Spine2, Chest), and articulated feet/toes.
  - Included 100-frame 3D humanoid Walk-to-Run progression routine (Ready Stance $\rightarrow$ Ground Walk Cycle $\rightarrow$ Jog Acceleration $\rightarrow$ Sprint Running $\rightarrow$ Controlled Ease).
- **Preset 3: Streamlined Game Biped 24-Joint Rig (`biped-24`)**:
  - Efficient 24-joint game skeleton without individual finger bones (single hand and foot pivots).
- **Custom Rig Configuration (`--custom-rig <path.json>`)**:
  - Pass any custom JSON skeleton specification defining bone hierarchies, anatomical landmark mapping, tail offsets, and constraint rules.
- **Universal Multi-Format Exporter**:
  - Generates `.usdz`, `.glb`, `.blend`, and `.fbx` assets for both pure rest-pose models and animated performance routines.
- **Automated Visual Previews**:
  - Contact sheet grid (`.png`) and full performance animation MP4 video.

---

## 🦴 Supported Rig Specifications

### 1. Shadow Puppet Rig (`shadow-puppet` / 19 Joints)

| Node Name | Chinese Term | Parent | Primary Function |
| :--- | :--- | :--- | :--- |
| `root` | 全局主根 | `None` | Ground-plane origin & master translation |
| `waist` | 腰 (胯/下身) | `root` | Pelvis & waist articulation |
| `spine` | 脊柱 (胸/上身) | `waist` | Torso tilt and chest posture |
| `neck` | 颈 (脖领) | `spine` | Neck socket pivot |
| `head` | 头 (头茬) | `neck` | Head orientation & nodding |
| `shoulder.L` / `.R` | 左/右肩 | `spine` | Shoulder pivots |
| `upper_arm.L` / `.R` | 左/右大臂 | `shoulder.L/R` | Upper arm segments |
| `elbow.L` / `.R` | 左/右肘 | `upper_arm.L/R` | Elbow hinge connections |
| `wrist.L` / `.R` | 左/右腕 | `elbow.L/R` | Wrist & hand pivots |
| `thigh.L` / `.R` | 左/右大腿 | `waist` | Hip joints |
| `knee.L` / `.R` | 左/右膝 | `thigh.L/R` | Knee hinge connections |
| `ankle.L` / `.R` | 左/右踝 | `knee.L/R` | Ankle & foot pivots |

### 2. Standard Humanoid Rig (`humanoid-65` / 65 Joints)

- **Torso & Head (12 bones)**: `root`, `hips`, `spine`, `spine1`, `spine2`, `chest`, `neck`, `head`, `head_top`, `jaw`, `eye.L`, `eye.R`
- **Left Arm & Hand (19 bones)**: `clavicle.L`, `upper_arm.L`, `forearm.L`, `hand.L`, `thumb.01-03.L`, `index.01-03.L`, `middle.01-03.L`, `ring.01-03.L`, `pinky.01-03.L`
- **Right Arm & Hand (19 bones)**: `clavicle.R`, `upper_arm.R`, `forearm.R`, `hand.R`, `thumb.01-03.R`, `index.01-03.R`, `middle.01-03.R`, `ring.01-03.R`, `pinky.01-03.R`
- **Legs & Feet (15 bones)**: `thigh.L/R`, `calf.L/R`, `foot.L/R`, `toe.L/R`, `toe_end.L/R`

---

## 📋 Environment & Dependencies

1. **Python Virtual Environment (`.venv`)**:
   ```bash
   # Create and activate virtual environment
   python3 -m venv .venv
   source .venv/bin/activate

   # Install dependencies
   pip install -r requirements.txt
   ```

2. **Blender 4.x**: Blender binary installed (e.g. `/Applications/Blender.app/Contents/MacOS/Blender`).

---

## 🚀 Quick Start & Usage

```bash
# 1. Rig standard 3D humanoid model (default humanoid-65 rig, 65 joints, full 5-finger hand articulation)
.venv/bin/python rig_binder.py \
  --model samples/base_basic_shaded.usdz \
  --output-dir outputs/humanoid

# 2. Rig shadow puppet model (19 joints, 2D planar locking + 100-frame shadow play routine)
.venv/bin/python rig_binder.py \
  --model samples/base_basic_shaded.usdz \
  --output-dir outputs/shadow_play \
  --rig-type shadow-puppet

# 3. Rig model with custom user-defined JSON skeleton
.venv/bin/python rig_binder.py \
  --model my_character.glb \
  --output-dir outputs/custom \
  --custom-rig presets/custom_template.json

# 4. Generate only pure rigged USDZ and GLB (skip animation & previews)
.venv/bin/python rig_binder.py \
  --model character.usdz \
  --formats usdz,glb \
  --no-anim
```

---

## ⚙️ Command-Line Arguments

```text
options:
  -h, --help            show this help message and exit
  --model, -m MODEL     (Required) Path to input 3D model file (.usdz, .glb, .gltf, .fbx, .obj)
  --output-dir, -o DIR  Output directory for generated files (default: outputs/)
  --name, -n NAME       Base name for outputs (default: derived from input file name)
  --rig-type, -r TYPE   Preset: 'humanoid-65' (65 joints standard humanoid 3D), 'shadow-puppet' (19 joints, 2D planar), 'biped-24' (24 joints). Default: humanoid-65
  --custom-rig, -c PATH Path to custom user-defined rig configuration JSON file
  --formats, -f FORMATS Comma-separated export formats (usdz, glb, blend, fbx. default: usdz,glb,blend)
  --no-anim             Generate only pure rigged model without animation routine
  --no-preview          Disable generating PNG contact sheet and MP4 preview video
  --blender-path PATH   Custom path to Blender executable binary
```

---

## 📁 Output Deliverables

| Deliverable | Format | Description |
| :--- | :--- | :--- |
| `<name>_rigged.usdz` | USDZ | Pure rigged model in default rest pose |
| `<name>_rigged.glb` | GLTF/GLB | Pure rigged model for Web, Three.js, Babylon.js, Game engines |
| `<name>_rigged.blend` | Blender | Pure rigged Blender project file |
| `<name>_animated.usdz` | USDZ | Model with baked performance routine animation |
| `<name>_animated.glb` | GLTF/GLB | Model with baked performance routine animation |
| `<name>_animated.blend` | Blender | Blender project file with baked action |
| `<name>_preview_grid.png` | PNG Image | 4-stage visual contact sheet preview |
| `<name>_preview_anim.mp4` | MP4 Video | Full 100-frame animation video preview |

---

## 🛠️ Defining Custom Rigs (`--custom-rig`)

Create a JSON file conforming to the specification below (see [`presets/custom_template.json`](file:///Volumes/Workspace/gitrepos/dailystudio/frame-and-fable/xr/rig-binder/presets/custom_template.json)):

```json
{
  "name": "my_custom_rig",
  "type": "standard_3d",
  "joints_count": 4,
  "bones": [
    { "name": "root", "parent": null, "head_key": "root", "tail_offset": [0, 0, 0.1] },
    { "name": "body", "parent": "root", "head_key": "waist", "tail_key": "chest" },
    { "name": "arm.L", "parent": "body", "head_key": "l_shoulder", "tail_key": "l_hand" },
    { "name": "arm.R", "parent": "body", "head_key": "r_shoulder", "tail_key": "r_hand" }
  ]
}
```
