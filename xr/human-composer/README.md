# Human Composer

A CLI tool powered by Blender to compose, align, and bind accessories (such as hair models) to 3D human body models in USDZ format.

## Key Features

- **Multi-View Reference Alignment**: Leverages 2D multi-angle character reference images (`--ref-front`, `--ref-left`, `--ref-right`, `--ref-back`) to automatically calculate 3D scale, position, depth, and volume offsets so the hair aligns accurately with the head.
- **Full Armature Binding & Rigging**: Binds and parents the hair mesh to the body's skeleton (`Armature`) and paints vertex group weights to `mixamorig_Head`, allowing the hair to deform synchronously with head movements and dancing animations.
- **Texture Conflict Resolution**: Automatically avoids overwrites when both body and hair USDZ models contain same-named textures (such as `textures/shaded.png`) by isolating, renaming, and relinking shader nodes before USDZ export.
- **Headless Blender Automation**: Executes via Blender's background scripting mode without requiring a GUI.

---

## Prerequisites

1. **Python 3.10+**
2. **Blender 4.0+**
   - On macOS: installed at `/Applications/Blender.app` (auto-detected).
   - On Linux/Windows: `blender` in system `PATH`, or set `BLENDER_PATH=/path/to/blender`, or pass `--blender <path>`.

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

### 1. Basic Binding (Geometric Alignment)

If reference images are not available, Human Composer will automatically align the hair to the body's scalp and skull geometry:

```bash
python human-composer.py bind \
  --body path/to/body.usdz \
  --hair path/to/hair.usdz \
  --output path/to/output_bound.usdz
```

---

### 2. Multi-View Reference Alignment (Recommended)

Provide reference images from different angles to achieve precise alignment that matches the character's appearance:

```bash
python human-composer.py bind \
  --body tests/man_anim_base.usdz \
  --hair tests/man_hair.usdz \
  --ref-front tests/man_ref_front.png \
  --ref-left tests/man_ref_left.png \
  --ref-back tests/man_ref_back.png \
  --output tests/man_bound.usdz \
  --preview-dir tests/man_previews
```

#### Female Model Example:

```bash
python human-composer.py bind \
  --body tests/woman_anim_base.usdz \
  --hair tests/woman_hair.usdz \
  --ref-front tests/woman_ref_front.png \
  --ref-right tests/woman_ref_right.png \
  --ref-back tests/woman_ref_back.png \
  --output tests/woman_bound.usdz \
  --preview-dir tests/woman_previews
```

---

## CLI Options

```
usage: human-composer.py bind [-h] --body BODY --hair HAIR
                              [--ref-front REF_FRONT] [--ref-left REF_LEFT]
                              [--ref-right REF_RIGHT] [--ref-back REF_BACK]
                              [--output OUTPUT] [--blender BLENDER]
                              [--preview-dir PREVIEW_DIR]

Required arguments:
  --body BODY           Path to input body USDZ model (contains mesh and armature).
  --hair HAIR           Path to input hair USDZ model.

Reference image arguments (optional):
  --ref-front REF_FRONT Path to front-angle reference image.
  --ref-left REF_LEFT   Path to left-angle reference image.
  --ref-right REF_RIGHT Path to right-angle reference image.
  --ref-back REF_BACK   Path to back-angle reference image.

Output & Configuration:
  --output OUTPUT       Path to output bound USDZ file. Default: <body_stem>_bound.usdz.
  --preview-dir DIR     Directory to save 4-view orthographic verification renders.
  --blender PATH        Path to custom Blender executable (optional).
```

---

## Technical Details

1. **Reference Silhouette Extraction**:
   `core/ref_analyzer.py` samples background colors from reference images, segments foreground silhouettes, and computes character height ($H_{ref}$) and head boundary metrics ($X_{center}, W_{head}, Y_{top}$).
2. **2D-to-3D Scale Mapping**:
   Using the character's 3D height ($H_{3D}$), the analyzer calculates the exact metric conversion:
   $$m/\text{px} = \frac{H_{3D}}{H_{ref}}$$
   This translates 2D pixel widths and offsets into 3D target coordinates ($S_x, S_y, S_z, T_x, T_y, T_z$), accounting for natural volume puff and scalp clearance.
3. **Texture Isolation**:
   `core/blender_binder.py` unpacks both USDZ archives into separate staging directories, renames `shaded.png` to `body_shaded.png` and `hair_shaded.png`, and updates Principled BSDF node trees before re-exporting to avoid collision.
4. **Skeletal Animation Support**:
   The bound hair inherits the body's skeletal hierarchy and is assigned 1.0 weight to `mixamorig_Head`, ensuring hair moves synchronously with animation files (such as `tests/man_anim_hip_hop_dancing.usdc`).

---

## Project Structure

```
human-composer/
├── human-composer.py       # Top-level CLI entry point
├── requirements.txt        # Python dependencies (numpy, Pillow, scipy)
├── core/
│   ├── ref_analyzer.py     # Reference image silhouette & metric extractor
│   └── blender_binder.py   # Headless Blender worker script
└── tests/                  # Sample USDZ models, USDC animations & reference images
```
