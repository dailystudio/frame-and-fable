# Human Composer

A CLI tool powered by Blender to compose, align, and bind accessories (such as hair models) to 3D human body models in USDZ format.

## Key Features

- **Multi-View Reference Alignment**: Leverages 2D multi-angle character reference images (`--ref-front`, `--ref-left`, `--ref-right`, `--ref-back`) to dynamically calculate 3D scale, position, depth, and crown volume offsets so hair fits the skull naturally.
- **Full Armature Binding & Rigging**: Binds and parents the hair mesh to the body's skeleton (`Armature`) and paints vertex group weights to `mixamorig_Head`, allowing hair to deform synchronously with head movement and skeletal animations.
- **Texture Conflict Resolution**: Automatically avoids overwrites when both body and hair USDZ models contain identically named textures (such as `textures/shaded.png`) by isolating, renaming, and relinking shader nodes before USDZ export.
- **Automated Output Suite**: Generates a dedicated subdirectory per model under `outputs/` containing:
  - **Bound USDZ Model**: Ready for AR / XR / 3D scenes.
  - **Static Preview Image (`preview.png`)**: High-resolution rendered preview.
  - **Sequenced Showcase Animation (`preview_animation.mp4`)**:
    1. **360° Turntable**: Full character presentation rotation around the vertical axis.
    2. **180° Head Turn**: Head smoothly rotates left and right with cinematic camera zoom to demonstrate bone binding.
    3. **Skeletal Animation**: Plays the first skeletal animation clip (if present in the model or provided via `--anim`).
  - **Intermediate Comparisons (`intermediates/`)**: Multi-angle renders and side-by-side comparison images against reference photos (via `--intermediate`).
- **Headless Blender Automation**: Executes seamlessly via Blender's background scripting mode without requiring a GUI.

---

## Prerequisites

1. **Python 3.10+**
2. **Blender 4.0+**
   - **macOS**: Installed at `/Applications/Blender.app` (auto-detected).
   - **Linux / Windows**: `blender` in system `PATH`, or set `BLENDER_PATH=/path/to/blender`, or pass `--blender <path>`.

---

## Installation

Clone or navigate to the repository, create a virtual environment, and install dependencies:

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

## Usage

### 1. Basic Binding (Fast USDZ Generation)

By default, binding runs in seconds and outputs the bound USDZ into `outputs/<model_name>/` (inferred from the body filename, e.g. `tests/man_anim_base.usdz` -> `outputs/man/`):

```bash
python human-composer.py bind \
  --body tests/man_anim_base.usdz \
  --hair tests/man_hair.usdz
```

This generates:
- `outputs/man/man_bound.usdz`

#### Adding Previews (`--preview`, `--preview-anim`):
Previews are optional and can be triggered as needed:
```bash
# Generate static preview image
python human-composer.py bind \
  --body tests/man_anim_base.usdz \
  --hair tests/man_hair.usdz \
  --preview

# Generate sequenced showcase preview animation video (MP4)
python human-composer.py bind \
  --body tests/man_anim_base.usdz \
  --hair tests/man_hair.usdz \
  --preview-anim

# Generate both static preview and animation video
python human-composer.py bind \
  --body tests/man_anim_base.usdz \
  --hair tests/man_hair.usdz \
  --preview --preview-anim
```

---

### 2. Multi-View Reference Alignment with Intermediates

Provide multi-angle reference photos and add `--intermediate` to generate side-by-side comparison images:

```bash
python human-composer.py bind \
  --body tests/man_anim_base.usdz \
  --hair tests/man_hair.usdz \
  --ref-front tests/man_ref_front.png \
  --ref-left tests/man_ref_left.png \
  --ref-back tests/man_ref_back.png \
  --intermediate
```

#### Female Model Example:

```bash
python human-composer.py bind \
  --body tests/woman_anim_base.usdz \
  --hair tests/woman_hair.usdz \
  --ref-front tests/woman_ref_front.png \
  --ref-right tests/woman_ref_right.png \
  --ref-back tests/woman_ref_back.png \
  --intermediate
```

---

### 3. Inspecting Model Information (`info`)

Inspect any 3D model (USDZ, USDC, etc.) to list parts, bounding boxes, dimensions, vertices, textures, skeletal armatures, and animation clips:

```bash
# Full model inspection
python human-composer.py info tests/man_anim_base.usdz

# Filter to a specific part (by mesh name, material, 'skeleton', or 'anim')
python human-composer.py info tests/man_anim_base.usdz --part skeleton
python human-composer.py info tests/man_anim_hip_hop_dancing.usdc --part anim
python human-composer.py info outputs/man/man_bound.usdz --part hair

# Output as raw JSON
python human-composer.py info tests/man_anim_base.usdz --json
```

---

## Output Structure

When executing a binding task with `--intermediate`:

