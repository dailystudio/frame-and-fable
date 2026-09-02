# 3D Model Composer (`model-composer`)

An automated Python and Blender pipeline to **fit, scale, rig, skin, animate, and verify** modular 3D character assets (Body, Skeleton Animation, Hair, and Garments) with zero manual intervention.

Outputs production-ready **animated USDZ** (`UsdSkel`), **Blender** (`.blend` with packed textures), **glTF 2.0** (`.glb`), and **FBX** (`.fbx`) files, along with multi-view verification renders and side-by-side comparison sheets against 2D reference concept art.

---

## Features

- **Automated Anatomical Landmark Detection**: Programmatically analyzes body topology to extract head skull dimensions, breast cleavage mid-line, ribcage volume, waist indentation, and hip width.
- **Intelligent Scaling & Alignment**: Automatically normalizes standalone bounding boxes (e.g. $1.9\,\text{m}$ unit hair/dress exports) to accurately fit the character's cranium and torso.
- **Sweetheart & Cleavage Alignment**: Aligns bodice necklines precisely with the breast mid-line and chest contours.
- **Stratified Parametric Skinning**: Uses continuous height-gradient joint weighting to eliminate the polygon tearing and spiking caused by standard nearest-neighbor proximity weight transfer on flared skirts.
- **Native Pixar `UsdSkel` Animation Composition**: Embeds runtime skeletal animation tracks (`UsdSkel.Animation`), skeleton topologies (`UsdSkel.Skeleton`), and per-vertex skinning bindings (`UsdSkel.BindingAPI`) into `.usdz` archives compatible with Apple Quick Look, iOS, Reality Composer, visionOS, and DCC tools.
- **Modular Garment Support**: Handles full dresses (tube gowns), upper tops/shirts, skirts, pants/trousers, and separate two-piece outfits.
- **4-View Turnaround QC & Reference Comparison**: Renders Front, Left-Side, Right-Side, and Back views, automatically building side-by-side composite sheets with concept art.

---

## Requirements & Setup

```bash
# Install host Python dependencies for CLI and composite image rendering:
pip install -r requirements.txt
```

- **Blender 4.0+** (Recommended: Blender 4.2, 4.3, or 4.4)
  - Must be installed on the system (e.g. `/Applications/Blender.app`, `/usr/bin/blender`, or in `PATH`).
  - Contains embedded `bpy` and Pixar `pxr.Usd` / `pxr.UsdSkel` modules out-of-the-box.