```
outputs/
└── man/
    ├── man_bound.usdz            # Bound 3D model with rigged skeleton and distinct textures
    ├── preview.png               # High-res static render
    ├── preview_animation.mp4     # 360-degree turntable video loop
    └── intermediates/            # Generated when --intermediate is passed
        ├── render_front.png
        ├── render_left.png
        ├── render_back.png
        ├── comparison_front.png  # Side-by-side: reference photo vs. 3D render
        ├── comparison_left.png
        └── comparison_back.png
```

---

## CLI Options

```
usage: human-composer.py bind [-h] --body BODY --hair HAIR
                              [--ref-front REF_FRONT] [--ref-left REF_LEFT]
                              [--ref-right REF_RIGHT] [--ref-back REF_BACK]
                              [--output-dir OUTPUT_DIR] [--output OUTPUT]
                              [--name NAME] [--intermediate] [--blender BLENDER]
```

### `bind` Command Options

| Flag | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--body` | Path | *Required* | Path to input human body USDZ model (mesh + armature). |
| `--hair` | Path | *Required* | Path to input hair accessory USDZ model. |
| `--ref-front` | Path | `None` | Path to front-angle reference image. |
| `--ref-left` | Path | `None` | Path to left-angle reference image. |
| `--ref-right` | Path | `None` | Path to right-angle reference image. |
| `--ref-back` | Path | `None` | Path to back-angle reference image. |
| `--output-dir` | Path | `outputs` | Root output directory. A subfolder named after the model will be created inside. |
| `--output` | Path | `None` | Custom explicit destination path (overrides `--output-dir`). |
| `--name` | String | `None` | Custom model name for the subdirectory (default: inferred from `--body`). |
| `--preview` | Flag | `False` | Generate high-resolution static preview render (`preview.png`). |
| `--preview-anim` | Flag | `False` | Generate sequenced showcase preview animation video (`preview_animation.mp4`). |
| `--intermediate` | Flag | `False` | Also output multi-angle renders and side-by-side reference comparison images. |
| `--anim` | Path | `None` | Path to optional skeletal animation file (USDZ/USDC) to play in Phase 3 of preview animation. |
| `--blender` | Path | Auto | Path to custom Blender executable. |

### `info` Command Options

```
usage: human-composer.py info [-h] [--model MODEL] [--part PART] [--json] [--blender BLENDER] [model]
```

| Flag | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `model` / `--model` | Path | *Required* | Path to 3D model file (USDZ, USDC, OBJ, etc.). |
| `--part` | String | `None` | Filter inspection to a specific part/mesh name, material name, part index, or `'skeleton'`. |
| `--json` | Flag | `False` | Output raw inspection metadata in JSON format. |
| `--blender` | Path | Auto | Path to custom Blender executable. |

---

## Technical Details

1. **Dynamic Reference Silhouette Extraction**:
   `core/ref_analyzer.py` samples background colors, segments character silhouettes, and calculates character pixel height ($H_{ref}$), head boundary dimensions ($W_{head}, H_{head}$), and horizontal centers ($X_{center}$).
2. **2D-to-3D Metric Conversion**:
   Using the character's real 3D height ($H_{3D}$), the script derives physical metric conversion:
   $$m/\text{px} = \frac{H_{3D}}{H_{ref}}$$
   This maps 2D pixel proportions directly to 3D bounding transforms ($S_x, S_y, S_z, T_x, T_y, T_z$), with crown volume clearance ($Z \ge Z_{head} + 0.03\text{m}$) and backward depth offsets ($Y \ge Y_{center} + 0.038\text{m}$) to prevent scalp clipping.
3. **Texture Isolation**:
   `core/blender_binder.py` unpacks both USDZ models into isolated staging folders, renames `shaded.png` to `body_shaded.png` and `hair_shaded.png`, and repoints Blender Image datablocks and Principled BSDF nodes before USDZ re-export.
4. **Skeletal Animation Support**:
   The bound hair mesh is parented to the body's armature and assigned 1.0 weight to the `mixamorig_Head` vertex group, enabling seamless deformation during motion and dancing animations (e.g. `tests/man_anim_hip_hop_dancing.usdc`).

---

## Project Structure

```
human-composer/
├── human-composer.py       # Top-level CLI entry point (bind, info)
├── requirements.txt        # Python dependencies (numpy, Pillow, scipy)
├── core/
│   ├── ref_analyzer.py     # Reference silhouette analyzer & metric solver
│   ├── blender_binder.py   # Headless Blender worker script (binding, anti-clipping, video)
│   └── model_inspector.py  # 3D metadata inspector (meshes, bounds, skeleton, animations)
├── outputs/                # Default generated outputs directory
└── tests/                  # Sample test assets (USDZ models, USDC animations, reference photos)
```