- **Python 3.9+**
- **Host Packages** (defined in [`requirements.txt`](file:///Volumes/Workspace/gitrepos/dailystudio/frame-and-fable/xr/model-composer/requirements.txt)):
  - `Pillow>=10.0.0` (for composite side-by-side comparison sheets)
  - `numpy>=1.24.0` (for numerical landmark calculation)
  - `scipy>=1.10.0` (for geometric transformations)

---

## Inputs & Arguments

```bash
python3 auto_combine_models.py [OPTIONS]
```

### 1. Model Inputs
| Argument | Type | Required | Description |
| :--- | :---: | :---: | :--- |
| `--body` | File Path | **Yes** | Base textured character body model (`.usdz`, `.usdc`, `.glb`, `.blend`). |
| `--anim` | File Path | Optional | Skeletal motion/animation track (`.usdc`, `.fbx`, `.glb`). If omitted, uses `--body`'s internal armature. |
| `--hair` | File Path | Optional | Hair mesh model (`.usdz`, `.glb`, `.obj`). |
| `--cloth` | File Path | Optional | Single garment model (e.g., dress, skirt, top) (`.usdz`, `.glb`, `.obj`). |
| `--cloth-type`| Enum | Optional | Garment classification: `auto` *(default)*, `full_dress`, `tube`, `top`, `shirt`, `skirt`, `bottom`, `pants`. |
| `--top` | File Path | Optional | Upper garment model for two-piece outfits (`.usdz`, `.glb`). |
| `--bottom` / `--skirt` | File Path | Optional | Lower garment model for two-piece outfits (`.usdz`, `.glb`). |

### 2. Reference Images (Turnaround QC)
| Argument | Type | Required | Description |
| :--- | :---: | :---: | :--- |
| `--ref-front` | File Path | Optional | Front-view concept reference image (`.png`, `.jpg`). |
| `--ref-right` | File Path | Optional | Right side-view concept reference image (`.png`, `.jpg`). |
| `--ref-left` | File Path | Optional | Left side-view concept reference image (`.png`, `.jpg`). |
| `--ref-back` | File Path | Optional | Back-view concept reference image (`.png`, `.jpg`). |

### 3. Pipeline Configuration
| Argument | Type | Required | Description |
| :--- | :---: | :---: | :--- |
| `--output-dir` | Directory | Optional | Target output directory (Default: `./output_combined`). |
| `--blender-path`| File Path | Optional | Custom path to Blender executable if not in standard system locations. |

---

## Generated Outputs

When execution completes, the target `--output-dir` contains:

```
output_dir/
├── combined_character.usdz       # Production animated USDZ (UsdSkel runtime + textures)
├── combined_character.blend      # Master Blender file (packed textures, 65-bone rig, action)
├── combined_character.glb        # glTF 2.0 binary format with embedded animations
├── combined_character.fbx        # Baked FBX animation
├── pipeline_config.json          # Cached parameter configuration
├── textures/                     # Extracted and deduplicated PBR diffuse/albedo maps
│   ├── body_shaded.png
│   ├── hair_shaded.png
│   └── cloth_shaded.png
└── renders/                      # Multi-view validation renders & comparisons
    ├── render_front.png          # Front orthographic/perspective render
    ├── render_left.png           # Left side-view render
    ├── render_right.png          # Right side-view render
    ├── render_back.png           # Back-view render
    ├── render_anim_greeting.png  # Mid-animation gesture validation render
    ├── compare_front.png         # Side-by-side: Render vs --ref-front
    ├── compare_right.png         # Side-by-side: Render vs --ref-right
    └── compare_back.png          # Side-by-side: Render vs --ref-back
```

---

## Usage Examples

### Example 1: Full Dress with Animation and 3 Reference Images
```bash
python3 auto_combine_models.py \
    --body ./test/body_anim_base.usdz \
    --anim ./test/body_anim_standing_greeting.usdc \
    --hair ./test/hair.usdz \
    --cloth ./test/tube.usdz \
    --ref-front ./test/ref_front.png \
    --ref-right ./test/ref_right.png \
    --ref-back ./test/ref_back.png \
    --output-dir ./test_output
```

### Example 2: Minimal Execution (3D Models Only, No Reference Images)
```bash
python3 auto_combine_models.py \
    --body ./character_base.usdz \
    --anim ./walking_animation.usdc \
    --hair ./hair.usdz \
    --cloth ./gown.usdz \
    --output-dir ./output_walk
```

### Example 3: Modular Two-Piece Outfit (Top + Skirt)
```bash
python3 auto_combine_models.py \
    --body ./body_base.usdz \
    --anim ./dance_motion.usdc \
    --hair ./hair.usdz \
    --top ./blouse.usdz \
    --bottom ./pleated_skirt.usdz \
    --output-dir ./output_dance
```

---

## Core Algorithms & Mathematical Principles

```
  [Raw Assets (USDZ/USDC)]
             │
             ├──► 1. Texture Deduplication & PBR Material Authoring
             ├──► 2. 3D Anatomical Landmark Extraction (Head, Cleavage, Waist, Hips)
             ├──► 3. Geometric Matrix Normalization & Tailored Alignment
             ├──► 4. Stratified Parametric Skinning (Multi-Bone Weight Interpolation)
             └──► 5. Pixar UsdSkel Stage Composition & Multi-View Rendering
```

### 1. 3D Anatomical Landmark Extraction
Rather than relying on 2D image heuristics, the pipeline calculates ground-truth surface landmarks directly from the vertex buffers $\mathbf{V}_{\text{body}} \in \mathbb{R}^{N \times 3}$:

* **Cranial Center & Skull Diameter**:
  $$\mathbf{V}_{\text{head}} = \{ \mathbf{v} \in \mathbf{V}_{\text{body}} \mid v_z > 1.35\,\text{m} \}$$
  $$Z_{\text{crown}} = \max(\mathbf{V}_{\text{head}, z}), \quad W_{\text{skull}} = \max(\mathbf{V}_{\text{head}, x}) - \min(\mathbf{V}_{\text{head}, x})$$
* **Breast Cleavage Mid-line**:
  $$\mathbf{V}_{\text{chest}} = \{ \mathbf{v} \in \mathbf{V}_{\text{body}} \mid 1.05\,\text{m} < v_z < 1.25\,\text{m} \}$$
  Extracts the breast apex $Z_{\text{apex}} \approx 1.175\,\text{m}$ and center cleavage dip $Z_{\text{mid}} \approx 1.135\,\text{m}$.
* **Waistline**:
  Identifies the minimum lateral circumference ring $Z_{\text{waist}} \approx 0.985\,\text{m}$.

---

### 2. Geometric Normalization & Fitting
Raw assets generated by 3D tools are often normalized into unit bounding boxes (e.g. $1.90\,\text{m}$ height). The pipeline applies affine transformation matrices $\mathbf{M} = \mathbf{T} \mathbf{R} \mathbf{S}$:

* **Hair Alignment**: Scales width/depth to match cranium diameter ($S = 0.595, 0.615, 0.595$), applies $-2.5^\circ X$-pitch rotation, and anchors to the skull apex ($T_z = 0.812\,\text{m}$).
* **Bodice & Dress Alignment**: Scales the bodice to match the chest depth and waist ($S = 0.835, 0.895, 0.760$), aligning the sweetheart center dip precisely to $Z_{\text{mid}} = 1.135\,\text{m}$ and extending the skirt hem to floor level ($Z = 0.00\,\text{m}$).

---

### 3. Stratified Parametric Skinning
Standard proximity-based *Data Transfer / Nearest Weight Transfer* fails on flared garments because outer ruffled folds are geometrically closest to thigh and knee vertices. When legs swing, ruffles spike and tear.

The pipeline applies **Height-Stratified Parametric Weighting**:

```
Z >= 1.13m (Upper Bodice):      100% Spine2
1.05m <= Z < 1.13m (Mid-Torso): Linear Blend [Spine2 -> Spine1]
0.98m <= Z < 1.05m (Underbust): Linear Blend [Spine1 -> Spine]
0.88m <= Z < 0.98m (Waistline): Linear Blend [Spine -> Hips]
Z < 0.88m (Flared Skirt):       75% - 80% Hips (Volume Anchor)
                                20% - 25% LeftUpLeg / RightUpLeg (Natural Sway)
```

* **Hair Skinning**: Bound $100\%$ rigidly to `mixamorig_Head` (Joint Index `5`), preserving cranium volume during head turns without rubbery neck stretching.

---

### 4. Native Pixar `UsdSkel` Schema Integration
The pipeline constructs the USD stage using Pixar's `pxr.UsdSkel` specification:
- **`UsdSkel.Root`**: Defines the top-level skeletal transformation context.
- **`UsdSkel.Skeleton`**: Authorizes the 65-bone joint hierarchy.
- **`UsdSkel.Animation`**: Encodes the 154-frame rotation and translation timecodes.
- **`UsdSkel.BindingAPI`**: Sets vertex-interpolated `primvars:skel:jointIndices` (8 influences per vertex) and `primvars:skel:jointWeights`, linked to `UsdPreviewSurface` material shading networks.

---

## Directory Structure

```
model-composer/
├── auto_combine_models.py   # Main automated pipeline script
└── README.md                # Documentation & algorithm reference
```

## License

Internal DailyStudio frame-and-fable XR Toolkit. All rights reserved.
